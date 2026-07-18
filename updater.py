"""
Self-updater library for the Cisco Advisory Impact Analyzer.

Standard library only, and intentionally runnable on the *base* Python interpreter (like
install.py) — it must be able to repair an install even when the .venv or the app's
dependencies are broken. It never imports the analyzer modules and never reads, transmits,
or overwrites the user's data (the preserve-list: .env, inventory/, output/, .venv/).

Networking uses urllib, which honors HTTP(S)_PROXY environment variables (same as cisco.py).

The thin CLI wrapper is update.py; run.py uses read_installed_version() and passive_check().
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "VERSION"
MANIFEST_FILE = ROOT / "MANIFEST"
REQUIREMENTS = ROOT / "requirements.txt"
BACKUP_DIR = ROOT / ".update-backup"
MARKER_FILE = ROOT / ".update-in-progress"

# User/local data an update must never modify or delete.
PRESERVE = {".env", "inventory", "output", ".venv"}
# Updater-managed paths that must never be treated as replaceable "app files".
INTERNAL = {".git", ".update-backup", ".update-in-progress"}

ASSET_NAME = "cisco-advisory-impact-analyzer.zip"
CHECKSUM_SUFFIX = ".sha256"
DEFAULT_REPO = "xavient/cisco-advisory-impact-analyzer"
UA = {"User-Agent": "cisco-advisory-impact-analyzer-updater"}


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class UpdaterError(Exception):
    """Base class for updater failures."""


class VerificationError(UpdaterError):
    """The downloaded package failed integrity/version verification."""


class ApplyReverted(UpdaterError):
    """Applying the update failed, but the previous version was restored."""


class ApplyRevertFailed(UpdaterError):
    """Applying the update failed AND the automatic revert also failed."""


# --------------------------------------------------------------------------- #
# Repo / URLs
# --------------------------------------------------------------------------- #
def repo():
    return os.environ.get("CAIA_UPDATE_REPO", "").strip() or DEFAULT_REPO


def api_latest_url():
    return f"https://api.github.com/repos/{repo()}/releases/latest"


def latest_redirect_url():
    return f"https://github.com/{repo()}/releases/latest"


def asset_url(tag):
    return f"https://github.com/{repo()}/releases/download/{tag}/{ASSET_NAME}"


def checksum_url(tag):
    return asset_url(tag) + CHECKSUM_SUFFIX


# --------------------------------------------------------------------------- #
# Version reading & comparison
# --------------------------------------------------------------------------- #
def read_installed_version():
    """Return the installed version string, or None if missing/unreadable/blank."""
    try:
        text = VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


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
# Latest-release discovery (GitHub API, with redirect fallback)
# --------------------------------------------------------------------------- #
def _open(url, timeout, headers=None):
    req = urllib.request.Request(url, headers=headers or UA)
    return urllib.request.urlopen(req, timeout=timeout)


def _latest_via_api(timeout):
    headers = dict(UA)
    headers["Accept"] = "application/vnd.github+json"
    with _open(api_latest_url(), timeout, headers) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    tag = data.get("tag_name")
    return tag.strip() if tag else None


def _latest_via_redirect(timeout):
    # /releases/latest 302-redirects to /releases/tag/<version>; urllib follows it.
    with _open(latest_redirect_url(), timeout) as resp:
        final = resp.geturl()
    marker = "/releases/tag/"
    idx = final.find(marker)
    if idx == -1:
        return None
    tag = final[idx + len(marker):].strip("/").split("/")[0].split("?")[0]
    return tag or None


def resolve_latest(timeout=10):
    """Return (tag, reachable). On any failure the fallback is tried; then (None, False)."""
    try:
        tag = _latest_via_api(timeout)
        if tag:
            return tag, True
    except Exception:  # noqa: BLE001 - rate limit (403), offline, proxy, bad JSON
        pass
    try:
        tag = _latest_via_redirect(timeout)
        if tag:
            return tag, True
    except Exception:  # noqa: BLE001
        pass
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

    Stateless and never raises — safe to call from run.py before a normal analyzer run.
    """
    try:
        result = check_update(timeout=timeout)
    except Exception:  # noqa: BLE001
        return None
    return result["latest"] if result["status"] == "update_available" else None


