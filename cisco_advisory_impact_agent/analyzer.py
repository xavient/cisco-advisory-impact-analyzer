#!/usr/bin/env python3
"""
Cisco Advisory Impact Agent (AI-driven)
=======================================
Given a Cisco Event Response (ERP) URL, find every referenced security advisory,
download its CSAF, extract the "Vulnerable Products" / "Products Confirmed Not
Vulnerable" sections plus the enumerated affected releases, and ask the FueliX AI
which firewalls in your inventory are impacted. Writes a timestamped Excel report.

This module holds the analysis run flow; the command-line entry point is
`cisco_advisory_impact_agent.cli`. Inputs are read from, and the report is written
to, the current working folder (an `output/` subfolder), so the tool works from any
folder once installed.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cisco_advisory_impact_agent import cisco, config, fuelix
from cisco_advisory_impact_agent import inventory as inv
from cisco_advisory_impact_agent import ui
from cisco_advisory_impact_agent.report import write_report

CISCO_HOST = "sec.cloudapps.cisco.com"


def die(msg, hint=None):
    ui.fail(msg)
    if hint:
        ui.plain(ui.dim(hint))
    sys.exit(1)


def default_output_dir():
    """Reports go to ./output in the current working folder (Assumptions, FR-020)."""
    return Path.cwd() / "output"


# --------------------------------------------------------------------------- #
# Folders
# --------------------------------------------------------------------------- #
def ensure_dirs(*dirs):
    """Create each folder (and parents) if missing. A missing folder is never an
    error; an already-existing folder is left untouched."""
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Inventory discovery & selection
# --------------------------------------------------------------------------- #
def _is_valid_inventory(path, sheet):
    """True if `path` parses as an inventory with the required structure and rows."""
    try:
        return bool(inv.load_inventory(path, sheet))
    except Exception:  # noqa: BLE001 - InventoryError, BadZipFile, empty file, etc.
        return False


def _xlsx_candidates(folder):
    """The .xlsx files in `folder`, ignoring Excel lock/temp files (~$*.xlsx)."""
    return sorted(p for p in folder.glob("*.xlsx") if not p.name.startswith("~$"))


def resolve_inventory(explicit=None, interactive=True, folder=None, sheet="FW_List"):
    """Return the inventory .xlsx to analyze.

    With --inventory (explicit) the given file is used directly (validated when loaded).
    Otherwise the current working folder is searched: exactly one valid inventory is used
    silently; if there is not exactly one, an interactive session lists the folder's files
    and lets the user pick (validating and re-prompting), while a non-interactive session
    fails with an actionable error (FR-015, FR-016, FR-025).
    """
    if explicit:
        p = Path(explicit)
        if not p.exists():
            die(f"Inventory file not found: {p}")
        return p

    folder = Path(folder) if folder else Path.cwd()
    valid = [p for p in _xlsx_candidates(folder) if _is_valid_inventory(p, sheet)]
    if len(valid) == 1:
        return valid[0]

    if not interactive:
        if not valid:
            die(f"No valid inventory .xlsx found in {folder}.",
                hint="Place your firewall inventory .xlsx (sheet 'FW_List') here, or pass "
                     "--inventory PATH.")
        die(f"More than one valid inventory .xlsx found in {folder}.",
            hint="Choose one with --inventory PATH.")
    return _pick_inventory(folder, sheet)


def _pick_inventory(folder, sheet):
    """Interactively list the folder's files and let the user pick a valid inventory."""
    files = sorted(
        p for p in folder.iterdir()
        if p.is_file() and not p.name.startswith("~$") and not p.name.startswith(".")
    )
    if not files:
        die(f"No files to analyze in {folder}.",
            hint="Place your firewall inventory .xlsx (sheet 'FW_List') here, then run again.")

    ui.plain()
    ui.system("Select the inventory file to analyze:")
    names = [p.name for p in files]
    while True:
        choice = ui.select("Inventory", names)
        chosen = folder / choice
        if _is_valid_inventory(chosen, sheet):
            return chosen
        ui.warn(f"'{choice}' is not a valid inventory (need an .xlsx with sheet "
                f"'{sheet}' and the expected columns). Please choose another.")


