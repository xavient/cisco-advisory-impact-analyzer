<!--
Sync Impact Report
==================
Version change: 1.2.0 → 1.3.0
Rationale: Added GitHub as an allowed external endpoint for the self-updater
           (update.py / updater.py), recording the "reviewed change" mandated by the
           Technology & Data Constraints section. New allowed endpoint / material
           guidance → MINOR bump. The analyzer's own contacted endpoints are unchanged.

Modified principles: (none)
Added sections: (none)
Modified sections:
  - Technology & Data Constraints (Networking bullet expanded to allow the updater's
    GitHub release endpoints over HTTPS)
Removed sections: (none)

Templates requiring updates:
  - .specify/templates/plan-template.md ✅ aligned (Constitution Check resolves gates
    dynamically from this file — no hardcoded references to update)
  - .specify/templates/spec-template.md ✅ aligned (no constitution references)
  - .specify/templates/tasks-template.md ✅ aligned (no constitution references)

Follow-up TODOs: (none)

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
hardcoded paths. Setup and execution MUST work through the provided `install.py` /
`run.py` entry points and the self-contained `.venv`, without requiring the user to
activate the virtual environment manually.

Rationale: Operators run this on whatever machine they have; a determination that
differs by platform is a correctness bug, not a cosmetic one.

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
API keys and other secrets MUST live only in the untracked `.env` file and MUST NEVER be
committed, logged, or printed. The tool MUST refuse to run when a required secret is
missing rather than proceeding insecurely. Inventory data MUST stay local; only the
minimum advisory and inventory context required for a determination may be sent to the
FueliX AI endpoint. `.gitignore` MUST continue to exclude secrets, inventory, and
generated reports.

Rationale: The inventory describes an organization's security posture and the API key is
a personal credential; leaking either is a direct harm.

## Technology & Data Constraints

- Language/runtime: Python 3.9 or newer.
- Source of truth: Cisco Event Response (ERP) pages and official advisory CSAF JSON
  fetched from `sec.cloudapps.cisco.com`. No scraped or cached-as-authoritative
  alternatives.
- AI provider: FueliX (OpenAI-compatible Chat Completions endpoint) accessed over the
  standard library, using the current default model configured in `fuelix.py`.
- Inputs/outputs: inventory is read from `inventory.xlsx` (sheet `FW_List`); reports are
  written as timestamped `analysis_output_*.xlsx` files. Header matching MUST stay
  tolerant of minor naming variation.
- Networking: the analyzer itself contacts only `sec.cloudapps.cisco.com` (Cisco
  ERP/CSAF) and `api.fuelix.ai` (AI). The self-updater (`update.py` / `updater.py`)
  additionally contacts GitHub — `api.github.com`, `github.com`, and
  `objects.githubusercontent.com` — solely to discover the latest release and download the
  checksum-verified release package over HTTPS; it sends no inventory or secrets. Adding
  any further external endpoint remains a reviewed change.

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
  MUST stay accurate for install and run steps whenever those flows change. Their
  installation instructions MUST remain consistent with each other and with the code —
  including the `inventory/` and `output/` folder conventions and where files are placed
  or written. A change to the instructions in one MUST be mirrored in the other within the
  same pull request.

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

**Version**: 1.3.0 | **Ratified**: 2026-07-14 | **Last Amended**: 2026-07-17
