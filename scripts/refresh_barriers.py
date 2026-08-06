#!/usr/bin/env python3
"""
refresh_barriers.py — why enterprises do NOT use AI (Eurostat isoc_eb_ain2).

The Monitor's adoption module says how many firms use AI; this says why the others do not,
which is the August brief's theme. Eurostat publishes eight reasons on a single question, as a
percentage of ALL enterprises with 10+ employees, so the shares are not shares of non-adopters
and do not sum to anything meaningful. That is stated on the figure rather than corrected away.

DO NOT TURN THIS INTO A TIME SERIES WITHOUT CHECKING THE ROUTING FIRST.
This is a single-year cross-section by design, and that is what keeps it honest. In the
Swedish source register the barrier question's ROUTING changed between the 2021 and 2023
waves, so the two years describe different universes:

    2021  asked of all non-adopters          3,425 firms answered
    2023  gated on E_AI_EC == 1 (considered     482 firms answered
          AI but did not adopt)

A 2021-versus-2023 barrier trend would therefore compare a broad group with a narrow,
self-selected one, and any movement would be routing rather than a change in what firms
say. Verified 6 Aug 2026 on P1207 ITFtg_Stora_2021 and _2023; see
lab-infrastructure/data-notes/variable-semantics.csv (E_AI_B* row) and
projects/proworker-gov/notes/ai-mode-coding-check_2026-08-06.md.

The Eurostat series here is a separate, harmonised product, so it need not inherit the
Swedish routing; the point is that this has to be CHECKED against the Eurostat metadata
before any cross-year claim, not assumed either way. The variable names below are borrowed
from the SCB register as labels only.

Run: python3 scripts/refresh_barriers.py   ->  data/barriers.yaml
"""
import json
import urllib.request
from pathlib import Path

import yaml

BASE = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/isoc_eb_ain2"
        "?format=JSON&lang=EN&unit=PC_ENT&size_emp=GE10&nace_r2=C10-S951_X_K")
LABELS = {
    "E_AI_BLE": "Lack of relevant expertise",
    "E_AI_BCST": "Costs seem too high",
    "E_AI_BNU": "Not useful for the enterprise",
    "E_AI_BDDT": "Data availability or quality",
    "E_AI_BINC": "Incompatible with existing systems",
    "E_AI_BCDP": "Data-protection and privacy concerns",
    "E_AI_BLEG": "Unclear legal consequences",
    "E_AI_BEC": "Ethical considerations",
}


def fetch(geo, year):
    url = f"{BASE}&geo={geo}&time={year}"
    with urllib.request.urlopen(url, timeout=60) as r:
        d = json.load(r)
    idx = d["dimension"]["indic_is"]["category"]["index"]
    vals = d["value"]
    out = {}
    for code in LABELS:
        i = idx.get(code)
        if i is None:
            continue
        v = vals.get(str(i))
        if v is not None:
            out[code] = float(v)
    return out


def main():
    year = 2025
    eu, se = fetch("EU27_2020", year), fetch("SE", year)
    rows = [{"name": LABELS[c], "share": round(se.get(c, 0.0), 1),
             "eu": round(eu.get(c, 0.0), 1), "is_se": True}
            for c in LABELS if c in se or c in eu]
    rows.sort(key=lambda r: -r["share"])
    doc = {
        "meta": {"year": year, "source": "Eurostat, isoc_eb_ain2",
                 "unit": "per cent of all enterprises with 10 or more employees",
                 "geo": "Sweden, with the EU27 average for comparison"},
        "lede": ("Adoption figures say how many firms use AI. This says what stops the rest. "
                 "The reasons are reported as a share of all enterprises, not of non-adopters, "
                 "so they describe how widespread each obstacle is rather than dividing "
                 "non-adopters between causes."),
        "rows": rows,
    }
    Path("data/barriers.yaml").write_text(
        yaml.dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"barriers.yaml: {len(rows)} reasons, {year}")
    for r in rows:
        print(f"   SE {r['share']:5.1f}%   EU {r['eu']:5.1f}%   {r['name']}")


if __name__ == "__main__":
    main()
