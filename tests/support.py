"""Shared helpers for the tests: load the linter module from the skill folder."""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "avalonia-lint"
LINTER_PATH = SKILL_DIR / "scripts" / "avalonia_lint.py"
RULES_PATH = SKILL_DIR / "rules.json"


def lint_module():
    """Import avalonia_lint.py; the skill folder name contains a hyphen, so a plain import does not work."""
    if "avalonia_lint" in sys.modules:
        return sys.modules["avalonia_lint"]
    spec = importlib.util.spec_from_file_location("avalonia_lint", LINTER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["avalonia_lint"] = module
    spec.loader.exec_module(module)
    return module
