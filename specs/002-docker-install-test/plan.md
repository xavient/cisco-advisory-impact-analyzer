# Implementation Plan: Dockerized End-to-End Installation Test

**Branch**: `002-docker-install-test` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-docker-install-test/spec.md`

## Summary

Provide a single maintainer-run shell script that spins up a fresh, disposable Docker
container mirroring a clean end-user machine (minimum-supported Python 3.9 on Debian slim,
no pre-built `.venv`/`.env`/deps/inventory), places the **published release package** into
it (downloaded fresh from the GitHub latest-release URL), and drops the maintainer into an
interactive shell in the package folder so they can run `python3 install.py` and exercise
installation — and optionally a full analyzer run — exactly as an end user would. The
harness downloads and unpacks on the host, builds the image from a staging directory that
**excludes repo secrets**, bind-mounts an empty share folder for bringing an inventory in
and capturing reports, defaults to removing the environment on exit, and offers `--keep`
(preserve for debugging) and `--local <zip|dir>` (test a release candidate before publish).

## Technical Context

**Language/Version**: Bash launcher (`test-install.sh`); Docker image `python:3.9-slim`
(the container's Python is 3.9, the tool's minimum supported version). The analyzer under
test is unchanged Python 3.9+.

**Primary Dependencies**: Host-side — Docker Engine/Desktop, plus `curl` and `unzip`
(standard on macOS/Linux). Container-side — the `python:3.9-slim` base image (ships `pip`,
`venv`, `ensurepip`, `ca-certificates`, `bash`); the two existing runtime packages
(`openpyxl`, `python-dotenv`) are installed **by the real `install.py`**, not baked in. No
change to the analyzer's runtime dependency set.

**Storage**: Ephemeral only by default. A host temp staging dir holds the downloaded/
unpacked release (removed on exit); an (empty at launch) host share dir is bind-mounted for
inventory drop-in and output capture; the container filesystem is disposable.

**Testing**: Interactive, manual validation via the scenarios in
[quickstart.md](./quickstart.md) (land in shell → `python3 install.py` → "Setup complete"
→ optional `run.py`). The harness is itself validated by running it; no unit-test suite is
added for the shell script.

**Target Platform**: macOS or Linux host with a running Docker daemon; Linux container.
`python:3.9-slim` is multi-arch, so Docker pulls the host-matching arch (arm64 on Apple
Silicon, amd64 elsewhere) — no emulation required.

**Project Type**: Maintainer dev-tooling — a CLI shell script plus a Dockerfile. Not part
of the shipped end-user package.

**Performance Goals**: From invoking the script to an interactive shell in under 5 minutes
on a typical connection (SC-001), dominated by the base-image pull (first run) and pip
install inside `install.py`.

**Constraints**: The Docker build context MUST be the staging dir (release contents only),
never the repo root, so `.env`/`.venv`/inventory never enter the image (Principle V). Clean
baseline before install (FR-003, SC-002); fresh download each run (FR-004); interactive TTY
for the installer's hidden-input prompts (FR-006); default removal on exit with opt-in
`--keep` (FR-010); actionable preflight/download failures (FR-007, FR-008).

**Scale/Scope**: One container per run; a single release archive; small unit of work.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against Constitution v1.1.0:

- **I. Standard-Library-First & Minimal Dependencies** — PASS. Adds **no** runtime
  dependency to the analyzer. Docker/`curl`/`unzip` are maintainer *test* tools, not part
  of the shipped package; inside the container only the existing `openpyxl` /
  `python-dotenv` are installed, and only by the real installer.
- **II. Cross-Platform Parity** — PASS (with documented scope). Principle II governs the
  shipped **analyzer**, which is unchanged. The harness is a `.sh` for macOS/Linux hosts and
  validates installation on a **Linux** container; it does not run on Windows and does not
  cover macOS/Windows install paths — those remain manual. This is an accepted scope limit
  of a dev tool the maintainer explicitly requested as a shell script, not a regression of
  the tool's own parity.
- **III. CLI-First, Scriptable Interface** — PASS. The harness is a single scriptable
  command with flags (`--keep`, `--local`, `--help`), meaningful exit codes (non-zero on
  preflight/download failure; `130` on interrupt), and actionable error messages. It also
  leans on the installer's / launcher's existing flag-driven modes (`--inventory`,
  `--output-dir`, `--dry-run`).
- **IV. Conservative & Traceable Analysis (NON-NEGOTIABLE)** — PASS (N/A). No analysis logic
  is touched; the harness only exercises `install.py`/`run.py`.
- **V. Secrets Hygiene & Data Locality** — PASS (reinforced). Build context excludes the
  repo, so the maintainer's `.env`, `.venv`, and inventory never enter the image. The FueliX
  key is typed into the **ephemeral** container and destroyed on exit; the bind-mounted
  share is an empty maintainer-controlled folder, not the repo. The harness sends nothing
  anywhere — the only outbound traffic is GitHub (release download) on the host and PyPI via
  the installer, both pre-existing behaviors of "download the release and run install.py",
  and neither expands the **analyzer's** contacted endpoints (`sec.cloudapps.cisco.com`,
  `api.fuelix.ai`).
- **Branching Strategy** — PASS. Work is on `002-docker-install-test`, to be merged to
  `main` via PR.

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/002-docker-install-test/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── cli.md           # test-install.sh CLI + container runtime contract
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created here)
```

### Source Code (repository root)

The project is a flat single-project CLI. This feature adds a self-contained maintainer
tool in its own folder and touches nothing in the analyzer's source:

```text
tools/
└── install-test/
    ├── test-install.sh   # NEW: the one command the maintainer runs (preflight → download →
    │                     #      stage → build → interactive shell → cleanup / --keep)
    ├── Dockerfile        # NEW: FROM python:3.9-slim; WORKDIR app; COPY staged release; CMD bash
    └── README.md         # NEW: short usage note (mirrors contracts/cli.md)

.gitignore               # UPDATED: ignore the harness's local share/staging artifacts if
                         #          created in-repo (e.g. tools/install-test/share/)
README.md                # UPDATED (optional task): "For maintainers" note pointing at the harness

# Unchanged: analyzer.py, cisco.py, inventory.py, fuelix.py, report.py, install.py, run.py, ui.py
# Unchanged: tests/ (pytest unit tests — distinct from this Docker harness)
```

**Structure Decision**: Isolate the harness under `tools/install-test/` so it is clearly
maintainer tooling and never confused with the shipped package or the `tests/` unit suite.
The Dockerfile lives beside the script but is built against the **staging temp dir** as its
context (`docker build -f tools/install-test/Dockerfile <staging>`), guaranteeing repo
secrets stay out of the image. No analyzer source changes are required.

## Complexity Tracking

> No constitutional violations. Section intentionally empty.
