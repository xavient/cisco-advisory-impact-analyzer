"""
Offline unit tests for the splash banner in the ui module.

Covers the banner content (wordmark, product name, TELUS Digital slogan), the plain-text
rendering used when colour is disabled, and the CAIA_NO_BANNER / non-TTY gating that keeps
piped output and automation clean.

Run with:  python -m unittest tests.test_banner
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cisco_advisory_impact_agent import ui  # noqa: E402


class BannerContentTests(unittest.TestCase):
    def test_text_contains_name_and_telus_slogan(self):
        text = ui.banner_text()
        self.assertIn("Cisco Advisory Impact Agent", text)
        self.assertIn("TELUS Digital", text)
        self.assertIn("█", text)  # the block-letter wordmark rendered

    def test_plain_when_colour_disabled(self):
        # With colour off, no ANSI escape sequences should leak into the banner.
        with mock.patch.object(ui, "_ENABLED", False):
            text = ui.banner_text()
        self.assertNotIn("\033[", text)


class BannerGatingTests(unittest.TestCase):
    def test_no_banner_env_disables(self):
        with mock.patch.dict(os.environ, {"CAIA_NO_BANNER": "1"}), \
                mock.patch.object(sys.stdout, "isatty", return_value=True):
            self.assertFalse(ui.banner_enabled())

    def test_non_tty_disables(self):
        with mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch.object(sys.stdout, "isatty", return_value=False):
            os.environ.pop("CAIA_NO_BANNER", None)
            self.assertFalse(ui.banner_enabled())

    def test_interactive_tty_enables(self):
        with mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch.object(sys.stdout, "isatty", return_value=True):
            os.environ.pop("CAIA_NO_BANNER", None)
            self.assertTrue(ui.banner_enabled())

    def test_banner_prints_nothing_when_disabled(self):
        with mock.patch.object(ui, "banner_enabled", return_value=False), \
                mock.patch("builtins.print") as p:
            ui.banner()
        p.assert_not_called()


if __name__ == "__main__":
    unittest.main()
