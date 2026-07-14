"""
FueliX (Fuel iX) AI client.

FueliX exposes an OpenAI-compatible Chat Completions endpoint, so we POST a standard
{model, messages, ...} body and read choices[0].message.content. Only the standard
library is used for the HTTP call.

The public entry point is assess_advisory(): it asks the model, for one advisory, which
inventory combos are impacted and returns a normalized dict.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://api.fuelix.ai/v1"
DEFAULT_MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """\
You are a Cisco firewall vulnerability impact analyst. You are given ONE Cisco security \
advisory and a firewall inventory that contains ONLY ASA and FTD devices. Decide which \
inventory devices are impacted by that advisory.

Apply these rules IN ORDER and stop at the first that matches:
1. If the impact depends on runtime configuration that the inventory does NOT track \
(for example: high availability / HA, file policy, remote access VPN, SAML SSO, Snort \
detection engine settings, "if configured", "if enabled", or "if it was managing" \
specific devices) -> category "indeterminate".
2. If the advisory affects ONLY product families we cannot match against this inventory \
(Cisco Secure Firewall Management Center / FMC software, Cloud-Delivered FMC / cdFMC, \
Security Cloud Control / SCC, or Open Source Snort) -> "indeterminate". The inventory has \
no FMC, cdFMC, SCC or Snort devices.
3. If a matchable family (ASA or FTD) is affected but there are NO specific affected \
software releases you can enumerate -> "indeterminate".
4. Otherwise, match the affected releases against each inventory combo's version. Return \
the ids of the combos whose family AND version are affected -> category "affected". If a \
matchable family is affected with enumerable releases but no inventory combo matches -> \
"not_affected".

Version matching guidance: Cisco versions are irregular (e.g. 7.4.2.3, 9.16(4)67, \
9.20.4.14). Compare them numerically, segment by segment. A device build that is a more \
specific extension of an affected release counts as a match (device 7.4.2.1-30 matches \
affected 7.4.2.1). Honor "X to Y" release ranges inclusively. Only match a combo whose \
family equals the affected family (do not match an ASA combo against an FTD release).

Return STRICT JSON only. No prose, no markdown, no code fences. Exactly this shape:
{"category": "affected" | "not_affected" | "indeterminate",
 "impacted_combo_ids": [<int>, ...],
 "summary": "<1-2 sentence description of the affected products>",
 "reasoning": "<one short sentence>"}
When category is not "affected", impacted_combo_ids must be []."""


def build_user_prompt(adv, combos):
    av = adv.get("affected_versions") or {}
    if av:
        releases = "\n".join(
            f"  {fam}: {', '.join(vers)}" for fam, vers in sorted(av.items())
        )
    else:
        releases = "  (none enumerated in the CSAF product data)"

    combo_lines = "\n".join(
        f"{c['id']} | {c['model']} | {c['family']} | {c['version']} | {c['count']}"
        for c in combos
    )

    return f"""\
ADVISORY ID: {adv.get('id', '')}
TITLE: {adv.get('title', '')}

VULNERABLE PRODUCTS:
{adv.get('vulnerable_products') or '(section not present)'}

PRODUCTS CONFIRMED NOT VULNERABLE:
{adv.get('not_vulnerable') or '(section not present)'}

ENUMERATED AFFECTED RELEASES (from CSAF product data):
{releases}

INVENTORY COMBOS (id | model | type | version | device_count):
{combo_lines}

Decide the category and, if "affected", the impacted combo ids. Return STRICT JSON only."""


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def chat(messages, api_key, model=DEFAULT_MODEL, base_url=DEFAULT_BASE_URL,
         temperature=None, timeout=90, retries=2):
    """Call the OpenAI-compatible chat completions endpoint; return the reply text.

    temperature is omitted unless explicitly provided — some FueliX-hosted models
    (e.g. Claude via Vertex) reject it as deprecated.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": messages}
    if temperature is not None:
        payload["temperature"] = temperature
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        # A browser-like UA avoids Cloudflare's default bot block (error 1010) that
        # rejects Python's stdlib "Python-urllib/x.y" signature.
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
    }

    last_err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            detail = _read_error(e)
            # 4xx (except 429) are not worth retrying — surface immediately.
            if e.code != 429 and 400 <= e.code < 500:
                raise RuntimeError(
                    f"FueliX API error {e.code}: {detail}"
                ) from e
            last_err = RuntimeError(f"FueliX API error {e.code}: {detail}")
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
            last_err = RuntimeError(f"FueliX request failed: {e}")
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    raise last_err


def _read_error(e):
    try:
        return e.read().decode("utf-8", errors="replace")[:500]
    except Exception:  # noqa: BLE001
        return str(e)


# --------------------------------------------------------------------------- #
# JSON parsing
# --------------------------------------------------------------------------- #
def _parse_json(text):
    """Extract the first JSON object from a model reply, tolerating code fences."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n", "", t)
        t = re.sub(r"\n```$", "", t).strip()
    try:
        return json.loads(t)
    except ValueError:
        pass
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end > start:
        return json.loads(t[start : end + 1])
    raise ValueError("no JSON object found in model reply")


def _normalize(obj):
    category = str(obj.get("category", "")).strip().lower()
    if category not in ("affected", "not_affected", "indeterminate"):
        category = "indeterminate"
    ids = obj.get("impacted_combo_ids") or []
    if not isinstance(ids, list):
        ids = []
    if category != "affected":
        ids = []
    return {
        "category": category,
        "impacted_combo_ids": ids,
        "summary": str(obj.get("summary", "")).strip(),
        "reasoning": str(obj.get("reasoning", "")).strip(),
    }


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def assess_advisory(adv, combos, api_key, model=DEFAULT_MODEL,
                    base_url=DEFAULT_BASE_URL, timeout=90):
    """Ask the model to assess one advisory. Returns the normalized dict.

    On a JSON-parse failure the call is retried once with a stricter reminder.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(adv, combos)},
    ]
    reply = chat(messages, api_key, model=model, base_url=base_url, timeout=timeout)
    try:
        return _normalize(_parse_json(reply))
    except ValueError:
        messages.append({"role": "assistant", "content": reply})
        messages.append(
            {"role": "user", "content": "Return ONLY the JSON object, nothing else."}
        )
        reply = chat(messages, api_key, model=model, base_url=base_url, timeout=timeout)
        return _normalize(_parse_json(reply))
