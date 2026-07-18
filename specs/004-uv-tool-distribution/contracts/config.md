# Config Contract: per-user configuration

Defines the persistent per-user configuration the tool reads on every run and `--config`
writes (FR-008–FR-011, D7/D8). Replaces the old repo-local `.env`.

## Location

Resolved with stdlib only (no `platformdirs` dependency), directory
`cisco-advisory-impact-analyzer/`, file name `config`:

| OS | Directory |
|----|-----------|
| Windows | `%APPDATA%\cisco-advisory-impact-analyzer\` |
| macOS | `~/Library/Application Support/cisco-advisory-impact-analyzer/` |
| Linux/other | `${XDG_CONFIG_HOME:-~/.config}/cisco-advisory-impact-analyzer/` |

Kept out of any working folder and out of version control. Not created until `--config` writes
it (or the tool writes it on first `--config`).

## File format

`KEY=value`, one per line; `#` comments and blank lines ignored; values may be quoted.
Human-editable (required for the base-URL "edit the file directly" path, FR-010). Example:

```
FUELIX_API_KEY=sk-...redacted...
FUELIX_MODEL=claude-sonnet-5
FUELIX_BASE_URL=https://api.fuelix.ai/v1
```

## Keys

| Key | Meaning | Default | Set via `--config`? |
|-----|---------|---------|---------------------|
| `FUELIX_API_KEY` | FueliX API key (secret) | (none) | Yes — prompted (FR-008) |
| `FUELIX_MODEL` | Model id | `claude-sonnet-5` | Yes — curated menu (FR-009) |
| `FUELIX_BASE_URL` | OpenAI-compatible base URL | `https://api.fuelix.ai/v1` | No — env/file-edit only (FR-010) |

## Resolution precedence (per key)

`environment variable` → `per-user config file` → `built-in default` (D8, Assumptions). Env
vars always win so automation can override; `--config` never writes env vars.

## Security (Principle V, FR-023)

- The config file is created with `0600` (owner-only) permissions on POSIX; on Windows it lives
  under the per-user profile with default user ACLs.
- The API key is never logged, printed back in full, or transmitted anywhere except FueliX for
  analysis. `--config` re-run offers to keep or replace it without echoing it.
- Version/update checks never read or transmit this file (FR-023).

## `--config` behavior

1. Prompt for the API key (hidden input); empty input keeps the existing value.
2. Present the curated model menu with `claude-sonnet-5` as default; a currently-configured
   model absent from the list is shown as the current value and is keepable (FR-009).
3. Do not prompt for base URL (FR-010).
4. Write the file atomically with owner-only permissions; report where it was saved.
