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

import yaml

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



def check_aggregates(docs, problems):
    """C. A comparator must be named for the population it actually covers.

    Added 12 Aug 2026, after the exposure comparator was called "the EU average" in the brief,
    in View A's prose and on four chart reference lines. It is the mean over the 36 EU-LFS
    countries in cross_country.yaml, seven of which (Iceland, Montenegro, Norway, Serbia,
    Switzerland, Turkey, the United Kingdom) are not in the EU, so a reader comparing it with
    the adoption card's EU27 figure was comparing two different country sets under one name.

    Two precise probes rather than one loose one. A first attempt matched any "EU" within forty
    characters of the number and produced six hits, all false: axis ticks reading "30% 40% EU27",
    the phrase "EU-LFS", and the sentence that correctly says seven countries are OUTSIDE the EU.
    A checker that cries wolf gets switched off, so this one targets the two shapes the claim can
    actually take: the reference line's own label, which carries name and value in one element,
    and prose that puts an EU word and an averaging word next to the figure.
    """
    cc = yaml.safe_load((ROOT / "data" / "cross_country.yaml").read_text(encoding="utf-8"))
    mean = cc["meta"]["mean_share"]
    n = cc["meta"]["n_countries"]
    non_eu = {"Iceland", "Montenegro", "Norway", "Serbia", "Switzerland", "Turkey",
              "United Kingdom"} & {c["name"] for c in cc["countries"]}
    if not non_eu:
        return          # the set became EU-only; "EU" would then be fair and this check is moot
    tell = f"{len(non_eu)} of the countries are outside the EU ({', '.join(sorted(non_eu))})"

    # (1) the reference line's label: "<name> <value>" in one <text class="meanlab"> element
    lab = re.compile(r'<text class="meanlab"[^>]*>([^<]*)</text>')
    for path in sorted(docs.rglob("*.html")) + sorted(docs.rglob("*.svg")):
        for m in lab.finditer(path.read_text(encoding="utf-8", errors="ignore")):
            txt = m.group(1).strip()
            num = re.search(r"([\d.]+)\s*$", txt)
            on_mean = (num and abs(float(num.group(1)) - mean) < 0.05) or "-country" not in txt
            if re.match(r"EU\b|EU27\b", txt) and on_mean and abs(
                    float(num.group(1)) - mean if num else mean) < 0.05:
                problems.append(f"{path.relative_to(docs)}: reference line labelled "
                                f"\u201c{txt}\u201d plots the {n}-country exposure mean. {tell}.")

    # (2) prose: an EU word and an averaging word next to the figure, with nothing between them
    claim = re.compile(
        r"(EU-?(?:27)?)[\s-]*(average|mean|snittet|snitt|genomsnittet|genomsnitt)"
        r"[^.%<]{0,24}" + re.escape(f"{mean:.0f}") + r"\s*%"
        r"|" + re.escape(f"{mean:.0f}") + r"\s*%[^.%<]{0,24}"
        r"(EU-?(?:27)?)[\s-]*(average|mean|snittet|snitt|genomsnittet|genomsnitt)")
    for path in sorted(docs.rglob("*.html")):
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8",
                                                                        errors="ignore")))
        for m in claim.finditer(txt):
            problems.append(f"{path.relative_to(docs)}: calls the {n}-country exposure mean an "
                            f"EU average: \u201c{m.group(0).strip()}\u201d. {tell}.")



def check_brief_length(problems):
    """D. The brief is a ONE-page publication, in both languages, every month.

    Added 12 Aug 2026 on Magnus's instruction ("should always be 1 page"). The August issue ran
    to 666 words against 90-142 for every other month, because only its theme had been written
    out in full, and it printed to three pages before the print stylesheet was fixed and to a
    cramped one after. Rather than re-print twelve months through a headless browser on every
    build, this bounds the input: at the sheet's type size a page holds about 560 words of body
    copy besides the chart, so an issue over the budget will not fit however the CSS is tuned.

    Checked for all twelve themes and both languages, because the calendar means a build only
    ever renders one of them and an overlong February would otherwise surface in February.
    """
    budget = 560
    import os as _os
    prev = _os.environ.get("BRIEF_MONTH_OVERRIDE")
    try:
        sys.path.insert(0, str(ROOT))
        import importlib
        build = importlib.import_module("build")
        for month in range(1, 13):
            _os.environ["BRIEF_MONTH_OVERRIDE"] = f"2027-{month:02d}"
            for lang in ("en", "sv"):
                page = re.sub(r"<svg.*?</svg>", "", build.brief(lang), flags=re.S)
                body = re.findall(r'<p class="bp">(.*?)</p>', page, re.S)
                words = sum(len(re.sub(r"<[^>]+>", "", b).split()) for b in body)
                if words > budget:
                    problems.append(
                        f"brief {lang.upper()} month {month}: {words} words of body copy against a "
                        f"{budget}-word budget, so it will not fit one page. Cut the copy; do not "
                        f"shrink the type, which is already at the floor for a printed sheet.")
    except Exception as e:                      # a checker must not break the build it guards
        problems.append(f"brief length check could not run: {type(e).__name__}: {e}")
    finally:
        if prev is None:
            _os.environ.pop("BRIEF_MONTH_OVERRIDE", None)
        else:
            _os.environ["BRIEF_MONTH_OVERRIDE"] = prev



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
    check_aggregates(docs, problems)
    check_brief_length(problems)

    if problems:
        print(f"check_claims: {len(problems)} problem(s)\n")
        for p in problems:
            print(f"  FAIL  {p}\n")
        print("A module may differ from its neighbours; it may not do so silently.")
        return 1
    print("check_claims: every JobTech module states a unit, no generator/output "
          "disagreement, no stale assertions, page and Brief agree, and no comparator "
          "is named for a population it does not cover, and every month's brief fits one page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
