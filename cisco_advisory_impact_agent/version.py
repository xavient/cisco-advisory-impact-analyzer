"""Version reporting and uv-based updates.

The installed version is read from the package metadata single-sourced from the committed
`VERSION` file (falling back to that file for source-tree runs). Latest-version discovery reuses
the GitHub release logic from the retired in-repo updater (standard library only, sends no
inventory or secrets). Updating is delegated to `uv`, which reinstalls the tool from the git
source — this module never overlays files in place.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from importlib.metadata import PackageNotFoundError, version as _dist_version
from pathlib import Path

DIST_NAME = "cisco-advisory-impact-agent"
DEFAULT_REPO = "xavient/cisco-advisory-impact-analyzer"  # GitHub repo name (URL) is unchanged
UA = {"User-Agent": "cisco-advisory-impact-agent"}

# VERSION lives at the repo root, one level above this package (used only for source-tree runs).
_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


class UpdateError(Exception):
    """A `--update` could not be completed; the installed version is left working."""


class UninstallError(Exception):
    """A `--uninstall` could not be completed; the installed tool is left as-is."""


# --------------------------------------------------------------------------- #
# Installed version
# --------------------------------------------------------------------------- #
def read_installed_version():
    """Return the installed distribution version, or None if it cannot be determined.

    Uses installed package metadata (works from any working folder once uv-installed) and
    falls back to reading the committed VERSION file when run from an uninstalled source tree.
    """
    try:
        return _dist_version(DIST_NAME)
    except PackageNotFoundError:
        pass
    try:
        text = _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


# --------------------------------------------------------------------------- #
# Version parsing & comparison
# --------------------------------------------------------------------------- #
def parse_version(s):
    """Parse a version string into a tuple of ints, or None if unparseable.

    Strips a leading 'v'; takes the leading digits of each dotted component and stops at
    the first non-numeric component (e.g. '9.16(4)67' -> (9, 16)). '' / None -> None.
    """
    if not s:
        return None
    s = s.strip()
    if s[:1] in ("v", "V"):
        s = s[1:]
    parts = []
    for chunk in s.split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) if parts else None


def compare_versions(a, b):
    """Return -1 if a < b, 0 if equal, 1 if a > b (semantic, component-wise).

    An unparseable/unknown version sorts below any real version; two unknowns are equal.
    """
    pa, pb = parse_version(a), parse_version(b)
    if pa is None and pb is None:
        return 0
    if pa is None:
        return -1
    if pb is None:
        return 1
    n = max(len(pa), len(pb))
    pa = pa + (0,) * (n - len(pa))
    pb = pb + (0,) * (n - len(pb))
    return (pa > pb) - (pa < pb)


# --------------------------------------------------------------------------- #
# Repo / URLs
# --------------------------------------------------------------------------- #
def repo():
    return os.environ.get("CAIA_UPDATE_REPO", "").strip() or DEFAULT_REPO


def _api_latest_url():
    return f"https://api.github.com/repos/{repo()}/releases/latest"


def _latest_redirect_url():
    return f"https://github.com/{repo()}/releases/latest"


def _tags_api_url():
    return f"https://api.github.com/repos/{repo()}/tags"


def git_source(tag=None):
    """The `--from` git source uv installs; pinned to a tag when given."""
    base = f"git+https://github.com/{repo()}"
    return f"{base}@{tag}" if tag else base


# --------------------------------------------------------------------------- #
# Latest-release discovery (GitHub API, with redirect + tags fallbacks)
# --------------------------------------------------------------------------- #
def _open(url, timeout, headers=None):
    req = urllib.request.Request(url, headers=headers or UA)
    return urllib.request.urlopen(req, timeout=timeout)


def _latest_via_api(timeout):
    headers = dict(UA)
    headers["Accept"] = "application/vnd.github+json"
    with _open(_api_latest_url(), timeout, headers) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    tag = data.get("tag_name")
    return tag.strip() if tag else None


def _latest_via_redirect(timeout):
    # /releases/latest 302-redirects to /releases/tag/<version>; urllib follows it.
    with _open(_latest_redirect_url(), timeout) as resp:
        final = resp.geturl()
    marker = "/releases/tag/"
    idx = final.find(marker)
    if idx == -1:
        return None
    tag = final[idx + len(marker):].strip("/").split("/")[0].split("?")[0]
    return tag or None


def _latest_via_tags(timeout):
    # Fallback when no GitHub Release object exists: pick the highest semantic tag.
    headers = dict(UA)
    headers["Accept"] = "application/vnd.github+json"
    with _open(_tags_api_url(), timeout, headers) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    best = None
    for entry in data or []:
        name = (entry.get("name") or "").strip()
        if parse_version(name) and (best is None or compare_versions(name, best) > 0):
            best = name
    return best


def resolve_latest(timeout=10):
    """Return (tag, reachable). Tries the release API, the web redirect, then the tags API."""
    for finder in (_latest_via_api, _latest_via_redirect, _latest_via_tags):
        try:
            tag = finder(timeout)
            if tag:
                return tag, True
        except Exception:  # noqa: BLE001 - rate limit (403), offline, proxy, bad JSON
            continue
    return None, False


def check_update(timeout=10):
    """Return {status, installed, latest}.

    status is one of: up_to_date, update_available, ahead, latest_unknown.
    """
    installed = read_installed_version()
    latest, reachable = resolve_latest(timeout=timeout)
    if not reachable or not latest:
        return {"status": "latest_unknown", "installed": installed, "latest": None}
    cmp = compare_versions(installed or "", latest)
    status = "update_available" if cmp < 0 else "ahead" if cmp > 0 else "up_to_date"
    return {"status": status, "installed": installed, "latest": latest}


def passive_check(timeout=2):
    """Best-effort: return the newer version string if an update is available, else None.

    Stateless, time-bounded, and never raises — safe to call at the start of a run.
    """
    try:
        result = check_update(timeout=timeout)
    except Exception:  # noqa: BLE001
        return None
    return result["latest"] if result["status"] == "update_available" else None


# --------------------------------------------------------------------------- #
# uv-based update
# --------------------------------------------------------------------------- #
def find_uv():
    """Locate the uv executable, or None. Tries PATH then uv's default install dirs."""
    exe = shutil.which("uv")
    if exe:
        return exe
    home = Path.home()
    candidates = []
    env_dir = os.environ.get("UV_INSTALL_DIR")
    if env_dir:
        candidates.append(Path(env_dir) / ("uv.exe" if os.name == "nt" else "uv"))
    if os.name == "nt":
        candidates += [
            home / ".local" / "bin" / "uv.exe",
            home / "AppData" / "Roaming" / "uv" / "uv.exe",
        ]
    else:
        candidates.append(home / ".local" / "bin" / "uv")
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def perform_update(tag):
    """Reinstall the tool at `tag` via uv. Raises UpdateError on any failure.

    On Windows the running command shim is file-locked, so an in-place reinstall while this
    process is alive can fail; the raised message then points the user at the exact uv command
    to run from a fresh shell.
    """
    uv = find_uv()
    manual = (f"uv tool install {DIST_NAME} --from '{git_source(tag)}' --force")
    if not uv:
        raise UpdateError(
            "uv was not found on PATH. Update manually with:\n    " + manual)
    cmd = [uv, "tool", "install", DIST_NAME, "--from", git_source(tag), "--force"]
    try:
        proc = subprocess.run(cmd)
    except OSError as e:
        raise UpdateError(f"could not run uv ({e}). Update manually with:\n    " + manual)
    if proc.returncode != 0:
        raise UpdateError(
            f"uv exited with code {proc.returncode}; your current version is unchanged.\n"
            "If you are on Windows, close this command and run:\n    " + manual)


