# Business Requirements Document (BRD): Self-Update Mechanism (Auto-Updater)

## Document Control

| Field             | Value                                                        |
| ----------------- | ------------------------------------------------------------ |
| BRD ID            | BRD-001                                                      |
| Title             | Self-Update Mechanism (Auto-Updater)                        |
| Author            | Ali Bahaloo / TELUS Digital                                 |
| Status            | Draft                                                        |
| Version           | 0.1.0                                                        |
| Created           | 2026-07-17                                                   |
| Last updated      | 2026-07-17                                                   |
| Related documents | Repo: https://github.com/xavient/cisco-advisory-impact-analyzer · Latest release asset: https://github.com/xavient/cisco-advisory-impact-analyzer/releases/latest/download/cisco-advisory-impact-analyzer.zip · Constitution: `.specify/memory/constitution.md` · Landing page version pill: `docs/index.html` |

## 1. Executive Summary

The Cisco Advisory Impact Analyzer is distributed as a downloadable ZIP with no built-in way to update. Today, staying current means manually re-downloading the ZIP and copying files over an existing install — an error-prone process that risks overwriting the user's API key, inventory, and generated reports. This BRD defines a one-command self-updater that fetches the latest published release, replaces the application files in place, and preserves the user's configuration, data, and environment — together with the version awareness the tool needs to know whether an update is warranted.

## 2. Business Context & Problem Statement

The tool ships as loose Python files inside a ZIP from GitHub Releases. Users unzip it, run an installer that creates a private environment (`.venv`), stores their FueliX API key in `.env`, and keeps their firewall inventory in `inventory/` and generated reports in `output/`. All of that user/local data lives *inside the same folder* as the application code.

Consequences today:

- **No safe update path.** To get a newer version, a user must re-download and manually merge files. A careless copy overwrites `.env` (their API key) or clobbers `inventory/` and `output/` — causing lost credentials or data.
- **No version awareness.** The application does not record which version is installed. A user cannot tell what they are running, and the tool cannot detect that a newer release exists. (The public landing page already reads the *latest* release tag from GitHub, but the installed copy knows nothing about itself.)
- **Stale installs.** Advisory-matching logic and Cisco data-format handling improve between releases. Users who never update silently run outdated analysis, undermining trust in results.
- **Support burden.** "Which version are you on?" cannot be answered, and update mishaps generate avoidable support requests.

The cost is measured in lost time (manual updates), risk (credential/data loss, silently outdated results), and support overhead.

## 3. Business Objectives & Goals

- **G1** — Let any user update to the latest release with a single, safe command run from the tool's folder.
- **G2** — Guarantee that user configuration and data (API key, inventory, generated reports, installed environment) survive every update untouched.
- **G3** — Make the installed version knowable to both the user and the tool, and comparable against the latest published release.
- **G4** — Keep installs current so advisory analysis reflects the newest logic, without forcing users through a manual re-install.
- **G5** — Work reliably across Windows, macOS, and Linux and within corporate/proxied networks, consistent with the existing installer and launcher.

## 4. Stakeholders & Users

| Stakeholder / user | Role in this product | What they need from it |
| ------------------ | -------------------- | ---------------------- |
| Security / network analyst running the tool | Primary user | Update in one step without losing their API key, inventory, or reports; confidence they are running the latest logic |
| Team lead / tool champion | Primary / rollout owner | A repeatable, low-risk update everyone on the team can perform unaided |
| Maintainers (this repo) | Publisher | A release process where the published package's version always matches the release tag, so update checks are trustworthy |
| Support / help desk | Indirect | Ability to ask and confirm which version a user runs; fewer update-related incidents |
| IT / security review | Reviewer | Assurance that updates come from the official source over a trusted channel and never expose secrets |

## 5. Scope

### 5.1 In Scope

