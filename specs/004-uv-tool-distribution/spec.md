# Feature Specification: uv Tool Distribution

**Feature Branch**: `004-uv-tool-distribution`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "Make this app distributed via uv. Users install with `uv tool install cisco-advisory-impact-analyzer --from git+https://github.com/xavient/cisco-advisory-impact-analyzer`, then run a single `cisco-advisory-impact-analyzer` command (with `--help`, `--version`, `--update`, `--config` flags) from any folder."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install and run an analysis from any folder (Priority: P1)

An operator installs the tool once with a single `uv tool install ... --from git+<repo>` command. The tool and its dependencies land on their PATH. From then on they can `cd` into any working folder that holds their firewall inventory, type `cisco-advisory-impact-analyzer`, and be guided through an interactive analysis whose report is written next to where they are working — without ever cloning the repository, creating a virtual environment, or activating one.

**Why this priority**: This is the entire point of the feature. If a user cannot install with the documented command and run an analysis from an arbitrary folder, nothing else matters. It replaces the current clone + `install.py` + `run.py` onboarding with a single install command and a single run command.

**Independent Test**: On a clean machine with `uv` present, run the documented install command, then from a fresh folder containing a valid inventory file run `cisco-advisory-impact-analyzer` with a configured API key and a valid ERP URL, and confirm a report appears in an `output/` folder inside that same working folder.

**Acceptance Scenarios**:

1. **Given** a machine with `uv` installed and no prior copy of this tool, **When** the user runs `uv tool install cisco-advisory-impact-analyzer --from git+https://github.com/xavient/cisco-advisory-impact-analyzer`, **Then** the command installs the tool and all of its runtime dependencies and exposes a `cisco-advisory-impact-analyzer` command on the user's PATH.
2. **Given** the tool is installed and an API key is configured, **When** the user runs `cisco-advisory-impact-analyzer` from a folder containing exactly one valid inventory file and provides a valid ERP URL and confirms, **Then** the analysis runs and a timestamped report is written to an `output/` folder inside that working folder (created if absent).
3. **Given** an analysis is in progress or the tool is waiting at any prompt, **When** the user presses Ctrl+C, **Then** the tool stops promptly without a traceback and leaves no partial report behind.

---

### User Story 2 - Configure credentials once, use everywhere (Priority: P1)

Because the tool now runs from any folder rather than from a checkout that holds a `.env` file, the operator needs a way to store their FueliX credentials once so every future run in any folder can find them. Running `cisco-advisory-impact-analyzer --config` lets them set their API key (and model / base URL), stored in a per-user location that persists across runs and folders.

**Why this priority**: Without persistent, folder-independent configuration the P1 run flow cannot find an API key, so this is equally foundational. The tool must refuse to analyze without a key and point the user to `--config`.

**Independent Test**: Run `--config` and set an API key, then from a completely different folder run the tool and confirm it proceeds past the credential check without re-prompting for the key.

**Acceptance Scenarios**:

1. **Given** no credentials are configured, **When** the user runs `cisco-advisory-impact-analyzer --config`, **Then** they are prompted for a FueliX API key, can also set the model and base URL, and the values are saved to a per-user location.
2. **Given** an API key is already configured, **When** the user runs `--config` again, **Then** they can view/keep the existing key or replace it, and the model and base URL retain their existing values unless changed.
3. **Given** no API key is configured, **When** the user runs `cisco-advisory-impact-analyzer` (the analysis flow), **Then** the tool stops with a clear, actionable error telling them to run `cisco-advisory-impact-analyzer --config`, and exits non-zero.
4. **Given** an API key is configured, **When** the user runs the analysis flow, **Then** the credential check passes silently and the flow continues.

---

### User Story 3 - Discover, and stay on, the latest version (Priority: P2)

Operators need to know what version they are on and whether a newer one exists, and to update without remembering `uv` syntax. `--version` prints the installed version and tells them if a newer one is published; `--update` performs the upgrade; and a normal run offers to update first if a newer version is available.

