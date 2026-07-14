# Cisco Advisory Impact Analyzer

Paste a Cisco **Event Response (ERP)** link and get back a spreadsheet telling you
**which of your firewalls are affected**.

Behind the scenes it finds every security advisory referenced by the ERP, downloads each
advisory's official data (CSAF), and uses AI (via **FueliX**) to compare the affected
products and software releases against **your firewall inventory**. The result is a
timestamped Excel file listing, per advisory, the impacted firewalls — or `Indeterminate`
/ `Not Affected`.

Works on **macOS, Windows, and Linux**.

---

## Before you start — what you need

Please make sure you have all four of these. The tool will not run without them.

| # | Requirement | How to get it |
| - | ----------- | ------------- |
| 1 | **Python 3.9 or newer** | Install once from the links below. |
| 2 | **A FueliX API key** | Get yours from <https://dev.fuelix.ai> — each person needs their own (steps below). |
| 3 | **Your firewall inventory** as an Excel file named **`inventory.xlsx`** | You build this yourself (format below). |
| 4 | **Internet access** to `sec.cloudapps.cisco.com` and `api.fuelix.ai` | Usually already available; corporate proxies can block these. |

> The API key is stored in a small file called **`.env`** in the tool's folder. **The
> installer creates this file for you** and asks for your key — you do not need to make it
> by hand. The tool will refuse to run if the `.env` file or the key is missing.

**Installing Python (one time):**
- **Windows:** <https://www.python.org/downloads/windows/> — on the first installer
  screen, tick **“Add python.exe to PATH”** before clicking Install. (Or install “Python”
  from the Microsoft Store.)
- **macOS:** <https://www.python.org/downloads/macos/> (or `brew install python`).
- **Linux:** use your package manager, e.g. `sudo apt install python3 python3-venv`.

### Inventory format

`inventory.xlsx` must have a sheet named **`FW_List`** with these columns (header names
can vary slightly — matching is flexible):

| FirewallName | Model | Firewalltype | IOS version | Priority |
| ------------ | ----- | ------------ | ----------- | -------- |
| FWLOC1-001 | ISA-3000 | FTD | 7.4.2 | 2 |
| FWLOC3-004 | ASA 5506 | ASA | 9.16(4)67 | 1 |

`Firewalltype` should be `FTD`, `ASA`, or `ASAv`. If you don't have a template, run the
installer first — it will tell you where to put the file.

---

## Install (one time)

**1. Get the tool.** On the GitHub page, click the green **`Code`** button → **Download
ZIP**. Unzip it. You'll get a folder (e.g. `cisco-advisory-impact-analyzer`).

**2. Put your inventory in that folder.** Copy your `inventory.xlsx` into the unzipped
folder, next to the files like `install.py` and `run.py`.

**3. Open a terminal *in that folder*.**
- **Windows:** open the folder in File Explorer, then Shift + right-click an empty area →
  **“Open PowerShell window here.”**
- **macOS:** open **Terminal**, type `cd ` (with a space), then drag the folder onto the
  Terminal window and press Enter.
- **Linux:** right-click the folder → **“Open Terminal Here,”** or `cd` into it.

**4. Run the installer.**

```bash
python3 install.py        # macOS / Linux
python install.py         # Windows  (if that fails, try:  py install.py)
```

The installer will:
1. check your Python version,
2. create a private, self-contained environment (`.venv`) — it does **not** touch your
   system Python,
3. install the two small packages it needs,
4. **ask for your FueliX API key** (typing is hidden) and save it to `.env`,
5. confirm your `inventory.xlsx` is present,
6. run a quick self-check.

When it finishes you'll see **“Setup complete.”**

---

## Run it

In the same folder, each time you want to analyze an ERP:

```bash
python3 run.py            # macOS / Linux
python run.py             # Windows  (or:  py run.py)
```

Then **paste the Cisco ERP link** when prompted, for example:

```
https://sec.cloudapps.cisco.com/security/center/viewErp.x?alertId=ERP-75736
```

(A single advisory link — `.../CiscoSecurityAdvisory/cisco-sa-...` — also works.)

The tool finds all advisories, analyzes each one against your inventory, and writes a file
named **`analysis_output_<date>_<time>.xlsx`** in the same folder.

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

