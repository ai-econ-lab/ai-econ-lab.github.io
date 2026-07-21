#!/usr/bin/env python3
"""Refresh the Adoption module's 'Sweden, in depth' cut: AI adoption by firm size.

    python3 scripts/refresh_swe_adoption.py    # -> data/swe_adoption.yaml, then build.py

Public data: SCB, ICT usage in enterprises (NV0116), table AiTeknikerTypN, technology
'0080 = use of at least one AI technology'. It decomposes the national adoption headline
(which the cross-country Eurostat bar shows) into the firm-SIZE gradient: large firms adopt
far more than small ones. The all-firms total matches the Eurostat figure (both trace to
this SCB survey). Rerun this, then build.py. DO NOT hand-edit the yaml.
"""
import json, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCB = "https://api.scb.se/OV0104/v1/doris/en/ssd/START/NV/NV0116/NV0116M/AiTeknikerTypN"
YEAR, PREV = "2025", "2021"
# SCB size-class code -> (display name, highlight?). Order = how the bars stack (biggest first).
SIZES = [
    ("250-",   "250+ employees",   False),
    ("50-249", "50–249 employees", False),
    ("Tot250", "All firms (10+)",  True),   # the headline that ties to the cross-country bar
    ("10-49",  "10–49 employees",  False),
]


def fetch():
    q = {"query": [
        {"code": "TypAvTeknik", "selection": {"filter": "item", "values": ["0080"]}},
        {"code": "Redovisningsgrupp", "selection": {"filter": "item", "values": [s[0] for s in SIZES]}},
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
    tpos = idx["Tid"]                                   # {"2021":0,"2025":1}
    out = {}
    # value order: TypAvTeknik(1) x Redovisningsgrupp x ContentsCode(1) x Tid
    for scode, spos in idx["Redovisningsgrupp"].items():
        base = spos * nT
        cur = val[base + tpos[YEAR]]
        prev = val[base + tpos[PREV]]
        out[scode] = (cur, prev)
    return out


def main():
    data = fetch()
    rows = []
    for code, name, hi in SIZES:
        cur, prev = data.get(code, (None, None))
        if cur is None:
            continue
        rows.append({"code": code, "name": name, "adoption": int(round(cur)),
                     "prev": (None if prev is None else int(round(prev))), "is_se": hi})
    total = next((r["adoption"] for r in rows if r["code"] == "Tot250"), None)
    lines = [
        "# AI adoption by firm size in Sweden (Adoption module, 'Sweden, in depth').",
        "# Auto-generated; rerun scripts/refresh_swe_adoption.py then build.py. DO NOT hand-edit.",
        "meta:",
        '  indicator: "Enterprises using at least one AI technology, by firm size"',
        '  unit: "% of enterprises"',
        '  source: "SCB, ICT usage in enterprises (NV0116)"',
        f"  year: {YEAR}",
        f"  prev_year: {PREV}",
        f"  total: {total}",
        "sizes:",
    ]
    for r in rows:
        prev = "null" if r["prev"] is None else r["prev"]
        lines.append(f'  - {{code: "{r["code"]}", name: "{r["name"]}", adoption: {r["adoption"]}, '
                     f'prev: {prev}, is_se: {str(r["is_se"]).lower()}}}')
    out = ROOT / "data" / "swe_adoption.yaml"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out.name}: " + ", ".join(f"{r['name']}={r['adoption']}%" for r in rows))


if __name__ == "__main__":
    main()
