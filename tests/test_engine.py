"""Behavior tests for the linter engine, independent of the real rule catalog."""

import json
import tempfile
import unittest
from pathlib import Path

from support import lint_module

lint = lint_module()


def rule(**overrides):
    base = {
        "id": "AV-TEST-01",
        "title": "Test rule",
        "severity": "warning",
        "targets": ["*.axaml"],
        "check": "line",
        "pattern": r"Watermark=",
        "source": "https://docs.avaloniaui.net/docs/test#anchor",
        "message": "Use PlaceholderText.",
        "bad": '<TextBox Watermark="x" />',
        "good": '<TextBox PlaceholderText="x" />',
    }
    base.update(overrides)
    return lint.Rule.from_dict(base)


AVALONIA_CSPROJ = '<Project><ItemGroup><PackageReference Include="Avalonia" /></ItemGroup></Project>'
PLAIN_CSPROJ = '<Project><ItemGroup><PackageReference Include="Npgsql" /></ItemGroup></Project>'


class ScanTextTests(unittest.TestCase):
    def test_line_check_reports_one_based_line(self):
        findings = lint.scan_text(rule(), "View.axaml", "<Grid>\n  <TextBox Watermark=\"x\" />\n</Grid>")
        self.assertEqual([2], [f.line for f in findings])

    def test_target_glob_limits_files(self):
        self.assertEqual([], lint.scan_text(rule(), "View.cs", 'Watermark="x"'))

    def test_multiline_check_reports_line_of_match_start(self):
        r = rule(check="multiline", pattern=r"<StackPanel>\s*<ListBox")
        findings = lint.scan_text(r, "V.axaml", "<Grid/>\n<StackPanel>\n  <ListBox/>\n</StackPanel>")
        self.assertEqual([2], [f.line for f in findings])

    def test_file_requires_reports_trigger_when_requirement_missing(self):
        r = rule(targets=["*.cs"], check="file-requires", when=r"override void Render\(", pattern=r"AffectsRender")
        text = "class A {\n  public override void Render(DrawingContext c) {}\n}"
        self.assertEqual([2], [f.line for f in lint.scan_text(r, "A.cs", text)])
        self.assertEqual([], lint.scan_text(r, "A.cs", text + "\n// AffectsRender<A>(X);"))

    def test_unless_skips_whole_file(self):
        r = rule(unless=r"x:DataType")
        self.assertEqual([], lint.scan_text(r, "V.axaml", '<UserControl x:DataType="vm:A"><TextBox Watermark="x"/>'))

    def test_inline_disable_on_same_or_previous_line(self):
        same = '<TextBox Watermark="x" /> <!-- avalonia-lint-disable AV-TEST-01 -->'
        previous = '// avalonia-lint-disable AV-TEST-01\n<TextBox Watermark="x" />'
        other_rule = '<!-- avalonia-lint-disable AV-TEST-99 -->\n<TextBox Watermark="x" />'
        self.assertEqual([], lint.scan_text(rule(), "V.axaml", same))
        self.assertEqual([], lint.scan_text(rule(), "V.axaml", previous))
        self.assertEqual(1, len(lint.scan_text(rule(), "V.axaml", other_rule)))

    def test_file_level_disable(self):
        text = '<!-- avalonia-lint-disable-file AV-TEST-01 -->\n<TextBox Watermark="x" />'
        self.assertEqual([], lint.scan_text(rule(), "V.axaml", text))

    def test_manual_rules_never_scan(self):
        self.assertEqual([], lint.scan_text(rule(check="manual", pattern=None), "V.axaml", 'Watermark="x"'))


class RuleValidationTests(unittest.TestCase):
    def test_unknown_check_is_rejected(self):
        with self.assertRaises(ValueError):
            rule(check="magic")

    def test_unknown_severity_is_rejected(self):
        with self.assertRaises(ValueError):
            rule(severity="fatal")

    def test_automatic_rule_needs_pattern(self):
        with self.assertRaises(ValueError):
            rule(pattern=None)


class LintTreeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_excluded_folders_are_skipped(self):
        for folder in ["bin", "obj", ".git", "node_modules", ".claude/worktrees/x", ".claude/skills/avalonia-lint/evals"]:
            self.write(f"{folder}/V.axaml", '<TextBox Watermark="x" />')
        self.write("src/V.axaml", '<TextBox Watermark="x" />')
        findings = lint.lint(self.root, [rule()])
        self.assertEqual(["src/V.axaml"], [f.path for f in findings])

    def test_cs_rules_only_apply_to_avalonia_projects(self):
        r = rule(targets=["*.cs"], pattern=r"GetAwaiter\(\)\.GetResult\(\)")
        self.write("src/Desktop/Desktop.csproj", AVALONIA_CSPROJ)
        self.write("src/Desktop/App.cs", "x.GetAwaiter().GetResult();")
        self.write("src/Api/Api.csproj", PLAIN_CSPROJ)
        self.write("src/Api/Mail.cs", "x.GetAwaiter().GetResult();")
        self.assertEqual(["src/Desktop/App.cs"], [f.path for f in lint.lint(self.root, [r])])

    def test_scope_any_applies_everywhere(self):
        r = rule(targets=["*.cs"], pattern=r"Thread\.Sleep", scope="any")
        self.write("src/Api/Api.csproj", PLAIN_CSPROJ)
        self.write("src/Api/Mail.cs", "Thread.Sleep(1);")
        self.assertEqual(1, len(lint.lint(self.root, [r])))

    def test_project_requires_looks_across_the_project(self):
        r = rule(targets=["*.cs"], check="project-requires", when=r"StartWithClassicDesktopLifetime",
                 pattern=r"UnhandledException")
        self.write("app/App.csproj", AVALONIA_CSPROJ)
        self.write("app/Program.cs", "BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);")
        self.assertEqual(["app/Program.cs"], [f.path for f in lint.lint(self.root, [r])])
        self.write("app/App.axaml.cs", "Dispatcher.UIThread.UnhandledException += OnError;")
        self.assertEqual([], lint.lint(self.root, [r]))

    def test_config_disable_and_ignore_with_reason(self):
        self.write("src/A.axaml", '<TextBox Watermark="x" />')
        self.write("src/B.axaml", '<TextBox Watermark="x" />')
        config = lint.Config.from_dict({"ignore": [{"rule": "AV-TEST-01", "path": "src/A.axaml", "reason": "legacy"}]})
        self.assertEqual(["src/B.axaml"], [f.path for f in lint.lint(self.root, [rule()], config)])
        config = lint.Config.from_dict({"disable": ["AV-TEST-01"]})
        self.assertEqual([], lint.lint(self.root, [rule()], config))

    def test_ignore_without_reason_is_rejected(self):
        with self.assertRaises(ValueError):
            lint.Config.from_dict({"ignore": [{"rule": "AV-TEST-01", "path": "src/A.axaml"}]})

    def test_ignore_path_accepts_glob(self):
        self.write("src/Views/A.axaml", '<TextBox Watermark="x" />')
        config = lint.Config.from_dict({"ignore": [{"rule": "AV-TEST-01", "path": "src/Views/*.axaml", "reason": "x"}]})
        self.assertEqual([], lint.lint(self.root, [rule()], config))


class MainTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.rules = self.root / "rules.json"
        self.rules.write_text(json.dumps({"rules": [rule().to_dict()]}), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def run_main(self, *args):
        return lint.main([str(self.project), "--rules", str(self.rules), *args], out=_Sink())

    def test_exit_code_follows_fail_on(self):
        (self.project / "V.axaml").write_text('<TextBox Watermark="x" />', encoding="utf-8")
        self.assertEqual(0, self.run_main())  # warning, default fail-on=error
        self.assertEqual(1, self.run_main("--fail-on", "warning"))

    def test_clean_project_exits_zero(self):
        self.assertEqual(0, self.run_main("--fail-on", "info"))

    def test_config_file_is_read_from_project_root(self):
        (self.project / "V.axaml").write_text('<TextBox Watermark="x" />', encoding="utf-8")
        (self.project / ".avalonia-lint.json").write_text(json.dumps({"disable": ["AV-TEST-01"]}), encoding="utf-8")
        self.assertEqual(0, self.run_main("--fail-on", "info"))

    def test_json_output_lists_findings(self):
        (self.project / "V.axaml").write_text('<TextBox Watermark="x" />', encoding="utf-8")
        sink = _Sink()
        lint.main([str(self.project), "--rules", str(self.rules), "--format", "json"], out=sink)
        data = json.loads(sink.text)
        self.assertEqual("AV-TEST-01", data["findings"][0]["rule"])
        self.assertEqual(1, data["findings"][0]["line"])

    def test_manual_lists_only_manual_rules(self):
        manual = rule(id="AV-TEST-02", check="manual", pattern=None, title="Check by hand").to_dict()
        self.rules.write_text(json.dumps({"rules": [rule().to_dict(), manual]}), encoding="utf-8")
        sink = _Sink()
        self.assertEqual(0, lint.main(["--manual", "--rules", str(self.rules)], out=sink))
        self.assertIn("AV-TEST-02", sink.text)
        self.assertNotIn("AV-TEST-01", sink.text)


class _Sink:
    def __init__(self):
        self.text = ""

    def write(self, value):
        self.text += value


if __name__ == "__main__":
    unittest.main()
