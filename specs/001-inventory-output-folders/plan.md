# Implementation Plan: Inventory & Output Folders

**Branch**: `001-inventory-output-folders` | **Date**: 2026-07-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-inventory-output-folders/spec.md`

## Summary

Move the analyzer's inputs and outputs into dedicated folders resolved beside the program:
read the firewall inventory from an `inventory/` folder (which must contain exactly one
`.xlsx` file) and write every timestamped report into an `output/` folder. Both folders
are created automatically at startup if missing; only a missing/duplicate inventory *file*
is an error. The change is confined to path resolution and startup checks in `analyzer.py`
(with a small default change threaded to `report.write_report`), preserving the existing
CLI override flags for automation.

## Technical Context

**Language/Version**: Python 3.9+

**Primary Dependencies**: Standard library (`pathlib`, `argparse`); `openpyxl` for reading
the inventory and writing reports (already a dependency). No new dependencies.

**Storage**: Local filesystem only — `inventory/` (single `.xlsx` input) and `output/`
(timestamped `.xlsx` reports), both relative to the program directory.

**Testing**: `pytest` (existing `tests/`), using `tmp_path` fixtures to exercise folder
resolution, auto-creation, and the exactly-one-file rule.

**Target Platform**: macOS, Windows, Linux (cross-platform CLI).

**Project Type**: Single-project CLI tool.

**Performance Goals**: Not applicable — folder checks are O(files-in-inventory-folder) and
negligible against network/AI time.

**Constraints**: Must run identically on all three platforms (use `pathlib`, no shelling
out); must not break existing `--inventory` / `--output-dir` automation overrides.

**Scale/Scope**: Single inventory file (~1000 rows), many accumulated report files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against Constitution v1.1.0:

- **I. Standard-Library-First & Minimal Dependencies** — PASS. Uses only `pathlib`/`argparse`
  plus the existing `openpyxl`. No new dependency introduced.
- **II. Cross-Platform Parity** — PASS. Folder resolution uses `pathlib` relative to
  `Path(__file__).resolve().parent`; `mkdir(parents=True, exist_ok=True)` behaves
  identically on all platforms. No OS-specific paths.
- **III. CLI-First, Scriptable Interface** — PASS. Default behavior uses the folders; the
  existing `--inventory` and `--output-dir` flags are retained as overrides so runs stay
  scriptable and testable. Errors remain actionable via `ui`/`die`.
- **IV. Conservative & Traceable Analysis (NON-NEGOTIABLE)** — PASS. No change to analysis
  logic or determinations; this is purely input/output plumbing. Refusing to run on an
  ambiguous inventory (0 or >1 files) *strengthens* correctness by preventing analysis of
  the wrong inventory.
- **V. Secrets Hygiene & Data Locality** — PASS. No change to secret handling; inventory and
  reports remain local. `.gitignore` already ignores `inventory.xlsx` and
  `analysis_output_*.xlsx`; it must be updated to ignore the new `inventory/` and `output/`
  folder contents (tracked as a task).
- **Branching Strategy** — PASS. Work is on branch `001-inventory-output-folders`, to be
  merged into `main` via PR.

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-inventory-output-folders/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── cli.md           # CLI + folder-resolution contract
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

The project is a flat single-project CLI; there is no `src/` tree. Relevant files:

```text
analyzer.py          # Orchestrator + CLI. Path resolution & startup folder checks live here:
                     #   - ROOT (program dir) already defined
                     #   - find_inventory(): change to scan ROOT/inventory for exactly one .xlsx
                     #   - new ensure_dirs(): create inventory/ and output/ at startup
                     #   - argparse defaults: --inventory (folder-based), --output-dir -> ROOT/output
report.py            # write_report(results, output_dir): already parameterized; default updated
inventory.py         # Unchanged (reads whatever path find_inventory returns)
run.py               # Unchanged (launcher)
tests/
└── test_folders.py  # NEW: folder resolution, auto-create, exactly-one-file rule

inventory/           # NEW runtime folder (created by the tool; holds the single .xlsx)
output/              # NEW runtime folder (created by the tool; holds timestamped reports)
```

**Structure Decision**: Keep the existing flat layout — this feature only touches path
resolution and startup logic in `analyzer.py` and a default value in `report.py`, plus a
new unit test module. No restructuring is warranted.

## Complexity Tracking

> No constitutional violations. Section intentionally empty.
