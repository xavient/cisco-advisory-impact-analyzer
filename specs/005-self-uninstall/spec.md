# Feature Specification: Self-Uninstall Command

**Feature Branch**: `005-self-uninstall`

**Created**: 2026-07-19

**Status**: Draft

**Input**: BRD-002 (`brds/002-uninstall.md`). Add a `caia --uninstall` command that removes the uv-installed tool (and its `caia` command) the same way it was installed, after a confirmation prompt (with a `--yes` flag to skip it for scripted use), preserves the per-user configuration (FueliX API key + model) by default while reporting its on-disk location so nothing is silently destroyed, never touches user work products (reports/inventory/CSAF), gracefully handles non-uv (source-checkout) installs and a missing uv, and uses a simple zero/non-zero exit status.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Remove the tool in one command, keeping my saved settings (Priority: P1)

An analyst who installed the tool via `uv` and no longer needs it runs `caia --uninstall`. The tool asks them to confirm, then removes itself and its `caia` command the same way it was installed. It preserves their saved FueliX API key and model, and on success tells them exactly where that saved configuration still lives and how to delete it if they want to — so nothing is destroyed by surprise.

**Why this priority**: This is the core of the feature and the whole reason it exists — a single, memorable, safe removal command that completes the install → update → uninstall lifecycle. Shipping only this story already delivers the primary value; every other story refines the edges around it.

**Independent Test**: On a machine with the tool uv-installed and a saved API key, run `caia --uninstall`, confirm at the prompt, and verify the `caia` command is gone, the tool's environment is removed, the configuration file is untouched, and the success message names the configuration's on-disk location.

**Acceptance Scenarios**:

1. **Given** a tool installed via `uv` with a saved API key and model, **When** the user runs `caia --uninstall` and confirms, **Then** the tool and its `caia` command are removed and the per-user configuration file is left byte-for-byte unchanged.
2. **Given** the removal succeeds, **When** it completes, **Then** the tool reports the on-disk location of the preserved configuration and states how to remove it manually, and exits with a success (zero) status.
3. **Given** the user is shown the confirmation prompt, **When** they decline (the default), **Then** nothing is removed, the tool exits with a non-success status, and the installation remains fully usable.
4. **Given** generated reports, an inventory file, and downloaded advisory files exist in the user's working folders, **When** the uninstall completes, **Then** none of those files are modified or deleted.

---

### User Story 2 - Remove the tool without a prompt, for scripts or fleet cleanup (Priority: P2)

A team lead or an automation script removes the tool across one or many machines by running `caia --uninstall` with a skip-confirmation option (e.g. `--yes`). No prompt appears, the tool is removed, and the outcome is signalled through the process exit status so the script can react.

**Why this priority**: Enables scripted and fleet-wide cleanup, which is important for a team-distributed internal tool but is a refinement of the interactive P1 flow rather than a prerequisite for it.

**Independent Test**: In a non-interactive context, run `caia --uninstall --yes` against a uv-installed tool and verify no prompt is shown, the tool is removed, and the process exits zero; run the same when nothing is installed via uv and verify a non-zero exit.

**Acceptance Scenarios**:

1. **Given** the skip-confirmation option is supplied, **When** the uninstall runs, **Then** no prompt is shown and the tool is removed.
2. **Given** the uninstall succeeds, **When** the process ends, **Then** it exits zero; **Given** it does not complete removal for any reason, **When** the process ends, **Then** it exits non-zero, so automation can distinguish success from every other outcome.

---

### User Story 3 - Get a clear explanation when automatic removal isn't possible (Priority: P3)

A developer running from a source checkout, or a user whose `uv` cannot be found on PATH, runs `caia --uninstall`. Instead of a confusing failure, the tool detects the situation and gives a plain explanation — and, where applicable, the exact manual command to remove the tool — without leaving a half-removed state.

**Why this priority**: Protects against confusing failures in known edge environments and preserves trust, but only matters once the main removal flow (P1) exists.

**Independent Test**: Run `caia --uninstall` from a source/pip install and confirm it reports "nothing to uninstall" and changes nothing; simulate `uv` missing from PATH on a uv-install and confirm it prints the exact manual command and exits non-zero.

**Acceptance Scenarios**:

1. **Given** the tool is running from a source checkout or a `pip install .` (not a `uv` tool install), **When** the user runs `caia --uninstall`, **Then** the tool explains that it is not uv-installed and there is nothing to uninstall, makes no changes, and exits non-zero.
2. **Given** the tool is uv-installed but `uv` cannot be located, **When** the user runs `caia --uninstall`, **Then** the tool prints the exact manual removal command, makes no partial changes, and exits non-zero.
3. **Given** the current platform cannot delete the running command in place (e.g. the command file is locked on Windows), **When** the uninstall runs, **Then** the tool clearly instructs the user how to finish removal from a fresh session rather than reporting a misleading success.

---

### Edge Cases