## The `.env` file and your API key

Your FueliX API key lives in a small file called **`.env`** in the tool's folder. The
installer creates this file and asks for your key, so normally you just paste the key when
prompted. **The tool will not run without it.**

### Getting your FueliX API key

1. Go to **<https://dev.fuelix.ai>** and log in.
2. You should already have a **Default** project. Click its **`...`** menu, then **View**.
3. Under **API keys**, a key should already be listed. **Copy** it.
4. Paste it into the installer when it asks for `FUELIX_API_KEY` (or into `.env`, below).

Each person uses **their own** key — don't share keys.

### What's in `.env`

```
FUELIX_API_KEY=your-key-here
FUELIX_MODEL=claude-sonnet-5
FUELIX_BASE_URL=https://api.fuelix.ai/v1
```

- **`FUELIX_API_KEY`** (required) — your personal key from the Dev Portal (steps above).
- **`FUELIX_MODEL`** (optional) — the AI model to use. The default is `claude-sonnet-5`;
  change it only if your organization has a different model id enabled.
- **`FUELIX_BASE_URL`** (optional) — the API endpoint; leave as-is unless told otherwise.
- Keep `.env` **private** — it contains your key. Don't commit it or share it.

If you'd rather set it up manually instead of using the installer, copy the provided
**`.env.example`** to **`.env`** and paste your key in.

---

## Troubleshooting

- **`python: command not found` / `'python' is not recognized`** — Python isn't installed
  or isn't on your PATH. On macOS/Linux use `python3`; on Windows try `py` instead of
  `python`, or reinstall Python with **“Add python.exe to PATH”** ticked.
- **`Missing FUELIX_API_KEY`** — your `.env` has no key. Re-run `python install.py`, or
  open `.env` and set `FUELIX_API_KEY=...`.
- **`No inventory spreadsheet found`** — put your `inventory.xlsx` in this folder.
- **Dependency install failed / `pip` errors** — usually a network or corporate-proxy
  block on PyPI. Confirm you have internet access and try again; ask IT if PyPI is blocked.
- **Everything comes back `Indeterminate`** — either the advisories are genuinely
  config-dependent / FMC-only, or the tool couldn't reach `sec.cloudapps.cisco.com`. Run
  `python run.py --dry-run` to see what was downloaded without calling the AI.
- **`FueliX API error` (4xx)** — check your API key is correct and that `FUELIX_MODEL` is a
  model your org has enabled (in the FueliX Dev Portal, <https://dev.fuelix.ai>).

---

## Advanced options

Extra flags can be passed through `run.py`, e.g. `python run.py --dry-run`:

| Flag | Purpose |
| ---- | ------- |
| `--url <URL>` | supply the ERP/advisory URL instead of being prompted |
| `--inventory <PATH>` | use an inventory file elsewhere |
| `--sheet <NAME>` | inventory sheet name (default `FW_List`) |
| `--output-dir <DIR>` | where to write the report (default: this folder) |
| `--dry-run` | run everything **without** calling the AI (no API key needed) — handy to test setup |
| `--no-keep-temp` | delete the downloaded CSAF files when finished |

---

## For maintainers

<details>
<summary>How it works & how to hand it out</summary>

**Modules**

| File | Responsibility |
| ---- | -------------- |
| `analyzer.py` | orchestration + interactive prompts |
| `cisco.py` | fetch ERP/CSAF, discover advisories, extract sections + affected versions |
| `inventory.py` | read the inventory, collapse it into distinct model/type/version combos |
| `fuelix.py` | OpenAI-compatible FueliX client + per-advisory assessment |
| `report.py` | write the styled Excel report |
| `install.py` / `run.py` | cross-platform installer and launcher |
| `ui.py` | terminal colors + prompts (no dependencies) |

To keep the AI prompt small and reliable, the inventory rows are collapsed into distinct
`(model, type, version)` combos; the AI returns which combos are impacted and the tool
expands them back into firewall names.

**Handing it to teammates:** just point them at the GitHub repo — they follow the Install
section above. Secrets and per-user data (`.env`, `.venv/`, `inventory.xlsx`,
`analysis_output_*.xlsx`) are excluded via `.gitignore`, so they never ship in the repo.
Each teammate supplies their own API key and inventory.

</details>
