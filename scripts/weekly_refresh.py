#!/usr/bin/env python3
"""Weekly AUTO-APPLY refresh of the Monitor's API-backed sources.

Run by the monitor-refresh GitHub Action (Mondays); fine to run locally too:

    python3 scripts/weekly_refresh.py     # then build.py if it reports changes

The automation has two tiers, because "capture every source update" needs
detection everywhere but auto-application only where a machine can verify the
result end-to-end:

  AUTO-APPLY (this script) — pure public-API pulls, nothing outside this repo:
    refresh_cross_country.py   Eurostat isoc_eb_ai   -> data/cross_country_adoption.yaml
    refresh_swe_adoption.py    SCB NV0116            -> data/swe_adoption.yaml
  WATCH (scripts/check_sources.py) — sources needing a human step: AI Index PDF
    (View C), DAIOE dataset releases, EU-LFS weights (gated on the DAIOE
    vintage), SCB AMU (needs a local DAIOE crosswalk). A hit opens a GitHub
    issue instead of guessing.

Every refreshed file must pass a sanity gate BEFORE it can reach the site: a
glitchy API response has to fail loudly here, never publish. On a failed gate
the file is restored from git and the run exits non-zero, which turns the
Action red (GitHub then emails the maintainer). The gates are deliberately
coarse (country counts, 0-100 bounds, the wave year must not go backwards):
they catch a broken pull, not a subtly wrong one — the per-figure vintages on
the site remain the human-audited truth.
"""
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def run_refresher(script):
    """Run one refresh script; return True on success."""
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / script)],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(f"FAIL {script}: {r.stderr.strip()[-500:]}")
        return False
    tail = r.stdout.strip().splitlines()
    print(f"ok   {script}" + (f" — {tail[-1]}" if tail else ""))
    return True


def restore(relpath):
    subprocess.run(["git", "checkout", "--", relpath], cwd=ROOT, check=False)


def load(relpath):
    return yaml.safe_load((ROOT / relpath).read_text(encoding="utf-8"))


def pct_ok(v):
    return v is None or (isinstance(v, (int, float)) and 0 <= v <= 100)


def check_adoption(d, prev_year):
    rows = d["countries"]
    assert len(rows) >= 25, f"only {len(rows)} countries (Eurostat wave incomplete?)"
    assert any(r.get("is_se") for r in rows), "Sweden missing"
    assert all(pct_ok(r.get("adoption")) and pct_ok(r.get("prev")) for r in rows), \
        "adoption share outside 0-100"
    assert pct_ok(d["meta"].get("eu_avg")), "eu_avg outside 0-100"
    y = int(d["meta"]["year"])
    assert prev_year <= y <= prev_year + 5, f"wave year went from {prev_year} to {y}"


def check_swe(d, prev_year):
    rows = d["sizes"]
    assert len(rows) >= 3, f"only {len(rows)} size classes"
    assert all(pct_ok(r.get("adoption")) and pct_ok(r.get("prev")) for r in rows), \
        "adoption share outside 0-100"
    assert pct_ok(d["meta"].get("total")), "total outside 0-100"
    y = int(d["meta"]["year"])
    assert prev_year <= y <= prev_year + 5, f"wave year went from {prev_year} to {y}"


JOBS = [
    ("refresh_cross_country.py", "data/cross_country_adoption.yaml", check_adoption),
    ("refresh_swe_adoption.py", "data/swe_adoption.yaml", check_swe),
]


def main():
    failed = []
    for script, target, gate in JOBS:
        prev_year = int(load(target)["meta"]["year"])   # before the pull: the year must not regress
        if not run_refresher(script):
            restore(target)
            failed.append(script)
            continue
        try:
            gate(load(target), prev_year)
        except Exception as e:                          # noqa: BLE001 — any gate breach means restore
            print(f"GATE {script}: {e} — restoring {target}")
            restore(target)
            failed.append(script)

    diff = subprocess.run(["git", "diff", "--name-only", "--", "data/"],
                          cwd=ROOT, capture_output=True, text=True).stdout.strip()
    print("changed: " + (diff.replace("\n", ", ") or "nothing"))
    if failed:
        sys.exit(f"refresh failed for: {', '.join(failed)}")


if __name__ == "__main__":
    main()
