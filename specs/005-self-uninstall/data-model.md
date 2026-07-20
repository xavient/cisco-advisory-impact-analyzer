# Phase 1 Data Model: Self-Uninstall Command

This feature manages **no persistent data of its own** — it introduces no new files, schemas, or records. What follows models the entities the command *reasons about* (from spec §Key Entities) and the transient outcome state that maps to the process exit code. This is a behavioral model, not a storage schema.

## Entities

### InstallKind (derived, not stored)

The classification the command computes at start-up to decide how to behave.

| Value | Meaning | Signal | Action |
|-------|---------|--------|--------|
| `uv_managed` | Installed as a uv tool | `uv tool list` includes `cisco-advisory-impact-agent` (when `uv` is locatable) | Enter confirmation/removal flow |
| `not_installed` | Not installed as a distribution | `importlib.metadata.version(DIST_NAME)` raises `PackageNotFoundError` | Idempotent no-op (exit 0) |
| `pip_or_source` | Installed but not uv-managed | Distribution present, `uv tool list` does not include it | Idempotent no-op (exit 0) |
| `unknown_uv_absent` | Distribution present, `uv` not locatable | `find_uv()` is `None` and metadata present | Manual-command fallback (exit non-zero) |

- **Relationships**: derived from the runtime environment (installed metadata + `uv` availability). Not persisted.
- **Validation / rules**: classification is computed once, before any prompt, so the command never prompts in a state where it cannot act.

### PerUserConfiguration (read-only reference)

The stored FueliX settings. **Referenced, never modified** by this feature.

| Field | Description | Source |
|-------|-------------|--------|
| location (path) | OS-appropriate per-user config file path | `config.config_path()` |
| exists | whether that file is present | `config_path().exists()` |

- **Attributes deliberately NOT read**: the file's *contents* (API key, model, base URL) are never opened, printed, or transmitted — only the path and its existence are used (Constitution V).
- **Lifecycle rule**: uninstall MUST leave this file byte-for-byte unchanged. It lives outside the uv tool environment, so `uv tool uninstall` does not touch it.

### UvTool (external, managed by uv)

The installed tool that `uv` owns and removes.

| Field | Description | Source |
|-------|-------------|--------|
| distribution name | `cisco-advisory-impact-agent` | `version.DIST_NAME` |
| command | `caia` console script on PATH | exposed by the install |
| environment | uv-managed isolated venv | owned by `uv` |

- **Rule**: the tool never removes these directly; removal is delegated to `uv tool uninstall <distribution name>`.

### WorkProducts (out of scope, must remain untouched)

Generated reports (`output/`), inventory `.xlsx`, and downloaded CSAF files in the user's working folders. The command never enumerates, reads, or deletes these; they are named here only to assert the invariant that uninstall leaves them alone.

## Outcome → Exit Code state map

The single transient "state machine" of the command. Each run resolves to exactly one outcome:

```text
start
  ├─ InstallKind == not_installed / pip_or_source ─────────────► NOTHING_TO_UNINSTALL  (exit 0)
  ├─ InstallKind == unknown_uv_absent ─────────────────────────► MANUAL_REQUIRED       (exit ≠0)
  └─ InstallKind == uv_managed
        ├─ not --yes AND not a TTY ──────────────────────────► REFUSED_NONINTERACTIVE (exit ≠0)
        ├─ not --yes AND TTY AND user declines ──────────────► DECLINED               (exit ≠0)
        └─ --yes OR user confirms → run `uv tool uninstall`
              ├─ success ────────────────────────────────────► REMOVED               (exit 0)
              └─ uv non-zero (e.g. Windows self-lock) ────────► REMOVAL_FAILED        (exit ≠0)

any point: Ctrl+C / EOF ─────────────────────────────────────► INTERRUPTED           (exit 130)
```

- **Success set (exit 0)**: `REMOVED`, `NOTHING_TO_UNINSTALL` — i.e. "the tool is not installed as a uv tool at the end of the run."
- **Action-still-needed set (exit ≠0)**: `MANUAL_REQUIRED`, `REFUSED_NONINTERACTIVE`, `DECLINED`, `REMOVAL_FAILED`.
- **Interrupt**: `INTERRUPTED` → 130 (handled by `main()`'s existing `KeyboardInterrupt` guard).
- Each terminal outcome emits an actionable, secret-free message (see the CLI contract for exact message intents).
