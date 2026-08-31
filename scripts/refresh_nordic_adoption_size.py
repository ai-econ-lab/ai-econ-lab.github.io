#!/usr/bin/env python3
"""Refresh the Adoption module's Nordic cut: AI adoption by firm size, four countries.

    python3 scripts/refresh_nordic_adoption_size.py   # -> data/nordic_adoption_size.yaml, then build.py

Public data: Eurostat isoc_eb_ai, indicator E_AI_TANY ("enterprises using at least one of the AI
technologies"), unit PC_ENT, NACE C10-S951_X_K. The Swedish total this returns, 35.0, is the same
figure SCB publishes nationally and the same one the cross-country bar shows, so the three agree
by construction rather than by luck.

Why four countries and not five: **Iceland has no row in this table at all.** It is present in the
exposure module, which comes from the LFS, and absent here. A country missing from a source is
missing, and the yaml says so rather than leaving a reader to infer it from a gap.

Why this cut and not adoption by industry: Eurostat publishes ONE NACE value, the all-activities
aggregate. Verified against the API on 31 Aug 2026 by listing the dimension. The industry cut on
the Monitor is Swedish because SCB publishes it nationally; there is no Nordic equivalent unless
DST, SSB and Tilastokeskus each publish their own.

DO NOT hand-edit the yaml.
"""
import json, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/isoc_eb_ai"
UA = "AI-Econ Lab research (mlodefalk@gmail.com)"
YEAR, PREV = "2025", "2021"
GEO = ["DK", "FI", "SE", "NO"]                      # Eurostat's own order; Iceland has no rows
# Eurostat size code -> (English, Swedish). GE10 is the headline that ties to the country bar.
SIZES = [("GE250", "250+ employees", "250+ anställda"),
         ("50-249", "50–249 employees", "50–249 anställda"),
         ("GE10", "All firms, 10+", "Alla företag, 10+"),
         ("10-49", "10–49 employees", "10–49 anställda")]


def fetch():
    q = "&".join(["format=JSON", "lang=EN", "unit=PC_ENT", "indic_is=E_AI_TANY"]
                 + [f"size_emp={s[0]}" for s in SIZES]
                 + [f"geo={g}" for g in GEO]
                 + [f"time={t}" for t in (PREV, YEAR)])
    with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA}),
                                timeout=60) as r:
        d = json.load(r)
    ids, size, val = d["id"], d["size"], d["value"]
    idx = {k: d["dimension"][k]["category"]["index"] for k in ids}
    names = d["dimension"]["geo"]["category"]["label"]

    def at(**sel):
        pos = 0
        for k, n in zip(ids, size):
            pos = pos * n + idx[k][sel[k]]
        return val.get(str(pos))

    out = {}
    for code, _, _ in SIZES:
        if code not in idx["size_emp"]:
            continue
        for g in idx["geo"]:
            cur = at(freq="A", unit="PC_ENT", size_emp=code, nace_r2="C10-S951_X_K",
                     indic_is="E_AI_TANY", geo=g, time=YEAR)
            prev = at(freq="A", unit="PC_ENT", size_emp=code, nace_r2="C10-S951_X_K",
                      indic_is="E_AI_TANY", geo=g, time=PREV)
            if cur is not None:
                out.setdefault(g, []).append((code, round(cur, 1),
                                              None if prev is None else round(prev, 1)))
    return out, names


def main():
    data, names = fetch()
    lbl = {c: (en, sv) for c, en, sv in SIZES}
    order = [c for c, _, _ in SIZES]

    lines = [
        "# AI adoption by firm size across the Nordics (Adoption module).",
        "# Auto-generated; rerun scripts/refresh_nordic_adoption_size.py then build.py. DO NOT hand-edit.",
        "# Iceland is absent: it has no row in Eurostat's AI table, though it is in the exposure module.",
        "meta:",
        '  indicator: "Enterprises using at least one AI technology, by firm size"',
        '  unit: "% of enterprises"',
        '  source: "Eurostat, isoc_eb_ai"',
        f"  year: {YEAR}",
        f"  prev_year: {PREV}",
        f"  countries: {len(data)}",
        "countries:",
    ]
    for g in GEO:
        rows = data.get(g)
        if not rows:
            continue
        rows.sort(key=lambda r: order.index(r[0]))
        head = next((v for c, v, _ in rows if c == "GE10"), None)
        lines.append(f'  - code: "{g}"')
        lines.append(f'    name: "{names[g]}"')
        lines.append(f"    is_se: {str(g == 'SE').lower()}")
        lines.append(f"    headline: {head}")
        lines.append("    sizes:")
        for code, cur, prev in rows:
            en, sv = lbl[code]
            lines.append(f'      - {{code: "{code}", name: "{en}", name_sv: "{sv}", '
                         f"adoption: {cur}, prev: {'null' if prev is None else prev}, "
                         f"is_se: {str(code == 'GE10').lower()}}}")
    out = ROOT / "data" / "nordic_adoption_size.yaml"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}: " +
          ", ".join(f"{names[g]} {next(v for c, v, _ in data[g] if c == 'GE10')}%"
                    for g in GEO if g in data))


if __name__ == "__main__":
    main()
