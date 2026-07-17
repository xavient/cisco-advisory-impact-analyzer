#!/usr/bin/env bash
#
# test-install.sh — spin up a fresh, disposable Docker container that mirrors a clean
# end-user machine, place the released package in it, and drop you into an interactive
# shell so you can run `python3 install.py` and test the whole installation end to end.
#
# Usage:
#   ./tools/install-test/test-install.sh [--keep] [--local <path>] [--share <dir>]
#
# See tools/install-test/README.md and specs/002-docker-install-test/contracts/cli.md.

set -euo pipefail

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
RELEASE_URL="https://github.com/xavient/cisco-advisory-impact-analyzer/releases/latest/download/cisco-advisory-impact-analyzer.zip"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKERFILE="$SCRIPT_DIR/Dockerfile"
CONTAINER_WORKDIR="/work/app"
SHARE_MOUNT="/work/share"

# Files/dirs that must never enter the image (secrets + local build artifacts).
EXCLUDES=(".git" ".venv" "venv" ".env" "inventory" "output" "__pycache__")

# Exit codes (see contracts/cli.md)
EXIT_USAGE=2
EXIT_PREFLIGHT=3
EXIT_ACQUIRE=4

# --------------------------------------------------------------------------- #
# Small output helpers
# --------------------------------------------------------------------------- #
if [ -t 1 ]; then
  BOLD="$(printf '\033[1m')"; DIM="$(printf '\033[2m')"; RED="$(printf '\033[31m')"
  GREEN="$(printf '\033[32m')"; YELLOW="$(printf '\033[33m')"; RESET="$(printf '\033[0m')"
else
  BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; RESET=""
fi
info()  { printf '%s==>%s %s\n' "$BOLD" "$RESET" "$*"; }
ok()    { printf '%s✓%s %s\n' "$GREEN" "$RESET" "$*"; }
warn()  { printf '%s!%s %s\n' "$YELLOW" "$RESET" "$*" >&2; }
die()   { printf '%s✗ %s%s\n' "$RED" "$1" "$RESET" >&2; exit "${2:-1}"; }

usage() {
  cat <<EOF
${BOLD}test-install.sh${RESET} — end-to-end installation test in a fresh Docker container

Usage:
  ./tools/install-test/test-install.sh [OPTIONS]

Options:
  --keep            Keep the container and image after you exit (for debugging).
                    Prints how to re-enter and remove them. Default: remove on exit.
  --local <path>    Test a local package instead of downloading the published release.
                    <path> may be a .zip or a directory (secrets/build artifacts are
                    excluded from a directory source).
  --share <dir>     Host folder to bind-mount at ${SHARE_MOUNT} (created if missing).
                    Use it to bring an inventory .xlsx in and get reports out.
                    Default: a temp folder whose path is printed.
  -h, --help        Show this help and exit.

Once inside the container:
  python3 install.py        # run and test the installer end to end
EOF
}

# --------------------------------------------------------------------------- #
# Argument parsing (T003)
# --------------------------------------------------------------------------- #
KEEP=0
LOCAL_SRC=""
SHARE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --keep) KEEP=1; shift ;;
    --local)
      [ $# -ge 2 ] || { usage >&2; die "--local requires a <path> argument" $EXIT_USAGE; }
      LOCAL_SRC="$2"; shift 2 ;;
    --local=*) LOCAL_SRC="${1#*=}"; shift ;;
    --share)
      [ $# -ge 2 ] || { usage >&2; die "--share requires a <dir> argument" $EXIT_USAGE; }
      SHARE="$2"; shift 2 ;;
    --share=*) SHARE="${1#*=}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "Unknown option: $1" $EXIT_USAGE ;;
  esac
done

# --------------------------------------------------------------------------- #
# Cleanup + traps (T006, extended by T016/T017)
# --------------------------------------------------------------------------- #
STAGING=""
IMAGE=""
CONTAINER_NAME=""
SHARE_IS_TEMP=0

