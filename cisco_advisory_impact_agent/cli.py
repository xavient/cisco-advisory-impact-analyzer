"""Single command-line entry point for the Cisco Advisory Impact Agent.

Installed as the `caia` console script (see pyproject.toml). Dispatches
`--help`/`--version`/`--update`/`--config` and, with no mode flag, the interactive/flag-driven
analysis run. Ctrl+C anywhere exits 130 with no traceback (Constitution III, FR-012).
"""

from __future__ import annotations

import argparse
import os
import sys

from cisco_advisory_impact_agent import analyzer, config, ui, version


class _Parser(argparse.ArgumentParser):
    """ArgumentParser whose `--help` omits the `usage:` synopsis.

    Every flag is already spelled out under the options section, and the splash banner sits
    above it, so the compact synopsis is pure duplication in `--help`. Argument *errors* still
    print usage (via the unchanged `format_usage()`), where it's the only hint offered.
    """

    def format_help(self):
        # argparse's own format_help(), minus the leading formatter.add_usage(...) call.
        formatter = self._get_formatter()
        formatter.add_text(self.description)
        for group in self._action_groups:
            formatter.start_section(group.title)
            formatter.add_text(group.description)
            formatter.add_arguments(group._group_actions)
            formatter.end_section()
        formatter.add_text(self.epilog)
        return formatter.format_help()

    def error(self, message):
        # On a bad argument, show the error in red first (right below the splash), then the
        # same options list as --help. Exit code stays 2 (argparse's convention) for scripts.
        # Output goes to stdout, like the banner and the rest of the app, so it reliably lands
        # after the hero rather than racing the banner on a separate stream.
        ui.plain(ui.red(f"{self.prog}: error: {message}"))
        ui.plain()
        self.print_help()
        raise SystemExit(2)


def build_parser():
    ap = _Parser(
        prog="caia",
        description="AI-driven analysis of which firewalls in your inventory are impacted "
                    "by a Cisco security advisory.",
    )
    # Mode flags (handled in precedence order; not combined).
    ap.add_argument("--version", action="store_true",
                    help="Print the installed version and check for a newer one")
    ap.add_argument("--update", action="store_true",
                    help="Update to the latest published version via uv")
    ap.add_argument("--config", dest="do_config", action="store_true",
                    help="Set your FueliX API key and model (stored per-user)")
    # Analysis flags (a supplied flag skips its interactive prompt — FR-025).
    ap.add_argument("--url", help="ERP page URL or single advisory URL (else prompted)")
    ap.add_argument("--inventory",
                    help="Path to an inventory .xlsx (else discovered in the current folder)")
    ap.add_argument("--sheet", default="FW_List", help="Inventory sheet name")
    ap.add_argument("--output-dir", dest="output_dir", default=None,
                    help="Where to write the report (default: ./output in the current folder)")
    ap.add_argument("--dry-run", action="store_true", help="Skip the AI call (pipeline test)")
    ap.add_argument("--keep-temp", dest="keep_temp", action="store_true", default=True,
                    help="Keep downloaded CSAF temp files (default)")
    ap.add_argument("--no-keep-temp", dest="keep_temp", action="store_false",
                    help="Delete downloaded CSAF temp files after the run")
    ap.add_argument("--no-update-check", dest="no_update_check", action="store_true",
                    help="Skip the start-of-run check for a newer version")
    return ap


def _dispatch(argv):
    args = build_parser().parse_args(argv)
    if args.version:
        return cmd_version()
    if args.update:
        return cmd_update()
    if args.do_config:
        return config.run_config()
    return cmd_run(args)


# --------------------------------------------------------------------------- #
# --version
# --------------------------------------------------------------------------- #
def cmd_version():
    installed = version.read_installed_version() or "unknown"
    ui.plain(installed)
    newer = version.passive_check(timeout=2)  # best-effort, ~2s bound (FR-006, SC-008)
    if newer:
        ui.info(f"A newer version ({ui.bold(newer)}) is available. "
                "Update with: " + ui.bold("caia --update"))
    return 0


# --------------------------------------------------------------------------- #
# --update
# --------------------------------------------------------------------------- #
def cmd_update():
    result = version.check_update()
    installed = result["installed"] or "unknown"
    status = result["status"]

    if status == "latest_unknown":
        ui.fail("Could not determine the latest version (GitHub unreachable or rate-limited).")
        ui.plain(ui.dim(f"Check your connection/proxy and try again. Installed: {installed}"))
        return 3
    if status == "up_to_date":
        ui.ok(f"Already up to date ({installed}).")
        return 0
    if status == "ahead":
        ui.ok(f"Installed {installed} is ahead of latest {result['latest']}; nothing to do.")
        return 0

    tag = result["latest"]
    ui.system(f"Update available: {ui.bold(installed)} {ui.dim('->')} {ui.bold(tag)}")
    try:
        ui.info("Reinstalling via uv ...")
        version.perform_update(tag)
    except version.UpdateError as e:
        ui.fail(f"Update failed: {e}")
        return 4
    ui.ok(f"Updated to {ui.bold(tag)}. "
          "Run " + ui.bold("caia") + " again to use it.")
    return 0


# --------------------------------------------------------------------------- #
# Run (no mode flag)
# --------------------------------------------------------------------------- #
def _start_of_run_update_nudge(args):
    """Best-effort, non-blocking update offer at the start of an interactive run (FR-013).

    Skipped when --no-update-check / CAIA_NO_UPDATE_CHECK is set, when not attached to a TTY, or
    in a flag-driven run (a URL was supplied). Answering yes updates and exits (the running
    process is the old code); answering no continues on the current version.
    """
    if args.no_update_check or os.environ.get("CAIA_NO_UPDATE_CHECK"):
        return
    if args.url or not sys.stdin.isatty():
        return
    newer = version.passive_check(timeout=2)
    if not newer:
        return
    installed = version.read_installed_version() or "unknown"
    ui.info(f"A new version {ui.bold(newer)} is available (you have {installed}).")
    if not ui.confirm("Do you want to update now?", default=False):
        return
    try:
        version.perform_update(newer)
    except version.UpdateError as e:
        ui.fail(f"Update failed: {e}")
        ui.warn("Continuing with the current version.")
        return
    ui.ok(f"Updated to {ui.bold(newer)}. "
          "Please re-run " + ui.bold("caia") + " to use the new version.")
    raise SystemExit(0)


def cmd_run(args):
    _start_of_run_update_nudge(args)
    return analyzer.run(args)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main(argv=None):
    """Console-script entry point. Returns a process exit code."""
    try:
        ui.banner()  # splash shown once per invocation (interactive TTY only; see CAIA_NO_BANNER)
        return _dispatch(argv)
    except KeyboardInterrupt:
        print()
        ui.warn("Cancelled.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
