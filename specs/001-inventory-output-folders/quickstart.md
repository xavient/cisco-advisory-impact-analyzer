# Quickstart: Validate Inventory & Output Folders

Runnable scenarios proving the feature works end-to-end. Assumes the tool is installed
(`python install.py`) with a working `.venv` and `.env`. Run all commands from the program
directory. See [contracts/cli.md](./contracts/cli.md) for the full behavior contract and
[data-model.md](./data-model.md) for the folder rules.

## Prerequisites

- Installed environment (`.venv` present) and a valid FueliX key in `.env`.
- A valid inventory spreadsheet available (with sheet `FW_List`).

## Scenario 1 — Folders auto-created, empty inventory errors

```bash
rm -rf inventory output          # start clean
python run.py --dry-run          # or answer the ERP prompt; --dry-run skips the AI call
```

Expected: `inventory/` and `output/` are created, then the tool exits non-zero with a
message telling you to place one `.xlsx` inventory file in `inventory/`.

## Scenario 2 — Single inventory file, clean run

```bash
cp /path/to/your_inventory.xlsx inventory/
python run.py --url "https://sec.cloudapps.cisco.com/security/center/viewErp.x?alertId=ERP-XXXXX"
```

Expected: the tool selects the one `.xlsx`, runs the analysis, and writes exactly one
`analysis_output_<timestamp>.xlsx` into `output/`.

## Scenario 3 — Stray files are ignored

```bash
touch inventory/notes.txt inventory/.DS_Store "inventory/~\$your_inventory.xlsx"
python run.py --dry-run
```

Expected: the run still proceeds using the single real `.xlsx` — the `.txt`, `.DS_Store`,
and `~$` lock file are not counted.

## Scenario 4 — Multiple inventory files are rejected

```bash
cp inventory/your_inventory.xlsx inventory/second.xlsx
python run.py --dry-run
```

Expected: non-zero exit with a message that more than one inventory file was found, asking
you to remove the extras so only one remains. Clean up:

```bash
rm inventory/second.xlsx
```

## Scenario 5 — Reports accumulate without overwrite

```bash
python run.py --url "…ERP-XXXXX…"
python run.py --url "…ERP-XXXXX…"
ls output/
```

Expected: two distinct `analysis_output_<timestamp>.xlsx` files; neither overwrites the
other.

## Automated checks

```bash
.venv/bin/python -m unittest discover -s tests
```

Expected: the new folder-behavior tests (auto-create, exactly-one-file selection, stray-file
filtering, multi-file error, no-overwrite output) pass. The tests use the standard-library
`unittest` framework (no extra dependency, per Constitution Principle I) and work entirely
in temporary directories, so they never touch the real `inventory/`/`output/` folders.
