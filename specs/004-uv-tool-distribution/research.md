# Phase 0 Research: uv Tool Distribution

Resolves the unknowns from the plan's Technical Context. Each item: Decision / Rationale /
Alternatives considered.

## D1. Packaging layout & build backend

**Decision**: Adopt a flat package directory `cisco_advisory_impact_analyzer/` at the repo
root (moving today's top-level modules into it) with a `pyproject.toml` using the
`setuptools` build backend and a `[project.scripts]` entry point
`cisco-advisory-impact-analyzer = "cisco_advisory_impact_analyzer.cli:main"`.

**Rationale**: `uv tool install` needs a build-backend-buildable project exposing a console
script; setuptools is ubiquitous, needs no runtime footprint, and auto-discovers a
single-package flat layout. A package dir (vs. shipping `analyzer.py`, `cisco.py`, `ui.py`…
as top-level modules) avoids polluting the global import namespace with generic names and
prevents import shadowing during tests. Keeping it at the repo root (not `src/`) lets the
stdlib `unittest` suite keep using a simple `sys.path` insert with no editable install.

**Alternatives considered**: (a) `hatchling` backend — fine, but reading the version from a
bare `VERSION` file needs a plugin/regex, whereas setuptools supports it natively; (b) `src/`
layout — best-practice for import isolation but adds an editable-install step to the current
test workflow for marginal benefit here; (c) flat `py-modules` with no package — rejected for
namespace pollution.

## D2. Single-sourcing the product version

**Decision**: Keep the committed `VERSION` file as the single source of truth. In
`pyproject.toml`: `[project] dynamic = ["version"]` and
`[tool.setuptools.dynamic] version = { file = "VERSION" }`. At runtime read the version with
`importlib.metadata.version("cisco-advisory-impact-analyzer")`.

**Rationale**: Preserves the constitution's "Versioning & releases" gate (VERSION is the
source of truth) and the release workflow's tag==VERSION check unchanged. setuptools reads the
raw file contents as the version and strips leading/trailing whitespace, so a trailing newline
in `VERSION` is fine and no stamping step is needed. `importlib.metadata` is stdlib since
Python 3.8, so it satisfies the 3.9+ target and Principle I, and it works from any working
folder because it reads installed distribution metadata rather than a file next to the script
(there is no such file once installed by uv).

**Confirmed constraints** (verification agent, setuptools docs): requires
`setuptools >= 61.0.0` declared in `[build-system] requires`; `version` must NOT also be set
statically in `[project]`. `importlib.metadata.version("cisco-advisory-impact-analyzer")` uses
the *distribution* name (hyphens), not the import name, and raises `PackageNotFoundError` when
run from an uninstalled source tree — so `version.py` MUST fall back to reading the committed
`VERSION` file on `PackageNotFoundError`, keeping `--version` working during development.

**Alternatives considered**: Hard-coding the version in `pyproject.toml` (breaks the single
source of truth and the CI gate); a runtime `VERSION` file shipped as package data (fragile —
the file is not reliably next to the installed entry point).

## D3. `--update` via uv orchestration

**Decision**: `--update` (and the "yes" branch of the run-start prompt) resolves the latest
published release tag, then reinstalls the tool pinned to that tag by spawning uv (exact,
verified form):

```
uv tool install cisco-advisory-impact-analyzer \
  --from 'git+https://github.com/xavient/cisco-advisory-impact-analyzer@<tag>' --force
```

`--force` is required (the tool is already installed) and re-fetches the git ref; add
`--reinstall` if the git cache must be re-resolved. `uv tool upgrade <name>` alone is NOT
dependable for a git source (its outdated-check compares against PyPI by name). After a
successful reinstall the run-start "yes" path exits and instructs the user to re-run (per the
2026-07-18 clarification); explicit `--update` reports success and exits. If the latest tag
cannot be resolved, behave per status (already-latest → report; unknown → actionable error).

**Rationale**: The tool must not overlay files in place (Assumptions); delegating to uv is the
supported upgrade mechanism and keeps the installed environment consistent. Pinning to the
resolved release tag (rather than reinstalling default-branch HEAD) makes the result
deterministic and matches "a newer *published version* is available." The running process is
the old code, so exiting after the reinstall (rather than continuing) avoids executing a
half-updated tool.

