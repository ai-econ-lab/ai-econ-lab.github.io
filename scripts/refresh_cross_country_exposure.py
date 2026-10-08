#!/usr/bin/env python3
"""Build data/cross_country.yaml: share of each country's jobs in the most AI-exposed occupations.

    python3 scripts/refresh_cross_country_exposure.py            # -> data/cross_country.yaml, then build.py

WHY THIS FILE EXISTS (8 Oct 2026). The Monitor's 'Across countries' exposure view was built by
two scripts in the AI Unboxed repo (projects/daioe/cross-country-heterogeneity/scripts/
04_country_exposure_view.py and 05_top_tier_share.py) from a pre-release DAIOE panel whose path
no longer exists. When Magnus moved every DAIOE-based Monitor module to the v1.1.0
second-generation composites (8 Oct 2026, decision recorded in ai-monitor
notes/2026-10-08_task_daioe-v110-composites.md), the view needed a generator that reads the
PUBLISHED deposit, like scripts/build_daioe_occupations.py does for the DAIOE page. This is it.
The method is the one of 04 + 05, unchanged:

  1. Exposure by ISCO-08 2-digit sub-major group = unweighted mean of the 4-digit scores in the
     group (the two 3-digit rows the bundle carries, 211 and 315, are included, as before).
     Economic logic: the EU-LFS publishes employment only at 2 digits.
  2. Most AI-exposed = the top 25% of those groups by exposure (cut at the 75th-percentile score,
     ties in; 11 of 40 groups).
  3. For each country, the share of employment (EU-LFS lfsa_egai2d, ages 15-64, thousands) in
     those groups, at the weight year or the country's latest earlier year. The `exposure`
     column is the employment-weighted mean group score, kept for reference and the CSV.

Exposure input (from v1.1.0): `daioe_g2gen`, the second-generation generative composite
(language modelling, image generation, conversation, software engineering; standardised units),
vintage-2025, score year 2025. Levels are not comparable to the legacy v2023 scale; the
top-25% membership is what the page uses. Most of the 2025 step comes from software
engineering's first measured year (VINTAGES.md, "Known caveats").

The bundle is read from the pipeline's local dist/ copy and checked against SHA256SUMS.
EU-LFS is pulled live from Eurostat (ec.europa.eu, allowlisted), like refresh_cross_country.py.

Options exist for one reason, the faithfulness check: `--col daioe_genai --year 2023
--weight-year 2023` must reproduce the v2023 file's membership and shares.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics as st
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = Path(os.environ.get("AIEL_WORKSPACE", ROOT.parents[1]))
BUNDLE = WORKSPACE / "lab-infrastructure/daioe-pipeline/dist/daioe-v1.1.0-scores"
VINTAGE = "vintage-2025"
PANEL = f"{VINTAGE}/daioe_isco08.tsv"
OUT = ROOT / "data" / "cross_country.yaml"

COL, YEAR = "daioe_g2gen", 2025          # exposure input (ML, 8 Oct 2026)
WEIGHT_YEAR = 2025                       # newest EU-LFS year on 8 Oct 2026 (was 2023)
FIRST_LFS_YEAR = 2019                    # earliest fallback year for a country missing the weight year

EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/lfsa_egai2d"
NAMES = {"LU": "Luxembourg", "SE": "Sweden", "NL": "Netherlands", "CH": "Switzerland",
         "BE": "Belgium", "UK": "United Kingdom", "NO": "Norway", "DK": "Denmark",
         "IE": "Ireland", "DE": "Germany", "FI": "Finland", "IS": "Iceland", "FR": "France",
         "MT": "Malta", "CY": "Cyprus", "LT": "Lithuania", "AT": "Austria", "EE": "Estonia",
         "PL": "Poland", "PT": "Portugal", "LV": "Latvia", "SI": "Slovenia", "CZ": "Czechia",
         "HR": "Croatia", "IT": "Italy", "SK": "Slovakia", "HU": "Hungary", "EL": "Greece",
         "ME": "Montenegro", "ES": "Spain", "MK": "N. Macedonia", "RS": "Serbia",
         "BG": "Bulgaria", "BA": "Bosnia & Herz.", "RO": "Romania", "TR": "Turkey",
         "AL": "Albania"}


def check_bundle() -> None:
    """Refuse to run off the deposit: the panel must match SHA256SUMS."""
    for line in (BUNDLE / "SHA256SUMS").read_text().splitlines():
        if line.strip().endswith(PANEL):
            want = line.split()[0]
            got = hashlib.sha256((BUNDLE / PANEL).read_bytes()).hexdigest()
            if got != want:
                raise SystemExit(f"SHA256 mismatch for {PANEL}: bundle is not the v1.1.0 deposit")
            print(f"bundle verified: {PANEL} matches SHA256SUMS")
            return
    raise SystemExit(f"{PANEL} not listed in SHA256SUMS")


def exposure_isco2d(col: str, year: int) -> dict[str, float]:
    """Unweighted mean of the 4-digit (and the two 3-digit) scores within each 2-digit group."""
    d = pd.read_csv(BUNDLE / PANEL, sep="\t", dtype={"occ_code_isco08": str})
    d = d[(d["year"] == year) & d[col].notna()].copy()
    d["isco2d"] = d["occ_code_isco08"].str[:2]
    return d.groupby("isco2d")[col].mean().to_dict()


def fetch_lfs(years: list[int]) -> pd.DataFrame:
    """EU-LFS employment (thousands, 15-64) by country x year x ISCO-08 2-digit."""
    rows = []
    for y in years:
        qs = urllib.parse.urlencode([("format", "JSON"), ("lang", "EN"), ("age", "Y15-64"),
                                     ("sex", "T"), ("unit", "THS_PER"), ("time", str(y))])
        req = urllib.request.Request(f"{EUROSTAT}?{qs}",
                                     headers={"User-Agent": "python-urllib (research use)"})
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.load(r)
        ids, sizes = d["id"], d["size"]
        code_of = {k: [c for c, _ in sorted(d["dimension"][k]["category"]["index"].items(),
                                            key=lambda kv: kv[1])] for k in ids}
        for flat, v in d["value"].items():
            rem, coords = int(flat), []
            for s in reversed(sizes):
                coords.append(rem % s); rem //= s
            rec = {k: code_of[k][c] for k, c in zip(ids, reversed(coords))}
            rows.append({"country": rec["geo"], "year": int(rec["time"]),
                         "isco08": rec["isco08"], "emp_ths": v})
    df = pd.DataFrame(rows)
    # real countries only (2-letter codes, not the EU/EA aggregates); true 2-digit codes only
    df = df[(df["country"].str.len() == 2) & ~df["country"].isin(["EU", "EA"])]
    df = df[df["isco08"].str.fullmatch(r"OC\d\d")]
    df["isco2d"] = df["isco08"].str[2:]
    return df[["country", "year", "isco2d", "emp_ths"]]


def usable_year(lfs: pd.DataFrame, floor: float = 0.8) -> dict[str, int]:
    """Each country's weight year: the latest year whose published cells are not thinned out.

    Eurostat suppresses unreliable cells, and a suppressed cell leaves the denominator too.
    Luxembourg's 2025 release publishes 16 2-digit cells against 29 in 2024 and 31 in 2023
    (86% of its 2024 employment), which would lift its top-tier share from about 66% to 75%
    by deletion alone. A year counts only if it publishes at least `floor` of the most cells
    the country publishes in any year pulled; otherwise the country falls back a year, and the
    page marks the year it uses ('YY). Counting cells, not employment, keeps a real fall in
    employment (Montenegro, 2020) from reading as suppression.
    """
    n = lfs.groupby(["country", "year"])["isco2d"].nunique()
    out = {}
    for c in lfs["country"].unique():
        cells = n[c]
        ok = [y for y in cells.index if cells[y] >= floor * cells.max()]
        out[c] = int(max(ok))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--col", default=COL)
    ap.add_argument("--year", type=int, default=YEAR)
    ap.add_argument("--weight-year", type=int, default=WEIGHT_YEAR)
    ap.add_argument("--lfs-csv", help="read EU-LFS from a local CSV (country,year,isco2d,emp_ths) "
                                      "instead of Eurostat; used for the faithfulness check")
    ap.add_argument("--dry-run", action="store_true", help="print, do not write the yaml")
    a = ap.parse_args()

    check_bundle()
    expo = exposure_isco2d(a.col, a.year)
    scores = sorted(expo.values())
    cut = scores[int(round(len(scores) * 3 / 4)) - 1]           # TOP QUARTILE (top 25%)
    top = {k for k, v in expo.items() if v >= cut}

    if a.lfs_csv:
        lfs = pd.read_csv(a.lfs_csv, dtype={"isco2d": str, "country": str})
        lfs["isco2d"] = lfs["isco2d"].str.zfill(2)
    else:
        lfs = fetch_lfs(list(range(FIRST_LFS_YEAR, a.weight_year + 1)))
    lfs = lfs[lfs["year"] <= a.weight_year].dropna(subset=["emp_ths"])
    latest = usable_year(lfs)

    out = []
    for c, g in lfs.groupby("country"):
        if c not in NAMES:
            continue
        occ = g[g["year"] == latest[c]].set_index("isco2d")["emp_ths"].to_dict()
        total = sum(occ.values())
        den = sum(e for i, e in occ.items() if i in expo)
        if den <= 0:
            continue
        out.append({
            "code": c, "name": NAMES[c],
            "share": round(sum(e for i, e in occ.items() if i in top) / den * 100, 1),
            "exposure": round(sum(e * expo[i] for i, e in occ.items() if i in expo) / den, 4),
            "coverage": round(den / total * 100, 1), "year": int(latest[c]), "is_se": c == "SE"})
    out.sort(key=lambda r: -r["share"])
    mean_share = round(st.mean(r["share"] for r in out), 2)   # 2 dp: a 1-dp 36.5 prints as "36"
    mean_expo = round(st.mean(r["exposure"] for r in out), 3)
    se = next(r for r in out if r["code"] == "SE")
    print(f"{a.col} {a.year}: top tier = {len(top)} of {len(expo)} ISCO-2d groups {sorted(top)}")
    print(f"weights: EU-LFS {a.weight_year} (latest-year fallback for "
          f"{sorted(c for c, y in latest.items() if y < a.weight_year and c in NAMES)})")
    print(f"SE {se['share']}% (rank {out.index(se) + 1} of {len(out)}); mean {mean_share}%; "
          f"top 3 {[(r['code'], r['share']) for r in out[:3]]}")
    if a.dry_run:
        return

    version = f"v{a.year}"
    variant = "generative-AI composite (g2gen)" if a.col == "daioe_g2gen" else "generative-AI"
    meta = {
        "variant": variant,
        "daioe_version": version,
        "daioe_column": a.col,
        "metric": f"Share of employment in the most AI-exposed occupations (top 25% of occupations by DAIOE {a.col.removeprefix('daioe_')})",
        "tier_note": (f"Most AI-exposed occupations = the top 25% (quartile) of ISCO-08 2-digit "
                      f"occupations by DAIOE {variant} exposure, {version}"),
        "employment_source": "Eurostat EU-LFS (lfsa_egai2d)",
        "weight_year": a.weight_year,
        "mean": mean_expo,
        "mean_share": mean_share,
        "n_countries": len(out),
        "note": "Descriptive only. Exposure is not displacement: exposure predicts occupational growth as often as decline.",
    }
    L = ["# Cross-country workforce AI-exposure - Monitor 'Across countries' (View A).",
         "# INTERPRETABLE metric: share of jobs in the most AI-exposed occupations (top 25% of ISCO-08 2-digit groups).",
         "# Generated by scripts/refresh_cross_country_exposure.py (DAIOE v1.1.0 bundle x Eurostat EU-LFS). Do not hand-edit.",
         "meta:"]
    for k, v in meta.items():
        L.append(f'  {k}: "{v}"' if isinstance(v, str) else f"  {k}: {v}")
    L.append("countries:")
    for r in out:
        L.append(f'  - {{code: "{r["code"]}", name: "{r["name"]}", share: {r["share"]}, '
                 f'exposure: {r["exposure"]}, coverage: {r["coverage"]}, year: {r["year"]}, '
                 f'is_se: {str(r["is_se"]).lower()}}}')
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    yaml.safe_load(OUT.read_text(encoding="utf-8"))            # refuse to leave a broken file
    print(f"wrote {OUT.name}: {len(out)} countries")


if __name__ == "__main__":
    main()
