#!/usr/bin/env python3
"""Refresh the Adoption module's sector cut: AI adoption by industry.

    python3 scripts/refresh_swe_adoption_sector.py   # -> data/swe_adoption_sector.yaml, then build.py

Same public source and same table as the firm-size cut: SCB, ICT usage in enterprises
(NV0116), table AiTeknikerTypN, technology '0080 = use of at least one AI technology'.
The `Redovisningsgrupp` dimension carries both size classes and SNI industry groups, so
this is the size chart's sibling and the two are exactly comparable: same survey, same
question, same year, same share definition.

Why it exists (31 Aug 2026): the September brief asserted that adoption "depends far more
on how big a firm is than on what it does". The table says otherwise. The industry spread
runs 12 to 88 per cent, the size spread 14 to 72, so what a firm does separates it MORE
than how big it is. The claim could not be checked without this cut, so the cut is built.

DO NOT hand-edit the yaml.
"""
import json, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCB = "https://api.scb.se/OV0104/v1/doris/en/ssd/START/NV/NV0116/NV0116M/AiTeknikerTypN"
YEAR, PREV = "2025", "2021"

# SCB study-domain code -> (English name, Swedish name, highlight?).
# Order = how the bars stack, highest adoption first; the total sits in its sorted place
# so the reader can see which industries clear the national figure and which do not.
# `IKT` is deliberately excluded from the default bars: it overlaps 58-63 and manufacturing
# rather than partitioning them, so showing both double-counts. Kept in the yaml as a
# separate `overlay` entry for anyone who wants the ICT-sector definition explicitly.
SECTORS = [
    ("58-63",              "Information and communication", "Information och kommunikation", False),
    ("68",                 "Real estate",                   "Fastighetsverksamhet",          False),
    ("69-75, 77-82, 95.1", "Other services",                "Övriga tjänsteföretag",         False),
    ("35-39",              "Energy and recycling",          "Energi och återvinning",        False),
    ("TotSNI",             "All industries",                "Samtliga branscher",            True),
    ("10-33",              "Manufacturing",                 "Tillverkning",                  False),
    ("45-47",              "Trade and motor repair",        "Handel och motorreparation",    False),
    ("55-56",              "Accommodation and food",        "Hotell och restaurang",         False),
    ("41-43",              "Construction",                  "Byggverksamhet",                False),
    ("49-53",              "Transport and storage",         "Transport och magasinering",    False),
]
OVERLAY = ("IKT", "ICT sector (overlapping definition)", "IKT-sektorn (överlappande avgränsning)")


def fetch(codes):
    q = {"query": [
        {"code": "TypAvTeknik", "selection": {"filter": "item", "values": ["0080"]}},
        {"code": "Redovisningsgrupp", "selection": {"filter": "item", "values": codes}},
        {"code": "ContentsCode", "selection": {"filter": "item", "values": ["000007JC"]}},   # share, percent
        {"code": "Tid", "selection": {"filter": "item", "values": [PREV, YEAR]}}],
        "response": {"format": "json-stat2"}}
    req = urllib.request.Request(SCB, data=json.dumps(q).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "research"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    ids, sizes, val = d["id"], d["size"], d["value"]
    idx = {k: d["dimension"][k]["category"]["index"] for k in ids}
    nT = sizes[ids.index("Tid")]
    tpos = idx["Tid"]
    out = {}
    for code, pos in idx["Redovisningsgrupp"].items():
        base = pos * nT
        out[code] = (val[base + tpos[YEAR]], val[base + tpos[PREV]])
    return out


def q(s):
    return '"' + s.replace('"', '\\"') + '"'


def main():
    codes = [s[0] for s in SECTORS] + [OVERLAY[0]]
    data = fetch(codes)

    rows = []
    for code, en, sv, hi in SECTORS:
        cur, prev = data.get(code, (None, None))
        if cur is None:
            continue
        rows.append({"code": code, "name_en": en, "name_sv": sv,
                     "adoption": int(round(cur)),
                     "prev": (None if prev is None else int(round(prev))), "is_se": hi})

    total = next((r["adoption"] for r in rows if r["code"] == "TotSNI"), None)
    bars = [r for r in rows if r["code"] != "TotSNI"]
    lo, hi_ = min(r["adoption"] for r in bars), max(r["adoption"] for r in bars)

    ov_cur, ov_prev = data.get(OVERLAY[0], (None, None))

    lines = [
        "# AI adoption by industry in Sweden (Adoption module, 'Sweden, in depth').",
        "# Auto-generated; rerun scripts/refresh_swe_adoption_sector.py then build.py. DO NOT hand-edit.",
        "# Sibling of swe_adoption.yaml: same table, same technology code, same year.",
        "meta:",
        '  indicator: "Enterprises using at least one AI technology, by industry"',
        '  unit: "% of enterprises"',
        '  source: "SCB, ICT usage in enterprises (NV0116)"',
        f"  year: {YEAR}",
        f"  prev_year: {PREV}",
        f"  total: {total}",
        f"  spread_low: {lo}",
        f"  spread_high: {hi_}",
        "sectors:",
    ]
    for r in rows:
        prev = "null" if r["prev"] is None else r["prev"]
        lines.append(
            f'  - {{code: {q(r["code"])}, name_en: {q(r["name_en"])}, name_sv: {q(r["name_sv"])}, '
            f'adoption: {r["adoption"]}, prev: {prev}, is_se: {str(r["is_se"]).lower()}}}')
    lines += [
        "# Overlaps the industry rows above rather than partitioning them; never plot it",
        "# alongside them without saying so.",
        "overlay:",
        f'  - {{code: {q(OVERLAY[0])}, name_en: {q(OVERLAY[1])}, name_sv: {q(OVERLAY[2])}, '
        f'adoption: {int(round(ov_cur))}, prev: {int(round(ov_prev))}}}',
    ]
    out = ROOT / "data" / "swe_adoption_sector.yaml"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(rows)} industries, total {total}%, spread {lo}-{hi_}%)")


if __name__ == "__main__":
    main()
