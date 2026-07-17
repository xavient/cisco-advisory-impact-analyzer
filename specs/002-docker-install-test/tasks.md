---

description: "Task list for Dockerized End-to-End Installation Test"
---

# Tasks: Dockerized End-to-End Installation Test

**Input**: Design documents from `/specs/002-docker-install-test/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: Not requested. The plan validates the harness manually via `quickstart.md`
scenarios (no automated test suite is added for the shell script), so this task list
contains **no test tasks**.

**Organization**: Tasks are grouped by user story. Because this feature ships as just two
files (`tools/install-test/test-install.sh` and `tools/install-test/Dockerfile`), each user
story is an **incremental slice of the same script**, independently *validatable* via its
quickstart scenario rather than independently deployable. Tasks that edit the same file are
therefore sequential (no `[P]`); `[P]` is used only across genuinely different files.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- All paths are repository-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the harness folder and skeletons of the two artifacts.

- [X] T001 Create the harness directory `tools/install-test/`
- [X] T002 [P] Create `tools/install-test/Dockerfile` skeleton: `FROM python:3.9-slim`, a clean `WORKDIR` (e.g. `/work/app`), `COPY . /work/app`, `CMD ["/bin/bash"]` — no `RUN pip install`, no baked deps (per research.md D2/D8)
- [X] T003 Create `tools/install-test/test-install.sh` skeleton: shebang, `set -euo pipefail`, `--help`/`-h` usage text, argument parsing for `--keep`, `--local <path>`, `--share <dir>`, unknown-flag → stderr + exit `2`; then `chmod +x` the script (contracts/cli.md Options)
- [X] T004 [P] Create `tools/install-test/README.md` with a short usage note mirroring contracts/cli.md

**Checkpoint**: `./tools/install-test/test-install.sh --help` prints usage and exits `0`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared mechanics every story relies on. **No user story work can begin until this phase is complete.**

- [X] T005 In `tools/install-test/test-install.sh`, implement `preflight()`: verify `docker` on PATH and daemon reachable (`docker info`), and `curl` + `unzip` present; on failure print an actionable message and exit `3` (FR-007, research.md D7)
- [X] T006 In `tools/install-test/test-install.sh`, create a host staging temp dir (`mktemp -d`) and install an `EXIT`/`INT`/`TERM` trap that always removes the staging dir and makes interrupts exit `130` (foundation for cleanup; extended in US3) (FR-010, data-model Validation rules)

**Checkpoint**: Running the script fails fast with a clear message when Docker is down, and never leaves a staging temp dir behind.

---

## Phase 3: User Story 1 - Fresh environment with an interactive shell for the installer (Priority: P1) 🎯 MVP

**Goal**: One command produces a fresh container holding the release and drops the maintainer into an interactive shell in the package folder, ready to run `python3 install.py`.

**Independent Test**: Run `./tools/install-test/test-install.sh`; confirm you land at an interactive `bash` prompt in the folder containing `install.py`, and that `python3 install.py` runs and its prompts accept typed input (quickstart Scenarios 1 & 3).

- [X] T007 [US1] In `tools/install-test/test-install.sh`, download the published release fresh via `curl -fL <latest-release .zip URL>` into the staging dir; on download failure print a message identifying the download and exit `4` (FR-004 default source, FR-008, research.md D1)
- [X] T008 [US1] In `tools/install-test/test-install.sh`, unpack the archive and locate the directory containing `install.py` under staging (`find -maxdepth 3`); set it as `APP_ROOT`; if not found, print an actionable error and exit `4` (research.md D6)
- [X] T009 [US1] In `tools/install-test/test-install.sh`, build a throwaway image from `APP_ROOT` as the build context using the Dockerfile with a unique tag: `docker build -f tools/install-test/Dockerfile "$APP_ROOT" -t <tag>` (research.md D2)
- [X] T010 [US1] In `tools/install-test/test-install.sh`, run the container interactively — `docker run -it ... <tag> /bin/bash` — starting in the app working directory so the installer's hidden-input prompts work over a real TTY (FR-005, FR-006)
- [X] T011 [US1] In `tools/install-test/test-install.sh`, resolve the share dir (`--share <dir>` created if missing, else a temp dir), bind-mount it to `/work/share`, and print its absolute host path prominently (FR-011, research.md D5)
- [X] T012 [US1] In `tools/install-test/test-install.sh`, print an on-entry guidance banner (or MOTD) telling the maintainer to run `python3 install.py`, where `/work/share` is, and how to bring an inventory in / capture `output/` via the mount (quickstart Scenarios 3 & 4)

**Checkpoint**: MVP complete — a maintainer can go from one command to a working interactive install session in a fresh container.

---

## Phase 4: User Story 2 - Environment mirrors a clean end-user machine using the published package (Priority: P2)

**Goal**: Guarantee the environment is a faithful clean end-user machine (minimum Python 3.9, no leftover install state, no repo secrets) and support validating a pre-publish package.

**Independent Test**: Before running `install.py`, inspect the container: `python3 --version` is 3.9.x, and there is no `.venv`/`.env`, no importable `openpyxl`/`python-dotenv`, and no inventory (quickstart Scenario 2); and `--local .` stages the working tree without secrets.

- [X] T013 [US2] In `tools/install-test/Dockerfile`, confirm/lock the clean-baseline guarantees: base `python:3.9-slim`, no dependency install steps, workdir contains only release files (no `.venv`/`.env`) — so the pre-install container is a true clean slate (FR-003, US2-AS2/AS3)
- [X] T014 [US2] In `tools/install-test/test-install.sh`, enforce that the Docker build context is the staging-derived `APP_ROOT` only (never the repo root) and add a guard asserting `APP_ROOT` resolves under the staging dir, so `.env`/`.venv`/inventory can never enter the image (SC-002, research.md D3, Constitution V)
- [X] T015 [US2] In `tools/install-test/test-install.sh`, implement `--local <path>`: a `.zip` is unpacked into staging like the published archive; a directory is copied into staging with an exclude list (`.venv/`, `.env`, `inventory/`, `output/`, `__pycache__/`, `.git/`, `*.pyc`, `~$*.xlsx`) to preserve the clean baseline (FR-012, research.md D9)

**Checkpoint**: US1 + US2 — the fresh shell is verifiably a clean 3.9 end-user machine, secrets stay out, and pre-publish packages can be tested.

---

## Phase 5: User Story 3 - Repeatable and self-cleaning tests (Priority: P3)

**Goal**: Every run starts from the same pristine baseline and, by default, leaves nothing behind; `--keep` preserves a run for debugging.

**Independent Test**: Run, `exit`, and confirm `docker ps -a` / `docker images` show no leftovers; run again and get an identical clean baseline; run with `--keep` and confirm the container/image are retained with printed re-enter/remove commands (quickstart Scenarios 5 & 6).

- [X] T016 [US3] In `tools/install-test/test-install.sh`, default cleanup: run the container with `--rm` (auto-removed on exit) and extend the trap to remove the throwaway image (`docker rmi`) and any temp share dir on normal exit, error, or interrupt — leaving zero environments on the host (FR-002, FR-009, FR-010, SC-005)
- [X] T017 [US3] In `tools/install-test/test-install.sh`, implement `--keep`: use a named container without `--rm`, retain the image and (if temp) the share dir, and print exact commands to re-enter (`docker start -ai <name>`) and later remove (`docker rm <name>` / `docker rmi <tag>`) (FR-010, research.md D4)

**Checkpoint**: All three stories functional — repeatable, self-cleaning by default, keepable on demand.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, ignores, and full end-to-end validation.

- [X] T018 [P] Update `.gitignore` to ignore any in-repo harness artifacts (e.g. `tools/install-test/share/` and any local staging output)
- [X] T019 [P] Update the root `README.md` "For maintainers" section with a short note pointing at `tools/install-test/test-install.sh`
- [X] T020 [P] Reconcile the script's `--help` text and `tools/install-test/README.md` with contracts/cli.md (flags, exit codes)
- [X] T021 Run all `quickstart.md` scenarios (1–8) end to end and confirm expected outcomes, including failure modes (Docker down, missing release) and `--keep`/`--local` paths (SC-001, SC-003, SC-006)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately. T001 first; then T002/T004 `[P]` and T003.
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**.
- **User Stories (Phase 3–5)**: All depend on Foundational. Because they edit the same
  `test-install.sh`, run them in priority order (US1 → US2 → US3) rather than in parallel.
- **Polish (Phase 6)**: Depends on the desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational. Delivers the MVP.
- **US2 (P2)**: Builds on US1's acquisition/build steps (hardens fidelity + adds `--local`);
  independently *validatable* by inspecting the clean baseline.
- **US3 (P3)**: Builds on US1's `docker run` (adds cleanup + `--keep`); independently
  *validatable* by checking for leftovers after exit.

### Within Each User Story

- Tasks touching `test-install.sh` are sequential (same file).
- US1: acquire (T007) → locate (T008) → build (T009) → run (T010) → mount (T011) → banner (T012).

### Parallel Opportunities

- Setup: T002 (Dockerfile) and T004 (README) run in parallel with each other and alongside T003 (script) — different files.
- Polish: T018 (`.gitignore`), T019 (root README), T020 (harness README/`--help`) are different files → `[P]`.
- The three user stories are **not** parallelizable with each other (shared `test-install.sh`).

---

## Parallel Example: Setup Phase

```bash
# After T001 (mkdir), these touch different files and can run together:
Task: "T002 Create tools/install-test/Dockerfile skeleton"
Task: "T004 Create tools/install-test/README.md"
# T003 (test-install.sh skeleton) is a different file too and can run alongside T002/T004.
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (T001–T004)
2. Phase 2: Foundational (T005–T006) — **blocks everything**
3. Phase 3: User Story 1 (T007–T012)
4. **STOP and VALIDATE**: run the script, land in the shell, run `python3 install.py` to
   "Setup complete" (quickstart Scenarios 1 & 3).

### Incremental Delivery

1. Setup + Foundational → base ready
2. US1 → validate → **MVP** (interactive install works)
3. US2 → validate clean-baseline fidelity + `--local`
4. US3 → validate repeatability, default cleanup, `--keep`
5. Polish → docs, ignores, full quickstart pass

---

## Notes

- No automated tests requested; validation is the `quickstart.md` scenarios (T021).
- `[P]` = different files, no dependencies. Most US tasks share `test-install.sh` → sequential.
- Constitution V: keep the Docker build context on the staging dir (T014) so repo secrets
  never enter the image.
- Commit after each task or logical group; work stays on branch `002-docker-install-test`.
