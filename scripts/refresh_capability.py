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
  WATCHED       METR task horizons and ARC-AGI. Neither can be auto-applied: the tiles are
                editorial readings of a chart ("12-17 h", "x2 every ~4 mo"), not a field to
                copy. So the job here is detection: watch a source identity, flag when it
                moves, and let a human read the new number. A watched fact that has not been
                re-read within STALE_DAYS is reported as stale rather than quietly shown as
                current.

  VERIFIED      METR, additionally, since 4 Sep 2026. The page embeds its full results blob,
                so while the tile text still needs a human, the NUMBERS BEHIND IT DO NOT: the
                doubling time and the top two 50%-horizon measurements are read straight out
                of benchmarkDataV1_1 on every run and compared with the expected values in
                monitor.yaml's capability.check block. This is the difference between "nobody
                has looked in four months" and "the figures were confirmed correct this
                morning", and only the second is worth a person's attention when it breaks.
                Divergence beyond the stored tolerance is a note, and notes fail the weekly
                run. ARC gets no such check: its leaderboard streams client-side and the HTML
                carries no scores at all.

                WHAT "IDENTITY" MEANS DIFFERS BY SOURCE, and that matters more than it sounds.
                Hashing a whole page detects changes that are not changes: metr.org serves
                byte-different HTML from different CDN edges, so the runner and a laptop
                disagree permanently, and the gate then trips on every run forever. It did.
                So each watched source declares how to identify itself:

                  data anchor  METR. Its page embeds a thData blob carrying the benchmark
                               names and the two task-suite content hashes
                               (long_tasks_version, swaa_version). Those change exactly when
                               the measurements change and are identical from every vantage:
                               verified 12 Aug 2026 across six fetches spanning two different
                               whole-page hashes, one of them a 605 KB response against the
                               usual 417 KB. This is the anchor to prefer wherever a source
                               offers one.
                  page hash    ARC-AGI, because it offers nothing better. The leaderboard is a
                               Next.js app that streams its rows client-side; the HTML carries
                               no scores and its page chunk is 6 KB of d3 rendering code with
                               no data and no fetch call (checked 12 Aug 2026). Its page hash
                               is at least vantage-stable, so detection works even though the
                               figure itself must still be read in a browser.

                A source that stops yielding its anchor is an error, never a silent fallback to
                page hashing: falling back would trip the gate and read as a data change.

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
import os
import re
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STATE_FILE = Path(__file__).resolve().parent / "watch_state.json"
OUT = DATA / "capability.yaml"
UA = {"User-Agent": "AIEL-monitor-refresh (python-urllib; research use)"}

EPOCH_CSV = "https://epoch.ai/data/notable_ai_models.csv"
STALE_DAYS = 120           # one quarter plus a fortnight of slack
TODAY = dt.date.today()

# The state file is the runner's record of what a human has signed off. A local run that
# writes it silently overwrites that record with values from a different vantage, which is
# how the METR gate jammed between 10 and 12 Aug 2026: a local run put a laptop's page hash
# in as the acknowledged one, the runner could never match it, and neither clearing route
# could fire again. So CI owns the file. Locally the script still prints everything and still
# regenerates capability.yaml; it just does not persist. Set AIEL_ALLOW_STATE_WRITE=1 to
# override, which is for a deliberate schema migration and nothing else.
CI_OWNS_STATE = bool(os.environ.get("GITHUB_ACTIONS"))
ALLOW_STATE_WRITE = CI_OWNS_STATE or os.environ.get("AIEL_ALLOW_STATE_WRITE") == "1"


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
def metr_identity(raw):
    """METR's data identity: its benchmark names and the two task-suite content hashes.

    The page embeds a thData blob whose dataset objects carry benchmark_name,
    long_tasks_version and swaa_version. Those are the suite's own content hashes, so they
    move when the measurements move and not when the CDN, the page shell or an asset digest
    moves. Collected as distinct sorted sets rather than by picking out "the current one":
    a new benchmark version appearing is exactly the event we want flagged, so hardcoding
    v1.1 here would hide the thing worth catching.

    The benchmark names are kept whole and only the 40-character hashes are truncated. An
    earlier draft truncated everything to 12 characters, which collapsed METR-Horizon-v1.0
    and METR-Horizon-v1.1 into one token and would have concealed a new suite entirely.

    Returns None if the fields are absent, which the caller treats as an error."""
    text = raw.decode("utf-8", "replace")

    def distinct(field, cut=None):
        found = set(re.findall(rf'"{field}":"([^"]+)"', text))
        return sorted(v[:cut] if cut else v for v in found)

    names = distinct("benchmark_name")
    long_tasks = distinct("long_tasks_version", 12)
    swaa = distinct("swaa_version", 12)
    if not (names and long_tasks and swaa):
        return None
    return (f"benchmarks={','.join(names)} long_tasks={','.join(long_tasks)} "
            f"swaa={','.join(swaa)}")


