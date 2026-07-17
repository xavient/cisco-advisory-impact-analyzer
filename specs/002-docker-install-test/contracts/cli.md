# Contract: `test-install.sh` CLI + Container Runtime

**Feature**: `002-docker-install-test` | **Date**: 2026-07-16

This is the interface contract for the maintainer-facing harness. It is a CLI tool
(Constitution Principle III), so the contract is its command usage, flags, exit codes, and
the runtime contract of the container it produces.

## Location & invocation

```text
tools/install-test/test-install.sh
```

Run from the repository root (recommended) or anywhere:

```bash
./tools/install-test/test-install.sh [OPTIONS]
```

## Options

| Flag | Arg | Default | Meaning |
|------|-----|---------|---------|
| `--keep` | — | off | Do **not** remove the container/image on exit; print re-enter and remove commands. |
| `--local <path>` | `.zip` or directory | unset | Use a local package instead of downloading the published release (FR-012). A directory is staged with secret/build artifacts excluded. |
| `--share <dir>` | directory | temp dir | Host folder bind-mounted at `/work/share` (created if missing; never auto-removed). If omitted, a temp dir is used and its absolute path is printed. |
| `-h`, `--help` | — | — | Print usage and exit `0`. |

Unknown flags ⇒ usage message on stderr, exit `2`.

## Behavior (happy path)

1. **Preflight**: verify `docker` on PATH and daemon reachable (`docker info`); verify
   `curl` and `unzip` present. On failure: actionable message → non-zero exit (FR-007).
2. **Acquire release**: download the published `.zip` fresh (or use `--local`) into a host
   temp **staging** dir; on download failure, message identifying the download → non-zero
   exit, no container started (FR-008, SC-006).
3. **Locate app root**: find the dir containing `install.py` under staging (D6); if absent,
   actionable error → non-zero exit.
4. **Build**: `docker build -f tools/install-test/Dockerfile "<app-root>" -t <tag>` — build
   context is the staged release only (never the repo) (D3).
5. **Run**: `docker run -it [--rm|--name <name>] -v "<share>":/work/share <tag> /bin/bash`
   — drops the maintainer at an interactive shell in the app working directory (FR-005,
   FR-006).
6. **Exit**: default removes container (`--rm`) and image (trap); with `--keep` retains both
   and prints how to re-enter/remove. Staging always removed. Interrupt ⇒ exit `130`
   (FR-010).

## Exit codes

| Code | Condition |
|------|-----------|
| `0` | Interactive session completed and cleanup succeeded (or `--help`). |
| `2` | Invalid usage / unknown flag. |
| `3` | Preflight failed (Docker missing or daemon down; or missing `curl`/`unzip`). |
| `4` | Release could not be obtained (download failed / `--local` path missing / no `install.py`). |
| `130` | Interrupted (Ctrl-C / SIGINT). |

> Exact non-zero codes may be refined in implementation; the contract is: `0` success,
> distinct non-zero per failure class, `130` on interrupt.

## Container runtime contract

| Aspect | Contract |
|--------|----------|
| Base image | `python:3.9-slim` |
| `python3 --version` | reports `3.9.x` |
| Working directory | app root containing `install.py`, `run.py`, `requirements.txt`, … |
| Preexisting state | no `.venv/`, no `.env`, `openpyxl`/`python-dotenv` **not** importable until installed |
| Shell | `/bin/bash`, interactive with a TTY |
| Mount | host share ↔ `/work/share`, empty at launch |
| Network | outbound to GitHub (host download) and PyPI (in-container `pip`) available |

## Interaction with the tool under test (existing, unchanged interfaces)

The harness does not add flags to the app; it relies on the installer/launcher contracts
already documented for the analyzer:

- `python3 install.py` — interactive install (Python check → `.venv` → deps → `.env` key →
  folders/inventory → smoke test). Non-interactive: `--yes`, `--api-key`, `--model`,
  `--inventory <path>`, `--no-run`, `--recreate-venv`.
- `python3 run.py [--url … | --inventory /work/share/<f>.xlsx | --output-dir /work/share |
  --dry-run]` — launches the analyzer via the created `.venv`.

## Acceptance (maps to spec)

- Lands at an interactive shell in the package folder → FR-005, US1-AS1.
- `python3 install.py` prompts accept typed input, finishes "Setup complete" → FR-006,
  US1-AS2, SC-003.
- Pre-install inspection shows no venv/env/deps/inventory → FR-003, US2-AS2, SC-002.
- `python3 --version` = 3.9.x → US2-AS3.
- Re-run yields identical clean baseline; nothing accumulates → FR-009, SC-004; exit leaves
  zero environments by default → FR-010, SC-005.
- Docker-down / download-fail produce actionable messages, no empty shell → FR-007, FR-008,
  SC-006.
