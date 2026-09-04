#!/usr/bin/env python3
"""Fail when JobTech has published an archive period the site has not ingested.

    python3 scripts/check_archive_release.py
    python3 scripts/check_archive_release.py --coverage 2026-03   # positive control

WHY THIS EXISTS. The archive-based series (the annual trend and the monthly chart) advance
one JobTech release at a time: the running year arrives as quarterly files on
data.jobtechdev.se/annonser/historiska/, and nothing else can move those charts, because the
JobStream flow is a different subset of ads and runs higher in level (splice check
2026-07-24), so it is never spliced onto the archive line. Between releases the headline
provisional number stands still by construction; that is fine, and since 4 Sep 2026 the page
says what the point covers so the stillness is legible.

What is NOT fine is the other side of that bargain: when the next quarterly file lands,
nobody is told. The bulk re-score is a laptop run (bulk_pipeline_v11.py refuses to download
by design), so a new quarter sits unincorporated until someone happens to look, and the site
serves an ever-staler "so far" with no signal anywhere. Same class as the 13-17 August
silence: not a broken job, a missing one. This check is the signal.

It compares two public facts and needs no credential: the archive listing upstream, and the
coverage the site itself publishes in data/monthly_demand.yaml (meta.last, written by
refresh_monthly_demand.py from the bulk). When a listed file implies months beyond that
coverage, the check fails and prints the ingest runbook. It runs in the WEEKLY
monitor-refresh job on purpose: a weekly red mail until the quarter is ingested is a nag
proportionate to a laptop task of a few hours, where a daily one would train the reader to
ignore red (the alarm-fatigue rule in site-refresh.yml).

If the listing cannot be fetched it stands down LOUDLY and exits 0: an unreachable CDN is
upstream weather, not a stale site, and a check that reds on weather gets muted. The
stand-down is printed so a green run never claims a comparison it did not make.
"""
from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

LISTING = "https://data.jobtechdev.se/annonser/historiska/"
SITE = Path(__file__).resolve().parent.parent
# Quarter files end at month 3*Q; a plain year file ends at December. The .zst mirrors of the
# same periods are ignored, as are the taxonomy and readme entries the listing also carries.
FILE_RE = re.compile(r'href="[^"]*?/(\d{4})(?:-Q([1-4]))?\.jsonl\.zip"')


def published_coverage() -> str:
    """The last month the site's own monthly series claims, e.g. '2026-06'."""
    md = yaml.safe_load((SITE / "data" / "monthly_demand.yaml").read_text(encoding="utf-8"))
    return str(md["meta"]["last"])


def listed_periods() -> list[tuple[str, str]]:
    """[(label, final_month)] for every archive file upstream, e.g. ('2026-Q2', '2026-06')."""
    req = urllib.request.Request(LISTING, headers={
        "User-Agent": "AI-Econ Lab research (mlodefalk@gmail.com)"})
    html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    out = []
    for y, q in set(FILE_RE.findall(html)):
        label = f"{y}-Q{q}" if q else y
        out.append((label, f"{y}-{3 * int(q):02d}" if q else f"{y}-12"))
    return sorted(out)


def main() -> int:
    coverage = published_coverage()
    if "--coverage" in sys.argv:
        coverage = sys.argv[sys.argv.index("--coverage") + 1]

    try:
        periods = listed_periods()
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        print("The archive listing did NOT get checked: "
              f"{LISTING} was unreachable ({e}).\n"
              "New-release detection stands down until the next run; the site itself is "
              "unaffected.")
        return 0
    if not periods:
        # A reachable page with zero matching files means the listing changed shape, which
        # would otherwise read as an eternal green. Shape drift is a failure.
        print(f"FAIL  {LISTING} matched no archive files; the listing format has changed "
              "and this check is blind. Update FILE_RE in check_archive_release.py.")
        return 1

    behind = [(lbl, fin) for lbl, fin in periods if fin > coverage]
    if behind:
        labels = ", ".join(lbl for lbl, _ in behind)
        print(f"FAIL  the site's archive series ends {coverage}, but JobTech has published: "
              f"{labels}.\n"
              "Ingest on the laptop (each step states its own bulk; ~2h per quarter):\n")
        for lbl, _ in behind:
            print(f"  curl -o ~/.cache/aiel-jobads/{lbl}.jsonl.zip "
                  f"{LISTING.rstrip('/')}/{lbl}.jsonl.zip")
            print(f"  python3 scripts/bulk_pipeline_v11.py {lbl}          # in ai-monitor")
        print("  python3 scripts/aggregate_v11_series.py --bulk=<current bulk>\n"
              "  python3 scripts/build_monthly_series_v11.py --bulk=<current bulk>\n"
              "  commit data/<bulk>/ and data/free_cuts/ in ai-monitor and push;\n"
              "  the daily site-refresh then propagates it, no site-side step needed.")
        return 1

    print(f"ok    archive series ends {coverage}; nothing newer upstream "
          f"(latest listed: {periods[-1][0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