**Windows caveat (verification agent)**: on POSIX, uv can replace the launcher/venv files while
the tool runs (the running process keeps its open inode). On **Windows the running `.exe` shim
is file-locked** and uv cannot overwrite it while our process is alive. Mitigation: run the uv
reinstall such that our process exits before uv rewrites the shim — spawn uv detached and exit,
or if the in-place reinstall reports the shim is in use, fall back to printing the exact
`uv tool install …@<tag> --force` command for the user to run from a fresh shell. The
"update → exit → re-run" behavior chosen for the run-start prompt aligns naturally with this;
`--update` carries the same Windows handling so cross-platform parity (Principle II) holds.

**Alternatives considered**: `uv tool upgrade cisco-advisory-impact-analyzer` (unreliable for
git sources, see above); reinstalling default-branch HEAD — could pull an unreleased VERSION.

## D4. Locating `uv` at runtime

**Decision**: Resolve the `uv` executable with `shutil.which("uv")`, then fall back to the
well-known install locations (`~/.local/bin/uv`, `%USERPROFILE%\.local\bin\uv.exe`, or
`$UV_INSTALL_DIR`) before giving up. If still not found, fail `--update` with an actionable
message ("uv was not found on PATH; reinstall/update with `uv tool install … --from git+…`")
and leave the installed version working (edge case in the spec). Never assume a bare `uv`
name is invokable and never hard-code a single path.

**Rationale**: The tool was installed by uv, so uv is normally on PATH, but the verification
agent confirmed `uv` is NOT guaranteed on the child process's PATH; the fallback locations are
uv's documented default install dirs. `shutil.which` + fallbacks are stdlib and cross-platform.
This satisfies the "`--update` cannot complete (uv unavailable at runtime)" edge case.

**Alternatives considered**: Bundling/vendoring uv (out of scope; uv is a documented
prerequisite); guessing install paths (brittle, violates cross-platform parity).

## D5. Version discovery (latest published release)

**Decision**: Reuse the existing, constitution-approved discovery logic from `updater.py`
(`resolve_latest` → GitHub `/releases/latest` API with the web-redirect fallback,
`parse_version`/`compare_versions`, `check_update` status mapping), relocated into
`version.py`. Bound the run-start and `--version` checks to ~2 s (`timeout=2`) and treat any
failure as "skip silently / proceed on current version." Keep the `CAIA_UPDATE_REPO` override.