# --------------------------------------------------------------------------- #
# Manifest helpers (pure)
# --------------------------------------------------------------------------- #
def read_manifest(path):
    """Read a MANIFEST file into a list of relative POSIX paths (skip blanks/comments)."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def is_preserved(rel_path):
    """True if a repo-relative path is under the preserve-list or an updater-internal path."""
    top = str(rel_path).replace("\\", "/").split("/", 1)[0]
    return top in PRESERVE or top in INTERNAL


def manifest_removals(old_manifest, new_manifest):
    """Paths present in old but not new, excluding preserve-list / internal paths."""
    new_set = set(new_manifest)
    return [p for p in old_manifest
            if p not in new_set and not is_preserved(p)]


# --------------------------------------------------------------------------- #
# Download & verify
# --------------------------------------------------------------------------- #
def _download(url, dest, timeout):
    with _open(url, timeout) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


def download_release(tag, dest_dir, timeout=60):
    """Download the tag-pinned zip + .sha256 into dest_dir. Returns (zip_path, sha_path)."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    zip_path = dest / ASSET_NAME
    sha_path = dest / (ASSET_NAME + CHECKSUM_SUFFIX)
    _download(asset_url(tag), zip_path, timeout)
    _download(checksum_url(tag), sha_path, timeout)
    return zip_path, sha_path


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _expected_sha(sha_path):
    text = Path(sha_path).read_text(encoding="utf-8", errors="replace").strip()
    return text.split()[0].lower() if text else ""


def _find_package_root(extract_dir):
    """Locate the directory that contains a VERSION file, searching depth <= 2."""
    extract_dir = Path(extract_dir)
    if (extract_dir / "VERSION").is_file():
        return extract_dir
    for d1 in sorted(p for p in extract_dir.iterdir() if p.is_dir()):
        if (d1 / "VERSION").is_file():
            return d1
        for d2 in sorted(p for p in d1.iterdir() if p.is_dir()):
            if (d2 / "VERSION").is_file():
                return d2
    return None


def verify_package(zip_path, sha_path, tag, extract_dir):
    """Verify SHA-256 + well-formed zip + embedded VERSION == tag; extract; return the root.

    Raises VerificationError on any failure (before any installed file is touched).
    """
    expected = _expected_sha(sha_path)
    actual = _sha256(zip_path)
    if not expected or actual != expected:
        raise VerificationError(
            f"checksum mismatch (expected {expected or 'none'}, got {actual})")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            bad = zf.testzip()
            if bad is not None:
                raise VerificationError(f"corrupt archive entry: {bad}")
            zf.extractall(extract_dir)
    except zipfile.BadZipFile as e:
        raise VerificationError(f"not a valid zip archive: {e}")
    root = _find_package_root(extract_dir)
    if root is None:
        raise VerificationError("package has no VERSION file")
    embedded = (root / "VERSION").read_text(encoding="utf-8").strip()
    if compare_versions(embedded, tag) != 0:
        raise VerificationError(f"package version {embedded!r} does not match tag {tag!r}")
    return root


# --------------------------------------------------------------------------- #
# Backup / apply / rollback
# --------------------------------------------------------------------------- #
def _timestamp():
    return time.strftime("%Y%m%d-%H%M%S")


def _iter_files(root):
    """Yield (abs_path, rel_posix) for every file under root."""
    root = Path(root)
    for p in root.rglob("*"):
        if p.is_file():
            yield p, p.relative_to(root).as_posix()


