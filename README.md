# Cisco Advisory Impact Analyzer

Paste a Cisco **Event Response (ERP)** link and get back a spreadsheet telling you
**which of your firewalls are affected**.

Behind the scenes it finds every security advisory referenced by the ERP, downloads each
advisory's official data (CSAF), and uses AI (via **FueliX**) to compare the affected
products and software releases against **your firewall inventory**. The result is a
timestamped Excel file listing, per advisory, the impacted firewalls — or `Indeterminate`
/ `Not Affected`.

Installed as a **[uv](https://docs.astral.sh/uv/) tool**: one install command, then a single
`cisco-advisory-impact-analyzer` command you can run from any folder. Works on **macOS,
Windows, and Linux**.

---

## Before you start — what you need

| # | Requirement | How to get it |
| - | ----------- | ------------- |
| 1 | **uv** | Install once — see <https://docs.astral.sh/uv/getting-started/installation/>. uv manages Python for you, so you don't need to install Python separately. |
| 2 | **A FueliX API key** | Get yours from <https://dev.fuelix.ai> — each person needs their own (steps below). |
| 3 | **Your firewall inventory** as an Excel `.xlsx` file in the folder you run from | You build this yourself (format below). |
| 4 | **Internet access** to `sec.cloudapps.cisco.com` and `api.fuelix.ai` | Usually already available; corporate proxies can block these. |

> Your API key is stored once, per user, via `cisco-advisory-impact-analyzer --config`. The
> tool will refuse to analyze until a key is configured, and it points you to `--config`.

### Inventory format

Your inventory `.xlsx` must have a sheet named **`FW_List`** with these columns (header
names can vary slightly — matching is flexible):

| FirewallName | Model | Firewalltype | IOS version | Priority |
| ------------ | ----- | ------------ | ----------- | -------- |
| FWLOC1-001 | ISA-3000 | FTD | 7.4.2 | 2 |
| FWLOC3-004 | ASA 5506 | ASA | 9.16(4)67 | 1 |

`Firewalltype` should be `FTD`, `ASA`, or `ASAv`. Put the file in whatever folder you plan to
run the tool from; the report is written to an `output/` folder next to it.

---

## Install (one time)

With `uv` on your machine, install the tool straight from GitHub:

```bash
uv tool install cisco-advisory-impact-analyzer \
  --from git+https://github.com/xavient/cisco-advisory-impact-analyzer
```

This puts a single **`cisco-advisory-impact-analyzer`** command on your PATH. There is no
repository to clone and no virtual environment to create or activate.

Then set your FueliX API key once (stored per-user, used from any folder):

```bash
cisco-advisory-impact-analyzer --config
```

`--config` asks for your API key (typing is hidden) and lets you pick the AI model from a short
list (default `claude-sonnet-5`). The values are saved to a per-user config file — see
[Configuration](#configuration-your-api-key) below.

---

## Run it

`cd` into the folder that holds your inventory `.xlsx`, then:

```bash
cisco-advisory-impact-analyzer
```

The tool finds your inventory in that folder (if there's more than one candidate, it lists them
and lets you pick), then **prompts for the Cisco ERP link**, for example:

```
https://sec.cloudapps.cisco.com/security/center/viewErp.x?alertId=ERP-75736
```

(A single advisory link — `.../CiscoSecurityAdvisory/cisco-sa-...` — also works.)

After you confirm, it analyzes each advisory against your inventory and writes a file named
**`analysis_output_<date>_<time>.xlsx`** into an **`output`** folder inside your current folder
(created automatically). Each run adds a new timestamped file, so previous reports are kept.

Press **Ctrl+C** at any time to cancel cleanly.

### Understanding the output

The spreadsheet has three columns:

| Column | What it means |
| ------ | ------------- |
| **Vendor Advisory#** | the advisory id (e.g. `cisco-sa-...`) |
| **Effected Product Description** | a short summary of the affected products |
| **Expected Assessment** | the impacted firewalls (one `FirewallName` per line), or `Indeterminate` / `Not Affected` |

- **A list of firewall names** — those devices match the affected product and software
  release; review them.
- **`Not Affected`** — the advisory applies to ASA/FTD, but none of your devices are on an
  affected release.
- **`Indeterminate`** — impact can't be decided from the inventory alone. Usually because
  it depends on runtime configuration you don't track (High Availability, VPN/SAML, file
  policy, Snort settings, …) or because it only affects products you don't have (FMC,
  cdFMC, SCC, Snort). These need a manual look.

---

## Keeping it up to date

New releases improve the advisory-matching logic, so it's worth staying current:

```bash
cisco-advisory-impact-analyzer --version   # print your version; note if a newer one exists
cisco-advisory-impact-analyzer --update    # update to the latest release via uv
```

`--update` checks the latest published release and, if newer, reinstalls the tool with `uv`
(pinned to that release). When you start a normal run and a newer version is available, the tool
also offers to update first — answer **yes** to update (it then asks you to re-run) or **no** to
continue on your current version. The version check is best-effort and time-bounded, so it never
blocks a run; skip it with `--no-update-check` or `CAIA_NO_UPDATE_CHECK=1`.

