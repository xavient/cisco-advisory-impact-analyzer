# Contract: Release Artifacts & Automation

**Feature**: `003-auto-updater` | **Date**: 2026-07-17

This is the maintainer/CI-side counterpart of the CLI contract. It defines what every
published release MUST contain so the updater's version and integrity checks are always
accurate (FR-020, FR-021). The updater in [cli.md](./cli.md) consumes exactly these artifacts.

## Trigger

The release workflow (`.github/workflows/release.yml`) runs when a **version tag is pushed**
(pattern like `[0-9]+.[0-9]+.[0-9]+`, matching existing tags `1.0.0`, `1.1.0`) and/or when a
GitHub release is published. It requires no manual packaging step.

## Produced release assets

| Asset | Format | Purpose |
|-------|--------|---------|
| `cisco-advisory-impact-analyzer.zip` | Flat zip of runtime files (D11/D12) | The package the updater downloads and applies. Reachable at both the tag-pinned URL `…/releases/download/<tag>/…` and the moving `…/releases/latest/download/…` URL. |
| `cisco-advisory-impact-analyzer.zip.sha256` | one line: `<64-hex>  cisco-advisory-impact-analyzer.zip` | SHA-256 the updater verifies before applying (FR-006). |

## Package contents contract

The zip **MUST**:
- Contain a root `VERSION` file whose content **equals the release tag** (no leading `v`).
- Contain a root `MANIFEST` listing every packaged path (newline-separated POSIX paths).
- Contain the runtime files needed to run and update the tool: the analyzer/support `*.py`
  (`analyzer.py`, `cisco.py`, `fuelix.py`, `inventory.py`, `report.py`, `ui.py`),
  `install.py`, `run.py`, `update.py`, `updater.py`, `requirements.txt`, `README.md`,
  `.env.example`, and `docs/`.

The zip **MUST NOT** contain user/local data or dev-only artifacts (Principle V, D12):
`.env`, `.venv/`, `inventory/`, `output/`, `.git/`, `.github/`, `.specify/`, `specs/`,
`brds/`, `tests/`, `tools/`, `__pycache__/`, `*.pyc`, `.claude/`, `.DS_Store`,
`.update-backup/`.

## Invariants (map to spec)

- Embedded `VERSION` == tag for 100% of releases → FR-020, SC-005 (no version drift).
- Every release has a matching `.sha256` → FR-006 is always satisfiable.
- Automated, no manual packaging → FR-021.
- Latest tag is discoverable via the GitHub Releases API `tag_name` (same source the landing
  page uses) → FR-004, Dependencies.

## Verification

A release is valid when: downloading the two assets, recomputing `sha256(zip)` equals the
`.sha256` content, the zip opens cleanly, and its root `VERSION` equals the tag. This is
exactly the updater's pre-apply check (cli.md step 6) and is exercised in
[quickstart.md](../quickstart.md) scenario 7.
