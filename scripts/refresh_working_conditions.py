#!/usr/bin/env python3
"""Refresh the Monitor 'Working conditions & AI exposure' module data (item 1).

    python3 scripts/refresh_working_conditions.py     # → data/working_conditions.yaml, then build.py

Public data only: SCB Arbetsmiljoundersokningen (AM0501A/ArbmiljoSSYK, by SSYK occupation × gender)
crossed with DAIOE generative-AI exposure by SSYK. For each psychosocial condition and each gender,
it reports the mean share among the LEAST- vs MOST-AI-exposed occupations (exposure terciles over
2-digit SSYK). Descriptive/correlational — the causal version is a separate register study.

DAIOE source: lab-infrastructure (genai, v2023 public release). Rerun this, then build.py.
"""
import json, csv, statistics as st, urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAIOE_CSV = Path.home() / "Documents/Workspace/lab-infrastructure/ai-monitor/data/daioe_subdomains_ssyk4.csv"
DAIOE_YEAR = 2023                      # site's public DAIOE release
SCB = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0501/AM0501A/ArbmiljoSSYK"
YEAR = "2024"                          # freshest Arbetsmiljoundersokning
# condition code → (English label, higher-is: 'strain'|'resource'|'sentiment')
CONDS = [
    ("PsykAnst",         "Mentally strenuous work",         "strain"),
    ("OlustAEO",         "Can influence own work",          "resource"),
    ("KanSEAKopplaBort", "Can't switch off after work",     "strain"),
    ("TekUtvNegativ",    "Negative view of technology","strain"),
    ("Meningsfullt",     "Work feels meaningful",           "resource"),
]
GENDERS = [("TOT", "all"), ("2", "women"), ("1", "men")]

def daioe_by_ssyk2():
    lvl = defaultdict(list)
    for r in csv.DictReader(open(DAIOE_CSV)):
        if r["domain"] == "genai" and int(r["year"]) == DAIOE_YEAR:
            try: lvl[r["ssyk4"][:2]].append(float(r["pctl"]))
            except ValueError: pass
    return {k: st.mean(v) for k, v in lvl.items()}

def fetch_scb():
    q = {"query": [
        {"code": "Arbetsmiljofraga", "selection": {"filter": "item", "values": [c[0] for c in CONDS]}},
        {"code": "Kon", "selection": {"filter": "item", "values": ["1", "2", "TOT"]}},
        {"code": "Yrke", "selection": {"filter": "all", "values": ["*"]}},
        {"code": "ContentsCode", "selection": {"filter": "item", "values": ["000007XA"]}},
        {"code": "Tid", "selection": {"filter": "item", "values": [YEAR]}}],
        "response": {"format": "json-stat2"}}
    req = urllib.request.Request(SCB, data=json.dumps(q).encode(),
                                headers={"Content-Type": "application/json", "User-Agent": "research"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    ids, sizes, val = d["id"], d["size"], d["value"]
    inv = {k: {v: kk for kk, v in d["dimension"][k]["category"]["index"].items()} for k in ids}
    def coords(f):
        c = []
        for s in reversed(sizes): c.append(f % s); f //= s
        return list(reversed(c))
    recs = []
    for i, v in enumerate(val):
        if v is None: continue
        c = coords(i); rec = {ids[j]: inv[ids[j]][c[j]] for j in range(len(ids))}; rec["v"] = v; recs.append(rec)
    return recs

def main():
    expo = daioe_by_ssyk2()
    recs = fetch_scb()
    def tiers(code, kon):
        pts = [(expo.get(r["Yrke"]), r["v"]) for r in recs
               if r["Arbetsmiljofraga"] == code and r["Kon"] == kon and len(r["Yrke"]) == 2 and expo.get(r["Yrke"]) is not None]
        srt = sorted(pts, key=lambda p: p[0]); k = len(srt) // 3
        return round(st.mean([p[1] for p in srt[:k]]), 1), round(st.mean([p[1] for p in srt[-k:]]), 1), len(srt)
    L = ["# Working conditions & AI exposure (Monitor item 1). Auto-generated; rerun",
         "# scripts/refresh_working_conditions.py then build.py. Public data, descriptive.",
         "meta:",
         f'  daioe_variant: "generative-AI"',
         f'  daioe_version: "v{DAIOE_YEAR}"',
         f'  wc_source: "SCB Arbetsmiljoundersokningen {YEAR}"',
         f'  wc_year: {YEAR}',
         '  measure: "% of employed, mean over least- vs most-exposed occupations (DAIOE terciles, SSYK 2-digit)"',
         "conditions:"]
    for code, label, kind in CONDS:
        L.append(f'  - code: "{code}"')
        L.append(f'    label: "{label}"')
        L.append(f'    kind: "{kind}"')
        for kon, g in GENDERS:
            lo, hi, n = tiers(code, kon)
            L.append(f'    {g}: {{lo: {lo}, hi: {hi}}}')
        L.append(f'    n_occ: {tiers(code, "TOT")[2]}')
    (ROOT / "data" / "working_conditions.yaml").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"✓ working_conditions.yaml — {len(CONDS)} conditions × 3 genders; DAIOE genai v{DAIOE_YEAR} × SCB {YEAR}")

if __name__ == "__main__":
    main()
