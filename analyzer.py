#!/usr/bin/env python3
"""
Cisco Advisory Impact Analyzer (AI-driven)
==========================================
Given a Cisco Event Response (ERP) URL, find every referenced security advisory,
download its CSAF, extract the "Vulnerable Products" / "Products Confirmed Not
Vulnerable" sections plus the enumerated affected releases, and ask the FueliX AI
which firewalls in your inventory are impacted. Writes a timestamped Excel report.

Typical use (interactive):
    python analyzer.py
    -> place inventory.xlsx and .env next to this script first.

Automation / testing:
    python analyzer.py --url <ERP_OR_ADVISORY_URL> [--inventory PATH]
                       [--output-dir DIR] [--dry-run] [--keep-temp/--no-keep-temp]
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cisco
import fuelix
import inventory as inv
import ui
from report import write_report

ROOT = Path(__file__).resolve().parent
CISCO_HOST = "sec.cloudapps.cisco.com"


def die(msg, hint=None):
    ui.fail(msg)
    if hint:
        ui.plain(ui.dim(hint))
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Environment / .env
# --------------------------------------------------------------------------- #
def load_env(root):
    """Load root/.env into os.environ. Uses python-dotenv if available, else a
    minimal stdlib parser so the app still works with only openpyxl installed."""
    env_path = root / ".env"
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
        return
    except ImportError:
        pass
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), val)


# --------------------------------------------------------------------------- #
# Inventory discovery
# --------------------------------------------------------------------------- #
def find_inventory(root, explicit=None):
    if explicit:
        p = Path(explicit)
        if not p.exists():
            die(f"Inventory file not found: {p}")
        return p
    preferred = root / "inventory.xlsx"
    if preferred.exists():
        return preferred
    candidates = sorted(
        p for p in root.glob("*.xlsx")
        if not p.name.startswith("analysis_output_") and not p.name.startswith("~$")
    )
    if candidates:
        return candidates[0]
    die(f"No inventory spreadsheet found in {root}.",
        hint="Place your firewall inventory there as 'inventory.xlsx' (sheet 'FW_List').")


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
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Cisco advisory impact analyzer (AI-driven)")
    ap.add_argument("--url", help="ERP page URL or single advisory URL (else prompted)")
    ap.add_argument("--inventory", help="Path to inventory .xlsx (else auto-detected in root)")
    ap.add_argument("--sheet", default="FW_List", help="Inventory sheet name")
    ap.add_argument("--output-dir", default=str(ROOT), help="Where to write the report")
    ap.add_argument("--dry-run", action="store_true", help="Skip the AI call (pipeline test)")
    ap.add_argument("--keep-temp", dest="keep_temp", action="store_true", default=True)
    ap.add_argument("--no-keep-temp", dest="keep_temp", action="store_false")
    args = ap.parse_args()

    load_env(ROOT)

    # 1. API key check (skipped for dry-run so the pipeline can be tested offline).
    api_key = os.environ.get("FUELIX_API_KEY", "").strip()
    if not args.dry_run and not api_key:
        die("Missing FUELIX_API_KEY.",
            hint=f"Copy .env.example to .env in {ROOT} and set your FueliX API key "
                 "(or run install.py).")
    model = os.environ.get("FUELIX_MODEL", fuelix.DEFAULT_MODEL).strip()
    base_url = os.environ.get("FUELIX_BASE_URL", fuelix.DEFAULT_BASE_URL).strip()

    # 2. Inventory.
    inv_path = find_inventory(ROOT, args.inventory)
    inventory = inv.load_inventory(inv_path, args.sheet)
    if not inventory:
        die(f"Inventory {inv_path} has no firewall rows.")
    combos, combo_map = inv.build_combos(inventory)
    ui.ok(f"Loaded {ui.bold(str(len(inventory)))} firewalls "
          f"({len(combos)} distinct combos) from {ui.bold(inv_path.name)}.")

    # 3. URL.
    url = args.url if args.url else prompt_for_url()
    if args.url and not is_valid_cisco_url(url):
        die(f"Invalid Cisco URL: {url}")

    # 4. Discover advisories.
    ui.plain()
    ui.system("Discovering advisories ...")
    slugs = cisco.discover_advisories(url)
    if not slugs:
        die("No advisories found at that URL.")
    ui.ok(f"Found {ui.bold(str(len(slugs)))} advisory(ies).")

    # 5. Temp folder for CSAF downloads.
    temp_dir = Path(tempfile.mkdtemp(prefix="csaf_"))
    ui.info("Downloading CSAF files to: " + ui.dim(str(temp_dir)))

    if not args.dry_run:
        ui.system(f"Analyzing with FueliX model '{model}' ...")
    ui.plain()

    # 6. Process each advisory.
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

    # 7. Write the report.
    out = write_report(results, args.output_dir)
    ui.plain()
    ui.ok("Wrote " + ui.bold(out))

    # 8. Temp cleanup.
    if args.keep_temp:
        ui.plain(ui.dim(f"CSAF files kept at: {temp_dir}"))
    else:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_cli():
    """Entry point with graceful Ctrl+C / EOF handling (no traceback)."""
    try:
        main()
    except KeyboardInterrupt:
        print()
        ui.warn("Cancelled.")
        sys.exit(130)


if __name__ == "__main__":
    run_cli()
