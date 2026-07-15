# CLI & Folder-Resolution Contract

The tool's external interface is its command line (`python run.py` → `analyzer.py`) plus
the filesystem folders it reads and writes. This contract defines the observable behavior
after this feature; it is the acceptance surface for tests.

## Folder resolution

- `PROGRAM_DIR = Path(__file__).resolve().parent` (of `analyzer.py`).
- `INVENTORY_DIR = PROGRAM_DIR / "inventory"` unless overridden.
- `OUTPUT_DIR = PROGRAM_DIR / "output"` unless overridden.
- Resolution is independent of the operator's current working directory.

## CLI flags (contract)

| Flag | Default | Behavior |
|------|---------|----------|
| `--inventory PATH` | (auto: single `.xlsx` in `INVENTORY_DIR`) | If given, use this exact file and skip folder scan/exactly-one check. |
| `--output-dir DIR` | `PROGRAM_DIR/output` | Directory reports are written to. Created if missing. |
| `--sheet NAME` | `FW_List` | Unchanged. |
| `--url`, `--dry-run`, `--keep-temp/--no-keep-temp` | unchanged | Unchanged. |

> The overrides exist for automation/testing (Constitution III). Default (no overrides) is
> the folder-based behavior specified by this feature.

## Startup behavior (contract)

1. Ensure `INVENTORY_DIR` exists — create it (and parents) if missing. Never an error.
2. Ensure `OUTPUT_DIR` exists — create it (and parents) if missing. Never an error.
3. Select the inventory file (unless `--inventory` given):
   - Qualifying files = `INVENTORY_DIR.glob("*.xlsx")` minus names starting with `~$`.
   - Exactly 1 → use it.
   - 0 → exit non-zero with a message telling the operator to place one `.xlsx` inventory
     file in `INVENTORY_DIR`.
   - ≥2 → exit non-zero with a message listing that multiple were found and asking the
     operator to remove extras so only one remains.

## Exit codes

| Condition | Exit |
|-----------|------|
| Success | 0 |
| No inventory file in `INVENTORY_DIR` | non-zero (via existing `die`) |
| More than one inventory file | non-zero (via existing `die`) |
| User interrupt (Ctrl+C) | 130 (unchanged) |

## Observable outputs

- Reports appear only in `OUTPUT_DIR`, named `analysis_output_<YYYYMMDD_HHMMSS>.xlsx`.
- Repeated runs add new files without deleting or overwriting existing ones.

## Contract test scenarios

| # | Given | When | Then |
|---|-------|------|------|
| C1 | No `inventory/` or `output/` folder | run startup | both folders created; then "no inventory file" error |
| C2 | `inventory/` has one `.xlsx` (+ a `.DS_Store`, a `~$x.xlsx`, a `notes.txt`) | run | that one `.xlsx` selected; run proceeds |
| C3 | `inventory/` has two `.xlsx` files | run | non-zero exit, "more than one" message |
| C4 | `inventory/` empty | run | non-zero exit, "no inventory file" message |
| C5 | valid inventory, run twice | run x2 | two distinct timestamped files in `output/`, none overwritten |
| C6 | `--inventory /tmp/x.xlsx` given | run | that file used; `inventory/` scan skipped |
