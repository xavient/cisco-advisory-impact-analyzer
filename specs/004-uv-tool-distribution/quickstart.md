# Quickstart & Validation: uv Tool Distribution

Runnable scenarios that prove the feature end-to-end. Flags, exit codes, and config schema are
defined in [contracts/cli.md](contracts/cli.md) and [contracts/config.md](contracts/config.md);
entities in [data-model.md](data-model.md). Each scenario names the spec IDs it validates.

## Prerequisites

- `uv` on PATH (`uv --version`).
- A clean shell with no prior copy of the tool: `uv tool uninstall cisco-advisory-impact-analyzer` (ignore "not installed").
- A valid firewall inventory `.xlsx` (sheet `FW_List`) and a FueliX API key for the full-run scenarios.
- Local dev alternative to installing from GitHub: `uv tool install --from . cisco-advisory-impact-analyzer` from a repo checkout.

## Scenario 1 — Install and run from any folder (US1, FR-001–FR-003, SC-001, SC-003)

```sh
uv tool install cisco-advisory-impact-analyzer \
  --from git+https://github.com/xavient/cisco-advisory-impact-analyzer
cisco-advisory-impact-analyzer --config        # set API key + model (Scenario 3)
mkdir -p ~/work-alpha && cd ~/work-alpha        # any folder, holds the inventory .xlsx
cisco-advisory-impact-analyzer                  # interactive run
```

**Expect**: a `cisco-advisory-impact-analyzer` command on PATH; the run writes
`~/work-alpha/output/analysis_output_*.xlsx` and prints the per-advisory summary. No clone, no
manual venv.

## Scenario 2 — Command surface & help (FR-005)

```sh
cisco-advisory-impact-analyzer --help
```

**Expect**: every flag from [contracts/cli.md](contracts/cli.md) listed with a description;
exit 0.

## Scenario 3 — Configure once, use everywhere (US2, FR-008–FR-011, FR-014, SC-002)

```sh
cisco-advisory-impact-analyzer --config         # enter API key; pick model (default claude-sonnet-5)
cd /tmp/some-other-folder
cisco-advisory-impact-analyzer --dry-run --url <ERP_URL> --inventory <PATH>  # key found, no re-prompt
```

**Expect**: config saved to the per-user location (see config contract) with owner-only perms;
a run from a different folder passes the credential check silently. **Negative**: with the key
unset (env unset AND config removed), a non-dry run stops with an error naming `--config` and
exits non-zero.

## Scenario 4 — Version & update flow (US3, FR-006, FR-007, SC-004)

```sh
cisco-advisory-impact-analyzer --version        # prints installed; notes if newer is published
cisco-advisory-impact-analyzer --update         # updates if newer; else "already latest"
```

Simulate "newer available" by installing an older tag first:
`uv tool install --from 'git+…@1.1.0' cisco-advisory-impact-analyzer --force`, then run
`--version`/`--update`.

**Expect**: `--version` reports newer-available and points to `--update` when a newer Release
exists; `--update` reinstalls via uv and reports success, then reports "already latest" on a
second run. Update-at-start "yes" performs the update and **exits asking you to re-run**
(FR-013).

## Scenario 5 — Guided inventory selection (US4, FR-015, FR-016)

```sh
cd "$(mktemp -d)"     # empty / no valid inventory
cisco-advisory-impact-analyzer
```

**Expect**: the tool lists the folder's files and prompts for a selection; an invalid pick is
explained and re-prompted; a valid pick proceeds to the URL step.

## Scenario 6 — Confirm before analyzing (US5, FR-017–FR-021)

**Expect**: at the URL step an invalid URL is rejected and re-prompted; a valid URL leads to a
"results saved to `output/` in this folder — Continue [y/N]?" prompt; "no" aborts cleanly; "yes"
runs and writes the report.

## Scenario 7 — Fully non-interactive run (FR-025, SC-009)

```sh
cd <folder-with-one-valid-inventory>
cisco-advisory-impact-analyzer --url <ERP_URL> --dry-run --no-update-check
```

**Expect**: completes with **zero prompts** (no update-offer, no confirmation); writes a report
(or dry-run summary). A missing/invalid input errors non-zero instead of prompting.

## Scenario 8 — Resilience & edge cases

- **Offline version check** (SC-005, SC-008): with network blocked, a normal run still completes;
  the run-start check is abandoned within ~2 s.
- **Ctrl+C** (FR-012, SC-006): pressing Ctrl+C at any prompt or mid-analysis exits 130 with no
  traceback and no partial report.
- **Unwritable folder**: in a read-only directory, the run fails with a clear message rather than
  losing the report.
- **`--update` with uv missing**: with `uv` off PATH, `--update` reports an actionable message and
  the installed version keeps working.

## Regression & cross-platform (FR-004, FR-022, SC-007)

```sh
python -m unittest discover -s tests -v
```

**Expect**: extraction/inventory/version/config tests pass. The analysis output for the same
inputs matches the pre-uv tool (FR-022). Manually confirm Scenarios 1–4 on macOS, Windows, and
Linux (SC-007) — note the Windows self-update shim caveat in [research.md](research.md) (D3).
