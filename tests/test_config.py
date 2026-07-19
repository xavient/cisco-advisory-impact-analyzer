"""
Offline unit tests for per-user configuration (config.py): OS-appropriate directory
resolution, the env -> file -> default precedence, and owner-only file permissions.

Uses stdlib `unittest` with `unittest.mock` for OS/env patching. No network, and all files are
written under a temporary directory. Run with:  python -m unittest tests.test_config
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cisco_advisory_impact_analyzer import config, fuelix  # noqa: E402


class ConfigBaseDirTests(unittest.TestCase):
    """The OS-appropriate base directory logic (pure, no global os.name patching)."""

    def test_windows_uses_appdata(self):
        base = config._resolve_base(
            "nt", "win32", {"APPDATA": r"C:\Users\t\AppData\Roaming"}, r"C:\Users\t")
        self.assertEqual(base, r"C:\Users\t\AppData\Roaming")

    def test_windows_falls_back_without_appdata(self):
        base = config._resolve_base("nt", "win32", {}, "HOME")
        self.assertEqual(base, os.path.join("HOME", "AppData", "Roaming"))

    def test_macos_uses_application_support(self):
        base = config._resolve_base("posix", "darwin", {}, "/Users/t")
        self.assertEqual(base, os.path.join("/Users/t", "Library", "Application Support"))

    def test_linux_respects_xdg(self):
        base = config._resolve_base("posix", "linux", {"XDG_CONFIG_HOME": "/tmp/xdg"}, "/home/t")
        self.assertEqual(base, "/tmp/xdg")

    def test_linux_defaults_to_dot_config(self):
        base = config._resolve_base("posix", "linux", {}, "/home/t")
        self.assertEqual(base, os.path.join("/home/t", ".config"))

    def test_config_dir_ends_with_app_name(self):
        self.assertEqual(config.config_dir().name, config.APP_DIR_NAME)


class ResolvePrecedenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "config"
        self.path.write_text("FUELIX_MODEL=file-model\nFUELIX_API_KEY=file-key\n",
                             encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_env_wins(self):
        with mock.patch.object(config, "config_path", return_value=self.path), \
             mock.patch.dict(os.environ, {"FUELIX_MODEL": "env-model"}, clear=True):
            self.assertEqual(config.resolve(config.MODEL), "env-model")

    def test_file_used_when_env_absent(self):
        with mock.patch.object(config, "config_path", return_value=self.path), \
             mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config.resolve(config.MODEL), "file-model")
            self.assertEqual(config.resolve(config.API_KEY), "file-key")

    def test_default_when_absent_everywhere(self):
        empty = Path(self._tmp.name) / "empty"
        empty.write_text("", encoding="utf-8")
        with mock.patch.object(config, "config_path", return_value=empty), \
             mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config.resolve(config.MODEL), fuelix.DEFAULT_MODEL)
            self.assertEqual(config.resolve(config.BASE_URL), fuelix.DEFAULT_BASE_URL)
            self.assertEqual(config.resolve(config.API_KEY), "")


class SaveTests(unittest.TestCase):
    def test_save_roundtrip_and_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / config.APP_DIR_NAME
            with mock.patch.object(config, "config_dir", return_value=cfg_dir), \
                 mock.patch.object(config, "config_path", return_value=cfg_dir / "config"):
                path = config.save({
                    config.API_KEY: "secret",
                    config.MODEL: "claude-sonnet-5",
                    config.BASE_URL: fuelix.DEFAULT_BASE_URL,
                })
                self.assertTrue(path.exists())
                loaded = config.load_file()
                self.assertEqual(loaded[config.API_KEY], "secret")
                self.assertEqual(loaded[config.MODEL], "claude-sonnet-5")
                if os.name != "nt":
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