def read_marker():
    try:
        return json.loads(MARKER_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_marker(old_version, target_version, backup_path):
    MARKER_FILE.write_text(
        json.dumps({"old_version": old_version,
                    "target_version": target_version,
                    "backup_path": str(backup_path)}),
        encoding="utf-8")


def clear_marker():
    try:
        MARKER_FILE.unlink()
    except OSError:
        pass


def create_backup(new_root, old_manifest, new_manifest):
    """Back up files the update will overwrite or remove (never the preserve-list).

    Returns the backup directory path.
    """
    old_version = read_installed_version() or "unknown"
    backup = BACKUP_DIR / f"{old_version}-{_timestamp()}"
    backup.mkdir(parents=True, exist_ok=True)

    to_touch = {rel for _, rel in _iter_files(new_root)}
    to_touch.update(manifest_removals(old_manifest, new_manifest))

    for rel in sorted(to_touch):
        if is_preserved(rel):
            continue
        src = ROOT / rel
        if src.is_file():
            dst = backup / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return backup


def apply_update(new_root):
    """Overlay staged files (skipping preserve-list) and apply manifest-driven removals.

    A backup and the in-progress marker MUST already exist. Raises on any failure.
    """
    old_manifest = read_manifest(MANIFEST_FILE)
    new_manifest = read_manifest(Path(new_root) / "MANIFEST")

    # Add / overwrite everything shipped in the package.
    for src, rel in _iter_files(new_root):
        if is_preserved(rel):
            continue
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # Remove files that were dropped between versions (only if we have both manifests).
    if old_manifest and new_manifest:
        for rel in manifest_removals(old_manifest, new_manifest):
            target = ROOT / rel
            try:
                if target.is_file():
                    target.unlink()
            except OSError:
                pass


def refresh_deps_if_changed(old_requirements_text):
    """Reinstall deps into the .venv if requirements.txt changed.

    Returns: 'unchanged', 'refreshed', or 'venv-missing'. Raises if pip fails.
    """
    new_text = REQUIREMENTS.read_text(encoding="utf-8") if REQUIREMENTS.exists() else ""
    if new_text == (old_requirements_text or ""):
        return "unchanged"
    py = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not py.exists():
        return "venv-missing"
    subprocess.run([str(py), "-m", "pip", "install", "-r", str(REQUIREMENTS)], check=True)
    return "refreshed"


def _newest_backup():
    if not BACKUP_DIR.is_dir():
        return None
    dirs = [d for d in BACKUP_DIR.iterdir() if d.is_dir()]
    return max(dirs, key=lambda d: d.stat().st_mtime) if dirs else None


def restore_backup(backup=None):
    """Restore the given (or newest) backup over the install; returns the backup used.

    Removes files the update had added (present now, absent from the backed-up manifest),
    then restores the backed-up files. Never touches the preserve-list. Raises UpdaterError
    if no backup exists.
    """
    backup = Path(backup) if backup else _newest_backup()
    if not backup or not backup.is_dir():
        raise UpdaterError("no backup available to restore")

    old_manifest = set(read_manifest(backup / "MANIFEST"))
    if old_manifest:
        for rel in read_manifest(MANIFEST_FILE):
            if rel in old_manifest or is_preserved(rel):
                continue
            target = ROOT / rel
            try:
                if target.is_file():
                    target.unlink()
            except OSError:
                pass

    for src, rel in _iter_files(backup):
        if is_preserved(rel):
            continue
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return backup


def prune_backups(keep=2):
    """Keep only the newest `keep` backups; remove older ones."""
    if not BACKUP_DIR.is_dir():
        return
    dirs = sorted((d for d in BACKUP_DIR.iterdir() if d.is_dir()),
                  key=lambda d: d.stat().st_mtime, reverse=True)
    for old in dirs[keep:]:
        shutil.rmtree(old, ignore_errors=True)


def apply_with_backup(new_root, tag):
    """Backup -> marker -> apply -> refresh deps -> prune -> clear marker.

    Returns {'deps': <status>, 'backup': <path>}. On apply failure, auto-reverts and raises
    ApplyReverted (revert ok) or ApplyRevertFailed (revert also failed).
    """
    old_version = read_installed_version() or "unknown"
    old_manifest = read_manifest(MANIFEST_FILE)
    new_manifest = read_manifest(Path(new_root) / "MANIFEST")
    old_req = REQUIREMENTS.read_text(encoding="utf-8") if REQUIREMENTS.exists() else ""

    backup = create_backup(new_root, old_manifest, new_manifest)
    _write_marker(old_version, tag, backup)

    try:
        apply_update(new_root)
    except Exception as apply_err:  # noqa: BLE001
        try:
            restore_backup(backup)
        except Exception as revert_err:  # noqa: BLE001 - leave marker for manual recovery
            raise ApplyRevertFailed(f"{apply_err}; revert error: {revert_err}") from apply_err
        clear_marker()
        raise ApplyReverted(str(apply_err)) from apply_err

    # Code is applied and valid; a dep-refresh failure does not roll back the code.
    try:
        deps = refresh_deps_if_changed(old_req)
    except Exception:  # noqa: BLE001
        deps = "refresh-failed"

    prune_backups(keep=2)
    clear_marker()
    return {"deps": deps, "backup": backup}


def recover_if_interrupted():
    """If a prior update left an in-progress marker, restore from its backup.

    Returns True if a recovery was performed.
    """
    marker = read_marker()
    if not marker:
        return False
    try:
        restore_backup(marker.get("backup_path"))
    except UpdaterError:
        pass
    clear_marker()
    return True