**Rationale**: This half of the updater is already tested (`test_updater.py`) and sends no
inventory or secrets (FR-023). Only the download/verify/backup/apply/rollback half is dropped
(now uv's job). The ~2 s bound satisfies FR-006/FR-013/SC-008.

**Alternatives considered**: Switching to the git tags API — loses the clean "latest" semantic
that `/releases/latest` provides and would need its own sorting.

## D6. Keeping `/releases/latest` resolvable after dropping zip assets

**Decision**: The release workflow keeps creating a GitHub **Release** for each tag (retaining
the tag==VERSION gate) but drops the zip-build + SHA-256 + asset-upload steps. No release asset
is needed because uv builds from the git source. As defense-in-depth, `version.py` also carries
a fallback to the git **tags** API (`/repos/{owner}/{repo}/tags`) if `/releases/latest` 404s.

**Rationale**: The verification agent confirmed `/releases/latest` (both REST and the web
redirect) requires a *published Release* object — a bare git tag returns 404. So version
discovery (D5) keeps working only if a Release exists; producing a Release without assets is
enough, and it matches how 1.0.0–1.2.0 were already published. The tags-API fallback keeps
discovery robust even if a future tag is pushed without a Release.

## D7. Per-user configuration storage

**Decision**: Store config in an OS-appropriate per-user directory resolved with stdlib only
(no `platformdirs` dependency):
- Windows: `%APPDATA%\cisco-advisory-impact-analyzer\config`
- macOS: `~/Library/Application Support/cisco-advisory-impact-analyzer/config`
- Linux/other: `${XDG_CONFIG_HOME:-~/.config}/cisco-advisory-impact-analyzer/config`

Format: simple `KEY=value` lines using the existing `FUELIX_*` names (`FUELIX_API_KEY`,
`FUELIX_MODEL`, `FUELIX_BASE_URL`), so the file is human-editable (needed for the base-URL
"edit the file directly" path) and parseable by the existing minimal parser. On POSIX, create
the file with `0600` (owner-only) permissions; on Windows rely on per-user profile ACLs.

**Rationale**: Avoids a new runtime dependency (Principle I); reuses the env-var vocabulary the
app already honors so precedence is coherent; `KEY=value` is the least-surprising editable
format and dodges the TOML-write problem (stdlib `tomllib` is read-only and absent on 3.9/3.10).

**Alternatives considered**: `platformdirs` (new dependency, rejected); JSON (editable but less
conventional for a `.env`-style secret file and worse for hand-editing); TOML (no stdlib writer,
unavailable on 3.9/3.10).

## D8. Configuration precedence

**Decision**: For each setting, precedence is **environment variable → per-user config file →
built-in default**. `--config` reads/writes the per-user file only; env vars are never written.
The analyzer resolves API key, model, and base URL through this order.

**Rationale**: Matches the spec Assumptions ("environment variables take precedence, followed by
the stored per-user configuration") and the current app's env-first behavior, keeping automation
overrides working (FR-025) without surprising interactive users.

**Alternatives considered**: File-over-env (breaks automation and the stated assumption).

## D9. Model selection menu (FR-009)

**Decision**: Maintain a curated in-product list of known-good FueliX models with
`claude-sonnet-5` (the current `fuelix.DEFAULT_MODEL`) as the default selection. `--config`
presents a numbered menu; if an already-configured model is absent from the list, show it as
the current value and allow keeping it. Base URL is not prompted (FR-010).

**Rationale**: Directly encodes FR-009/FR-010 and the "model list curated in-product"
assumption. A numbered menu is a small stdlib UI addition to `ui.py`.

**Alternatives considered**: Free-text model entry (rejected — spec requires a curated
selectable list); fetching the list from FueliX at runtime (out of scope; list is maintained
in-product).

## D10. CWD-relative inventory discovery, picker, and output

**Decision**: The run flow discovers the inventory in the **current working folder** (not a
fixed `inventory/` subfolder). If exactly one valid `.xlsx` is present, use it; otherwise list
the folder's files and let the user pick, validating with the existing inventory rules and
re-prompting on an invalid pick (FR-015/FR-016). `--inventory PATH` bypasses discovery
(FR-025). Reports are written to `./output/` in the current working folder, created if absent
(FR-020). Ctrl+C at any prompt exits 130 without a traceback.

**Rationale**: Matches the "results appear where I ran the command" mental model (Assumptions)
and the guided-selection story (US4). Reuses `inventory.load_inventory` validation unchanged
(Principle IV). This changes `analyzer.find_inventory`/directory constants and the
`test_folders.py` expectations.

**Alternatives considered**: Keeping the fixed `inventory/` subfolder (contradicts the
folder-independent run and US4 picker).

## D11. Single CLI entry point & flag dispatch

**Decision**: `cli.main()` parses top-level flags and dispatches: `--help` (argparse-generated
flag listing, FR-005), `--version` (FR-006), `--update` (FR-007), `--config` (FR-008–FR-011),
and otherwise the interactive/flag-driven analysis run (FR-012–FR-021, FR-025). Ctrl+C handling
wraps `main()` to exit 130 with no traceback.

**Rationale**: Consolidates today's `run.py` + `analyzer.py` + `update.py` CLIs into one
command, satisfying FR-002 (single executable) and Principle III. Analysis flags
(`--url`, `--inventory`, `--sheet`, `--output-dir`, `--dry-run`, `--keep-temp/--no-keep-temp`,
`--no-update-check`) carry over.

**Alternatives considered**: Subcommands (`config`, `update`) — the spec's UX is flag-based
(`--config`, `--update`), so flags match the documented interface.

## D12. What is retired (FR-024)

**Decision**: Remove `install.py`, `run.py`, the thin `update.py` CLI, `MANIFEST`, the
download/verify/backup/apply/rollback half of `updater.py`, `tools/release.py`'s zip
packaging assumptions, `tools/install-test/` (clone-install harness), and `tools/updater-sim.py`.
Retarget/replace their tests. Update `README.md`, `docs/index.html`, `CONTRIBUTING.md`, and the
constitution to describe only the uv flow.

**Rationale**: FR-024 requires uv to fully replace the previous mechanism with a single
documented path; leaving dead entry points would create conflicting install stories and keep
the docs/constitution inaccurate.

**Alternatives considered**: Deprecating gradually (rejected — the spec states a clean break;
old-flow users reinstall via uv).

## Constitution amendment required

FR-024 and gate II require amending the constitution within this feature: Principle II drops
the `install.py`/`run.py`/`.venv` mandate (while keeping the cross-platform-parity intent), and
the Technology & Data Constraints + self-updater paragraph are rewritten for uv-based updates.
Per Governance this is a backward-incompatible redefinition of a principle → a MAJOR bump of the
constitution's own version, with an updated Sync Impact Report. This is tracked as feature work,
not an unjustified violation.
