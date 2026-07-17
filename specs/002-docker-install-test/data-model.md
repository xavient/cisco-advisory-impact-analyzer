# Data Model: Dockerized End-to-End Installation Test

**Feature**: `002-docker-install-test` | **Date**: 2026-07-16

This feature has no persistent data store. Its "entities" are the runtime objects and
configuration the harness manipulates. They are documented here so tasks and contracts stay
consistent.

## Entities

### Test environment (container)

The fresh, disposable Linux container that mirrors a clean end-user machine.

| Field | Value / Rule |
|-------|--------------|
| Base image | `python:3.9-slim` (minimum supported Python; `pip`/`venv`/`bash` present) |
| Working directory | app root containing the release (e.g. `/work/app`) |
| Preinstalled tool state | **none** — no `.venv`, no `.env`, no installed project deps, no inventory (FR-003, SC-002) |
| Lifetime | Ephemeral; auto-removed on exit by default (`--rm`), retained only with `--keep` (FR-010) |
| Identity | Default: anonymous (`--rm`). `--keep`: a stable container name is assigned and printed |
| Arch | Matches host (multi-arch pull); no emulation |

**State transitions**: `absent → built(image) → running(interactive shell) → removed`
(default) or `→ stopped/kept` (with `--keep`).

### Release package (subject under test)

The archive an end user downloads; the thing being validated.

| Field | Value / Rule |
|-------|--------------|
| Default source | `https://github.com/xavient/cisco-advisory-impact-analyzer/releases/latest/download/cisco-advisory-impact-analyzer.zip` (FR-004) |
| Freshness | Re-downloaded on every run (no caching of the archive) |
| Local override | `--local <path>` = a `.zip` or a directory (FR-012) |
| Required marker | Must contain `install.py` (used to locate the app root; D6). Absence ⇒ actionable error |
| Cleanliness rule | When staged from a directory, excludes `.venv/`, `.env`, `inventory/`, `output/`, `__pycache__/`, `.git/`, `*.pyc`, `~$*.xlsx` |

### Staging directory (host, transient)

Where the release is unpacked on the host before the image is built.

| Field | Value / Rule |
|-------|--------------|
| Location | Host temp dir (`mktemp -d`) |
| Contents | Unpacked release only; becomes the Docker **build context** |
| Lifetime | Removed on exit (EXIT trap), always |
| Security rule | Never the repo root; guarantees secrets stay out of the image (Principle V, D3) |

### Share mount (host ↔ container bridge)

Empty-at-launch host folder bind-mounted into the container for inventory drop-in and
report capture (FR-011).

| Field | Value / Rule |
|-------|--------------|
| Container path | `/work/share` |
| Host path | `--share <dir>` (created if missing) or an auto-created temp dir whose absolute path is printed |
| State at launch | **Empty** — preserves clean baseline (FR-003, SC-002) |
| Usage | Maintainer drops `.xlsx` here; reports written here via `run.py --output-dir /work/share` |
| Lifetime | Explicit `--share` dir: never auto-removed. Temp share: removed on exit unless `--keep` |

### Launcher invocation (configuration)

The parsed options that parameterize one run. Full contract in
[contracts/cli.md](./contracts/cli.md).

| Field | Type | Default | Rule |
|-------|------|---------|------|
| `--keep` | flag | off | Retain container + image after exit; print re-enter/remove commands |
| `--local <path>` | path | (unset) | Use a local `.zip`/dir instead of downloading |
| `--share <dir>` | path | temp dir | Host folder to bind-mount as `/work/share` |
| `--help` | flag | — | Print usage and exit `0` |

## Relationships

```text
Launcher invocation
   │ downloads / stages
   ▼
Release package ──unpacked into──> Staging directory ──build context──> Test environment (image → container)
                                                                              │ bind-mounts
                                                                              ▼
                                                                        Share mount (host ↔ container)
```

## Validation rules (derived from requirements)

- Docker present + daemon reachable before any work (FR-007) — else exit non-zero.
- Release obtainable (download OK, or `--local` path exists) — else exit non-zero, no
  container started (FR-008, SC-006).
- Staged app root must contain `install.py` (D6) — else actionable error.
- Environment contains no `.venv` / `.env` / project deps / inventory before install
  (FR-003, SC-002).
- Share mount empty at launch (FR-011).
- On exit (normal, error, or interrupt): container removed and image removed unless
  `--keep`; staging always removed (FR-010, SC-005); exit `130` on interrupt.