# --------------------------------------------------------------------------- #
# uv-based uninstall
# --------------------------------------------------------------------------- #
# InstallKind — how this tool is currently installed, decided before `--uninstall` acts.
UV_MANAGED = "uv_managed"          # installed as a uv tool -> removable via uv
NOT_INSTALLED = "not_installed"    # no distribution metadata -> running from a source tree
PIP_OR_SOURCE = "pip_or_source"    # a distribution, but not a uv tool (e.g. `pip install .`)
UNKNOWN_UV_ABSENT = "unknown_uv_absent"  # a distribution present, but uv cannot be located


def _distribution_installed():
    """True if this tool is installed as a distribution (not merely an uninstalled source tree).

    Distinct from `read_installed_version()`, which falls back to the committed VERSION file and so
    reports a version even when nothing is installed.
    """
    try:
        _dist_version(DIST_NAME)
        return True
    except PackageNotFoundError:
        return False


def uv_tool_list_names(uv_path):
    """Return the set of installed uv tool (distribution) names, or an empty set on any failure.

    Parses `uv tool list`, whose output lists each tool as a top-level line (`name vX.Y.Z`)
    followed by indented/`- `-prefixed entry-point lines. Only the top-level names are collected.
    Never raises — a probe failure is treated as "no uv tools".
    """
    try:
        proc = subprocess.run([uv_path, "tool", "list"], capture_output=True, text=True)
    except OSError:
        return set()
    if proc.returncode != 0:
        return set()
    names = set()
    for line in proc.stdout.splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith("-"):
            continue
        parts = line.split()
        if parts:
            names.add(parts[0])
    return names


def classify_uninstall(uv_path=None):
    """Classify how this tool is installed, to decide how `--uninstall` should behave.

    Returns one of UV_MANAGED / NOT_INSTALLED / PIP_OR_SOURCE / UNKNOWN_UV_ABSENT. Detection is
    performed before any prompt so the command never prompts in a state where it cannot act.
    """
    if not _distribution_installed():
        return NOT_INSTALLED
    uv = uv_path or find_uv()
    if not uv:
        return UNKNOWN_UV_ABSENT
    if DIST_NAME in uv_tool_list_names(uv):
        return UV_MANAGED
    return PIP_OR_SOURCE


def perform_uninstall(uv_path=None):
    """Remove the uv-installed tool. Raises UninstallError on any failure.

    On Windows the running command shim can be file-locked, so an in-place uninstall while this
    process is alive can fail; the raised message then points the user at the exact command to run
    from a fresh shell (mirroring `perform_update`).
    """
    uv = uv_path or find_uv()
    manual = f"uv tool uninstall {DIST_NAME}"
    if not uv:
        raise UninstallError(
            "uv was not found on PATH. Uninstall manually with:\n    " + manual)
    cmd = [uv, "tool", "uninstall", DIST_NAME]
    try:
        proc = subprocess.run(cmd)
    except OSError as e:
        raise UninstallError(f"could not run uv ({e}). Uninstall manually with:\n    " + manual)
    if proc.returncode != 0:
        raise UninstallError(
            f"uv exited with code {proc.returncode}; the tool may not be fully removed.\n"
            "If you are on Windows, close this command and run:\n    " + manual)
