#!/usr/bin/env python3
"""
Interactive installer for the Cisco Advisory Impact Analyzer.

Works on macOS, Linux, and Windows. Assumes Python 3.9+ is already installed
(you're running it with Python right now). It will:

    1. verify the Python version,
    2. create a local virtual environment (.venv),
    3. install the required packages into it,
    4. help you set up your FueliX API key in .env,
    5. check that your inventory spreadsheet is present,
    6. run a quick smoke test, and
    7. optionally launch the analyzer.

Run it with:

    python install.py            (Windows)
    python3 install.py           (macOS / Linux)

Non-interactive options (for scripted setups) are shown with --help.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import ui

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
ENV_FILE = ROOT / ".env"
INVENTORY = ROOT / "inventory.xlsx"
MIN_PYTHON = (3, 9)
DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_BASE_URL = "https://api.fuelix.ai/v1"

IS_WINDOWS = os.name == "nt"


def venv_python():
    return VENV_DIR / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


# --------------------------------------------------------------------------- #
# Steps
# --------------------------------------------------------------------------- #
def check_python():
    if sys.version_info < MIN_PYTHON:
        need = ".".join(map(str, MIN_PYTHON))
        have = ".".join(map(str, sys.version_info[:3]))
        ui.fail(f"Python {need}+ is required, but this is Python {have}.")
        ui.plain("Install a newer Python and re-run:")
        ui.plain("  Windows : https://www.python.org/downloads/windows/ (or Microsoft Store)")
        ui.plain("  macOS   : https://www.python.org/downloads/macos/ (or `brew install python`)")
        ui.plain("  Linux   : use your package manager, e.g. `sudo apt install python3`")
        sys.exit(1)
    ui.ok(f"Python {'.'.join(map(str, sys.version_info[:3]))} at {ui.dim(sys.executable)}")


def create_venv(recreate=False):
    if VENV_DIR.exists() and venv_python().exists() and not recreate:
        ui.ok(f"Reusing existing virtual environment at {ui.dim(str(VENV_DIR))}")
        return
    if VENV_DIR.exists():
        ui.info(f"Removing existing {VENV_DIR} ...")
        shutil.rmtree(VENV_DIR, ignore_errors=True)
    ui.info(f"Creating virtual environment at {ui.dim(str(VENV_DIR))} ...")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    except subprocess.CalledProcessError:
        ui.fail("Could not create the virtual environment.")
        ui.plain("On Debian/Ubuntu you may need: sudo apt install python3-venv")
        sys.exit(1)
    ui.ok("Virtual environment created")


def install_requirements():
    py = venv_python()
    if not py.exists():
        ui.fail(f"venv interpreter not found at {py}")
        sys.exit(1)
    subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"],
                   capture_output=True)
    if not REQUIREMENTS.exists():
        ui.fail(f"{REQUIREMENTS.name} not found next to install.py")
        sys.exit(1)
    ui.info(f"Installing packages from {REQUIREMENTS.name} ...")
    try:
        subprocess.run([str(py), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
                       check=True)
    except subprocess.CalledProcessError:
        ui.fail("Dependency installation failed.")
        ui.plain("Check your internet connection / proxy and re-run install.py.")
        sys.exit(1)
    ui.ok("Dependencies installed")


def _read_env():
    values = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def _write_env(api_key, model, base_url):
    lines = [
        "# FueliX credentials for the Cisco Advisory Impact Analyzer.",
        "# Keep this file private - it contains your API key.",
        "",
        f"FUELIX_API_KEY={api_key}",
        f"FUELIX_MODEL={model}",
        f"FUELIX_BASE_URL={base_url}",
        "",
    ]
    ENV_FILE.write_text("\n".join(lines), encoding="utf-8")
    if not IS_WINDOWS:
        try:
            os.chmod(ENV_FILE, 0o600)  # rw for owner only
        except OSError:
            pass


def setup_env(cli_key=None, cli_model=None, assume_yes=False):
    existing = _read_env()
    existing_key = existing.get("FUELIX_API_KEY", "")

    if cli_key is not None:
        api_key = cli_key
    elif existing_key and (assume_yes or not ui.confirm(
            "An API key is already configured. Replace it?", default=False)):
        api_key = existing_key
        ui.ok("Keeping the existing API key")
    else:
        ui.system("Enter your FueliX API key from https://dev.fuelix.ai")
        ui.plain(ui.dim("(Default project -> '...' -> View -> API keys -> copy the key.)"))
        ui.plain(ui.dim("Input is hidden. Press Enter to skip and edit .env later."))
        api_key = ui.ask_secret("FUELIX_API_KEY")

    model = cli_model or existing.get("FUELIX_MODEL") or DEFAULT_MODEL
    if cli_model is None and not assume_yes and not existing.get("FUELIX_MODEL"):
        model = ui.ask("FueliX model", default=DEFAULT_MODEL)
    base_url = existing.get("FUELIX_BASE_URL") or DEFAULT_BASE_URL

    _write_env(api_key, model, base_url)
    if api_key:
        ui.ok(f"Wrote {ENV_FILE.name} (model: {ui.bold(model)})")
    else:
        ui.warn(f"Wrote {ENV_FILE.name} WITHOUT an API key - set FUELIX_API_KEY "
                "before running the analyzer.")


def check_inventory(cli_inventory=None, assume_yes=False):
    if INVENTORY.exists():
        ui.ok(f"Found inventory: {ui.bold(INVENTORY.name)}")
        return
    if cli_inventory:
        src = Path(cli_inventory)
    elif assume_yes:
        ui.warn(f"No {INVENTORY.name} found - add it before running the analyzer.")
        return
    else:
        ui.system(f"No '{INVENTORY.name}' found in this folder.")
        path = ui.ask("Path to your inventory .xlsx to copy here (Enter to skip)")
        if not path:
            ui.warn(f"Skipped. Place your inventory here as '{INVENTORY.name}' "
                    "before running the analyzer.")
            return
        src = Path(path).expanduser()

    if src.exists() and src.suffix.lower() == ".xlsx":
        shutil.copy2(src, INVENTORY)
        ui.ok(f"Copied inventory to {ui.bold(INVENTORY.name)}")
    else:
        ui.warn(f"'{src}' is not a valid .xlsx file. Add '{INVENTORY.name}' manually.")


def smoke_test():
    py = venv_python()
    result = subprocess.run(
        [str(py), "-c", "import openpyxl, dotenv; print('imports OK')"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        ui.ok("Smoke test passed (" + result.stdout.strip() + ")")
        return True
    ui.fail("Smoke test failed:")
    ui.plain(result.stderr.strip())
    return False


def run_command_hint():
    return "python run.py" if IS_WINDOWS else "python3 run.py"


def maybe_launch(assume_yes, no_run):
    if no_run:
        return
    if not assume_yes and ui.confirm("\nRun the analyzer now?", default=False):
        subprocess.run([str(venv_python()), str(ROOT / "analyzer.py")])


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Installer for the Cisco Advisory Analyzer")
    ap.add_argument("--api-key", help="Set the FueliX API key non-interactively")
    ap.add_argument("--model", help="FueliX model id (default claude-sonnet-5)")
    ap.add_argument("--inventory", help="Path to an inventory .xlsx to copy in")
    ap.add_argument("--recreate-venv", action="store_true", help="Delete and rebuild .venv")
    ap.add_argument("--yes", action="store_true",
                    help="Accept defaults / keep existing config without prompting")
    ap.add_argument("--no-run", action="store_true", help="Do not offer to launch at the end")
    args = ap.parse_args()

    ui.title("Cisco Advisory Impact Analyzer - installer")

    total = 6
    ui.step(1, total, "Checking Python")
    check_python()

    ui.step(2, total, "Setting up the virtual environment")
    create_venv(recreate=args.recreate_venv)

    ui.step(3, total, "Installing dependencies")
    install_requirements()

    ui.step(4, total, "Configuring FueliX credentials (.env)")
    setup_env(cli_key=args.api_key, cli_model=args.model, assume_yes=args.yes)

    ui.step(5, total, "Checking the firewall inventory")
    check_inventory(cli_inventory=args.inventory, assume_yes=args.yes)

    ui.step(6, total, "Verifying the installation")
    ok = smoke_test()

    print()
    ui.rule()
    if ok:
        ui.ok("Setup complete. To run the analyzer:")
        ui.plain("    " + ui.bold(run_command_hint()))
        ui.plain("You'll be prompted to paste the Cisco Event Response (ERP) URL.")
    else:
        ui.warn("Setup finished with warnings - see the messages above.")
    ui.rule()

    maybe_launch(assume_yes=args.yes, no_run=args.no_run)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        ui.warn("Cancelled.")
        sys.exit(130)
