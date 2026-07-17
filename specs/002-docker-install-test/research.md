# Research: Dockerized End-to-End Installation Test

**Feature**: `002-docker-install-test` | **Date**: 2026-07-16

All spec-level unknowns were resolved during `/speckit-clarify` (base image, inventory
injection, cleanup control). This document records the remaining implementation-level
decisions and their rationale. No `NEEDS CLARIFICATION` items remain.

---

## D1. Where the release is downloaded — host vs. container

**Decision**: Download and unpack the release archive **on the host** (in the launcher
script), then feed it to the image build.

**Rationale**: Host-side download lets the script detect a failed/absent release
(`curl -fL` non-zero exit) and abort with an actionable message *before* building anything
(FR-008), matching the user's mental model ("download the package… then run install.py").
It also sidesteps Docker layer-cache staleness: a `RUN curl …` layer would be cached and
could serve an old archive, undermining "obtained fresh for each run" (FR-004). Host `curl`
re-fetches every run.

**Alternatives considered**: Download inside the Dockerfile (`RUN curl`) — rejected for
layer-cache staleness and clumsier failure handling. Download at container *runtime* via
entrypoint — rejected: pushes network failure past the point where the maintainer is
already dropped into a shell (violates "never dropped into an empty environment", SC-006).

## D2. Getting files into the container — build/COPY vs. bind-mount the release

**Decision**: **Build a throwaway image** that `COPY`s the staged release into the working
directory; run it with `docker run -it`.

**Rationale**: Files living in the container's own filesystem (not a bind mount) is what
makes it a faithful "fresh machine": `install.py` creates `.venv` and installs packages on
native container storage (fast, and identical to a real install), and there is zero risk of
the container writing into the host repo. Building also normalizes the unknown zip layout
(see D6).