- A command-line updater, run from the tool's folder, that fetches the latest published release and replaces the application files in place.
- Version awareness: an authoritative record of the installed version, and a way for both the user and the tool to read it.
- Determining the latest available version from the official GitHub release source and comparing it to the installed version.
- Preserving all user/local data across an update: `.env`, the contents of `inventory/` and `output/`, and the `.venv/` environment.
- Restoring a fully working installation after update, including refreshing dependencies when the requirements have changed.
- A check-only mode that reports current vs. latest without modifying anything.
- A recoverable backup of replaced files so a failed or unwanted update can be reverted.
- Keeping the published release package's recorded version in sync with the release tag so update checks never mislead.

### 5.2 Out of Scope

- **Unattended / background auto-apply.** Updates are user-initiated by running the command. (A passive "update available" notice is the only automatic behavior — see Journey 4.)
- **Migrating or transforming user data** (e.g., inventory format changes) between versions — that responsibility, if ever needed, belongs to the analyzer itself.
- **Alternative distribution channels** — pip/PyPI, OS package managers, or packaged executables/installers.
- **Updating the Python interpreter** or other system-level prerequisites.
- **Creating GitHub releases** through the tool — maintainers publish releases; this product only consumes them (and, per BR-15, keeps the package version in sync at publish time).
- **Rollback to arbitrary historical versions** — only reverting the most recent update (last known good) is supported.

## 6. User Journeys *(feeds the spec's prioritized user stories)*

### Journey 1 — Update to the latest version, keeping my data (Priority: P1)

- **Actor:** Analyst with an existing install of an older version.
- **Trigger:** They run the update command from the tool's folder.
- **Outcome / value:** Their installation is upgraded to the latest release, their API key, inventory, reports, and environment are untouched, and the tool is immediately usable.
- **Flow:**
  1. From the tool's folder, the user runs the update command.
  2. The tool reads its installed version and looks up the latest published release.
  3. If a newer version exists, it shows `current → new` and asks for confirmation.
  4. On confirmation, it downloads the latest release package and verifies it is complete before changing anything.
  5. It replaces the application files, skipping the user's `.env`, `inventory/`, `output/`, and `.venv/`.
  6. If dependencies changed, it refreshes them into the existing environment.
  7. It reports success and the new installed version.
- **Acceptance:**
  - **Given** an install on an older version with a populated `.env`, inventory, and prior reports, **When** the user runs the update and confirms, **Then** the application files are updated to the latest release and `.env`, `inventory/`, `output/`, and `.venv/` are byte-for-byte unchanged.
  - **Given** the requirements changed in the new release, **When** the update completes, **Then** running the analyzer works without a manual dependency step.
  - **Given** the download is interrupted or fails verification, **When** the update runs, **Then** no application files are modified and the previous install remains fully usable.

### Journey 2 — Check my version and whether an update exists (Priority: P2)

- **Actor:** Cautious analyst or support agent.
- **Trigger:** They want to know what they are running and whether they are current — without changing anything.
- **Outcome / value:** They see the installed version and whether a newer one is available, and can decide when to update.
- **Flow:**
  1. The user runs the tool with a version/check request.
  2. The tool prints the installed version.
  3. It looks up the latest release and reports whether the install is current or an update is available (and which version).
- **Acceptance:**
  - **Given** any install, **When** the user requests the version, **Then** the tool prints the installed version that matches the published release it came from.
  - **Given** a newer release exists, **When** the user runs the check, **Then** the tool reports that an update is available and names the newer version, without modifying any files.
  - **Given** the install is already on the latest version, **When** the user runs the update, **Then** the tool reports "already up to date" and makes no changes.

### Journey 3 — Recover from a failed or unwanted update (Priority: P3)

- **Actor:** Analyst whose update went wrong, or who wants to revert.
- **Trigger:** An update failed midway, or the new version behaves unexpectedly.
- **Outcome / value:** The previous working installation is restored, with data intact.
- **Flow:**
  1. The updater has kept a backup of the files it replaced.
  2. The user restores the previous version from that backup.
  3. The tool runs again as before, with `.env`, inventory, and reports intact.
- **Acceptance:**
  - **Given** an update was applied, **When** the user chooses to revert, **Then** the prior application files are restored and user data remains intact.
  - **Given** an update aborted partway due to an error, **When** the user inspects the install, **Then** it is either fully on the old version or fully on the new version — never a broken mixture.

