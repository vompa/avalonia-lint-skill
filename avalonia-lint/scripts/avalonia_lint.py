#!/usr/bin/env python3
"""avalonia-lint: check an Avalonia 12 project against rules derived from the official documentation.

Usage:
    python avalonia_lint.py <project-root> [--format text|json] [--fail-on error|warning|info|never]
    python avalonia_lint.py --manual            # checklist of rules that need human or Claude judgment

Only the Python standard library is used. The rule catalog is rules.json next to this script's folder.
Exceptions live in <project-root>/.avalonia-lint.json or in inline comments:
    // avalonia-lint-disable AV-XXX-01        (this line or the next one, C#)
    <!-- avalonia-lint-disable AV-XXX-01 -->  (this line or the next one, XAML)
    avalonia-lint-disable-file AV-XXX-01      (anywhere in the file, whole file)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

SEVERITIES = ("info", "warning", "error")
CHECKS = ("line", "multiline", "file-requires", "project-requires", "manual")
SCOPES = ("avalonia", "any")
EXCLUDED_DIRS = {"bin", "obj", ".git", ".vs", ".idea", "node_modules", "__pycache__"}
# Claude Code folder: worktrees are copies of the repository, skills hold sample files (this skill's evals).
EXCLUDED_PATHS = (".claude",)
MAX_FILE_BYTES = 2_000_000
CONFIG_FILE = ".avalonia-lint.json"
DEFAULT_RULES = Path(__file__).resolve().parent.parent / "rules.json"

_DISABLE_LINE = re.compile(r"avalonia-lint-disable(?!-file)\s+([A-Z0-9][A-Z0-9\-,\s]*)")
_DISABLE_FILE = re.compile(r"avalonia-lint-disable-file\s+([A-Z0-9][A-Z0-9\-,\s]*)")
_AVALONIA_REFERENCE = re.compile(r"Include=\"Avalonia(\.|\")")


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    severity: str
    targets: tuple[str, ...]
    check: str
    source: str
    message: str
    bad: str = ""
    good: str = ""
    pattern: str | None = None
    when: str | None = None
    unless: str | None = None
    scope: str = "avalonia"
    derived: bool = False
    ignore_case: bool = False
    _compiled: dict = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        rule = cls(
            id=data["id"],
            title=data["title"],
            severity=data["severity"],
            targets=tuple(data["targets"]),
            check=data["check"],
            source=data["source"],
            message=data["message"],
            bad=data.get("bad", ""),
            good=data.get("good", ""),
            pattern=data.get("pattern"),
            when=data.get("when"),
            unless=data.get("unless"),
            scope=data.get("scope", "avalonia"),
            derived=bool(data.get("derived", False)),
            ignore_case=bool(data.get("ignore_case", False)),
        )
        rule._validate()
        return rule

    def to_dict(self) -> dict:
        data = {
            "id": self.id, "title": self.title, "severity": self.severity, "targets": list(self.targets),
            "check": self.check, "source": self.source, "message": self.message,
            "bad": self.bad, "good": self.good, "scope": self.scope, "derived": self.derived,
        }
        for key in ("pattern", "when", "unless"):
            if getattr(self, key) is not None:
                data[key] = getattr(self, key)
        if self.ignore_case:
            data["ignore_case"] = True
        return data

    def _validate(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"{self.id}: unknown severity {self.severity!r}")
        if self.check not in CHECKS:
            raise ValueError(f"{self.id}: unknown check {self.check!r}")
        if self.scope not in SCOPES:
            raise ValueError(f"{self.id}: unknown scope {self.scope!r}")
        if not self.targets:
            raise ValueError(f"{self.id}: targets must not be empty")
        if self.check != "manual" and not self.pattern:
            raise ValueError(f"{self.id}: check {self.check!r} needs a pattern")
        if self.check in ("file-requires", "project-requires") and not self.when:
            raise ValueError(f"{self.id}: check {self.check!r} needs 'when'")
        for key in ("pattern", "when", "unless"):
            if getattr(self, key) is not None:
                self.regex(key)  # raises re.error on a broken pattern

    def regex(self, key: str) -> re.Pattern:
        if key not in self._compiled:
            flags = re.MULTILINE | (re.IGNORECASE if self.ignore_case else 0)
            self._compiled[key] = re.compile(getattr(self, key), flags)
        return self._compiled[key]

    def applies_to(self, relative_path: str) -> bool:
        name = PurePosixPath(relative_path).name
        for target in self.targets:
            if "/" in target:
                if fnmatch(relative_path, target) or fnmatch(relative_path, target.replace("**/", "")):
                    return True
            elif fnmatch(name, target):
                return True
        return False


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    path: str
    line: int
    title: str
    message: str
    source: str

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    def to_text(self) -> str:
        return f"{self.path}:{self.line}: {self.severity} {self.rule} {self.title}: {self.message} ({self.source})"


@dataclass(frozen=True)
class Ignore:
    rule: str
    path: str
    reason: str


@dataclass
class Config:
    disable: set[str] = field(default_factory=set)
    ignore: list[Ignore] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        ignores = []
        for entry in data.get("ignore", []):
            if not entry.get("reason", "").strip():
                raise ValueError(f"{CONFIG_FILE}: ignore entry for {entry.get('rule')} needs a reason")
            ignores.append(Ignore(entry["rule"], entry["path"].replace("\\", "/"), entry["reason"]))
        return cls(disable=set(data.get("disable", [])), ignore=ignores)

    @classmethod
    def load(cls, root: Path) -> "Config":
        path = root / CONFIG_FILE
        if not path.is_file():
            return cls()
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def allows(self, finding: Finding) -> bool:
        if finding.rule in self.disable:
            return False
        return not any(i.rule == finding.rule and fnmatch(finding.path, i.path) for i in self.ignore)


def load_rules(path: Path | str = DEFAULT_RULES) -> list[Rule]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Rule.from_dict(entry) for entry in data["rules"]]


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _ids(match_text: str) -> set[str]:
    return {part for part in re.split(r"[\s,]+", match_text) if part}


def _file_disabled(rule: Rule, text: str) -> bool:
    return any(rule.id in _ids(m.group(1)) for m in _DISABLE_FILE.finditer(text))


def _line_disabled(rule: Rule, lines: list[str], line: int) -> bool:
    for index in (line - 1, line - 2):  # same line, previous line (0-based indexes)
        if 0 <= index < len(lines):
            match = _DISABLE_LINE.search(lines[index])
            if match and rule.id in _ids(match.group(1)):
                return True
    return False


def _finding(rule: Rule, path: str, line: int) -> Finding:
    return Finding(rule.id, rule.severity, path, line, rule.title, rule.message, rule.source)


def _raw_lines(rule: Rule, text: str) -> list[int]:
    if rule.check == "line":
        pattern = rule.regex("pattern")
        return [i for i, line in enumerate(text.splitlines(), 1) if pattern.search(line)]
    if rule.check == "multiline":
        return [_line_of(text, m.start()) for m in rule.regex("pattern").finditer(text)]
    if rule.check == "file-requires":
        trigger = rule.regex("when").search(text)
        if trigger and not rule.regex("pattern").search(text):
            return [_line_of(text, trigger.start())]
    return []


def _filter(rule: Rule, path: str, text: str, raw: list[int]) -> list[Finding]:
    if not raw or _file_disabled(rule, text):
        return []
    lines = text.splitlines()
    return [_finding(rule, path, n) for n in sorted(set(raw)) if not _line_disabled(rule, lines, n)]


def scan_text(rule: Rule, path: str, text: str) -> list[Finding]:
    """Check one file's text against one rule (all checks except project-requires and manual)."""
    if rule.check in ("manual", "project-requires") or not rule.applies_to(path):
        return []
    if rule.unless and rule.regex("unless").search(text):
        return []
    return _filter(rule, path, text, _raw_lines(rule, text))


