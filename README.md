# avalonia-lint

A Claude Code skill that lints Avalonia 12 apps against the official [Avalonia documentation](https://docs.avaloniaui.net) and reports what does not fit, each finding with a link to the page that states the rule.

- **Rule catalog** ([avalonia-lint/rules.json](avalonia-lint/rules.json)): id, severity, file targets, a regex check or a manual check, source link, message, and a wrong/right example per rule.
- **Linter** ([avalonia-lint/scripts/avalonia_lint.py](avalonia-lint/scripts/avalonia_lint.py)): Python 3.10+, standard library only. Scans AXAML, C# and project files, skips build output, and runs C# rules only in projects that reference Avalonia.
- **Manual checklist**: rules that need judgment, printed with `--manual` and applied by Claude while reading the code.
- **Skill** ([avalonia-lint/SKILL.md](avalonia-lint/SKILL.md)): when Claude loads it, how findings are judged, how waivers work.

## Use

Install as a plugin from this repository (marketplace `vompa-skills`), or copy the `avalonia-lint` folder into `.claude/skills/` of your project. Then ask Claude to "lint the Avalonia app" or run the script yourself:

```bash
python avalonia-lint/scripts/avalonia_lint.py path/to/your/repo
python avalonia-lint/scripts/avalonia_lint.py path/to/your/repo --format json --fail-on warning
python avalonia-lint/scripts/avalonia_lint.py --manual
```

Exit code 1 when a finding reaches the `--fail-on` threshold (default `error`), so the script can run in CI.

Deliberate deviations go into `.avalonia-lint.json` in the project root (`disable` list, `ignore` entries with `rule`, `path` glob and a required `reason`) or into an inline comment `avalonia-lint-disable AV-XXX`. Details in [SKILL.md](avalonia-lint/SKILL.md#waivers).

## How the catalog was built

All pages of the Avalonia documentation (excluding the generated API reference) were read for Avalonia 12.1. Rule candidates were consolidated, duplicates merged, claims about API names checked against the XML documentation of the Avalonia 12.1.4 NuGet packages, and every automatic rule was run against a real Avalonia 12 application to remove false positives. Contradictions inside the documentation are listed in [doc-conflicts.md](avalonia-lint/references/doc-conflicts.md).

The catalog is an independent, paraphrased summary. It is not affiliated with or endorsed by AvaloniaUI OÜ. For design rules (Fluent 2, spacing, states, accessibility patterns) see the companion skill [fluent2-avalonia](https://github.com/vompa/fluent2-avalonia-skill), whose [Avalonia 12 notes](https://github.com/vompa/fluent2-avalonia-skill/blob/main/fluent2-avalonia/references/avalonia-12-notes.md) cover v11 names and migration pitfalls from a design angle.

## Develop

```bash
python scripts/validate.py                                # skill structure, links, evals, catalog
python -m unittest discover -s tests -p "test_*.py"      # engine tests, bad/good example of every rule
python scripts/check_catalog.py some-fragment.json        # check a catalog fragment
```

Every automatic rule must flag its `bad` example and stay quiet on its `good` example; the tests enforce it.

## License

[MIT](LICENSE). Privacy: [PRIVACY.md](PRIVACY.md).
