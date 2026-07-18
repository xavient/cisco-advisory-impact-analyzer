#!/usr/bin/env python3
"""Cut a release by tagging the commit with the current VERSION.

VERSION is the single source of truth (see CONTRIBUTING.md and the constitution's
"Versioning & releases" gate). This helper reads VERSION and pushes a matching git
tag, so the tag can never disagree with the committed version — the same invariant
the Release workflow enforces on the CI side. Run it from a clean checkout of `main`
after the VERSION-bump PR has merged.

Usage:
    python tools/release.py            # tag $(cat VERSION) and push it to origin
    python tools/release.py --dry-run  # print what would happen, change nothing
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")  # matches the tag glob in release.yml


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _fail(message: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="print actions without tagging or pushing"
    )
    parser.add_argument(
        "--remote", default="origin", help="git remote to push the tag to (default: origin)"
    )
    args = parser.parse_args()

    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not SEMVER.match(version):
        _fail(f"VERSION ({version!r}) is not a MAJOR.MINOR.PATCH string")

    # Refuse to release from a dirty tree — the tag must point at a committed state.
    if _git("status", "--porcelain"):
        _fail("working tree is not clean; commit or stash changes before releasing")

    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        print(f"warning: releasing from '{branch}', not 'main'", file=sys.stderr)

    existing = _git("tag", "--list", version)
    if existing:
        _fail(f"tag {version} already exists locally; bump VERSION for a new release")

    if args.dry_run:
        print(f"[dry-run] would create tag {version} at {_git('rev-parse', '--short', 'HEAD')}")
        print(f"[dry-run] would run: git push {args.remote} {version}")
        return

    _git("tag", version)
    print(f"created tag {version}")
    subprocess.run(["git", "push", args.remote, version], cwd=ROOT, check=True)
    print(f"pushed {version} to {args.remote} — the Release workflow will build and publish it")


if __name__ == "__main__":
    main()
