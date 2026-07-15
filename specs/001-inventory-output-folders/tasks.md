---

description: "Task list for Inventory & Output Folders"
---

# Tasks: Inventory & Output Folders

**Input**: Design documents from `/specs/001-inventory-output-folders/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: Included. The constitution (Principle IV + Development Workflow) requires tests
for parsing/selection logic, and the plan specifies `tests/test_folders.py`. Implemented
with the standard-library `unittest` framework (not pytest) to honor Principle I —
pytest is not a project dependency. Run: `python -m unittest discover -s tests`.

**Organization**: Tasks are grouped by user story. This is a flat single-project CLI; the
files touched are `analyzer.py`, `report.py`, `tests/test_folders.py`, `.gitignore`, and
`README.md` at the repository root.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

- Repository root holds the flat module layout (`analyzer.py`, `report.py`, `inventory.py`,
  `tests/`). No `src/` tree — adjust any generic guidance accordingly.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the workspace for the folder-based layout

- [X] T001 [P] Add `/inventory/` and `/output/` (folder contents) to `.gitignore` at repo root, keeping the existing `inventory.xlsx` and `analysis_output_*.xlsx` ignores
- [X] T002 [P] Create `tests/test_folders.py` with a pytest skeleton (imports, `tmp_path` fixtures) at repo root

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Path constants and startup folder auto-creation shared by all stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Define folder path constants in `analyzer.py` — `INVENTORY_DIR = ROOT / "inventory"` and `OUTPUT_DIR = ROOT / "output"` (reuse existing `ROOT = Path(__file__).resolve().parent`)
- [X] T004 Add an `ensure_dirs()` function in `analyzer.py` that calls `mkdir(parents=True, exist_ok=True)` on `INVENTORY_DIR` and `OUTPUT_DIR`, and invoke it early in `run_cli()`/`main()` before inventory selection (FR-007; never errors on missing folder)

**Checkpoint**: Both folders are created at startup on all platforms; path constants ready

---

## Phase 3: User Story 1 - Dedicated inventory folder with a single source file (Priority: P1) 🎯 MVP

**Goal**: The tool locates and uses the one `.xlsx` inventory in `inventory/`, resolved
beside the program, ignoring stray files.

**Independent Test**: Place exactly one `.xlsx` in `inventory/` (plus a `.txt`, `.DS_Store`,
`~$*.xlsx`), run the analyzer, and confirm that one file is used and analysis proceeds.

### Tests for User Story 1 ⚠️

> Write these FIRST and ensure they FAIL before implementation

- [X] T005 [P] [US1] Test in `tests/test_folders.py`: `find_inventory` selects the single `.xlsx` in `INVENTORY_DIR` while ignoring `notes.txt`, `.DS_Store`, and `~$x.xlsx` (contract C2)
- [X] T006 [P] [US1] Test in `tests/test_folders.py`: an explicit `--inventory PATH` override bypasses the folder scan and uses that file (contract C6)

### Implementation for User Story 1

- [X] T007 [US1] Rewrite `find_inventory(root, explicit=None)` in `analyzer.py` to scan `INVENTORY_DIR.glob("*.xlsx")`, excluding names starting with `~$`, and select the single qualifying file (FR-001, FR-002, FR-009, FR-010)
- [X] T008 [US1] Ensure the `--inventory` override still short-circuits to the given path (existing `explicit` branch) and that the default path is folder-based, not `ROOT/inventory.xlsx`

**Checkpoint**: With one `.xlsx` present, the tool runs end-to-end using it

---

## Phase 4: User Story 2 - Reject multiple inventory files to avoid collisions (Priority: P1)

**Goal**: The tool refuses to run when `inventory/` holds zero or more than one `.xlsx`,
with actionable, non-developer-friendly messages.

**Independent Test**: Put two `.xlsx` files in `inventory/` → expect a "more than one …
clean up" error and non-zero exit; empty `inventory/` → expect a "no inventory file found"
error.

### Tests for User Story 2 ⚠️

- [X] T009 [P] [US2] Test in `tests/test_folders.py`: two `.xlsx` files → `find_inventory` exits non-zero with a "more than one" message (contract C3)
- [X] T010 [P] [US2] Test in `tests/test_folders.py`: empty `inventory/` → `find_inventory` exits non-zero with a "no inventory file found" message (contract C4)
- [X] T011 [P] [US2] Test in `tests/test_folders.py`: missing `inventory/`+`output/` are auto-created, then the empty-inventory error fires (contract C1; exercises T004 + this story)

### Implementation for User Story 2

- [X] T012 [US2] In `find_inventory` (`analyzer.py`), when the qualifying `.xlsx` count is 0, call `die(...)` with a message telling the operator to place one `.xlsx` in `INVENTORY_DIR` (FR-004, FR-008)
- [X] T013 [US2] In `find_inventory` (`analyzer.py`), when the count is ≥2, call `die(...)` listing the files found and asking the operator to remove extras so only one remains (FR-003, FR-008)

**Checkpoint**: Ambiguous or empty inventory folders are rejected clearly; US1 still works

---

## Phase 5: User Story 3 - Output files collected in a dedicated folder (Priority: P2)

**Goal**: Every report is written into `output/` beside the program, accumulating without
overwrite.

**Independent Test**: Run the analyzer twice and confirm two distinct
`analysis_output_<timestamp>.xlsx` files exist in `output/`, neither overwritten.

### Tests for User Story 3 ⚠️

- [X] T014 [P] [US3] Test in `tests/test_folders.py`: `report.write_report` writes into the given output dir with an `analysis_output_<timestamp>.xlsx` name, and two calls produce two files with no overwrite (contract C5)

### Implementation for User Story 3

- [X] T015 [US3] Change the `--output-dir` default in `analyzer.py` argparse from `str(ROOT)` to `str(OUTPUT_DIR)` (FR-005)
- [X] T016 [P] [US3] Update `report.write_report(results, output_dir=...)` default in `report.py` from `"."` to a folder-based default consistent with `OUTPUT_DIR` (or require the caller to pass it); confirm timestamped naming/uniqueness is preserved (FR-006)

**Checkpoint**: Reports land only in `output/` and accumulate safely

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and end-to-end validation across all stories

- [X] T017 [P] Update `README.md`: describe the new `inventory/` (single `.xlsx`) and `output/` folders, replacing the "place inventory.xlsx next to the script / outputs in the folder" instructions
- [X] T018 [P] Update the module docstring/usage examples in `analyzer.py` (lines ~11–16) to reflect folder-based inputs/outputs
- [X] T019 Run `.venv/bin/python -m unittest discover -s tests` and confirm the new folder tests pass
- [X] T020 Run the quickstart.md scenarios 1–5 to validate end-to-end behavior on this machine

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Stories (Phase 3–5)**: All depend on Foundational completion
- **Polish (Phase 6)**: Depends on the desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational. Rewrites `find_inventory` selection logic.
- **US2 (P1)**: Builds on US1 — adds the 0/>1 error branches to the same `find_inventory`
  function, so it must follow US1 (same file/function).
- **US3 (P2)**: Independent of US1/US2 — touches `--output-dir` default and `report.py`
  only. Can proceed in parallel with US1/US2 once Foundational is done.

### Within Each User Story

- Tests written first and expected to FAIL before implementation
- Selection logic (US1) before its error branches (US2)

### Parallel Opportunities

- Setup: T001 and T002 in parallel [P]
- US1 tests T005, T006 in parallel [P]; US2 tests T009–T011 in parallel [P]
- US3 (T014–T016) can run in parallel with US1/US2 work (different concern; T016 [P] is a
  different file, `report.py`)
- Polish docs T017, T018 in parallel [P]

---

## Parallel Example: User Story 1

```bash
# Launch US1 tests together (write first, expect FAIL):
Task: "find_inventory selects single .xlsx, ignores stray files (C2) in tests/test_folders.py"
Task: "--inventory override bypasses folder scan (C6) in tests/test_folders.py"
```

---

## Implementation Strategy

### MVP First (US1 + US2)

Because US1 and US2 are both P1 and share `find_inventory`, the minimum shippable slice is:

1. Phase 1 Setup → Phase 2 Foundational
2. Phase 3 US1 (select the single file)
3. Phase 4 US2 (reject 0/>1)
4. **STOP and VALIDATE**: correct, safe inventory handling from the `inventory/` folder

### Incremental Delivery

1. Setup + Foundational → folders auto-created
2. US1 → single-file selection works → demo
3. US2 → collision/empty guards → demo (safe MVP)
4. US3 → outputs into `output/` → demo
5. Polish → README/docstring + quickstart validation

---

## Notes

- [P] = different files, no dependencies
- US1 and US2 modify the same `find_inventory` function; keep them sequential
- Existing `--inventory` / `--output-dir` flags are retained as overrides (Constitution III)
  and are the mechanism the tests use to avoid touching the real folders
- Commit after each task or logical group; land via PR into `main` (Constitution branching)
