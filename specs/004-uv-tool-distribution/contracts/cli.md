# CLI Contract: `cisco-advisory-impact-analyzer`

The single console-script command exposed by the uv-installed tool (FR-002). One entry point
(`cisco_advisory_impact_analyzer.cli:main`) dispatches on flags. This contract defines the
observable interface: flags, dispatch precedence, prompts, exit codes.

## Installation (documented path, FR-001)

```
uv tool install cisco-advisory-impact-analyzer \
  --from git+https://github.com/xavient/cisco-advisory-impact-analyzer
```

Prerequisite: `uv` on PATH (Assumptions). Exposes `cisco-advisory-impact-analyzer` on PATH,
runnable from any folder (FR-002, FR-003).

## Flags

| Flag | Purpose | Req |
|------|---------|-----|
| `--help` | List every flag with a short description; exit 0. | FR-005 |
| `--version` | Print installed version, then best-effort (~2 s) check for a newer published version; if newer, say so and point to `--update`. | FR-006 |
| `--update` | Resolve latest published version; if newer, reinstall via uv and report success; if not, print current version and report "already latest". | FR-007 |
| `--config` | Interactively set API key (prompt) and model (curated menu, default `claude-sonnet-5`); persist to per-user config. Base URL NOT prompted. | FR-008–FR-011 |
| `--url URL` | Cisco ERP/advisory URL; supplied → skip the URL prompt. | FR-017, FR-025 |
| `--inventory PATH` | Inventory `.xlsx`; supplied → skip discovery/picker. | FR-015, FR-025 |
| `--sheet NAME` | Inventory sheet (default `FW_List`). | (carried over) |
| `--output-dir DIR` | Report destination (default `./output/` in cwd). | FR-020, FR-025 |
| `--dry-run` | Skip the AI call (pipeline test); also skips the API-key gate. | FR-025, Constitution III |
| `--keep-temp` / `--no-keep-temp` | Keep or delete downloaded CSAF temp files (default keep). | (carried over) |
| `--no-update-check` | Skip the run-start version check (also via `CAIA_NO_UPDATE_CHECK`). | (carried over) |

## Dispatch precedence

`--help` → `--version` → `--update` → `--config` → analysis run (no mode flag). The first
matching mode flag is handled and the command exits; mode flags are not combined.

## Interactive analysis run (no mode flag)

Ordered gates (each prompt is skipped when the corresponding flag/config makes it
unnecessary — FR-025):

1. **Version check** (best-effort, ~2 s, non-blocking): if newer available, prompt
   `A new version is available. Do you want to update now? [y/N]`.
   - `y` → update via uv, then **exit** with a "re-run the command" message (do not continue).
   - `n` (or check skipped/failed) → continue on current version.
   Skipped when `--no-update-check`/env set, or when running fully flag-driven.
2. **API-key gate** (FR-014): key resolved (env → config) → proceed; absent → actionable error
   naming `--config`, exit non-zero. Skipped for `--dry-run`.
3. **Inventory** (FR-015/FR-016): exactly one valid `.xlsx` in cwd → use it; else list files and
   prompt to pick, validate, re-prompt on invalid. Skipped when `--inventory` given.
4. **URL** (FR-017/FR-018): prompt, validate Cisco ERP/advisory URL, re-prompt on invalid.
   Skipped when `--url` given (still validated).
5. **Confirmation** (FR-019): show "the URL will be analyzed; results saved to `output/` in this
   folder — Continue [y/N]?"; proceed only on yes. Skipped in fully flag-driven runs.
6. **Analyze & write** (FR-020/FR-021): run existing analysis; write `output/analysis_output_*.xlsx`;
   print the per-advisory summary; exit.

## Exit codes (Constitution III)

| Code | Meaning |
|------|---------|
| 0 | Success (including "already up to date", `--help`). |
| non-zero | Actionable failure (missing API key, invalid inputs, unwritable output, etc.). |
| 130 | Ctrl+C / EOF at any prompt or mid-analysis — no traceback (FR-012, SC-006). |

`--update` failures (network/permission/uv-missing) report an actionable message and leave the
installed version working (edge cases). On Windows the shim is file-locked while running, so an
in-place self-reinstall may need the process to exit first / fall back to printing the exact uv
command (see research D3).

## Non-interactive contract (FR-025, SC-009)

An invocation supplying all inputs needed to run (`--url` and a resolvable inventory via
`--inventory` or a single valid `.xlsx` in cwd, plus a configured/`--dry-run` key) completes
end-to-end with **zero prompts** — the update-offer and the final confirmation are also
skipped. Validation failures still error out (non-zero) instead of prompting.