> On Windows, the running command can't overwrite itself while it's open. If an in-place update
> reports the file is in use, close the terminal and run the `uv tool install … --force` command
> it prints from a fresh shell.

---

## Configuration (your API key)

`cisco-advisory-impact-analyzer --config` stores your settings in a per-user file, so every run
in any folder can find them:

| OS | Config file |
| -- | ----------- |
| macOS | `~/Library/Application Support/cisco-advisory-impact-analyzer/config` |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/cisco-advisory-impact-analyzer/config` |
| Windows | `%APPDATA%\cisco-advisory-impact-analyzer\config` |

The file is `KEY=value` and looks like this (you may edit it by hand):

```
FUELIX_API_KEY=your-key-here
FUELIX_MODEL=claude-sonnet-5
FUELIX_BASE_URL=https://api.fuelix.ai/v1
```

- **`FUELIX_API_KEY`** (required) — your personal key from the Dev Portal (steps below).
- **`FUELIX_MODEL`** (optional) — chosen from a menu during `--config`; default `claude-sonnet-5`.
- **`FUELIX_BASE_URL`** (optional) — the API endpoint; **not** prompted by `--config`. Change it
  only by editing the file or setting the environment variable, and only if told to.

Precedence for every setting is **environment variable → config file → built-in default**, so
`FUELIX_API_KEY` / `FUELIX_MODEL` / `FUELIX_BASE_URL` in the environment still work for
automation. On macOS/Linux the config file is created owner-only (`chmod 600`). Keep it private
— it contains your key.

### Getting your FueliX API key

1. Go to **<https://dev.fuelix.ai>** and log in.
2. You should already have a **Default** project. Click its **`...`** menu, then **View**.
3. Under **API keys**, a key should already be listed. **Copy** it.
4. Paste it when `cisco-advisory-impact-analyzer --config` asks for it.

Each person uses **their own** key — don't share keys.

---

## Troubleshooting

- **`cisco-advisory-impact-analyzer: command not found`** — the tool's bin directory isn't on
  your PATH. Run `uv tool update-shell` (or restart your terminal), or check
  `uv tool list`.
- **`No FueliX API key is configured`** — run `cisco-advisory-impact-analyzer --config` to set
  your key, or export `FUELIX_API_KEY`.
- **`No valid inventory .xlsx found`** — run the tool from the folder that holds your inventory
  `.xlsx` (sheet `FW_List`), or pass `--inventory PATH`.
- **`--update` says uv wasn't found** — uv isn't on the tool's PATH. Re-run the
  `uv tool install … --from git+…` command from a shell where `uv` works.
- **Everything comes back `Indeterminate`** — either the advisories are genuinely
  config-dependent / FMC-only, or the tool couldn't reach `sec.cloudapps.cisco.com`. Run with
  `--dry-run` to see what was downloaded without calling the AI.
- **`FueliX API error` (4xx)** — check your API key is correct and that `FUELIX_MODEL` is a
  model your org has enabled (in the FueliX Dev Portal, <https://dev.fuelix.ai>).

---

## Advanced / automation

The analysis is fully flag-driven for scripting — supplying an input skips its prompt, and a
fully-specified run has no prompts at all (no update offer, no confirmation):

| Flag | Purpose |
| ---- | ------- |
| `--url <URL>` | supply the ERP/advisory URL instead of being prompted |
| `--inventory <PATH>` | use a specific inventory file, bypassing folder discovery |
| `--sheet <NAME>` | inventory sheet name (default `FW_List`) |
| `--output-dir <DIR>` | where to write the report (default: `./output`) |
| `--dry-run` | run everything **without** calling the AI (no API key needed) — handy to test setup |
| `--no-keep-temp` | delete the downloaded CSAF files when finished |
| `--no-update-check` | skip the start-of-run version check |

---

## For maintainers

<details>
<summary>How it works & how to hand it out</summary>

**Package layout** (`cisco_advisory_impact_analyzer/`)

| Module | Responsibility |
| ------ | -------------- |
| `cli.py` | single entry point; dispatches `--help`/`--version`/`--update`/`--config` and the run |
| `analyzer.py` | run flow + interactive prompts (working-folder inventory + `output/`) |
| `cisco.py` | fetch ERP/CSAF, discover advisories, extract sections + affected versions |
| `inventory.py` | read the inventory, collapse it into distinct model/type/version combos |
| `fuelix.py` | OpenAI-compatible FueliX client + per-advisory assessment |
| `report.py` | write the styled Excel report |
| `config.py` | per-user configuration (paths, precedence, `--config`) |
| `version.py` | installed version, GitHub release discovery, uv-based update |
| `ui.py` | terminal colors + prompts (no dependencies) |

The version is single-sourced from the committed `VERSION` file into the package metadata and
reported at runtime via `importlib.metadata`. To keep the AI prompt small and reliable, the
inventory rows are collapsed into distinct `(model, type, version)` combos; the AI returns which
combos are impacted and the tool expands them back into firewall names.

**Handing it to teammates:** point them at the install command above. Each teammate supplies
their own API key (`--config`) and inventory.

**Local development:** install from a checkout with `uv tool install --from . cisco-advisory-impact-analyzer --force`, and run the tests with `python -m unittest discover -s tests`. See `CONTRIBUTING.md` for the release process.

</details>
