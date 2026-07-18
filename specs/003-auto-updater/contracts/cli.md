# Contract: `update.py` CLI + `run.py` version/nudge

**Feature**: `003-auto-updater` | **Date**: 2026-07-17

The feature's user-facing surface is the command line (Constitution Principle III). This
contract defines `update.py`'s usage, flags, exit codes, and messages, plus the additions to
`run.py`. It is stable regardless of internal implementation.

## `update.py`

### Invocation

Run from the tool folder with the **base** Python (no `.venv` needed), mirroring `install.py`:

```bash
python3 update.py [OPTIONS]      # macOS / Linux
python update.py  [OPTIONS]      # Windows
```

### Options

| Flag | Arg | Default | Meaning |
|------|-----|---------|---------|
| *(none)* | — | — | Check for a newer release; if one exists, show `current → new`, **confirm**, then update. |
| `--check` | — | off | Report installed vs latest and whether an update is available; **make no changes** (FR-008). |
| `--yes`, `-y` | — | off | Skip the confirmation prompt (scripted/non-interactive updates) (FR-009). |
| `--rollback` | — | off | Restore the most recent backup (revert to the prior version); user data untouched (FR-011). |
| `--repo` / `CAIA_UPDATE_REPO` | `owner/name` | `xavient/cisco-advisory-impact-analyzer` | Override the release source (fork testing) (D13). |
| `-h`, `--help` | — | — | Print usage and exit `0`. |

Unknown flags ⇒ usage on stderr, exit `2`.

### Behavior — default (update) path

1. **Read installed version** from `VERSION` (unknown ⇒ treat as older) (FR-003).
2. **Resolve latest** via the GitHub API, falling back to the `/releases/latest` redirect
   (FR-004). Unreachable/rate-limited ⇒ actionable message, **exit 3**, no changes (FR-015).
3. **Compare** with semantic-version ordering (FR-004):
   - equal ⇒ `"Already up to date (x.y.z)."` → **exit 0**, no changes (FR-005).
   - installed newer ⇒ `"Installed x.y.z is ahead of latest a.b.c; nothing to do."` → exit 0.
   - latest newer ⇒ continue.
4. **Confirm**: show `current → new` and prompt (`ui.confirm`); `--yes` skips. Decline ⇒
   exit 0, no changes (US1-AS4).
5. **Download** the tag-pinned asset + its `.sha256` to a temp dir (FR-014, HTTPS, proxy-
   honored). Download failure ⇒ **exit 4**, no changes.
6. **Verify** SHA-256 == published, zip well-formed, embedded `VERSION` == tag (FR-006). Any
   failure ⇒ **exit 4**, no changes.
7. **Back up** files to be replaced/removed (+ `VERSION`/`MANIFEST`); write
   `.update-in-progress` (FR-011).
8. **Apply**: overlay staged files **skipping the preserve-list**; remove files dropped from
   the manifest (FR-002, FR-019).
9. **Refresh deps** if `requirements.txt` changed and `.venv` exists (FR-007).
10. **Finish**: update `VERSION`/`MANIFEST`, prune old backups, clear the marker; print the
    new installed version → **exit 0**.

On any failure in 8–9 ⇒ **auto-revert** from the backup: success → **exit 5** (restored to
old version); revert also failed → **exit 6** (advise `--rollback`).

### Behavior — `--check`

Prints, without modifying anything:

```text
Installed: 1.1.0
Latest:    1.2.0
Status:    update available  (run: python3 update.py)
```

Statuses: `up to date` · `update available` · `ahead of latest` · `latest unknown (could not
reach GitHub)`. Exit `0` when it could report installed version (even if latest unknown);
exit `3` only if it cannot determine the installed version *and* latest.

### Behavior — `--rollback`

Restores the newest `.update-backup/…` over the install (preserve-list untouched), restores
the prior `VERSION`/`MANIFEST`, and prints the reverted version. No backup present ⇒ actionable
message, exit `1`. Success ⇒ exit `0`.

### Startup recovery

If `.update-in-progress` exists at startup (a prior update was interrupted), the tool reports
it and restores from the recorded backup before proceeding (FR-012).

### Exit codes

| Code | Condition |
|------|-----------|
| `0` | Updated, already up to date, ahead, `--check` reported, `--rollback` restored, or `--help`. |
| `1` | Generic failure (e.g. `--rollback` with no backup). |
| `2` | Invalid usage / unknown flag. |
| `3` | Could not determine the latest version (network / rate-limited). |
| `4` | Download or verification failed — **no files changed**. |
| `5` | Apply failed; **auto-revert succeeded** (install restored to prior version). |
| `6` | Apply failed; **revert also failed** (manual `--rollback` may be needed). |
| `130` | Interrupted (Ctrl-C / EOF). |

> Exact non-zero values may be refined in implementation; the contract is: `0` success,
> distinct non-zero per failure class, `4` guarantees no changes, `5`/`6` distinguish
> self-healed vs needs-attention, `130` on interrupt.

### Guarantees (map to spec)

- Preserve-list byte-for-byte unchanged after update **and** rollback → FR-002, SC-002.
- No file touched unless download+verify pass → FR-006, SC-004, US1-AS3.
- Never reads/sends/overwrites `.env` → FR-017.
- Actionable errors + meaningful exit codes → FR-018, Principle III.

## `run.py` additions

| Flag / env | Meaning |
|------------|---------|
| `--version` | Print the installed version (from `VERSION`) and exit `0` (FR-010). Handled by `run.py` before delegating to the analyzer; not passed through. |
| `--no-update-check` | Disable the passive update nudge for this run. Consumed by `run.py`, not passed to the analyzer. |
| `CAIA_NO_UPDATE_CHECK` (env) | Same as `--no-update-check`, persistent for the shell/session. |

**Passive nudge contract** (FR-016): before delegating, `run.py` performs a best-effort
latest check with a **short timeout (~2 s)**, fully guarded so any error/timeout is silent.
If a newer version exists it prints **one** line, e.g.:

```text
› A new version 1.2.0 is available (you have 1.1.0). Update with: python3 update.py
```

The analyzer then runs **normally regardless** of the check result (US4-AS1/AS2). Stateless
(no persisted timestamp — Q5). Skipped when disabled or for `--version`.
