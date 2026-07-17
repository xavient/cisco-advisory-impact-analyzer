# Implementation Plan: Self-Update Mechanism (Auto-Updater)

**Branch**: `003-auto-updater` | **Date**: 2026-07-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-auto-updater/spec.md`

## Summary

Add a one-command, standard-library-only self-updater to the flat Python CLI. A plain-text
`VERSION` file becomes the single source of truth for the installed version (read by the
updater, the passive nudge, and `run.py --version`). A new `update.py` (thin CLI) over a new
`updater.py` (stdlib helper module) resolves the latest release from GitHub, compares it to
the installed version with **semantic-version ordering**, and — on confirmation — downloads
the release asset pinned to the resolved tag, **verifies it against the release's SHA-256
checksum** (plus a well-formed-archive + embedded-`VERSION`-matches-tag check), **backs up**
the files it will replace, then overlays the new files **skipping the preserve-list**
(`.env`, `inventory/`, `output/`, `.venv/`). If the requirements changed it refreshes deps
via the existing `.venv` pip. Any error after backup triggers an **automatic revert**; a
`--rollback` command restores the most recent backup on demand. A best-effort, stateless,
short-timeout **passive nudge** in `run.py` tells users when a newer version exists. A new
**GitHub Actions release workflow** guarantees every release ships a package whose embedded
`VERSION` equals the tag, a `MANIFEST`, and a `.sha256` checksum — so the version and
integrity checks never drift (FR-020/FR-021).

The updater runs on the **base Python** (no reliance on `.venv`), mirroring `install.py`, so
it can recover a broken environment. All networking uses `urllib` (proxy-aware, like
`cisco.py`); all output uses the existing `ui` module.

## Technical Context

**Language/Version**: Python 3.9+ (Constitution Technology Constraints). New code targets the
same floor as `install.py`/`run.py` and, like the installer, runs on the **base interpreter**
without importing analyzer modules or requiring `.venv`.

**Primary Dependencies**: **None added** (Constitution Principle I). Updater uses only the
standard library: `urllib.request`/`urllib.error` (HTTP + proxy), `json` (GitHub API),
`hashlib` (SHA-256), `zipfile` (archive), `tempfile`/`shutil`/`pathlib`/`os` (staging,
backup, overlay), `argparse` (CLI), and the existing in-repo `ui` module for output. The
dependency **refresh** step shells out to the existing `.venv`'s `pip` (as `install.py`
does) — it does not import third-party packages into the updater.

**Storage**: Local files inside the tool folder only. New on-disk artifacts: a tracked
plain-text `VERSION`; a shipped `MANIFEST` (list of packaged paths); a gitignored
`.update-backup/<version>-<timestamp>/` backup tree; and a transient `.update-in-progress`
marker used for crash/interrupt recovery. No database; no persisted network state (the
passive nudge is stateless).

**Testing**: `unittest` (the repo's existing suite, run via `python -m unittest discover -s
tests`). New offline unit tests cover the pure logic: semantic-version parse/compare,
manifest add/remove diff, preserve-list exclusion, and `VERSION` read/validate. Network,
download/verify, and apply/rollback flows are validated manually via
[quickstart.md](./quickstart.md) against a real release (network-dependent, not in CI).

**Target Platform**: Windows, macOS, Linux (Constitution Principle II). `pathlib` + `os.name`
guards; no shell/path assumptions; invoked as `python update.py` (Windows) / `python3
update.py` (macOS/Linux), matching the `install.py`/`run.py` convention.

**Project Type**: Flat single-project CLI (same shape as the existing analyzer). This feature
adds a self-contained updater plus one CI workflow; it changes `run.py`, `.gitignore`, and
the docs, and touches **no** analysis logic.

**Performance Goals**: Check (installed vs latest) completes in < 10 s when reachable
(SC-008); full update completes in < 2 min on a normal connection (SC-001); the passive
nudge adds no noticeable delay (short timeout, best-effort — FR-016).

**Constraints**: Standard-library-only (Principle I); must run without a working `.venv`
(recover broken installs); must never read, transmit, log, or overwrite `.env` (Principle V,
FR-017); preserve-list is inviolable (FR-002); the install must always be fully-old or
fully-new and recoverable (FR-012); HTTPS-only from the official repo, proxy-honored
(FR-014); graceful under GitHub rate limits / offline (FR-015).

**Scale/Scope**: Small — a handful of shipped files, one release archive (< a few MB), one
container-free CLI. New endpoint surface: GitHub only.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against Constitution **v1.2.0**:

- **I. Standard-Library-First & Minimal Dependencies** — **PASS**. Zero new runtime
  dependencies: `urllib`, `hashlib`, `zipfile`, `json`, `shutil`, `tempfile`, `pathlib`,
  `argparse` are all stdlib. HTTP mirrors `cisco.py`'s existing `urllib.request` usage. The
  dependency-refresh step reuses the `.venv` pip that `install.py` already drives.
- **II. Cross-Platform Parity** — **PASS**. `pathlib`/`os.name` throughout; no shell-outs for
  file ops; `python[3] update.py` entry mirrors `install.py`/`run.py`; self-replacement is
  handled in an OS-neutral way (see research D7); backup/overlay use `shutil`.
- **III. CLI-First, Scriptable Interface** — **PASS**. `update.py` offers interactive
  (confirm prompt via `ui.confirm`) **and** flag-driven modes (`--check`, `--yes`,
  `--rollback`); `run.py` gains `--version` and `--no-update-check`. Errors are actionable
  (`ui.fail` + hint), exit codes are meaningful (0 success/up-to-date; distinct non-zero per
  failure class; 130 on interrupt via the existing `run_cli` pattern).
- **IV. Conservative & Traceable Analysis (NON-NEGOTIABLE)** — **PASS (N/A)**. No advisory,
  CSAF, inventory, or AI logic is touched. `analyzer.py`, `cisco.py`, `fuelix.py`,
  `inventory.py`, `report.py` are unchanged.
- **V. Secrets Hygiene & Data Locality** — **PASS (reinforced)**. `.env` is on the
  preserve-list (never backed up, overwritten, or deleted) and is never read or transmitted
  by the updater. Only the minimum GitHub metadata/artifact traffic occurs; **no inventory or
  secret leaves the machine**. `.gitignore` continues to exclude secrets/inventory/reports
  and adds the backup tree.
- **Technology & Data Constraints — new external endpoint (REVIEWED CHANGE)** — **PASS with
  justification**. The constitution states only `sec.cloudapps.cisco.com` and
  `api.fuelix.ai` are contacted and that *"adding a new external endpoint is a reviewed
  change."* This feature intentionally adds GitHub (`api.github.com`, `github.com`, and the
  asset-redirect host `objects.githubusercontent.com`) — the update source. Justification:
  it is the entire purpose of the feature, is HTTPS-only, sends no secrets or inventory, and
  is the **same source** the landing page (`docs/index.html`) already queries. The reviewed
  change is ratified **in this PR** by an early Foundational governance-gate task (tasks
  **T005**) that amends the constitution's allowed-endpoints list **before** any
  endpoint-contacting code lands (see research D13). Not a violation → no Complexity
  Tracking entry.
- **Branching Strategy** — **PASS**. Work is on `003-auto-updater`, to merge to `main` via PR.
- **Development Workflow & Quality Gates** — **PASS**. New pure-logic tests added (semver,
  manifest diff, preserve-list). README **and** `docs/index.html` are updated in the same PR
  for the new update/`--version` flow (Documentation gate). No analysis parsing changed, so
  no CSAF/inventory test changes are required.

No unjustified violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/003-auto-updater/
├── plan.md                    # This file (/speckit-plan output)
├── research.md                # Phase 0 output — decisions D1–D14
├── data-model.md              # Phase 1 output — entities, on-disk artifacts, state machine
├── quickstart.md              # Phase 1 output — runnable validation scenarios
├── contracts/                 # Phase 1 output
│   ├── cli.md                 # update.py + run.py (--version, --no-update-check) contract
│   └── release-artifacts.md   # release workflow + asset naming/format contract (FR-020/021)
└── tasks.md                   # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Flat single-project layout. New files and the (small) set of touched files:

```text
VERSION                     # NEW: plain-text single source of truth for the installed
                            #      version (e.g. "1.2.0"); shipped in every release package.
