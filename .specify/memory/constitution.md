<!--
Sync Impact Report
==================
Version change: 2.0.0 → 2.1.0
Rationale: Relaxed Principle II so that installing as a `uv` tool is the *primary, recommended*
           distribution rather than the *sole* one: a `pip install .` from a source checkout
           (into a virtual environment) is now a supported fallback for environments where `uv`
           cannot be installed. This adds an allowance without removing or redefining a principle
           (no bespoke installers return), so the bump is MINOR. The Technology & Data Constraints
           Distribution bullet was updated to match. README and docs/index.html document the
           no-uv path. This constitution's own version is independent of the product version.

Modified principles:
  - II. Cross-Platform Parity (uv is now primary/recommended; pip-from-source added as a supported fallback)
Added sections: (none)
Modified sections:
  - Technology & Data Constraints (Distribution bullet notes the pip-from-source fallback)
Removed sections: (none)

Templates requiring updates:
  - .specify/templates/plan-template.md ✅ aligned (Constitution Check resolves gates dynamically)
  - .specify/templates/spec-template.md ✅ aligned (no constitution references)
  - .specify/templates/tasks-template.md ✅ aligned (no constitution references)

Follow-up TODOs: (none)

Previous version 2.0.0 (2026-07-18): redefined Principle II for uv-tool distribution (dropped the
install.py/run.py/.venv mandate); updated Principle V (per-user config secrets) and Technology &
Data Constraints (uv-based updates, working-folder I/O). Enacted spec 004 (FR-024). MAJOR.
Previous version 1.4.0 (2026-07-17): added the "Versioning & releases" quality gate — the
committed VERSION file is the single source of truth and the Release workflow enforces tag == VERSION.
Previous version 1.3.0 (2026-07-17): allowed the self-updater's GitHub release endpoints
over HTTPS in Technology & Data Constraints.
Previous version 1.2.0 (2026-07-16): expanded the Documentation quality gate to cover
docs/index.html and README consistency.
Previous version 1.1.0 (2026-07-14): added the "Branching Strategy" section.
Previous version 1.0.0 (2026-07-14): initial ratification — Core Principles I–V,
Technology & Data Constraints, Development Workflow & Quality Gates, Governance.
-->

# Cisco Advisory Impact Analyzer Constitution

## Core Principles

### I. Standard-Library-First & Minimal Dependencies
All network access (HTTP to Cisco and to FueliX) and core logic MUST use the Python
standard library. A third-party package MAY be added ONLY when the standard library
cannot reasonably provide the capability, and each such dependency MUST be justified in
the pull request that introduces it. The runtime dependency set is deliberately small
(currently `openpyxl` for Excel and `python-dotenv` for `.env` loading); growing it is a
reviewed decision, not a default.

Rationale: A small, standard-library-based footprint keeps the tool portable, trivially
installable behind corporate proxies, and low in supply-chain attack surface — essential
for a security tool run on operators' machines.

### II. Cross-Platform Parity
The tool MUST behave identically on macOS, Windows, and Linux. Code MUST NOT assume a
specific OS, path separator, or shell; use `pathlib` and `os.name` guards rather than
hardcoded paths. The tool's primary, recommended distribution is a `uv` tool: installation
exposes a single `cisco-advisory-impact-analyzer` command on the user's PATH that runs from
any working folder, without the user cloning the repository or creating or activating a
virtual environment. For environments where `uv` cannot be installed, the tool MUST also be
installable from a source checkout with standard Python tooling (`pip install .` into a
virtual environment) as a supported fallback; no bespoke installer scripts are reintroduced.
Any per-user paths (configuration, output) MUST resolve to OS-appropriate locations.

Rationale: Operators run this on whatever machine they have; a determination that
differs by platform is a correctness bug, not a cosmetic one. A single uv-installed command
gives every platform the same install/run/update experience with no manual environment setup.

### III. CLI-First, Scriptable Interface
Every capability MUST be reachable through the command line. The tool MUST support both
an interactive mode and a fully flag-driven mode (e.g. `--url`, `--inventory`,
`--output-dir`, `--dry-run`) so it can be automated and tested without human input.
Human-readable output goes to the user via the `ui` module; errors MUST be actionable
(state what failed and how to fix it). Exit codes MUST be meaningful (non-zero on
failure; `130` on interrupt).

Rationale: Scriptability enables automation and repeatable tests; clear text I/O keeps
the tool debuggable and honest about what it did.

