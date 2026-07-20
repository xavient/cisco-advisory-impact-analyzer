# Quickstart & Validation: Self-Uninstall Command

How to exercise `caia --uninstall` end-to-end and confirm each user story. See [contracts/uninstall-cli.md](./contracts/uninstall-cli.md) for the full contract and [data-model.md](./data-model.md) for the outcome→exit-code map. This is a run/validation guide — implementation belongs in `tasks.md`.

## Prerequisites

- `uv` installed and on PATH (`uv --version`).
- Python 3.9+.
- A throwaway environment (VM/container/user profile) is ideal, since the happy-path scenario removes the tool.

## Automated validation (primary)

The core logic is covered by unit tests that mock `uv` and the environment — no real install/removal needed:

```bash
# from repo root
python -m pytest tests/test_version.py tests/test_cli.py -q
```

Expected: all pass, including the new detection (`uv_managed` / `not_installed` / `pip_or_source` / `unknown_uv_absent`), removal, prompt-gating, and exit-code cases. The suite mocks `version.find_uv()`, `uv tool list`, and the removal subprocess (following the existing `tests/test_version.py` patterns), so it does not touch the real machine.

## Manual end-to-end scenarios

Run from any working folder (the tool is on PATH once installed).

### Scenario A — Happy path, config preserved (US1 · P1)

```bash
uv tool install cisco-advisory-impact-agent --from 'git+https://github.com/xavient/cisco-advisory-impact-analyzer'
caia --config        # save an API key + model so there is config to preserve
caia --uninstall     # answer "y" at the prompt
```

Expect: prompt defaults to No; after confirming, the tool is removed, `caia` is no longer found (`command -v caia` empty), the success message names the preserved config path, and the exit code is 0 (`echo $?`). Verify the config file still exists at the reported path and its contents are unchanged.

### Scenario B — Decline the prompt (US1 · P1)

```bash
caia --uninstall     # answer "n" (or just press Enter — default is No)
echo $?              # non-zero
caia --version       # still works — nothing was removed
```

### Scenario C — Non-interactive removal via --yes (US2 · P2)

```bash
caia --uninstall --yes < /dev/null    # no prompt
echo $?                                # 0 when removed (or already absent)
```

Re-run the same command on an already-clean machine and confirm it still exits 0 ("nothing to uninstall") — proving idempotence for fleet cleanup.

### Scenario D — Non-interactive WITHOUT --yes is refused (FR-003a)

```bash
caia --uninstall < /dev/null   # no TTY, no --yes
echo $?                        # non-zero; message says --yes is required; nothing removed
```

### Scenario E — Source checkout / pip install (US3 · P1 edge)

```bash
# from a cloned repo, not a uv tool install
python -m cisco_advisory_impact_agent.cli --uninstall   # or an entry point from `pip install .`
echo $?   # 0 — reports "nothing to uninstall", makes no changes
```

### Scenario F — uv missing (US3 · P2 edge)

```bash
# on a uv-managed install, with uv temporarily off PATH
PATH="/usr/bin:/bin" caia --uninstall --yes   # find_uv() also checks ~/.local/bin; ensure it truly can't resolve
echo $?   # non-zero; prints the exact manual `uv tool uninstall …` command; nothing removed
```

### Scenario G — Interrupt (FR-009)

```bash
caia --uninstall     # press Ctrl+C at the prompt
echo $?              # 130, no traceback
```

## Acceptance mapping

| Scenario | Validates |
|----------|-----------|
| A | US1 AS1, AS2, AS4; FR-001, FR-002, FR-005, FR-006 |
| B | US1 AS3; FR-002, FR-009 |
| C | US2 AS1, AS2; FR-003, FR-009 (idempotent success) |
| D | FR-003a; non-interactive edge case |
| E | US3 AS1; FR-007 |
| F | US3 AS2; FR-008 |
| G | FR-009 (interrupt) |

## Success signal

The feature is validated when the automated suite passes and Scenarios A–G behave as described — in particular: the config file is preserved and disclosed on success, work products are never touched, and the exit codes match the idempotent-success contract (0 ⟺ not installed as a uv tool; non-zero ⟺ action still needed; 130 ⟺ interrupt).
