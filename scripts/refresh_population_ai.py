#!/usr/bin/env python3
"""Refresh Swedish POPULATION genAI use from SCB, for the Adoption module.

    python3 scripts/refresh_population_ai.py        # writes data/population_ai.yaml

Why this exists. The Adoption module measures firms (Eurostat, SCB's enterprise ICT
survey) and one slice of workers (Akavia, a professional-union panel). It has had nothing
representative of the population. SCB publishes exactly that: "Befolkningens it-användning"
now carries a dedicated AI area (LE0108Q) with genAI use for ages 16–74, by sex and age,
with margins of error — a probability sample and official statistics, which is a stronger
instrument than anything else in the module.

This is the PUBLIC aggregate. The lab separately holds BITA microdata in MONA
(ORU-MICRO-AI, individual-level genAI use, purpose and non-use reasons); that is red-zone
research data and must never reach this site. The two are different objects with the same
origin — use this file for the Monitor and MONA for papers.

Tables:
  LE0108T82  Använt generativa AI-verktyg — share of persons. Clean, both waves, used.
  LE0108T83  Syfte (professional / education / private). Two uses:
             (a) purpose_latest: the latest cross-section for all 16–74.
             (b) employed_work: the worker-level rate, i.e. the share of ALL employed
                 persons (group "Anställda/Egna företagare") who used genAI for
                 professional or work-related purposes. Written from 2025 only.
             BASE, verified 9 Oct 2026 and re-verified on every run (base_check below):
             T83 is "andel personer" of the whole reporting group, not of genAI users.
             The estimated count divided by the share reproduces the group's population
             as implied by T82 (2025: 4.64M both; 2026: 4.22M vs 4.25M), whereas a
             users-only base would be T82's user count (2.09M, 2.59M). The group is
             self-reported main activity "arbetande" (employees, self-employed, unpaid
             family workers), ages 16+ with no upper bound (SCB, "BITA Redovisnings-
             grupper", 2026-10-05). Recall: last three months before Q1 (kvalitets-
             deklaration 2026, Table 2).
             WHY NOT 2024: genAI was a Swedish national add-on in 2024 and part of
             Eurostat's model questionnaire from 2025 (kvalitetsdeklaration 2026, p. 16).
             The 2024 purposes do not cohere (employed: formal education 20%, private 3%,
             against 4% and 36% in 2025), so 2024 is a different instrument, not a wave.

Stdlib only. api.scb.se is on the lab allowlist.

Auto-applied weekly since 17 Aug 2026 (scripts/weekly_refresh.py). Unlike the barriers pull,
a new wave here is welcome: the survey year comes from the API rather than from a constant,
and T82 carries no break, so the gate only checks that the year does not go backwards.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "population_ai.yaml"
BASE = "https://api.scb.se/OV0104/v1/doris/sv/ssd/LE/LE0108/LE0108Q"

AGES = ["16-24", "25-34", "35-44", "45-54", "55-64", "65-74"]
AGE_LABEL = {"16-24": "16–24", "25-34": "25–34", "35-44": "35–44",
             "45-54": "45–54", "55-64": "55–64", "65-74": "65–74"}


def post(table: str, query: list) -> dict:
    req = urllib.request.Request(
        f"{BASE}/{table}",
        data=json.dumps({"query": query, "response": {"format": "json"}}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def num(v):
    """SCB writes '..' for suppressed cells; keep them out of the yaml as null."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


EMP = "ansfor"          # SCB reporting group "Anställda/Egna företagare"
EMP_FIRST = "2025"      # first wave on Eurostat's model questionnaire; 2024 is not comparable


def table_updated(table: str) -> str:
    """SCB's own publication stamp for a table (date part), from the level listing.
    Used as the vintage instead of a fetch date, so a weekly rerun that finds nothing new
    leaves the yaml byte-identical."""
    with urllib.request.urlopen(BASE, timeout=60) as r:
        for t in json.loads(r.read()):
            if t["id"] == table:
                return t["updated"][:10]
    raise SystemExit(f"{table} is no longer listed under LE0108Q; check SCB before publishing")


