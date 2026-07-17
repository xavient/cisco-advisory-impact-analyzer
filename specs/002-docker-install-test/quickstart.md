# Quickstart & Validation: Dockerized End-to-End Installation Test

**Feature**: `002-docker-install-test` | **Date**: 2026-07-16

Runnable scenarios that prove the harness works end to end. See
[contracts/cli.md](./contracts/cli.md) for the full CLI/runtime contract and
[data-model.md](./data-model.md) for the entities referenced below.

## Prerequisites

- Docker installed and the daemon running (`docker info` succeeds).
- `curl` and `unzip` on PATH (standard on macOS/Linux).
- A published release exists at the latest-release URL (for the default path). To test
  before publishing, use `--local`.
- Optional (for a full analyzer run): a FueliX API key and an inventory `.xlsx`.

## Scenario 1 — Reach the interactive shell (US1, SC-001)

```bash
./tools/install-test/test-install.sh
```

**Expected**: Preflight passes; the release downloads and unpacks; an image builds; you are
dropped into an interactive `bash` prompt inside the container, in the folder that holds
`install.py`. Under ~5 minutes on a typical connection.

```bash
# inside the container
pwd            # -> the app working dir
ls             # -> install.py, run.py, requirements.txt, analyzer.py, ...
python3 --version   # -> Python 3.9.x
```

## Scenario 2 — Verify the clean baseline BEFORE installing (US2, SC-002)

```bash
# inside the container, before running install.py
ls -a                     # no .venv, no .env
python3 -c "import openpyxl"   # -> ModuleNotFoundError (deps not installed yet)
ls inventory 2>/dev/null || echo "no inventory dir/files"
```

**Expected**: no `.venv`, no `.env`, project dependencies not importable, no inventory
present. This is the "fresh end-user machine" guarantee.

## Scenario 3 — Run the installer end to end (US1, SC-003)

```bash
# inside the container
python3 install.py
```

**Expected**: the installer walks its steps (Python check → creates `.venv` → installs
`openpyxl`/`python-dotenv` → prompts for the FueliX API key with hidden input → sets up
`inventory/` and `output/` → smoke test) and ends with **"Setup complete."** Prompts accept
typed input (proves the TTY works, FR-006).

> No key handy? You can still complete installation — press Enter to skip the key (the
> installer warns and continues), or run `python3 install.py --yes` for a fully
> non-interactive pass.

## Scenario 4 — Full analyzer run via the shared mount (US1 follow-on, FR-011)

Bring an inventory in and get the report back out through the bind-mounted share.

```bash
# On the HOST, in another terminal: copy your inventory into the share dir the script printed
cp ~/my-firewalls.xlsx "<printed-share-path>/inventory.xlsx"
```

```bash
# inside the container (after install.py)
python3 run.py --inventory /work/share/inventory.xlsx --output-dir /work/share --dry-run
```

**Expected**: with `--dry-run` the analyzer fetches/parses without calling the AI (no key
needed) and writes a report into `/work/share`, which appears on the host in the share dir.
Drop `--dry-run` and paste an ERP URL to exercise the real AI path with your key.

## Scenario 5 — Repeatability & default cleanup (US3, SC-004, SC-005)

```bash
exit                                   # leave the container
docker ps -a                           # -> no leftover container from this run
docker images | grep -i install-test  # -> no leftover harness image
./tools/install-test/test-install.sh   # run again -> identical clean baseline
```

**Expected**: after a normal exit nothing from the run remains on the host; a second run
starts from the same pristine state. Repeat 10× without failures from leftover state.

## Scenario 6 — Keep the environment for debugging (FR-010)

```bash
./tools/install-test/test-install.sh --keep
# ... reproduce a failure, then exit
```

**Expected**: on exit the container/image are **retained** and the script prints the exact
commands to re-enter (`docker start -ai <name>`) and later remove them.

## Scenario 7 — Test a release candidate before publishing (FR-012)

```bash
./tools/install-test/test-install.sh --local ./dist/cisco-advisory-impact-analyzer.zip
# or point at a working directory (secrets/build artifacts are excluded from staging):
./tools/install-test/test-install.sh --local .
```

**Expected**: the local package is used instead of the download; a directory source is
staged with `.venv/`, `.env`, `inventory/`, `output/`, `__pycache__/`, `.git/` excluded, so
the baseline stays clean.

## Scenario 8 — Failure modes are actionable (SC-006)

```bash
# Docker daemon stopped:
./tools/install-test/test-install.sh      # -> clear "Docker is required / not running" message, non-zero exit

# Simulate an unavailable release:
./tools/install-test/test-install.sh --local ./does-not-exist.zip   # -> clear message, non-zero exit
```

**Expected**: the script stops with a message identifying the cause and never drops you
into an empty or broken shell.

## Traceability

| Scenario | Requirements / Success Criteria |
|----------|---------------------------------|
| 1 | FR-001, FR-005, FR-006, SC-001 |
| 2 | FR-003, SC-002 (US2-AS2, US2-AS3) |
| 3 | FR-006, SC-003 (US1-AS2, US1-AS3) |
| 4 | FR-011 |
| 5 | FR-002, FR-009, FR-010, SC-004, SC-005 |
| 6 | FR-010 |
| 7 | FR-004, FR-012 |
| 8 | FR-007, FR-008, SC-006 |
