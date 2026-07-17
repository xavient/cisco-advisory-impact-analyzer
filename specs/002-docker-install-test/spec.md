# Feature Specification: Dockerized End-to-End Installation Test

**Feature Branch**: `002-docker-install-test`

**Created**: 2026-07-16

**Status**: Draft

**Input**: User description: "build a test script to test the whole installation. End users download the package from https://github.com/xavient/cisco-advisory-impact-analyzer/releases/latest/download/cisco-advisory-impact-analyzer.zip. I want to have a script that I can run with which we will build a fresh new envionment on docker that I can test the installation on. This can be a `.sh` file. that I run, build the container, and login to it with the files copied, so from there I will just do `python3 install.py` and test it out end to end."

## Clarifications

### Session 2026-07-16

- Q: Which Python + base OS should the fresh environment provide? → A: `python:3.9-slim` — pin the minimum supported Python (3.9) on a Debian-based image with pip/venv ready, to catch 3.9-specific compatibility regressions that a newer Python would hide.
- Q: How does the maintainer get their own inventory file in for a full analyzer run without polluting the clean baseline? → A: Bind-mount an empty host folder as a drop-zone (and use it to capture `output/`); it is empty at launch so the clean-baseline guarantee holds, and the maintainer copies their `.xlsx` in after landing in the shell.
- Q: What controls whether the throwaway environment is kept or removed after a test (e.g. to inspect a failed install)? → A: Default to remove on exit (including interruption); provide an opt-in `--keep` flag set at launch to preserve the environment for inspection.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fresh environment with an interactive shell for the installer (Priority: P1)

A maintainer wants to confirm that the shipped installer works on a machine that has
never seen this tool before. They run one script from the project on their own machine.
The script prepares a brand-new, throwaway environment that contains the release package
and nothing else the tool created, then drops the maintainer into an interactive command
prompt inside that environment, positioned in the package folder. From there the
maintainer types `python3 install.py` and works through the installer exactly as a real
end user would — answering its prompts, watching each step, and confirming it finishes
with "Setup complete."

**Why this priority**: This is the entire point of the feature — a reproducible way to
exercise the real installer by hand in a clean environment. Without the interactive shell
in a fresh environment, there is nothing to test.

**Independent Test**: Run the script on a machine with the container tooling available and
confirm it ends at an interactive shell inside the environment, in the package folder,
where running `python3 install.py` starts the installer and its prompts respond to typed
input.

**Acceptance Scenarios**:

1. **Given** the container tooling is available and the maintainer runs the script,
   **When** the script finishes preparing the environment, **Then** the maintainer is left
   at an interactive shell running inside that environment, in the folder that holds the
   release package.
2. **Given** the maintainer is at that shell, **When** they run `python3 install.py`,
   **Then** the installer runs and its interactive prompts (for example the FueliX API key
   and the model) accept typed input and respond as they would on a real end-user machine.
3. **Given** the installer has finished, **When** the maintainer inspects the environment,
   **Then** the virtual environment, dependencies, and `.env` file that the installer just
   created are present and usable for a follow-up run of the analyzer.

---

### User Story 2 - Environment mirrors a clean end-user machine using the published package (Priority: P2)

The maintainer wants the test to reflect what real users actually download and run, not
the maintainer's own working copy with its already-built `.venv`, `.env`, cached
dependencies, or leftover inventory files. The prepared environment starts from a clean
operating system that has only a supported Python available, and the package under test is
the published release archive that end users download — obtained fresh for the test — so
the maintainer is validating the artifact that ships, not local development state.

**Why this priority**: A test that accidentally reuses the maintainer's local environment
would pass even when the shipped package is broken. Fidelity to the real end-user starting
point is what makes the result trustworthy, so it ranks just below having a runnable test
at all.

**Independent Test**: Prepare the environment, then inspect the package folder before
running the installer and confirm there is no pre-existing virtual environment, no `.env`,
no installed project dependencies, and no inventory file — only the contents of the
downloaded release package plus a clean Python.

**Acceptance Scenarios**:

1. **Given** the maintainer runs the script, **When** the environment is prepared,
   **Then** the package placed in it is the published release archive fetched for this test
   (not a copy of the maintainer's local working tree).
2. **Given** the prepared environment before the installer runs, **When** the maintainer
   inspects it, **Then** it contains no virtual environment, no `.env`, no pre-installed
   project dependencies, and no inventory file.
3. **Given** the environment, **When** the maintainer checks the available Python,
   **Then** a Python version supported by the tool (3.9 or newer) is present so
   `python3 install.py` can run.

---

### User Story 3 - Repeatable and self-cleaning tests (Priority: P3)

The maintainer expects to run this test many times — after each release or fix — without
the machine slowly filling up with leftover environments and without one test run
contaminating the next. Every run starts from the same pristine baseline, and finishing a
run leaves the maintainer's machine as it was before.

**Why this priority**: This makes the tool safe to use routinely. It is valuable but not
required to get a single useful test result, so it is the lowest of the three.

**Independent Test**: Run the script, exit the shell, run it again, and confirm the second
run starts from the same clean baseline as the first and that no test environments remain
on the host after exiting.

**Acceptance Scenarios**:

1. **Given** a completed test run, **When** the maintainer exits the interactive shell,
   **Then** the throwaway environment is removed and does not persist on the host.
2. **Given** a prior test run has completed, **When** the maintainer runs the script again,
   **Then** the new environment starts from the same clean baseline, unaffected by the
   previous run.

---

### Edge Cases

- **Container tooling missing or not running**: The script stops immediately with a clear
  message telling the maintainer that the container runtime is required and is not
  available, rather than failing partway with an obscure error.
- **Release archive cannot be downloaded** (no published release yet, network/proxy block,
  or the URL returns an error): The script stops with an actionable message identifying the
  download as the cause, instead of dropping the maintainer into an empty environment.
- **No internet access inside the environment**: `install.py` needs to install
  dependencies from the network; when that is unavailable the installer's own error path
  should surface, and the test correctly reflects that a networkless machine cannot
  complete installation.
- **Host processor architecture differs from the package's expectations** (for example
  Apple Silicon vs. x86): The environment still provides a working Python and the installer
  runs; any architecture-specific behavior is observed as part of the test rather than
  masked.
- **Maintainer wants a full analyzer run, not just installation**: After installation the
  maintainer needs their own API key (entered at the installer prompt) and an inventory
  file inside the environment to exercise the analyzer end to end; they supply the file by
  dropping it into the empty host folder bind-mounted into the environment (FR-011), and
  generated reports appear back in that folder on the host.
- **Maintainer exits the shell abnormally** (Ctrl+C, closing the terminal): The throwaway
  environment should still be cleaned up rather than lingering.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The test MUST be startable by running a single script file from the project
  on the maintainer's machine, with no manual multi-step setup beyond that one command.
- **FR-002**: The script MUST prepare a fresh, isolated, throwaway environment for each run
  that is independent of the maintainer's host machine and of any previous run.
- **FR-003**: The prepared environment MUST start from a clean operating system baseline
  that provides the **minimum supported Python (3.9)** on a Debian-based image (equivalent
  to `python:3.9-slim`, with `pip` and `venv` available) and MUST NOT contain a pre-existing
  virtual environment, `.env` file, installed project dependencies, or inventory file.
  Pinning the minimum supported version is deliberate — it surfaces 3.9-specific
  compatibility regressions that a newer Python would hide.
- **FR-004**: By default the package under test MUST be the published release archive that
  end users download (the "latest release" package), obtained fresh for each run, so the
  test validates the shipped artifact rather than local development state.
- **FR-005**: The contents of the release package MUST be placed into a working folder
  inside the environment, and the maintainer MUST be left at an interactive shell whose
  starting location is that folder.
- **FR-006**: The interactive shell MUST support running `python3 install.py` and MUST
  allow the installer's interactive prompts to accept typed input, matching how the
  installer behaves on a real end-user machine.
- **FR-007**: The script MUST detect when the required container tooling is missing or not
  running and MUST stop with an actionable message instead of proceeding.