def employed_work_block(latest: str) -> list[str]:
    """Share of ALL employed persons (16+) who used genAI for work, with SCB's margins.

    The base is asserted, not assumed: for each year the group population implied by T83
    (count / share) must match the one implied by T82 (count / share) within 6%, which
    holds only if T83's share is of the whole group. If SCB ever switched T83 to a
    users-only base the implied population would fall to the user count (roughly half)
    and this stops the refresh instead of publishing a mislabelled rate."""
    q = [{"code": "Kon", "selection": {"filter": "item", "values": ["1+2"]}},
         {"code": "Redovisningsgrupp", "selection": {"filter": "item", "values": [EMP]}}]
    t83 = post("LE0108T83", [{"code": "SyftAnd", "selection": {"filter": "item",
                                                               "values": ["ProfarbAnd"]}}] + q)
    t82 = post("LE0108T82", [{"code": "AnvInternet", "selection": {"filter": "item",
                                                                   "values": ["1280"]}}] + q)
    # values order follows ContentsCode: count, count moe, share, share moe
    work = {e["key"][3]: [num(v) for v in e["values"]] for e in t83["data"]}
    used = {e["key"][3]: [num(v) for v in e["values"]] for e in t82["data"]}
    years = sorted(y for y in work if y >= EMP_FIRST and work[y][2] is not None)
    assert years and years[-1] == latest, f"employed work-use years {years} vs survey {latest}"
    L = ["employed_work:",
         "  # Share of ALL employed persons aged 16+ (SCB group \"Anställda/Egna företagare\":",
         "  # main activity working, employees and self-employed) who used generative AI for",
         "  # professional or work-related purposes in the last three months (Q1 survey).",
         "  # NOT a share of genAI users: base_check reproduces the group population from",
         "  # both tables each run. From 2025 only; see the script header for why not 2024.",
         '  indicator: "Employed persons who used generative AI for work"',
         '  unit: "% of all employed persons aged 16+"',
         '  group: "Anställda/Egna företagare (employees and self-employed)"',
         '  source: "SCB, Befolkningens it-användning / ICT use among the population '
         '(LE0108T83)"',
         f'  scb_updated: "{table_updated("LE0108T83")}"',
         "  series:"]
    for y in years:
        n, _, pct, moe = work[y]
        un, _, upct, _ = used[y]
        pop83, pop82 = n / pct * 100, un / upct * 100
        assert abs(pop83 / pop82 - 1) < 0.06, (
            f"{y}: T83 implies {pop83:,.0f} employed, T82 {pop82:,.0f}; the purpose share "
            "may no longer be of all employed. Check SCB before publishing.")
        L.append(f"    - {{year: {y}, pct: {pct:g}, moe: {moe:g}, "
                 f"base_check: {{pop_t83: {round(pop83, -4):.0f}, pop_t82: {round(pop82, -4):.0f}, "
                 f"users_t82: {un:.0f}}}}}")
    return L


