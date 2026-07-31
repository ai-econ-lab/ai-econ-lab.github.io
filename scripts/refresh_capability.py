#!/usr/bin/env python3
"""Build data/capability.yaml — Module 5, and the refresher the module was promising.

Read-gate item A8: the module's flag said "External series · refreshed quarterly" while it
was the only module on the Monitor with no refresh script, so nothing enforced the promise
and its figures had drifted four to five months behind. Magnus's call on 31 Jul 2026 was to
write the refresher rather than drop the word.

Not every external series can be honestly automated, so this splits them:

  AUTO-APPLIED  Epoch AI training-compute growth. epoch.ai publishes notable_ai_models.csv,
                so the trend is recomputed here from the raw rows rather than quoted: an OLS
                fit of log10(training compute) on publication date over all notable models
                since 2020. The as-of date is the newest publication date in the file, so it
                cannot drift behind the source.
  WATCHED       METR task horizons and ARC-AGI. Neither publishes the headline figure in a
                machine-readable form (METR's public repo carries release dates only), so the
                job here is detection: hash the source page, flag when it moves, and let a
                human read the new number. A watched fact that has not been re-read within
                STALE_DAYS is reported as stale rather than quietly shown as current.

The flag string is generated from what actually happened, so the page can only ever claim
the freshness it has.

Run:  python3 scripts/refresh_capability.py        (then python3 build.py)
"""
import csv
import datetime as dt
import hashlib
import io
import json
import math
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STATE_FILE = Path(__file__).resolve().parent / "watch_state.json"
OUT = DATA / "capability.yaml"
UA = {"User-Agent": "AIEL-monitor-refresh (python-urllib; research use)"}

EPOCH_CSV = "https://epoch.ai/data/notable_ai_models.csv"
WATCHED = {
    "metr": "https://metr.org/time-horizons/",
    # the leaderboard, not /arc-agi: the overview page carries no scores, so hashing it
    # would report "unchanged" while the numbers underneath moved
    "arc": "https://arcprize.org/leaderboard",
}
STALE_DAYS = 120           # one quarter plus a fortnight of slack
TODAY = dt.date.today()


def get(url, timeout=90):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ------------------------------------------------------------------ Epoch: recomputed
def epoch_compute_trend():
    """OLS of log10(training compute FLOP) on decimal publication year, models since 2020.

    Returns (multiple_per_year, n_models, asof_date). Fitted on all notable models rather
    than on a frontier subset: the frontier top-decile fit gives a visibly lower figure
    (~3.6x), so the label must say which population it describes, and the published Epoch
    headline this module quotes is the notable-models one."""
    rows = list(csv.DictReader(io.StringIO(get(EPOCH_CSV).decode("utf-8", "replace"))))
    pts, latest = [], None
    for r in rows:
        d = (r.get("Publication date") or "").strip()
        c = (r.get("Training compute (FLOP)") or "").strip()
        if len(d) < 10:
            continue
        try:
            day = dt.date.fromisoformat(d[:10])
        except ValueError:
            continue
        latest = day if latest is None or day > latest else latest
        if not c:
            continue
        try:
            v = float(c)
        except ValueError:
            continue
        if v <= 0 or day.year < 2020:
            continue
        pts.append((day.year + (day.timetuple().tm_yday - 1) / 365.25, math.log10(v)))
    if len(pts) < 30:
        raise SystemExit(f"epoch: only {len(pts)} usable rows since 2020 — refusing to fit")
    n = len(pts)
    mx = sum(a for a, _ in pts) / n
    my = sum(b for _, b in pts) / n
    slope = (sum((a - mx) * (b - my) for a, b in pts) / sum((a - mx) ** 2 for a, _ in pts))
    return 10 ** slope, n, latest


# ------------------------------------------------------------------ METR / ARC: watched
def page_fingerprint(url):
    try:
        return hashlib.sha256(get(url)).hexdigest()[:16]
    except Exception as e:                      # a dead source must not kill the build
        return f"ERROR:{type(e).__name__}"


def month_name(d):
    return d.strftime("%b %Y")


