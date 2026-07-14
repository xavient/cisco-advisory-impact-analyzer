"""
Cisco data access: fetch an Event Response (ERP) page, discover the advisories it
references, download each advisory's CSAF JSON, and extract the pieces we care about
(the two product sections and the enumerated affected releases).

All HTTP uses the standard library so the app has no networking dependency.
"""

from __future__ import annotations

import html as _html
import json
import re
import sys
import urllib.error
import urllib.request

BASE = "https://sec.cloudapps.cisco.com"
UA = {"User-Agent": "Mozilla/5.0 (compatible; AdvisoryImpactBot/0.1)"}

# Product families we can reason about from the firewall inventory. FMC is included
# so FMC-only advisories carry their versions into the AI context (the AI then marks
# them Indeterminate because the inventory holds no FMC devices).
MATCHABLE_FAMILIES = {"ASA", "FTD", "FMC"}

# Slug of a Cisco security advisory, e.g. cisco-sa-onprem-fmc-authbypass-5JPp45V2
SLUG_RE = re.compile(r"/CiscoSecurityAdvisory/(cisco-sa-[A-Za-z0-9\-]+)")


# --------------------------------------------------------------------------- #
# Fetch helpers
# --------------------------------------------------------------------------- #
def _get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_text(url):
    try:
        return _get(url).decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        print(f"  ! could not fetch {url}: {e}", file=sys.stderr)
        return None


def fetch_json(url):
    """Fetch and parse JSON regardless of the server's Content-Type header."""
    try:
        return json.loads(_get(url))
    except Exception as e:  # noqa: BLE001
        print(f"  ! CSAF unavailable ({url}): {e}", file=sys.stderr)
        return None


def csaf_url(slug):
    return f"{BASE}/security/center/content/CiscoSecurityAdvisory/{slug}/csaf/{slug}.json"


# --------------------------------------------------------------------------- #
# Advisory discovery
# --------------------------------------------------------------------------- #
def discover_advisories(url):
    """Return an ordered, de-duplicated list of advisory slugs.

    Accepts an ERP page URL (many advisories) or a single advisory URL.
    """
    direct = SLUG_RE.search(url)
    if "viewErp" not in url and direct:
        return [direct.group(1)]
    html = fetch_text(url)
    if not html:
        return [direct.group(1)] if direct else []
    seen, out = set(), []
    for slug in SLUG_RE.findall(html):
        slug = slug.split("/")[0]  # drop any trailing path (e.g. /csaf)
        if slug not in seen:
            seen.add(slug)
            out.append(slug)
    return out


# --------------------------------------------------------------------------- #
# Family detection
# --------------------------------------------------------------------------- #
def detect_family(name):
    n = (name or "").lower()
    if "management center" in n or re.search(r"\bfmc\b", n):
        return "FMC"
    if "threat defense" in n or re.search(r"\bftd\b", n):
        return "FTD"
    if "adaptive security appliance" in n or re.search(r"\basav?\b", n):
        return "ASA"
    if "snort" in n:
        return "SNORT"
    return "OTHER"


# --------------------------------------------------------------------------- #
# Text cleaning
# --------------------------------------------------------------------------- #
def _clean(text):
    text = _html.unescape(text or "")
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    # CSAF notes embed hyperlink anchors as ["#fs"] style tokens; drop them.
    text = re.sub(r'\["#[^"]*"\]', "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# --------------------------------------------------------------------------- #
# CSAF extraction
# --------------------------------------------------------------------------- #
def _all_notes(csaf):
    notes = list(csaf.get("document", {}).get("notes", []) or [])
    for v in csaf.get("vulnerabilities", []) or []:
        notes += v.get("notes", []) or []
    return notes


def get_note(csaf, title):
    """Return the cleaned text of the note whose title matches (case-insensitive)."""
    want = title.strip().lower()
    for n in _all_notes(csaf):
        if (n.get("title") or "").strip().lower() == want:
            return _clean(n.get("text", ""))
    return ""


def advisory_id(csaf):
    return (csaf.get("document", {}).get("tracking", {}).get("id") or "").strip()


def advisory_title(csaf):
    return (csaf.get("document", {}).get("title") or "").strip()


def _build_leaf_map(branches, family_name, out):
    """Map every product leaf id -> (family, version_string).

    Family comes from the nearest product_family / product_name ancestor; the
    version string is the leaf's own product name (e.g. "7.0.0").
    """
    for b in branches or []:
        cat = b.get("category")
        name = b.get("name", "")
        fam_name = name if cat in ("product_family", "product_name") else family_name
        product = b.get("product")
        if product and product.get("product_id"):
            version = product.get("name") or name
            out[product["product_id"]] = (detect_family(fam_name or name), version)
        _build_leaf_map(b.get("branches"), fam_name, out)
    return out


def parse_csaf_affected_versions(csaf):
    """Return {family: sorted[version_str]} for the matchable families.

    Handles both CSAF product_tree shapes:
      * relationships present: known_affected holds composite ids
        (CSAFPID-<ver>:<platform>) that resolve via relationships[].product_reference
        to the version leaf.
      * no relationships: known_affected points directly at leaf product ids.
    """
    tree = csaf.get("product_tree", {}) or {}
    leaf = _build_leaf_map(tree.get("branches"), None, {})

    rel = {}
    for r in tree.get("relationships", []) or []:
        fpn = (r.get("full_product_name") or {}).get("product_id")
        if fpn:
            rel[fpn] = r.get("product_reference")

    out = {}
    for vuln in csaf.get("vulnerabilities", []) or []:
        for pid in vuln.get("product_status", {}).get("known_affected", []) or []:
            base = rel.get(pid) or pid.split(":")[0]
            fam, ver = leaf.get(base) or leaf.get(pid) or (None, None)
            if fam in MATCHABLE_FAMILIES and ver:
                out.setdefault(fam, set()).add(ver)

    return {fam: sorted(vs, key=_version_key) for fam, vs in out.items()}


def _version_key(s):
    return tuple(int(x) for x in re.findall(r"\d+", str(s)))


def extract_advisory(csaf, slug=None):
    """Collapse a CSAF document into the fields the analyzer needs."""
    return {
        "id": advisory_id(csaf) or (slug or ""),
        "title": advisory_title(csaf),
        "vulnerable_products": get_note(csaf, "Vulnerable Products"),
        "not_vulnerable": get_note(csaf, "Products Confirmed Not Vulnerable"),
        "affected_versions": parse_csaf_affected_versions(csaf),
    }
