#!/usr/bin/env python3
"""Validate the skill package: SKILL.md frontmatter, local Markdown links, evals.json and the rule catalog.

Usage: python scripts/validate.py   (exit code 1 on any problem)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "avalonia-lint"
SKILL_NAME = "avalonia-lint"
MAX_DESCRIPTION = 1024
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_catalog  # noqa: E402  (sibling script)


def check_frontmatter() -> list[str]:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return ["SKILL.md: missing YAML frontmatter"]
    fields = dict(
        line.split(":", 1) for line in match.group(1).splitlines() if ":" in line
    )
    problems = []
    if fields.get("name", "").strip() != SKILL_NAME:
        problems.append(f"SKILL.md: name must be {SKILL_NAME}")
    description = fields.get("description", "").strip()
    if not description:
        problems.append("SKILL.md: description is missing")
    elif len(description) > MAX_DESCRIPTION:
        problems.append(f"SKILL.md: description longer than {MAX_DESCRIPTION} characters")
    return problems


def check_links() -> list[str]:
    problems = []
    for md in [*REPO_ROOT.glob("*.md"), *SKILL_DIR.rglob("*.md")]:
        for target in LINK.findall(md.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path = (md.parent / target.split("#", 1)[0]).resolve()
            if not path.exists():
                problems.append(f"{md.relative_to(REPO_ROOT)}: broken link {target}")
    return problems


def check_evals() -> list[str]:
    path = SKILL_DIR / "evals" / "evals.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    if data.get("skill_name") != SKILL_NAME:
        problems.append(f"evals.json: skill_name must be {SKILL_NAME}")
    evals = data.get("evals") or []
    if not evals:
        problems.append("evals.json: no evals")
    ids = [e.get("id") for e in evals]
    if len(ids) != len(set(ids)):
        problems.append("evals.json: duplicate ids")
    for entry in evals:
        for key in ("id", "prompt", "expected_output"):
            if not entry.get(key):
                problems.append(f"evals.json: eval {entry.get('id')} misses {key}")
        for name in entry.get("files", []):
            if not (SKILL_DIR / "evals" / name).exists():
                problems.append(f"evals.json: eval {entry.get('id')} file not found: {name}")
    return problems


def check_rules() -> list[str]:
    lint = check_catalog.load_linter()
    entries = json.loads(check_catalog.DEFAULT_CATALOG.read_text(encoding="utf-8"))["rules"]
    problems, seen = [], set()
    for entry in entries:
        if entry.get("id") in seen:
            problems.append(f"rules.json: duplicate id {entry.get('id')}")
        seen.add(entry.get("id"))
        problems += [f"rules.json: {p}" for p in check_catalog.check_entry(lint, entry)]
    return problems


def main() -> int:
    problems = check_frontmatter() + check_links() + check_evals() + check_rules()
    for problem in problems:
        print(problem)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