- **FR-008**: The script MUST detect when the release package cannot be obtained and MUST
  stop with an actionable message that identifies the download as the cause.
- **FR-009**: The test MUST be repeatable: running the script again MUST reproduce the same
  clean baseline without residue from earlier runs affecting the outcome.
- **FR-010**: On exit — including normal exit and interruption — the throwaway environment
  MUST by default be removed so repeated runs do not accumulate leftover environments on
  the host. The script MUST also offer an opt-in `--keep` flag, set at launch, that
  preserves the environment after exit so the maintainer can inspect a failed or
  interesting installation; when `--keep` is used the script MUST print how to re-enter and
  later remove that environment.
- **FR-011**: The environment MUST allow the maintainer to bring in their own inventory
  file so that, after installation, a full analyzer run can also be exercised end to end
  (not only the installer). This MUST be done via a host folder bind-mounted into the
  environment that is **empty at launch** (preserving the clean-baseline guarantee of
  FR-003 and SC-002); the maintainer copies their `.xlsx` into it after reaching the shell.
  The same mounted folder MUST also expose the generated `output/` reports back on the host
  so results can be inspected after the environment is gone.
- **FR-012**: The script SHOULD allow the maintainer to test a locally built package
  instead of the published release, to support validating a release candidate before it is
  published. *(Optional convenience; the default remains the published release per
  FR-004.)*

### Key Entities *(include if feature involves data)*

- **Test environment**: The fresh, isolated, disposable workspace created for one test run.
  It provides a clean operating system with a supported Python and holds the package under
  test. It has no persistence between runs.
- **Release package**: The archive end users download from the project's latest release. It
  contains the installer and all program files needed to install and run the analyzer. It
  is the subject of the test.
- **Test launcher script**: The single script the maintainer runs on their host. It
  prepares the environment, obtains and unpacks the release package into it, and hands the
  maintainer an interactive shell in the package folder.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Starting from the project on their machine, a maintainer can go from running
  one command to an interactive shell inside the fresh environment in under 5 minutes on a
  typical connection, without any manual steps in between.
- **SC-002**: In 100% of runs, the environment presented to the maintainer contains none of
  the maintainer's local install state (no virtual environment, no `.env`, no installed
  project dependencies, no inventory) before the installer is run.
- **SC-003**: Running `python3 install.py` inside the environment completes all installer
  steps and reports "Setup complete" when given valid inputs, confirming the shipped
  package installs end to end.
- **SC-004**: The full test can be repeated at least 10 consecutive times with each run
  beginning from an identical clean baseline and no failures caused by leftover state.
- **SC-005**: After a maintainer exits the shell in the default mode (i.e. when they have
  not opted to preserve the environment for inspection), zero test environments created by
  the script remain on the host.
- **SC-006**: When the container tooling is unavailable or the release cannot be
  downloaded, the maintainer receives a clear, actionable message identifying the cause in
  100% of such cases, and is never dropped into an empty or broken environment.

## Assumptions

- The test environment is delivered as a container (Docker), and the launcher is a `.sh`
  shell script, as explicitly requested by the maintainer. This is the intended delivery
  mechanism, not an incidental choice.
- The maintainer runs the script on a machine (macOS, Linux, or a compatible shell
  environment) that has a working container runtime installed and running.
- "The whole installation" primarily means running `install.py` interactively to
  completion; exercising the analyzer (`run.py`) afterward is a supported follow-on that
  requires the maintainer to supply their own FueliX API key and an inventory file.
- The default package under test is the published latest release; validating an unpublished
  release candidate from a local build is a secondary, optional path (FR-012).
- The environment has outbound internet access so the installer can download its
  dependencies and the maintainer can reach the release URL; a networkless environment is
  expected to fail installation and that failure is a valid test result, not a defect in
  this feature.
- Per the project constitution, this feature is developed on its own branch off `main` and
  merged via pull request; the test tooling itself does not send secrets or inventory data
  anywhere and keeps all test data local to the throwaway environment.
