#!/usr/bin/env python3
"""Daily check that the ARC-AGI-3 tile still matches ARC Prize's own leaderboard data.

WHY DAILY. ARC Prize publishes verified results mid-week (GPT-6 Astra on Wednesday 2 Sep
2026), while the weekly refresh runs on Mondays, so a moved top score could sit wrong on
the site for six days. On 2 Sep it was wrong by a factor of two. This reads the same data
file as refresh_capability.py, with the same reader, and compares the two numbers on the
tile with capability.check.arc in data/monitor.yaml.

It writes nothing and commits nothing. It exits non-zero when a top score has moved past
the tolerance or the source stops answering, which turns the arc-watch run red and makes
GitHub email the maintainer. A new row below the top does not trip it.

When it trips: read the new result on arcprize.org, update the ARC tile in monitor.yaml's
capability.facts AND capability.check.arc together, push.

Run:  python3 scripts/watch_arc_daily.py
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from refresh_capability import ARC_V3_JSON, DATA, arc_figures, arc_tops, get  # noqa: E402


def main():
    want = yaml.safe_load((DATA / "monitor.yaml").read_text(encoding="utf-8"))
    want = (want.get("capability") or {}).get("check", {}).get("arc")
    if not want:
        sys.exit("capability.check.arc is missing from data/monitor.yaml: nothing to compare")
    try:
        raw = get(ARC_V3_JSON)
    except Exception as e:
        sys.exit(f"ARC data file unreachable ({type(e).__name__}: {e})")
    tops, got = arc_tops(raw), arc_figures(raw)
    if tops is None or got is None:
        sys.exit("ARC data file no longer yields the two figures: rewrite arc_tops() in "
                 "scripts/refresh_capability.py")
    for h, (pct, model, day) in sorted(tops.items()):
        print(f"   {h:<17} top {pct:5.1f}%  {model}  ({day})")
    tol = float(want.get("tol_pct", 0.5)) / 100.0
    off = [f"{f} is {got[f]} on the source, {want[f]} on the site"
           for f in got if f in want and abs(got[f] - float(want[f])) > tol * abs(float(want[f]))]
    if off:
        sys.exit("ARC-AGI-3 top score MOVED: " + "; ".join(off) + ". Update the ARC tile in "
                 "capability.facts and capability.check.arc in data/monitor.yaml together.")
    print(f"ARC-AGI-3 tile matches the source: {got}")


if __name__ == "__main__":
    main()
