#!/usr/bin/env python3
"""Refresh the Monitor 'Entry-level squeeze' series (Outcomes module).

    python3 scripts/refresh_entry_level_squeeze.py   # -> data/entry_level_squeeze.yaml, then build.py

Public data only: JobTech / Platsbanken job ads (CC0). For each year, the share of openings that
require NO prior experience (an entry-level proxy, from the ad's structured 'experience' field),
computed separately for the MOST- vs LEAST-AI-exposed occupations (DAIOE generative-AI terciles
over SSYK). The 'experience' field is populated from 2020, so the series starts there.

The story is the high-minus-low GAP: AI-exposed occupations advertise proportionally fewer
entry-level openings, and the gap widens. Descriptive, an ad-based echo of the Canaries finding;
not causal (the negative gap is partly structural, since less-exposed work skews lower-skill).

Source CSV: lab-infrastructure/ai-monitor/scripts/entry_level_squeeze.py.
"""
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path.home() / "Documents/Workspace/lab-infrastructure/ai-monitor/data/entry_level_squeeze.csv"
FIRST_YEAR = 2020                       # 'experience' field unpopulated before 2020
DAIOE_VARIANT, DAIOE_VERSION = "generative-AI", "v2023"


def main():
    by_year = defaultdict(dict)
    with open(SRC, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            y = int(r["year"])
            if y < FIRST_YEAR:
                continue
            by_year[y][r["tier"]] = float(r["noexp_share_pct"])

    series = []
    for y in sorted(by_year):
        hi, lo = by_year[y].get("high"), by_year[y].get("low")
        if hi is None or lo is None:
            continue
        # gap = most-exposed minus least-exposed entry-level share (negative = the squeeze)
        series.append({"year": y, "high": round(hi, 1), "low": round(lo, 1), "gap": round(hi - lo, 1)})

    if not series:
        raise SystemExit("no usable rows found in " + str(SRC))

    ymax = 5 * (int(max(s["low"] for s in series) // 5) + 1)   # round up to a clean 5
    lines = [
        "# Entry-level squeeze (Monitor Outcomes module). Auto-generated; rerun",
        "# scripts/refresh_entry_level_squeeze.py then build.py. Public data, descriptive.",
        "meta:",
        f'  daioe_variant: "{DAIOE_VARIANT}"',
        f'  daioe_version: "{DAIOE_VERSION}"',
        '  source: "JobTech / Platsbanken job ads (CC0)"',
        '  measure: "Share of openings requiring no prior experience, by AI-exposure tier (DAIOE genai terciles, SSYK)"',
        f"  first_year: {series[0]['year']}",
        f"  last_year: {series[-1]['year']}",
        f"  gap_first: {series[0]['gap']}",
        f"  gap_last: {series[-1]['gap']}",
        f"  ymax: {ymax}",
        "series:",
    ]
    for s in series:
        lines.append(f"  - {{year: {s['year']}, high: {s['high']}, low: {s['low']}, gap: {s['gap']}}}")
    out = ROOT / "data" / "entry_level_squeeze.yaml"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out.name}: {len(series)} years {series[0]['year']}-{series[-1]['year']}, "
          f"gap {series[0]['gap']:+} -> {series[-1]['gap']:+} pp")


if __name__ == "__main__":
    main()