def parse_asof(foot):
    """Pull 'May 2026' out of a footnote like 'METR Time Horizon 1.1 · May 2026'."""
    tail = foot.split("·")[-1].strip()
    for fmt in ("%b %Y", "%B %Y"):
        try:
            return dt.datetime.strptime(tail, fmt).date()
        except ValueError:
            pass
    return None


def main():
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    cur = yaml.safe_load((DATA / "monitor.yaml").read_text(encoding="utf-8"))["capability"]

    mult, n_models, epoch_asof = epoch_compute_trend()
    print(f"epoch: x{mult:.2f}/year on {n_models} notable models since 2020, "
          f"file current to {epoch_asof}")

    notes, stale, undated = [], [], []
    for key, url in WATCHED.items():
        fp = page_fingerprint(url)
        prev = state.get(f"capability_{key}_fp")
        if fp.startswith("ERROR:"):
            notes.append(f"{key}: source unreachable ({fp[6:]})")
        elif prev and prev != fp:
            notes.append(f"{key}: source page CHANGED since last check — re-read the figure")
        state[f"capability_{key}_fp"] = fp
        state[f"capability_{key}_checked"] = TODAY.isoformat()

    facts = []
    for f in cur["facts"]:
        foot, num, lab = f["foot"], f["num"], f["lab"]
        src = foot.split("·")[0].strip().lower()
        if src.startswith("epoch"):
            num = f"×{mult:.1f} per year"
            lab = ("Growth of computing power used to train notable AI models, since 2020 "
                   "(refit here from Epoch's model table, not quoted)")
            foot = f"Epoch AI · notable models · {month_name(epoch_asof)}"
            asof = epoch_asof
            mode = "auto"
        else:
            asof = parse_asof(foot)
            mode = "watched"
            if asof is None:
                # a footnote with no date can never be stale-checked, which is how the
                # doubling-time tile sat undated behind a quarterly promise
                undated.append(foot)
            elif (TODAY - asof).days > STALE_DAYS:
                stale.append(f"{foot} ({(TODAY - asof).days} days old)")
        facts.append({"num": num, "lab": lab, "foot": foot, "mode": mode,
                      "asof": asof.isoformat() if asof else None})

    words = {1: "one", 2: "two", 3: "three", 4: "four"}
    n_overdue = len(stale)
    if n_overdue:
        w = words.get(n_overdue, str(n_overdue))
        flag = (f"External series · checked {TODAY:%d %b %Y} · "
                f"{w} figure{'s' if n_overdue > 1 else ''} awaiting a source update")
    else:
        flag = f"External series · checked {TODAY:%d %b %Y}"

    block = {
        # weekly_refresh.py keys every job off meta.year and refuses a year that regresses;
        # ours is the vintage of the auto-applied fact, the only one that can move by itself
        "meta": {"year": epoch_asof.year, "epoch_asof": epoch_asof.isoformat(),
                 "epoch_multiple": round(mult, 2), "epoch_n_models": n_models},
        "flag": flag,
        "intro": cur["intro"],
        "facts": facts,
        "links": cur["links"],
        "caveat": (cur["caveat"] + " The compute trend is recomputed here from Epoch's "
                   "public model table on every refresh; the METR and ARC-AGI figures are "
                   "read by hand when their sources move, and each tile carries its own date."),
        "checked": TODAY.isoformat(),
        "stale": stale,
        "undated": undated,
        "notes": notes,
    }
    OUT.write_text(
        "# Generated by scripts/refresh_capability.py. Do not hand-edit.\n"
        + yaml.dump(block, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8")
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    print(f"\ncapability.yaml written · flag: {flag}")
    for f in facts:
        print(f"   [{f['mode']:7}] {f['num']:<16} {f['foot']}")
    for s in stale:
        print(f"   STALE:   {s}")
    for u in undated:
        print(f"   UNDATED: {u} — give it a date in monitor.yaml or it is never checked")
    for nte in notes:
        print(f"   NOTE:    {nte}")


if __name__ == "__main__":
    main()
