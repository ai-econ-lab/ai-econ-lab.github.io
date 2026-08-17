#!/usr/bin/env python3
"""
refresh_barriers.py — why enterprises do NOT use AI (Eurostat isoc_eb_ain2).

The Monitor's adoption module says how many firms use AI; this says why the others do not,
which is the August brief's theme. Eurostat publishes eight reasons on a single question, as a
percentage of ALL enterprises with 10+ PERSONS EMPLOYED (Eurostat size class GE10, which
counts working proprietors and family workers, unlike "employees"), so the shares are not
shares of non-adopters
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

CHECKED, 10 Aug 2026. It DOES inherit the routing, and Eurostat says so itself.

Every one of the eight Swedish 2023 barrier cells carries Eurostat flag `b`, break in time
series, in the JSON-stat `status` block of isoc_eb_ain2. Sweden is the ONLY one of the 27
reporting countries flagged that year, which rules out an EU-wide methodology change and
points straight back at the national routing change found in the register. The harmonised
product did not wash it out.

What that permits, and what it forbids:

  2021 -> 2023 (SE)   FORBIDDEN. Eurostat's own break flag. Exclude 2021, or plot it with
                      the break marked and say what it is. Do not compute a change.
  2023 -> 2025 (SE)   PERMITTED. No break flagged on 2024 or 2025, so those three years are
                      one comparable series: 5.08, 7.73, 5.34 for lack of expertise. The
                      2024 spike and 2025 fall are large; they are not a flagged break, but
                      three points is a short series and the swing deserves saying so.
  cross-country       PERMITTED from 2023, which is where EU27_2020 begins. Note DK has no
                      2023 value and FI no 2024, so a full 27-country panel exists only for
                      2023 and 2025.

Verified against the API rather than the metadata prose, because the flag is the
authoritative statement: isoc_eb_ain2, unit PC_ENT, size_emp GE10, nace C10-S951_X_K,
dataset updated 2026-06-15. Re-check the flags if Eurostat republishes.

The variable names below are borrowed from the SCB register as labels only.

Auto-applied weekly since 17 Aug 2026, under a gate in scripts/weekly_refresh.py that is
inverted from every other one there: a change in meta.year FAILS the run instead of passing
it, for the routing reason above. Re-pulling within a wave is what the schedule is for; a new
wave is a question about universes and belongs to a person, not to a Monday cron job.

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
# The Swedish label for each reason, because three consumers need one: the SV sheet in
# build.py, the SV one-pager (scripts/build_onepager.py) and the SV social card. Lydia's
# review on 11 Aug 2026 found the SV brief drawing these bars in English, and the fix put
# name_sv into data/barriers.yaml by hand. That left this generator unable to reproduce its
# own committed output: running it deleted all eight labels, and build.py falls back with
# r.get("name_sv", r["name"]), so a Swedish sheet with English bar labels would have gone
# out with nothing raised anywhere. Holding the labels here (17 Aug 2026) is what allows the
# weekly refresh to run this script at all. Keyed on the Eurostat code rather than on the
# English label, since a wording change upstream would otherwise orphan the translation just
# as quietly.
LABELS_SV = {
    "E_AI_BLE": "Brist på relevant kompetens",
    "E_AI_BCST": "Kostnaderna verkar för höga",
    "E_AI_BNU": "Inte användbart för företaget",
    "E_AI_BDDT": "Datatillgång eller datakvalitet",
    "E_AI_BINC": "Oförenligt med befintliga system",
    "E_AI_BCDP": "Oro för dataskydd och integritet",
    "E_AI_BLEG": "Oklara rättsliga konsekvenser",
    "E_AI_BEC": "Etiska överväganden",
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
    rows = [{"name": LABELS[c], "name_sv": LABELS_SV[c], "share": round(se.get(c, 0.0), 1),
             "eu": round(eu.get(c, 0.0), 1), "is_se": True}
            for c in LABELS if c in se or c in eu]
    # Ordered by the EU column, not the Swedish one. Both the brief and the one-pager lead
    # with the EU picture and read Sweden against it, so a chart ordered by Sweden makes the
    # series the sentence describes first arrive out of order: legal consequences is second
    # in the EU and fourth in Sweden, and the reader following the EU bars downward sees the
    # rank break. Sorting here rather than in each consumer keeps one order everywhere.
    rows.sort(key=lambda r: -r["eu"])
    doc = {
        "meta": {"year": year, "source": "Eurostat, isoc_eb_ain2",
                 "unit": "per cent of all enterprises with 10 or more persons employed",
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
