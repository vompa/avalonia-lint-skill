#!/usr/bin/env python3
"""Check rule catalog files: schema, unique ids, and that each automatic rule flags `bad` but not `good`.

Usage: python scripts/check_catalog.py [catalog.json ...]   (default: avalonia-lint/rules.json)
Each file holds {"rules": [...]} in the format of avalonia-lint/rules.json. Exit code 1 on any problem.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LINTER = REPO_ROOT / "avalonia-lint" / "scripts" / "avalonia_lint.py"
DEFAULT_CATALOG = REPO_ROOT / "avalonia-lint" / "rules.json"
REQUIRED = ("id", "title", "severity", "targets", "check", "source", "message")
SOURCE_PREFIX = "https://docs.avaloniaui.net/"


def load_linter():
    spec = importlib.util.spec_from_file_location("avalonia_lint", LINTER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["avalonia_lint"] = module
    spec.loader.exec_module(module)
    return module


def sample_name(targets: list[str]) -> str:
    return targets[0].replace("**/", "").replace("*", "Sample")


def check_entry(lint, entry: dict) -> list[str]:
    rule_id = entry.get("id", "<no id>")
    missing = [key for key in REQUIRED if not entry.get(key)]
    if missing:
        return [f"{rule_id}: missing {', '.join(missing)}"]
    if not entry["source"].startswith(SOURCE_PREFIX):
        return [f"{rule_id}: source must start with {SOURCE_PREFIX}"]
    try:
        rule = lint.Rule.from_dict(entry)
    except Exception as error:  # schema or regex error, reported per rule
        return [f"{rule_id}: {error}"]
    if rule.check == "manual":
        return []
    if not rule.bad or not rule.good:
        return [f"{rule_id}: automatic rules need 'bad' and 'good' examples"]
    name = sample_name(list(rule.targets))
    if rule.check == "project-requires":
        hits_bad = lint.scan_project_text(rule, {name: rule.bad})
        hits_good = lint.scan_project_text(rule, {name: rule.good})
    else:
        hits_bad = lint.scan_text(rule, name, rule.bad)
        hits_good = lint.scan_text(rule, name, rule.good)
    problems = []
    if not hits_bad:
        problems.append(f"{rule_id}: 'bad' example is not flagged")
    if hits_good:
        problems.append(f"{rule_id}: 'good' example is flagged")
    return problems


def main(argv: list[str]) -> int:
    lint = load_linter()
    files = [Path(a) for a in argv] or [DEFAULT_CATALOG]
    problems, seen, total = [], {}, 0
    for path in files:
        entries = json.loads(path.read_text(encoding="utf-8"))["rules"]
        for entry in entries:
            total += 1
            rule_id = entry.get("id")
            if rule_id in seen:
                problems.append(f"{rule_id}: duplicate id (also in {seen[rule_id]})")
            seen[rule_id] = path.name
            problems += check_entry(lint, entry)
    for problem in problems:
        print(problem)
    print(f"{total} rule(s) checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
