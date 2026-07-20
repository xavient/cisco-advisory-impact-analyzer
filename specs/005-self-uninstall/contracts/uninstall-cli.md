# CLI Contract: `caia --uninstall`

The user-facing contract for the self-uninstall command. Observable behavior only — flags, ordering, message *intent*, side effects, and exit codes. Exact wording is an implementation detail; the assertions below are the contract.

## Invocation

```text
caia --uninstall [--yes | -y]
```

- **`--uninstall`** — mode flag. Removes the uv-installed tool and its `caia` command.
- **`--yes` / `-y`** — modifier. Skips the confirmation prompt (for scripted / unattended use). Has no effect on outcomes other than suppressing the prompt (it never forces a removal that cannot happen).

### Mode precedence

`--uninstall` is a mutually-exclusive mode, handled in the existing `_dispatch()` precedence chain alongside `--version`, `--update`, `--config`. Modes are not combined; a single invocation performs one mode. (Precedence relative to the other modes is fixed in `_dispatch()`; `--uninstall` slots in with them and is never merged with an analysis run.)

## Preconditions & classification (before any prompt)

The command first classifies the environment (see data-model.md `InstallKind`) and branches **before** prompting, so it never prompts in a state where it cannot act:

1. **Not installed as a distribution** (source checkout) → `NOTHING_TO_UNINSTALL`.
2. **Installed but not a uv tool** (pip/editable) → `NOTHING_TO_UNINSTALL`.
3. **Distribution present but `uv` not locatable** → `MANUAL_REQUIRED`.
4. **uv-managed and `uv` present** → proceed to confirmation gating.

## Confirmation gating (uv-managed + uv present only)

In order:

1. `--yes` present → proceed without prompting.
2. else stdin is **not** a TTY → `REFUSED_NONINTERACTIVE` (no prompt, no changes).
3. else prompt "remove?" defaulting to **No** → decline ⇒ `DECLINED`; accept ⇒ proceed.

## Removal

- Delegates to `uv tool uninstall cisco-advisory-impact-agent`.
- Success ⇒ `REMOVED`. Non-zero from `uv` (incl. Windows self-lock) ⇒ `REMOVAL_FAILED`.

## Outcomes, message intent, and exit codes

| Outcome | Exit | Message intent (secret-free, actionable) | Side effects |
|---------|------|------------------------------------------|--------------|
| `REMOVED` | 0 | Confirms the tool was removed; states the preserved config's path (or that none existed) and how to delete it manually | Tool + `caia` command removed via `uv`; config file **untouched** |
| `NOTHING_TO_UNINSTALL` | 0 | Explains it is not uv-installed (source/pip), so there is nothing to uninstall | **None** |
| `MANUAL_REQUIRED` | ≠0 | States `uv` could not be located; prints the exact manual `uv tool uninstall …` command | **None** (no partial removal) |
| `REFUSED_NONINTERACTIVE` | ≠0 | States `--yes` is required for non-interactive use | **None** |
| `DECLINED` | ≠0 | Acknowledges cancellation | **None** |
| `REMOVAL_FAILED` | ≠0 | States removal failed; on Windows, instructs to re-run the manual command from a fresh shell | Possibly none/partial — `uv` owns its own atomicity; the tool makes no direct edits |
| `INTERRUPTED` | 130 | (Handled by `main()`) prints "Cancelled." with no traceback | **None** |

### Exit-code guarantee (for automation)

- **Exit 0** ⟺ the tool is **not installed as a uv tool** at the end of the run (`REMOVED` or `NOTHING_TO_UNINSTALL`).
- **Non-zero** ⟺ action is still needed (`MANUAL_REQUIRED`, `REFUSED_NONINTERACTIVE`, `DECLINED`, `REMOVAL_FAILED`).
- **130** ⟺ interrupted.

This makes `caia --uninstall --yes` **idempotent** across a fleet: already-clean machines exit 0.

## Invariants (all outcomes)

- **INV-1**: The per-user configuration file is never modified or deleted. Its *contents* are never read, printed, logged, or transmitted — only its path and existence are used.
- **INV-2**: No user work products (reports, inventory, CSAF files) are read, modified, or deleted.
- **INV-3**: No network access occurs.
- **INV-4**: The command never proceeds with removal without either `--yes` or an affirmative interactive confirmation.
- **INV-5**: Every non-success message names the concrete next step (manual command, `--yes`, or re-run from a fresh shell).

## Test-observable assertions (map to acceptance scenarios)

- `caia --uninstall --yes` on a uv-managed install → removal invoked; exit 0; success message includes the config path (US1 AS1–AS2, US2 AS1).
- Interactive decline → no removal invoked; exit ≠0; install still usable (US1 AS3).
- Config file present vs absent → message reports the path vs "no saved configuration" (US1 AS2, FR-005).
- From a source/pip install → no removal invoked; exit 0; "nothing to uninstall" (US3 AS1, FR-007).
- uv-managed but `uv` absent → manual command printed; exit ≠0; no removal invoked (US3 AS2, FR-008).
- Non-interactive (no TTY) without `--yes` → refused; exit ≠0; no removal invoked (FR-003a).
- `uv` returns non-zero → failure surfaced; exit ≠0; no false success (US3 AS3, FR-011/FR-013).
- Ctrl+C at prompt → exit 130, no traceback (FR-009).