MANIFEST                    # NEW: newline-separated list of packaged paths, shipped in the
                            #      package; used to remove files dropped between versions.
update.py                   # NEW: thin CLI — `python3 update.py [--check|--rollback|--yes]`.
                            #      Runs on base Python; delegates to updater.py; uses ui.
updater.py                  # NEW: stdlib-only library — installed_version(), latest_release()
                            #      (GitHub API + redirect fallback), semver compare,
                            #      download+verify (SHA-256/zip/VERSION), backup, apply
                            #      (overlay minus preserve-list), manifest diff, rollback,
                            #      dependency refresh, passive check helper.

run.py                      # MODIFIED: add `--version` (print VERSION) handled before
                            #           delegating; add best-effort passive update nudge with
                            #           `--no-update-check` / CAIA_NO_UPDATE_CHECK opt-out.
.gitignore                  # MODIFIED: ignore /.update-backup/ and /.update-in-progress.
README.md                   # MODIFIED: document `python3 update.py`, `--version`, rollback,
                            #           and the update-check opt-out (Documentation gate).
docs/index.html             # MODIFIED: note in-place updating via `python3 update.py`
                            #           (Documentation gate — mirror README).

.github/workflows/
└── release.yml             # NEW: on tag push — stamp VERSION=tag, build the package (flat
                            #      zip excluding dev/user files), generate MANIFEST + SHA-256,
                            #      attach zip + .sha256 to the GitHub release (FR-020/FR-021).

tests/
└── test_updater.py         # NEW: offline unit tests — semver parse/compare, manifest
                            #      add/remove diff, preserve-list exclusion, VERSION read.

# Unchanged: analyzer.py, cisco.py, inventory.py, fuelix.py, report.py, install.py, ui.py
# Unchanged: tests/test_extraction.py, tests/test_folders.py
```

**Structure Decision**: Keep the flat layout (consistent with the existing tool). Split the
updater into a **library** (`updater.py`, stdlib-only, unit-testable in isolation) and a
**thin CLI** (`update.py`), so the pure logic (semver, manifest diff, preserve-list) is
tested offline while the CLI stays a small orchestration layer — the same
library/entrypoint separation the constitution's testability gate rewards. `run.py` imports
only the lightweight version/check helpers from `updater.py` for `--version` and the nudge.
The release workflow lives under `.github/workflows/` and is the maintainer-side counterpart
that keeps `VERSION`/checksum honest.

## Complexity Tracking

> No unjustified constitutional violations. The single reviewed change (new GitHub endpoint)
> is justified inline in the Constitution Check and in research D13; section intentionally
> empty.