### Journey 4 — Be nudged when an update is available (Priority: P4)

- **Actor:** Analyst using the tool normally.
- **Trigger:** They run the analyzer while a newer release exists.
- **Outcome / value:** They learn that an update is available and how to get it, without any interruption to their current task.
- **Flow:**
  1. During a normal run, the tool checks (best-effort, non-blocking) whether a newer release exists.
  2. If so, it prints a brief notice naming the new version and the update command.
  3. The current task proceeds unaffected regardless of the check's result.
- **Acceptance:**
  - **Given** a newer release exists, **When** the user runs the analyzer, **Then** a short notice about the available update is shown and the analysis still completes normally.
  - **Given** the update check cannot reach the network, **When** the user runs the analyzer, **Then** no error or delay is imposed and the analysis completes normally.

## 7. Business Requirements

| ID    | Requirement                                                                                                                                                   | Priority |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| BR-01 | The product MUST provide a single command, run from the tool's folder, that updates the installation to the latest published release.                          | P1       |
| BR-02 | The product MUST preserve all user/local data across an update — specifically `.env`, the contents of `inventory/` and `output/`, and the `.venv/` — never modifying or deleting them. | P1       |
| BR-03 | The product MUST record the installed version in a single authoritative, human-readable identifier that matches the release it was distributed as.             | P1       |
| BR-04 | The product MUST determine the latest available version from the official GitHub release source before applying an update.                                     | P1       |
| BR-05 | The product MUST make no changes when the install is already on the latest version, and MUST report that it is up to date.                                     | P1       |
| BR-06 | The product MUST verify the downloaded package is complete and valid before replacing any files, and MUST leave the existing install untouched if verification fails. | P1       |
| BR-07 | The product MUST leave the installation fully working after an update, including refreshing dependencies when the requirements have changed.                   | P1       |
| BR-08 | The product SHOULD offer a check-only mode that reports installed vs. latest version without modifying anything.                                               | P2       |
| BR-09 | The product SHOULD show the current and target versions and require user confirmation before applying an update, with an option to skip the prompt for scripted use. | P2       |
| BR-10 | The product SHOULD let the user read the installed version through the existing run command.                                                                   | P2       |
| BR-11 | The product SHOULD keep a recoverable backup of the files it replaces so a failed or unwanted update can be reverted.                                          | P3       |
| BR-12 | The product SHOULD operate correctly on Windows, macOS, and Linux, consistent with the existing installer and launcher.                                        | P3       |
| BR-13 | The product SHOULD function through corporate network proxies, consistent with how the tool already reaches external services.                                 | P3       |
| BR-14 | The product SHOULD passively notify the user when a newer version is available during normal use, without blocking, delaying, or failing the current task.     | P4       |
| BR-15 | The product SHOULD ensure that each published release package carries a recorded version identical to its release tag, so update checks are always accurate.    | P2       |

## 8. Success Metrics & Measurable Outcomes

- **SC-01** — A user on an older version can reach the latest version with a single command and no manual file copying, in a typical time under two minutes on a normal connection.
- **SC-02** — 100% of updates preserve `.env`, `inventory/`, `output/`, and `.venv/` with zero data loss.
- **SC-03** — Running the updater when already current results in zero file changes.
- **SC-04** — A failed download or failed verification leaves the previous install fully intact and usable in 100% of cases (no partial/broken state).
- **SC-05** — The version reported by an installed copy matches the release it came from for 100% of published releases (no version drift).
- **SC-06** — The update completes without OS-specific manual steps on Windows, macOS, and Linux.
- **SC-07** — After an update that changes dependencies, the analyzer runs successfully without the user performing a separate install step.

## 9. Assumptions

- Distribution remains GitHub Releases, with the release asset reachable at the `/releases/latest/download/cisco-advisory-impact-analyzer.zip` URL and the latest version discoverable from the official GitHub release source.
- Releases are tagged with sortable, semantic-style versions (e.g., `1.1.0`), matching current practice.
- Users run the updater from within the unzipped tool folder (an existing install).
- Users have network access to GitHub (subject to their corporate proxy).
- User/local data (`.env`, `inventory/`, `output/`, `.venv/`) is not part of the released package and therefore is never shipped inside an update.
- The base Python used to install the tool is available for running the updater.

