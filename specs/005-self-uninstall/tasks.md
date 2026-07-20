---

description: "Task list for the Self-Uninstall Command feature"
---

# Tasks: Self-Uninstall Command

**Input**: Design documents from `/specs/005-self-uninstall/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/uninstall-cli.md](./contracts/uninstall-cli.md), [quickstart.md](./quickstart.md)

**Tests**: Included. The plan's Technical Context commits to unit tests (`tests/test_version.py`, `tests/test_cli.py`) and the constitution's Development Workflow quality gate requires the suite to pass — so test tasks are part of this feature, not optional.

**Organization**: Tasks are grouped by user story. This feature is one cohesive command (`caia --uninstall`), so the three stories extend the *same* `cmd_uninstall` orchestration in `cli.py` on top of shared, independently-unit-testable helpers in `version.py`. US1 is a genuinely shippable MVP; US2 and US3 add distinct branches/messaging with their own tests.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish carry no story label)
- Exact file paths are included in every task

## Path Conventions

Single-project CLI. Source lives in `cisco_advisory_impact_agent/`, tests in `tests/`, docs in `README.md` and `docs/index.html` (repository root).

---

## Phase 1: Setup

**Purpose**: Establish a clean baseline before changing anything

- [ ] T001 Establish a green baseline: run `python -m pytest -q` from the repo root and confirm the existing suite passes. Confirm no new runtime dependency is required (feature is standard-library only per plan.md).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared, unit-testable plumbing in `version.py` plus the CLI entrypoint wiring. Every user story depends on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 Add `UninstallError(Exception)` to `cisco_advisory_impact_agent/version.py`, mirroring the existing `UpdateError` (docstring: "a `--uninstall` could not be completed; the install is left as-is").
- [ ] T003 Add `_distribution_installed()` to `cisco_advisory_impact_agent/version.py`: return `True`/`False` using `importlib.metadata.version(DIST_NAME)` (catch `PackageNotFoundError` → `False`). This is the "installed as a distribution?" signal (distinct from `read_installed_version()`, which falls back to the VERSION file).
- [ ] T004 Add `uv_tool_list_names(uv_path)` to `cisco_advisory_impact_agent/version.py`: run `uv tool list`, parse the leading tool/distribution name of each line into a set; return an empty set on any `OSError`/non-zero (never raise). Used to authoritatively answer "is this a uv tool?" per research Decision 3.
- [ ] T005 Add `InstallKind` constants (`UV_MANAGED`, `NOT_INSTALLED`, `PIP_OR_SOURCE`, `UNKNOWN_UV_ABSENT`) and `classify_uninstall(uv_path=None)` to `cisco_advisory_impact_agent/version.py`, composing `find_uv()`, `_distribution_installed()`, and `uv_tool_list_names()` into the decision tree from data-model.md (`NOT_INSTALLED` when metadata absent; `UV_MANAGED` when `uv` present and `DIST_NAME` listed; `PIP_OR_SOURCE` when `uv` present and not listed; `UNKNOWN_UV_ABSENT` when metadata present but `uv` not locatable).
- [ ] T006 Add `perform_uninstall()` to `cisco_advisory_impact_agent/version.py`, mirroring `perform_update()`: build the manual command string `uv tool uninstall cisco-advisory-impact-agent`, run `[uv, "tool", "uninstall", DIST_NAME]`, raise `UninstallError` (with the manual command and the Windows "close this command and run … from a fresh shell" note) on `OSError` or a non-zero return code.
- [ ] T007 [P] Add the `--uninstall` mode flag and the `--yes`/`-y` modifier to `build_parser()` in `cisco_advisory_impact_agent/cli.py`, with help text sitting beside `--update`/`--config` (different file from T002–T006, so parallelizable with the `version.py` stream).
- [ ] T008 Wire `--uninstall` into `_dispatch()` in `cisco_advisory_impact_agent/cli.py` to call `cmd_uninstall(args)` within the existing mode-precedence chain (version → update → uninstall → config → run; modes are mutually exclusive, not combined). `cmd_uninstall` itself is implemented in US1 (T009).

**Checkpoint**: Shared helpers exist and are unit-testable; the CLI parses `--uninstall`/`--yes` and dispatches to `cmd_uninstall`.

---

## Phase 3: User Story 1 - Remove the tool in one command, keeping my saved settings (Priority: P1) 🎯 MVP

**Goal**: On a uv-managed install, `caia --uninstall` (confirmed, or `--yes`) removes the tool via `uv` and, on success, discloses the preserved per-user config location. Declining removes nothing.

**Independent Test**: With `version.classify_uninstall` mocked to `UV_MANAGED` and `version.perform_uninstall` mocked, run `cmd_uninstall` with `--yes` → asserts `perform_uninstall` was invoked, exit code 0, and the success message includes the config path; run interactively and decline → asserts `perform_uninstall` NOT invoked and a non-zero exit.

### Implementation for User Story 1

- [ ] T009 [US1] Implement `cmd_uninstall(args)` in `cisco_advisory_impact_agent/cli.py`: call `version.classify_uninstall()`; for `UV_MANAGED`, confirm via `ui.confirm("Remove caia?", default=False)` unless `args.yes`; on proceed, call `version.perform_uninstall()`; catch `version.UninstallError` → `ui.fail(...)` and return non-zero; on success → `ui.ok(...)` and return 0. (Other `InstallKind` branches are added in US2/US3; a decline returns non-zero.)
- [ ] T010 [US1] Add success-time config disclosure in `cmd_uninstall` (`cisco_advisory_impact_agent/cli.py`, importing `config`): if `config.config_path().exists()`, report its path and how to delete it manually; otherwise state there was no saved configuration to preserve. Never read or print the file's contents (Constitution V / contract INV-1).
- [ ] T011 [P] [US1] Add CLI tests in `tests/test_cli.py` (patching `version.classify_uninstall`→`UV_MANAGED`, `version.perform_uninstall`, `config.config_path`, capturing stdout via `contextlib.redirect_stdout`): happy path with `--yes` (perform called, exit 0, config path in output); interactive confirm accepted vs declined (declined → not called, non-zero, install intact); config present vs absent messaging (FR-005).
- [ ] T012 [P] [US1] Add version tests in `tests/test_version.py` (patching `version.find_uv` and the removal subprocess, per existing `find_uv` test patterns): `perform_uninstall()` success (correct `uv tool uninstall DIST_NAME` argv, no raise) and failure (non-zero return and `OSError` both raise `UninstallError` carrying the manual command).

**Checkpoint**: `caia --uninstall`/`--uninstall --yes` fully removes a uv-managed install and discloses the preserved config — MVP shippable and independently testable.

---

## Phase 4: User Story 2 - Remove the tool without a prompt, for scripts or fleet cleanup (Priority: P2)

**Goal**: `--yes` skips the prompt; non-interactive without `--yes` refuses safely; "not installed as a uv tool" is an idempotent success (exit 0). The exit-code contract lets automation tell "tool is gone" from "action still needed."

**Independent Test**: With `sys.stdin.isatty` and `version.classify_uninstall` mocked: `--uninstall --yes` on `UV_MANAGED` → no prompt, exit 0; `--uninstall` with no TTY and no `--yes` → refused, non-zero, `perform_uninstall` not invoked; `classify → NOT_INSTALLED`/`PIP_OR_SOURCE` → informational message, exit 0 (re-run also exits 0).

### Implementation for User Story 2

- [ ] T013 [US2] Extend `cmd_uninstall` gating in `cisco_advisory_impact_agent/cli.py` for the `UV_MANAGED` branch, in order: `args.yes` → proceed without prompting; elif `not sys.stdin.isatty()` → refuse (message: `--yes` is required for non-interactive use), make no changes, return non-zero (FR-003a); else prompt as in US1.
- [ ] T014 [US2] Extend `cmd_uninstall` in `cisco_advisory_impact_agent/cli.py` for the idempotent branches: `NOT_INSTALLED` and `PIP_OR_SOURCE` → print an informational "not installed as a uv tool; nothing to uninstall" message and return 0 (no prompt, no changes) per research Decision 9.
- [ ] T015 [US2] Add CLI tests in `tests/test_cli.py`: `--yes` suppresses the prompt (no `input` call) and exits 0; non-interactive (`isatty`→False) without `--yes` refuses with non-zero and does not call `perform_uninstall`; `NOT_INSTALLED` and `PIP_OR_SOURCE` each exit 0 with the informational message; a repeat run stays exit 0 (idempotence for fleet cleanup).

**Checkpoint**: Scripted/fleet removal works; already-clean machines exit 0; unsafe non-interactive removal is refused.

---

## Phase 5: User Story 3 - Get a clear explanation when automatic removal isn't possible (Priority: P3)

**Goal**: When automatic removal can't proceed, the tool explains clearly and points to the exact next step, without a half-removed state — `uv` missing (manual command, non-zero) and removal failure / Windows self-lock (instruct to re-run from a fresh shell, non-zero). The source/pip "nothing to uninstall" message (implemented in US2) is verified here for clarity.

**Independent Test**: With `version.classify_uninstall` mocked: `UNKNOWN_UV_ABSENT` → prints the exact `uv tool uninstall cisco-advisory-impact-agent` command, non-zero, `perform_uninstall` not invoked; `UV_MANAGED` with `perform_uninstall` raising `UninstallError` → surfaces the actionable message (incl. Windows fresh-shell guidance), non-zero, no false success; `PIP_OR_SOURCE` → message clearly states it's a source/pip install (exit 0).

### Implementation for User Story 3

- [ ] T016 [US3] Extend `cmd_uninstall` in `cisco_advisory_impact_agent/cli.py` for `UNKNOWN_UV_ABSENT`: print that `uv` could not be located plus the exact manual removal command, make no changes, return non-zero (FR-008).
- [ ] T017 [US3] Verify/round out the `REMOVAL_FAILED` path in `cisco_advisory_impact_agent/cli.py`: `cmd_uninstall` catches `version.UninstallError` and surfaces its full actionable message (manual command + Windows "run from a fresh shell" guidance from T006), returning non-zero and claiming no success (FR-011, FR-013).
- [ ] T018 [US3] Add CLI tests in `tests/test_cli.py`: `UNKNOWN_UV_ABSENT` → manual command printed, non-zero, `perform_uninstall` not called (AS2); `perform_uninstall` raising `UninstallError` → actionable message surfaced, non-zero, no false success (AS3); `PIP_OR_SOURCE` message clearly explains a source/pip install (AS1).

**Checkpoint**: Every non-removable situation yields a clear, actionable message and a correct exit code — no confusing failures, no half-removed state.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation consistency (Documentation quality gate) and end-to-end validation

- [ ] T019 [P] Add an "Uninstall" section to `README.md` beside Install/Update: `caia --uninstall` (and `--yes`), that the saved API key/config is preserved and where it lives, and the manual `uv tool uninstall cisco-advisory-impact-agent` fallback.
- [ ] T020 [P] Mirror the same uninstall instructions in `docs/index.html` (the Documentation gate requires README and the landing page to stay consistent with each other and the code).
- [ ] T021 Run the full suite `python -m pytest -q` from the repo root and confirm all tests pass (existing + new).
- [ ] T022 Execute the [quickstart.md](./quickstart.md) validation: automated (`pytest tests/test_version.py tests/test_cli.py`) and, on a throwaway uv install, manual Scenarios A–G; note any scenario that could not be exercised.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories**.
- **User Stories (Phases 3–5)**: all depend on Foundational. Because US1/US2/US3 edit the *same* `cmd_uninstall` function in `cli.py`, they are executed **sequentially in priority order** (P1 → P2 → P3), not in parallel across stories.
- **Polish (Phase 6)**: depends on the desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: needs Foundational (T002–T008). Introduces `cmd_uninstall`. Independently testable and shippable as the MVP.
- **US2 (P2)**: needs Foundational + US1's `cmd_uninstall` (T009/T010) to extend. Independently testable via its own mocked branches.
- **US3 (P3)**: needs Foundational + US1's `cmd_uninstall`. Independent of US2 in behavior (different branches), but edits the same file, so sequenced after US2.

### Within Each User Story

- Implementation before its tests (tests exercise the implemented branches).
- In US1, `cmd_uninstall` core (T009) before config disclosure (T010) before tests.

### Parallel Opportunities

- **Foundational**: T007 (`cli.py` arg parsing) is `[P]` with the `version.py` stream (T002–T006), since they are different files; T002–T006 are sequential among themselves (all edit `version.py`), and T008 follows T007 (same file).
- **US1**: T011 (`tests/test_cli.py`) and T012 (`tests/test_version.py`) are `[P]` with each other once implementation (T009/T010, T006) is done — different files.
- **Polish**: T019 (`README.md`) and T020 (`docs/index.html`) are `[P]` — different files.
- **Cross-story**: none — US1/US2/US3 share `cmd_uninstall`, so they cannot be parallelized against each other.

---

## Parallel Example: Foundational + US1

```bash
# Foundational: the cli.py flag work can proceed alongside the version.py helper stream
Task: "T007 Add --uninstall/--yes to build_parser() in cisco_advisory_impact_agent/cli.py"
# ... in parallel with the sequential version.py tasks T002 → T006

