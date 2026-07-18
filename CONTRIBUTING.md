# Contributing

This project is governed by the [constitution](.specify/memory/constitution.md). Read it
before making changes — the Core Principles and quality gates there are enforced at review
time.

## Branching & pull requests

- `main` is the single long-lived branch and must always be releasable.
- Every change reaches `main` through a pull request. Direct commits to `main` are not
  permitted.
- Features are developed on a spec branch created off `main` (see the Spec Kit flow under
  `.specify/`). Small chores may use a short-lived `chore/*` branch.
- The existing test suite (`python -m pytest`) must pass before a change is merged.

## Versioning & releases

There are **three independent version numbers** in this repo — do not conflate them:

| Version | Lives in | Tracks |
|---|---|---|
| **Product version** | `VERSION` | The shipped app; what the self-updater compares |
| **Release tag** | git tags / GitHub Releases | The commit a release is built from |
| **Constitution version** | header + Sync Impact Report in `constitution.md` | The governance document's own semver |

`VERSION` is the **single source of truth** for the product version and follows
[semantic versioning](https://semver.org/). The release tag must equal it, and CI enforces
this: the [Release workflow](.github/workflows/release.yml) refuses to publish when the
pushed tag does not match `VERSION`. This keeps the committed version, the git tag, and the
packaged `VERSION` from ever drifting.

The constitution version is separate and only bumps when you amend the constitution — never
tie it to a product release.

### Cutting a release

1. **Bump `VERSION`** to the new number (e.g. `1.3.0`) in a pull request, and merge it to
   `main`. Because bumps go through a PR, `main` always reflects the latest released version.
2. **Tag and push** the matching version. From a clean checkout of `main`:

   ```sh
   python tools/release.py          # tags $(cat VERSION) and pushes it
   # or, equivalently, by hand:
   git tag 1.3.0 && git push origin 1.3.0
   ```

   `tools/release.py` reads `VERSION` and pushes a matching tag, so you can't hand-type a
   mismatched one; pass `--dry-run` to preview.
3. **CI builds and publishes.** The Release workflow verifies `tag == VERSION`, packages the
   runtime files into `cisco-advisory-impact-analyzer.zip`, generates a SHA-256 checksum, and
   publishes the GitHub Release the self-updater downloads from.

If the tag and `VERSION` disagree, the workflow fails fast with a clear error — bump `VERSION`
in a PR first, then re-tag.

> **Bootstrap note:** installs older than the first release that shipped the self-updater must
> be re-installed once manually to get onto a version that contains `updater.py`. From then on,
> every future release is picked up automatically.
