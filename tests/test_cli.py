"""
Offline unit tests for the CLI argument parser.

Verifies that `--help` omits the redundant `usage:` synopsis (the flags are already listed
under the options section) while argument errors still surface usage.

Run with:  python -m unittest tests.test_cli
"""

import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cisco_advisory_impact_agent import cli  # noqa: E402


class HelpTests(unittest.TestCase):
    def test_help_omits_usage_synopsis(self):
        text = cli.build_parser().format_help()
        self.assertNotIn("usage:", text)

    def test_help_still_lists_options(self):
        text = cli.build_parser().format_help()
        for flag in ("--config", "--version", "--url", "--dry-run"):
            self.assertIn(flag, text)

    def test_errors_still_show_usage(self):
        # Argument errors rely on the (unchanged) usage line as their only hint.
        self.assertTrue(cli.build_parser().format_usage().startswith("usage:"))


class ErrorOutputTests(unittest.TestCase):
    def _run_bad_arg(self):
        buf = io.StringIO()
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stdout(buf):
            cli.build_parser().parse_args(["--nope"])
        return cm.exception.code, buf.getvalue()

    def test_unknown_arg_exits_2(self):
        code, _ = self._run_bad_arg()
        self.assertEqual(code, 2)

    def test_error_message_then_options(self):
        _, out = self._run_bad_arg()
        # The error line comes first, then the same options list as --help.
        self.assertIn("error: unrecognized arguments: --nope", out)
        self.assertLess(out.index("error:"), out.index("--config"))
        for flag in ("--config", "--version", "--dry-run"):
            self.assertIn(flag, out)


if __name__ == "__main__":
    unittest.main()
