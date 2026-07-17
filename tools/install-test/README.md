# Install test harness (maintainer tool)

`test-install.sh` spins up a **fresh, disposable Docker container** that mirrors a clean
end-user machine, drops the **released package** into it, and hands you an interactive
shell so you can run `python3 install.py` and test the whole installation exactly as an end
user would.

This is maintainer tooling — it is **not** part of the shipped package.

## Requirements

- Docker installed and running (`docker info` succeeds)
- `curl` and `unzip` on PATH (standard on macOS/Linux)

## Usage

```bash
./tools/install-test/test-install.sh [OPTIONS]
```

| Option | Meaning |
| ------ | ------- |
| `--keep` | Keep the container + image after you exit (for debugging); prints how to re-enter and remove them. Default: everything is removed on exit. |
| `--local <path>` | Test a local package instead of downloading the published release. `<path>` is a `.zip` or a directory (a directory is staged with `.git/`, `.venv/`, `.env`, `inventory/`, `output/`, `__pycache__/`, `*.pyc` excluded). |
| `--share <dir>` | Host folder bind-mounted at `/work/share` (created if missing). Use it to bring an inventory `.xlsx` in and get reports back out. Default: a temp folder whose path is printed. |
| `-h`, `--help` | Show help and exit. |

Exit codes: `0` success · `2` invalid usage · `3` preflight failed (Docker/curl/unzip) ·
`4` release could not be obtained · `130` interrupted.

## What it does

1. Preflight-checks Docker (and `curl`/`unzip`).
2. Downloads the published release fresh (or uses `--local`) into a host temp staging dir.
3. Locates `install.py` in the package and builds a `python:3.9-slim` image **from the
   staged release only** — your repo's `.env`/`.venv`/inventory never enter the image.
4. Bind-mounts an empty share folder and drops you into an interactive shell in the
   package directory.
5. On exit, removes the container, image, and temp dirs (unless `--keep`).

## Inside the container

```bash
python3 install.py                 # test the installer end to end -> "Setup complete."

# optional full analyzer run using the shared mount:
cp /work/share/*.xlsx inventory/   # or use --inventory below
python3 run.py --inventory /work/share/inventory.xlsx --output-dir /work/share --dry-run
```

## Automated (non-interactive) smoke test

Set `INSTALL_TEST_EXEC` to run a command in the container instead of opening a shell —
useful for CI or a quick self-check:

```bash
INSTALL_TEST_EXEC='python3 install.py --yes --no-run' ./tools/install-test/test-install.sh --local .
```

See [../../specs/002-docker-install-test/quickstart.md](../../specs/002-docker-install-test/quickstart.md)
for full validation scenarios and
[../../specs/002-docker-install-test/contracts/cli.md](../../specs/002-docker-install-test/contracts/cli.md)
for the complete contract.
