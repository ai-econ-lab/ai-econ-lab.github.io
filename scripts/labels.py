#!/usr/bin/env python3
"""Short display labels for occupational (and other categorical) titles in charts.

WHY. Official occupational titles are written to be unambiguous in a classification, not to
fit beside a bar. SCB's SSYK label for one of Sweden's largest occupations is "Assistant
nurses, home care, home nursing, elderly care and habilitation" -- 72 characters. The ranked
bar chart sizes its label gutter to the longest label and grows the canvas rather than
clipping (build.py::barplot explains why clipping was worse), so that one title pushed the
viewBox from 640 to 796 and took 57 per cent of the width for the gutter. On a phone in
portrait the SVG scales to the container, so the reader saw a column of titles and a sliver
of chart. The information was all there and none of it was legible.

WHAT THIS DOES. What statistical agencies do with the same problem: keep the head of the
title, drop the enumeration behind it, and mark that something was dropped -- "etc." in
English, "m.m." in Swedish. The full title is never thrown away; callers put it in the SVG's
<title> so hover and assistive technology still read the official label, and the CSV exports
carry it unshortened because a data file has no width to run out of.

THE RULE, in order, keeping whichever candidate survives that is longest:

  1. an explicit override, for the few where the mechanical answer reads badly;
  2. a title that already ends in its own mark ("m.fl.", "m.m.", "etc.") and fits without it
     keeps the head instead: "Systemanalytiker och IT-arkitekter m.fl." (40) becomes
     "Systemanalytiker och IT-arkitekter" (34) rather than losing IT-arkitekter to a rule
     that appends the mark it just removed;
  3. cut at a comma or semicolon, keeping as many whole segments as fit;
  4. cut at " and " / " och ", same;
  5. cut at a word boundary, then drop a dangling function word ("inom", "och", "and", "of"),
     because "Engineers and technicians within m.m." is worse than "Engineers and technicians m.m.".

Rules 3-5 generate candidates that are COMPARED rather than tried in order, because neither
"shortest" nor "longest" is right on its own:

  "Ingenjörer och tekniker inom elektroteknik"   och-cut "Ingenjörer m.m."            (15)
                                                word-cut "Ingenjörer och tekniker m.m." (28)
  "Medical secretaries and care administrators"  and-cut "Medical secretaries etc."     (24)
                                                word-cut "Medical secretaries and care etc." (33)

The word cut is longer in both. It is right in the first (a complete conjunct, minus a
trailing prepositional phrase) and wrong in the second (a conjunction whose second half was
cut mid-phrase, leaving "and care"). Telling those apart properly needs phrase structure. So
the rule is a preference with a price: take the clause boundary unless it costs more than
CLAUSE_PREMIUM of what the word cut would have kept. 15/28 = 54% is too expensive; 24/33 =
73% is not.

LIMIT. 36 characters, the length of "Electrical engineers and technicians", which Magnus
picked as the longest title that still reads on a phone. It is one constant, here, and
check_label_lengths.py fails the build if any rendered label exceeds it.
"""
from __future__ import annotations

import re

MAX_LABEL_CHARS = 36

# How much of the word-cut's length a clause cut must retain to be preferred. See the module
# docstring: a clause boundary reads better, but not at any price.
CLAUSE_PREMIUM = 0.60

# Marks a title may already carry, meaning "and others of this kind". Swedish official titles
# use them constantly, and they are the first thing to drop: they are the least informative
# part of the title and the only part the shortener would otherwise re-add.
SELF_MARKS = (" m.fl.", " m.fl", " m.m.", " etc.", " etc", " o.d.", " o.dyl.")

# " etc." and " m.m." are the conventional marks; both are five characters including the space.
MARK = {"en": " etc.", "sv": " m.m."}

# Dangling words at a cut, which read as truncation damage rather than abbreviation.
TRAILING_STOPWORDS = {
    "en": {"and", "or", "of", "in", "on", "for", "with", "the", "a", "to", "within"},
    "sv": {"och", "eller", "inom", "i", "på", "för", "med", "till", "samt"},
}

# Where the mechanical answer reads badly, say so once, here, rather than tuning the rule
# until it happens to suit one title and quietly changes the others. Keys are the full
# official label; values must themselves fit MAX_LABEL_CHARS (check_label_lengths.py enforces
# that, so an override cannot reintroduce the defect it exists to fix).
OVERRIDES: dict[str, str] = {}


def _fits(s: str, limit: int) -> bool:
    return len(s) <= limit


def _by_separator(label: str, pattern: str, mark: str, limit: int) -> str | None:
    """Greedy prefix of whole segments, plus the mark, if anything was actually dropped."""
    parts = re.split(pattern, label)
    if len(parts) < 2:
        return None
    seps = re.findall(pattern, label)
    out = parts[0]
    kept = 1
    while kept < len(parts):
        nxt = out + seps[kept - 1] + parts[kept]
        if not _fits(nxt + mark, limit):
            break
        out, kept = nxt, kept + 1
    if kept == len(parts):
        return None                      # nothing dropped: not a shortening
    out = out.rstrip(" ,;")
    return out + mark if _fits(out + mark, limit) and out else None


def _by_word(label: str, mark: str, limit: int, lang: str) -> str | None:
    words = label.split()
    out: list[str] = []
    for w in words:
        cand = " ".join(out + [w])
        if not _fits(cand + mark, limit):
            break
        out.append(w)
    while out and out[-1].lower().strip(",;") in TRAILING_STOPWORDS.get(lang, set()):
        out.pop()
    if not out or len(out) == len(words):
        return None
    return " ".join(out).rstrip(" ,;") + mark


def shorten(label: str, lang: str = "en", limit: int = MAX_LABEL_CHARS) -> str:
    """A display label of at most `limit` characters. The full label is the caller's to keep."""
    label = (label or "").strip()
    if len(label) <= limit:
        return label
    if label in OVERRIDES:
        return OVERRIDES[label]

    # A title that already carries its own mark: drop it and see whether the head fits.
    for sm in SELF_MARKS:
        if label.lower().endswith(sm):
            head = label[: -len(sm)].rstrip(" ,;")
            if _fits(head, limit):
                return head
            label = head            # shorten the head; the mark is re-added by the rules below
            break

    mark = MARK.get(lang, MARK["en"])
    clause = [c for c in (_by_separator(label, r"\s*[;,]\s*", mark, limit),
                          _by_separator(label, r"\s+(?:and|och)\s+", mark, limit))
              if c and _fits(c, limit)]
    word = _by_word(label, mark, limit, lang)
    word = word if word and _fits(word, limit) else None

    best_clause = max(clause, key=len) if clause else None
    if best_clause and (not word or len(best_clause) >= CLAUSE_PREMIUM * len(word)):
        return best_clause
    if word:
        return word

    # A single word longer than the limit. Nothing reads well here; cut and mark it visibly
    # rather than returning something that silently overflows the gutter.
    return label[: max(1, limit - 1)].rstrip() + "…"


def is_shortened(label: str, lang: str = "en", limit: int = MAX_LABEL_CHARS) -> bool:
    return shorten(label, lang, limit) != (label or "").strip()
