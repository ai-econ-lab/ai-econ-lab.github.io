#!/usr/bin/env python3
"""Build data/occupations.yaml: where AI demand actually sits, by occupation.

Was hand-maintained, which is why it still carried the v1 national figure (0.44%) after the
v1.1 freeze moved it. Generated now, from the same series the rest of the Monitor uses, so
it cannot drift again.

Source: ai-monitor/data/bulk_v14/derived/series_ssyk4.csv, DISTINCT ADVERTISEMENTS.
Measure: the strict floor, i.e. the share of an occupation's advertisements that ask for AI
skills in the role itself. An occupation reads zero when no advertisement asks for AI in the
role, not when the word AI never appears.

The English occupation names are OUR renderings of the employment service's Swedish labels,
so they are kept in a translation table here rather than invented per run: a name that
silently changed between builds would be worse than one that is occasionally missing.

Run:  python3 scripts/refresh_occupations.py
"""
import csv
from pathlib import Path

import yaml

from monitor_root import MONITOR_ROOT, DEF_LABEL, bulk_dir

SRC = (MONITOR_ROOT
       / f"data/{bulk_dir()}/derived/series_ssyk4.csv")
ANNUAL = (MONITOR_ROOT
          / f"data/{bulk_dir()}/derived/series_annual.csv")
OUT = Path(__file__).resolve().parent.parent / "data" / "occupations.yaml"
PREV = OUT
YEAR = "2025"
MIN_ADS = 400
TOP_N = 9
ZERO_N = 3


# Our English renderings of the employment service's Swedish occupational labels, kept
# explicit so a name cannot silently change between builds. An unlisted label falls through
# to the Swedish original, which is visible and fixable, rather than to a guess.
EN = {
    "Doktorander": "Doctoral students",
    "Forskarassistenter m.fl.": "Research assistants",
    "Övriga IT-specialister": "Other IT specialists",
    "Mjukvaru- och systemutvecklare m.fl.": "Software and systems developers",
    "Universitets- och högskolelektorer": "University lecturers",
    "Fysiker och astronomer": "Physicists and astronomers",
    "Kemister": "Chemists",
    "Ingenjörer och tekniker inom elektroteknik": "Electrical engineers and technicians",
    "Systemanalytiker och IT-arkitekter m.fl.": "Systems analysts and IT architects",
    "Cell- och molekylärbiologer m.fl.": "Cell and molecular biologists",
    "Personliga assistenter": "Personal care assistants",
    "Grundskollärare": "Primary school teachers",
    "Grundutbildade sjuksköterskor": "Registered nurses",
    # Two variants of the same SSYK label. The employment service moved from commas to
    # semicolons and added hemsjukvård, and because the lookup below falls back to the key
    # itself, the miss did not fail: it published the Swedish label verbatim on an English
    # page, under a caveat promising "our English renderings". Keep both spellings.
    "Undersköterskor, hemtjänst, äldreboende och habilitering": (
        "Assistant nurses, home and elderly care"),
    "Undersköterskor; hemtjänst; hemsjukvård; äldreboende och habilitering": (
        "Assistant nurses, home care, home nursing, elderly care and habilitation"),
    "Lager- och terminalpersonal": "Warehouse and terminal staff",
    "Specialistläkare": "Specialist physicians",
}


def main():
    prev = yaml.safe_load(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    names = EN

    rows = []
    for r in csv.DictReader(SRC.open(encoding="utf-8")):
        if r["year"] != YEAR:
            continue
        ads = int(r["total_dd"])
        if ads < MIN_ADS or not r["label"]:
            continue
        rows.append({"label": r["label"], "ads": ads,
                     "share": round(100 * int(r["floor_dd"]) / ads, 2)})

    national = next(float(r["floor_pct"]) for r in csv.DictReader(ANNUAL.open(encoding="utf-8"))
                    if r["year"] == YEAR)

    rows.sort(key=lambda x: (-x["share"], -x["ads"]))
    top = rows[:TOP_N]
    zero = sorted([x for x in rows if x["share"] == 0.0], key=lambda x: -x["ads"])[:ZERO_N]

    doc = {
        "meta": {"year": int(YEAR), "national": round(national, 2),
                 "source": f"JobTech / Platsbanken job ads (CC0), {DEF_LABEL}, "
                           "distinct advertisements",
                 "measure": prev.get("meta", {}).get("measure",
                            "share of the occupation's advertisements that ask for AI skills "
                            "in the role itself (the strict floor)"),
                 "min_ads": MIN_ADS},
        "lede": prev.get("lede", ""),
        # name_sv carries the employment service's own Swedish label alongside our English
        # rendering, so the Swedish one-pager can print Swedish occupation names instead of
        # glosses. Added 10 Aug 2026.
        "top": [{"name": names.get(x["label"], x["label"]), "name_sv": x["label"], "share": x["share"],
                 "ads": x["ads"], "is_se": False} for x in top],
        "zero": [{"name": names.get(x["label"], x["label"]), "name_sv": x["label"], "share": 0.0,
                  "ads": x["ads"], "is_se": False} for x in zero],
        "caveat": prev.get("caveat", ""),
    }
    OUT.write_text("# Generated by scripts/refresh_occupations.py. Do not hand-edit.\n"
                   + yaml.dump(doc, allow_unicode=True, sort_keys=False, width=95),
                   encoding="utf-8")
    # AN UNMAPPED LABEL IS A DEFECT, NOT A DEFAULT. `names.get(label, label)` degrades to the
    # Swedish label, which reads as data on an English page and slipped through for the
    # assistant-nurses row when the employment service respelled it. Name the misses, and exit
    # non-zero so weekly_refresh restores the file from git rather than publishing Swedish.
    missing = sorted({x["label"] for x in top + zero if x["label"] not in names})
    if missing:
        raise SystemExit("occupations: no English rendering for "
                         + "; ".join(f'"{m}"' for m in missing)
                         + " — add it to EN in this script. The page's caveat promises English "
                           "renderings, so publishing the Swedish label would break that promise.")
    print(f"occupations.yaml: {YEAR}, national floor {national:.2f}%, "
          f"{len(rows)} occupations with >= {MIN_ADS} distinct ads")
    for x in top:
        print(f"   {x['share']:>6.2f}%  {x['ads']:>7,}  {x['label']}")
    print("   zero:")
    for x in zero:
        print(f"   {x['share']:>6.2f}%  {x['ads']:>7,}  {x['label']}")


if __name__ == "__main__":
    main()
