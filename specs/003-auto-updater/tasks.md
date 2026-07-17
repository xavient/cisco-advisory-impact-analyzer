---

description: "Task list for Self-Update Mechanism (Auto-Updater)"
---

# Tasks: Self-Update Mechanism (Auto-Updater)

**Input**: Design documents from `/specs/003-auto-updater/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md,
contracts/release-artifacts.md, quickstart.md

**Tests**: Requested (targeted). The plan's Testing section and the constitution's
testability gate require offline unit tests for the pure logic — semantic-version
parse/compare, manifest add/remove diff, preserve-list exclusion, and `VERSION` read. These
appear as test tasks next to the logic they cover. Network/download/apply/rollback flows are
validated manually via `quickstart.md` (not in CI).

**Organization**: Tasks are grouped by user story. The feature is a small set of files
(`VERSION`, `MANIFEST`, `updater.py`, `update.py`, plus edits to `run.py`/`.gitignore`/docs
and a release workflow). Most story work extends the same `updater.py`/`update.py`, so those
tasks are sequential; `[P]` is used only across genuinely different files.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US4)
- All paths are repository-relative (flat single-project layout per plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the version source-of-truth, the updater module skeleton, and ignores.

- [ ] T001 Create `VERSION` at the repo root containing the current released version (`1.1.0`, no leading `v`) — the single source of truth read by the updater, `run.py --version`, and the nudge (FR-003, research D1). The release workflow stamps it thereafter.
- [ ] T002 [P] Create `updater.py` skeleton at the repo root: module docstring (stdlib-only, runs on base Python), imports (`urllib.request`/`urllib.error`, `json`, `hashlib`, `zipfile`, `tempfile`, `shutil`, `os`, `pathlib`), and constants — `REPO = "xavient/cisco-advisory-impact-analyzer"` with `CAIA_UPDATE_REPO` override, derived GitHub API/asset URLs, `PRESERVE = {".env", "inventory", "output", ".venv"}`, and backup/marker path constants (`.update-backup/`, `.update-in-progress`) (research D13, data-model).
- [ ] T003 [P] Update `.gitignore` to ignore `/.update-backup/` and `/.update-in-progress` (plan Structure, data-model).
- [ ] T004 [P] Create `MANIFEST` at the repo root listing the packaged runtime paths (the exclude list in research D12), so a from-source install carries an old manifest for future removal diffs (FR-019).

**Checkpoint**: `python3 -c "import updater"` imports cleanly; `VERSION`, `MANIFEST`, and the ignores exist.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ratify the reviewed change (new external endpoint) **before any networking code
is introduced**, then build the shared primitives used by **every** user story — read the
installed version, compare versions, and resolve the latest release. **No user story work can
begin until this phase is complete.**

- [ ] T005 **Governance gate (do first, blocks T008)**: Amend `.specify/memory/constitution.md` to add GitHub (`api.github.com`, `github.com`, `objects.githubusercontent.com`) to the allowed external endpoints for the updater — with a Sync Impact Report and a version bump — recording the constitution-mandated "reviewed change" **in this PR, before** the endpoint-contacting code lands. Use `/speckit-constitution` (plan Constitution Check, research D13).
- [ ] T006 In `updater.py`, implement `read_installed_version()` reading the root `VERSION`; a missing/unparseable file yields *unknown* (sorts as older; never crashes) (FR-003, data-model).
- [ ] T007 In `updater.py`, implement `parse_version()` and `compare_versions()` — numeric, component-wise; strip a leading `v`; missing components → `0` (`1.2` == `1.2.0`); unknown sorts lowest; must order `1.10.0` > `1.9.0` (FR-004, spec Clarifications Q3).
- [ ] T008 In `updater.py`, implement `resolve_latest()` — GitHub Releases API `tag_name` (send `Accept: application/vnd.github+json` + `User-Agent`; `urllib` honors `HTTP(S)_PROXY`), with a fallback that reads the tag from the `…/releases/latest` redirect URL on HTTP 403/rate-limit/unreachable; return `(tag, reachable)`. **Requires the T005 reviewed change** (FR-004, FR-013 proxy, FR-015, research D2).
- [ ] T009 In `updater.py`, implement `check_update()` combining installed + latest into an Update Check Result: `up_to_date` | `update_available` | `ahead` | `latest_unknown` (FR-004, FR-005, data-model).
- [ ] T010 Create `tests/test_updater.py` with offline unit tests for `parse_version`/`compare_versions` (equal, older, ahead, `v`-prefix, `1.10.0` > `1.9.0`, unknown) and `read_installed_version` (present / missing / garbage) (Constitution testability; quickstart "Automated checks").

**Checkpoint**: The reviewed change is ratified; `python3 -m unittest tests.test_updater` passes; version compare + `check_update()` behave correctly offline (with a stubbed latest).

---

## Phase 3: User Story 1 - Update to the latest version, keeping my data (Priority: P1) 🎯 MVP

**Goal**: `python3 update.py` takes an older install to the latest release — download, verify,
back up, apply preserving the preserve-list, refresh deps — leaving the tool immediately
usable.

**Independent Test**: On an older install with a populated `.env`, an `inventory/*.xlsx`, and
prior reports, run `python3 update.py` (and `--yes`); confirm the app files are the latest,
the tool runs, and `.env`/`inventory/`/`output/`/`.venv/` are unchanged. A tampered/failed
download makes no changes (quickstart Scenarios 3, 5, 7).

- [ ] T011 [US1] In `updater.py`, implement `download_release(tag)` — download the **tag-pinned** asset `cisco-advisory-impact-analyzer.zip` and its sibling `…zip.sha256` over HTTPS into a temp dir (`urllib`, proxy-honored); actionable error on failure (FR-014, research D3).
- [ ] T012 [US1] In `updater.py`, implement `verify_package()` — SHA-256 of the zip equals the published digest, the archive is a well-formed zip (`ZipFile` + `testzip()`), and its embedded root `VERSION` equals the tag; extract to staging and locate the package root (dir containing `VERSION`, depth ≤ 2). Any failure ⇒ no files changed (FR-006, research D3/D11).
- [ ] T013 [US1] In `updater.py`, implement `create_backup()` — before any change, copy every file the update will overwrite or remove (plus the current `VERSION`/`MANIFEST`) into `.update-backup/<old>-<timestamp>/`, **never** touching the preserve-list (FR-011, research D4/D8).
- [ ] T014 [US1] In `updater.py`, implement `apply_update()` — write the `.update-in-progress` marker; overlay staged files skipping `PRESERVE` / `.git/` / `.update-backup/` / the marker; apply manifest-diff deletions (old ∖ new, minus preserve-list); write the new `VERSION`/`MANIFEST`; clear the marker (FR-002, FR-012 marker, FR-019, research D4/D5).
- [ ] T015 [US1] In `updater.py`, implement `refresh_deps_if_changed()` — compare old vs new `requirements.txt`; if changed and a `.venv` exists, run the venv interpreter (`.venv/Scripts/python.exe` on Windows, `.venv/bin/python` otherwise) `-m pip install -r requirements.txt`; if no `.venv`, print an actionable hint to run `install.py` (FR-007, research D6).
- [ ] T016 [US1] Extend `tests/test_updater.py` with offline tests for the manifest add/remove diff (old ∖ new) and preserve-list exclusion (pure functions; no network/filesystem side effects) (Constitution testability).
- [ ] T017 [US1] Create `update.py` — argparse CLI (default update path, `--yes`/`-y`, `--repo`, `--help`) that orchestrates check → show `current → new` → `ui.confirm` (skipped by `--yes`) → download → verify → backup → apply → refresh deps → report new version; up-to-date/ahead short-circuit with no changes; actionable `ui.fail` errors and exit codes `0/1/2/3/4` with `130` on Ctrl-C via a `run_cli`-style handler (FR-001, FR-005, FR-009, FR-018, contracts/cli.md, research D14). Rollback/auto-revert/recovery are added in US3.

**Checkpoint**: MVP — an older install updates to latest in one command; preserve-list intact; deps refreshed; a failed verify exits `4` with zero changes.

---

## Phase 4: User Story 2 - Check my version and whether an update exists (Priority: P2)

**Goal**: Report the installed version and whether a newer one exists, changing nothing.

**Independent Test**: `python3 update.py --check` prints Installed/Latest/Status; `python3
run.py --version` prints the installed version; already-latest is a no-op (quickstart
Scenarios 1, 2, 4).

- [ ] T018 [P] [US2] In `update.py`, add `--check` mode — print `Installed` / `Latest` / `Status` from `check_update()` (`up to date` | `update available` | `ahead of latest` | `latest unknown`) and make **no** changes. Exit `0` whenever the installed version is readable (even if latest is unknown); exit `3` only when neither installed nor latest can be determined (per contracts/cli.md) (FR-008).
- [ ] T019 [P] [US2] In `run.py`, add `--version` handling **before** delegating to the analyzer — print `read_installed_version()` and exit `0`; the flag is consumed by `run.py`, not passed through (FR-010, contracts/cli.md).

**Checkpoint**: US1 + US2 — users can update, and can inspect version/availability without side effects.

---

## Phase 5: User Story 3 - Recover from a failed or unwanted update (Priority: P3)

**Goal**: A one-step rollback plus automatic recovery, so an install is always fully-old or
fully-new and never a broken mixture.

**Independent Test**: After an update, `python3 update.py --rollback` restores the prior
version with data intact; an apply error auto-reverts; an interrupted apply is recovered on
the next invocation (quickstart Scenarios 6, 10).

- [ ] T020 [US3] In `updater.py`, implement `restore_backup()` — restore the newest `.update-backup/…` over the install (skipping the preserve-list) and restore the prior `VERSION`/`MANIFEST` (FR-011).
- [ ] T021 [US3] In `updater.py`, wire **auto-revert**: if `apply_update()` (or the finalize step) raises, call `restore_backup()`; return distinct outcomes for revert-succeeded vs revert-failed so the CLI can exit `5` vs `6` (FR-012, research D14).
- [ ] T022 [US3] In `updater.py`, implement **startup recovery**: if `.update-in-progress` exists, restore from the recorded backup before doing anything else (FR-012, data-model recovery).
- [ ] T023 [US3] In `updater.py`, implement backup **retention pruning** — on a successful update keep only the last 2 backups (research D8).
- [ ] T024 [US3] In `update.py`, add the `--rollback` command (restore newest backup, report reverted version, exit `1` if none), call startup recovery at entry, and surface the auto-revert exit codes `5`/`6` from the update path (FR-011, FR-012, contracts/cli.md, research D14).

**Checkpoint**: US1–US3 — updates are reversible and crash-safe; the preserve-list survives rollback.

---

## Phase 6: User Story 4 - Be nudged when an update is available (Priority: P4)

**Goal**: A best-effort, stateless, non-blocking notice during a normal analyzer run.

**Independent Test**: With a local `VERSION` below the latest, `python3 run.py --dry-run`
prints one update notice and still runs; `--no-update-check` / `CAIA_NO_UPDATE_CHECK`
suppresses it; offline shows no notice and no delay (quickstart Scenario 9).

- [ ] T025 [US4] In `updater.py`, add `passive_check(timeout=2)` — best-effort, short-timeout, swallow-all wrapper returning the newer version or `None` (stateless; never raises) (FR-016, research D9).
- [ ] T026 [US4] In `run.py`, call `passive_check()` before delegating and print one `ui.info` line if newer (naming the version + `python3 update.py`); add `--no-update-check` (consumed, not passed through) and honor `CAIA_NO_UPDATE_CHECK`; the run must never be blocked, delayed noticeably, or failed by the check (FR-016, contracts/cli.md).

**Checkpoint**: All four stories functional — update, check, recover, and passive nudge.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Release automation (required — FR-020/FR-021), documentation parity, and full
validation. (The constitution amendment moved to the Foundational governance gate, T005.)

- [ ] T027 [P] Create `.github/workflows/release.yml` — on a version-tag push: stamp `VERSION` = tag, regenerate `MANIFEST`, build the flat `cisco-advisory-impact-analyzer.zip` (runtime files only, per research D12 excludes), compute `cisco-advisory-impact-analyzer.zip.sha256`, and upload both as release assets (FR-020, FR-021, contracts/release-artifacts.md).
- [ ] T028 [P] Update `README.md` to document `python3 update.py`, `--check`, `--yes`, `--rollback`, `python3 run.py --version`, and the `--no-update-check` / `CAIA_NO_UPDATE_CHECK` opt-out (Constitution Documentation gate).
- [ ] T029 [P] Update `docs/index.html` with an in-place update note (`python3 update.py`), mirroring the README so the two stay consistent (Constitution Documentation gate).
- [ ] T030 Run all `quickstart.md` scenarios (1–10) plus the release-side validation end-to-end, confirming outcomes including failure/offline/rollback paths (SC-001–SC-009).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately. T001 first; T002/T003/T004 `[P]`.
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**. T005 (governance
  gate) runs first and blocks the endpoint-contacting T008; T006–T009 extend `updater.py`
  sequentially; T010 (tests) after the version primitives.
- **User Stories (Phases 3–6)**: All depend on Foundational. US1 → US2 → US3 mostly extend
  the same `updater.py`/`update.py`, so run in priority order; US4 touches `run.py` +
  `updater.py`.
- **Polish (Phase 7)**: Depends on the desired user stories being complete (T027 release
  automation can proceed once the shipped file set/`MANIFEST` is stable).

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational. Delivers the MVP (a working update).
- **US2 (P2)**: Depends on Foundational (`check_update`, `read_installed_version`);
  independent of US1's apply path — independently testable via `--check` / `--version`.
- **US3 (P3)**: Builds on US1's backup/marker (adds rollback, auto-revert, recovery);
  independently testable by reverting an applied update.
- **US4 (P4)**: Depends on Foundational (`check_update`); independent of US1–US3 —
  independently testable via a normal run.

### Within Each User Story

- Tests (where included) sit next to the logic they cover: semver/VERSION tests in
  Foundational (T010); manifest-diff/preserve tests in US1 (T016).
- `updater.py` library functions before the `update.py`/`run.py` code that calls them.
- US1 order: download (T011) → verify (T012) → backup (T013) → apply (T014) → deps (T015) →
  CLI (T017).

### Parallel Opportunities

- **Setup**: T002 (`updater.py`), T003 (`.gitignore`), T004 (`MANIFEST`) are different files → `[P]`.
- **US2**: T018 (`update.py`) and T019 (`run.py`) are different files with no interdependency → `[P]`.
- **Polish**: T027 (`release.yml`), T028 (`README.md`), T029 (`docs/index.html`) are different
  files → `[P]`. T030 (validation) runs last.
- The Foundational governance gate (T005) and each story's `updater.py` edits are sequential.

---

## Parallel Example: Setup Phase

```bash
# After T001 (VERSION), these touch different files and can run together:
Task: "T002 Create updater.py skeleton with constants"
Task: "T003 Update .gitignore for backup/marker"
Task: "T004 Create MANIFEST with packaged runtime paths"
```

## Parallel Example: Polish Phase

```bash
# Different files — run together:
Task: "T027 Create .github/workflows/release.yml"
Task: "T028 Update README.md for the update commands"
Task: "T029 Update docs/index.html with the update note"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (T001–T004)
2. Phase 2: Foundational (T005–T010) — **blocks everything** (T005 governance gate first)
3. Phase 3: User Story 1 (T011–T017)
4. **STOP and VALIDATE**: on an older install run `python3 update.py`; confirm it reaches the
   latest with the preserve-list untouched, and a failed verify makes no changes (quickstart
   Scenarios 3, 5, 7). For dev before the release workflow exists, point `CAIA_UPDATE_REPO`
   at a fork carrying a test release (zip + `.sha256` + embedded `VERSION`).

### Incremental Delivery

1. Setup + Foundational → base ready (reviewed change ratified)
2. US1 → validate → **MVP** (update works, data safe)
3. US2 → validate `--check` / `run.py --version`
4. US3 → validate rollback + crash recovery
5. US4 → validate the passive nudge
6. Polish → release automation (T027), docs parity (T028/T029), full quickstart + release
   validation (T030)

---

## Notes

- Targeted tests only (pure logic): `tests/test_updater.py` (T010, T016). Network/apply/
  rollback are validated via `quickstart.md` (T030).
- `[P]` = different files, no dependencies. Same-file edits (`updater.py`, `update.py`,
  `run.py`) are sequential.
- Constitution: stdlib-only (no new deps), cross-platform (`pathlib`/`os.name`), never read/
  send/overwrite `.env` (preserve-list), meaningful exit codes; GitHub is the one reviewed
  new endpoint, ratified up front in T005 before any networking code.
- The updater runs on **base Python** (like `install.py`) — do not import analyzer modules or
  require `.venv`.
- Commit after each task or logical group; work stays on branch `003-auto-updater`.
