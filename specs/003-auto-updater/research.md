# Research: Self-Update Mechanism (Auto-Updater)

**Feature**: `003-auto-updater` | **Date**: 2026-07-17

All spec-level unknowns were resolved during `/speckit-clarify` (integrity via SHA-256,
release automation in scope, semantic-version comparison, rollback command + auto-revert,
stateless once-per-run nudge). This document records the remaining **implementation-level**
decisions and their rationale. No `NEEDS CLARIFICATION` items remain.

Repository under management: `https://github.com/xavient/cisco-advisory-impact-analyzer`.

---

## D1. Single source of truth for the installed version

**Decision**: A tracked **plain-text `VERSION`** file at the repo/package root containing just
the version string (e.g. `1.2.0`). Read by `updater.py`, the passive nudge, and `run.py
--version`. Shipped inside every release package (FR-003).

**Rationale**: The updater runs on the **base interpreter** and must work even when the code
is mid-replacement or the `.venv` is broken; a plain file is readable without importing any
app module (which a `__version__` constant would require). It is trivial for the release
workflow to stamp (`echo "$TAG" > VERSION`) and for a human/support to read. One file, one
truth — matching FR-003/FR-020.

**Alternatives considered**: `__version__` in a Python module — rejected: couples version
reads to importing code that may be broken/being-replaced, and the updater deliberately does
not import app modules. `git describe` — rejected: release packages contain no `.git`.

## D2. Discovering the latest version

**Decision**: Primary — GitHub Releases API
`GET https://api.github.com/repos/xavient/cisco-advisory-impact-analyzer/releases/latest`,
read `tag_name`. Send `Accept: application/vnd.github+json` and a `User-Agent` (GitHub
requires a UA). **Fallback** when the API is rate-limited (HTTP 403 with rate-limit headers)
or unreachable: issue a request to `https://github.com/xavient/.../releases/latest` and read
the **final redirected URL**, which resolves to `.../releases/tag/<version>`; parse the tag
from the path.

**Rationale**: The API is the same source `docs/index.html` already uses (Dependencies →
"stay consistent"). The redirect fallback does not consume the JSON API's 60/hr
unauthenticated budget, giving resilience on shared corporate egress IPs (FR-015). Both are
plain `urllib` GETs.

**Alternatives considered**: Authenticated API (higher rate limit) — rejected: requires a
token (secret) for a public repo, against Principle V's minimalism. Scraping the releases
HTML — rejected as brittle; the redirect gives the tag structurally.

## D3. Download target + integrity verification

**Decision**: After resolving the tag, download the asset from the **tag-pinned** URL
`https://github.com/xavient/.../releases/download/<tag>/cisco-advisory-impact-analyzer.zip`
(not the moving `/latest/` URL, so the bytes match the compared version) into a temp dir.
Download the sibling checksum asset
`cisco-advisory-impact-analyzer.zip.sha256` from the same release. Verify, in order, before
touching any installed file:
1. **SHA-256** of the downloaded zip equals the published digest (`hashlib.sha256`).
2. The archive is a **well-formed zip** (`zipfile.ZipFile` opens; `testzip()` is `None`).
3. The archive contains a `VERSION` entry whose content **equals the resolved tag**
   (expected-version check).

Any failure ⇒ abort with an actionable message, **no** files changed (FR-006).

**Rationale**: Implements the Q1 clarification (checksum-verified) with stdlib only. The
three layers catch, respectively, tampering/corruption, truncated/invalid archives, and
tag/package mismatches (a mis-stamped release). Pinning to the tag guarantees the checksum we
compare is the checksum of the bytes we will apply.

**Checksum file format**: single line `"<hex-sha256>  cisco-advisory-impact-analyzer.zip"`
(the `sha256sum` convention). The updater reads the first 64-hex token; tolerant of a
bare-digest line too.

**Alternatives considered**: GPG/minisign signatures (Q1 option C) — rejected by the
clarification (key-management/dependency cost). HTTPS-only (Q1 option B) — rejected by the
clarification. `SHA256SUMS` multi-file manifest — unnecessary for a single asset; the
per-asset `.sha256` is simpler.

## D4. Apply strategy — backup, overlay, recoverable window

**Decision**: Never rename/replace the whole directory (the `.venv` and open files make a
cross-platform atomic dir-swap impractical). Instead:
1. Extract the verified zip to a temp **staging** dir; locate the package root (dir
   containing `VERSION` — see D11).
2. **Back up** every currently-installed file the update will overwrite or delete (excluding
   the preserve-list) into `.update-backup/<old-version>-<timestamp>/`, preserving relative
   paths. Also copy the current `VERSION` and `MANIFEST` into the backup.
3. Write a `.update-in-progress` marker (records old version, backup path, target version).
4. **Overlay-copy** staged files onto the install dir, **skipping the preserve-list**
   (`.env`, `inventory/`, `output/`, `.venv/`), `.git/`, `.update-backup/`, and the marker.
