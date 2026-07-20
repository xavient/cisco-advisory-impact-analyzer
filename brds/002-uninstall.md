# Business Requirements Document (BRD): Self-Uninstall Command

## Document Control

| Field             | Value                                                        |
| ----------------- | ------------------------------------------------------------ |
| BRD ID            | BRD-002                                                      |
| Title             | Self-Uninstall Command                                       |
| Author            | Ali Bahaloo / TELUS Digital                                 |
| Status            | Draft                                                        |
| Version           | 0.1.0                                                        |
| Created           | 2026-07-19                                                   |
| Last updated      | 2026-07-19                                                   |
| Related documents | Repo: https://github.com/xavient/cisco-advisory-impact-analyzer · BRD-001 (Self-Update Mechanism): `brds/001-auto-updater.md` · Constitution: `.specify/memory/constitution.md` |

## 1. Executive Summary

The Cisco Advisory Impact Agent installs as the `caia` command via `uv tool install`, and it can already update itself in place with `caia --update`. It has no matching way to remove itself: users must recall and type the exact `uv` incantation and the tool's full distribution name, which few remember. This BRD defines a single command — `caia --uninstall` — that removes the tool the same way it was installed, confirms before doing so, and clearly tells the user where their saved API key still lives so it is never silently destroyed. It is the natural twin of the existing self-updater.

## 2. Business Context & Problem Statement

The tool is distributed as a `uv` tool. Installing places the `caia` command on the user's PATH and its code in an isolated, uv-managed environment; `caia --update` reinstalls the latest release through the same mechanism. Separately, the tool stores the user's FueliX API key and model choice in a per-user configuration directory that lives **outside** the installed code.

Consequences today:

- **No discoverable removal path.** To uninstall, a user must know the underlying package manager, the exact distribution name (`cisco-advisory-impact-agent`, which differs from the `caia` command they actually type), and the correct subcommand. This is friction at exactly the moment a user has decided to stop using the tool, and it generates support questions.
- **Inconsistent lifecycle.** The tool offers first-class install and update experiences but drops the user at the end of that lifecycle, breaking the "one simple command" expectation the rest of the CLI sets.
- **Orphaned secret risk.** Because the API key lives outside the installed code, any removal — whether via the package manager or a future built-in command — leaves the key on disk. A user who believes they have "removed the tool" may not realize a credential remains, which is both a security and a trust concern.
- **Uncertain outcome for evaluators.** Analysts and teams evaluating the tool need a clean, confident way to back it out. Absent one, trialling the tool feels higher-commitment than it is.

The cost is measured in friction and support load at removal time, and in the risk of a credential silently left behind after a user believes the tool is gone.

## 3. Business Objectives & Goals

- **G1** — Let any user remove the tool with a single, memorable command consistent with how they installed and updated it.
- **G2** — Never destroy the user's stored credential without their knowledge: preserve the per-user configuration by default and tell the user exactly where it remains.
- **G3** — Make removal safe and predictable — a clear confirmation before acting, and an honest, actionable message when removal cannot be completed automatically.
- **G4** — Complete the tool's lifecycle so install, update, and uninstall feel like one coherent experience.
- **G5** — Behave sensibly across Windows, macOS, and Linux, consistent with the existing installer and updater.

## 4. Stakeholders & Users

| Stakeholder / user | Role in this product | What they need from it |
| ------------------ | -------------------- | ---------------------- |
| Security / network analyst running the tool | Primary user | Remove the tool in one step, without hunting for package-manager commands, and know what (if anything) is left behind |
| Team lead / tool champion | Rollout owner | A repeatable, low-risk way for the whole team to back the tool out |
| Analyst / team evaluating the tool | Trial user | Confidence that a trial can be cleanly reversed, lowering the barrier to trying it |
| IT / security review | Reviewer | Assurance that removal does not silently strip files it should not, and that any residual secret is disclosed to the user |
| Support / help desk | Indirect | Fewer "how do I remove this?" requests; a single command to point users to |

