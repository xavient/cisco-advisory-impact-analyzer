# Implementation Plan: uv Tool Distribution

**Branch**: `004-uv-tool-distribution` | **Date**: 2026-07-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-uv-tool-distribution/spec.md`

## Summary

Repackage the analyzer so it installs and runs as a `uv` tool: `uv tool install cisco-advisory-impact-analyzer --from git+https://github.com/xavient/cisco-advisory-impact-analyzer` puts a single `cisco-advisory-impact-analyzer` command on the user's PATH that runs from any folder. The current clone + `install.py` + `run.py` + in-repo self-updater flow is retired. The analysis logic itself is unchanged; the work is packaging (a `pyproject.toml` with a console-script entry point and the runtime modules moved into an importable package), a unified CLI dispatcher (`--help`/`--version`/`--update`/`--config` plus the existing analysis flags), per-user configuration replacing the repo-local `.env`, a uv-orchestrated update path replacing the file-overlay updater, and reading inputs/writing `output/` relative to the current working folder. Because Principle II currently mandates `install.py`/`run.py`/`.venv`, this feature also amends the constitution.

## Technical Context

**Language/Version**: Python 3.9+ (constitution Technology & Data Constraints; must stay 3.9-compatible even though the dev machine runs newer)

**Primary Dependencies**: Runtime — `openpyxl` (Excel), `python-dotenv` (optional `.env` parsing, already present). Build — `setuptools` build backend (build-time only, not shipped at runtime). External prerequisite — `uv` on the end user's machine (install/run/update). No new runtime dependency is added: per-user config directories and the update orchestration use only the standard library + a `uv` subprocess.

**Storage**: Files only. Per-user config file in an OS-appropriate config directory (secret: FueliX API key, owner-only permissions where supported); inventory `.xlsx` read from the current working folder; timestamped `.xlsx` reports written to `./output/` in the current working folder.

**Testing**: `unittest` (stdlib, per minimal-dependencies principle), run via `python -m unittest discover -s tests`. Existing `test_extraction.py`, `test_folders.py`, `test_updater.py` are updated/retargeted; new tests cover config resolution/precedence, version reporting, and the CWD-relative inventory/output behavior.

**Target Platform**: macOS, Windows, Linux (cross-platform parity, Principle II).

**Project Type**: Single-project CLI tool distributed as a uv tool.

**Performance Goals**: Analysis performance unchanged (FR-022). The run-start version check and `--version` check are bounded to ~2 s and skipped on timeout (FR-006, FR-013, SC-008).

**Constraints**: Standard-library-first networking (Principle I); the analyzer contacts only `sec.cloudapps.cisco.com` and `api.fuelix.ai`; version/update checks contact only GitHub release endpoints and transmit no inventory or secrets (FR-023). Ctrl+C exits with code 130 and no traceback (Principle III, FR-012).

**Scale/Scope**: Single-user desktop CLI; inventories on the order of ~1000 firewall rows collapsed into combos (unchanged from today).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.4.0. Gate-by-gate:

- **I. Standard-Library-First & Minimal Dependencies** — PASS. No new *runtime* dependency: per-user config paths, secret-file permissions, and the update flow use only stdlib (`os`, `pathlib`, `importlib.metadata`, `subprocess`, existing `urllib`). `setuptools` is a build-time-only backend, not shipped. `uv` is an external prerequisite, not a Python package dependency. `openpyxl` and `python-dotenv` are unchanged.
- **II. Cross-Platform Parity** — ⚠️ CONFLICT (intended amendment). Principle II literally requires setup/execution "through the provided `install.py` / `run.py` entry points and the self-contained `.venv`, without requiring the user to activate the virtual environment manually." FR-024 retires exactly those entry points. The *intent* of Principle II (identical behavior on macOS/Windows/Linux, no venv activation) is preserved and strengthened by uv. This is resolved by amending Principle II (and the Technology & Data Constraints + self-updater references) as part of this feature — see Complexity Tracking.
- **III. CLI-First, Scriptable Interface** — PASS. A single CLI exposes every capability; FR-025 keeps a fully flag-driven mode (`--url`, `--inventory`, `--output-dir`, `--dry-run`) that skips prompts; errors stay actionable; exit codes remain meaningful (130 on interrupt).
- **IV. Conservative & Traceable Analysis (NON-NEGOTIABLE)** — PASS. Analysis behavior is explicitly unchanged (FR-022); no advisory/CSAF/inventory/AI logic is touched.
- **V. Secrets Hygiene & Data Locality** — PASS (with a location change). The API key moves from a repo-local `.env` to a per-user config file with owner-only permissions; it is still never committed, logged, or printed, and env vars still take precedence. Inventory stays local; only the same minimum context is sent to FueliX. The constitution's Technology & Data Constraints (which reference the in-repo updater's GitHub endpoints) are updated to describe uv-based updates.

