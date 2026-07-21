#!/usr/bin/env python3
"""Refresh the Monitor 'Across countries' firm-adoption data from Eurostat (freshest wave).

    python3 scripts/refresh_cross_country.py     # → data/cross_country_adoption.yaml, then build.py

Pulls isoc_eb_ai E_AI_TANY (enterprises using at least one AI technology, % of enterprises with
10+ persons employed, NACE C10-S951_X_K), keeps the latest available year plus the previous wave
for a year-on-year change, and the EU27 line. Public data (ec.europa.eu, allowlisted). Run this on
a schedule so the site tracks each new Eurostat wave, like the SCB/Platsbanken pipeline.
"""
import json, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
PARAMS = [("format", "JSON"), ("lang", "EN"), ("size_emp", "GE10"),
          ("unit", "PC_ENT"), ("nace_r2", "C10-S951_X_K"), ("indic_is", "E_AI_TANY")]
NAMES = {"LU":"Luxembourg","SE":"Sweden","NL":"Netherlands","CH":"Switzerland","BE":"Belgium",
"UK":"United Kingdom","NO":"Norway","DK":"Denmark","IE":"Ireland","DE":"Germany","FI":"Finland",
"IS":"Iceland","FR":"France","MT":"Malta","CY":"Cyprus","LT":"Lithuania","AT":"Austria","EE":"Estonia",
"PL":"Poland","PT":"Portugal","LV":"Latvia","SI":"Slovenia","CZ":"Czechia","HR":"Croatia","IT":"Italy",
"SK":"Slovakia","HU":"Hungary","EL":"Greece","ME":"Montenegro","ES":"Spain","MK":"N. Macedonia",
"RS":"Serbia","BG":"Bulgaria","BA":"Bosnia & Herz.","RO":"Romania","TR":"Turkey","AL":"Albania"}

def pull():
    url = f"{BASE}/isoc_eb_ai?{urllib.parse.urlencode(PARAMS)}"
    req = urllib.request.Request(url, headers={"User-Agent": "python-urllib (research use)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    ids, sizes, val = d["id"], d["size"], d["value"]
    inv = {dn: {v: k for k, v in d["dimension"][dn]["category"]["index"].items()} for dn in ("geo", "time")}
    ig, it = ids.index("geo"), ids.index("time")
    def coords(flat):
        c = []
        for s in reversed(sizes): c.append(flat % s); flat //= s
        return list(reversed(c))
    tab = {}
    for k, v in val.items():
        c = coords(int(k)); g = inv["geo"][c[ig]]; t = inv["time"][c[it]]
        tab.setdefault(g, {})[t] = v
    return tab

def main():
    tab = pull()
    years = sorted({t for g in tab.values() for t in g})
    latest = years[-1]
    prev = next((y for y in reversed(years[:-1])
                 if sum(1 for g in tab if y in tab[g]) >= 20), years[-2])
    rows = []
    for g, ys in tab.items():
        if g in NAMES and latest in ys:
            rows.append((g, ys[latest], ys.get(prev)))
    rows.sort(key=lambda r: -r[1])
    eu = tab.get("EU27_2020", {}).get(latest)
    L = ["# Cross-country firm AI-adoption — Monitor View B. Auto-refreshed from Eurostat isoc_eb_ai",
         "# (E_AI_TANY: enterprises using >=1 AI technology, % of enterprises 10+ employed). Freshest wave.",
         "# Rerun scripts/refresh_cross_country.py to update, then build.py. DO NOT hand-edit.",
         "meta:",
         '  indicator: "Enterprises using at least one AI technology"',
         '  unit: "% of enterprises (10+ employed)"',
         '  source: "Eurostat, isoc_eb_ai (E_AI_TANY)"',
         f'  year: {latest}',
         f'  prev_year: {prev}',
         f'  eu_avg: {round(eu,1) if eu is not None else "null"}',
         f'  n_countries: {len(rows)}',
         "countries:"]
    for g, v, pv in rows:
        pvs = f", prev: {round(pv,1)}" if pv is not None else ""
        L.append(f'  - {{code: "{g}", name: "{NAMES[g]}", adoption: {round(v,1)}, year: {latest}{pvs}, is_se: {str(g=="SE").lower()}}}')
    (ROOT / "data" / "cross_country_adoption.yaml").write_text("\n".join(L) + "\n", encoding="utf-8")
    se = next((v for g, v, _ in rows if g == "SE"), None)
    print(f"✓ cross_country_adoption.yaml — {len(rows)} countries, year {latest} (prev {prev}); "
          f"EU {eu}; Sweden {se}. Now: python3 build.py && git add -A && commit && push")

if __name__ == "__main__":
    main()
