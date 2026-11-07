"""Every automatic rule in the catalog must flag its `bad` example and stay quiet on its `good` example."""

import unittest

from support import RULES_PATH, lint_module

lint = lint_module()
RULES = lint.load_rules(RULES_PATH)


def sample_name(rule):
    """A file name that matches the rule's first target glob."""
    target = rule.targets[0]
    return target.replace("**/", "").replace("*", "Sample")


class CatalogExampleTests(unittest.TestCase):
    def test_catalog_is_not_empty(self):
        self.assertGreater(len(RULES), 50)

    def test_ids_are_unique(self):
        ids = [r.id for r in RULES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_sample_name_matches_target(self):
        for rule in RULES:
            with self.subTest(rule=rule.id):
                self.assertTrue(rule.applies_to(sample_name(rule)), sample_name(rule))

    def test_bad_example_is_flagged(self):
        for rule in RULES:
            if rule.check in ("manual", "project-requires"):
                continue
            with self.subTest(rule=rule.id):
                self.assertTrue(lint.scan_text(rule, sample_name(rule), rule.bad), rule.bad)

    def test_good_example_is_clean(self):
        for rule in RULES:
            if rule.check in ("manual", "project-requires"):
                continue
            with self.subTest(rule=rule.id):
                self.assertEqual([], lint.scan_text(rule, sample_name(rule), rule.good), rule.good)

    def test_project_rules_check_bad_and_good_as_single_file(self):
        for rule in RULES:
            if rule.check != "project-requires":
                continue
            with self.subTest(rule=rule.id):
                self.assertTrue(lint.scan_project_text(rule, {sample_name(rule): rule.bad}))
                self.assertEqual([], lint.scan_project_text(rule, {sample_name(rule): rule.good}))


if __name__ == "__main__":
    unittest.main()
