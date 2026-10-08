#!/usr/bin/env python3
"""Refresh the Monitor 'Working conditions & AI exposure' module data (item 1).

    python3 scripts/refresh_working_conditions.py     # → data/working_conditions.yaml, then build.py

Public data only: SCB Arbetsmiljoundersokningen (AM0501A/ArbmiljoSSYK, by SSYK occupation × gender)
crossed with DAIOE generative-AI exposure by SSYK. For each psychosocial condition and each gender,
it reports the mean share among the LEAST- vs MOST-AI-exposed occupations (exposure terciles over
2-digit SSYK). Descriptive/correlational — the causal version is a separate register study.

DAIOE source (from 8 Oct 2026, ML): the v1.1.0 deposit, vintage-2025, SSYK 2012 panel, column
daioe_g2gen (the second-generation generative composite), score year 2025, checked against the
bundle's SHA256SUMS. Each 4-digit occupation gets its tie-invariant midrank percentile within the
year (the bundle README's convention); a 2-digit group's exposure is the mean percentile of its
4-digit occupations, as before. Until 8 Oct the input was the legacy genai index, 2023, from
ai-monitor's F0 file (data/daioe_subdomains_ssyk4.csv). `--legacy` reproduces that file.
Rerun this, then build.py.
"""
import json, csv, hashlib, os, statistics as st, sys, urllib.request
from collections import defaultdict
from pathlib import Path

from monitor_root import MONITOR_ROOT

ROOT = Path(__file__).resolve().parent.parent
DAIOE_CSV = MONITOR_ROOT / "data/daioe_subdomains_ssyk4.csv"     # legacy input, --legacy only
WORKSPACE = Path(os.environ.get("AIEL_WORKSPACE", ROOT.parents[1]))
BUNDLE = WORKSPACE / "lab-infrastructure/daioe-pipeline/dist/daioe-v1.1.0-scores"
PANEL = "vintage-2025/daioe_ssyk2012.tsv"
DAIOE_COL, DAIOE_YEAR = "daioe_g2gen", 2025      # exposure input (ML, 8 Oct 2026)
LEGACY = "--legacy" in sys.argv
if LEGACY:
    DAIOE_YEAR = 2023
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
    """Mean exposure percentile of the 4-digit occupations within each 2-digit SSYK group."""
    lvl = defaultdict(list)
    if LEGACY:
        for r in csv.DictReader(open(DAIOE_CSV)):
            if r["domain"] == "genai" and int(r["year"]) == DAIOE_YEAR:
                try: lvl[r["ssyk4"][:2]].append(float(r["pctl"]))
                except ValueError: pass
        return {k: st.mean(v) for k, v in lvl.items()}
    want = next(l.split()[0] for l in (BUNDLE / "SHA256SUMS").read_text().splitlines()
                if l.strip().endswith(PANEL))
    if hashlib.sha256((BUNDLE / PANEL).read_bytes()).hexdigest() != want:
        raise SystemExit(f"SHA256 mismatch for {PANEL}: bundle is not the v1.1.0 deposit")
    import pandas as pd
    d = pd.read_csv(BUNDLE / PANEL, sep="\t")
    d = d[(d["year"] == DAIOE_YEAR) & d[DAIOE_COL].notna()].copy()
    d["ssyk4"] = d["ssyk2012_4"].astype(int).astype(str).str.zfill(4)
    d["pctl"] = 100 * d[DAIOE_COL].rank(method="average") / len(d)
    for code, p in zip(d["ssyk4"], d["pctl"]):
        lvl[code[:2]].append(p)
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
         f'  daioe_variant: "{"generative-AI" if LEGACY else "generative-AI composite (g2gen)"}"',
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
    print(f"✓ working_conditions.yaml — {len(CONDS)} conditions × 3 genders; DAIOE {"genai" if LEGACY else "g2gen"} v{DAIOE_YEAR} × SCB {YEAR}")

if __name__ == "__main__":
    main()