# US1: after cmd_uninstall + disclosure exist, run both test files together
Task: "T011 CLI tests in tests/test_cli.py"
Task: "T012 version tests (perform_uninstall) in tests/test_version.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (green baseline).
2. Phase 2: Foundational (helpers + CLI wiring) — CRITICAL, blocks everything.
3. Phase 3: User Story 1 — happy-path removal + config disclosure.
4. **STOP and VALIDATE**: `caia --uninstall`/`--uninstall --yes` removes a uv-managed install and discloses the preserved config.
5. This is a shippable increment on its own.

### Incremental Delivery

1. Setup + Foundational → plumbing ready.
2. US1 → MVP (remove + disclose) → validate → demo.
3. US2 → scripted `--yes`, non-interactive refusal, idempotent exit codes → validate.
4. US3 → clear explanations for uv-missing / removal-failure → validate.
5. Polish → README + landing-page docs, full suite + quickstart validation.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- `[Story]` labels map tasks to spec.md user stories for traceability.
- The three stories share `cmd_uninstall`; keep each story's branch and messaging cohesive and commit after each logical group.
- Invariants to uphold in every branch (contract INV-1…INV-5): never read/print/transmit the API key (only its path); never touch user work products; no network access; never remove without `--yes` or an affirmative prompt; every non-success message names the next step.
- Ctrl+C → exit 130 with no traceback is already handled by `main()`'s `KeyboardInterrupt` guard — no per-task work needed, but keep prompts routed through `ui.confirm`/`ui.ask` which raise `KeyboardInterrupt`.