# --------------------------------------------------------------------------- #
# URL validation / prompting
# --------------------------------------------------------------------------- #
def is_valid_cisco_url(url):
    try:
        u = urlparse(url.strip())
    except Exception:  # noqa: BLE001
        return False
    if u.scheme not in ("http", "https") or u.netloc.lower() != CISCO_HOST:
        return False
    if "viewErp" in u.path:
        alert = parse_qs(u.query).get("alertId", [""])[0]
        return alert.upper().startswith("ERP-")
    return bool(cisco.SLUG_RE.search(u.path))


def prompt_for_url():
    ui.plain()
    ui.system("Paste the Cisco Event Response (ERP) URL.")
    ui.plain(ui.dim("Example: https://sec.cloudapps.cisco.com/security/center/"
                    "viewErp.x?alertId=ERP-75736"))
    for _ in range(5):
        url = ui.ask("URL")
        if not url:
            die("No URL provided. Exiting.")
        if is_valid_cisco_url(url):
            return url
        ui.warn(f"That doesn't look like a Cisco advisory/ERP URL on {CISCO_HOST}. "
                "Please try again.")
    die("Too many invalid attempts. Exiting.")


# --------------------------------------------------------------------------- #
# Per-advisory processing
# --------------------------------------------------------------------------- #
def download_and_extract(slug, temp_dir):
    """Fetch a CSAF, save it to temp_dir, and return the extracted advisory dict
    (or None if the CSAF could not be retrieved/parsed)."""
    csaf = cisco.fetch_json(cisco.csaf_url(slug))
    if not csaf:
        return None
    try:
        (temp_dir / f"{slug}.json").write_text(_dumps(csaf), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass  # saving the raw file is best-effort; extraction is what matters
    return cisco.extract_advisory(csaf, slug=slug)


def _dumps(obj):
    import json

    return json.dumps(obj, indent=2, ensure_ascii=False)


def assessment_text(result, combo_map):
    """Turn a fuelix result dict into the output cell text."""
    category = result["category"]
    if category == "affected":
        names = inv.expand_combo_ids(result["impacted_combo_ids"], combo_map)
        return "\n".join(names) if names else "Not Affected"
    if category == "not_affected":
        return "Not Affected"
    return "Indeterminate"


def _result_line(adv_id, label, color, stream=None):
    line = (f"{ui.dim('-')} {ui.bold(adv_id)} {ui.dim('->')} {color(label)}")
    print(line, file=stream or sys.stdout)


def _assessment_label(assessment):
    """Short colored label + color function for a per-advisory assessment cell."""
    if assessment == "Indeterminate":
        return "Indeterminate", ui.yellow
    if assessment == "Not Affected":
        return "Not Affected", ui.gray
    names = assessment.splitlines()
    label = names[0] + (f"  (+{len(names) - 1} more)" if len(names) > 1 else "")
    return label, ui.green


# --------------------------------------------------------------------------- #
# Run flow
# --------------------------------------------------------------------------- #
def run(args):
    """Execute the analysis flow for the parsed CLI args. Returns a process exit code.

    A supplied flag skips its interactive prompt; providing the URL makes the run fully
    flag-driven, which also skips the confirmation prompt (FR-025).
    """
    config.load_local_env()
    api_key = config.resolve(config.API_KEY)
    model = config.resolve(config.MODEL)
    base_url = config.resolve(config.BASE_URL)

    output_dir = Path(args.output_dir) if args.output_dir else default_output_dir()
    interactive = sys.stdin.isatty()
    fully_flag_driven = bool(args.url)

    # 1. API key check (skipped for dry-run so the pipeline can be tested offline).
    if not args.dry_run and not api_key:
        die("No FueliX API key is configured.",
            hint="Run 'caia --config' to set your FueliX API key.")

    # 2. Inventory (discover in the working folder or let the user pick).
    inv_path = resolve_inventory(args.inventory, interactive, sheet=args.sheet)
    try:
        inventory = inv.load_inventory(inv_path, args.sheet)
    except inv.InventoryError as e:
        die(str(e))
    if not inventory:
        die(f"Inventory {inv_path} has no firewall rows.")
    combos, combo_map = inv.build_combos(inventory)
    ui.ok(f"Loaded {ui.bold(str(len(inventory)))} firewalls "
          f"({len(combos)} distinct combos) from {ui.bold(inv_path.name)}.")

    # 3. URL (supplied via --url or prompted).
    if args.url:
        url = args.url.strip()
        if not is_valid_cisco_url(url):
            die(f"Invalid Cisco URL: {url}")
    else:
        url = prompt_for_url()

    # 4. Confirmation (skipped in a fully flag-driven run).
    if not fully_flag_driven:
        ui.plain()
        ui.system(f"The advisory URL will be analyzed and the report saved to "
                  f"{ui.bold(str(output_dir))} in this folder.")
        if not ui.confirm("Continue", default=False):
            ui.plain("No changes made.")
            return 0

    # 5. Discover advisories.
    ui.plain()
    ui.system("Discovering advisories ...")
    slugs = cisco.discover_advisories(url)
    if not slugs:
        die("No advisories found at that URL.")
    ui.ok(f"Found {ui.bold(str(len(slugs)))} advisory(ies).")

    # 6. Temp folder for CSAF downloads.
    temp_dir = Path(tempfile.mkdtemp(prefix="csaf_"))
    ui.info("Downloading CSAF files to: " + ui.dim(str(temp_dir)))

    if not args.dry_run:
        ui.system(f"Analyzing with FueliX model '{model}' ...")
    ui.plain()

    # 7. Process each advisory.
    results = []
    for slug in slugs:
        adv = download_and_extract(slug, temp_dir)
        if adv is None:
            _result_line(slug, "Indeterminate (CSAF unavailable)", ui.yellow)
            results.append((slug, "CSAF could not be retrieved.", "Indeterminate"))
            continue

        if args.dry_run:
            desc = (adv["vulnerable_products"] or adv["title"] or "")[:300]
            fams = ", ".join(sorted(adv["affected_versions"])) or "none"
            _result_line(adv["id"], f"DRY-RUN (families: {fams})", ui.cyan)
            results.append((adv["id"], desc, "DRY-RUN (no AI call)"))
            continue

        try:
            res = fuelix.assess_advisory(adv, combos, api_key, model=model,
                                         base_url=base_url)
            assessment = assessment_text(res, combo_map)
            desc = res["summary"] or (adv["vulnerable_products"] or adv["title"])
            label, color = _assessment_label(assessment)
            _result_line(adv["id"], label, color)
            results.append((adv["id"], desc, assessment))
        except Exception as e:  # noqa: BLE001
            _result_line(adv["id"], f"ERROR: {e}", ui.red, stream=sys.stderr)
            results.append((adv["id"],
                            adv["vulnerable_products"] or adv["title"],
                            f"ERROR: {e}"))

    # 8. Write the report (creating output/ if needed; fail clearly if it cannot be created).
    try:
        ensure_dirs(output_dir)
        out = write_report(results, str(output_dir))
    except OSError as e:
        die(f"Could not write the report to {output_dir}: {e}",
            hint="Check that the current folder is writable, or pass --output-dir DIR.")
    ui.plain()
    ui.ok("Wrote " + ui.bold(out))

    # 9. Temp cleanup.
    if args.keep_temp:
        ui.plain(ui.dim(f"CSAF files kept at: {temp_dir}"))
    else:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return 0
