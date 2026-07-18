# Feature Specification: Self-Update Mechanism (Auto-Updater)

**Feature Branch**: `003-auto-updater`

**Created**: 2026-07-17

**Status**: Draft

**Input**: BRD-001 (`brds/001-auto-updater.md`) — "Turn the auto-updater BRD into a spec: a one-command self-updater that fetches the latest published release, replaces the application files in place, preserves the user's configuration/data/environment, and makes the installed version knowable so the tool can check whether an update is warranted."

## Clarifications

### Session 2026-07-17

- Q: How should the downloaded release package be verified before it replaces any files? → A: Publish a SHA-256 checksum with each release; the updater verifies the hash before applying (in addition to HTTPS and a well-formed-archive / expected-version check).
- Q: Is automating the release packaging (version + checksum) in scope for this feature, or left to maintainers? → A: In scope — an automated release pipeline (triggered on a version tag) builds the package with version = tag, generates the SHA-256 checksum, and attaches both to the GitHub release.
- Q: How are installed vs. latest versions compared to decide whether an update is available? → A: Semantic-version comparison — parse into numeric components and compare numerically (e.g. 1.10.0 > 1.9.0), yielding up-to-date, update-available (latest > installed), or ahead (installed > latest).
- Q: How does a user revert an update? → A: A dedicated rollback command restores the most recent backup in one step; additionally the updater automatically self-reverts if an apply fails part-way.
- Q: How often does the passive update-notice check run, and is it stateful? → A: At most once per analyzer run, stateless (no persisted last-check timestamp), short timeout, best-effort; disable via a flag or environment variable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Update to the latest version, keeping my data (Priority: P1)

An analyst who already has the tool installed runs a single update command from the tool's folder. The tool figures out what version is installed, checks the latest published release, and — if a newer one exists — shows the change, asks for confirmation, downloads and verifies the new release, and replaces the application files in place. Throughout, the analyst's API key, firewall inventory, generated reports, and installed environment are left untouched. When it finishes, the tool is immediately usable and reports the new version.

**Why this priority**: This is the core value of the feature and the whole reason it exists — a safe, one-step path to the latest version that never risks the user's credentials or data. It is the minimum viable product: on its own it eliminates the error-prone manual re-download-and-copy process.

**Independent Test**: On an install pinned to an older version with a populated `.env`, an inventory file, and prior reports, run the update command and confirm. Verify the application files now match the latest release, the tool runs, and `.env`, `inventory/`, `output/`, and `.venv/` are unchanged.

**Acceptance Scenarios**:

1. **Given** an install on an older version with a populated `.env`, an inventory file, and prior reports, **When** the user runs the update command and confirms, **Then** the application files are updated to the latest release and `.env`, `inventory/` contents, `output/` contents, and `.venv/` are byte-for-byte unchanged.
2. **Given** the latest release changed the required dependencies, **When** the update completes, **Then** the analyzer runs successfully without the user performing a separate dependency-install step.
3. **Given** the download is interrupted or fails verification, **When** the update runs, **Then** no application files are modified and the previous install remains fully usable.
4. **Given** a newer release exists, **When** the user is shown the `current → new` change and declines confirmation, **Then** no files are modified.

---

### User Story 2 - Check my version and whether an update exists (Priority: P2)

A cautious analyst or a support agent wants to know exactly which version is installed and whether a newer one is available — without changing anything. They run a check (or a version request) and see the installed version and, if reachable, the latest available version and whether an update is available.

**Why this priority**: Version awareness is foundational — it answers "which version are you on?" for support and lets users decide when to update. It is valuable on its own even before anyone updates, and it underpins the up-to-date short-circuit in Story 1.

**Independent Test**: On any install, run the version/check command and confirm it prints the installed version; with network available and a newer release published, confirm it reports that an update is available and names the newer version, while making zero file changes.

**Acceptance Scenarios**:

1. **Given** any install, **When** the user requests the version, **Then** the tool prints the installed version, matching the release it was distributed as.
2. **Given** a newer release exists and the network is reachable, **When** the user runs the check, **Then** the tool reports that an update is available and names the newer version, and modifies no files.
3. **Given** the install is already on the latest version, **When** the user runs the update or check, **Then** the tool reports "already up to date" and makes no changes.
4. **Given** the release source is unreachable, **When** the user runs the check, **Then** the tool still reports the installed version and clearly states that the latest version could not be determined.

