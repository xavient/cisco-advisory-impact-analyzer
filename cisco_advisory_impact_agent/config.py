"""Per-user configuration: FueliX API key, model, and base URL.

Stored in an OS-appropriate per-user location (not any working folder), readable by later runs
from any folder. Resolution precedence for every setting is: environment variable -> per-user
config file -> built-in default. Standard library only for path/file handling; the API key file
is owner-only where the OS supports it. See specs/004-uv-tool-distribution/contracts/config.md.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from cisco_advisory_impact_agent import fuelix, ui

APP_DIR_NAME = "caia"
CONFIG_FILE_NAME = "config"

# Keys managed here, mirroring the environment-variable names the app already honors.
API_KEY = "FUELIX_API_KEY"
MODEL = "FUELIX_MODEL"
BASE_URL = "FUELIX_BASE_URL"
KEYS = (API_KEY, MODEL, BASE_URL)

DEFAULTS = {MODEL: fuelix.DEFAULT_MODEL, BASE_URL: fuelix.DEFAULT_BASE_URL}


# --------------------------------------------------------------------------- #
# Location
# --------------------------------------------------------------------------- #
def _resolve_base(os_name, platform, environ, home):
    """Return the OS-appropriate per-user base directory (as a string).

    Pure and injectable so the OS logic is testable without patching `os.name` globally
    (which would change pathlib's Path flavour and break on the test host).
    """
    if os_name == "nt":
        return environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    if platform == "darwin":
        return os.path.join(home, "Library", "Application Support")
    return environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")


def config_dir():
    """OS-appropriate per-user config directory for this tool."""
    base = _resolve_base(os.name, sys.platform, os.environ, str(Path.home()))
    return Path(base) / APP_DIR_NAME


def config_path():
    return config_dir() / CONFIG_FILE_NAME


# --------------------------------------------------------------------------- #
# File load / save
# --------------------------------------------------------------------------- #
def load_file():
    """Read the per-user config file into a dict (KEY=value). Missing file -> {}."""
    result = {}
    try:
        text = config_path().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return result
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        result[key.strip()] = val.strip().strip('"').strip("'")
    return result


def save(values):
    """Write the given settings to the per-user config file with owner-only permissions."""
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = config_path()

    lines = [
        "# Cisco Advisory Impact Agent configuration.",
        "# Managed by `caia --config`; you may edit values by hand.",
        "# Environment variables (FUELIX_API_KEY / FUELIX_MODEL / FUELIX_BASE_URL) override these.",
    ]
    for key in KEYS:
        val = values.get(key)
        if val is not None and str(val) != "":
            lines.append(f"{key}={val}")
    text = "\n".join(lines) + "\n"

    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    _chmod_600(tmp)
    os.replace(tmp, path)
    _chmod_600(path)
    return path


def _chmod_600(path):
    try:
        os.chmod(path, 0o600)
    except (OSError, NotImplementedError):
        pass  # e.g. Windows without POSIX perms — rely on per-user profile ACLs.


# --------------------------------------------------------------------------- #
# Resolution (env -> file -> default)
# --------------------------------------------------------------------------- #
def resolve(key, file_values=None):
    """Resolve a setting: environment variable, then the config file, then the default."""
    env = os.environ.get(key)
    if env is not None and env.strip():
        return env.strip()
    values = load_file() if file_values is None else file_values
    val = values.get(key)
    if val is not None and str(val).strip():
        return str(val).strip()
    return DEFAULTS.get(key, "")


def load_local_env():
    """Load a `.env` from the current working folder into the environment (best-effort).

    Values are applied with setdefault so real environment variables still win. This keeps the
    automation path convenient without requiring a per-user config.
    """
    env_path = Path.cwd() / ".env"
    try:
        from dotenv import dotenv_values

        for key, val in dotenv_values(env_path).items():
            if val is not None:
                os.environ.setdefault(key, val)
        return
    except ImportError:
        pass
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


# --------------------------------------------------------------------------- #
# Interactive `--config`
# --------------------------------------------------------------------------- #
def run_config():
    """Interactively set the API key and model; persist to the per-user config file (FR-008..011)."""
    existing = load_file()
    ui.title("Configure Cisco Advisory Impact Agent")

    # API key (secret). Empty input keeps the existing value.
    if existing.get(API_KEY):
        ui.plain("An API key is already configured " + ui.dim("(hidden)."))
        entered = ui.ask_secret("New API key (press Enter to keep the current one)")
        api_key = entered or existing[API_KEY]
    else:
        api_key = ui.ask_secret("FueliX API key")
        while not api_key:
            ui.warn("The API key cannot be empty.")
            api_key = ui.ask_secret("FueliX API key")

    # Model (curated menu). A configured model not in the list is shown as current and keepable.
    current_model = existing.get(MODEL, fuelix.DEFAULT_MODEL)
    options = list(fuelix.KNOWN_MODELS)
    if current_model not in options:
        options = [current_model] + options
    ui.plain()
    ui.system("Choose the FueliX model:")
    model = ui.select("Model", options, default=current_model)

    # Base URL is not prompted (FR-010); preserve the existing/default so the file stays editable.
    base_url = existing.get(BASE_URL, fuelix.DEFAULT_BASE_URL)

    path = save({API_KEY: api_key, MODEL: model, BASE_URL: base_url})
    ui.plain()
    ui.ok("Saved configuration to " + ui.bold(str(path)) + ".")
    ui.plain(ui.dim("The base URL is not prompted; edit the file or set FUELIX_BASE_URL to change it."))
    return 0