5. Apply manifest-driven deletions (D5).
6. Refresh deps if needed (D8), update `VERSION`/`MANIFEST`, then **clear the marker**.

If any step 4–6 raises, **auto-revert**: restore from the backup and remove partially-copied
new files, then clear the marker (FR-012). If the process is hard-interrupted, the marker
survives; the next `update.py`/`run.py` invocation detects it and performs recovery,
and `--rollback` can restore explicitly.

**Rationale**: Satisfies "fully old or fully new, never a mixture, recoverable" (FR-012)
cross-platform without fragile atomic-rename tricks. The backup is the rollback source
(FR-011). The marker converts a hard interrupt into a detectable, recoverable state rather
than silent corruption.

**Alternatives considered**: Atomic dir rename/symlink swap — rejected: not reliable on
Windows, and the in-tree `.venv`/user data complicate it. Copy-new-then-swap whole tree —
rejected: doubles disk and still must exclude preserve-list.

## D5. Handling files added or removed between versions (FR-019)

**Decision**: Ship a **`MANIFEST`** (newline-separated packaged paths) inside each release
package and record the applied manifest in the install (the shipped `MANIFEST` file itself).
On apply: **add/overwrite** every path in the new manifest (except preserve-list); then
**remove** any path present in the *old* manifest but absent from the *new* one (except
preserve-list). If no old manifest exists (an install predating this feature), skip deletions
that round and `ui.warn` that stale-file cleanup is deferred to the next update.

**Rationale**: Pure overlay handles additions but leaves orphaned files when a release drops
one; the manifest diff makes removals deterministic and testable without guessing. Preserve-
list is always excluded from deletion, protecting user data.

**Alternatives considered**: Diff the whole tree against the package (treat every non-package
file as stale) — rejected: would delete user data and any local files not on the preserve-
list. Never remove files — rejected: violates FR-019's "files removed … handled".

## D6. Dependency refresh (FR-007)

**Decision**: After a successful overlay, compare old vs new `requirements.txt` (byte/hash).
If changed and a `.venv` exists, run `"<venv python>" -m pip install -r requirements.txt`
(the same interpreter-resolution `install.py`/`run.py` use: `.venv/Scripts/python.exe` on
Windows, `.venv/bin/python` elsewhere). If `.venv` is absent, print an actionable hint to run
`install.py`. Refresh failure is surfaced but does not roll back the code (the new code is
valid; deps can be re-run).

**Rationale**: Keeps the install runnable without a manual step (FR-007, SC-007) while the
updater itself stays on base Python (Principle I / recover-broken-venv constraint).

**Alternatives considered**: Always reinstall — rejected: slow and needless when unchanged.
Have the updater import/install packages itself — rejected: violates the base-Python
constraint.

## D7. Self-replacement of the updater

**Decision**: No relauncher/bootstrap for v1. `update.py`/`updater.py` are read into memory
by the interpreter before the overlay runs, so overwriting their files on disk mid-run is
safe on macOS/Linux (POSIX unlinks are fine) and on Windows (CPython reads the script fully
and does not hold an exclusive lock during execution). The overlay copies files
individually; if it fails while replacing the updater's own file, the backup still contains
the original and auto-revert/`--rollback` restores it.

**Rationale**: Simplicity (Principle: minimal moving parts) with correctness preserved by the
backup + marker. Matches the spec's "completes safely even when its own files are among those
replaced" (FR-012) without a second process.

**Alternatives considered**: Spawn a detached helper that swaps files after the parent exits
— rejected as unnecessary complexity for a script-based tool; revisit only if a real Windows
lock is observed.

## D8. Backup location & retention

**Decision**: Backups live in `.update-backup/<old-version>-<timestamp>/` inside the tool
folder (gitignored). Retain the **most recent** backup for rollback; prune older backups on a
successful update, keeping the last **2** by default (immediate + one prior) to bound disk
use. `--rollback` restores the newest backup.

**Rationale**: Satisfies FR-011 ("at minimum the most recent") and SC-009 while preventing
unbounded growth. In-folder keeps rollback self-contained and cross-platform.

**Alternatives considered**: System temp dir — rejected: may be cleared between runs, losing
rollback. Keep all backups — rejected: disk bloat.

## D9. Passive update nudge (FR-016)

**Decision**: In `run.py`, before delegating to the analyzer, perform a **best-effort**
latest-version check with a **short timeout (2 s)** wrapped in a blanket `try/except` that
swallows every error. If a newer version is found, print one `ui.info` line naming the
version and `python3 update.py`. **Stateless** (no persisted timestamp — Q5). Disable via
`--no-update-check` (consumed by `run.py`, not passed to the analyzer) or the
`CAIA_NO_UPDATE_CHECK` environment variable. Also skipped implicitly for `--version`.