---

### User Story 3 - Recover from a failed or unwanted update (Priority: P3)

An analyst whose update went wrong — or who simply wants to go back — restores the previous version. Because the updater kept a backup of the files it replaced, the prior version can be brought back with the user's data still intact. And if an update is interrupted, the install is never left as a broken half-and-half mixture.

**Why this priority**: A safety net that makes updating low-risk. It is lower priority than performing the update itself but materially increases trust and adoption, especially for a security tool run on operators' machines.

**Independent Test**: Apply an update, then run the rollback command; confirm the prior application files are restored and `.env`, inventory, and reports remain intact. Separately, interrupt an update partway and confirm the install is either fully old or fully new — never mixed.

**Acceptance Scenarios**:

1. **Given** an update was applied and a backup exists, **When** the user runs the rollback command, **Then** the prior application files are restored from the most recent backup and user data (`.env`, `inventory/`, `output/`) remains intact.
2. **Given** an apply errors part-way, **When** the failure occurs, **Then** the tool automatically restores the previous version, leaving the install fully on the old version.
3. **Given** an update is hard-interrupted (e.g., power loss), **When** the user inspects the install afterward, **Then** it is either fully on the old version or fully on the new version — never a broken mixture — and the rollback command can restore the prior version.

---

### User Story 4 - Be nudged when an update is available (Priority: P4)

An analyst using the tool normally is told, unobtrusively, when a newer release exists — without any interruption to the task at hand. During a normal run, the tool does a best-effort, non-blocking check and, if a newer version is out, prints a brief notice naming it and the update command.

**Why this priority**: A convenience that keeps installs current by surfacing updates passively. It is the lowest priority because the update and check capabilities already let motivated users stay current; this only reduces the chance of silently running stale logic.

**Independent Test**: With a newer release published, run the analyzer normally and confirm a short update notice appears while the analysis still completes. With the network disabled, confirm the run completes with no error, delay, or notice.

**Acceptance Scenarios**:

1. **Given** a newer release exists, **When** the user runs the analyzer, **Then** a short notice about the available update (with the new version and the update command) is shown and the analysis still completes normally.
2. **Given** the update check cannot reach the network, **When** the user runs the analyzer, **Then** no error or noticeable delay is imposed and the analysis completes normally with no notice.

---

### Edge Cases

