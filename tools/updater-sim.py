#!/usr/bin/env python3
"""
Offline, no-network simulator for the self-updater.

Exercises the real updater.py pipeline — build a fake newer release, then
verify_package() -> apply_with_backup() -> restore_backup() — against THIS install,
without contacting GitHub. Use it inside the Docker sandbox (or any checkout) to watch a
full update-and-rollback cycle and confirm the preserve-list is never touched.

    python3 tools/updater-sim.py            # bump the minor version and simulate
    python3 tools/updater-sim.py 3.0.0      # simulate updating to a specific version

It leaves the install exactly as it found it (the demo change is applied, then rolled back,
and the temporary backup it created is removed). Standard library only; runs on base Python.
Tip: run `python3 install.py` first so a real .env / .venv exist for a fuller check.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_ROOT))

import updater  # noqa: E402

DEMO_FILE = "SIM_UPDATED.txt"


def _c(ok, msg):
    print(("  ok " if ok else "  XX ") + msg)
    if not ok:
        raise SystemExit(f"FAILED: {msg}")


def _next_version(current):
    parts = updater.parse_version(current or "")
    if not parts:
        return "9999.0.0"
    major = parts[0]
    minor = parts[1] if len(parts) > 1 else 0
    return f"{major}.{minor + 1}.0"


def _snapshot_preserve():
    """Fingerprint the preserve-list so we can prove it never changes."""
    snap = {}
    for name in sorted(updater.PRESERVE):
        p = APP_ROOT / name
        if p.is_file():
            snap[name] = hashlib.sha256(p.read_bytes()).hexdigest()
        elif p.is_dir():
            snap[name] = sorted(
                (f.relative_to(p).as_posix(), f.stat().st_size)
                for f in p.rglob("*") if f.is_file())
        else:
            snap[name] = None
    return snap


def _build_fake_release(new_version, workdir):
    """Copy the shipped files (per MANIFEST) into a staging dir, bump VERSION, add a demo
    file, regenerate MANIFEST, then zip it flat and write a matching .sha256."""
    staging = workdir / "pkg"
    staging.mkdir()
    manifest = updater.read_manifest(updater.MANIFEST_FILE) or [
        p.name for p in APP_ROOT.glob("*.py")]
    for rel in manifest:
        src = APP_ROOT / rel
        if src.is_file():
            dst = staging / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    (staging / "VERSION").write_text(new_version + "\n", encoding="utf-8")
    (staging / DEMO_FILE).write_text(
        f"This file was added by updater-sim for version {new_version}.\n", encoding="utf-8")
    files = sorted(f.relative_to(staging).as_posix()
                   for f in staging.rglob("*") if f.is_file())
    (staging / "MANIFEST").write_text("\n".join(files) + "\n", encoding="utf-8")

    zip_path = workdir / updater.ASSET_NAME
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in staging.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(staging).as_posix())
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sha_path = zip_path.with_name(zip_path.name + updater.CHECKSUM_SUFFIX)
    sha_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    return zip_path, sha_path


def main():
    new_version = sys.argv[1] if len(sys.argv) > 1 else None
    old_version = updater.read_installed_version()
    new_version = new_version or _next_version(old_version)

    print(f"\nUpdater simulation (offline)  {old_version or 'unknown'} -> {new_version}")
    print("-" * 60)

    preserve_before = _snapshot_preserve()

    with tempfile.TemporaryDirectory(prefix="updater_sim_") as td:
        td = Path(td)
        print("Building a fake release package (no network) ...")
        zip_path, sha_path = _build_fake_release(new_version, td)

        print("1. Verifying package (SHA-256 + well-formed zip + embedded VERSION):")
        new_root = updater.verify_package(zip_path, sha_path, new_version, td / "extract")
        _c(new_root is not None, "package verified")

        print("2. Applying update (backup -> overlay -> deps -> finalize):")
        outcome = updater.apply_with_backup(new_root, new_version)
        _c(updater.read_installed_version() == new_version,
           f"VERSION is now {new_version}")
        _c((APP_ROOT / DEMO_FILE).exists(), f"added file {DEMO_FILE} is present")
        _c(_snapshot_preserve() == preserve_before,
           "preserve-list (.env / inventory / output / .venv) unchanged after apply")
        print(f"     (dependency refresh: {outcome['deps']})")

        print("3. Rolling back (restore the backup):")
        updater.restore_backup()
        _c(updater.read_installed_version() == old_version,
           f"VERSION restored to {old_version or 'unknown'}")
        _c(not (APP_ROOT / DEMO_FILE).exists(),
           f"added file {DEMO_FILE} removed on rollback")
        _c(_snapshot_preserve() == preserve_before,
           "preserve-list unchanged after rollback")

    # Leave the install exactly as we found it.
    shutil.rmtree(updater.BACKUP_DIR, ignore_errors=True)
    updater.clear_marker()

    print("-" * 60)
    print("SIMULATION PASSED — full verify -> apply -> rollback cycle, data preserved.\n")


if __name__ == "__main__":
    main()
