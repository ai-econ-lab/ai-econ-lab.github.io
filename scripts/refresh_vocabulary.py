#!/usr/bin/env python3
"""Build data/vocabulary.yaml: what words the AI ads actually use, era by era.

WHY THIS EXISTS. The standing objection to any long AI-in-Demand series is that a term list
written in 2026 is being applied backwards, so the early years are measured with today's
vocabulary and the growth is an artefact. This chart answers it with the data: the ads of 2006
are dominated by words almost nobody uses now (data mining, expert systems), and the generative
vocabulary is absent until 2022. The list is not anachronistic; the language turned over.

TERMS ARE DATE-GATED. Four product names in the frozen v1 list match ads published before the
product existed (gemini, claude, copilot, and chatgpt on a shorter fuse). Ungated, this chart
would show a reader "gemini, 2006", which is a false positive rather than a fact about 2006. See
`ai-monitor/notes/v1_1-fixlist_anachronisms_2026-07-30.md`; the gate here is for DISPLAY only and
changes no published series, because v1 is frozen.

THE COUNTING UNIT IS EMITTED HERE, NOT PATCHED INTO THE OUTPUT. On 31 July the v1.1 migration
hand-edited `data/vocabulary.yaml`'s source line to claim "distinct advertisements" while every
number in the file was still a raw-record count, and this script would have silently reverted
the claim on its next run. The chart is now built from `term_composition.csv`, which counts each
advertisement once, and the source string below states that because the generator says so.
Never hand-edit the output: the header says not to, and that is exactly how the two disagreed.

Run:  python3 scripts/refresh_vocabulary.py
"""
import csv
import json
import re
from pathlib import Path

from monitor_root import MONITOR_ROOT

SRC = (MONITOR_ROOT
       / "data/diagnostics/term_composition.csv")
OUT = Path(__file__).resolve().parent.parent / "data" / "vocabulary.yaml"

# THE FAMILY MAP AND THE YEAR GATES NOW LIVE BESIDE THE TERM LIST THEY SHADOW, in
# ai-monitor/config/vocabulary_families.json. They were two hand-written lists here: which band
# a term draws in, and from which year a polysemous term may count. Both name the same terms the
# definition names, in a different repository, maintained by hand -- so they drifted by
# construction. Every freeze added terms and nothing told this file.
#
# By 19 Aug 2026 the drift was 26.4% of all term hits unclassified, peaking at 44.7% in a
# period, and it was not neutral: the residual held "ml" (4,239 hits, v1.4's own addition), the
# genAI vocabulary of 2023-2026, and every hyphen and newline variant of terms already mapped.
# The chart understated its own finding, worst in the years it is about -- 2026-Q2 generative
# read 20.8% where the mapped figure is 35.5%.
#
# ai-monitor/scripts/check_vocabulary_families.py fails the build when a term above the
# threshold has no family, so the next freeze cannot re-open the gap quietly.
FAMILY_MAP = json.loads(
    (MONITOR_ROOT / "config" / "vocabulary_families.json").read_text(encoding="utf-8"))
GATE = {k: v for k, v in FAMILY_MAP["year_gate"].items() if not k.startswith("_")}
FOLD = set(FAMILY_MAP["display"]["fold_into_other"])


def squash(s):
    """Lowercase, and drop whitespace, hyphens and underscores.

    This is the fix for the variant problem: the old map matched the literal substring
    "machine learning", so "machine-learning" (297 hits), "machinelearning" (66) and
    "machine\nlearning" (18) all fell through to unclassified while the term they are spelt
    differently from sat in the ml band.
    """
    return re.sub(r"[\s\-_]+", "", s.lower())


def family(term):
    t = squash(term)
    for name in FAMILY_MAP["order"]:
        spec = FAMILY_MAP["families"][name]
        if any(squash(k) == t for k in spec["exact"]):
            return name
        if any(squash(k) in t for k in spec["contains"]):
            return name
    return "other"


def band(term):
    """The band the CHART draws, which is the family unless the chart does not draw it yet."""
    f = family(term)
    return "other" if f in FOLD else f


rows = list(csv.DictReader(SRC.open(encoding="utf-8")))
cols = [c for c in rows[0] if c not in ("term", "total")]

series, other_max = [], 0
for c in cols:
    agg, tot = {}, 0
    for r in rows:
        n = int(r[c] or 0)
        y = int(c[:4])
        # Gate keys are squashed too. They were raw substrings, which is why "finjustering"
        # was gated and "fine-tuning" was not: the same term, spelt with a hyphen, was a
        # different string to this line.
        if not n or any(squash(g) in squash(r["term"]) and y < yr for g, yr in GATE.items()):
            continue
        agg[band(r["term"])] = agg.get(band(r["term"]), 0) + n
        tot += n
    if not tot:
        continue
    pct = {k: round(100 * v / tot, 2) for k, v in agg.items()}
    other_max = max(other_max, pct.get("other", 0))
    series.append({"p": c, "early": pct.get("early", 0), "ml": pct.get("ml", 0),
                   "generic": pct.get("generic", 0), "genai": pct.get("genai", 0),
                   "autonomy": pct.get("autonomy", 0), "other": pct.get("other", 0), "n": tot})

first, last = series[0], series[-1]
lines = ["# Generated by scripts/refresh_vocabulary.py. Do not hand-edit.",
         "meta:",
         f"  first: {first['p']}", f"  last: {last['p']}", f"  n_periods: {len(series)}",
         f"  early_first: {first['early']}", f"  early_last: {last['early']}",
         f"  genai_last: {last['genai']}", f"  ml_peak: {max(s['ml'] for s in series)}",
         f"  other_max: {round(other_max, 1)}",
         f"  total_term_hits: {sum(s['n'] for s in series)}",
         "  source: JobTech historical job ads (Arbetsförmedlingen), CC0, frozen v1.1 term "
         "list, distinct advertisements",
         "series:"]
for s in series:
    lines.append(f"  - {{p: '{s['p']}', early: {s['early']}, ml: {s['ml']}, "
                 f"generic: {s['generic']}, genai: {s['genai']}, autonomy: {s['autonomy']}, "
                 f"other: {s['other']}, n: {s['n']}}}")
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"vocabulary.yaml: {len(series)} periods, {first['p']} to {last['p']}")
print(f"  early-era words   {first['early']:.0f}% -> {last['early']:.1f}%")
print(f"  generative words  {first['genai']:.1f}% -> {last['genai']:.1f}%")
print(f"  unclassified peaks at {other_max:.1f}%")
