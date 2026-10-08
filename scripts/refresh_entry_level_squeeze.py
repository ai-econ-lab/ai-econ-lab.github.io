#!/usr/bin/env python3
"""Refresh the Monitor 'Entry-level squeeze' series (Outcomes module).

    python3 scripts/refresh_entry_level_squeeze.py   # -> data/entry_level_squeeze.yaml, then build.py

Public data only: JobTech / Platsbanken job ads (CC0). For each year, the share of openings that
require NO prior experience (an entry-level proxy, from the ad's structured 'experience' field),
computed separately for the MOST- vs LEAST-AI-exposed occupations (terciles of SSYK 2012
occupations by DAIOE's generative-AI composite g2gen, v1.1.0, score year 2025, since 8 Oct 2026;
until then the legacy genai index). Aggregation (Magnus, 8 Oct 2026, v1.7): EMPLOYMENT-WEIGHTED
occupations: each occupation's own no-experience share of its API ad records (50+ records that
year), averaged within the tier with 2024 employment weights (SCB YREG50BAS). Until v1.7 the
module pooled ad records within each tier, which let a few large-volume occupations near the
tier boundaries carry the gap (v1.7 revision log, "Exposure input moved to DAIOE v1.1.0").
The 'experience' field is populated from 2020, so the series starts there.

The story is the high-minus-low GAP: AI-exposed occupations advertise somewhat fewer entry-level
openings, but the gap has NOT widened (about -6pp in 2020, about -5pp in 2025 on g2gen). The
earlier "widening" reading (-3.1 -> -5.3pp, pooled records, 2023 index) did not hold up. Descriptive,
not causal (the negative gap is partly structural, since less-exposed work skews lower-skill).

Source CSV: lab-infrastructure/ai-monitor/scripts/entry_level_squeeze.py.
"""
import csv
from collections import defaultdict
from pathlib import Path

from monitor_root import MONITOR_ROOT

ROOT = Path(__file__).resolve().parent.parent
SRC = MONITOR_ROOT / "data/entry_level_squeeze.csv"
FIRST_YEAR = 2020                       # 'experience' field unpopulated before 2020
DAIOE_VARIANT, DAIOE_VERSION = "generative-AI composite (g2gen)", "v2025"


def main():
    by_year = defaultdict(dict)
    with open(SRC, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            y = int(r["year"])
            if y < FIRST_YEAR:
                continue
            by_year[y][r["tier"]] = float(r["noexp_share_pct"])
            by_year[y][r["tier"] + "_n"] = int(r["n_occ"])

    series = []
    for y in sorted(by_year):
        hi, lo = by_year[y].get("high"), by_year[y].get("low")
        if hi is None or lo is None:
            continue
        # gap = most-exposed minus least-exposed entry-level share (negative = the squeeze)
        # gap from the two rounded shares, so the page's numbers add up as printed
        series.append({"year": y, "high": round(hi, 1), "low": round(lo, 1),
                       "gap": round(round(hi, 1) - round(lo, 1), 1)})

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
        '  measure: "Share of openings requiring no prior experience, by AI-exposure tier (DAIOE g2gen terciles, SSYK), employment-weighted occupations"',
        '  aggregation: "employment-weighted occupations (SCB YREG50BAS 2024), occupations with 50+ ad records a year"',
        f"  n_occ_high_last: {by_year[series[-1]['year']]['high_n']}",
        f"  n_occ_low_last: {by_year[series[-1]['year']]['low_n']}",
        # widest gap in the window, so the page can say the gap has not widened with the numbers
        f"  gap_min: {min(s['gap'] for s in series)}",
        f"  gap_min_year: {min(series, key=lambda s: s['gap'])['year']}",
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