### IV. Conservative & Traceable Analysis (NON-NEGOTIABLE)
Impact determinations MUST NOT overstate risk. When the available data is insufficient
to decide — for example when impact depends on runtime configuration the inventory does
not track — the result MUST be `Indeterminate`, never a guess. Every determination MUST
be traceable to official Cisco source data (the ERP page and each advisory's CSAF JSON);
the tool MUST NOT invent advisory facts. AI-derived output MUST be normalized and
validated before it reaches the report.

Rationale: People act on these reports to protect firewalls. A false "Not Affected" is
dangerous and a fabricated "Affected" erodes trust; conservative, source-anchored
results are the only acceptable posture.

### V. Secrets Hygiene & Data Locality
API keys and other secrets MUST live only in the per-user configuration file (or in
environment variables) and MUST NEVER be committed, logged, or printed. The per-user
configuration file MUST be stored outside any working folder and, where the OS supports
it, restricted to owner-only permissions. The tool MUST refuse to run when a required
secret is missing rather than proceeding insecurely. Inventory data MUST stay local; only
the minimum advisory and inventory context required for a determination may be sent to the
FueliX AI endpoint. `.gitignore` MUST continue to exclude secrets, inventory, and
generated reports.

Rationale: The inventory describes an organization's security posture and the API key is
a personal credential; leaking either is a direct harm.

## Technology & Data Constraints

- Language/runtime: Python 3.9 or newer.
- Distribution: the recommended path installs, runs, and updates the tool as a `uv` tool
  (`uv tool install cisco-advisory-impact-analyzer --from git+<repo>`); `uv` is an external
  prerequisite on the user's machine, not a bundled runtime dependency. A `pip install .` from a
  source checkout (into a virtual environment) is a supported fallback where `uv` is unavailable;
  `--update` is uv-specific and does not apply on that path. The product version is single-sourced
  from the committed `VERSION` file into the package metadata at build time.
- Source of truth: Cisco Event Response (ERP) pages and official advisory CSAF JSON
  fetched from `sec.cloudapps.cisco.com`. No scraped or cached-as-authoritative
  alternatives.
- AI provider: FueliX (OpenAI-compatible Chat Completions endpoint) accessed over the
  standard library, using the current default model configured in `fuelix.py`.
- Inputs/outputs: the inventory is a user-provided `.xlsx` (sheet `FW_List`) located in the
  current working folder; reports are written as timestamped `analysis_output_*.xlsx` files
  into an `output/` folder inside that same working folder. Header matching MUST stay
  tolerant of minor naming variation.
- Networking: the analyzer itself contacts only `sec.cloudapps.cisco.com` (Cisco
  ERP/CSAF) and `api.fuelix.ai` (AI). Version and update checks additionally contact
  GitHub — `api.github.com` and `github.com` — solely to discover the latest published
  release; they send no inventory or secrets and MUST be best-effort and time-bounded so
  they never block a run. Updating is delegated to `uv`, which reinstalls the tool from the
  git source (and, like any installer, may fetch build/runtime dependencies from the Python
  package index); the tool orchestrates this rather than overlaying files in place. Adding
  any further external endpoint the analyzer itself contacts remains a reviewed change.

## Branching Strategy

- `main` is the single long-lived branch and MUST always be in a working state.
- Every spec (feature) MUST be developed on its own branch created directly off `main`.
  Spec branches MUST NOT be branched off other feature branches.
- Changes MUST reach `main` only through a pull request that merges the spec's branch
  into `main`. Direct commits to `main` are not permitted.
- Each pull request MUST verify compliance with the Core Principles (see Governance)
  before it may be merged.

Rationale: Isolating each spec on a branch off `main` keeps features independent and
`main` releasable, while the mandatory pull request provides the review checkpoint where
constitutional compliance is enforced.

## Development Workflow & Quality Gates

- Tests: extraction and parsing logic (CSAF product sections, affected releases,
  inventory matching) MUST have tests, and the existing test suite MUST pass before a
  change is merged. Changes to CSAF/ERP parsing or inventory matching MUST add or update
  tests covering the new behavior.
- Dry-run: user-facing changes that affect analysis flow SHOULD be exercisable via
  `--dry-run` (no AI call, no network write) to keep verification cheap.
- Review: pull requests MUST confirm compliance with the Core Principles, especially
  Principle IV (conservative, traceable analysis) and Principle V (secrets/data
  handling). Any new runtime dependency MUST be explicitly justified (Principle I).
- Documentation: the `README.md` and the GitHub Pages landing page (`docs/index.html`)
  MUST stay accurate for the uv install, run, update, and configuration steps whenever
  those flows change. Their instructions MUST remain consistent with each other and with
  the code — including the working-folder inventory and `output/` conventions and where
  files are read and written. A change to the instructions in one MUST be mirrored in the
  other within the same pull request.
- Versioning & releases: the committed `VERSION` file is the single source of truth for the
  product version and MUST follow semantic versioning. A release is cut by pushing a git tag
  equal to the current `VERSION` and publishing a matching GitHub Release; the Release workflow
  MUST refuse to publish when the pushed tag does not match `VERSION`. The product version is
  single-sourced from `VERSION` into the package metadata at build time, so the committed
  version, the git tag, and the version the installed tool reports never drift. Bumping
  `VERSION` is an ordinary change that reaches `main` through a pull request (see Branching
  Strategy), and the tag is pushed only after that PR merges. This product version is
  independent of this constitution's own version. See `CONTRIBUTING.md` for the release runbook.

## Governance

This constitution supersedes ad-hoc practice for the Cisco Advisory Impact Analyzer. All
changes MUST comply with the Core Principles; when a change cannot, the reviewer MUST
require either a compliant alternative or an explicit, documented justification recorded
in the pull request.

Amendments to this constitution MUST be made by editing this file, MUST include an
updated Sync Impact Report, and MUST bump the version per semantic versioning:
- MAJOR: backward-incompatible removal or redefinition of a principle or governance rule.
- MINOR: a new principle/section, or materially expanded guidance.
- PATCH: clarifications, wording, and non-semantic refinements.

Compliance is verified at review time. Dependent Spec Kit artifacts (plan, spec, and
tasks templates and their generated documents) MUST remain consistent with the principles
above; the Constitution Check in the planning workflow enforces this on each feature.

**Version**: 2.1.0 | **Ratified**: 2026-07-14 | **Last Amended**: 2026-07-18
