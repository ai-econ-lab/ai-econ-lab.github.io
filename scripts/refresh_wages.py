#!/usr/bin/env python3
"""Build data/wages.yaml: pay by DAIOE generative-AI exposure tercile.

WHY THIS EXISTS, AND WHY IT DID NOT UNTIL NOW. This was the last Monitor data file without a
generator, and the gap had already cost something. On 31 July the module was converted to real
terms (`ai-monitor/data/wages/deflate.py`, commit a27cead), read-gate item A7 was recorded as
closed, and the conversion never reached the site: that commit touches only ai-monitor files,
and `wages.yaml` was hand-edited, so there was no path for it to travel. The page went on
publishing nominal while the project's own record said real.

The same shape as `occupation_tiers.yaml`, which carried a false caption for the same reason,
and QUEUE records a near-miss where a hand edit "silently ate half of wages.yaml".

So: the basis is chosen HERE, in code, and written into the prose the page renders. Page and
method note cannot diverge again without this file changing.

WHY REAL TERMS (Magnus, 1 Aug 2026). The deflators are built, sourced and rerunnable, the
qualitative finding is stronger (Swedish real wages are flat in every exposure group over eleven
years, a starker null than "+34% nominal"), and leaving nominal would have left A7 wrong.

ONE ARITHMETIC POINT THAT MATTERS. Deflation leaves the HIGH/LOW pay RATIO exactly unchanged, so
the earlier note that "deflation does not change the between-group comparison" is true of the
ratio. It is NOT true of a DIFFERENCE OF GROWTH RATES, which is what the overview card reports:
the US gap is −8.9pp nominal against −6.6pp real. Any copy quoting a growth-rate gap must quote
the real one.

Run:  python3 scripts/refresh_wages.py [--nominal]

`--nominal` emits the pre-31-July basis and exists for one reason: it reproduces the previous
hand-maintained file, which is how this generator was checked for faithfulness rather than mere
plausibility.
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

import yaml

SRC = (Path.home() / "Documents/Workspace/lab-infrastructure/ai-monitor" / "data" / "wages")
OUT = Path(__file__).resolve().parent.parent / "data" / "wages.yaml"

COUNTRIES = [
    ("sweden", "Sweden · median monthly salary",
     "SCB wage structure statistics (lönestrukturstatistik), SSYK 2012 4-digit, all sectors, "
     "{first}–{last}; {n} occupations, employment-weighted (Yrkesregistret 2023)"),
    ("us", "United States · median annual wage",
     "BLS OEWS national, detailed SOC, May {first}–May {last}; {n} occupations, "
     "employment-weighted"),
]

# Named here because the page must state them and the page is generated from this file.
DEFLATORS = ("SCB KPI (2020=100), calendar-year mean, for Sweden; FRED CPI-U (NSA) at each "
             "May, matched to the OEWS reference month, for the United States; Eurostat HICP "
             "annual average for the EU27 line")


def load(key, real):
    """Series rows for one country, on the chosen basis."""
    fp = SRC / f"wages_exposure_{key}{'_real' if real else ''}.csv"
    if not fp.exists():
        raise SystemExit(f"REFUSING: {fp} missing. Run ai-monitor's wages_build.py"
                         + (" and deflate.py" if real else "") + " first.")
    col = "wage_index_real" if real else "wage_index"
    # n_occupations is PER TERCILE, so the panel size is the sum of the three, not the max.
    # Summing reproduces the US figure (692) in the hand-maintained file exactly. It gives
    # Sweden 314 where the hand-written string said 311; the module note says the balanced
    # panel is 314 (105/104/105) and separately that "all 311 ... carry a weight", so the note
    # disagrees with itself. 314 is what the series is actually built on, so 314 is published.
    per, ncount = defaultdict(dict), defaultdict(int)
    for r in csv.DictReader(fp.open(encoding="utf-8")):
        y = int(r["year"])
        per[y][r["exposure_group"].lower()] = round(float(r[col]), 1)
        ncount[y] += int(float(r["n_occupations"]))
    nocc = ncount[min(ncount)]
    if len(set(ncount.values())) != 1:
        raise SystemExit(f"REFUSING: {fp.name} panel size varies by year {dict(ncount)}; "
                         f"the series claims a balanced panel.")
    rows = [{"year": y, "high": v["high"], "mid": v["mid"], "low": v["low"]}
            for y, v in sorted(per.items())]
    return rows, nocc


def pct(series, g):
    """Growth over the whole window, in per cent, from an index based at 100."""
    return series[-1][g] - 100.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nominal", action="store_true",
                    help="emit the pre-31-July basis; used to verify this generator against "
                         "the hand-maintained file it replaces")
    a = ap.parse_args()
    real = not a.nominal
    prev = yaml.safe_load(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    basis = "real" if real else "nominal"

    countries = []
    for key, label, src in COUNTRIES:
        rows, nocc = load(key, real)
        countries.append({
            "key": key, "label": label,
            "source": src.format(first=rows[0]["year"], last=rows[-1]["year"], n=nocc),
            "base_year": rows[0]["year"], "series": rows,
        })

    se = next(c for c in countries if c["key"] == "sweden")["series"]
    us = next(c for c in countries if c["key"] == "us")["series"]
    gap_us = pct(us, "high") - pct(us, "low")

    if real:
        intro = ("Pay as an outcome: are wages in AI-exposed occupations pulling away, or "
                 "falling behind? Occupations are split into thirds by their DAIOE "
                 "generative-AI exposure; each line tracks the group's median wage in REAL "
                 "terms, indexed to 100 in the first year. Read the gap between lines, not "
                 "the level.")
        headline = (
            f"Over the past decade the most AI-exposed occupations have NOT pulled away in pay. "
            f"In the United States their real median wage grew {pct(us, 'high'):.1f} per cent "
            f"against {pct(us, 'low'):.1f} per cent for the least exposed "
            f"({us[0]['year']} to {us[-1]['year']}), a gap of {gap_us:.1f} percentage points the "
            f"other way. In Sweden real wages are close to flat in all three groups over "
            f"{se[0]['year']} to {se[-1]['year']} (most exposed {pct(se, 'high'):+.1f} per cent, "
            f"middle {pct(se, 'mid'):+.1f}, least {pct(se, 'low'):+.1f}). Read the post-2022 turn "
            f"with care: that window also covers the tightening cycle, which fell hardest on the "
            f"same professional and technical occupations, so its timing does not identify a "
            f"cause. AI-exposed occupations remain the best paid in level terms in both countries.")
        cav0 = (f"Real wages, deflated with {DEFLATORS}. Deflation leaves the pay RATIO between "
                f"groups exactly unchanged, so it cannot manufacture the result; it does change a "
                f"difference of growth rates, which is why the figures above are the real ones.")
    else:
        intro = prev.get("intro", "")
        headline = prev.get("headline", "")
        cav0 = ("Nominal wages; inflation affects all groups alike within a country, so the gap "
                "between lines is the signal.")

    doc = {
        "intro": intro,
        "headline": headline,
        "countries": countries,
        "eu_line": prev.get("eu_line", ""),
        "caveats": [
            cav0,
            "Exposure is DAIOE generative-AI (v2023), fixed over time: the lines answer how pay "
            "moved in occupations that are exposed today.",
            # Was "Sweden is unweighted across occupations", three lines below a source line
            # saying employment-weighted. The 27 July weighting updated the series and the
            # source string and not this caveat.
            "Both countries are employment-weighted, with weights held fixed (Sweden: "
            "Yrkesregistret 2023) so the index reads as wage growth rather than employment "
            "reallocation between occupations.",
            "Descriptive, not causal: composition, sector and skill mix all move wages too.",
        ],
    }
    OUT.write_text(
        f"# Wages by DAIOE generative-AI exposure tercile, {basis.upper()} terms.\n"
        f"# Generated by scripts/refresh_wages.py. Do not hand-edit: this file was hand-\n"
        f"# maintained until 1 Aug 2026, which is why the 31 July real-terms conversion never\n"
        f"# reached the page while read-gate A7 recorded it as shipped.\n"
        + yaml.dump(doc, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8")
    print(f"wages.yaml: {basis} terms, {len(countries)} countries")
    print(f"  US   {us[0]['year']}–{us[-1]['year']}: high {pct(us,'high'):+.1f}%  "
          f"low {pct(us,'low'):+.1f}%  gap {gap_us:+.1f}pp")
    print(f"  SE   {se[0]['year']}–{se[-1]['year']}: high {pct(se,'high'):+.1f}%  "
          f"low {pct(se,'low'):+.1f}%  gap {pct(se,'high')-pct(se,'low'):+.1f}pp")


if __name__ == "__main__":
    main()
