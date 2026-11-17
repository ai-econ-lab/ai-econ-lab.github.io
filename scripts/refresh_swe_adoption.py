#!/usr/bin/env python3
"""Refresh the Adoption module's 'Sweden, in depth' cut: AI adoption by firm size.

    python3 scripts/refresh_swe_adoption.py    # -> data/swe_adoption.yaml, then build.py

Public data: SCB, ICT usage in enterprises (NV0116), technology '0080 = use of at least one
AI technology'. It decomposes the national adoption headline into the firm-SIZE gradient:
large firms adopt far more than small ones. DO NOT hand-edit the yaml.

YEAR AND TABLE ARE DISCOVERED, NOT PINNED (17 Nov 2026). This script used to ask the SNI 2007
table `AiTeknikerTypN` for a hard-coded YEAR = "2025". SCB published 2026 on 5 Nov 2026 in a
new table classified by SNI 2025 (`AiTeknikerTypSNI2025`), so the script went on re-pulling
2025 every Monday and stayed green while the site fell a year behind. Now `scb_nv0116m.latest`
picks the newest year across every `AiTeknikerTyp*` table, and the comparison year is the most
recent earlier wave in any of them.

Comparability across the reclassification. Firm-size classes do not depend on the industry
code, and SCB's headline is the same population in both tables (all surveyed industries, 10+
employees: `TotSNI` equals `Tot250` in both), so the four classes from 10 employees up carry a
change. The micro classes did change: 2026 publishes 0–1 and 2–9 employees where 2025 had 0,
1–4 and 5–9, so those rows carry no change. That is written into meta.series_note, which the
page prints, rather than left for a reader to discover.

The headline (Tot250) is the level Eurostat publishes for firms with 10+ employees. It equals
the Eurostat bar only when both are the same wave; when SCB is ahead (as from Nov 2026 until
Eurostat's 2026 release) the page says which is which.
"""
from pathlib import Path

import scb_nv0116m as scb

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "AiTeknikerTyp"
TECH = "0080"   # use of at least one AI technology
# SCB size-class code -> (display name, Swedish name, highlight?). Order = how the bars stack.
# Both micro ladders are listed; only the classes the current table publishes are written.
# Micro classes added 12 Aug 2026 (Sweden is one of two countries reporting 0-9 to Eurostat);
# Swedish names 31 Aug 2026; "Headline: 10+ employees" after Lydia's SV proofread, 3 Sep 2026.
SIZES = [
    ("250-",   "250+ employees",   "250+ anställda",     False),
    ("50-249", "50–249 employees", "50–249 anställda",   False),
    ("Tot250", "Headline: 10+ employees", "Huvudtal: 10+ anställda", True),
    ("10-49",  "10–49 employees",  "10–49 anställda",    False),
    ("2-9",    "2–9 employees",    "2–9 anställda",      False),   # SNI 2025 table, 2026-
    ("5-9",    "5–9 employees",    "5–9 anställda",      False),   # SNI 2007 table, -2025
    ("1-4",    "1–4 employees",    "1–4 anställda",      False),   # SNI 2007 table, -2025
    ("0-1",    "0–1 employees",    "0–1 anställda",      False),   # SNI 2025 table, 2026-
    ("0",      "No employees",     "Inga anställda",     False),   # SNI 2007 table, -2025
]


def comparison(cur_table, year):
    """(table, year) of the most recent earlier wave: same table if it has one, otherwise the
    newest earlier year in any sibling table."""
    best = None
    for t in scb.tables():
        if not t["id"].startswith(PREFIX):
            continue
        earlier = [y for y in scb.years(t["id"]) if y < year]
        if earlier:
            cand = (max(earlier), t["id"] == cur_table, t["id"])
            if best is None or cand > best:
                best = cand
    return (best[2], best[0]) if best else (None, None)


def main():
    table, year = scb.latest(PREFIX)
    ptable, pyear = comparison(table, year)
    codes = [s[0] for s in SIZES]
    cur = scb.values(table, TECH, codes, year)
    prev = scb.values(ptable, TECH, codes, pyear) if ptable else {}
    rows = []
    for code, name, name_sv, hi in SIZES:
        if code not in cur:
            continue
        p = prev.get(code)
        rows.append({"code": code, "name": name, "name_sv": name_sv, "adoption": int(round(cur[code])),
                     "prev": None if p is None else int(round(p)), "is_se": hi})
    total = next(r["adoption"] for r in rows if r["code"] == "Tot250")
    note = ""
    if ptable and ptable != table:
        # Reader-facing (the page prints it): no table ids here, they are in meta.table/prev_table.
        note = (f"SCB moved the survey to new industry codes (SNI 2025) in {year}. Size classes from "
                f"10 employees up are comparable with {pyear}; the smallest size classes were "
                f"redefined, so they show no change.")
    lines = [
        "# AI adoption by firm size in Sweden (Adoption module, 'Sweden, in depth').",
        "# Auto-generated; rerun scripts/refresh_swe_adoption.py then build.py. DO NOT hand-edit.",
        "meta:",
        '  indicator: "Enterprises using at least one AI technology, by firm size"',
        '  unit: "% of enterprises"',
        '  source: "SCB, ICT usage in enterprises (NV0116)"',
        f"  table: {table}",
        f"  year: {year}",
        f"  prev_table: {ptable}",
        f"  prev_year: {pyear}",
        f"  total: {total}",
        f'  series_note: "{note}"',
        "sizes:",
    ]
    for r in rows:
        p = "null" if r["prev"] is None else r["prev"]
        lines.append(f'  - {{code: "{r["code"]}", name: "{r["name"]}", name_sv: "{r["name_sv"]}", '
                     f'adoption: {r["adoption"]}, prev: {p}, is_se: {str(r["is_se"]).lower()}}}')
    out = ROOT / "data" / "swe_adoption.yaml"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out.name} from {table} {year} (vs {ptable} {pyear}): "
          + ", ".join(f"{r['name']}={r['adoption']}%" for r in rows))


if __name__ == "__main__":
    main()