## 5. Scope

### 5.1 In Scope

- A command-line option, `caia --uninstall`, that removes the installed tool the same way it was installed (via `uv`), including the `caia` command on PATH and the tool's managed environment.
- A confirmation prompt before any removal, with an option to skip the prompt for scripted/unattended use.
- Preserving the per-user configuration (the stored FueliX API key and model) by default, and clearly reporting its on-disk location so the user can remove it themselves if they wish.
- Graceful, informative handling when removal cannot proceed automatically — specifically when the tool is not installed via `uv` (e.g., run from a source checkout) or when `uv` cannot be located — including the exact manual command to run instead.
- Consistent behavior and messaging across Windows, macOS, and Linux, acknowledging the platform limitation on self-removal (see Risks / Open Questions).

### 5.2 Out of Scope

- **Deleting the user's configuration / API key by any means.** Removal always preserves it and tells the user where it lives; v1 provides no in-tool way to delete it (no purge option). The user deletes the file themselves using the reported path.
- **Deleting user work products** — generated reports (`output/`), firewall inventory files, or downloaded advisory (CSAF) files. These live in the user's own working folders and are the user's to keep or delete.
- **Uninstalling the package manager itself** (`uv`) or any other system-level prerequisite (e.g., the Python interpreter).
- **Removing installs that were not created through `uv`** — for these, the command explains the situation rather than attempting removal.
- **Guaranteeing flawless self-removal on every platform** — where the running command cannot delete itself in place, the command falls back to instructing the user (see Risks).

## 6. User Journeys *(feeds the spec's prioritized user stories)*

### Journey 1 — Remove the tool in one command, keeping my saved settings (Priority: P1)

- **Actor:** Analyst with the tool installed via `uv` who no longer needs it.
- **Trigger:** They run `caia --uninstall`.
- **Outcome / value:** The tool and its `caia` command are removed; their saved API key is left intact but its location is disclosed, so nothing is destroyed by surprise.
- **Flow:**
  1. The user runs `caia --uninstall`.
  2. The tool asks the user to confirm removal, defaulting to "no."
  3. On confirmation, it removes the installed tool and the `caia` command via the same mechanism used to install it.
  4. It reports success and states where the user's saved configuration (API key and model) still resides, and how to delete it if desired.
- **Acceptance:**
  - **Given** a tool installed via `uv` with a saved API key, **When** the user runs `caia --uninstall` and confirms, **Then** the tool and its `caia` command are removed and the saved configuration file is left untouched.
  - **Given** the removal succeeds, **When** it completes, **Then** the tool reports the on-disk location of the preserved configuration and how to remove it manually.
  - **Given** the user is prompted to confirm, **When** they decline, **Then** nothing is removed and the tool exits without changes.

### Journey 2 — Remove the tool without a prompt, for scripts or fleet cleanup (Priority: P2)

- **Actor:** Team lead or automation removing the tool across machines.
- **Trigger:** They run the uninstall command with a "skip confirmation" option.
- **Outcome / value:** The tool is removed non-interactively, enabling scripted or fleet-wide cleanup.
- **Flow:**
  1. The operator runs `caia --uninstall` with the confirmation-skip option.
  2. The tool removes itself without prompting.
  3. It reports the outcome in a way a script can act on.
- **Acceptance:**
  - **Given** the confirmation-skip option is supplied, **When** the uninstall runs, **Then** no prompt is shown and the tool is removed.
  - **Given** the uninstall succeeds or fails, **When** it finishes, **Then** it signals success or failure via its exit status so automation can react.

### Journey 3 — Get a clear explanation when automatic removal isn't possible (Priority: P3)

- **Actor:** Developer running from a source checkout, or a user whose package manager isn't found on PATH.
- **Trigger:** They run `caia --uninstall` in an environment where automatic removal cannot proceed.
- **Outcome / value:** Instead of a confusing failure, they get a plain explanation and the exact manual step to take.
- **Flow:**
  1. The user runs `caia --uninstall`.
  2. The tool detects that it was not installed via `uv` (e.g., a source/editable run) or that `uv` cannot be located.
  3. It explains the situation and, where applicable, prints the exact manual command to remove the tool.