def metr_figures(raw):
    """The numbers behind the two METR tiles, read out of the page's own data blob.

    `benchmarkDataV1_1` carries doubling_time_in_days for the current suite and a
    p50_horizon_length estimate per model, in minutes. The tile shows a BAND ("12-17 h"),
    which is the top two measurements, so both are returned rather than only the maximum:
    a new frontier model displacing the top entry moves one number and not the other, and
    the band is wrong in a different way in each case.

    Returns None if the blob or either field is absent, which the caller reports rather
    than silently skipping. Getting no answer from a source that used to answer is exactly
    the event this check exists to catch."""
    m = re.search(r"const benchmarkDataV1_1 = (\{.*?\});\s*\n",
                  raw.decode("utf-8", "replace"), re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    dt = (d.get("doubling_time_in_days") or {}).get("from_2023_on") or {}
    p50 = sorted((r["metrics"]["p50_horizon_length"]["estimate"]
                  for r in (d.get("results") or {}).values()
                  if "p50_horizon_length" in (r.get("metrics") or {})), reverse=True)
    if not dt.get("point_estimate") or len(p50) < 2:
        return None
    return {"doubling_days": round(dt["point_estimate"], 3),
            "top_p50_hours": round(p50[0] / 60, 2),
            "second_p50_hours": round(p50[1] / 60, 2)}


WATCHED = {
    "metr": {"url": "https://metr.org/time-horizons/", "identity": metr_identity,
             "figures": metr_figures},
    # the leaderboard, not /arc-agi: the overview page carries no scores, so watching it
    # would report "unchanged" while the numbers underneath moved. No data anchor exists
    # either way, so this one is a page hash; see the module docstring.
    "arc": {"url": "https://arcprize.org/leaderboard", "identity": None},
}


def source_identity(cfg):
    """What this source looks like right now, plus the bytes it came in.

    The identity is prefixed with the scheme that produced it, so the state file says how
    each source is being watched and a scheme change is visible rather than looking like a
    data change. The raw bytes come back too because the figure check reads the same
    response: one request, two uses.

    Returns (identity, raw) and raw is None whenever the identity is an ERROR."""
    try:
        raw = get(cfg["url"])
    except Exception as e:                      # a dead source must not kill the build
        return f"ERROR:{type(e).__name__}", None
    if cfg["identity"] is None:
        return "page:" + hashlib.sha256(raw).hexdigest()[:16], raw
    ident = cfg["identity"](raw)
    if ident is None:
        # Never fall back to a page hash: that would trip the gate and read as a data
        # change, when what actually happened is that our anchor needs rewriting.
        return "ERROR:AnchorMissing", None
    return "data:" + ident, raw


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


def as_date(v):
    """YAML gives an unquoted 2026-08-03 as a date and a quoted one as a string; the state
    file always holds strings. Normalise both, and treat anything unparseable as absent."""
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v).strip())
    except (ValueError, TypeError, AttributeError):
        return None


