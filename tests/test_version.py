"""
Offline unit tests for the version module's pure logic.

Covers semantic-version parsing/comparison, installed-version reading (via the VERSION-file
fallback when the distribution is not installed), and the uv-executable lookup fallback. No
network access — the GitHub discovery functions are exercised only through their pure helpers.

Run with:  python -m unittest tests.test_version
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cisco_advisory_impact_analyzer import version  # noqa: E402


class ParseVersionTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(version.parse_version("1.2.0"), (1, 2, 0))

    def test_strips_leading_v(self):
        self.assertEqual(version.parse_version("v1.2"), (1, 2))
        self.assertEqual(version.parse_version("V3.4.5"), (3, 4, 5))

    def test_stops_at_non_numeric_component(self):
        # Irregular Cisco-style strings: keep the leading numeric prefix.
        self.assertEqual(version.parse_version("9.16(4)67"), (9, 16))

    def test_unparseable_is_none(self):
        for bad in ("", None, "abc", "v"):
            self.assertIsNone(version.parse_version(bad))


class CompareVersionsTests(unittest.TestCase):
    def test_numeric_not_lexical(self):
        # The headline correctness case: 1.10.0 must be newer than 1.9.0.
        self.assertEqual(version.compare_versions("1.10.0", "1.9.0"), 1)
        self.assertEqual(version.compare_versions("1.9.0", "1.10.0"), -1)

    def test_equal_and_padding(self):
        self.assertEqual(version.compare_versions("1.2.0", "1.2.0"), 0)
        self.assertEqual(version.compare_versions("1.2", "1.2.0"), 0)

    def test_v_prefix_equivalent(self):
        self.assertEqual(version.compare_versions("v1.2.0", "1.2.0"), 0)

    def test_ahead(self):
        self.assertEqual(version.compare_versions("2.0.0", "1.9.9"), 1)

    def test_unknown_sorts_lowest(self):
        self.assertEqual(version.compare_versions(None, "1.0.0"), -1)
        self.assertEqual(version.compare_versions("1.0.0", None), 1)
        self.assertEqual(version.compare_versions(None, None), 0)


class ReadInstalledVersionTests(unittest.TestCase):
    def test_reads_a_parseable_version(self):
        # Either the installed distribution metadata or the VERSION-file fallback; both parse.
        v = version.read_installed_version()
        self.assertIsNotNone(v)
        self.assertIsNotNone(version.parse_version(v))

    def test_version_file_fallback(self):
        # Simulate an uninstalled source tree: metadata lookup fails -> VERSION file is read.
        with mock.patch.object(version, "_dist_version",
                               side_effect=version.PackageNotFoundError()):
            v = version.read_installed_version()
        self.assertIsNotNone(v)
        self.assertIsNotNone(version.parse_version(v))


class FindUvTests(unittest.TestCase):
    def test_prefers_path(self):
        with mock.patch.object(version.shutil, "which", return_value="/usr/bin/uv"):
            self.assertEqual(version.find_uv(), "/usr/bin/uv")

    def test_none_when_absent(self):
        with mock.patch.object(version.shutil, "which", return_value=None), \
             mock.patch.object(version.Path, "exists", return_value=False):
            self.assertIsNone(version.find_uv())


class GitSourceTests(unittest.TestCase):
    def test_pins_tag(self):
        self.assertTrue(version.git_source("1.5.0").endswith("@1.5.0"))
        self.assertFalse(version.git_source().endswith("@None"))


if __name__ == "__main__":
    unittest.main()
