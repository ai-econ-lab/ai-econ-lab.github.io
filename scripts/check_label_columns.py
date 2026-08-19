#!/usr/bin/env python3
"""Fail when a stored short label disagrees with the rule that is supposed to produce it.

    python3 scripts/check_label_columns.py

WHY. data/occupations.yaml and data/occupation_tiers.yaml carry a name_short (and
name_sv_short) beside any official title too long to print. That column is DERIVED: labels.py
is the single source of truth and build.py calls shorten() when it draws each label, so
nothing reads the column at build time. It is written down for two things the rendering path
cannot give:

  visibility  a name_short line in the data says "that title was too long", where Magnus
              reads the data, rather than only in a chart he would have to look at on a phone.
  a diff      a new SSYK title long enough to shorten, or a change to the rule, moves what the
              site prints. Without the column, data/ shows nothing and the change is silent.

A derived column that nothing reads is exactly the kind of thing that rots: it survives a rule
change, disagrees with the site, and is believed because it is committed. So it is checked.
This compares every stored short label against shorten(), and fails on any disagreement,
including a name_short that should not be there at all because its title now fits.

If a shortened title reads badly, put the hand-written version in labels.OVERRIDES and re-run
the refresh script. Do not edit the YAML: it says "Do not hand-edit" and the next refresh
would overwrite it anyway -- and this check would fail in between.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from labels import MAX_LABEL_CHARS, shorten  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# file -> (list keys to walk, [(name field, short field, language)])
SOURCES = {
    "occupations.yaml": (("top", "zero"),
                         (("name", "name_short", "en"), ("name_sv", "name_sv_short", "sv"))),
    "occupation_tiers.yaml": (("rows",), (("name", "name_short", "en"),)),
}


def main() -> int:
    problems: list[str] = []
    checked = stored = 0

    for fname, (groups, fields) in SOURCES.items():
        path = DATA / fname
        if not path.exists():
            problems.append(f"{fname}: missing")
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for g in groups:
            for row in (doc.get(g) or []):
                for name_f, short_f, lang in fields:
                    name = row.get(name_f)
                    if not name:
                        continue
                    checked += 1
                    want = shorten(str(name), lang)
                    have = row.get(short_f)
                    if want == name:
                        if have is not None:
                            problems.append(
                                f"{fname} [{g}] {name!r}: has {short_f}={have!r} but the title "
                                f"fits in {MAX_LABEL_CHARS} characters -- the column should go")
                        continue
                    stored += 1
                    if have is None:
                        problems.append(
                            f"{fname} [{g}] {name!r} is {len(str(name))} characters and has no "
                            f"{short_f}. Re-run the refresh script that writes {fname}.")
                    elif have != want:
                        problems.append(
                            f"{fname} [{g}] {name!r}: {short_f} is {have!r}, the rule gives "
                            f"{want!r}. Re-run the refresh script, or put {have!r} in "
                            f"labels.OVERRIDES if that is the label you want.")

    print(f"{checked} titles checked · {stored} shortened · limit {MAX_LABEL_CHARS}")
    if problems:
        print(f"\nFAIL. {len(problems)} disagreement(s):")
        for p in problems:
            print("  " + p)
        return 1
    print("\nOK. Every stored short label matches labels.shorten().")
    return 0


if __name__ == "__main__":
    sys.exit(main())