- **Already latest**: The updater makes no changes and reports "up to date."
- **Release source unreachable / rate-limited**: The command reports the condition with an actionable message, changes nothing, and still reports the installed version; the passive nudge silently does nothing.
- **Corporate proxy required**: The tool honors the environment's configured proxy; if the download is still blocked, it gives an actionable error and changes nothing.
- **Corrupt or incomplete download**: Verification fails before any file is touched; the install is unchanged.
- **Interrupted mid-update** (cancellation, crash, power loss): The install ends fully old or fully new; a backup is available for recovery.
- **Updater's own files change in the new release**: The update still completes safely even though the running updater is among the files being replaced.
- **Missing or unreadable installed-version identifier** (e.g., an install predating this feature): The tool treats the version as unknown/older, still functions, and offers to update.
- **Requirements unchanged between versions**: The update skips the dependency-refresh step.
- **Preserve-list path absent** (e.g., no inventory placed yet): The update proceeds without error and does not create spurious data.
- **Local version newer than the latest release** (e.g., a development copy): The tool reports it is ahead / no update needed and changes nothing.
- **Insufficient disk space during backup or extraction**: The update aborts safely before replacing files; the install is unchanged.
- **Run from the wrong directory** (not the tool's folder): The tool detects this and gives an actionable error rather than modifying unrelated files.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST provide a single command, runnable from the tool's folder, that updates the installation to the latest published release.
- **FR-002**: The update MUST preserve the user's local data and configuration without modification or deletion — specifically the `.env` file, all contents of the `inventory/` folder, all contents of the `output/` folder, and the `.venv/` environment (the "preserve-list").
- **FR-003**: The tool MUST record its installed version as a single authoritative, human-readable identifier that matches the release it was distributed as, and MUST be able to report it.
- **FR-004**: The tool MUST determine the latest available version from the official release source and compare it against the installed version using semantic-version ordering (numeric, component-wise — e.g. `1.10.0` > `1.9.0`), before applying any update. The comparison MUST yield exactly one of: up to date (equal), update available (latest > installed), or ahead (installed > latest).
- **FR-005**: When the installed version is already the latest, the tool MUST make no changes and MUST report that the installation is up to date.
- **FR-006**: The tool MUST fully download the release package over HTTPS and verify its integrity before modifying any installed file: it MUST confirm the download matches the SHA-256 checksum published with the release, and that the archive is well-formed and contains the expected version identifier. If any check fails, the tool MUST make no changes and leave the existing install fully usable.
- **FR-007**: After a successful update, the tool MUST leave the installation ready to run, refreshing dependencies when the release's requirements have changed, so the analyzer runs without a separate manual install step.
- **FR-008**: The tool MUST provide a check-only mode that reports the installed and latest versions and whether an update is available, without modifying any files.
- **FR-009**: Before applying an update, the tool MUST show the current and target versions and require user confirmation, and MUST provide a non-interactive option to skip the prompt for scripted use.
- **FR-010**: Users MUST be able to read the installed version through the tool's existing run entry point (e.g., a version flag), not only through the updater.
- **FR-011**: Before replacing any files, the tool MUST create a recoverable backup of the files it will replace, and MUST provide a dedicated command that restores the most recent backup — reverting to the prior version in one step — with user data intact.
- **FR-012**: The update MUST keep the installation in a consistent state — fully on the previous version or fully on the new version, never a partial mixture. If applying the update errors part-way, the tool MUST automatically restore the previous version from the backup. If the process is hard-interrupted (e.g., power loss) or the updater's own files are among those being replaced, the install MUST remain recoverable so a subsequent run or the rollback command (FR-011) can restore a consistent state.
- **FR-013**: The tool MUST behave consistently on Windows, macOS, and Linux, using the tool's existing entry points and self-contained environment, without requiring the user to manually activate that environment.
- **FR-014**: The tool MUST retrieve updates only from the official repository's releases over a secure (HTTPS) channel, and MUST honor the environment's configured network proxy.
- **FR-015**: The tool MUST degrade gracefully when the release source is unreachable or rate-limited: it MUST report the condition with an actionable message and MUST NOT leave the install in a broken state.
- **FR-016**: During a normal analyzer run, the tool SHOULD perform a best-effort, non-blocking check for a newer release at most once per run (stateless — no persisted last-check timestamp), using a short timeout, and, if a newer release exists, display a brief notice naming the new version and how to update. This check MUST NOT block, delay, or fail the run when the network is unavailable or rate-limited, and MUST be possible to disable via a flag or environment variable.
- **FR-017**: The tool MUST never transmit, expose, log, or overwrite the user's API key or `.env` during any update or check.
- **FR-018**: Command output MUST be actionable on failure (state what failed and how to fix it), and the command MUST use meaningful exit codes (non-zero on failure; the tool's interrupt convention on cancellation).
- **FR-019**: The update MUST apply all application files contained in the release package except the preserve-list, so that files added or removed between versions are handled without a manual step.
- **FR-020**: Each published release package MUST carry a recorded version identifier equal to its release tag, and each release MUST publish a SHA-256 checksum of the package, so that the tool can make accurate version comparisons and verify package integrity before applying.
- **FR-021**: The release process MUST be automated so that publishing a release (via a version tag) builds the release package with its recorded version equal to the tag, generates the package's SHA-256 checksum, and attaches both to the published release — with no manual packaging step, so version and checksum never drift from the tag.

### Key Entities *(include if feature involves data)*

- **Installed Version**: The authoritative identifier of the version currently installed locally; read by the updater, the check mode, and the run entry point; matches the release the install came from.
- **Latest Release**: The most recent published release as reported by the official release source, comprising a version identifier and a downloadable release package.
- **Release Package**: The distributable archive for a release. Contains the application files needed to run the tool plus the recorded version identifier; excludes user/local data and development-only artifacts. Each release also publishes a SHA-256 checksum of this package for integrity verification.
- **Preserve-list**: The set of user/local paths an update must never modify or delete: `.env`, `inventory/`, `output/`, `.venv/`.
- **Backup**: A recoverable snapshot of the files replaced by an update, enabling a revert to the prior version.
- **Update Check Result**: The semantic-version comparison outcome between installed and latest versions — up to date (equal), update available (latest > installed, with the target version), ahead (installed > latest), or latest-unknown (source unreachable).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user on an older version reaches the latest version with a single command and no manual file copying, typically in under two minutes on a normal connection.
- **SC-002**: 100% of updates preserve `.env`, `inventory/`, `output/`, and `.venv/` with zero data loss.
- **SC-003**: Running the updater when already current results in zero file changes and a clear "up to date" message.
- **SC-004**: A failed download or failed verification leaves the previous install fully intact and usable in 100% of cases (no partial or broken state).
- **SC-005**: The version reported by an installed copy matches the release it came from for 100% of published releases (no version drift).
- **SC-006**: The update completes with no OS-specific manual steps on Windows, macOS, and Linux.
- **SC-007**: After an update that changes dependencies, the analyzer runs successfully without the user performing a separate install step.
- **SC-008**: A user or support agent can determine the installed version, and whether an update is available, in a single command that completes in under 10 seconds when the network is reachable.
- **SC-009**: After an unwanted update, a user can revert to the prior version and resume work with their data intact.

## Assumptions

- Distribution remains GitHub Releases; the latest version is discoverable from the official release source and the release package is reachable at the `/releases/latest/download/cisco-advisory-impact-analyzer.zip` URL.
- Releases are tagged with sortable, semantic-style versions (e.g., `1.1.0`), matching current practice.
- Users run the updater from within the unzipped tool folder (an existing install).
- Users have network access to GitHub, subject to their corporate proxy.
- User/local data (`.env`, `inventory/`, `output/`, `.venv/`) is not part of the released package and is therefore never shipped inside an update.
- The base Python used to install the tool is available for running the updater; the updater does not rely on a working `.venv` or extra installed packages (so it can recover a broken environment) — consistent with the existing installer.
- For v1, only updating to the latest release is supported; pinning to or downgrading to an arbitrary historical version is not offered.
- An update applies all files in the release package except the preserve-list.
- The released package contains the runtime files needed to run the tool (application code, `requirements.txt`, README, landing page, and the version identifier) and excludes development-only artifacts (e.g., `tests/`, `specs/`, `.specify/`) and user data.
- Package verification means the download matches the SHA-256 checksum published with the release, the archive is well-formed, and it contains the expected version identifier.
- Backups are stored within the tool folder; at minimum the most recently replaced set is retained to enable rollback.
- The passive update notice is best-effort and stateless — checked at most once per analyzer run, with a short timeout and no persisted state — and can be disabled via a flag or environment variable.

## Dependencies

- **Input (external)**: The official GitHub release source — the latest version identifier and the downloadable release package. Note: contacting GitHub (`github.com` / `api.github.com`) is a new external endpoint relative to the current tool, which only contacts Cisco and FueliX; per the project constitution this is a reviewed change.
- **Input**: An authoritative version identifier carried inside each release package (see FR-003/FR-020).
- **Handoff (publisher process, in scope)**: An automated release pipeline packages each release with a version identifier equal to its tag and a SHA-256 checksum, and attaches both to the published GitHub release, so the version and checksum never drift from the tag (FR-021).
- **Related**: The public landing page (`docs/index.html`) already surfaces the latest release version from the same source; the updater's notion of "latest" should remain consistent with it.

## Out of Scope

- Unattended or background auto-apply of updates (updates are user-initiated; only the passive notice is automatic).
- Migrating or transforming user data (e.g., inventory format changes) between versions.
- Alternative distribution channels (pip/PyPI, OS package managers, packaged executables/installers).
- Updating the Python interpreter or other system-level prerequisites.
- Creating or publishing GitHub releases from the *runtime tool* (an analyst running the updater never creates releases). Note: automated packaging of a release's versioned artifact and checksum, triggered when a maintainer publishes a tagged release, IS in scope (FR-021).
- Rollback to arbitrary historical versions beyond the most recent backup (last known good).
