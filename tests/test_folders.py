#!/usr/bin/env python3
"""
Tests for working-folder inventory discovery/selection and report output
(analyzer.resolve_inventory, analyzer.default_output_dir, analyzer.ensure_dirs,
report.write_report).

Uses the standard-library `unittest` framework (no third-party test dependency, per the
project's minimal-dependencies principle). Run with:

    python -m unittest discover -s tests

All filesystem work happens under a temporary directory, so the user's real files are never
touched. Inventory discovery now validates candidates against the required structure, so tests
build genuine .xlsx workbooks rather than empty placeholder files.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cisco_advisory_impact_analyzer import analyzer, ui  # noqa: E402
from cisco_advisory_impact_analyzer import report  # noqa: E402


def _make_inventory(path, rows=1):
    """Write a minimal valid inventory workbook (sheet FW_List + required columns)."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "FW_List"
    ws.append(["FirewallName", "Model", "FirewallType", "IOS version"])
    for i in range(rows):
        ws.append([f"fw{i}", "ASA5525", "ASA", "9.16(4)67"])
    wb.save(path)


def _touch(path):
    Path(path).write_bytes(b"")


class ResolveInventoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_selects_single_valid_xlsx_ignoring_stray_files(self):
        """Exactly one valid .xlsx is selected; .txt / lock / invalid files are ignored."""
        real = self.folder / "fw_inventory.xlsx"
        _make_inventory(real)
        _touch(self.folder / "notes.txt")
        _touch(self.folder / "~$fw_inventory.xlsx")  # Excel lock file
        _touch(self.folder / "broken.xlsx")          # not a real workbook -> invalid

        chosen = analyzer.resolve_inventory(interactive=False, folder=self.folder)
        self.assertEqual(chosen, real)

    def test_explicit_override_bypasses_folder_scan(self):
        """--inventory PATH uses that file and never scans the folder."""
        _make_inventory(self.folder / "a.xlsx")
        _make_inventory(self.folder / "b.xlsx")
        explicit = self.folder / "elsewhere.xlsx"
        _make_inventory(explicit)

        chosen = analyzer.resolve_inventory(explicit=str(explicit), interactive=False,
                                            folder=self.folder)
        self.assertEqual(chosen, explicit)

    def test_multiple_valid_non_interactive_is_error(self):
        """Two valid inventories with no TTY -> fatal error (non-zero exit)."""
        _make_inventory(self.folder / "one.xlsx")
        _make_inventory(self.folder / "two.xlsx")
        with self.assertRaises(SystemExit) as cm:
            analyzer.resolve_inventory(interactive=False, folder=self.folder)
        self.assertNotEqual(cm.exception.code, 0)

    def test_no_valid_non_interactive_is_error(self):
        """No valid inventory with no TTY -> fatal error (non-zero exit)."""
        _touch(self.folder / "notes.txt")
        with self.assertRaises(SystemExit) as cm:
            analyzer.resolve_inventory(interactive=False, folder=self.folder)
        self.assertNotEqual(cm.exception.code, 0)

    def test_explicit_missing_file_is_error(self):
        with self.assertRaises(SystemExit):
            analyzer.resolve_inventory(explicit=str(self.folder / "nope.xlsx"),
                                       interactive=False, folder=self.folder)


class PickerTests(unittest.TestCase):
    """The interactive picker lists files, validates the choice, and re-prompts on invalid."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_lists_and_reprompts_until_valid(self):
        _touch(self.folder / "bad.xlsx")            # invalid -> should be rejected
        good = self.folder / "good.xlsx"
        _make_inventory(good)
        _make_inventory(self.folder / "good2.xlsx")  # 2 valid -> forces the picker

        answers = iter(["bad.xlsx", "good.xlsx"])
        with mock.patch.object(ui, "select", lambda *a, **k: next(answers)):
            chosen = analyzer.resolve_inventory(interactive=True, folder=self.folder)
        self.assertEqual(chosen, good)

    def test_empty_folder_is_error(self):
        with self.assertRaises(SystemExit):
            analyzer.resolve_inventory(interactive=True, folder=self.folder)


class OutputDirTests(unittest.TestCase):
    def test_default_output_dir_is_cwd_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(analyzer.Path, "cwd", return_value=Path(tmp)):
                self.assertEqual(analyzer.default_output_dir(), Path(tmp) / "output")

    def test_ensure_dirs_creates_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "output"
            self.assertFalse(out_dir.exists())
            analyzer.ensure_dirs(out_dir)
            self.assertTrue(out_dir.is_dir())
            analyzer.ensure_dirs(out_dir)  # idempotent


class WriteReportTests(unittest.TestCase):
    def test_reports_accumulate_without_overwrite(self):
        """Two writes produce two distinct files in the output dir; none overwritten."""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "output"  # does not exist yet -> must be created
            rows = [("cisco-sa-x", "desc", "Indeterminate")]

            p1 = report.write_report(rows, str(out_dir))
            p2 = report.write_report(rows, str(out_dir))

            self.assertTrue(Path(p1).exists())
            self.assertTrue(Path(p2).exists())
            self.assertNotEqual(p1, p2)
            xlsx = sorted(out_dir.glob("analysis_output_*.xlsx"))
            self.assertEqual(len(xlsx), 2)


if __name__ == "__main__":
    unittest.main()
