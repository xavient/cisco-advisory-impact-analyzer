#!/usr/bin/env python3
"""
One-command self-updater for the Cisco Advisory Impact Analyzer.

    python3 update.py             # check, confirm, and update to the latest release
    python3 update.py --check     # report installed vs latest; make no changes
    python3 update.py --yes       # update without the confirmation prompt (scripted)
    python3 update.py --rollback  # restore the most recent backup (previous version)

Run it from the tool's folder with the base Python (no virtual environment needed) — the
same way you run install.py:

    python update.py              (Windows)
    python3 update.py             (macOS / Linux)

Standard library only. Your API key (.env), inventory, reports, and .venv are never touched.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

import ui
import updater


def _print_status(result):
    installed = result["installed"] or "unknown"
    ui.plain(f"Installed: {ui.bold(installed)}")
    if result["status"] == "latest_unknown":
        ui.plain("Latest:    " + ui.dim("unknown (could not reach GitHub)"))
        ui.plain("Status:    " + ui.yellow("latest unknown"))
        return
    ui.plain(f"Latest:    {ui.bold(result['latest'])}")
    labels = {
        "up_to_date": ui.green("up to date"),
        "update_available": (ui.yellow("update available")
                             + ui.dim("  (run: python3 update.py)")),
        "ahead": ui.cyan("ahead of latest"),
    }
    ui.plain("Status:    " + labels[result["status"]])


def cmd_check():
    result = updater.check_update()
    _print_status(result)
    # Exit 3 only when we can report neither the installed nor the latest version.
    if result["status"] == "latest_unknown" and not result["installed"]:
        return 3
    return 0


def cmd_rollback():
    try:
        backup = updater.restore_backup()
    except updater.UpdaterError as e:
        ui.fail(str(e))
        ui.plain(ui.dim("There is no previous version to roll back to."))
        return 1
    updater.clear_marker()
    version = updater.read_installed_version() or "unknown"
    ui.ok(f"Rolled back to {ui.bold(version)} " + ui.dim(f"(from {backup.name})") + ".")
    return 0


def cmd_update(assume_yes):
    if updater.recover_if_interrupted():
        ui.warn("A previous update was interrupted; the install was restored to its "
                "prior state before continuing.")

    result = updater.check_update()
    installed = result["installed"] or "unknown"

    if result["status"] == "latest_unknown":
        ui.fail("Could not determine the latest version (GitHub unreachable or rate-limited).")
        ui.plain(ui.dim(f"Check your connection/proxy and try again. Installed: {installed}"))
        return 3
    if result["status"] == "up_to_date":
        ui.ok(f"Already up to date ({installed}).")
        return 0
    if result["status"] == "ahead":
        ui.ok(f"Installed {installed} is ahead of latest {result['latest']}; nothing to do.")
        return 0

    tag = result["latest"]
    ui.system(f"Update available: {ui.bold(installed)} {ui.dim('->')} {ui.bold(tag)}")
    if not assume_yes and not ui.confirm("Download and apply this update?", default=False):
        ui.plain("No changes made.")
        return 0

    with tempfile.TemporaryDirectory(prefix="caia_update_") as td:
        td = Path(td)
        try:
            ui.info("Downloading release ...")
            zip_path, sha_path = updater.download_release(tag, td)
        except Exception as e:  # noqa: BLE001
            ui.fail(f"Download failed: {e}")
            ui.plain(ui.dim("No files were changed."))
            return 4

        try:
            ui.info("Verifying package ...")
            new_root = updater.verify_package(zip_path, sha_path, tag, td / "extract")
        except updater.VerificationError as e:
            ui.fail(f"Verification failed: {e}")
            ui.plain(ui.dim("No files were changed."))
            return 4

        try:
            ui.info("Backing up and applying ...")
            outcome = updater.apply_with_backup(new_root, tag)
        except updater.ApplyReverted as e:
            ui.fail(f"Update failed while applying: {e}")
            ui.warn("The install was automatically reverted to the previous version.")
            return 5
        except updater.ApplyRevertFailed as e:
            ui.fail(f"Update failed and the automatic revert also failed: {e}")
            ui.plain(ui.dim("Run 'python3 update.py --rollback' to restore from backup."))
            return 6

    deps = outcome["deps"]
    if deps == "refreshed":
        ui.ok("Dependencies refreshed.")
    elif deps == "venv-missing":
        ui.warn("Requirements changed but no .venv was found — run 'python3 install.py' "
                "to (re)install dependencies.")
    elif deps == "refresh-failed":
        ui.warn("The update applied, but refreshing dependencies failed — run "
                "'python3 install.py' to complete the dependency update.")

    ui.ok(f"Updated to {ui.bold(tag)}.")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Self-updater for the Cisco Advisory Impact Analyzer")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="Report installed vs latest version; make no changes")
    mode.add_argument("--rollback", action="store_true",
                      help="Restore the most recent backup (revert the last update)")
    ap.add_argument("--yes", "-y", action="store_true",
                    help="Skip the confirmation prompt (for scripted updates)")
    ap.add_argument("--repo", metavar="OWNER/NAME",
                    help="Override the release source (also via CAIA_UPDATE_REPO)")
    args = ap.parse_args()

    if args.repo:
        os.environ["CAIA_UPDATE_REPO"] = args.repo

    if args.check:
        return cmd_check()
    if args.rollback:
        return cmd_rollback()
    return cmd_update(assume_yes=args.yes)


def run_cli():
    """Entry point with graceful Ctrl+C / EOF handling (no traceback)."""
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        ui.warn("Cancelled.")
        sys.exit(130)


if __name__ == "__main__":
    run_cli()
