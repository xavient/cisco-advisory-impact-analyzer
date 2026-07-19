#!/usr/bin/env bash
#
# Clean-room test of the uv install + run flow in a fresh Docker container.
#
# Spins up a throwaway container with no prior copy of the tool, installs uv, runs the
# documented `uv tool install` command, and smoke-tests the result (--version, --help, the
# API-key gate, and a dry-run that writes a report). Your local .venv, config, and API key
# never enter the container.
#
# Usage:
#   tools/install-test.sh                 # test the current working tree (local mode, default)
#   tools/install-test.sh --git           # test `--from git+<repo>@<current-branch>`
#   tools/install-test.sh --git main      # test a specific branch/tag/commit from GitHub
#   tools/install-test.sh --image python:3.12-slim   # use a different base image (default 3.9)
#
# Requires Docker. Local mode works offline against your tree; the container still needs
# network to fetch uv and (for --git) clone the repo.
set -euo pipefail

REPO_URL="https://github.com/xavient/cisco-advisory-impact-analyzer"
IMAGE="python:3.9-slim"   # 3.9 is the minimum supported Python — install on the floor
MODE="local"
GIT_REF=""

usage() { awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --git)
      MODE="git"
      if [ $# -gt 1 ] && [ "${2#--}" = "$2" ]; then GIT_REF="$2"; shift; fi
      ;;
    --image) IMAGE="${2:?--image needs a value}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown argument '$1'" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

command -v docker >/dev/null 2>&1 || { echo "error: Docker is required but not found on PATH." >&2; exit 1; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Resolve what uv will install from, and (local mode) stage a clean copy of the tree.
STAGE=""
MOUNT_ARGS=()
if [ "$MODE" = "git" ]; then
  [ -n "$GIT_REF" ] || GIT_REF="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
  INSTALL_FROM="git+${REPO_URL}@${GIT_REF}"
  echo ">> Mode: git  (uv tool install ... --from ${INSTALL_FROM})"
else
  STAGE="$(mktemp -d)"
  trap 'rm -rf "$STAGE"' EXIT
  # Copy the working tree minus local/build junk, so the container sees a clean source.
  tar -C "$ROOT" \
    --exclude='./.git' --exclude='./.venv' --exclude='./build' --exclude='./dist' \
    --exclude='./output' --exclude='./inventory' --exclude='./.update-backup' \
    --exclude='*.egg-info' --exclude='__pycache__' \
    -cf - . | tar -C "$STAGE" -xf -
  INSTALL_FROM="/src"
  # Read-write: it's a disposable copy, and setuptools writes egg-info into the tree at build.
  MOUNT_ARGS=(-v "${STAGE}:/src")
  echo ">> Mode: local  (uv tool install ... --from /src  <- current working tree)"
fi

echo ">> Base image: ${IMAGE}"

# Script run inside the container.
CONTAINER_SCRIPT='
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
echo "== installing prerequisites (curl, git) =="
apt-get update -qq >/dev/null
apt-get install -y -qq curl ca-certificates git >/dev/null

echo "== installing uv =="
curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
export PATH="$HOME/.local/bin:$PATH"
uv --version

echo "== uv tool install (the documented command) =="
uv tool install cisco-advisory-impact-analyzer --from "$INSTALL_FROM"

echo "== command is on PATH =="
command -v caia

echo "== --version =="
caia --version

echo "== --help =="
caia --help >/dev/null && echo "help OK"

echo "== prepare a working folder with a valid inventory =="
mkdir -p /work && cd /work
uv run --with openpyxl python - <<PY
import openpyxl
wb = openpyxl.Workbook(); ws = wb.active; ws.title = "FW_List"
ws.append(["FirewallName", "Model", "FirewallType", "IOS version"])
ws.append(["fw-1", "ASA5525", "ASA", "9.16(4)67"])
wb.save("inv.xlsx")
print("wrote inv.xlsx")
PY

URL="https://sec.cloudapps.cisco.com/security/center/content/CiscoSecurityAdvisory/cisco-sa-test-abcd1234"

echo "== API-key gate: a real run with no key must exit non-zero and name --config =="
if caia --url "$URL" --inventory inv.xlsx --no-update-check; then
  echo "FAIL: expected a non-zero exit when no API key is configured"; exit 1
fi
echo "key gate OK (exited non-zero)"

echo "== dry-run writes a report into ./output =="
caia --dry-run --url "$URL" --inventory inv.xlsx --no-update-check
ls output/analysis_output_*.xlsx >/dev/null 2>&1 && echo "report written OK" || { echo "FAIL: no report"; exit 1; }

echo
echo "ALL CHECKS PASSED"
'

# The ${arr[@]+"${arr[@]}"} guard keeps an empty MOUNT_ARGS (git mode) from tripping `set -u`
# on bash 3.2 (macOS's default).
docker run --rm ${MOUNT_ARGS[@]+"${MOUNT_ARGS[@]}"} -e INSTALL_FROM="$INSTALL_FROM" \
  "$IMAGE" bash -c "$CONTAINER_SCRIPT"

echo
echo ">> install-test succeeded (${MODE} mode, ${IMAGE})."
