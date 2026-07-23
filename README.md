<p align="center">
  <img src="docs/TELUS_Digital_logo.png" alt="TELUS Digital" width="360">
</p>

<h1 align="center">Cisco Advisory Impact Agent</h1>

<p align="center"><strong>Agentic firewall impact analysis for Cisco security advisories</strong></p>

---

Paste a Cisco **Event Response (ERP)** link and get back a spreadsheet telling you
**which of your firewalls are affected**.

Behind the scenes it finds every security advisory referenced by the ERP, downloads each
advisory's official data (CSAF), and uses AI (via **FueliX**) to compare the affected
products and software releases against **your firewall inventory**. The result is a
timestamped Excel file listing, per advisory, the impacted firewalls.

Installed as a **[uv](https://docs.astral.sh/uv/) tool**: one install command, then a single
`caia` command you can run from any folder. Works on **macOS,
Windows, and Linux**.

---

## Before you start — what you need

| # | Requirement | How to get it |
| - | ----------- | ------------- |
| 1 | **uv** (recommended) — or just **Python 3.9+** | It manages Python for you. Not sure if you have it? See [Get uv](#get-uv) below — check first, install only if needed. Can't install uv? See [Install without uv](#install-without-uv-python-only) — you only need Python. |
| 2 | **A FueliX API key** | Get yours from <https://dev.fuelix.ai> — each person needs their own (steps below). |
| 3 | **Your firewall inventory** as an Excel `.xlsx` file in the folder you run from | You build this yourself (format below). |
| 4 | **Internet access** to `sec.cloudapps.cisco.com` and `api.fuelix.ai` | Usually already available; corporate proxies can block these. |

> Your API key is stored once, per user, via `caia --config`. The
> tool will refuse to analyze until a key is configured, and it points you to `--config`.

### Get uv

First check whether uv is already installed — then install it only if it isn't.

**1. Check if it's installed.** Works the same on macOS, Windows, and Linux — it prints a
version number if uv is there, or says `command not found` (macOS/Linux) / errors (Windows)
if it isn't:

```bash
uv --version
```

**2. Not installed? Install it** for your operating system:

- **macOS / Linux** — official standalone installer (no admin/root needed):

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- **Windows** — official standalone installer, run in **PowerShell**:

  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

Prefer a package manager? Use `brew install uv` (macOS); `winget install --id=astral-sh.uv -e`
or `scoop install main/uv` (Windows); or `pipx install uv` / `pip install uv` (any OS).

After installing, open a **new** terminal and re-run `uv --version` to confirm. More methods
and details: <https://docs.astral.sh/uv/getting-started/installation/>.

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
uv tool install cisco-advisory-impact-agent \
  --from git+https://github.com/xavient/cisco-advisory-impact-agent
```

This puts a single **`caia`** command on your PATH. There is no
repository to clone and no virtual environment to create or activate.

Then set your FueliX API key once (stored per-user, used from any folder):

```bash
caia --config
```

`--config` asks for your API key (typing is hidden) and lets you pick the AI model from a short
list (default `claude-sonnet-5`). The values are saved to a per-user config file — see
[Configuration](#configuration-your-api-key) below.

---

## Install without uv (Python only)

If you **can't install uv** (e.g. a locked-down machine), you can install and run the tool with
just **Python 3.9 or newer** — the `venv` and `pip` modules that ship with Python. No admin
rights and no extra tools are needed.

**1. Get the code.** On the GitHub page, click the green **`Code`** button → **Download ZIP**,
and unzip it. (Or `git clone` the repo.) Open a terminal **inside** the unzipped folder.

**2. Create an isolated environment and install the tool into it:**

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install .
```

This installs the `caia` command **inside that environment**. From then
on it behaves exactly like the uv install — use it as described in [Run it](#run-it) and
[Configuration](#configuration-your-api-key) (`caia --config`, then
`caia` from your inventory folder).

**Notes for this path:**

- **Activate first, every session.** In each new terminal, re-run the activation command
  (`source .venv/bin/activate` on macOS/Linux, `.venv\Scripts\Activate.ps1` on Windows) before
  using the command. If you don't want to activate, call it by full path — e.g.
  `.venv/bin/caia` — or run `python -m cisco_advisory_impact_agent.cli`.
- **Updating is manual here.** `--update` is uv-specific and will report that uv wasn't found. To
  update, download the newer ZIP and re-run `python -m pip install .` in your environment. Pass
  `--no-update-check` to skip the start-of-run version check.
- Everything else — `--config`, inventory discovery, the `output/` folder, `--dry-run`, and the
  analysis itself — works identically to the uv install.

---

## Run it

`cd` into the folder that holds your inventory `.xlsx`, then:

```bash
caia
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
caia --version   # print your version; note if a newer one exists
caia --update    # update to the latest release via uv
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

## Uninstall

Remove the tool the same way it was installed — with one command:

```bash
caia --uninstall          # asks you to confirm first
caia --uninstall --yes    # skip the prompt (for scripts / fleet cleanup)
```

This removes the `caia` command and its uv-managed environment. **Your saved settings are kept** —
the per-user config file (see [Configuration](#configuration-your-api-key) for its exact location)
is never touched, so your API key is preserved; on success the tool prints the path and you can
delete that file yourself if you want it gone.

- `--uninstall` is uv-specific. If you installed [without uv](#install-without-uv-python-only), it
  reports there's nothing to uninstall — remove it with the Python tooling you used
  (e.g. `pip uninstall cisco-advisory-impact-agent`).
- If uv can't be found, it prints the exact manual command: `uv tool uninstall cisco-advisory-impact-agent`.
- On Windows, if the running command can't remove itself, close the terminal and run that manual
  command from a fresh shell.
- The exit status is script-friendly: `0` once the tool is gone (including when it was already not
  installed), non-zero when action is still needed (declined, uv missing, or removal failed).

---

## Configuration (your API key)

`caia --config` stores your settings in a per-user file, so every run
in any folder can find them:

| OS | Config file |
| -- | ----------- |
| macOS | `~/Library/Application Support/caia/config` |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/caia/config` |
| Windows | `%APPDATA%\caia\config` |

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
4. Paste it when `caia --config` asks for it.

Each person uses **their own** key — don't share keys.

---

## Troubleshooting

- **`caia: command not found`** — the tool's bin directory isn't on
  your PATH. Run `uv tool update-shell` (or restart your terminal), or check
  `uv tool list`.
- **`No FueliX API key is configured`** — run `caia --config` to set
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

On startup the tool prints a splash banner. It is shown only on an interactive terminal, so
piped or redirected output (e.g. `caia --version > file`) stays clean; set `CAIA_NO_BANNER=1`
to suppress it everywhere.

---

## For maintainers

<details>
<summary>How it works & how to hand it out</summary>

**Package layout** (`cisco_advisory_impact_agent/`)

| Module | Responsibility |
| ------ | -------------- |
| `cli.py` | single entry point; dispatches `--help`/`--version`/`--update`/`--uninstall`/`--config` and the run |
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

**Local development:** install from a checkout with `uv tool install --from . cisco-advisory-impact-agent --force`, and run the tests with `python -m unittest discover -s tests`. See `CONTRIBUTING.md` for the release process.

</details>
