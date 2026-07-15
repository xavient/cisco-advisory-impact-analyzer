# Phase 1 Data Model: Inventory & Output Folders

This feature introduces no new business/domain entities — it changes where existing inputs
and outputs live. The "entities" here are filesystem locations and the rules that govern
them. The inventory *row* schema (name/model/family/version) is unchanged and owned by
`inventory.py`.

## Entities

### Inventory folder

- **Represents**: The single dedicated location holding the one inventory spreadsheet.
- **Location**: `<program_dir>/inventory` (program dir = `Path(__file__).resolve().parent`).
- **Lifecycle**: Created automatically at startup if absent (`mkdir(parents=True,
  exist_ok=True)`).
- **Validation rules**:
  - MUST contain exactly one `*.xlsx` file, excluding `~$*.xlsx` lock/temp files.
  - Files with any non-`.xlsx` extension and hidden OS metadata are ignored.
  - 0 qualifying files → error "no inventory file found" (FR-004).
  - >1 qualifying files → error "more than one inventory file; clean up" (FR-003).

### Inventory file

- **Represents**: The sole `.xlsx` spreadsheet describing the operator's firewalls.
- **Relationship**: The one qualifying entry in the Inventory folder; its path is passed to
  `inventory.load_inventory()` unchanged.
- **Validation rules**: Existing column/sheet validation in `inventory.py` still applies
  after selection (unreadable/invalid file → existing actionable error).

### Output folder

- **Represents**: The dedicated location collecting all generated reports.
- **Location**: `<program_dir>/output`.
- **Lifecycle**: Created automatically at startup if absent.
- **Validation rules**: None restricting contents — may hold zero-to-many report files.

### Report file

- **Represents**: One timestamped Excel result produced by a run.
- **Relationship**: Written into the Output folder; many may coexist.
- **Naming/uniqueness**: `analysis_output_<YYYYMMDD_HHMMSS>.xlsx` (unchanged). Uniqueness
  guaranteed across runs by the timestamp; new reports never overwrite existing ones.

## State / flow (startup sequence)

```text
start
 └─ ensure <program_dir>/inventory exists   (create if missing)
 └─ ensure <program_dir>/output   exists     (create if missing)
 └─ select inventory file from inventory/    (count *.xlsx, minus ~$*)
       ├─ 0  → die("no inventory file found …")
       ├─ >1 → die("more than one inventory file … clean up")
       └─ 1  → proceed with analysis
 └─ … run analysis …
 └─ write report into output/                 (timestamped name)
```

## Mapping to functional requirements

| Requirement | Entity / rule |
|-------------|---------------|
| FR-001, FR-010 | Inventory folder — location beside program |
| FR-002, FR-009 | Inventory folder — exactly one `.xlsx`, others ignored |
| FR-003 | Inventory folder — >1 file error |
| FR-004 | Inventory folder — 0 files error |
| FR-005, FR-006 | Output folder + Report file — dedicated dir, unique timestamped names |
| FR-007 | Both folders — auto-create at startup, no missing-folder error |
| FR-008 | Actionable error text for the two inventory-file errors |
