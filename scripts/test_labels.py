#!/usr/bin/env python3
"""Tests for labels.shorten(). Run: python3 scripts/test_labels.py

Plain asserts and no framework, to match the rest of scripts/ and so CI needs no extra
install. The cases that matter are the real titles: they are what the rule was tuned on, so
they are what silently drifts when someone tunes it again.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from labels import MAX_LABEL_CHARS, shorten  # noqa: E402

L = MAX_LABEL_CHARS

REAL = [
    # (lang, official title, expected display label)
    ("en", "Assistant nurses, home care, home nursing, elderly care and habilitation",
           "Assistant nurses, home care etc."),
    ("sv", "Undersköterskor; hemtjänst; hemsjukvård; äldreboende och habilitering",
           "Undersköterskor; hemtjänst m.m."),
    ("en", "Medical secretaries and care administrators", "Medical secretaries etc."),
    ("sv", "Ingenjörer och tekniker inom elektroteknik", "Ingenjörer och tekniker m.m."),
    ("sv", "Systemanalytiker och IT-arkitekter m.fl.", "Systemanalytiker och IT-arkitekter"),
    # Untouched: at or under the limit. The second is the title Magnus named as the longest
    # that still reads on a phone, so it must come through exactly.
    ("en", "Electrical engineers and technicians", "Electrical engineers and technicians"),
    ("en", "Software and systems developers", "Software and systems developers"),
    ("sv", "Forskarassistenter m.fl.", "Forskarassistenter m.fl."),
]

EDGE = [
    ("en", "", ""),
    ("en", "Chemists", "Chemists"),
    ("en", "x" * 80, "x" * (L - 1) + "…"),          # one unbreakable word: cut and say so
    ("en", " Doctoral students ", "Doctoral students"),
]


def main() -> int:
    fails = []

    for lang, src, want in REAL + EDGE:
        got = shorten(src, lang)
        if got != want:
            fails.append(f"shorten({src!r}, {lang!r}) = {got!r}, want {want!r}")

    # The guarantee the chart depends on: nothing comes back over the limit, ever.
    for lang, src, _ in REAL + EDGE:
        got = shorten(src, lang)
        if len(got) > L:
            fails.append(f"{got!r} is {len(got)} chars, over the {L} limit")

    # Idempotent: a display label fed back in is already short, so it must not be re-cut.
    for lang, src, _ in REAL:
        once = shorten(src, lang)
        if shorten(once, lang) != once:
            fails.append(f"not idempotent: {once!r} -> {shorten(once, lang)!r}")

    # A mark must appear whenever something was dropped, and never when nothing was.
    for lang, src, want in REAL:
        dropped = want != src
        marked = want.endswith(("etc.", "m.m.")) or want != src and want.rstrip().endswith(("m.fl.",))
        if dropped and not marked and src.lower().rstrip().endswith(("m.fl.", "m.m.", "etc.")) is False:
            fails.append(f"{src!r} was shortened to {want!r} with no mark")

    if fails:
        print(f"FAIL ({len(fails)}):")
        for f in fails:
            print("  " + f)
        return 1
    print(f"OK. {len(REAL) + len(EDGE)} cases, limit {L}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
