#!/usr/bin/env python3
"""Build data/trend.yaml: the annual AI-in-demand series, 2006 onwards.

WHY THIS EXISTS. Until 25 August 2026 the two trend lines were literal arrays typed by hand
into monitor.yaml, while build.py stamped every point with DEF_LABEL, which is derived from
the site's current DEF_VERSION. The label therefore tracked the freeze automatically and the
numbers only moved when somebody retyped them. At the v1.5 freeze nobody did, so the site
published the v1.4 series under a "frozen v1.5" stamp for six days: twenty of twenty-one rows
matched bulk_v14 exactly and none matched bulk_v15.

It was not a small difference. The v1.5 cleanup removes false friends (`klustring`, `tts`,
`moses`, `mapreduce`) and guards bare `ML`, and those removals bite hardest in the thin base
years. So the pooled 2006-08 base falls from 0.033% to 0.028% while 2025 barely moves, and the
headline multiple goes from 32x to 38x. The site published a 38x tile three inches above a
chart drawn from the 32x series, and both one-pagers said 32x under a "frozen v1.5" source
line.

This is the same defect the monthly block hit on 19 August, and it has the same remedy, which
build.py already applies there: a module states the definition IT was built from rather than
the site's. The trend was simply left behind. Two things follow from putting it here:

  1. The numbers are read from the generator, so they cannot drift from it by inaction.
  2. `meta.definition` travels with them, so the footer and the CSV stamp come from the data
     instead of from DEF_VERSION.

`--check` re-derives and compares without writing. That is the guard: it fails when the
committed series is not what the current bulk produces, which is the state the site was in
between 19 and 25 August and which nothing could see.

Run:  python3 scripts/refresh_trend.py
      python3 scripts/refresh_trend.py --check
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from monitor_root import MONITOR_ROOT, DEF_VERSION, DEF_FP, bulk_dir

SRC = MONITOR_ROOT / f"data/{bulk_dir()}/derived/series_annual.csv"
MANIFEST = SRC.parent / "_derived_manifest.json"
OUT = Path(__file__).resolve().parent.parent / "data" / "trend.yaml"

FIRST_YEAR = 2006


def genai_tile(rows: dict) -> dict:
    """The generative-AI tile's two numbers, which rotted independently of the trend.

    On 25 August the tile still read 28.7 per 10,000 from the v1.1 era while the count had
    been 1,217 since v1.3, i.e. 29.4. It is a hand-typed tile, so nothing recomputed it.
    """
    r = rows
    ads, genai, ai_any = int(r["ads"]), int(r["genai"]), int(r["ai_any"])
    return {"genai_per_10k": round(10000 * genai / ads, 1),
            "genai_share_of_ai_pct": round(100 * genai / ai_any)}


def read_series() -> tuple[list[int], list[float], list[float], int | None]:
    """Full calendar years, plus the current part-year folded into one appended point.

    The part-year rows carry a period suffix (`2026-H1`); the full years do not. They are
    summed rather than averaged, because a share of advertisements has to be recomputed from
    its own numerator and denominator, not averaged across halves of different sizes.
    """
    full, part = {}, []
    for r in csv.DictReader(SRC.open(encoding="utf-8")):
        y = r["year"]
        if "-" in y:
            part.append(r)
        else:
            full[int(y)] = r

    years = sorted(y for y in full if y >= FIRST_YEAR)
    # Two versions of the same series. The chart publishes three decimals; the multiples are
    # computed from the unrounded estimates, because the base years sit near 0.013% and
    # rounding them costs enough relative precision to move the floor multiple from 42 to 41.
    names_raw = [float(full[y]["ai_any_pct"]) for y in years]
    floor_raw = [float(full[y]["floor_pct"]) for y in years]

    provisional_from = None
    if part:
        ads = sum(int(r["ads"]) for r in part)
        names_raw.append(100 * sum(int(r["ai_any"]) for r in part) / ads if ads else 0.0)
        floor_raw.append(100 * sum(int(r["floor"]) for r in part) / ads if ads else 0.0)
        years.append(int(part[0]["year"].split("-")[0]))
        provisional_from = len(years) - 1
    return years, names_raw, floor_raw, provisional_from


def definition() -> str:
    """What the data says about itself, not what the site currently calls itself.

    The manifest is the same file check_vintages.py reads for the occupations module, so the
    two agree by construction rather than by anyone remembering to keep them aligned.
    """
    if MANIFEST.exists():
        d = json.loads(MANIFEST.read_text(encoding="utf-8"))
        text = str(d.get("definition") or d.get("version") or "")
        if text:
            return text if text.startswith("frozen") else f"frozen {text.split()[0]}"
    return f"frozen {DEF_VERSION}"


def multiples(years, names, floor) -> dict:
    """The fold-rises, computed once here instead of three times on the page.

    On 25 August the site carried four values for this one statistic: a hardcoded "22-fold"
    from the v1.3 era in the lede, a "32 times" computed in the panel against 2006 alone, a
    "38x" tile computed against a pooled 2006-08 base, and "about 32 times" in both one-pagers.
    Two of those were stale, and the other two differed because they used different bases.
    Emitting them here means the page states one number from one place.

    The pooled base matters: the early years are thin (about 60 flagged advertisements a year),
    so a single year's base makes the multiple hostage to noise in one number. The 2015-17 base
    is reported alongside because the term list has been stable across freezes there, which
    makes it the figure that does not move when the definition is cleaned.
    """
    idx = {y: i for i, y in enumerate(years)}

    def mean(cols, yrs):
        return sum(cols[idx[y]] for y in yrs) / len(yrs)

    last_full = max(y for y in years if y != years[-1]) if len(years) > 1 else years[-1]
    early, stable = (2006, 2007, 2008), (2015, 2016, 2017)
    out = {"base_years": "2006-2008", "last_full_year": last_full}
    if all(y in idx for y in early):
        out["base_pct"] = round(mean(names, early), 4)
        out["multiple"] = round(names[idx[last_full]] / mean(names, early), 1)
        out["multiple_floor"] = round(floor[idx[last_full]] / mean(floor, early), 1)
    if all(y in idx for y in stable):
        out["multiple_stable_base"] = round(names[idx[last_full]] / mean(names, stable), 1)
    return out


def render(years, names, floor, provisional_from, defn, extra=None) -> str:
    extra = extra or {}
    ymax = 1.5 if max(names) <= 1.5 else round(max(names) * 1.15, 1)
    ticks = [0, 0.5, 1.0, 1.5] if ymax == 1.5 else [0, ymax / 3, 2 * ymax / 3, ymax]
    lines = [
        "# Generated by scripts/refresh_trend.py. Do not hand-edit.",
        "#",
        "# Two lines. values = advertisements that NAME a specific AI skill anywhere in the",
        "# text; floor_values = advertisements that ASK for one in the role's own requirements.",
        "# The last point is the current part-year and is drawn provisional.",
        "meta:",
        f"  definition: {defn}",
        f"  def_fp: {DEF_FP}",
        f"  source: ai-monitor/{SRC.relative_to(MONITOR_ROOT)}",
        f"  first_year: {years[0]}",
        f"  last_year: {years[-1]}",
    ]
    for k, v in {**multiples(years, names, floor), **extra}.items():
        lines.append(f"  {k}: {v}")
    lines += [
        "trend:",
        f"  years:  [{', '.join(str(y) for y in years)}]",
        f"  values: [{', '.join(f'{round(v, 3):g}' for v in names)}]",
        f"  floor_values: [{', '.join(f'{round(v, 3):g}' for v in floor)}]",
    ]
    if provisional_from is not None:
        lines.append(f"  provisionalFrom: {provisional_from}")
    lines += [f"  ymax: {ymax:g}", f"  yticks: [{', '.join(f'{t:g}' for t in ticks)}]"]
    return "\n".join(lines) + "\n"


def tile_mismatches() -> list[str]:
    """The tiles are prose with a number in front, and they are typed by hand.

    They cannot be generated without turning the label into a template, so they are checked
    instead: whatever the tile asserts must equal what the series produces. This is the guard
    the "38x tile above a 32x chart" state needed and did not have.
    """
    import yaml
    site = Path(__file__).resolve().parent.parent / "data"
    doc = yaml.safe_load((site / "trend.yaml").read_text(encoding="utf-8"))["meta"]
    tiles = yaml.safe_load((site / "monitor.yaml").read_text(encoding="utf-8")).get("tiles", [])
    import re as _re
    out = []
    for tile in tiles:
        num, lab = str(tile.get("num", "")), str(tile.get("lab", ""))
        if "×" in num and "rise in ads" in lab:
            claimed_ = float(_re.sub(r"[^0-9.]", "", num))
            if abs(claimed_ - round(doc["multiple"])) > 0.5:
                out.append(f"tile says {num}, series gives {doc['multiple']:g}x")
            m = _re.search(r"floor rose (\d+)", lab)
            if m and abs(int(m.group(1)) - round(doc["multiple_floor"])) > 0.5:
                out.append(f"tile floor says {m.group(1)}x, series gives {doc['multiple_floor']:g}x")
            m = _re.search(r"the rise is ([\d.]+)×", lab)
            if m and abs(float(m.group(1)) - doc["multiple_stable_base"]) > 0.05:
                out.append(f"tile stable-base says {m.group(1)}×, series gives "
                           f"{doc['multiple_stable_base']:g}×")
        if "per 10,000" in lab:
            if abs(float(num) - doc["genai_per_10k"]) > 0.05:
                out.append(f"tile says {num} per 10,000, series gives {doc['genai_per_10k']}")
            m = _re.search(r"(\d+)% of AI demand", lab)
            if m and abs(int(m.group(1)) - doc["genai_share_of_ai_pct"]) > 0.5:
                out.append(f"tile says {m.group(1)}% of AI demand, series gives "
                           f"{doc['genai_share_of_ai_pct']}%")
    return out


def check() -> int:
    """Two halves, because they need different things to run.

    The TILE half reads only files in this repository, so it runs anywhere, CI included.
    The SERIES half needs the ai-monitor checkout, which CI deliberately does not have (see
    build-check.yml). It stands down loudly rather than passing quietly: a green run must not
    let anyone believe the series was compared when it was not. That is the same rule
    check_vintages.py states for itself, and it is the rule this defect broke.
    """
    problems = tile_mismatches()
    if SRC.exists():
        years, names, floor, prov = read_series()
        full = {r["year"]: r for r in csv.DictReader(SRC.open(encoding="utf-8"))
                if "-" not in r["year"]}
        last_full = str(max(int(y) for y in full))
        want = render(years, names, floor, prov, definition(), genai_tile(full[last_full]))
        if not OUT.exists():
            problems.append(f"{OUT.name} does not exist; run without --check to build it.")
        elif OUT.read_text(encoding="utf-8") != want:
            problems.append(
                f"{OUT.name} is not what {SRC.name} currently produces. The published series "
                f"has drifted from the generator, which is the state of 19-25 August 2026: a "
                f"v1.4 series under a v1.5 stamp. Fix: python3 scripts/refresh_trend.py")
    else:
        print("The series half did NOT run: no ai-monitor checkout at\n"
              f"  {SRC.parent}\n"
              "so trend.yaml was not compared against the generator. Only the tiles were\n"
              "checked. Set AI_MONITOR_ROOT to run the half that matters most.\n")

    if problems:
        print("FAIL")
        for b in problems:
            print(f"  {b}")
        return 1
    print(f"ok    tiles agree with trend.yaml"
          + (f", and trend.yaml matches {SRC.name} ({definition()})" if SRC.exists() else ""))
    return 0


def main() -> int:
    if "--check" in sys.argv:
        return check()
    if not SRC.exists():
        raise SystemExit(f"series not found: {SRC}\n  (DEF_VERSION is {DEF_VERSION})")
    years, names, floor, prov = read_series()
    full = {r["year"]: r for r in csv.DictReader(SRC.open(encoding="utf-8")) if "-" not in r["year"]}
    last_full = str(max(int(y) for y in full))
    text = render(years, names, floor, prov, definition(), genai_tile(full[last_full]))

    OUT.write_text(text, encoding="utf-8")
    m = multiples(years, names, floor)
    print(f"trend.yaml: {years[0]}-{years[-1]}, {definition()}")
    print(f"   {m['last_full_year']}: names {names[years.index(m['last_full_year'])]:.3f}%  "
          f"floor {floor[years.index(m['last_full_year'])]:.3f}%")
    print(f"   pooled {m['base_years']} base {m['base_pct']}%  ->  "
          f"{m['multiple']}x names, {m['multiple_floor']}x floor")
    print(f"   from the stable 2015-17 base: {m['multiple_stable_base']}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