def scan_project_text(rule: Rule, files: dict[str, str]) -> list[Finding]:
    """project-requires: if a target file matches `when`, some target file of the project must match `pattern`."""
    targets = {path: text for path, text in files.items() if rule.applies_to(path)}
    if any(rule.regex("pattern").search(text) for text in targets.values()):
        return []
    findings = []
    for path, text in targets.items():
        trigger = rule.regex("when").search(text)
        if trigger:
            findings += _filter(rule, path, text, [_line_of(text, trigger.start())])
    return findings


def _excluded(relative_dir: str) -> bool:
    return any(relative_dir == p or relative_dir.startswith(p + "/") for p in EXCLUDED_PATHS)


def _walk(root: Path) -> list[str]:
    files = []
    for directory, subdirs, names in os.walk(root):
        relative = Path(directory).relative_to(root).as_posix()
        prefix = "" if relative == "." else relative + "/"
        subdirs[:] = [d for d in subdirs if d not in EXCLUDED_DIRS and not _excluded(prefix + d)]
        files += [prefix + name for name in names]
    return sorted(files)


def _project_of(path: str, project_dirs: list[str]) -> str | None:
    """The nearest folder above `path` that holds a .csproj ('.' for the root), None when there is none."""
    parents = [p.as_posix() for p in PurePosixPath(path).parents]
    return next((p for p in parents if p in project_dirs), None)