## 10. Constraints

- The updater must run without a working `.venv` and without extra installed packages, so it can recover an install even when dependencies are broken or changed — consistent with how the existing installer runs.
- The updater must uphold the tool's secret-handling posture: it must never transmit, expose, or overwrite the user's `.env`/API key.
- Behavior must be consistent across Windows, macOS, and Linux, matching the existing installer and launcher.
- Updates must originate only from the official repository's releases and be retrieved over a trusted (HTTPS) channel.
- The solution must tolerate the public GitHub API's unauthenticated rate limits and degrade gracefully when they are hit.

## 11. Dependencies

- **Input** — The official GitHub release source: the latest version identifier and the downloadable release package.
- **Input** — An authoritative version identifier carried inside each release package (see BR-03/BR-15).
- **Output / handoff** — The publisher's release process, which must package each release with a version equal to its tag; this may require automating release packaging.
- **Related** — The public landing page (`docs/index.html`) already surfaces the latest release version from the same source; the updater's notion of "latest" should stay consistent with it.

## 12. Risks & Mitigations

| Risk                                                                 | Impact | Likelihood | Mitigation |
| ------------------------------------------------------------------- | ------ | ---------- | ---------- |
| A partial or corrupt update leaves the install broken                | H      | M          | Download and verify fully before replacing anything; apply atomically; keep a backup for rollback (BR-06, BR-11) |
| User data (`.env`, inventory, reports) overwritten during update     | H      | M          | Explicit preserve-list; user data never included in the package; verify data untouched (BR-02) |
| Version drift between the release tag, the package, and what the tool reports | M | M      | Package each release with a version equal to its tag, ideally automatically (BR-15) |
| GitHub API rate-limited or unreachable                               | M      | M          | Graceful fallback and clear messaging; passive nudge fails silently; download by `/latest/download` still works (BR-13, BR-14) |
| Corporate proxy blocks the download                                  | M      | M          | Honor the environment's proxy settings; give a clear, actionable error (BR-13) |
| The updater replaces itself mid-run and corrupts the process         | M      | L          | Design the update sequence so it completes safely even when its own files are among those replaced |
| Tampered or unofficial package is applied                            | H      | L          | Restrict source to the official repo over HTTPS; verify package integrity before applying (BR-06) |

## 13. Open Questions

- Should the update replace *all* application files in the package (including the updater and installer themselves), or only the analyzer's core code? (Leaning: replace everything except the preserve-list.)
- Is a non-interactive / assume-yes mode required for scripted or fleet-wide updates, or is interactive-only sufficient?
- Should users be able to update to (or pin) a specific version, or is "latest only" acceptable for v1?
- For this internal tool, is HTTPS transport integrity sufficient, or is an explicit package checksum/signature required?
- For the passive update nudge, should it be opt-out, and how frequently should it check?
- Where should backups be stored, and how many prior versions should be retained?
- Should development-only artifacts (`tests/`, `specs/`, `.specify/`) be part of the released package, since that determines what an update replaces?

## 14. Glossary

| Term          | Definition |
| ------------- | ---------- |
| ERP           | Cisco Event Response Page — the advisory-bundle URL the analyzer is pointed at. |
| CSAF          | Common Security Advisory Framework — the machine-readable advisory data the tool downloads. |
| FueliX        | The AI service the analyzer calls; its API key is stored in `.env`. |
| Inventory     | The user's firewall list (an `.xlsx` in `inventory/`) that advisories are matched against. |
| `.venv`       | The private Python environment the installer creates inside the tool folder. |
| Release asset | The downloadable `cisco-advisory-impact-analyzer.zip` attached to a GitHub release. |
| Tag           | The version label on a GitHub release (e.g., `1.1.0`). |
| Preserve-list | The set of user/local paths an update must never modify: `.env`, `inventory/`, `output/`, `.venv/`. |
| VERSION identifier | The authoritative record of the installed version, matching the release it came from. |
| Latest release | The most recent published release, as reported by the official GitHub release source. |
