# Quickstart & Validation: Self-Update Mechanism (Auto-Updater)

**Feature**: `003-auto-updater` | **Date**: 2026-07-17

Runnable scenarios that prove the feature end-to-end. Commands use `python3` (macOS/Linux);
use `python` on Windows. Interface details live in [contracts/cli.md](./contracts/cli.md) and
[contracts/release-artifacts.md](./contracts/release-artifacts.md); the entities and state
machine live in [data-model.md](./data-model.md). This guide is a validation checklist, not
implementation.

## Prerequisites

- An installed copy of the tool (run `python3 install.py` once) with a populated `.env`, an
  `inventory/*.xlsx`, and at least one report in `output/`.
- Network access to GitHub (through your proxy if any). Offline scenarios are called out.
- Two published test releases available (an older and a newer), or the `CAIA_UPDATE_REPO`
  override pointed at a fork with test releases (see [research D13](./research.md)).

> **Tip — simulate "older install"**: set the local `VERSION` to a value below the latest
> release (e.g. `echo 1.0.0 > VERSION`) to exercise the update path against a real newer
> release without publishing anything.

---

## Scenario 1 — Report the installed version (US2, FR-010)

```bash
python3 run.py --version
```

**Expect**: prints the version from `VERSION` (e.g. `1.1.0`) and exits `0`. The analyzer does
**not** start.

## Scenario 2 — Check for updates without changing anything (US2, FR-008)

```bash
python3 update.py --check
```

**Expect**: prints `Installed`, `Latest`, and a `Status` line (`up to date` / `update
available` / `ahead of latest`). **No files change.** Confirm with `git status` (only
untracked temp, if any) or by comparing file mtimes.

## Scenario 3 — Update to the latest, preserving data (US1, FR-001/002/006/007)

Record a baseline first:

```bash
shasum .env; ls -l inventory output        # note preserve-list state (use certutil on Windows)
python3 update.py                           # shows current → new, asks to confirm
```

**Expect**: shows `current → new`, downloads, **verifies the SHA-256**, backs up, applies,
refreshes deps if `requirements.txt` changed, prints the new version, exits `0`. Then:

```bash
python3 run.py --version                    # now the new version
shasum .env; ls -l inventory output         # unchanged
python3 run.py --dry-run                     # tool still runs (deps intact)
```

**Expect**: `.env`, `inventory/`, `output/`, `.venv/` are unchanged (SC-002); the analyzer
runs (SC-007).

## Scenario 4 — Already up to date is a no-op (US2, FR-005, SC-003)

```bash
python3 update.py            # immediately after Scenario 3
```

**Expect**: `Already up to date (x.y.z).`, exit `0`, **zero** file changes.

## Scenario 5 — Non-interactive update (FR-009)

```bash
echo 1.0.0 > VERSION         # simulate older install
python3 update.py --yes      # no prompt
```

**Expect**: updates without prompting; exit `0`.

## Scenario 6 — Rollback after an update (US3, FR-011, SC-009)

```bash
python3 update.py --rollback
python3 run.py --version     # back to the prior version
shasum .env; ls -l inventory output   # still unchanged
```

**Expect**: prior application files restored from the newest backup; preserve-list intact.

## Scenario 7 — Integrity failure makes no changes (FR-006, SC-004)

Tamper with verification (e.g. point `CAIA_UPDATE_REPO` at a release whose `.sha256` does not
match its zip, or intercept the download):

```bash
python3 update.py
```

**Expect**: verification fails, actionable message, **exit 4**, and `python3 run.py
--version` still reports the *old* version — no files touched.

## Scenario 8 — Offline / rate-limited degrades gracefully (FR-015)

Disable networking (or set an unreachable `CAIA_UPDATE_REPO`):

```bash
python3 update.py --check     # installed known, latest unknown
python3 update.py             # cannot determine what to update to
```

**Expect (both)**: `latest unknown (could not reach GitHub)` with an actionable hint; **no
files changed**; the installed version is still reported. Exit codes differ by command
(per [contracts/cli.md](./contracts/cli.md)): `--check` exits **0** because it could still
report the installed version, while the update path exits **3** because it cannot determine
the target version.

## Scenario 9 — Passive nudge during a normal run (US4, FR-016)

With the local `VERSION` set below the latest release:

```bash
python3 run.py --dry-run
```

**Expect**: one line like `A new version 1.2.0 is available … python3 update.py`, then the
analysis proceeds normally. Now disable it:

```bash
python3 run.py --dry-run --no-update-check      # or: CAIA_NO_UPDATE_CHECK=1 python3 run.py --dry-run
```

**Expect**: no notice; run proceeds. And offline:

```bash
# with networking off
python3 run.py --dry-run
```

**Expect**: no notice, **no delay** beyond the short timeout, run completes normally (US4-AS2).

## Scenario 10 — Interrupted update stays recoverable (US3, FR-012)

Interrupt an update during the apply phase (Ctrl-C), then re-run:

```bash
python3 update.py            # Ctrl-C mid-apply
python3 update.py            # or: python3 update.py --rollback
```

**Expect**: on the next invocation the `.update-in-progress` marker is detected and the
install is restored to a consistent state (fully old or fully new) — never a broken mixture.

---

## Automated checks (offline unit tests)

```bash
python -m unittest discover -s tests -v
```

**Expect**: `tests/test_updater.py` passes — semantic-version parse/compare (incl.
`1.10.0 > 1.9.0`), manifest add/remove diff, preserve-list exclusion, and `VERSION`
read/validate. These run without network (Constitution testability gate).

## Release-side validation (maintainer, FR-020/021)

After pushing a tag, confirm the workflow produced a valid release
([release-artifacts.md](./contracts/release-artifacts.md)):

```bash
curl -fL -o pkg.zip     https://github.com/xavient/cisco-advisory-impact-analyzer/releases/latest/download/cisco-advisory-impact-analyzer.zip
curl -fL -o pkg.sha256  https://github.com/xavient/cisco-advisory-impact-analyzer/releases/latest/download/cisco-advisory-impact-analyzer.zip.sha256
shasum -a 256 -c pkg.sha256          # digest matches
unzip -p pkg.zip VERSION             # equals the tag
```

**Expect**: checksum matches, and the embedded `VERSION` equals the release tag (no drift).
