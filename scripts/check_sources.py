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

Akavia has no watcher: the data arrive from the partner by hand. That round is
a documented manual workflow (process the new wave, reconcile against Akavia's
own published figures, update data/akavia.yaml, rebuild).
"""
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = Path(__file__).resolve().parent / "watch_state.json"
UA = {"User-Agent": "AIEL-monitor-watch (python-urllib; research use)"}


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
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
    for w in (watch_ai_index, watch_daioe_dataset, watch_eu_lfs, watch_scb_amu):
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
