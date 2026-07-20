# Phase 0 Research: Self-Uninstall Command

All Technical Context items are resolved; there are no open `NEEDS CLARIFICATION` markers (the spec and `/speckit-clarify` closed the behavioral questions). This document records the design decisions that shape Phase 1.

## Decision 1 — Delegate removal to `uv` (mirror `--update`)

- **Decision**: Remove the tool by invoking `uv tool uninstall cisco-advisory-impact-agent`, reusing `version.find_uv()` to locate the `uv` executable and the same subprocess pattern as `version.perform_update()`.
- **Rationale**: Installation and update already go through `uv` (Constitution II / Technology & Data Constraints). The exact inverse of `perform_update()`'s `uv tool install ... --force` is `uv tool uninstall <dist>`. Reusing `find_uv()` (which checks PATH and uv's default install dirs) and the established error/manual-command flow keeps behavior and messaging consistent and adds no new dependency.
- **Alternatives considered**:
  - *Manually delete the tool's venv + PATH shim ourselves* — rejected: fragile across uv versions and layouts, and risks leaving uv's own bookkeeping inconsistent. `uv` owns that state.
  - *`pip uninstall`* — rejected: the recommended distribution is a uv tool, not a pip package; pip is only relevant to the source fallback, which is treated as a no-op (Decision 3).

## Decision 2 — `DIST_NAME`, not the `caia` command name

- **Decision**: Target the distribution name `cisco-advisory-impact-agent` (already defined as `version.DIST_NAME`), not the `caia` command.
- **Rationale**: `uv tool uninstall` operates on the installed tool/distribution name; `caia` is merely the console-script entry point it exposes. `DIST_NAME` is already the single constant used by `perform_update()` and `read_installed_version()`.
- **Alternatives considered**: Hard-coding `caia` — rejected: `uv` would not recognize it as a tool name.

## Decision 3 — Detect install kind before acting (uv-managed vs source/pip)

- **Decision**: Classify the current install into one of three kinds and branch before prompting:
  1. **Not installed as a distribution** — `importlib.metadata` raises `PackageNotFoundError` (running from an un-installed source checkout). → *Nothing to uninstall* (exit 0).
  2. **uv-managed** — the distribution is installed under uv's tool directory. → Proceed to the confirmation/removal flow.
  3. **Installed but not uv-managed** — a `pip install .` / editable install. → *Nothing to uninstall* (exit 0, idempotent no-op per the clarify decision).
- **How the kind is determined**:
  - Primary signal: locate `uv` via `find_uv()`. When found, probe `uv tool list` and check whether `cisco-advisory-impact-agent` appears — an authoritative, layout-independent answer to "is this a uv tool?".
  - When `uv` cannot be located *and* the distribution metadata is present, we cannot confirm management and cannot act; treat as **uv-missing** (Decision 4) — print the manual command and exit non-zero — rather than guessing. When the distribution metadata is absent, it is unambiguously a source tree → *nothing to uninstall* (exit 0).
- **Rationale**: Ordering detection before the prompt avoids the poor UX of confirming and then reporting "nothing to do." Using `uv tool list` as the authority (when `uv` is available) avoids brittle path-guessing across uv versions and OSes. The idempotent-no-op outcome for non-uv installs is exactly the clarified behavior (fleet cleanup on already-clean machines must not report failure).
- **Alternatives considered**:
  - *Path-based detection* (compare the package location against `~/.local/share/uv/tools`, `%APPDATA%`/`%LOCALAPPDATA%`, `UV_TOOL_DIR`) — kept as a fallback idea but rejected as the primary signal: uv's data-dir layout is an implementation detail that has changed across versions and differs by OS; `uv tool list` is stable and explicit.
  - *Just run `uv tool uninstall` and interpret its exit/stderr* — rejected as the sole mechanism: uv's "not installed" wording is not a stable contract to parse, and it still needs the source-tree and uv-missing branches handled explicitly.

## Decision 4 — `uv` missing while a distribution is installed → manual fallback, non-zero

- **Decision**: When `find_uv()` returns `None` but the distribution appears installed, print the exact manual removal command (`uv tool install`-style manual string, i.e. `uv tool uninstall cisco-advisory-impact-agent`) and exit non-zero, making no partial changes.
- **Rationale**: Directly mirrors `perform_update()`'s "uv not found" branch and satisfies FR-008/FR-013. Non-zero because a manual step is still required — this is *not* the idempotent "already gone" success state.
- **Alternatives considered**: Silent exit 0 — rejected: it would falsely imply the tool is gone.