def watched_asof(cur, key):
    """The as-of date on the tile a watched source feeds, or None if it carries no date.

    Matched the same way the facts loop below picks the Epoch tile: on the source name at
    the head of the footnote, so 'metr' finds 'METR Time Horizon 1.1 · May 2026'."""
    for f in cur["facts"]:
        if f["foot"].split("·")[0].strip().lower().startswith(key):
            return parse_asof(f["foot"])
    return None


def main():
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    cur = yaml.safe_load((DATA / "monitor.yaml").read_text(encoding="utf-8"))["capability"]

    mult, n_models, epoch_asof = epoch_compute_trend()
    print(f"epoch: x{mult:.2f}/year on {n_models} notable models since 2020, "
          f"file current to {epoch_asof}")

    # A CHANGE NOTE MUST OUTLIVE THE RUN THAT RAISED IT. The first version stored the new
    # fingerprint on the same run that reported the change, so the note appeared exactly once
    # and any later run — the next Monday's, or a manual dispatch — erased it. That is the
    # ARC-AGI failure again in a smaller form: on 3 Aug 2026 the watcher caught METR moving,
    # and the alert was gone within the hour, unread.
    #
    # So capability_{key}_id is now the ACKNOWLEDGED identity: the source state a human has
    # actually read. A newer observed identity is held as _pending_id and re-reported every
    # run until the re-read happens. TWO THINGS COUNT AS A RE-READ:
    #
    #   the figure moved   the tile's own as-of date passes _pending_since_asof. Same
    #                      convention the stale gate uses: clearing the flag is the re-read.
    #   the figure did not a `reviewed: {metr: 2026-08-03}` stamp in monitor.yaml's capability
    #                      block, dated on or after the change was detected.
    #
    # The second route exists because the first cannot express the commonest outcome. On
    # 3 Aug 2026 METR's page changed while its figures did not: the stamp still read May 2026
    # and the model table was unchanged, so the only honest re-read was "looked, nothing
    # moved". With the date route alone, clearing that would have meant redating a May figure
    # as August — inventing provenance to silence an alarm, which is worse than the alarm.
    # `reviewed` separates when a figure is from from when we last checked it.
    reviewed = cur.get("reviewed") or {}
    expected = cur.get("check") or {}
    notes, stale, undated, stale_days, verified = [], [], [], [], {}
    for key, cfg in WATCHED.items():
        fp, raw = source_identity(cfg)
        state[f"capability_{key}_checked"] = TODAY.isoformat()
        ack_key = f"capability_{key}_id"
        pend_key = f"capability_{key}_pending_id"
        since_key = f"capability_{key}_pending_since_asof"
        det_key = f"capability_{key}_pending_detected"
        state.pop(f"capability_{key}_fp", None)          # retired whole-page-hash scheme
        state.pop(f"capability_{key}_pending_fp", None)

        if fp.startswith("ERROR:"):
            # Never remember an outage as an identity: the old code stored "ERROR:..." and
            # the next successful run then read that as a source change that never happened.
            reason = ("its thData anchor is gone — rewrite metr_identity()"
                      if fp == "ERROR:AnchorMissing" else f"source unreachable ({fp[6:]})")
            notes.append(f"{key}: {reason}")
            continue

        # THE FIGURE CHECK, where the source offers one. This is what turns "nobody has
        # looked since May" into "the numbers were confirmed this morning". It runs whether
        # or not the identity moved, because the two can come apart in both directions: a
        # page can be rebuilt without the measurements changing, and in principle a number
        # could move under an unchanged anchor, which is the case no watcher would catch.
        want = expected.get(key)
        if cfg.get("figures") and want:
            got = cfg["figures"](raw)
            if got is None:
                notes.append(f"{key}: the page no longer yields the figures we verify against "
                             f"— rewrite {cfg['figures'].__name__}()")
            else:
                tol = float(want.get("tol_pct", 5)) / 100.0
                off = [f"{f} is {got[f]} on the source, {want[f]} here"
                       for f in got
                       if f in want and abs(got[f] - float(want[f])) > tol * abs(float(want[f]))]
                if off:
                    notes.append(f"{key}: the source figures have MOVED — " + "; ".join(off)
                                 + f". Update the tiles and capability.check.{key} in "
                                   "monitor.yaml together.")
                else:
                    verified[key] = {"on": TODAY.isoformat(), **got}

        ack = state.get(ack_key)
        if ack is None or fp == ack:
            state[ack_key] = fp                    # first sight, or unchanged since the read
            for k in (pend_key, since_key, det_key):
                state.pop(k, None)
            continue

        # Record when this change was first seen BEFORE testing the sign-off, so a stamp
        # made the same day takes effect on this run. Testing first cost a run's lag: the
        # sign-off looked ignored until the next refresh, which reads as a broken gate.
        asof = watched_asof(cur, key)
        state.setdefault(since_key, asof.isoformat() if asof else "")
        state.setdefault(det_key, TODAY.isoformat())

        moved = bool(as_date(state[since_key]) and asof
                     and asof > as_date(state[since_key]))
        seen_on, det_on = as_date(reviewed.get(key)), as_date(state[det_key])
        signed_off = bool(seen_on and det_on and seen_on >= det_on)
        if moved or signed_off:
            state[ack_key] = fp
            for k in (pend_key, since_key, det_key):
                state.pop(k, None)
            continue

        state[pend_key] = fp
        what = "measurements" if fp.startswith("data:") else "source page"
        notes.append(f"{key}: {what} CHANGED since last check — re-read the figure "
                     f"(detected {state[det_key]}; was {ack}, now {fp}; if the figure is "
                     f"unchanged, stamp it in monitor.yaml as capability.reviewed.{key})")

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
                # The age as a number, not only inside a sentence. The weekly gate needs to
                # tell "old because the source has not published" from "old enough that we
                # should decide whether to keep showing it", and it cannot do that on prose.
                stale_days.append((TODAY - asof).days)
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
                   "public model table on every refresh; the METR figures are checked against "
                   "the source's own published measurements on every refresh and read by hand "
                   "when they move; the ARC-AGI figure is read by hand when its source moves. "
                   "Each tile carries its own date."),
        "checked": TODAY.isoformat(),
        # carried through so the generated file records when a watched source was last
        # confirmed unchanged, which is not the same thing as when its figure is from
        "reviewed": {k: str(v) for k, v in sorted(reviewed.items())},
        # What was checked against the source itself, not merely watched for movement. The
        # page prints nothing from this; it exists so a stale-looking date can be answered
        # with "and the figures were confirmed on <date>" rather than with a shrug.
        "verified": verified,
        # A POSITIVE CONTROL. Without it, deleting the check block in monitor.yaml, or a
        # rename that stops the figures function being found, would show up as silence:
        # no verification, no note, and a green run. The weekly gate asserts that every
        # source listed here came back either verified or complained about.
        "checks_configured": sorted(expected),
        "stale": stale,
        "stale_days": stale_days,
        "undated": undated,
        "notes": notes,
    }
    OUT.write_text(
        "# Generated by scripts/refresh_capability.py. Do not hand-edit.\n"
        + yaml.dump(block, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8")
    if ALLOW_STATE_WRITE:
        STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    print(f"\ncapability.yaml written · flag: {flag}")
    if not ALLOW_STATE_WRITE:
        print("   watch_state.json NOT written: CI owns it, and a local write would put this "
              "machine's view in as the acknowledged one. Clear a gate by stamping "
              "capability.reviewed.<source> in data/monitor.yaml instead.")
    for f in facts:
        print(f"   [{f['mode']:7}] {f['num']:<16} {f['foot']}")
    for k, v in verified.items():
        nums = ", ".join(f"{f}={v[f]}" for f in v if f != "on")
        print(f"   VERIFIED {k}: matches the source today ({nums})")
    for s in stale:
        print(f"   STALE:   {s}")
    for u in undated:
        print(f"   UNDATED: {u} — give it a date in monitor.yaml or it is never checked")
    for nte in notes:
        print(f"   NOTE:    {nte}")


if __name__ == "__main__":
    main()
