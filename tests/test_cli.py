"""
Offline unit tests for the CLI argument parser.

Verifies that `--help` omits the redundant `usage:` synopsis (the flags are already listed
under the options section) while argument errors still surface usage.

Run with:  python -m unittest tests.test_cli
"""

import contextlib
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cisco_advisory_impact_agent import cli, version  # noqa: E402


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


class UninstallTests(unittest.TestCase):
    """Behavioral tests for `caia --uninstall` (cli.cmd_uninstall)."""

    def setUp(self):
        # A real, existing path to stand in for a saved config file, and a guaranteed-missing one.
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.existing_cfg = Path(self._tmp.name) / "config"
        self.existing_cfg.write_text("FUELIX_API_KEY=x\n", encoding="utf-8")
        self.missing_cfg = Path(self._tmp.name) / "nope"

    def _run(self, yes=False):
        args = types.SimpleNamespace(yes=yes)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.cmd_uninstall(args)
        return code, buf.getvalue()

    @contextlib.contextmanager
    def _env(self, kind, *, isatty=True, cfg=None, perform=None, confirm=None):
        """Patch the collaborators cmd_uninstall touches."""
        cfg = cfg if cfg is not None else self.existing_cfg
        perform = perform if perform is not None else mock.DEFAULT
        with mock.patch.object(cli.version, "classify_uninstall", return_value=kind), \
             mock.patch.object(cli.config, "config_path", return_value=cfg), \
             mock.patch.object(cli.sys.stdin, "isatty", return_value=isatty), \
             mock.patch.object(cli.version, "perform_uninstall") as m_perform, \
             mock.patch.object(cli.ui, "confirm",
                               return_value=(True if confirm is None else confirm)) as m_confirm:
            if perform is not mock.DEFAULT:
                m_perform.side_effect = perform
            yield m_perform, m_confirm

    # --- US1: happy path + config disclosure ---------------------------------
    def test_us1_yes_removes_and_discloses_config(self):
        with self._env(version.UV_MANAGED, cfg=self.existing_cfg) as (perform, confirm):
            code, out = self._run(yes=True)
        self.assertEqual(code, 0)
        perform.assert_called_once()
        confirm.assert_not_called()
        self.assertIn(str(self.existing_cfg), out)
        self.assertIn("uninstalled", out.lower())

    def test_us1_interactive_confirm_removes(self):
        with self._env(version.UV_MANAGED, isatty=True, confirm=True) as (perform, confirm):
            code, _ = self._run(yes=False)
        self.assertEqual(code, 0)
        perform.assert_called_once()
        confirm.assert_called_once()

    def test_us1_interactive_decline_removes_nothing(self):
        with self._env(version.UV_MANAGED, isatty=True, confirm=False) as (perform, _):
            code, out = self._run(yes=False)
        self.assertNotEqual(code, 0)
        perform.assert_not_called()
        self.assertIn("nothing was removed", out.lower())

    def test_us1_config_absent_message(self):
        with self._env(version.UV_MANAGED, cfg=self.missing_cfg) as (perform, _):
            code, out = self._run(yes=True)
        self.assertEqual(code, 0)
        perform.assert_called_once()
        self.assertIn("no saved configuration", out.lower())

    # --- US2: --yes gating, non-interactive refusal, idempotence -------------
    def test_us2_yes_skips_prompt(self):
        with self._env(version.UV_MANAGED) as (perform, confirm):
            code, _ = self._run(yes=True)
        self.assertEqual(code, 0)
        confirm.assert_not_called()
        perform.assert_called_once()

    def test_us2_non_interactive_without_yes_refuses(self):
        with self._env(version.UV_MANAGED, isatty=False) as (perform, confirm):
            code, out = self._run(yes=False)
        self.assertNotEqual(code, 0)
        perform.assert_not_called()
        confirm.assert_not_called()
        self.assertIn("--yes", out)

    def test_us2_not_installed_is_idempotent_zero(self):
        with self._env(version.NOT_INSTALLED) as (perform, _):
            code, out = self._run(yes=True)
        self.assertEqual(code, 0)
        perform.assert_not_called()
        self.assertIn("nothing to uninstall", out.lower())

    def test_us2_pip_or_source_is_idempotent_zero(self):
        with self._env(version.PIP_OR_SOURCE) as (perform, _):
            code, _ = self._run(yes=True)
        self.assertEqual(code, 0)
        perform.assert_not_called()

    def test_us2_repeat_run_stays_zero(self):
        for _ in range(2):
            with self._env(version.NOT_INSTALLED) as (perform, _):
                code, _ = self._run(yes=True)
            self.assertEqual(code, 0)
            perform.assert_not_called()

    # --- US3: clear explanations when removal can't proceed ------------------
    def test_us3_uv_absent_prints_manual_command(self):
        with self._env(version.UNKNOWN_UV_ABSENT) as (perform, _):
            code, out = self._run(yes=True)
        self.assertNotEqual(code, 0)
        perform.assert_not_called()
        self.assertIn(f"uv tool uninstall {version.DIST_NAME}", out)

    def test_us3_removal_failure_surfaces_actionable_error(self):
        err = version.UninstallError(
            "uv exited with code 1; the tool may not be fully removed.\n"
            f"If you are on Windows, close this command and run:\n    "
            f"uv tool uninstall {version.DIST_NAME}")
        with self._env(version.UV_MANAGED, perform=err) as (perform, _):
            code, out = self._run(yes=True)
        self.assertNotEqual(code, 0)
        perform.assert_called_once()
        self.assertIn("failed", out.lower())
        self.assertNotIn("has been uninstalled", out.lower())  # no false success

    def test_us3_pip_or_source_message_is_clear(self):
        with self._env(version.PIP_OR_SOURCE) as (_perform, _):
            _code, out = self._run(yes=True)
        self.assertIn("source or pip", out.lower())


if __name__ == "__main__":
    unittest.main()
