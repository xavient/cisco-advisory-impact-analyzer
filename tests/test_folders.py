#!/usr/bin/env python3
"""
Tests for the inventory/output folder behavior (analyzer.find_inventory,
analyzer.ensure_dirs, report.write_report).

Uses the standard-library `unittest` framework (no third-party test dependency, per
the project's minimal-dependencies principle). Run with:

    python -m unittest discover -s tests            # macOS / Linux / Windows
    .venv/bin/python -m unittest discover -s tests  # via the project venv

All filesystem work happens under a temporary directory, so the real 'inventory' and
'output' folders are never touched.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import analyzer  # noqa: E402
import report  # noqa: E402


def _touch(path):
    Path(path).write_bytes(b"")


class FindInventoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.inv_dir = Path(self._tmp.name) / "inventory"
        self.inv_dir.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_selects_single_xlsx_ignoring_stray_files(self):
        """C2: exactly one .xlsx is selected; .txt/.DS_Store/~$ lock files are ignored."""
        real = self.inv_dir / "fw_inventory.xlsx"
        _touch(real)
        _touch(self.inv_dir / "notes.txt")
        _touch(self.inv_dir / ".DS_Store")
        _touch(self.inv_dir / "~$fw_inventory.xlsx")

        chosen = analyzer.find_inventory(self.inv_dir)
        self.assertEqual(chosen, real)

    def test_explicit_override_bypasses_folder_scan(self):
        """C6: --inventory PATH uses that file and never scans the folder."""
        # Two .xlsx in the folder would normally be an error; the override must win.
        _touch(self.inv_dir / "a.xlsx")
        _touch(self.inv_dir / "b.xlsx")
        explicit = Path(self._tmp.name) / "elsewhere.xlsx"
        _touch(explicit)

        chosen = analyzer.find_inventory(self.inv_dir, explicit=str(explicit))
        self.assertEqual(chosen, explicit)

    def test_multiple_xlsx_is_error(self):
        """C3: two .xlsx files -> fatal error (non-zero exit)."""
        _touch(self.inv_dir / "one.xlsx")
        _touch(self.inv_dir / "two.xlsx")
        with self.assertRaises(SystemExit) as cm:
            analyzer.find_inventory(self.inv_dir)
        self.assertNotEqual(cm.exception.code, 0)

    def test_empty_folder_is_error(self):
        """C4: no .xlsx file -> fatal error (non-zero exit)."""
        with self.assertRaises(SystemExit) as cm:
            analyzer.find_inventory(self.inv_dir)
        self.assertNotEqual(cm.exception.code, 0)


class EnsureDirsTests(unittest.TestCase):
    def test_creates_missing_then_empty_inventory_errors(self):
        """C1: missing inventory/ + output/ are created, then empty-inventory errors."""
        with tempfile.TemporaryDirectory() as tmp:
            inv_dir = Path(tmp) / "inventory"
            out_dir = Path(tmp) / "output"
            self.assertFalse(inv_dir.exists())
            self.assertFalse(out_dir.exists())

            analyzer.ensure_dirs(inv_dir, out_dir)
            self.assertTrue(inv_dir.is_dir())
            self.assertTrue(out_dir.is_dir())

            # Re-running is idempotent (no error on existing folders).
            analyzer.ensure_dirs(inv_dir, out_dir)

            with self.assertRaises(SystemExit):
                analyzer.find_inventory(inv_dir)


class WriteReportTests(unittest.TestCase):
    def test_reports_accumulate_without_overwrite(self):
        """C5: two writes produce two distinct files in the output dir; none overwritten."""
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
