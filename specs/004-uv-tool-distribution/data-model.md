# Phase 1 Data Model: uv Tool Distribution

Entities are drawn from the spec's Key Entities plus the concrete artifacts this feature
introduces. Analysis-internal structures (advisories, combos, results) are unchanged from
today (FR-022) and are summarized only where the new flow touches them.

## Installed tool

The on-PATH `cisco-advisory-impact-analyzer` command produced by `uv tool install`.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| version | str | `importlib.metadata.version("cisco-advisory-impact-analyzer")` | Single-sourced from `VERSION` at build (D2). Fallback: read `VERSION` file on `PackageNotFoundError` (source runs). |
| entry point | console script | `pyproject.toml [project.scripts]` | Maps to `cisco_advisory_impact_analyzer.cli:main` (FR-002). |

**Rules**: exactly one command is exposed (FR-002); runs from any working folder (FR-003);
version is read from installed metadata, never from a file in the working folder.

## User configuration

Persistent, per-user settings stored outside any working folder (D7, D8).

| Field | Env var | Config key | Default | Secret | Prompted by `--config` |
|-------|---------|-----------|---------|--------|------------------------|
| API key | `FUELIX_API_KEY` | `FUELIX_API_KEY` | (none) | yes | yes (FR-008) |
| Model | `FUELIX_MODEL` | `FUELIX_MODEL` | `claude-sonnet-5` | no | yes — curated menu (FR-009) |
| Base URL | `FUELIX_BASE_URL` | `FUELIX_BASE_URL` | `https://api.fuelix.ai/v1` | no | **no** — env/file-edit only (FR-010) |

**Location** (D7): `%APPDATA%\cisco-advisory-impact-analyzer\config` (Windows) /
`~/Library/Application Support/cisco-advisory-impact-analyzer/config` (macOS) /
`${XDG_CONFIG_HOME:-~/.config}/cisco-advisory-impact-analyzer/config` (Linux).

**Format**: `KEY=value` lines, human-editable, reusing the existing minimal parser.

**Permissions**: file created `0600` (owner-only) on POSIX; user-profile ACLs on Windows
(Principle V).

**Resolution order** (D8, per setting): environment variable → per-user config file →
built-in default. `--config` reads/writes only the file; env vars are never written.

**Rules**:
- API-key check gates the run: present → proceed; absent → actionable error naming `--config`,
  exit non-zero (FR-014, SC-002). Skipped only for `--dry-run`.
- `--config` re-run shows/keeps or replaces the existing key; model/base URL retain existing
  values unless changed (FR-008 scenario 2).
- Model menu default is `claude-sonnet-5`; an already-set model absent from the curated list is
  shown as the current value and is keepable (FR-009).

## Model catalog (curated, in-product)

| Field | Type | Notes |
|-------|------|-------|
| known_models | list[str] | Curated list maintained in the product; kept current with FueliX (Assumptions). Includes `claude-sonnet-5` (default). |

**Rules**: presented as a numbered selectable menu by `--config`; an out-of-list configured
model is preserved, not discarded (FR-009).

## Working folder

The user's current directory at run time (D10).

| Field | Type | Notes |
|-------|------|-------|
| cwd | path | Source of the inventory file; parent of `output/`. |
| output_dir | path | `./output/` relative to cwd; created if absent (FR-020). Overridable via `--output-dir` (FR-025). |

**Rules**: must be writable; if `output/` cannot be created, fail with a clear message rather
than losing the report (edge case). Reports never go next to the installed package (Assumptions).

## Inventory file

A user-provided `.xlsx` in the working folder conforming to the required structure.

| Field | Type | Notes |
|-------|------|-------|
| path | path | Discovered in cwd, or supplied via `--inventory` (bypasses discovery, FR-025). |
| sheet | str | Default `FW_List`; overridable via `--sheet`. |
| valid | bool | Validated by existing `inventory.load_inventory` rules (Principle IV, unchanged). |

**Discovery/selection rules** (FR-015/FR-016, US4):
1. If exactly one valid `.xlsx` is in the working folder → use it (lock/temp `~$*.xlsx` ignored).
2. Otherwise list the folder's files and prompt the user to pick one.
3. Validate the pick; on failure explain it is not a valid inventory and re-prompt; on success
   proceed to the URL step.

## Published version / release

A version made available in the project's release channel, compared against the installed
version to detect updates (D5, D6).

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| latest_tag | str \| None | GitHub `/releases/latest` (redirect fallback); tags-API fallback | Requires a published Release (D6). |
| status | enum | `updater/version` compare | `up_to_date` \| `update_available` \| `ahead` \| `latest_unknown`. |
| repo | str | `CAIA_UPDATE_REPO` or `xavient/cisco-advisory-impact-analyzer` | Override retained. |

**Rules**: run-start and `--version` checks are best-effort and time-bounded to ~2 s; any
failure → `latest_unknown` and the run proceeds silently (FR-006, FR-013, SC-005, SC-008).
Version parsing/compare rules are the existing `parse_version`/`compare_versions` (numeric,
component-wise; unknown sorts lowest).

## Report

The timestamped analysis output (unchanged content, FR-021/FR-022).

| Field | Type | Notes |
|-------|------|-------|
| path | path | `<output_dir>/analysis_output_<timestamp>.xlsx`; numeric suffix avoids overwrite. |
| columns | list | `Vendor Advisory#`, `Effected Product Description`, `Expected Assessment` (unchanged). |

**Rules**: written into the working folder's `output/`; the per-advisory summary shown today is
displayed after writing, then the tool exits (FR-020, FR-021).
