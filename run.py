#!/usr/bin/env python3
"""
Launcher for the Cisco Advisory Impact Analyzer.

Runs analyzer.py using the virtual environment created by install.py, so you never
have to activate the venv yourself. Works the same on macOS, Linux, and Windows:

    python run.py            (Windows)
    python3 run.py           (macOS / Linux)

Any extra arguments are passed straight through to analyzer.py, e.g.:

    python run.py --url https://sec.cloudapps.cisco.com/...   --dry-run
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import ui

ROOT = Path(__file__).resolve().parent
ANALYZER = ROOT / "analyzer.py"
VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main():
    if not VENV_PY.exists():
        ui.fail("The virtual environment isn't set up yet.")
        ui.plain("Run the installer first:")
        ui.plain("    python install.py" if os.name == "nt" else "    python3 install.py")
        sys.exit(1)

    args = sys.argv[1:]

    # Are we already running *inside* the venv? Check sys.prefix, not the executable
    # path: a venv's bin/python is a symlink to the base interpreter, so comparing
    # resolved executable paths gives a false match and loses the venv's packages.
    in_venv = Path(sys.prefix).resolve() == (ROOT / ".venv").resolve()
    if in_venv:
        sys.argv = [str(ANALYZER)] + args
        import analyzer  # noqa: WPS433

        analyzer.run_cli()
        return

    # Delegate to the venv interpreter. Ctrl+C reaches both us and the child; the
    # child prints its own "Cancelled." message, so here we just exit quietly.
    try:
        returncode = subprocess.run([str(VENV_PY), str(ANALYZER), *args]).returncode
    except KeyboardInterrupt:
        returncode = 130
    raise SystemExit(returncode)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