**Alternatives considered**: `docker run -v <staging>:/app` (bind-mount the release) —
rejected: the installer would write `.venv` onto a host bind mount (slow on macOS Docker
Desktop's VFS, and pollutes host temp), and it blurs the clean-machine boundary.
`docker cp` into a bare container after `run` — workable but more moving parts than a
single `build` + `run`; rejected for simplicity.

## D3. Build context must exclude repo secrets

**Decision**: Set the Docker **build context to the staging temp dir** (which contains only
the unpacked release), never the repo root. Build with
`docker build -f tools/install-test/Dockerfile "$APP_ROOT"`.

**Rationale**: Constitution Principle V. The repo root contains a real `.env`, `.venv/`,
and possibly a real `inventory/*.xlsx`. If any of these entered the image the test would be
neither clean (FR-003/SC-002) nor secret-safe. Staging the release separately guarantees
only shipped files are present. For `--local <dir>`, the copy into staging applies an
exclude list (see D5).

**Alternatives considered**: Build from repo root with a `.dockerignore` — rejected as
fragile: a mistake in `.dockerignore` silently leaks secrets; a separate staging dir is
secure by construction.

## D4. Cleanup, container lifetime, and `--keep`

**Decision**: Default run uses `docker run --rm -it` (container auto-removed on exit); the
script also removes the throwaway **image** via an `EXIT` trap, and removes the staging
temp dir. `--keep` switches to a **named** container without `--rm`, retains the image, and
prints exact re-enter (`docker start -ai <name>`) and remove (`docker rm <name>` /
`docker rmi <tag>`) commands. The trap also fires on Ctrl-C/SIGINT so interruption still
cleans up (FR-010), and the script exits `130` on interrupt (Principle III).

**Rationale**: Default-clean satisfies SC-005; `--keep` supports inspecting a failed
install without relying on unreliable success/failure detection of an interactive session
(the maintainer runs `install.py` by hand). A trap is the standard robust way to guarantee
cleanup across normal exit, error, and signal.

**Alternatives considered**: Prompt on exit — rejected (extra step every run, awkward on
interrupt). Default-keep with `--clean` — rejected (weakens the clean-by-default guarantee).

## D5. Bringing an inventory in and capturing output — the mounted share

**Decision**: Bind-mount one host **share dir** (empty at launch) into the container at a
neutral path (`/work/share`). Resolution: `--share <dir>` uses that dir (created if
missing, never auto-removed); otherwise a temp dir is created and its **absolute path is
printed prominently** so the maintainer can drop an `.xlsx` in from the host. Because the
share is empty at start and separate from the app's `inventory/`, the clean-baseline
guarantee holds. The maintainer either copies the file into `inventory/` inside the shell,
or points the tool at the mount directly (`run.py --inventory /work/share/<f>.xlsx
--output-dir /work/share`), which also writes reports back to the host share (FR-011).

**Rationale**: A single empty mount cleanly reconciles FR-011 (bring a file in / get
reports out) with FR-003/SC-002 (nothing present before install). Reusing the installer's
existing `--inventory` / `--output-dir` flags avoids any new app code.

**Alternatives considered**: Mounting the host dir directly onto `/opt/app/inventory` and
`/opt/app/output` — workable but two mounts and it overlays installer-created dirs; the
single neutral share + existing flags is simpler and documented in quickstart.

## D6. Unknown zip layout — locate `install.py`

**Decision**: After unpacking, **find the directory containing `install.py`**
(`find "$STAGING" -maxdepth 3 -name install.py`) and treat its parent as the app root /
build context. Fail with an actionable message if not found.

**Rationale**: There is no release-build workflow in the repo; the `.zip` is a
manually-uploaded asset whose internal structure (flat vs. nested top-level folder) is not
guaranteed. Locating `install.py` makes the harness robust to either layout and gives a
clear error if the archive is malformed (feeds SC-006).

**Alternatives considered**: Assume files at archive root, or assume a
`cisco-advisory-impact-analyzer/` top folder — rejected as brittle guesses.

## D7. Preflight checks

**Decision**: Before doing any work, verify Docker is installed (`command -v docker`) and
the daemon is reachable (`docker info`), else exit non-zero with a message telling the
maintainer to install/start Docker (FR-007). Also verify `curl` and `unzip` are present.

**Rationale**: Fail fast with cause, never proceed into a broken run (SC-006).

## D8. Interactive shell / TTY and base shell

**Decision**: `docker run -it … /bin/bash`. `python:3.9-slim` (Debian) includes `bash`.

**Rationale**: `install.py` uses hidden-input prompts (`getpass`) and interactive
confirmations; a real TTY (`-it`) is required for FR-006. Landing in `bash` (not `sh`)
matches a comfortable interactive experience.

**Alternatives considered**: `/bin/sh` — available but a poorer interactive shell; `bash`
is present so prefer it.

## D9. `--local` release-candidate path (FR-012)

**Decision**: `--local <path>` accepts a `.zip` **or** a directory. A `.zip` is unpacked to
staging like the published archive. A **directory** is copied to staging with an exclude
list (`.venv/`, `.env`, `inventory/`, `output/`, `__pycache__/`, `.git/`, `*.pyc`,
`~$*.xlsx`) so a clean baseline is preserved even when pointed at a live working tree.

**Rationale**: Lets a maintainer validate a build before publishing (FR-012) while never
compromising the clean-baseline / secrets guarantees.

**Alternatives considered**: `.zip`-only — simpler but forces a manual zip step; supporting
a dir with excludes is more convenient and still safe.

## D10. Container user

**Decision**: Run as the image default (`root`) for v1.

**Rationale**: Keeps bind-mount writes to the share reliable across Docker Desktop and
avoids uid-mapping rabbit holes; installation behavior (`venv`, `pip`) is unaffected.

**Alternatives considered**: A dedicated non-root user for higher end-user fidelity —
deferred as a possible future refinement; noted as a minor fidelity gap, not required by
any spec requirement.