- **Acceptance:**
  - **Given** the tool is running from a source checkout (not a `uv` install), **When** the user runs `caia --uninstall`, **Then** the tool explains that there is nothing to uninstall and makes no changes.
  - **Given** the tool is `uv`-installed but `uv` cannot be located, **When** the user runs `caia --uninstall`, **Then** the tool prints the exact manual removal command and exits with a non-success status, without leaving a half-removed state.
  - **Given** removal cannot complete on the current platform because the running command cannot delete itself in place, **When** the uninstall runs, **Then** the tool clearly instructs the user how to finish removal from a fresh session.

## 7. Business Requirements

| ID    | Requirement                                                                                                                                         | Priority |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| BR-01 | The product MUST provide a single command, `caia --uninstall`, that removes the installed tool and its `caia` command using the same mechanism it was installed with. | P1       |
| BR-02 | The product MUST preserve the user's per-user configuration (stored API key and model) by default and MUST NOT delete it as part of uninstalling.    | P1       |
| BR-03 | The product MUST, on successful removal, report the on-disk location of the preserved configuration and how the user can delete it themselves.        | P1       |
| BR-04 | The product MUST ask the user to confirm before removing anything, defaulting to not removing.                                                       | P1       |
| BR-05 | The product MUST make no changes to any user work products — generated reports, inventory files, or downloaded advisory files.                        | P1       |
| BR-06 | The product MUST detect when it is not installed via the package manager (e.g., a source checkout) and explain that there is nothing to uninstall, making no changes. | P1       |
| BR-07 | The product MUST offer an option to skip the confirmation prompt (e.g., `--yes`) for scripted or unattended removal.                                  | P2       |
| BR-08 | The product MUST signal outcome through its process exit status: zero on successful removal, non-zero otherwise, so automation can react.             | P2       |
| BR-09 | The product SHOULD, when the package manager cannot be located, print the exact manual removal command and exit without leaving a partially-removed state. | P2       |
| BR-10 | The product SHOULD behave consistently across Windows, macOS, and Linux, and where the running command cannot remove itself in place, instruct the user how to complete removal from a fresh session. | P3       |
| BR-11 | The product SHOULD surface the uninstall command in its help output and documentation, alongside the install and update instructions.               | P3       |

## 8. Success Metrics & Measurable Outcomes

- **SC-01** — A user can remove the tool with a single command, without needing to know the package-manager subcommand or the tool's distribution name.
- **SC-02** — 100% of successful uninstalls leave the per-user configuration file intact and report its location.
- **SC-03** — 100% of uninstalls leave user work products (reports, inventory, downloaded advisory files) unchanged.
- **SC-04** — Running `caia --uninstall` from a non-`uv` (source) install results in zero changes and a clear explanation.
- **SC-05** — When automatic removal cannot complete (package manager missing, or self-removal blocked by the platform), the user receives an actionable manual instruction in 100% of such cases, with no half-removed state.
- **SC-06** — Declining the confirmation prompt results in zero changes in 100% of cases.
- **SC-07** — A successful removal exits zero and every non-success path (nothing to remove, manual step required, declined, error) exits non-zero, so a script can distinguish success from every other outcome.

## 9. Assumptions

- The tool is distributed and installed as a `uv` tool, and `uv` is the mechanism used to remove it, consistent with how install and `caia --update` already work.
- The per-user configuration (API key and model) is stored outside the installed code and therefore is not removed when the tool's code is removed.
- On macOS and Linux, the running command can be removed in place and the invocation still completes; on Windows, in-place self-removal of the running command may be blocked, mirroring the constraint already documented for `caia --update`.
- Users run `caia --uninstall` themselves; there is no unattended/background removal.
- The `caia` command name and the `cisco-advisory-impact-agent` distribution name are the current, stable identifiers.

