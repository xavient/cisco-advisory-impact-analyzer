# Phase 0 Research: Inventory & Output Folders

All open questions were resolved during `/speckit-clarify` (spec Clarifications, Session
2026-07-14). No `NEEDS CLARIFICATION` markers remain. This document records the resulting
decisions and the technical approach.

## Decision 1: Folder location

- **Decision**: Resolve `inventory/` and `output/` relative to the program directory
  (`ROOT = Path(__file__).resolve().parent` in `analyzer.py`), not the operator's shell
  working directory.
- **Rationale**: Matches the existing design — `analyzer.py` already anchors `.env` and the
  inventory to `ROOT` — and the README's "put your files in the tool's folder" mental
  model. Independent of where the operator invokes `run.py`.
- **Alternatives considered**: Current working directory (rejected: breaks when run from
  elsewhere, diverges from today's behavior); CLI-flag-only (rejected: adds friction for
  the common case, though flags are retained as overrides).

## Decision 2: What counts as an inventory file

- **Decision**: Count only `*.xlsx` files in `inventory/`. Ignore every other extension,
  hidden OS metadata (`.DS_Store`), and spreadsheet lock/temp files (`~$*.xlsx`).
- **Rationale**: The tool only reads `.xlsx` inventories; counting by that type makes the
  "exactly one" rule precise and avoids false collisions from stray unrelated files.
- **Implementation note**: `sorted(p for p in (ROOT/"inventory").glob("*.xlsx") if not
  p.name.startswith("~$"))`. `glob("*.xlsx")` already excludes dotfiles.
- **Alternatives considered**: Count all visible files (rejected: a stray `notes.txt`
  would block runs); count `.xlsx` + `.xls` (rejected: tool cannot read legacy `.xls`).

## Decision 3: Missing-folder behavior

- **Decision**: Create both folders with `mkdir(parents=True, exist_ok=True)` at startup;
  a missing folder is never an error. After ensuring `inventory/` exists, apply the
  exactly-one-`.xlsx` rule: 0 files → error, >1 → error, 1 → proceed.
- **Rationale**: The tool owns `output/`, so auto-creating it removes friction; creating an
  empty `inventory/` gives the operator a clear place to drop their file, and the
  subsequent "no inventory file found" error tells them exactly what to do.
- **Alternatives considered**: Error on any missing folder (rejected by user); create only
  `output/` (rejected by user in favor of creating both).

## Decision 4: Preserve CLI override flags

- **Decision**: Keep `--inventory PATH` and `--output-dir DIR`. When provided, they
  override the folder-based defaults; when absent, defaults become `ROOT/inventory`
  (resolved to the single file) and `ROOT/output`.
- **Rationale**: Constitution Principle III (CLI-First, Scriptable) — automation and tests
  must be able to point at temp paths without moving files into the program directory.
- **Alternatives considered**: Remove the flags (rejected: breaks scriptability and makes
  the new behavior hard to unit-test with `tmp_path`).

## Decision 5: Report naming / uniqueness

- **Decision**: Unchanged — `report.write_report` continues to name files
  `analysis_output_<YYYYMMDD_HHMMSS>.xlsx`; only the destination directory changes to
  `output/`.
- **Rationale**: The timestamp scheme already provides per-run uniqueness and the team's
  reference format is preserved.
- **Open edge (deferred to tasks/implementation)**: two runs within the same second could
  collide. Low likelihood for an interactive tool; if addressed, append a short suffix on
  collision. Noted as a hardening task, not a blocker.
