# Implementation Plan: Self-Uninstall Command

**Branch**: `005-self-uninstall` | **Date**: 2026-07-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-self-uninstall/spec.md`

## Summary

Add a `caia --uninstall` command (with a `--yes` flag to skip confirmation) that removes the uv-installed tool the same way `caia --update` reinstalls it — by delegating to `uv`. The command is the mirror of the existing updater: it reuses `version.find_uv()` and the same subprocess/manual-fallback pattern. It confirms before acting (refusing safely when non-interactive without `--yes`), preserves the per-user configuration and discloses its path via `config.config_path()`, never touches user work products, treats "not installed as a uv tool" as an idempotent success (exit 0), and reserves non-zero exits for declined / uv-missing / error. No new runtime dependencies; standard library only.

## Technical Context

**Language/Version**: Python 3.9+ (matches `requires-python` in `pyproject.toml`)

**Primary Dependencies**: None new. Reuses the standard library already used by the updater — `subprocess` (invoke `uv`), `shutil.which` (locate `uv`, via `version.find_uv()`), `importlib.metadata` (detect whether the distribution is installed), `pathlib`/`os` (config-path disclosure, OS guards), `sys` (`stdin.isatty()`). Existing runtime deps (`openpyxl`, `python-dotenv`) are untouched.

**Storage**: N/A. The per-user config file is *read-only referenced* (its path is disclosed, and its existence checked) and is never modified or deleted.

**Testing**: `unittest` + `unittest.mock` (existing suite under `tests/`, run via `pytest`/`python -m pytest`). New cases extend `tests/test_version.py` (removal + detection logic) and `tests/test_cli.py` (flag parsing, dispatch, exit codes, prompt gating).

**Target Platform**: macOS, Windows, Linux (cross-platform parity, Constitution II).

**Project Type**: Single-project CLI (installed as the `caia` console script).

**Performance Goals**: N/A — the command is a thin wrapper around a single `uv` subprocess plus a best-effort `uv tool list` probe; no throughput/latency targets.

**Constraints**: Cross-platform parity with an explicit Windows self-removal fallback (the running command may be file-locked); secrets hygiene (never print/log/transmit the API key — only its containing file *path*); uv-specific (does not apply on the `pip install .` source fallback, where it is an idempotent no-op); meaningful exit codes (0 = idempotent "not installed as a uv tool"; non-zero = declined / uv-missing / error; 130 = interrupt).

**Scale/Scope**: Tiny. ~1 new CLI mode (+1 flag), ~2 new functions in `version.py`, ~1 dispatch function in `cli.py`, docs updates in `README.md` and `docs/index.html`, and unit tests. No new modules or directories.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against the Cisco Advisory Impact Agent Constitution v2.1.0:

- **I. Standard-Library-First & Minimal Dependencies** — PASS. No new dependency; all behavior uses the standard library (`subprocess`, `shutil`, `importlib.metadata`, `pathlib`, `os`, `sys`), exactly as the existing updater does.
- **II. Cross-Platform Parity** — PASS. Removal is delegated to `uv` identically on all platforms; `os.name`/`sys.platform` guards and `pathlib` are used for any path logic; the known Windows self-lock case is handled by catching the failure and printing the manual command (the same approach `perform_update` already documents).
- **III. CLI-First, Scriptable Interface** — PASS. New `--uninstall` mode reachable from the CLI; `--yes` enables unattended/scripted use; exit codes are meaningful (0 idempotent-success, non-zero on declined/uv-missing/error, 130 on interrupt); all error paths are actionable (state what failed and the manual command to finish).
- **IV. Conservative & Traceable Analysis (NON-NEGOTIABLE)** — N/A. This feature performs no advisory analysis and produces no impact determination; it neither reads inventory nor calls the AI. No analysis surface is touched.
- **V. Secrets Hygiene & Data Locality** — PASS. The command never reads, prints, logs, or transmits the API key; it only reports the *path* of the config file (not its contents) and preserves the file. No network access. Inventory and reports are never touched.
- **Technology & Data Constraints** — PASS. Removal is delegated to `uv`, mirroring the uv-based update; no new external endpoint is contacted (no GitHub/network call at all). Consistent with the constitution's note that uv-specific lifecycle commands do not apply on the pip-from-source path (there, `--uninstall` is an idempotent no-op).
- **Development Workflow & Quality Gates** — PASS (obligations captured as tasks). New logic gets unit tests; the `README.md` and `docs/index.html` uninstall instructions must be added alongside install/update and kept mutually consistent (Documentation gate); work proceeds on the `005-self-uninstall` branch off `main` and merges via PR (Branching Strategy). No `VERSION` semantics change beyond an ordinary release bump.

**Result (pre-Phase 0)**: PASS — no violations. Complexity Tracking is intentionally empty.

**Re-check (post-Phase 1 design)**: PASS — unchanged. The design (research.md, data-model.md, contracts/uninstall-cli.md, quickstart.md) introduces no new runtime dependency, no new module, and no network access; it only extends `cli.py`/`version.py`, reads `config.config_path()` for disclosure, and delegates removal to `uv`. Secrets hygiene holds (only the config *path* is surfaced, never its contents). No gate regressed; Complexity Tracking remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/005-self-uninstall/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── uninstall-cli.md # Phase 1 output — CLI command contract
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
cisco_advisory_impact_agent/
├── cli.py         # MODIFIED: add --uninstall + --yes args, cmd_uninstall(), dispatch (precedence)
├── version.py     # MODIFIED: add uninstall_target()/detection + perform_uninstall() (+ error type)
├── config.py      # REUSED (read-only): config_path()/config_dir() for disclosure — no change
└── ui.py          # REUSED: confirm(), ok/warn/fail/info/plain, isatty conventions — no change

tests/
├── test_version.py  # MODIFIED: detection (uv-managed vs source/pip) + perform_uninstall() cases
└── test_cli.py      # MODIFIED: --uninstall/--yes parsing, dispatch precedence, exit codes, prompt gating

README.md            # MODIFIED: add "Uninstall" section beside Install/Update
docs/index.html      # MODIFIED: mirror the uninstall instructions (Documentation gate)
```

**Structure Decision**: Single-project CLI. The feature extends the two existing modules that already own this lifecycle — `cli.py` (mode dispatch, flags) and `version.py` (uv orchestration via `find_uv()` and the subprocess/manual-fallback pattern) — rather than adding new modules. Config disclosure reuses `config.config_path()`; prompts and messaging reuse `ui`. Documentation is mirrored across `README.md` and `docs/index.html` per the Documentation quality gate.

## Complexity Tracking

> No Constitution Check violations — this section is intentionally empty.