**Why this priority**: The tool is a security utility whose correctness improves over time; keeping operators current matters, but a stale version still analyzes correctly, so this ranks below the core install/run/config flows.

**Independent Test**: With a newer version published than the one installed, run `--version` and confirm it reports the newer version is available and points to `--update`; run `--update` and confirm the tool upgrades and reports success; run `--update` again and confirm it reports the latest is already installed.

**Acceptance Scenarios**:

1. **Given** the tool is installed, **When** the user runs `cisco-advisory-impact-analyzer --version`, **Then** it prints the installed version, checks whether a newer version is published, and — if one is — tells the user a newer version is available and to update via `--update`.
2. **Given** a newer version is published, **When** the user runs `cisco-advisory-impact-analyzer --update`, **Then** the tool downloads and installs the newer version and notifies the user that the update succeeded.
3. **Given** no newer version is published, **When** the user runs `--update`, **Then** the tool prints the current version and notifies the user that the latest version is already installed.
4. **Given** a newer version is published, **When** the user starts a normal analysis run, **Then** the tool asks "A new version is available. Do you want to update now? [y/N]" before proceeding; answering no continues with the current version, and answering yes performs the update via `uv` and then exits, instructing the user to re-run the command (the run does not continue on the old code).

---

### User Story 4 - Guided inventory selection (Priority: P2)

When a user runs the analysis from a folder, the tool locates the inventory to analyze. If it cannot find a single valid inventory file, it lists the files in the folder and lets the user pick one, validating the selection and re-prompting on an invalid pick, so the user is never left guessing what file to place where.

**Why this priority**: This improves the run experience and removes a common failure mode, but the core analysis (US1) can function once a valid inventory is present; the guided picker is a usability enhancement on top of that.

**Independent Test**: Run the tool from a folder with no valid inventory and confirm it lists candidate files and lets you select one; select an invalid file and confirm it explains the problem and lets you choose again; select a valid file and confirm the analysis proceeds.

**Acceptance Scenarios**:

1. **Given** the working folder contains no recognizable inventory file, **When** the analysis flow reaches inventory discovery, **Then** the tool lists the files in the folder and prompts the user to select one.
2. **Given** the user selects a file that is not a valid inventory, **When** validation runs, **Then** the tool tells the user the file is not a valid inventory and lets them select another.
3. **Given** the user selects a file that is a valid inventory, **When** validation passes, **Then** the tool proceeds to the URL prompt.

---

### User Story 5 - Confirm before analyzing (Priority: P3)

Before spending time and making network/AI calls, the tool prompts the operator for the Cisco Event Response URL, validates it, and asks for an explicit confirmation that states the URL will be analyzed and that results will be saved to an `output/` folder in the current folder, so the operator always understands what is about to happen and where output will land.

**Why this priority**: A guardrail and clarity improvement; the analysis can technically run without a separate confirmation step, so it is the lowest priority of the interactive refinements.

**Independent Test**: Run the flow to the URL prompt, enter an invalid URL and confirm re-prompting, enter a valid URL, and confirm the tool shows a "results will be saved in output/ in this folder — Continue [y/N]?" prompt whose "no" answer aborts cleanly.

**Acceptance Scenarios**:

1. **Given** the credential and inventory checks passed, **When** the flow reaches the URL step, **Then** the user is prompted to enter the Cisco Event Response URL.
2. **Given** the user enters an invalid URL, **When** validation runs, **Then** the tool notifies the user it is invalid and prompts again.
3. **Given** the user enters a valid URL, **When** validation passes, **Then** the tool asks the user to confirm that the URL will be analyzed and the results saved to `output/` in the current folder, and only proceeds on "yes".
4. **Given** the analysis completes, **When** the report is written, **Then** the tool shows the same per-advisory summary it shows today and exits.

---

### Edge Cases

