---
name: avalonia-lint
description: Lints Avalonia 12 apps (AXAML, C#, csproj and props files) against the official Avalonia documentation and reports what does not fit, each finding with a doc link. Use this skill whenever the user asks to check, lint, review or audit an Avalonia app or a change to one, before a pull request that touches Avalonia views, styles, custom controls, ViewModels, App startup or project files, after upgrading from Avalonia 11, or when asking "what does the Avalonia documentation say about this code". Runs a standard-library Python linter with a rule catalog, then walks a manual checklist for rules that need judgment. Not for design and Fluent styling questions (use fluent2-avalonia), and not for WPF, WinUI or MAUI.
---

# Avalonia Lint

This skill checks an Avalonia 12 app against the official documentation at https://docs.avaloniaui.net. Every rule in [rules.json](rules.json) has a source link, a severity, a short message and a wrong/right example. Rules come in two kinds:

- **automatic**: a regex check that the script runs (`line`, `multiline`, `file-requires`, `project-requires`);
- **manual**: rules that need judgment (intent, data sizes, several places in the code). The script prints them as a checklist; you apply them by reading the code.

The catalog is a paraphrased, independent summary of the documentation. Where the documentation contradicts itself, [doc-conflicts.md](references/doc-conflicts.md) records which reading the catalog follows.

## Workflow

1. **Run the linter** on the repository or project root:

   ```bash
   python <skill-dir>/scripts/avalonia_lint.py <project-root>
   ```

   Options: `--format json`, `--fail-on error|warning|info|never` (default `error`; exit code 1 when a finding reaches the threshold), `--rules <catalog>`, `--config <file>`.
   The script skips `bin`, `obj`, `.git`, `.vs`, `.idea`, `node_modules` and `.claude/worktrees`. C# rules only run in projects whose `.csproj` references Avalonia, so a web API in the same repository is not flagged.

2. **Judge every finding.** A regex cannot see intent. For each hit open the code and decide:
   - *real*: report it with file, line, rule id, the documentation link and the fix from the rule;
   - *deliberate*: the code has a documented reason (a comment, a test, an ADR). Suggest a waiver (below), do not "fix" it;
   - *false positive*: say so and name the rule, so the catalog can be sharpened.

3. **Walk the manual checklist** for the areas the task touched:

   ```bash
   python <skill-dir>/scripts/avalonia_lint.py --manual
   ```

   Pick the rules that match the changed files (views, custom controls, startup, threading, tests, deployment) and check them by reading the code. Do not paste the whole checklist into the report.

4. **Report** grouped by severity: errors first, then warnings, then info. Per finding: `path:line`, rule id and title, one sentence on what is wrong, the fix, the source link. End with what was not checked (for example, runtime behavior or platforms the project does not target).

## Waivers

A deliberate deviation gets a waiver, never a silent ignore. Three forms:

- `.avalonia-lint.json` in the project root:

  ```json
  {
    "disable": ["AV-CTL-34"],
    "ignore": [
      {"rule": "AV-APP-07", "path": "src/App/ScheduledBackup.cs", "reason": "runs before Avalonia starts, no UI thread"}
    ]
  }
  ```

  `path` is a glob relative to the root; `reason` is required.
- inline on the same or the previous line: `// avalonia-lint-disable AV-APP-07` (C#) or `<!-- avalonia-lint-disable AV-BIND-04 -->` (AXAML);
- for a whole file: `avalonia-lint-disable-file AV-XXX`.

Prefer the config file: the reason is reviewed with the code.

## Rules of conduct

- Severity `error` means the documentation states it breaks the build or runtime, or a clear rule is broken. `warning` is a likely defect. `info` is advice; rules marked `derived` are inferred from examples and never above `info`.
- Licensed components (Avalonia Pro, Enterprise, Charts, TreeDataGrid, PdfViewer): point out the license requirement, never add a license key or a package on your own.
- Do not change code to satisfy a rule without the user asking for fixes. The linter reports; the user decides.
- When a rule looks wrong for Avalonia 12.1, check the API in the XML docs of the installed NuGet package (`~/.nuget/packages/avalonia/<version>/lib/*/Avalonia*.xml`) before reporting it, and mention the doubt.