- **User declines the prompt**: no changes; non-zero exit; installation still works.
- **Interrupted (Ctrl+C) at the prompt or mid-run**: the tool exits with the interrupt code (`130`) and prints no traceback, consistent with the rest of the CLI; no misleading success is reported.
- **No saved configuration exists**: on successful removal the tool reports that there was no saved configuration to preserve, rather than pointing at a non-existent file.
- **`--uninstall` combined with another mode flag** (e.g. `--update`, `--config`, `--version`): mode flags are handled in a defined precedence order and are not combined; the tool acts on a single mode per invocation.
- **`--yes` supplied but the tool is not uv-installed / `uv` missing**: the skip-confirmation flag does not force a removal that cannot happen; the same "nothing to uninstall" / "run this manually" explanation applies and the exit is non-zero.
- **Removal command reports failure** (non-zero from the package manager): the tool surfaces an actionable error, does not claim success, and does not leave the user believing the tool is gone when it is not.
- **Configuration removal is never offered in-tool**: v1 prints the location only; there is no interactive or flagged deletion of the configuration/API key.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST provide a `caia --uninstall` command that removes the installed tool and its `caia` command using the same package manager (`uv`) it was installed with.
- **FR-002**: The tool MUST ask the user to confirm before removing anything, defaulting to *not* removing.
- **FR-003**: The tool MUST provide an option (e.g. `--yes`) to skip the confirmation prompt for scripted or unattended removal.
- **FR-004**: The tool MUST preserve the user's per-user configuration (stored FueliX API key and model) during uninstall and MUST NOT delete it; v1 provides no in-tool means (interactive or flagged) to delete it.
- **FR-005**: On successful removal, the tool MUST report the on-disk location of the preserved configuration and how the user can delete it themselves; when no configuration file exists, it MUST say so instead of naming a non-existent path.
- **FR-006**: The tool MUST NOT modify or delete any user work products — generated reports (`output/`), inventory files, or downloaded advisory (CSAF) files.
- **FR-007**: The tool MUST detect when it is not installed via `uv` (e.g. a source checkout or `pip install .`) and explain that there is nothing to uninstall, making no changes.
- **FR-008**: When `uv` cannot be located, the tool MUST print the exact manual removal command and MUST NOT leave a partially-removed state.
- **FR-009**: The tool MUST exit with a zero status only on successful removal, and a non-zero status on every other outcome (nothing to remove, manual step required, declined, or error), so automation can distinguish success from all else. An interrupt (Ctrl+C) MUST exit `130` with no traceback.
- **FR-010**: The tool MUST NOT transmit, expose, log, or print the user's API key at any point during uninstall.
- **FR-011**: The tool SHOULD behave consistently across Windows, macOS, and Linux; where the running command cannot delete itself in place, it MUST instruct the user how to complete removal from a fresh session rather than reporting a misleading success.
- **FR-012**: The tool SHOULD surface the `--uninstall` command (and its `--yes` option) in its `--help` output and in user-facing documentation, alongside the install and update instructions.
- **FR-013**: When removal cannot be completed automatically or the package manager reports failure, the tool MUST present an actionable error that states what failed and the manual step to finish, consistent with the tool's existing error-messaging conventions.

### Key Entities

- **Installed tool**: the uv-managed application and the `caia` command on the user's PATH — the target of removal.
- **Per-user configuration**: the stored FueliX API key and model, kept in an OS-appropriate per-user location outside any working folder; preserved across uninstall and only ever *disclosed*, never removed by the tool.
- **User work products**: user-owned outputs and inputs — generated reports, inventory files, and downloaded advisory (CSAF) files — living in the user's working folders; never touched by uninstall.
- **Package manager (`uv`)**: the external mechanism that performs the actual removal; its presence and the install method determine whether automatic removal is possible.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can remove the tool with a single command, without needing to know the package-manager subcommand or the tool's distribution name.
- **SC-002**: 100% of successful uninstalls leave the per-user configuration file intact and report its location (or report that none existed).
- **SC-003**: 100% of uninstalls leave user work products (reports, inventory, downloaded advisory files) unchanged.
- **SC-004**: Running the command from a non-`uv` (source/pip) install results in zero changes and a clear explanation in 100% of cases.
- **SC-005**: When automatic removal cannot complete (package manager missing, or self-removal blocked by the platform), the user receives an actionable manual instruction in 100% of such cases, with no half-removed state.
- **SC-006**: Declining the confirmation prompt results in zero changes in 100% of cases.
- **SC-007**: A successful removal exits zero and every non-success outcome exits non-zero, so a script can reliably distinguish success from all other results.
- **SC-008**: The API key is never transmitted, printed, or logged during an uninstall in 100% of runs.

## Assumptions

- The tool is distributed and installed as a `uv` tool, and `uv` is the mechanism used to remove it, consistent with how install and `caia --update` already work. `--uninstall` is uv-specific and, like `--update`, does not apply to the `pip install .` source fallback (Constitution II / Technology & Data Constraints).
- The per-user configuration (API key and model) is stored outside any working folder and is not part of the installed code, so removing the tool's code does not remove it.
- On macOS and Linux the running command can be removed in place while the current invocation still completes; on Windows in-place self-removal of the running command may be blocked, mirroring the constraint already documented for `caia --update`.
- Users run `caia --uninstall` themselves; there is no unattended or background removal.
- The `caia` command name and the `cisco-advisory-impact-agent` distribution name are the current, stable identifiers used to identify what to remove.
- The tool does not track where the user placed their reports or inventory, so it does not enumerate those paths; its messaging states that work products in the user's working folders are left untouched rather than listing them.
- No in-tool configuration deletion (e.g. a `--purge` option) is in scope for v1; the user deletes the configuration file themselves using the reported path (BRD-002 §5.2, resolved during BRD review).
