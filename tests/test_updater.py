"""
Offline unit tests for the self-updater's pure logic.

Covers semantic-version parsing/comparison, installed-version reading, the manifest
add/remove diff, and preserve-list exclusion. No network or filesystem mutation of the
install — these exercise the deterministic helpers only.

Run with:  python -m unittest tests.test_updater
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import updater  # noqa: E402


class ParseVersionTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(updater.parse_version("1.2.0"), (1, 2, 0))

    def test_strips_leading_v(self):
        self.assertEqual(updater.parse_version("v1.2"), (1, 2))
        self.assertEqual(updater.parse_version("V3.4.5"), (3, 4, 5))

    def test_stops_at_non_numeric_component(self):
        # Irregular Cisco-style strings: keep the leading numeric prefix.
        self.assertEqual(updater.parse_version("9.16(4)67"), (9, 16))

    def test_unparseable_is_none(self):
        for bad in ("", None, "abc", "v"):
            self.assertIsNone(updater.parse_version(bad))


class CompareVersionsTests(unittest.TestCase):
    def test_numeric_not_lexical(self):
        # The headline correctness case: 1.10.0 must be newer than 1.9.0.
        self.assertEqual(updater.compare_versions("1.10.0", "1.9.0"), 1)
        self.assertEqual(updater.compare_versions("1.9.0", "1.10.0"), -1)

    def test_equal_and_padding(self):
        self.assertEqual(updater.compare_versions("1.2.0", "1.2.0"), 0)
        self.assertEqual(updater.compare_versions("1.2", "1.2.0"), 0)

    def test_v_prefix_equivalent(self):
        self.assertEqual(updater.compare_versions("v1.2.0", "1.2.0"), 0)

    def test_ahead(self):
        self.assertEqual(updater.compare_versions("2.0.0", "1.9.9"), 1)

    def test_unknown_sorts_lowest(self):
        self.assertEqual(updater.compare_versions(None, "1.0.0"), -1)
        self.assertEqual(updater.compare_versions("1.0.0", None), 1)
        self.assertEqual(updater.compare_versions(None, None), 0)


class ReadInstalledVersionTests(unittest.TestCase):
    def test_reads_repo_version_file(self):
        # The repo ships a VERSION file; it must be present and parseable.
        v = updater.read_installed_version()
        self.assertIsNotNone(v)
        self.assertIsNotNone(updater.parse_version(v))

    def test_missing_file_returns_none(self):
        original = updater.VERSION_FILE
        try:
            updater.VERSION_FILE = Path(os.devnull) / "nope" / "VERSION"
            self.assertIsNone(updater.read_installed_version())
        finally:
            updater.VERSION_FILE = original


class ManifestDiffTests(unittest.TestCase):
    def test_removals(self):
        old = ["a.py", "b.py", "docs/index.html"]
        new = ["a.py", "docs/index.html"]
        self.assertEqual(updater.manifest_removals(old, new), ["b.py"])

    def test_no_removals_when_superset(self):
        old = ["a.py"]
        new = ["a.py", "c.py"]
        self.assertEqual(updater.manifest_removals(old, new), [])

    def test_preserve_and_internal_never_removed(self):
        old = ["a.py", ".env", "inventory/list.xlsx", ".venv/pyvenv.cfg", ".git/config"]
        new = ["a.py"]
        # Only a.py is comparable; preserve-list / internal paths are excluded even if
        # (hypothetically) they appeared in an old manifest.
        self.assertEqual(updater.manifest_removals(old, new), [])


class PreserveListTests(unittest.TestCase):
    def test_preserved_paths(self):
        for p in (".env", "inventory/list.xlsx", "output/report.xlsx", ".venv/bin/python"):
            self.assertTrue(updater.is_preserved(p), p)

    def test_internal_paths(self):
        for p in (".git/config", ".update-backup/x", ".update-in-progress"):
            self.assertTrue(updater.is_preserved(p), p)

    def test_app_files_not_preserved(self):
        for p in ("analyzer.py", "docs/index.html", "VERSION", "requirements.txt"):
            self.assertFalse(updater.is_preserved(p), p)

    def test_windows_separators(self):
        self.assertTrue(updater.is_preserved("inventory\\list.xlsx"))


if __name__ == "__main__":
    unittest.main()