def main() -> None:
    # ── headline + age gradient + sex, both waves
    d = post("LE0108T82", [
        {"code": "AnvInternet", "selection": {"filter": "item", "values": ["1280"]}},
        {"code": "Kon", "selection": {"filter": "item", "values": ["1", "2", "1+2"]}},
        {"code": "Redovisningsgrupp",
         "selection": {"filter": "item", "values": ["tot16-74"] + AGES}},
        {"code": "ContentsCode",
         "selection": {"filter": "item", "values": ["000007L5", "000007LA"]}},
    ])
    cell = {}
    for e in d["data"]:
        _, sex, grp, yr = e["key"]
        cell[(grp, yr, sex)] = (num(e["values"][0]), num(e["values"][1]))
    years = sorted({k[1] for k in cell})
    latest, first = years[-1], years[0]

    def g(grp, yr, sex="1+2"):
        return cell.get((grp, yr, sex), (None, None))

    tot_l, moe_l = g("tot16-74", latest)
    tot_f, _ = g("tot16-74", first)
    men_l, _ = g("tot16-74", latest, "1")
    wom_l, _ = g("tot16-74", latest, "2")
    men_f, _ = g("tot16-74", first, "1")
    wom_f, _ = g("tot16-74", first, "2")

    L = [
        "# Swedish POPULATION genAI use — Adoption module, population level.",
        "# Generated by scripts/refresh_population_ai.py from SCB Befolkningens it-användning",
        "# (LE0108Q). DO NOT hand-edit; rerun the script, then build.py.",
        "#",
        "# This is the public aggregate. The lab's BITA microdata in MONA is red-zone and",
        "# must never appear here; see the script header.",
        "meta:",
        '  indicator: "Persons who have used generative AI tools"',
        '  unit: "% of persons aged 16–74"',
        # The English gloss is not decoration. build.py prints this string verbatim in the
        # figure footer of both editions, so on the English site a bare Swedish table name
        # was the only thing telling a reader what the source is; the 28 Jul 2026 pass that
        # glossed the Swedish source names edited the yaml and not this line, which meant
        # every run of this script since would have reverted it. Keep the gloss here.
        '  source: "SCB, Befolkningens it-användning / ICT use among the population '
        '(LE0108T82)"',
        '  url: "https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__LE__LE0108__LE0108Q/"',
        f'  year: {latest}',
        f'  first_year: {first}',
        '  design: "probability sample, official statistics; margins of error published"',
        '  reference_period: "first quarter of the survey year"',
        f'  headline: {tot_l:g}',
        f'  headline_moe: {moe_l:g}',
        f'  headline_first: {tot_f:g}',
        f'  men: {men_l:g}',
        f'  women: {wom_l:g}',
        f'  men_first: {men_f:g}',
        f'  women_first: {wom_f:g}',
        "by_age:",
    ]
    for a in AGES:
        cur, moe = g(a, latest)
        prev, _ = g(a, first)
        if cur is None:
            continue
        L.append(f'  - {{group: "{AGE_LABEL[a]}", adoption: {cur:g}, moe: {moe:g}, '
                 f'prev: {prev if prev is not None else "null"}}}')

    # ── purpose, latest wave only (see header for why not a series)
    p = post("LE0108T83", [
        {"code": "SyftAnd", "selection": {"filter": "item",
                                          "values": ["ProfarbAnd", "FormUtb", "PrivAnd"]}},
        {"code": "Kon", "selection": {"filter": "item", "values": ["1+2"]}},
        {"code": "Redovisningsgrupp", "selection": {"filter": "item", "values": ["tot16-74"]}},
        {"code": "ContentsCode", "selection": {"filter": "item", "values": ["000007LC"]}},
    ])
    lab = {"ProfarbAnd": "professional or work-related", "FormUtb": "formal education",
           "PrivAnd": "private"}
    L += ["purpose_latest:",
          f"  # {latest} cross-section only. Multiple response, share of ALL persons 16–74.",
          "  # The 2024 wave is deliberately omitted: its base is not reconcilable with this",
          "  # one (purposes sum to 41 against 28% total use in 2024, 66 against 42 in 2025;",
          "  # formal education halves while private quadruples). Base confirmed 9 Oct 2026:",
          "  # share of all persons; 2024 was a national add-on, Eurostat's module from 2025.",
          f"  year: {latest}",
          "  shares:"]
    for e in p["data"]:
        if e["key"][3] != latest:
            continue
        v = num(e["values"][0])
        if v is not None:
            L.append(f'    - {{purpose: "{lab[e["key"][0]]}", pct: {v:g}}}')

    # ── worker level: employed persons using genAI for work (see header: base and break)
    L += employed_work_block(latest)

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {latest} headline {tot_l:g}% (±{moe_l:g}), "
          f"{first} {tot_f:g}%; {len(AGES)} age groups; purpose {latest} only")


if __name__ == "__main__":
    main()
