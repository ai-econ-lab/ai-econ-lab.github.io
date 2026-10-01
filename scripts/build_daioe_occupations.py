#!/usr/bin/env python3
"""Build assets/daioe_occupations.json and data/daioe_exposure.yaml for the DAIOE page.

The DAIOE page's occupation lookup ("How exposed is your job?"), its beeswarm and its
most/least-exposed lists all read these two files. Until 1 Oct 2026 the JSON was assembled
by hand from the frozen 2010-2023 window; this script rebuilds both from the PUBLISHED
release so every number on the page traces to a citable deposit (verification rule V14).

Source: the DAIOE v1.0.0 scores bundle (Zenodo, doi:10.5281/zenodo.21873968), folder
`refresh-2024/`, which carries the frozen 2010-2023 window cell-identically and chains 2024
at the seam. The bundle is read from the pipeline's local `dist/` copy; the script refuses
to run if SHA256SUMS does not match, so the page cannot silently drift off the deposit.

Two measures, both legacy columns whose membership never changes (VINTAGES.md):
  genai    generative AI: language modelling + image generation
  allapps  all AI: the nine original application areas, genai's two included

Two classifications:
  isco     ISCO-08, English titles (424 occupations with scores)
  ssyk     SSYK 2012, Swedish titles (423), so Swedish users can search in Swedish

Percentiles are computed within year and classification as the tie-invariant midrank
(100 * average rank / N), the convention the bundle README recommends over the legacy
pctl_rank_* columns. The JSON stores raw index values; the page derives ranks from them.

Run order: this script, then build.py. When a new vintage changes the JSON, bump the
`?v=` on the two fetches of daioe_occupations.json in assets/app.js, so browsers holding
the old file do not pair it with new code.
    python3 scripts/build_daioe_occupations.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
BUNDLE = WORKSPACE / "lab-infrastructure/daioe-pipeline/dist/daioe-v1.0.0-scores"
VERSION = "1.0.0"
DOI = "10.5281/zenodo.21873968"
VINTAGE = "refresh-2024"
FIRST_YEAR = 2012          # 2010 and 2011 are empty in every panel (benchmark coverage starts 2012)
N_EXTREMES = 10            # rows in each of the page's most/least lists

MEASURES = {
    "genai": {
        "label": "Generative AI",
        "short": "genAI",
        "def": "AI that produces text and images: language modelling (the technology behind "
               "chatbots such as ChatGPT) and image generation.",
    },
    "allapps": {
        "label": "All AI",
        "short": "all AI",
        "def": "AI as a whole: nine application areas, from image and speech recognition, "
               "translation and reading comprehension to games, plus the two generative ones.",
    },
}

# Everyday English words that do not appear in ISCO's formal titles, mapped to ISCO-08 codes.
# Each code is checked against the release below and its title printed, so a wrong code fails
# loudly instead of sending a nurse to the wrong occupation.
ALIASES = {
    "nurse": ["2221", "3221"], "doctor": ["2211", "2212"], "physician": ["2211", "2212"],
    "gp": ["2211"], "surgeon": ["2212"], "teacher": ["2330", "2341", "2342", "2310"],
    "professor": ["2310"], "lecturer": ["2310"], "attorney": ["2611"], "solicitor": ["2611"],
    "programmer": ["2512", "2514"], "coder": ["2512", "2514"], "software engineer": ["2512"],
    "reporter": ["2642"], "cook": ["5120"], "cleaner": ["9112"], "carer": ["5322", "5321"],
    "care worker": ["5322", "5321"], "police": ["5412"], "builder": ["7111", "7115"],
    "truck driver": ["8332"], "lorry": ["8332"], "taxi": ["8322"], "bus": ["8331"],
    "shop assistant": ["5223"], "retail": ["5223"], "data scientist": ["2120"],
    "statistician": ["2120"], "translator": ["2643"], "interpreter": ["2643"],
    "ceo": ["1120"], "chief executive": ["1120"], "graphic designer": ["2166"],
    "web developer": ["2513"], "it support": ["3512"], "call centre": ["4222"],
    "customer service": ["4222"], "hr": ["2423"], "recruiter": ["2423"],
    "bookkeeper": ["4311"], "vet": ["2250"], "paramedic": ["3258"], "firefighter": ["5411"],
    "consultant": ["2421"], "farmer": ["6111", "6121"], "warehouse": ["4321", "9333"],
    "courier": ["9621"], "pilot": ["3153"], "mechanic": ["7231"], "hairdresser": ["5141"],
    "waiter": ["5131"], "secretary": ["4120"],
}


def check_bundle() -> None:
    """Refuse to build from a bundle that differs from the deposited one."""
    sums = (BUNDLE / "SHA256SUMS").read_text().split("\n")
    checked = 0
    for line in sums:
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        name = name.lstrip("*")
        if not name.startswith(VINTAGE) or not name.endswith(".tsv"):
            continue
        got = hashlib.sha256((BUNDLE / name).read_bytes()).hexdigest()
        if got != digest:
            raise SystemExit(f"SHA256 mismatch for {name}: bundle is not the v{VERSION} deposit")
        checked += 1
    if checked != 5:
        raise SystemExit(f"expected 5 {VINTAGE} panels in SHA256SUMS, checked {checked}")
    print(f"bundle verified: {checked} {VINTAGE} panels match SHA256SUMS")


def load(tax: str) -> pd.DataFrame:
    """One taxonomy panel, long by occupation-year, with zero-padded code and title."""
    d = pd.read_csv(BUNDLE / VINTAGE / f"daioe_{tax}.tsv", sep="\t", dtype=str)
    d["year"] = d["year"].astype(float).astype(int)
    for m in MEASURES:
        d[m] = pd.to_numeric(d[f"daioe_{m}"])
    if tax == "isco08":
        d["code"] = d["occ_code_isco08"].str.zfill(4)
        d["title"] = d["occ_title_isco08"]
    else:
        # The refresh panel stores SSYK numerically (leading zeros lost); titles come from the
        # bundle's canonical list, exactly as DOCUMENTATION.md tells Swedish users to join.
        d["code"] = d["ssyk2012_4"].astype(float).astype(int).astype(str).str.zfill(4)
        t = pd.read_csv(BUNDLE / "occupation_titles_ssyk.csv", dtype=str)
        t = t[t.taxonomy == "ssyk2012"].set_index("code")["title"]
        d["title"] = d["code"].map(t)
        if d["title"].isna().any():
            raise SystemExit(f"SSYK codes without a title: {sorted(d.loc[d.title.isna(), 'code'].unique())}")
    d["title"] = d["title"].str.strip()   # ISCO titles carry stray trailing spaces in the release
    d = d[d.year >= FIRST_YEAR]
    keep = d.groupby("code")[list(MEASURES)].transform("count").min(axis=1) == d.year.nunique()
    return d[keep][["code", "title", "year", *MEASURES]].sort_values(["code", "year"])


def midrank_pctl(s: pd.Series) -> pd.Series:
    return 100 * s.rank(method="average") / len(s)


def build_set(d: pd.DataFrame, label: str, lang: str) -> dict:
    years = sorted(d.year.unique())
    occ = []
    for code, g in d.groupby("code", sort=True):
        g = g.set_index("year").loc[years]
        occ.append([code, g["title"].iloc[0],
                    [round(v, 4) for v in g["genai"]],
                    [round(v, 3) for v in g["allapps"]]])
    # Distribution bands for the trend chart: median and 10th-90th percentile, per year.
    dist = {}
    for m in MEASURES:
        q = d.groupby("year")[m].quantile([0.1, 0.5, 0.9]).unstack()
        dist[m] = {k: [round(v, 4) for v in q[p]] for k, p in (("p10", 0.1), ("p50", 0.5), ("p90", 0.9))}
    return {"label": label, "lang": lang, "n": len(occ), "occ": occ, "dist": dist}


def main() -> None:
    check_bundle()
    isco, ssyk = load("isco08"), load("ssyk2012")
    years = sorted(isco.year.unique())
    assert years == sorted(ssyk.year.unique())

    codes = set(isco.code)
    for word, cs in ALIASES.items():
        for c in cs:
            if c not in codes:
                raise SystemExit(f"alias {word!r} -> {c}: not an ISCO-08 code with scores")
    title = isco.drop_duplicates("code").set_index("code")["title"]
    for word, cs in ALIASES.items():
        print(f"  alias {word:18s} -> " + "; ".join(f"{c} {title[c]}" for c in cs))

    out = {
        "version": VERSION, "doi": DOI, "vintage": VINTAGE, "years": [int(y) for y in years],
        "year": int(years[-1]), "measures": MEASURES,
        "sets": {"isco": build_set(isco, "ISCO-08", "en"), "ssyk": build_set(ssyk, "SSYK 2012", "sv")},
        "aliases": ALIASES,
    }
    path = ROOT / "assets" / "daioe_occupations.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.0f} kB): "
          f"{out['sets']['isco']['n']} ISCO + {out['sets']['ssyk']['n']} SSYK occupations, {years[0]}-{years[-1]}")

    # Most/least-exposed lists for the page: generative AI, ISCO-08, latest year.
    last = isco[isco.year == years[-1]].copy()
    last["pctl"] = midrank_pctl(last["genai"]).round(1)
    last = last.sort_values("genai", ascending=False)
    row = lambda r: {"occ": r.title, "score": round(float(r.genai), 2), "pctl": float(r.pctl)}
    exp = {
        "note": "DAIOE generative-AI exposure by occupation (ISCO-08). Higher = more exposed.",
        "source": f"DAIOE v{VERSION} ({VINTAGE}), doi:{DOI}, AI-Econ Lab; built by scripts/build_daioe_occupations.py",
        "year": int(years[-1]),
        "most": [row(r) for r in last.head(N_EXTREMES).itertuples()],
        "least": [row(r) for r in last.tail(N_EXTREMES).itertuples()],
    }
    ypath = ROOT / "data" / "daioe_exposure.yaml"
    ypath.write_text(yaml.safe_dump(exp, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"wrote {ypath.relative_to(ROOT)}: top {exp['most'][0]['occ']} {exp['most'][0]['score']}, "
          f"bottom {exp['least'][-1]['occ']} {exp['least'][-1]['score']}")


if __name__ == "__main__":
    main()