**Result**: One gate (II) fails against the *letter* of the current constitution and is remediated by a constitution amendment delivered within this feature (FR-024 already mandates updating the constitution). Documented in Complexity Tracking; not an unjustified violation.

**Post-Design Re-check (after Phase 1)**: No change. Phase 0/1 confirmed the design adds **no new runtime dependency** — per-user config paths and secret-file permissions use stdlib (`os`/`pathlib`), the version is read with stdlib `importlib.metadata` (D2), version discovery reuses the existing `urllib` code (D5), and `setuptools` is build-time only — so Principle I still passes. The API key relocates to a per-user, owner-only file (Principle V intact). Gate II remains the sole item and is closed by the constitution amendment tracked in Complexity Tracking. No new violations were introduced by the design.

## Project Structure

### Documentation (this feature)

```text
specs/004-uv-tool-distribution/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── cli.md           # Command surface, flags, exit codes, prompt flow
│   └── config.md        # Per-user config file schema + precedence
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created here)
```

### Source Code (repository root)

The flat top-level modules move into an importable package so setuptools can ship them and
expose a single console script. Runtime modules keep their names and internal logic; new
modules add the CLI dispatcher, per-user config, and uv-based update/version handling.

```text
pyproject.toml                       # NEW: packaging metadata, console script, dynamic version from VERSION
VERSION                              # UNCHANGED role: single source of truth for the product version
README.md                            # UPDATED: uv install/run/update as the only documented path (FR-024)
docs/index.html                      # UPDATED: uv install/run/update (FR-024)
CONTRIBUTING.md                      # UPDATED: release runbook drops zip/checksum packaging
.github/workflows/
├── ci.yml                           # UPDATED: install via uv / run tests against the package
└── release.yml                      # UPDATED: keep tag==VERSION gate + GitHub Release; drop zip+sha256 build

cisco_advisory_impact_analyzer/      # NEW package (moved from flat modules)
├── __init__.py
├── cli.py                           # NEW: single entry point; dispatches --help/--version/--update/--config/run
├── analyzer.py                      # MOVED: run flow; inventory discovery + output now CWD-relative; interactive picker
├── cisco.py                         # MOVED unchanged
├── fuelix.py                        # MOVED unchanged
├── inventory.py                     # MOVED unchanged
├── report.py                        # MOVED unchanged
├── ui.py                            # MOVED unchanged (+ any menu/select helper for the model list & picker)
├── config.py                        # NEW: per-user config dir, load/save, precedence (env > file > default), perms
└── version.py                       # NEW: installed version (importlib.metadata) + GitHub latest check + uv update

tests/
├── test_extraction.py              # RETARGETED imports (package-qualified)
├── test_folders.py                 # UPDATED: CWD-relative inventory/output + interactive picker
├── test_config.py                  # NEW: config resolution, precedence, permissions
└── test_version.py                 # NEW: version compare + check_update status mapping (reused pure logic)

# RETIRED (removed by FR-024):
#   install.py, run.py, update.py (thin CLI), MANIFEST,
#   updater.py's download/verify/backup/apply/rollback half (version-discovery half is
#     kept, relocated into version.py), tools/release.py's zip assumptions,
#   tools/install-test/ (clone-install harness), tools/updater-sim.py
```

**Structure Decision**: Single-project layout with a flat package directory
`cisco_advisory_impact_analyzer/` at the repository root (not a `src/` layout), so
`python -m unittest discover -s tests` keeps working with a simple path insert and no
editable install, while setuptools auto-discovers the package. A `pyproject.toml` with a
`[project.scripts]` entry point named `cisco-advisory-impact-analyzer` produces the single
on-PATH command. The version is single-sourced from the committed `VERSION` file into
package metadata (`[project] dynamic = ["version"]` + `[tool.setuptools.dynamic]`), and read
at runtime with `importlib.metadata.version(...)`, preserving the constitution's "VERSION is
the single source of truth" gate and the release workflow's tag==VERSION check.

## Complexity Tracking

> Constitution Check gate II fails against the current text and requires a documented amendment.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Amend Principle II (remove the `install.py`/`run.py`/`.venv` mandate) | FR-024 makes uv the single distribution/run/update path; the old entry points are retired | Keeping `install.py`/`run.py` alongside uv would leave two conflicting install stories, re-introduce the manual-venv onboarding the feature exists to remove, and keep the constitution describing a flow the product no longer ships |
| Amend Technology & Data Constraints + self-updater references | The in-repo `update.py`/`updater.py` overlay updater is replaced by uv orchestration; the constitution currently documents that updater's GitHub endpoints and behavior | Leaving the old text would make the constitution inaccurate about how updates work and which files touch the network |