cleanup() {
  rc=$?
  # Staging is always disposable — the release lives in the image after build.
  [ -n "$STAGING" ] && rm -rf "$STAGING" 2>/dev/null || true

  if [ "$KEEP" = "1" ]; then
    # Preserve container + image + (temp) share; tell the maintainer how to use/clean them.
    if [ -n "$IMAGE" ]; then
      printf '\n%s--keep: environment preserved.%s\n' "$BOLD" "$RESET" >&2
      [ -n "$CONTAINER_NAME" ] && \
        printf '  Re-enter : %sdocker start -ai %s%s\n' "$DIM" "$CONTAINER_NAME" "$RESET" >&2
      [ -n "$CONTAINER_NAME" ] && \
        printf '  Remove   : %sdocker rm -f %s && docker rmi %s%s\n' "$DIM" "$CONTAINER_NAME" "$IMAGE" "$RESET" >&2
      [ "$SHARE_IS_TEMP" = "1" ] && [ -n "$SHARE" ] && \
        printf '  Share dir: %s%s%s (not removed)\n' "$DIM" "$SHARE" "$RESET" >&2
    fi
  else
    [ -n "$IMAGE" ] && docker rmi -f "$IMAGE" >/dev/null 2>&1 || true
    [ "$SHARE_IS_TEMP" = "1" ] && [ -n "$SHARE" ] && rm -rf "$SHARE" 2>/dev/null || true
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'trap - INT; exit 130' INT TERM

# --------------------------------------------------------------------------- #
# Preflight (T005)
# --------------------------------------------------------------------------- #
preflight() {
  command -v docker >/dev/null 2>&1 || die \
    "Docker is required but 'docker' was not found on PATH. Install Docker Desktop/Engine and retry." $EXIT_PREFLIGHT
  docker info >/dev/null 2>&1 || die \
    "Docker is installed but the daemon is not reachable. Start Docker and retry." $EXIT_PREFLIGHT
  command -v unzip >/dev/null 2>&1 || die "'unzip' is required but was not found on PATH." $EXIT_PREFLIGHT
  if [ -z "$LOCAL_SRC" ]; then
    command -v curl >/dev/null 2>&1 || die "'curl' is required to download the release but was not found." $EXIT_PREFLIGHT
  fi
  ok "Docker is available and running."
}

# --------------------------------------------------------------------------- #
# Acquire the release into $STAGING/unpacked (T007, T015)
# --------------------------------------------------------------------------- #
copy_dir_excluding() {
  # copy_dir_excluding <src> <dest> — copy a directory tree, dropping secrets/artifacts.
  local src="$1" dest="$2" args=()
  local e
  for e in "${EXCLUDES[@]}"; do args+=("--exclude=./$e"); done
  args+=("--exclude=*.pyc" "--exclude=~\$*.xlsx")
  mkdir -p "$dest"
  ( cd "$src" && tar "${args[@]}" -cf - . ) | ( cd "$dest" && tar -xf - )
}

acquire() {
  STAGING="$(mktemp -d "${TMPDIR:-/tmp}/cisco-install-test.XXXXXX")"
  # Normalize (strip any trailing/double slash from $TMPDIR, resolve symlinks) so it
  # matches the `cd && pwd`-resolved APP_ROOT used by the build-context safety guard.
  STAGING="$(cd "$STAGING" && pwd)"
  local unpacked="$STAGING/unpacked"
  mkdir -p "$unpacked"

  if [ -n "$LOCAL_SRC" ]; then
    if [ -f "$LOCAL_SRC" ] && [ "${LOCAL_SRC##*.}" = "zip" ]; then
      info "Using local package (zip): $LOCAL_SRC"
      unzip -q "$LOCAL_SRC" -d "$unpacked" || die "Could not unzip '$LOCAL_SRC'." $EXIT_ACQUIRE
    elif [ -d "$LOCAL_SRC" ]; then
      info "Using local package (directory): $LOCAL_SRC  ${DIM}(secrets/build artifacts excluded)${RESET}"
      copy_dir_excluding "$LOCAL_SRC" "$unpacked"
    else
      die "--local path '$LOCAL_SRC' is neither an existing .zip nor a directory." $EXIT_ACQUIRE
    fi
  else
    info "Downloading the latest published release ..."
    printf '    %s%s%s\n' "$DIM" "$RELEASE_URL" "$RESET"
    curl -fL --retry 2 -o "$STAGING/package.zip" "$RELEASE_URL" || die \
      "Could not download the release package. Check that a release is published and that you have network access to GitHub." $EXIT_ACQUIRE
    unzip -q "$STAGING/package.zip" -d "$unpacked" || die "Downloaded archive could not be unzipped." $EXIT_ACQUIRE
  fi
  ok "Package staged."
}

# --------------------------------------------------------------------------- #
# Locate install.py -> APP_ROOT (T008) and guard it (T014)
# --------------------------------------------------------------------------- #
locate_app_root() {
  local found
  found="$(find "$STAGING/unpacked" -maxdepth 3 -name install.py -type f 2>/dev/null | head -n 1)"
  [ -n "$found" ] || die \
    "Could not find install.py in the package — the archive may be malformed or empty." $EXIT_ACQUIRE
  APP_ROOT="$(cd "$(dirname "$found")" && pwd)"

  # Defense in depth (Constitution V): the build context MUST live under staging, never
  # the repo, so no local .env/.venv/inventory can leak into the image.
  case "$APP_ROOT/" in
    "$STAGING"/*) : ;;
    *) die "Internal error: app root '$APP_ROOT' is not inside the staging dir; refusing to build." ;;
  esac
  ok "Found install.py at ${APP_ROOT#"$STAGING/unpacked/"}$([ "$APP_ROOT" = "$STAGING/unpacked" ] && echo '(package root)')"
}

# --------------------------------------------------------------------------- #
# Build the throwaway image (T009, T014)
# --------------------------------------------------------------------------- #
build_image() {
  IMAGE="cisco-install-test:$$"
  # Belt-and-suspenders: a .dockerignore in the context excludes anything sensitive that
  # a --local directory copy might still carry.
  {
    printf '%s\n' "${EXCLUDES[@]}"
    printf '%s\n' "*.pyc" "~\$*.xlsx" ".dockerignore"
  } > "$APP_ROOT/.dockerignore"

  info "Building the test image (python:3.9-slim) ..."
  docker build -f "$DOCKERFILE" -t "$IMAGE" "$APP_ROOT" >/dev/null || die "Docker image build failed."
  ok "Image built: $IMAGE"
}

# --------------------------------------------------------------------------- #
# Resolve the share mount (T011)
# --------------------------------------------------------------------------- #
resolve_share() {
  if [ -n "$SHARE" ]; then
    mkdir -p "$SHARE"
    SHARE="$(cd "$SHARE" && pwd)"
    SHARE_IS_TEMP=0
  else
    SHARE="$(mktemp -d "${TMPDIR:-/tmp}/cisco-install-test-share.XXXXXX")"
    SHARE="$(cd "$SHARE" && pwd)"
    SHARE_IS_TEMP=1
  fi
}

# --------------------------------------------------------------------------- #
# Launch the interactive shell (T010, T012)
# --------------------------------------------------------------------------- #
launch() {
  local welcome
  welcome="$(cat <<EOF
${BOLD}==============================================================${RESET}
 Cisco Advisory Impact Analyzer — fresh install test sandbox
${BOLD}==============================================================${RESET}
Clean python:3.9-slim container. To test the installer end to end:

    ${BOLD}python3 install.py${RESET}

Shared folder (host <-> container): ${SHARE_MOUNT}
  Host path: ${SHARE}
  • Drop an inventory .xlsx into the host path, then either:
       cp ${SHARE_MOUNT}/*.xlsx inventory/          # then run normally
    or point the tool straight at it:
       python3 run.py --inventory ${SHARE_MOUNT}/<file>.xlsx --output-dir ${SHARE_MOUNT}
  • Reports written to ${SHARE_MOUNT} appear back on your host.

Type 'exit' to leave.$([ "$KEEP" = "1" ] && echo ' (--keep: environment will be preserved.)' || echo ' This environment is removed on exit.')
EOF
)"

  local run_args=(-e "WELCOME=$welcome" -v "$SHARE:$SHARE_MOUNT" -w "$CONTAINER_WORKDIR")

  # Non-interactive escape hatch (Principle III: scriptable without human input). When
  # INSTALL_TEST_EXEC is set, run that command in the container and exit — used for
  # automated smoke-testing of this harness. Otherwise, hand over an interactive shell.
  if [ -n "${INSTALL_TEST_EXEC:-}" ]; then
    [ "$KEEP" = "1" ] && { CONTAINER_NAME="cisco-install-test-$$"; run_args+=(--name "$CONTAINER_NAME"); } || run_args+=(--rm)
    info "Running non-interactively: ${DIM}$INSTALL_TEST_EXEC${RESET}"
    set +e
    docker run "${run_args[@]}" "$IMAGE" bash -lc "$INSTALL_TEST_EXEC"
    set -e
    return
  fi

  run_args+=(-it)
  if [ "$KEEP" = "1" ]; then
    CONTAINER_NAME="cisco-install-test-$$"
    run_args+=(--name "$CONTAINER_NAME")
  else
    run_args+=(--rm)
  fi

  info "Launching the container. You now have an interactive shell.${DIM} (Ctrl-D / exit to leave)${RESET}"
  # Print the welcome banner inside the container, then hand over an interactive shell.
  set +e
  docker run "${run_args[@]}" "$IMAGE" bash -c 'printf "%s\n\n" "$WELCOME"; exec bash'
  set -e
}

# --------------------------------------------------------------------------- #
main() {
  preflight
  acquire
  locate_app_root
  build_image
  resolve_share
  launch
}

main