## Decision 5 — Confirmation gating and non-interactive safety

- **Decision**: Only in the **uv-managed + uv-present** branch, gate removal as follows, in order:
  1. `--yes` supplied → proceed without prompting.
  2. else if stdin is not a TTY (`sys.stdin.isatty()` is false) → **refuse**: print that `--yes` is required for non-interactive use, make no changes, exit non-zero (FR-003a).
  3. else prompt via `ui.confirm("Remove caia?", default=False)`; decline → make no changes, exit non-zero; accept → proceed.
- **Rationale**: Confirming a destructive action by default is the tool's conservative posture; refusing (rather than proceeding or blocking) when non-interactive without `--yes` was the explicit clarify decision, and it matches how the tool already skips TTY-only behavior (the start-of-run update nudge checks `sys.stdin.isatty()`).
- **Alternatives considered**: Proceed on no-TTY (unsafe), or block on `input()` (hangs scripts/CI) — both rejected by the clarify answer.

## Decision 6 — Self-removal: attempt, then fall back on failure

- **Decision**: Do not pre-branch on platform. Attempt `uv tool uninstall`; if it returns non-zero (the expected failure mode when the running command file is locked, notably on Windows), catch it and print the manual command to run from a fresh shell, exiting non-zero.
- **Rationale**: On macOS/Linux the running command can be unlinked in place while the process finishes, so the attempt succeeds and the process then prints its success message and returns 0. On Windows the attempt may fail, and the catch-and-instruct path is the same one `perform_update()` already uses. Attempting first is better than always instructing, because `uv` may handle the case itself.
- **Alternatives considered**: Detect Windows and always print the manual command without attempting — rejected: needlessly refuses a removal `uv` might complete.

## Decision 7 — Config preserved and disclosed; never deleted

- **Decision**: On a successful removal, report the on-disk config location using `config.config_path()`. If that file exists, tell the user where it is and that they can delete it manually; if it does not exist, state that there was no saved configuration to preserve. Never delete or read the file's contents; no `--purge` in v1.
- **Rationale**: Satisfies FR-002/FR-004/FR-005 and Constitution V (only the *path* is surfaced, never the key). The config lives outside the tool's uv environment (`config.config_dir()` resolves to an OS-appropriate per-user dir), so `uv tool uninstall` never touches it regardless.
- **Alternatives considered**: Auto-delete or offer interactive deletion — explicitly out of scope for v1 (BRD §5.2, spec Assumptions).

## Decision 8 — CLI surface and mode precedence

- **Decision**: Add `--uninstall` as a mode flag and `--yes` (with short alias `-y`) as a modifier in `cli.build_parser()`. Dispatch `--uninstall` in `_dispatch()` in the existing precedence chain; mode flags remain mutually exclusive (handled in order, not combined), consistent with `--version`/`--update`/`--config`. Surface both in `--help` and in `README.md` + `docs/index.html`.
- **Rationale**: Matches the established CLI pattern (Constitution III) and the existing `_dispatch()` precedence design. `--yes` is scoped as a general skip-confirmation modifier so it reads naturally with `--uninstall`.
- **Alternatives considered**: A separate `caia-uninstall` console script — rejected: heavier, and inconsistent with the single-command design.

## Decision 9 — Exit-code mapping (idempotent success model)

- **Decision**:
  | Outcome | Exit |
  |---|---|
  | Removed successfully | 0 |
  | Not installed as a uv tool (source/pip, or already removed) | 0 (idempotent no-op) |
  | User declined the prompt | non-zero |
  | Non-interactive without `--yes` | non-zero |
  | `uv` missing while installed (manual step required) | non-zero |
  | `uv` removal command failed (incl. Windows self-lock) | non-zero |
  | Interrupted (Ctrl+C) | 130, no traceback |
- **Rationale**: Directly encodes FR-009/SC-007 and the clarify decision — "tool is not installed as a uv tool" is success; non-zero means "action still needed." Ctrl+C → 130 is the repo-wide convention (Constitution III), already handled by `main()`'s `KeyboardInterrupt` guard.
- **Alternatives considered**: Distinct codes per outcome — rejected during BRD review in favor of the simple 0/non-zero scheme.