**Rationale**: Implements Q5 exactly; the short timeout + swallow-all guarantees no run is
blocked, delayed noticeably, or failed when offline/rate-limited (FR-016, US4-AS2).

**Alternatives considered**: Background thread that prints on completion — rejected: more
complex, risks interleaved output. Once-per-day with a state file — rejected by Q5
(statefulness).

## D10. Release automation (FR-020 / FR-021)

**Decision**: `.github/workflows/release.yml` triggers on **tag push** matching `[0-9]+.*`
(and/or release publication). Steps: check out at the tag; **stamp** `VERSION` with the tag;
**generate** `MANIFEST` (the list of packaged paths); **build** a flat zip
`cisco-advisory-impact-analyzer.zip` containing only runtime files (see D12 exclude list);
compute `cisco-advisory-impact-analyzer.zip.sha256`; **upload** both as release assets. The
job uses only standard runner tooling (`zip`, `sha256sum`, `gh`/action upload).

**Rationale**: The only way to *guarantee* embedded `VERSION` == tag and a present, correct
checksum on every release (Q2), removing the "version drift" and "forgot the checksum"
failure modes. Keeps the maintainer flow to "push a tag".

**Alternatives considered**: A documented manual/scripted procedure (Q2 option B) — rejected
by the clarification. Building the zip in the updater — nonsensical (the updater consumes it).

## D11. Package archive layout

**Decision**: The workflow produces a **flat** archive (runtime files at the zip root,
including `VERSION` and `MANIFEST`). For robustness the updater does **not** assume flatness:
after extraction it locates the package root as the directory that contains a `VERSION` file
(searching depth ≤ 2), mirroring 002's "find `install.py`" robustness.

**Rationale**: Flat keeps overlay mapping trivial; the locate-by-`VERSION` guard makes the
updater tolerant of a nested top-level folder (e.g. if the asset is ever regenerated
differently), avoiding a brittle hard-coded prefix.

**Alternatives considered**: Assume GitHub source-zip nesting (`<repo>-<sha>/`) — rejected:
this is a custom asset we control; nesting is not guaranteed either way, so detect it.

## D12. Package contents / exclude list

**Decision**: The release package **includes** runtime files: `*.py` (analyzer, cisco,
fuelix, inventory, report, ui, install, run, update, updater), `requirements.txt`, `README.md`,
`.env.example`, `docs/`, `VERSION`, `MANIFEST`. It **excludes** user/local data and dev-only
artifacts: `.env`, `.venv/`, `inventory/`, `output/`, `.git/`, `__pycache__/`, `*.pyc`,
`.github/`, `.specify/`, `specs/`, `brds/`, `tests/`, `tools/`, `.DS_Store`, `.claude/`,
`.update-backup/`.

**Rationale**: Ships what an end user needs to run and update, nothing more (matches the spec
Assumption and Out-of-Scope). Excluding `tests/`, `specs/`, `brds/` keeps the package lean;
excluding user/local data upholds Principle V and the preserve-list invariant.

**Alternatives considered**: Ship everything (source-zip style) — rejected: leaks dev
scaffolding and bloats the package; complicates the manifest/overlay.

## D13. Endpoint constant & the constitution reviewed change

**Decision**: `updater.py` defines constants `REPO = "xavient/cisco-advisory-impact-analyzer"`
and derived GitHub URLs (overridable via an env var, e.g. `CAIA_UPDATE_REPO`, for testing
against a fork). Contacted hosts: `api.github.com`, `github.com`,
`objects.githubusercontent.com` (asset CDN redirect). This is logged as the constitution's
**reviewed change** (new external endpoint); a follow-up should amend the constitution's
allowed-endpoints list to include GitHub for the updater.

**Rationale**: Centralizes the endpoint (like `cisco.BASE`), enables fork-testing without
code edits, and makes the reviewed-change explicit for the PR.

**Alternatives considered**: Hard-code with no override — rejected: blocks integration
testing against a throwaway repo.

## D14. Exit codes & error surface (Principle III)

**Decision**: `update.py` exit codes — `0` success, up-to-date, or ahead (no-op); `1` generic
failure; `2` invalid usage; `3` could not determine latest (network/rate-limit); `4`
download/verification failed (no changes made); `5` apply failed **and auto-revert
succeeded** (install restored to old version); `6` apply failed **and revert also failed**
(install may need manual `--rollback`); `130` interrupt (via the existing `run_cli`-style
handler). Every failure prints an actionable `ui.fail` + hint. `run.py --version` prints the
`VERSION` and exits `0`.

**Rationale**: Distinct non-zero codes per failure class (Principle III) make the tool
scriptable and support triage; separating code 5 vs 6 tells an operator whether their install
self-healed or needs attention.

**Alternatives considered**: Single non-zero for all failures — rejected: less scriptable and
hides the critical "revert failed" case.