- **`uv` not installed / install command fails**: Installation is out of the tool's control; documentation must state `uv` is a prerequisite. The tool itself only runs after a successful install.
- **Offline or GitHub unreachable during version/update checks**: Version and update checks MUST be best-effort and MUST NOT block or fail a normal analysis run; the automatic run-start check is bounded to roughly 2 seconds, and if it cannot complete within that bound the run proceeds silently on the current version.
- **`--update` cannot complete** (network failure, permission issue, `uv` unavailable at runtime): The tool MUST report the failure with an actionable message and leave the currently installed version working.
- **Working folder contains multiple valid inventory files**: The tool MUST NOT silently pick one; it MUST let the user choose (or apply the existing "exactly one" rule) so the analyzed inventory is unambiguous.
- **Working folder is not writable** (cannot create `output/`): The tool MUST fail with a clear message rather than losing the report.
- **User presses Ctrl+C at any prompt or mid-analysis**: MUST exit cleanly with the interrupt exit code and no traceback.
- **Configured API key is present but invalid/rejected by FueliX**: Surfaced as an actionable error during analysis (existing behavior), not as a config-time guarantee.
- **A local per-folder configuration file also exists**: Precedence between a per-user configuration and any per-folder configuration/environment variables must be well defined (see Assumptions).

## Clarifications

### Session 2026-07-18

- Q: When a newer version is available and the user answers "yes" to the update prompt at the start of a run, what should the tool do? → A: Perform the update via uv and then exit, instructing the user to re-run the command (do not continue the current run on partially updated or old code).
- Q: What should bound the best-effort version/update check so it can never hang a normal run? → A: Cap the check at roughly 2 seconds; if it does not complete within that bound, silently skip it and proceed on the current version.
- Q: How should the interactive flow behave when analysis flags (e.g. `--url`, `--inventory`, `--output-dir`, `--dry-run`) are supplied? → A: Each supplied flag skips its corresponding prompt (including the update-offer and confirmation prompts), enabling fully non-interactive runs; this is promoted to a functional requirement.

## Requirements *(mandatory)*

### Functional Requirements

#### Distribution & installation

- **FR-001**: The product MUST be installable as a uv tool via `uv tool install cisco-advisory-impact-analyzer --from git+https://github.com/xavient/cisco-advisory-impact-analyzer`, installing the tool and all of its runtime dependencies.
- **FR-002**: Installation MUST expose a single executable command named `cisco-advisory-impact-analyzer` on the user's PATH.
- **FR-003**: The installed tool MUST run correctly from any working folder, independent of where the package is installed, with no manual virtual-environment creation or activation by the user.
- **FR-004**: The product MUST continue to run on macOS, Windows, and Linux with equivalent behavior.

#### Command surface

- **FR-005**: `--help` MUST list every available flag with a short description of each.
- **FR-006**: `--version` MUST print the installed version, then perform a best-effort, time-bounded (roughly 2 seconds) check of whether a newer version is published and, if so, tell the user a newer version is available and to update via `--update`. If the check does not complete within that bound, `--version` MUST still report the installed version without erroring.
- **FR-007**: `--update` MUST check whether a newer version is published; if so it MUST download and install it and notify the user of success; if not it MUST print the current version and notify the user that the latest version is already installed.
- **FR-008**: `--config` MUST let the user set the FueliX API key by prompting for and accepting a string value.
- **FR-009**: `--config` MUST let the user set the FueliX model by choosing from a curated list of known-good models presented as a selectable menu, with `claude-sonnet-5` as the default selection. The list membership is maintained in the product and kept current with the models FueliX exposes; if an already-configured model is not in the list it MUST still be shown as the current value and be keepable.
- **FR-010**: `--config` MUST NOT interactively prompt for the FueliX base URL. The base URL defaults to the current FueliX endpoint and MUST be overridable only via an environment variable or by editing the stored configuration file directly, since it rarely changes.
- **FR-011**: Configuration set via `--config` MUST persist in a per-user location that is readable by later runs from any working folder.

#### Interactive analysis run (no flags)

