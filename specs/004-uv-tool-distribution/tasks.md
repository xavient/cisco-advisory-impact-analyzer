---

description: "Task list for uv Tool Distribution (004)"
---

# Tasks: uv Tool Distribution

**Input**: Design documents from `/specs/004-uv-tool-distribution/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: Test tasks ARE included — not as full TDD, but because the constitution's quality gate
requires tests for extraction/parsing/inventory-matching changes and that the existing suite keep
passing. New tests cover config resolution, version logic, and the CWD-relative run flow.

**Organization**: Tasks are grouped by user story. This feature repackages an existing codebase, so
Phase 1–2 do the package move + shared modules, each user story adds one slice of behavior, and the
final phase retires the old distribution and amends the constitution (FR-024).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story the task serves (US1–US5); omitted for Setup/Foundational/Polish
- Paths are repo-relative. The new package is `cisco_advisory_impact_analyzer/` at the repo root.

---

## Phase 1: Setup (Packaging skeleton)

**Purpose**: Turn the flat script layout into an installable uv tool package.

- [x] T001 Create `pyproject.toml` at repo root: `[build-system]` `requires = ["setuptools>=61.0.0"]` / `build-backend = "setuptools.build_meta"`; `[project]` name `cisco-advisory-impact-analyzer`, `requires-python = ">=3.9"`, `dependencies = ["openpyxl>=3.1", "python-dotenv>=1.0"]`, `dynamic = ["version"]`; `[project.scripts] cisco-advisory-impact-analyzer = "cisco_advisory_impact_analyzer.cli:main"`; `[tool.setuptools.dynamic] version = {file = "VERSION"}`; package discovery for `cisco_advisory_impact_analyzer` (research D1/D2).
- [x] T002 Create the package: add `cisco_advisory_impact_analyzer/__init__.py`, then `git mv` `cisco.py fuelix.py inventory.py report.py ui.py` into `cisco_advisory_impact_analyzer/` unchanged, fixing intra-package imports (e.g. `import cisco` → `from cisco_advisory_impact_analyzer import cisco`).

**Checkpoint**: `pyproject.toml` + package dir exist; runtime modules live inside the package.

---

## Phase 2: Foundational (Blocking prerequisites)

**Purpose**: Shared pieces every user story plugs into (single CLI entry, config resolution, version
helpers, menu helper). **No user story work starts until this phase is complete.**

- [x] T003 Create `cisco_advisory_impact_analyzer/cli.py`: single argparse entry `main()` with `--help`/`--version`/`--update`/`--config` and analysis flags (`--url`, `--inventory`, `--sheet`, `--output-dir`, `--dry-run`, `--keep-temp`/`--no-keep-temp`, `--no-update-check`); dispatch precedence per [contracts/cli.md](contracts/cli.md); `run_cli()` wrapper catching `KeyboardInterrupt`/EOF → exit 130 with no traceback (FR-005, FR-012). Mode handlers call into modules added by later phases (stubs for now).
- [x] T004 [P] Create `cisco_advisory_impact_analyzer/config.py`: per-user config dir resolution (Windows `%APPDATA%`, macOS `~/Library/Application Support`, else `${XDG_CONFIG_HOME:-~/.config}`), `KEY=value` file load/parse, `resolve(key)` with precedence env → file → default, defaults for `FUELIX_MODEL`/`FUELIX_BASE_URL`, and an atomic write helper that sets `0600` perms on POSIX (research D7/D8, [contracts/config.md](contracts/config.md)). No interactive UI yet.
- [x] T005 [P] Create `cisco_advisory_impact_analyzer/version.py` with the pure version helpers relocated from `updater.py`: `parse_version`, `compare_versions`, and `read_installed_version()` using `importlib.metadata.version("cisco-advisory-impact-analyzer")` with a fallback to reading the `VERSION` file on `PackageNotFoundError` (research D2/D5).
- [x] T006 [P] Add a reusable numbered-menu helper `select(label, options, default)` to `cisco_advisory_impact_analyzer/ui.py` (re-prompts on invalid input) — shared by the `--config` model menu (US2) and the inventory picker (US4).
- [x] T007 [P] Retarget `tests/test_extraction.py` imports to `cisco_advisory_impact_analyzer.cisco` so `python -m unittest discover -s tests` collects against the package.

**Checkpoint**: The command dispatches; config and version resolution work; menu helper available.

---

## Phase 3: User Story 1 - Install and run an analysis from any folder (Priority: P1) 🎯 MVP

**Goal**: The uv-installed command runs the existing analysis from any working folder and writes the
report to `./output/` in that folder.

**Independent Test**: On a clean machine with `uv`, `uv tool install --from git+<repo>`, set
`FUELIX_API_KEY` (env is enough here; the `--config` UI is US2), then from a fresh folder with one
valid inventory run `cisco-advisory-impact-analyzer --url <ERP_URL>` and confirm a report lands in
`./output/` (FR-001–FR-004, FR-020, FR-022, SC-001, SC-003).

- [x] T008 [US1] `git mv analyzer.py` into `cisco_advisory_impact_analyzer/` and update its imports to package-relative (`cisco`, `fuelix`, `inventory as inv`, `ui`, `report`).
- [x] T009 [US1] In `cisco_advisory_impact_analyzer/analyzer.py`, make I/O working-folder-relative: discover the inventory in `Path.cwd()` (drop the fixed `inventory/` subfolder), default `output_dir` to `Path.cwd()/"output"`, create `output/` if missing, and fail with a clear message if it cannot be created (FR-015 baseline, FR-020, edge case).
- [x] T010 [US1] Wire the run path in `cli.py`: resolve `api_key`/`model`/`base_url` via `config.resolve(...)`, enforce the API-key gate (skip for `--dry-run`) with an actionable error naming `--config` and a non-zero exit (FR-014), then invoke `analyzer` with resolved inputs. Core happy path accepts `--url` plus a single valid CWD inventory or `--inventory` (interactive URL/confirm/picker come in US4/US5).
- [x] T011 [US1] Confirm Ctrl+C anywhere in the run exits 130 with no traceback via `cli.run_cli()` and remove the old per-module Ctrl+C handling now centralized there (FR-012, SC-006).
- [x] T012 [P] [US1] Update `tests/test_folders.py` for CWD-relative behavior: run under a temp cwd, assert the inventory is found in cwd and the report is written to `<cwd>/output/`; keep the single/multiple/empty-inventory cases.
- [x] T013 [US1] Smoke-validate: `uv tool install --from . cisco-advisory-impact-analyzer --force`, then in a temp folder with one inventory run `cisco-advisory-impact-analyzer --dry-run --url <ERP_URL> --no-update-check` and confirm the report path is `<cwd>/output/…`.

**Checkpoint**: MVP — install once, run from any folder, report in `./output/`.

---

## Phase 4: User Story 2 - Configure credentials once, use everywhere (Priority: P1)

**Goal**: `--config` stores the FueliX API key + model in a per-user location so every future run in
any folder finds them.

**Independent Test**: Run `--config`, set a key; from a different folder run the tool and confirm it
passes the credential check without re-prompting (FR-008–FR-011, FR-014, SC-002).

- [x] T014 [P] [US2] Add the curated known-good model list (including default `claude-sonnet-5`) as a constant in `cisco_advisory_impact_analyzer/fuelix.py` (co-located with `DEFAULT_MODEL`).
- [x] T015 [US2] Implement `--config` in `config.py` + `cli.py`: prompt for the API key with `ui.ask_secret` (empty input keeps the existing value), present the model menu via `ui.select` (default `claude-sonnet-5`; a configured model absent from the list is shown as current and keepable), do NOT prompt for base URL (FR-010), write the file with `0600` perms, and report where it was saved (FR-008, FR-009, FR-011).
- [x] T016 [US2] Verify the run-flow API-key gate reads through `config.resolve` precedence (env → file → default) and its error message names `cisco-advisory-impact-analyzer --config` (FR-014); confirm env vars override the stored file.
- [x] T017 [P] [US2] Create `tests/test_config.py`: per-OS dir resolution (monkeypatch env/`os.name`/`sys.platform`), precedence order, `0600` perms on POSIX, keep-vs-replace key, and model value retention.

**Checkpoint**: Credentials persist per-user; runs from any folder authenticate silently.

---

## Phase 5: User Story 3 - Discover, and stay on, the latest version (Priority: P2)

**Goal**: `--version` reports installed + newer-available; `--update` upgrades via uv; a normal run
offers to update first if a newer version exists.

**Independent Test**: With a newer version published, `--version` reports it and points to `--update`;
`--update` upgrades and reports success; a second `--update` reports already-latest (FR-006, FR-007,
SC-004, SC-005, SC-008).

- [x] T018 [US3] Relocate GitHub discovery into `version.py`: `resolve_latest` (GitHub `/releases/latest` API with the web-redirect fallback, plus a `/repos/{repo}/tags` fallback — research D5/D6), `check_update` status mapping, and `passive_check(timeout=2)`; keep the `CAIA_UPDATE_REPO` override; transmit no inventory/secrets (FR-023).
- [x] T019 [US3] Implement `--version` in `cli.py` (FR-006): print the installed version, then a best-effort ~2 s check; if newer, tell the user and point to `--update`; on timeout/failure still print the installed version without erroring (SC-008).
- [x] T020 [US3] Implement `--update` in `cli.py` + a helper in `version.py` (FR-007): resolve the latest tag; locate uv via `shutil.which("uv")` with fallbacks (research D4); run `uv tool install cisco-advisory-impact-analyzer --from 'git+<repo>@<tag>' --force`; handle already-latest / latest-unknown / failure with actionable messages leaving the install working; handle the Windows shim file-lock (exit-then-reinstall, or fall back to printing the exact uv command — research D3).
- [x] T021 [US3] Implement the run-start update nudge in `cli.py` (FR-013): `passive_check` (~2 s, non-blocking); if newer, prompt `Do you want to update now? [y/N]` — **yes** performs the update then exits with a re-run message (do not continue on old code), **no** continues; skip when `--no-update-check`/`CAIA_NO_UPDATE_CHECK` is set; never block or fail the run (SC-005, SC-008).
- [x] T022 [P] [US3] Create `tests/test_version.py` from the pure-logic tests in `tests/test_updater.py` (parse/compare/installed-version/status mapping), retargeted to `version.py`; drop the now-obsolete manifest/preserve-list tests.

**Checkpoint**: Version reporting and uv-based updates work; run-start nudge is best-effort.

---

## Phase 6: User Story 4 - Guided inventory selection (Priority: P2)

**Goal**: When the working folder has no single valid inventory, the tool lists files, lets the user
pick, validates, and re-prompts on an invalid pick.

**Independent Test**: From a folder with no valid inventory, confirm the tool lists candidates and lets
you select; an invalid pick is explained and re-prompted; a valid pick proceeds (FR-015, FR-016).

- [x] T023 [US4] In `analyzer.py`, add the guided picker: if there is not exactly one valid `.xlsx` in the working folder, list the folder's files and prompt with `ui.select`, validate the choice with `inventory.load_inventory`, and re-prompt on an invalid inventory; `--inventory PATH` bypasses discovery entirely (FR-015, FR-016, FR-025).
- [x] T024 [P] [US4] Add tests (extend `tests/test_folders.py`) for the picker: no valid inventory → lists + selects; invalid pick → re-prompt; valid pick → proceeds.

**Checkpoint**: Users are guided to a valid inventory instead of hitting a hard error.

---

## Phase 7: User Story 5 - Confirm before analyzing (Priority: P3)

**Goal**: Prompt for the Cisco URL, validate it, then require an explicit confirmation that states the
URL will be analyzed and results saved to `output/` in the current folder.

**Independent Test**: At the URL step an invalid URL is re-prompted; a valid URL leads to a
"results saved to output/ … Continue [y/N]?" prompt whose "no" aborts cleanly (FR-017–FR-019, FR-021).

- [x] T025 [US5] Wire the URL step in `analyzer.py`/`cli.py` (FR-017/FR-018): prompt via `prompt_for_url` when `--url` is absent; validate the entered/passed URL and re-prompt on invalid; a `--url`-supplied value is still validated.
- [x] T026 [US5] Add the pre-analysis confirmation (FR-019): show "the URL will be analyzed; results will be saved to `output/` in this folder — Continue [y/N]?"; proceed only on yes; skip the confirmation in fully flag-driven runs (FR-025); after writing, show the per-advisory summary and exit (FR-021).

**Checkpoint**: The interactive flow is complete with a clear guardrail before network/AI calls.

---

## Phase 8: Polish & Cross-Cutting Concerns (FR-022–FR-025, FR-024 retirement, docs, constitution)

**Purpose**: Retire the old distribution, update all docs/CI, amend the constitution, and validate.

- [x] T027 Verify the non-interactive contract (FR-025, SC-009): a fully flag-driven invocation (`--url` + resolvable inventory + configured/`--dry-run` key) runs with **zero** prompts — no update-offer, no confirmation — and validation failures error non-zero instead of prompting; capture as a scripted check or test.
- [x] T028 [P] Retire the old distribution (FR-024): `git rm` `install.py`, `run.py`, `update.py`, `updater.py`, `MANIFEST`, `tools/install-test/`, `tools/updater-sim.py`; remove `tools/release.py`'s zip/packaging assumptions (keep only the tag-from-VERSION helper if still useful, else remove). Confirm nothing else imports them.
- [x] T029 [P] Update `.github/workflows/ci.yml` to install and test the package via uv (e.g. `uv run --with . python -m unittest discover -s tests` or `pip install .` then run), keeping the Python 3.9 + 3.12 matrix.
- [x] T030 [P] Update `.github/workflows/release.yml`: keep the `tag == VERSION` gate and keep creating the GitHub Release (needed for `/releases/latest`, research D6); drop the zip build, SHA-256, and asset-upload steps (uv builds from git source).
- [x] T031 [P] Rewrite `README.md` for the uv flow only (FR-024): `uv tool install --from git+<repo>`, running from any folder, `--config`/`--version`/`--update`, and CWD `inventory`/`output/` conventions; remove clone + `install.py`/`run.py` instructions.
- [x] T032 [P] Update `docs/index.html` to match `README.md` (uv install/run/update), keeping the two consistent per the constitution's Documentation gate (FR-024).
- [x] T033 [P] Update `CONTRIBUTING.md` release runbook: releases are a `VERSION`-matched tag + a GitHub Release object (no zip/checksum packaging step); the self-updater note is replaced by the uv-update description.
- [x] T034 [P] Update `.env.example` and `.gitignore`: document env-var usage + the per-user config location, and drop the now-unused `.update-backup`/`.update-in-progress` ignore lines and `tools/install-test/share/`.
- [x] T035 Amend the constitution via the `/speckit-constitution` skill (NOT a raw edit): Principle II drops the `install.py`/`run.py`/`.venv` mandate while keeping cross-platform parity; the Technology & Data Constraints + self-updater paragraph are rewritten for uv-based updates; MAJOR version bump (1.4.0 → 2.0.0) with an updated Sync Impact Report and dependent-template consistency (FR-024, plan Constitution Check gate II).
- [x] T036 Final validation: `python -m unittest discover -s tests -v` is green; execute the [quickstart.md](quickstart.md) scenarios; confirm analysis output is unchanged versus the pre-uv tool for the same inputs (FR-022); note manual macOS/Windows/Linux parity checks (SC-007).

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories**.
- **User stories (Phases 3–7)**: all depend on Foundational. US1 is the MVP; the others build on the
  same `analyzer.py`/`cli.py` so they are sequenced by priority (they touch overlapping files).
- **Polish (Phase 8)**: depends on the user stories being complete (old entry points can only be
  retired once the new command fully replaces them).

### User story dependencies

- **US1 (P1)** — MVP. Independently testable via an env-var API key (no US2 needed).
- **US2 (P1)** — independent of US1's run logic; adds the `--config` UI and persistent key.
- **US3 (P2)** — independent; adds `--version`/`--update` and the run-start nudge.
- **US4 (P2)** — refines US1's inventory step; test after US1.
- **US5 (P3)** — refines US1's URL/confirmation step; test after US1.

> Note: US4 and US5 both modify `analyzer.py`/`cli.py`, so treat them as sequential edits to those
> files rather than parallel work, even though each is independently *testable*.

### Within each story

- Models/helpers before wiring; wiring before its tests validate it.
- Commit after each task or logical group; keep `main` releasable via the branch/PR.

### Parallel opportunities

- **Foundational**: T004, T005, T006, T007 are `[P]` — different files, no interdependencies (after T003 exists).
- **US2**: T014 and T017 `[P]`; **US3**: T022 `[P]`; **US1**: T012 `[P]`.
- **Polish**: T028–T034 are largely `[P]` (distinct files: workflows, README, docs, CONTRIBUTING, .gitignore). T035 (constitution) and T036 (validation) run after the retirement/doc tasks.

---

## Parallel Example: Foundational phase

```bash
# After T003 (cli.py skeleton) exists, run these together — different files:
Task: "Create config.py per-user config + precedence (T004)"
Task: "Create version.py pure version helpers (T005)"
Task: "Add ui.select menu helper (T006)"
Task: "Retarget test_extraction.py imports (T007)"
```

## Parallel Example: Polish phase

```bash
# Independent files — safe to parallelize:
Task: "Update ci.yml for uv (T029)"
Task: "Update release.yml — keep Release, drop zip (T030)"
Task: "Rewrite README.md for uv (T031)"
Task: "Update docs/index.html (T032)"
Task: "Update CONTRIBUTING.md runbook (T033)"
```

---

## Implementation Strategy

### MVP first (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP and validate**: install via uv and
   run from a fresh folder with an env-var API key (SC-001, SC-003).

### Incremental delivery

1. Setup + Foundational → package installs and dispatches.
2. US1 → install & run from any folder (MVP).
3. US2 → persistent per-user credentials.
4. US3 → version reporting + uv update + run-start nudge.
5. US4 → guided inventory picker.
6. US5 → URL prompt + confirmation guardrail.
7. Polish → retire old flow, update CI/docs, **amend constitution**, full validation.

### Notes

- `[P]` = different files, no dependencies on incomplete tasks.
- Analysis logic (`cisco.py`, `fuelix.py`, `inventory.py`, `report.py`) stays behavior-identical
  (FR-022, Principle IV) — only its packaging and call sites change.
- **T035 must use `/speckit-constitution`**, not a hand edit, so the version bump, Sync Impact Report,
  and template consistency are handled correctly — it can be run any time before the PR merges but
  after the FR-024 code/doc changes exist.
- Keep secrets out of logs and version control throughout (Principle V, FR-023).