def _read(root: Path, path: str) -> str | None:
    full = root / path
    try:
        if full.stat().st_size > MAX_FILE_BYTES:
            return None
        return full.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def lint(root: Path | str, rules: list[Rule], config: Config | None = None) -> list[Finding]:
    root = Path(root)
    config = config or Config()
    active = [r for r in rules if r.check != "manual" and r.id not in config.disable]
    paths = [p for p in _walk(root) if p.endswith(".csproj") or any(r.applies_to(p) for r in active)]
    texts = {p: t for p in paths if (t := _read(root, p)) is not None}

    csprojs = [p for p in texts if p.endswith(".csproj")]
    project_dirs = sorted({PurePosixPath(p).parent.as_posix() for p in csprojs}, key=len, reverse=True)
    avalonia_dirs = {PurePosixPath(p).parent.as_posix() for p in csprojs if _AVALONIA_REFERENCE.search(texts[p])}

    def in_scope(rule: Rule, path: str) -> bool:
        if rule.scope == "any" or not path.endswith(".cs"):
            return True
        project = _project_of(path, project_dirs)
        return project in avalonia_dirs if project is not None else not csprojs

    findings: list[Finding] = []
    for rule in active:
        scoped = {p: t for p, t in texts.items() if rule.applies_to(p) and in_scope(rule, p)}
        if rule.check == "project-requires":
            groups: dict[str | None, dict[str, str]] = {}
            for path, text in scoped.items():
                groups.setdefault(_project_of(path, project_dirs), {})[path] = text
            for group in groups.values():
                findings += scan_project_text(rule, group)
        else:
            for path, text in scoped.items():
                findings += scan_text(rule, path, text)

    findings = [f for f in findings if config.allows(f)]
    return sorted(findings, key=lambda f: (f.path, f.line, f.rule))


def _manual_checklist(rules: list[Rule]) -> str:
    lines = ["# avalonia-lint manual checklist", ""]
    for rule in (r for r in rules if r.check == "manual"):
        derived = " (derived)" if rule.derived else ""
        lines.append(f"- [ ] {rule.id} [{rule.severity}] {rule.title}{derived}: {rule.message} ({rule.source})")
    return "\n".join(lines) + "\n"


def _summary(findings: list[Finding]) -> str:
    counts = {s: sum(1 for f in findings if f.severity == s) for s in reversed(SEVERITIES)}
    return f"{len(findings)} finding(s): " + ", ".join(f"{n} {s}" for s, n in counts.items())


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    parser = argparse.ArgumentParser(description="Lint an Avalonia 12 project against the documentation rules.")
    parser.add_argument("project", nargs="?", help="project or repository root")
    parser.add_argument("--rules", default=str(DEFAULT_RULES), help="rule catalog (default: rules.json of the skill)")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--fail-on", choices=(*SEVERITIES, "never"), default="error",
                        help="exit with 1 when a finding has at least this severity (default: error)")
    parser.add_argument("--manual", action="store_true", help="print the checklist of manual rules and exit")
    parser.add_argument("--config", help=f"exception file (default: <project>/{CONFIG_FILE})")
    args = parser.parse_args(argv)

    rules = load_rules(args.rules)
    if args.manual:
        out.write(_manual_checklist(rules))
        return 0
    if not args.project:
        parser.error("a project root is required unless --manual is given")

    root = Path(args.project).resolve()
    if args.config:
        config = Config.from_dict(json.loads(Path(args.config).read_text(encoding="utf-8")))
    else:
        config = Config.load(root)
    findings = lint(root, rules, config)

    if args.format == "json":
        payload = {"findings": [f.to_dict() for f in findings], "summary": _summary(findings)}
        out.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    else:
        for finding in findings:
            out.write(finding.to_text() + "\n")
        out.write(_summary(findings) + "\n")

    if args.fail_on == "never":
        return 0
    threshold = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f.severity) >= threshold for f in findings) else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
