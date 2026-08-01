#!/usr/bin/env python3
"""
check_claims.py -- does every module state a counting unit it is actually computed on?

WHY THIS EXISTS. On 1 August 2026 five separate places across three repositories asserted
something their own data contradicted, and none was a wrong number. Each was a sentence
claiming more than its design carried, which is the failure the Monitor read gate exists to
catch and which no test looked for:

  1. data/vocabulary.yaml's source line was hand-edited to read "distinct advertisements"
     while every number in the file was a raw-record count, and refresh_vocabulary.py still
     emitted "frozen v1 term list", so the claim would have silently reverted on the next run.
  2. build.py's monthly block told readers "the chart above still counts records ...
     correcting it is pending" three lines above its own footer saying "distinct
     advertisements", over data migrated a fortnight earlier.
  3. occupation_tiers.yaml's caption said "advertisements" over counts of ad records.
  4. Job quality and governance were on the distinct-ad unit but said nothing, while the
     entry-level squeeze was NOT and also said nothing, so silence read as agreement.
  5. (Other repo, same class) the MONA dictionary index reported 0% English coverage while
     holding 54% of it, mis-filed into a field named `sv`.

The common cause is structural rather than careless: data files are generated, prose is
hand-maintained, and nothing checked one against the other.

WHAT IT CHECKS, on the built HTML rather than the source, because the built page is what a
reader sees and what the Brief inherits:

  A. Every JobTech-derived figure footer names a counting unit. Silence is a failure, because
     a module that quietly differs from its neighbours is the case that bit us.
  B. A module claiming "distinct advertisements" is not fed by a file still on raw records.
  C. No page text says the correction is pending, which was true once and then was not.
  D. The Brief, which keeps its own copy of the prose and inherits only the data, does not
     contradict the page on the exposure ranking.

Exit code 1 on any failure, so it can gate a build.

Run:  python3 scripts/check_claims.py [--docs docs]
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A JobTech-derived footer must say which of these it counts. The exception is allowed to
# say so explicitly; what is forbidden is saying nothing.
UNIT_PHRASES = ("distinct advertisements", "distinct ads", "ad records")
JOBTECH = ("JobTech", "Platsbanken")

# Sentences that were true before a migration and false after it. Each is a real one that
# shipped, or nearly did.
STALE_ASSERTIONS = [
    # Tightened 1 Aug after a FALSE POSITIVE: the phrase "still counts records" is legitimate
    # when a caveat names the one module that genuinely does. What was wrong was the monthly
    # chart claiming it, so anchor the pattern to that claim rather than the bare phrase. A
    # check that fires on correct text gets ignored, which is worse than not having it.
    (r"chart above still counts records",
     "the monthly block's pre-migration sentence; the correction it calls pending happened"),
    (r"correcting it is .{0,30}pending",
     "same paragraph, other half"),
    (r"\b2nd[- ]highest of \d+(?!.{0,200}depends on where the line is drawn)",
     "a bare exposure ranking with no cut caveat within 200 characters (read-gate A1)"),
    (r"näst högst av \d+|näst mest exponerad",
     "the Swedish bare exposure ranking (read-gate A1)"),
]


def footers(html):
    """(source line, surrounding context) for every figure footer on a page."""
    out = []
    for m in re.finditer(r"Source:\s*([^<]{0,240})", html):
        out.append(" ".join(m.group(1).split()))
    return out


def check_page(path, label, problems):
    if not path.exists():
        problems.append(f"{label}: {path} not built")
        return
    html = path.read_text(encoding="utf-8")

    # A. JobTech footers must name a unit
    for s in footers(html):
        if any(j in s for j in JOBTECH) and not any(u in s for u in UNIT_PHRASES):
            problems.append(f"{label}: JobTech footer states no counting unit -> {s[:110]}")

    # C. stale assertions anywhere in the rendered text
    text = re.sub(r"<[^>]+>", " ", html)
    text = " ".join(text.split())
    for pat, why in STALE_ASSERTIONS:
        m = re.search(pat, text, re.I)
        if m:
            i = max(0, m.start() - 90)
            problems.append(f"{label}: {why} -> …{text[i:m.end() + 90]}…")


def check_sources(problems):
    """B. A generator's emitted unit must match the file it actually reads."""
    pairs = [
        ("scripts/refresh_vocabulary.py", "data/vocabulary.yaml",
         "term_composition.csv", "distinct advertisements"),
        ("scripts/refresh_occupation_tiers.py", "data/occupation_tiers.yaml",
         "tier_by_occupation.csv", "distinct advertisements"),
    ]
    for script, out, expect_src, expect_unit in pairs:
        sp, op = ROOT / script, ROOT / out
        if not sp.exists() or not op.exists():
            problems.append(f"missing {script} or {out}")
            continue
        s, o = sp.read_text(encoding="utf-8"), op.read_text(encoding="utf-8")
        if expect_src not in s:
            problems.append(f"{script} no longer reads {expect_src}; its unit claim is unchecked")
        if expect_unit not in o:
            problems.append(f"{out} does not state '{expect_unit}'")
        # the claim must come from the generator, not be patched into its output by hand
        if expect_unit not in s:
            problems.append(f"{script} does not EMIT '{expect_unit}', so {out} was hand-edited "
                            f"and will revert on the next run")
        if "Generated by" not in o.split("\n")[0]:
            problems.append(f"{out} has no generated-by header; is it hand-maintained again?")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="docs")
    a = ap.parse_args()
    docs = ROOT / a.docs

    problems = []
    check_page(docs / "monitor" / "index.html", "monitor", problems)
    check_page(docs / "monitor" / "brief" / "index.html", "brief EN", problems)
    check_page(docs / "monitor" / "brief" / "sv" / "index.html", "brief SV", problems)
    check_sources(problems)

    if problems:
        print(f"check_claims: {len(problems)} problem(s)\n")
        for p in problems:
            print(f"  FAIL  {p}\n")
        print("A module may differ from its neighbours; it may not do so silently.")
        return 1
    print("check_claims: every JobTech module states a unit, no generator/output "
          "disagreement, no stale assertions, page and Brief agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
