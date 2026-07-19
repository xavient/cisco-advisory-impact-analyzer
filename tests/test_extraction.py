#!/usr/bin/env python3
"""
Offline self-test for the CSAF extraction logic (cisco.py). No network, no AI.

Run against local CSAF sample files:
    python tests/test_extraction.py path/to/a.json path/to/b.json
If no paths are given, it looks for the known samples in ~/Downloads.

Checks, per file:
  * the two required note sections are found,
  * affected-version resolution returns something sane for both product_tree shapes.
Exits non-zero if any hard assertion fails.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cisco_advisory_impact_agent import cisco  # noqa: E402

DEFAULT_SAMPLES = [
    "cisco-sa-onprem-fmc-authbypass-5JPp45V2.json",  # relationships shape, FMC
    "cisco-sa-fmc-rce-NKhnULJh.json",                # relationships shape, FMC
    "cisco-sa-ftd-cmd-inj-mTzGZexf.json",            # relationships shape, FTD
    "cisco-sa-ucce-pcce-xss-2JVyg3uD.json",          # direct-leaf shape, no ASA/FTD/FMC
]


def sample_paths(argv):
    if argv:
        return [Path(p) for p in argv]
    dl = Path.home() / "Downloads"
    return [dl / name for name in DEFAULT_SAMPLES]


def main(argv):
    paths = sample_paths(argv)
    failures = 0
    for p in paths:
        if not p.exists():
            print(f"SKIP (missing): {p}")
            continue
        csaf = json.loads(p.read_text(encoding="utf-8"))
        adv = cisco.extract_advisory(csaf)
        print(f"\n=== {p.name} ===")
        print(f"  id: {adv['id']}")
        vp = adv["vulnerable_products"]
        nv = adv["not_vulnerable"]
        av = adv["affected_versions"]
        print(f"  Vulnerable Products note: {len(vp)} chars")
        print(f"  Products Confirmed Not Vulnerable note: {len(nv)} chars")
        print(f"  affected families -> "
              + (", ".join(f"{f}:{len(v)}" for f, v in sorted(av.items())) or "none"))
        for fam, vers in sorted(av.items()):
            print(f"      {fam}: {vers[:5]}{'...' if len(vers) > 5 else ''}")

        # Hard assertions.
        if not adv["id"]:
            print("  FAIL: no advisory id"); failures += 1
        if not vp:
            print("  FAIL: Vulnerable Products note empty"); failures += 1
        if not nv:
            print("  FAIL: Products Confirmed Not Vulnerable note empty"); failures += 1
        # Every enumerated version must be a non-empty string.
        for fam, vers in av.items():
            if not vers or any(not str(v).strip() for v in vers):
                print(f"  FAIL: bad versions for {fam}"); failures += 1

    print("\n" + ("ALL CHECKS PASSED" if failures == 0 else f"{failures} CHECK(S) FAILED"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
