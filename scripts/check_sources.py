#!/usr/bin/env python3
"""WATCHERS: has any Monitor source published something newer than the site shows?

Run by the monitor-refresh GitHub Action (Mondays); fine to run locally too:

    python3 scripts/check_sources.py      # prints flags, updates watch_state.json

These are the sources a machine cannot safely auto-apply, so the job here is
detection, not application: a hit opens a GitHub issue (when GH_TOKEN is set,
i.e. in the Action; title-deduplicated against open issues) so the update is a
tracked task instead of a silent gap. State lives in scripts/watch_state.json
(committed), so each event flags once, not every week.

Watched sources and why they need a human:
  ai_index      Stanford AI Index (annual, April) — View C. The figure lives in
                a ~40 MB report PDF; extraction is assisted, not automated:
                curl the PDF, pdftotext -layout, read the "AI job postings
                (% of all job postings)" figure, update
                data/cross_country_demand.yaml, rebuild.
  daioe_dataset New commits to github.com/ai-econ-lab/daioe_dataset — the public
                DAIOE release feeding the site's exposure chart, occupation
                search and View A. When DAIOE becomes an annually auto-updated
                index, promote this to the auto-apply tier (rerun the export in
                the Action) and sync with the index's release cycle.
  eu_lfs        Eurostat lfsa_egai2d (View A employment weights). Weights are
                deliberately held at the DAIOE vintage year, so a new LFS year
                is actionable only together with a new DAIOE release.
  scb_amu       SCB Arbetsmiljöundersökningen (working-conditions module) —
                refresh_working_conditions.py needs a local DAIOE×SSYK
                crosswalk, so it cannot run on the Action runner.
  fred_rps      FRED RPS genAI adoption (US benchmark). Quarterly; detection
                only, because the series carry caveats a machine should not
                paper over. Running since 27 Jul 2026 and left out of this list
                until 17 Aug 2026.
  eurostat_     Eurostat isoc_eb_ain2, the barrier question. The one watcher
  barriers      here whose subject is auto-refreshed: refresh_barriers.py runs
                every Monday, but pinned to one wave, so it can only ever
                re-pull the year it already publishes. The pin is deliberate
                (the question's routing changed between waves), and this is
                what stops the pin from also being a blindfold.

Akavia has no watcher: the data arrive from the partner by hand. That round is
a documented manual workflow (process the new wave, reconcile against Akavia's
own published figures, update data/akavia.yaml, rebuild).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = Path(__file__).resolve().parent / "watch_state.json"
BARRIERS_GENERATOR = Path(__file__).resolve().parent / "refresh_barriers.py"
UA = {"User-Agent": "AIEL-monitor-watch (python-urllib; research use)"}


def get(url, timeout=60, ua=True):
    """Fetch a URL. ua=False sends no custom User-Agent.

    FRED's edge times out on our identifying UA string but serves the stdlib default
    fine, so the RPS watcher passes ua=False. Everywhere else we identify ourselves.
    """
    headers = UA if ua else {}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        return r.read()


def watch_ai_index(state):
    nxt = state["ai_index_seen"] + 1
    page = get("https://hai.stanford.edu/ai-index").decode("utf-8", "replace").lower()
    if f"ai index report {nxt}" in page or f"ai index {nxt}" in page:
        state["ai_index_seen"] = nxt
        return (f"Stanford AI Index {nxt} is out — update Monitor View C (demand)",
                "New edition detected on hai.stanford.edu/ai-index (annual, April). "
                "Update recipe: curl the report PDF (too big for WebFetch), pdftotext -layout, "
                "read the 'AI job postings (% of all job postings) by select geographic areas' "
                "figure, update data/cross_country_demand.yaml (incl. the Next: line to "
                f"{nxt + 1}), python3 build.py, commit.")
    return None


def watch_daioe_dataset(state):
    c = json.loads(get("https://api.github.com/repos/ai-econ-lab/daioe_dataset/commits?per_page=1"))
    sha, date = c[0]["sha"], c[0]["commit"]["committer"]["date"]
    if sha != state["daioe_dataset_seen_sha"]:
        state["daioe_dataset_seen_sha"] = sha
        return (f"DAIOE dataset repo updated ({date[:10]}) — check for a new vintage",
                f"New commit {sha[:12]} on ai-econ-lab/daioe_dataset. If this is a new released "
                "vintage (e.g. v2024): re-export the site's exposure chart + occupation search "
                "(regen pulls daioe_isco08.csv), refresh View A weights to the matching EU-LFS "
                "year, and bump the 'Next: with the DAIOE v2024 release' figure lines.")
    return None


def watch_eu_lfs(state):
    d = json.loads(get("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
                       "lfsa_egai2d?format=JSON&lang=EN&geo=SE&sex=T&age=Y15-64"))
    latest = max(int(t) for t in d["dimension"]["time"]["category"]["index"])
    if latest > state["lfs_seen"]:
        state["lfs_seen"] = latest
        return (f"EU-LFS {latest} available (lfsa_egai2d) — View A weights refreshable",
                "New LFS year for the View A employment weights. Actionable only together with a "
                "matching DAIOE vintage (weights are held at the DAIOE year on purpose); regen via "
                "projects/daioe/cross-country-heterogeneity scripts.")
    return None


def watch_scb_amu(state):
    d = json.loads(get("https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0501/AM0501A/ArbmiljoSSYK"))
    tid = next(v for v in d["variables"] if v["code"] == "Tid")
    latest = max(int(y) for y in tid["values"])
    if latest > state["amu_seen"]:
        state["amu_seen"] = latest
        return (f"SCB Arbetsmiljöundersökningen {latest} is out — refresh working-conditions module",
                "Run locally (needs the DAIOE×SSYK crosswalk file): "
                "python3 scripts/refresh_working_conditions.py, then build.py, commit.")
    return None


def watch_fred_rps(state):
    """New quarterly observation in the US genAI adoption benchmark (FRED category 8).

    The Real-Time Population Survey (Bick, Blandin and Deming, Management Science 2026)
    is the best-documented US counterpart to our Swedish adoption measures. Detection
    only: a new quarter is a prompt to decide where, if anywhere, the number belongs —
    the series carry real caveats (quota-sampled Qualtrics panel, self-reported time
    savings, an awareness gate) that a machine should not paper over. Full review in
    lab-infrastructure/ai-monitor/notes/fred-rps-genai_2026-07-27.md.
    """
    csv_text = get("https://fred.stlouisfed.org/graph/fredgraph.csv"
                   "?id=RPSGENAIUSAGESHAREALL", ua=False).decode("utf-8", "replace")
    rows = [r for r in csv_text.strip().splitlines()[1:] if "," in r]
    latest_date, latest_val = rows[-1].split(",")[0], rows[-1].split(",")[1]
    if latest_date > state.get("fred_rps_seen", ""):
        state["fred_rps_seen"] = latest_date
        return (f"FRED RPS genAI adoption: new observation {latest_date} — US benchmark refreshed",
                f"RPSGENAIUSAGESHAREALL now reports {float(latest_val):.1f}% of US adults 18-64 "
                f"using genAI as of {latest_date}. 130 series in the category (adoption, "
                "used-for-work-last-week, time savings, work hours assisted; each overall and by "
                "industry and occupation), all at "
                "https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES_ID>.\n\n"
                "Before using any of it, re-read the caveats in "
                "lab-infrastructure/ai-monitor/notes/fred-rps-genai_2026-07-27.md: denominators "
                "differ across families (all 18-64s vs employed), time savings is a "
                "self-reported counterfactual and not measured productivity, the industry and "
                "occupation cuts are small-cell noisy quarter-on-quarter, and respondents who "
                "have never heard of genAI are routed past the module and counted as non-users.")
    return None


def pinned_barrier_year():
    """The barrier wave scripts/refresh_barriers.py is pinned to, read out of the generator.

    Derived, never repeated. That integer already exists in two places, the generator and
    meta.year in data/barriers.yaml, and a third copy here would be the one nobody remembers
    to move: the watcher would then report "no new wave" against a year the site left behind,
    which is worse than having no watcher, because it reads as an all-clear.

    Parsed rather than imported, for two reasons. refresh_barriers.py imports PyYAML, and the
    workflow describes that dependency as scoped to the refresh chain, so importing it here
    would quietly make the watchers depend on it too. And what is being checked is the literal
    a person edits, not what the module computes, so reading the literal is the more direct
    test. Raises if the constant has been renamed or is no longer a plain four-digit literal;
    main() turns that into a red run, which is right, because the alternative is a watcher
    comparing against a year it guessed.
    """
    m = re.search(r"^YEAR\s*=\s*(\d{4})\b",
                  BARRIERS_GENERATOR.read_text(encoding="utf-8"), re.MULTILINE)
    if not m:
        raise RuntimeError("no `YEAR = <four digits>` line in scripts/refresh_barriers.py; the "
                           "barrier watcher reads the pinned wave from there and will not guess")
    return int(m.group(1))


def watch_eurostat_barriers(state):
    """Has Eurostat published a barrier wave later than the one the site is pinned to?

    This one guards a gap the rest of the machinery cannot see. refresh_barriers.py is on the
    Monday auto-apply list, but it asks Eurostat for one fixed year, so it can only ever
    re-pull the wave it already publishes. The inverted year gate in weekly_refresh.py fires
    when a HUMAN moves that constant; nothing anywhere looks at what Eurostat has. Without
    this the site could sit on a superseded wave indefinitely and every run would stay green.

    Asked of one of the module's own eight indicators and of every country: one indicator
    because the eight are a single question and publish together, which keeps the response at
    ~5 KB instead of the ~79 KB the unfiltered cube returns, and no geo filter because a wave
    that reaches some countries before Sweden is still news, and whether it is actionable is
    the reading this issue asks for. The time dimension's category index is the published list
    of periods, so no scraping is involved.

    The reference point is max(pinned, last flagged): pinned so that the watcher goes quiet by
    itself once the generator catches up, last-flagged so that an undecided wave is raised once
    rather than every Monday. barriers_seen is deliberately absent from watch_state.json until
    something is flagged, since seeding it with the current wave would put back the third copy
    of the constant this function exists to avoid.
    """
    pinned = pinned_barrier_year()
    d = json.loads(get("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
                       "isoc_eb_ain2?format=JSON&lang=EN&unit=PC_ENT&size_emp=GE10"
                       "&nace_r2=C10-S951_X_K&indic_is=E_AI_BLE"))
    if not d.get("value"):
        raise RuntimeError("isoc_eb_ain2 returned no observations, so its time index says "
                           "nothing about which waves exist")
    latest = max(int(t) for t in d["dimension"]["time"]["category"]["index"])
    if latest <= max(pinned, int(state.get("barriers_seen", 0))):
        return None
    state["barriers_seen"] = latest
    return (f"Eurostat barrier wave {latest} is out (isoc_eb_ain2) — read the routing before "
            "the site moves",
            f"Eurostat now publishes isoc_eb_ain2 for {latest}. scripts/refresh_barriers.py is "
            f"pinned to YEAR = {pinned} and will go on re-pulling {pinned} until a person moves "
            "it, which is why this is an issue and not a refresh.\n\n"
            "THE PIN IS ABOUT ROUTING, NOT ABOUT CAUTION. The barrier question has not always "
            "been asked of the same firms. In the Swedish source register 2021 asked it of all "
            "non-adopters and 3,425 firms answered; 2023 gated it on E_AI_EC == 1, considered "
            "AI but did not adopt, and 482 firms answered. Eurostat carries that through rather "
            "than washing it out: every Swedish 2023 cell in isoc_eb_ain2 is flagged `b`, break "
            "in time series, and Sweden was the only one of the 27 reporting countries flagged "
            f"that year. A {pinned}-to-{latest} movement can therefore be routing rather than "
            "anything firms said, and a new wave need not describe the same universe at all.\n\n"
            "So the next step is a reading:\n\n"
            f"1. Pull the {latest} wave for Sweden and read the `status` block, not the values: "
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/isoc_eb_ain2"
            "?format=JSON&lang=EN&unit=PC_ENT&size_emp=GE10&nace_r2=C10-S951_X_K&geo=SE"
            f"&time={latest}. Check whether the eight E_AI_B* cells carry `b`, and whether any "
            "other country does.\n"
            f"2. Decide whether {latest} and {pinned} describe the same universe, and write the "
            "answer into the PERMITTED/FORBIDDEN table in the refresh_barriers.py docstring "
            "either way. That table is the record of this judgement; leaving it unextended is "
            "how the next reader loses the reason.\n"
            f"3. If it is publishable: set YEAR = {latest} in scripts/refresh_barriers.py, run "
            "`python3 scripts/refresh_barriers.py && python3 build.py`, and commit the "
            "regenerated data/barriers.yaml in the same change. check_barriers in "
            "weekly_refresh.py compares the regenerated year against the year in the COMMITTED "
            "barriers.yaml, so bumping the constant on its own just fails the next Monday run "
            "and restores the old file.\n"
            f"4. If it is not publishable: leave the pin at {pinned} and close this. The wave is "
            "recorded in watch_state.json, so it will not be raised again; the watcher fires "
            "next on whatever comes after it.")


def open_issue(title, body):
    """Create a GitHub issue unless an open one already has this title."""
    gh = shutil.which("gh")
    if not gh or not (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")):
        return
    existing = subprocess.run([gh, "issue", "list", "--state", "open", "--json", "title"],
                              cwd=ROOT, capture_output=True, text=True)
    titles = [i["title"] for i in json.loads(existing.stdout or "[]")]
    if title not in titles:
        subprocess.run([gh, "issue", "create", "--title", title, "--body", body],
                       cwd=ROOT, check=True, capture_output=True, text=True)


def main():
    state = json.loads(STATE_FILE.read_text())
    errors, flags = [], []
    for w in (watch_ai_index, watch_daioe_dataset, watch_eu_lfs, watch_scb_amu,
              watch_fred_rps, watch_eurostat_barriers):
        try:
            hit = w(state)
            if hit:
                flags.append(hit)
        except Exception as e:                 # noqa: BLE001 — a dead watcher must turn the run red
            errors.append(f"{w.__name__}: {e}")
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")

    for title, body in flags:
        print(f"FLAG {title}")
        open_issue(title, body)
    if not flags:
        print("no new source releases")
    if errors:
        sys.exit("watcher errors (source may be unmonitored!): " + "; ".join(errors))


if __name__ == "__main__":
    main()