## 10. Constraints

- Removal must uphold the tool's secret-handling posture: it must never transmit or expose the user's API key, and it must not silently delete it.
- Behavior and messaging must be consistent across Windows, macOS, and Linux, matching the existing installer and updater.
- The uninstall must reuse the tool's existing package-manager integration and confirmation conventions rather than introducing a divergent one, consistent with `caia --update` and `caia --config`.
- The command must not leave the installation in a partially-removed, unusable-yet-present state; where it cannot finish, it must either make no changes or clearly hand off the remaining step to the user.

## 11. Dependencies

- **Input** — The `uv` package manager, which performs the actual removal; the command depends on locating it (as `caia --update` already does).
- **Input** — The tool's stable distribution name, used to identify what to remove.
- **Related** — BRD-001 (Self-Update Mechanism): this feature is the lifecycle twin of `--update` and should reuse its package-manager discovery, confirmation, and manual-fallback patterns.
- **Related** — The per-user configuration component (API key / model storage), whose on-disk location must be reported to the user on successful removal.

## 12. Risks & Mitigations

| Risk                                                                                   | Impact | Likelihood | Mitigation |
| -------------------------------------------------------------------------------------- | ------ | ---------- | ---------- |
| The running command cannot delete itself in place (notably on Windows), leaving the command behind | M      | M          | Detect the failure and print the exact manual removal command to run from a fresh session; make no misleading "done" claim (BR-10) |
| User assumes uninstall also removed their API key, leaving a credential on disk unknowingly | M      | M          | Preserve config by default but always report its location and how to delete it on success (BR-02, BR-03) |
| User expects reports/inventory to be deleted, or fears they were | L      | M          | Explicitly leave work products untouched and state that they are preserved (BR-05) |
| The package manager (`uv`) is not on PATH, causing a confusing failure | M      | M          | Detect absence and print the exact manual command; exit with a clear status and no partial removal (BR-09) |
| Running from a source checkout produces a raw, confusing package-manager error | L      | M          | Pre-detect a non-`uv` install and explain there is nothing to uninstall, making no changes (BR-06) |
| Accidental removal via a mistyped command | M      | L          | Require confirmation defaulting to "no"; only skip it when an explicit skip option is given (BR-04, BR-07) |

## 13. Open Questions

- On successful removal, should the tool offer to delete the configuration interactively, or only print its location? (Leaning: print location only — no in-tool deletion in v1.)
- Should the uninstall attempt to detect and mention leftover user work products (reports/inventory) so the user can find them, or stay silent about paths it does not manage?

_Resolved during BRD review:_ a non-interactive skip-confirmation option (`--yes`) **is** in the v1 MVP (BR-07); the tool provides **no** in-tool config/API-key deletion in v1 — preserve-and-disclose only (Section 5.2); exit status is a **simple zero / non-zero** scheme (BR-08, SC-07).

## 14. Glossary

| Term          | Definition |
| ------------- | ---------- |
| `caia`        | The command the tool installs on the user's PATH; what users actually type. |
| `uv`          | The package manager used to install, update, and (per this BRD) remove the tool. |
| `uv` tool     | A command-line application installed by `uv` into its own managed, isolated environment with a command placed on PATH. |
| Distribution name | The tool's package identifier used by the package manager (`cisco-advisory-impact-agent`), distinct from the `caia` command name. |
| Per-user configuration | The stored FueliX API key and model choice, kept in a per-user location outside the installed code and preserved across uninstall. |
| FueliX        | The AI service the analyzer calls; its API key is stored in the per-user configuration. |
| Work products | User-owned outputs and inputs — generated reports, firewall inventory files, and downloaded advisory (CSAF) files — that the uninstall never touches. |
| Self-removal  | Removing the tool while the very command performing the removal is running; reliable on macOS/Linux, potentially blocked on Windows. |