- **FR-012**: Running the command with no flags MUST start the interactive analysis flow and MUST be cancellable at any point via Ctrl+C, exiting cleanly (exit code 130) without a traceback.
- **FR-013**: At the start of a run, the tool MUST perform a best-effort check for a newer version; if one is available it MUST prompt "Do you want to update now? [y/N]". If the user answers yes, the tool MUST perform the update via `uv` and then exit, instructing the user to re-run the command; it MUST NOT continue the current run on the old code. If the user answers no, the run continues on the current version. This check MUST be time-bounded to roughly 2 seconds; if it does not complete within that bound (e.g., the release channel is slow or unreachable) it MUST be skipped silently and the run MUST proceed on the current version. This check MUST NOT block or fail the run if it cannot complete.
- **FR-014**: The tool MUST verify a FueliX API key is configured; if present it proceeds, and if absent it MUST stop with an actionable error instructing the user to run `--config`, and exit non-zero.
- **FR-015**: The tool MUST look for a valid inventory file in the current working folder; if it does not find one, it MUST list the files in the folder and let the user select one.
- **FR-016**: When the user selects an inventory file, the tool MUST validate it against the required inventory structure; on failure it MUST tell the user the file is not a valid inventory and let them select another; on success it MUST proceed.
- **FR-017**: Once inventory and API key are available, the tool MUST prompt the user to enter the Cisco Event Response URL.
- **FR-018**: The tool MUST validate the entered URL; on an invalid URL it MUST notify the user and prompt again; on a valid URL it MUST proceed.
- **FR-019**: Before running the analysis, the tool MUST ask the user to confirm ("Continue [y/N]?") a message stating that the URL will be analyzed and the results saved to an `output/` folder in the current folder; it MUST proceed only on an affirmative answer.
- **FR-020**: The tool MUST run the existing analysis logic and write the report to an `output/` folder inside the current working folder, creating that folder if it does not exist.
- **FR-021**: After writing the report, the tool MUST display the same per-advisory summary shown by the current tool, then exit.

#### Non-interactive / flag-driven analysis

- **FR-025**: The analysis flow MUST remain fully flag-driven for automation, consistent with the CLI-first principle. When an analysis input is supplied as a flag (at minimum `--url`, `--inventory`, `--output-dir`, and `--dry-run`), the tool MUST skip the corresponding interactive prompt and use the supplied value; supplying the inputs needed to run MUST also skip the update-offer and the final "Continue [y/N]?" confirmation prompts, so a fully-specified invocation runs end-to-end without any interactive input. The API-key requirement (FR-014) and inventory/URL validation (FR-016, FR-018) still apply, failing with the same actionable, non-zero errors instead of re-prompting when running non-interactively.

#### Compatibility & non-regression

- **FR-022**: The analysis behavior (advisory discovery, CSAF extraction, inventory matching, conservative/traceable determinations, and report contents) MUST remain unchanged from the current tool; this feature changes packaging, configuration, and the interactive entry flow, not the analysis itself.
- **FR-023**: Version and update checks MUST NOT transmit inventory data or secrets; they may contact only the release-hosting service used to discover and fetch new versions.
- **FR-024**: uv distribution MUST fully replace the previous distribution mechanism. The git-clone + `install.py` + `run.py` + in-repo self-updater (`update.py` / `updater.py`) entry points MUST be retired, and the `README.md`, `docs/index.html`, and the constitution (which currently requires setup/execution through `install.py` / `run.py` and the in-repo `.venv`) MUST be updated so the uv install/run/update flow is the single documented path.

### Key Entities *(include if feature involves data)*

- **Installed tool**: The on-PATH `cisco-advisory-impact-analyzer` command produced by the uv installation, carrying an installed version identifier.
- **User configuration**: Persistent, per-user settings — FueliX API key (secret), model, and base URL — stored outside any working folder so all runs can read them.
- **Working folder**: The user's current directory at run time; source of the inventory file and parent of the `output/` folder where reports are written.
- **Inventory file**: A user-provided spreadsheet in the working folder that must conform to the required structure (the firewall list) to be accepted for analysis.
- **Published version / release**: A version made available in the project's release channel that the tool compares against the installed version to detect updates.
- **Report**: The timestamped analysis output written into the working folder's `output/` directory.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can go from a clean machine (with `uv` available) to a completed analysis report using exactly two commands they type — the install command and the run command — plus one `--config` step, with no repository clone and no manual virtual-environment steps.
- **SC-002**: 100% of runs started without a configured API key stop with a message that names `--config` as the fix and do not attempt analysis.
- **SC-003**: A report produced by the uv-installed tool is written into the working folder's `output/` directory in 100% of successful runs, and its contents match what the current tool produces for the same inputs.
- **SC-004**: `--version` correctly reflects update availability — reporting "newer available" when a newer version exists and nothing to update when on the latest — in 100% of checks where the release channel is reachable.
- **SC-005**: When the network or release channel is unreachable, a normal analysis run still completes (version/update check is skipped silently) in 100% of cases where inputs are otherwise valid.
- **SC-006**: Pressing Ctrl+C at any prompt or during analysis exits without a traceback in 100% of cases.
- **SC-007**: The tool runs with equivalent behavior on macOS, Windows, and Linux (verified on all three).
- **SC-008**: The automatic run-start version check never delays the run by more than ~2 seconds; in 100% of runs where the release channel is slow or unreachable, the check is abandoned within that bound and the run proceeds on the current version.
- **SC-009**: An invocation that supplies all required analysis inputs as flags completes end-to-end with zero interactive prompts in 100% of otherwise-valid runs.

## Assumptions

- **`uv` is a prerequisite**: Users have `uv` installed and available on PATH; installing `uv` itself is out of scope and covered only by documentation.
- **Distribution replaces the old flow**: uv becomes the sole supported distribution and run mechanism; the previous `install.py` / `run.py` / in-repo self-updater and clone-based instructions are retired, with the README, `docs/index.html`, and constitution updated to match (see FR-024). This is a breaking change for anyone on the old clone-based flow, who must reinstall via uv.
- **Model list is curated in-product**: The selectable model list for `--config` (FR-009) is maintained in the product; keeping it current with FueliX's available models is an ongoing maintenance item, and an unknown/previously-set model is preserved rather than discarded.
- **Base URL is advanced-only**: The FueliX base URL is not part of the interactive `--config` flow (FR-010); it stays at its default unless overridden via environment variable or a direct edit of the stored configuration file.
- **Per-user configuration location**: Configuration is stored in a standard per-user location appropriate to each OS, kept out of version control, and with the API key protected by owner-only permissions where the OS supports it. Environment variables (`FUELIX_API_KEY`, `FUELIX_MODEL`, `FUELIX_BASE_URL`) remain honored for automation.
- **Configuration precedence**: When both environment variables and stored per-user configuration are present, environment variables take precedence (consistent with the current app), followed by the stored per-user configuration.
- **"Published version" source**: New versions are discovered from the project's GitHub releases (the mechanism the current updater already uses), and installation/upgrade is performed through `uv` from the git source.
- **`--update` mechanism**: Updating is performed by invoking `uv` to reinstall/upgrade the tool from the git source at the newer version; the tool orchestrates this rather than overlaying files in place as the current in-repo updater does.
- **Inventory validation**: "Valid inventory" means the file conforms to the existing required structure (an `.xlsx` with the expected firewall-list sheet and columns); validation reuses the current inventory-parsing rules.
- **Output location**: Reports are written to `output/` relative to the current working folder (not relative to where the package is installed), matching the user's mental model of "results appear where I ran the command."
- **Package naming**: The distributed package and command name is `cisco-advisory-impact-analyzer`, matching the repository name and the documented install command.
- **Non-interactive/automation use**: Fully flag-driven analysis (e.g. providing the URL and inventory path as flags, and a dry-run mode) remains available for scripting and testing, consistent with the project's CLI-first principle, even though the primary documented experience is interactive. Supplied flags skip their corresponding prompts as well as the update-offer and confirmation prompts (see FR-025).

## Dependencies

- Requires `uv` on the end user's machine for installation, running, and updating.
- Requires reachable GitHub release endpoints for version discovery and updates (best-effort; not required for a normal analysis run).
- Requires reachable Cisco (`sec.cloudapps.cisco.com`) and FueliX (`api.fuelix.ai`) endpoints for the analysis itself, unchanged from today.
