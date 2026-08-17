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
    refresh_capability.py      Epoch AI              -> data/capability.yaml
    refresh_barriers.py        Eurostat isoc_eb_ain2 -> data/barriers.yaml
    refresh_population_ai.py   SCB LE0108T82         -> data/population_ai.yaml
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

Two of the gates check something else again: that a hand-augmentation of the
committed file survives the regenerated one. Both files added on 17 Aug 2026
carried an edit their generator did not reproduce, and in the barriers case the
loss was silent, because build.py falls back to the English label. A refresher
that cannot rebuild its own committed output does not belong on a schedule, so
the gate asserts the augmented field on every run rather than trusting that it
is still in the generator. The barriers year gate is inverted from all the
others; the reason for that is in check_barriers.
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


def check_capability(d, prev_year):
    """Module 5. Only the Epoch compute trend is auto-applied, so that is what is gated:
    a refit that lands outside 1.5x-15x per year means the model table changed shape, not
    that compute growth changed, and the old figure is safer than a wrong new one."""
    facts = d["facts"]
    assert len(facts) >= 3, f"only {len(facts)} capability tiles"
    m = d["meta"]["epoch_multiple"]
    assert 1.5 <= m <= 15, f"Epoch refit x{m}/year is outside the plausible band"
    assert d["meta"]["epoch_n_models"] >= 100, \
        f"only {d['meta']['epoch_n_models']} models in the Epoch fit"
    assert any(f.get("mode") == "auto" for f in facts), "no auto-applied fact left"
    y = int(d["meta"]["year"])
    assert prev_year <= y <= prev_year + 5, f"Epoch vintage went from {prev_year} to {y}"

    # THE HUMAN LOOP, ENFORCED. Magnus's decision of 1 Aug 2026: keep all four tiles and
    # commit to a quarterly re-read of the two watched sources. The machinery for detecting
    # staleness already worked before that decision -- the watcher flagged that ARC's page had
    # changed, and refresh_capability.py listed the tile as stale on the page itself. What
    # failed was that nobody acted, for four months, while the ARC-AGI-3 figure went from
    # "under 1%" to 30.2%. An honest flag that only ever appears on the page is a flag aimed
    # at readers, not at us.
    #
    # So a stale watched fact now FAILS the weekly run. The workflow commits and pushes before
    # its failure gate, so this notifies without blocking the Eurostat and SCB auto-refresh.
    # Clearing it is the re-read itself: read the source, update monitor.yaml, re-run
    # refresh_capability.py.
    stale = d.get("stale") or []
    assert not stale, ("watched capability sources are overdue a human re-read: "
                       + "; ".join(stale)
                       + ". Read the source, update the fact in data/monitor.yaml, and re-run "
                         "scripts/refresh_capability.py.")

    # The same argument applies one step earlier. `stale` fires only once STALE_DAYS have
    # run out; `notes` fires the moment a watched source page moves, which is the first
    # moment a re-read is worth doing. It was left out of this gate, and nothing else reads
    # it: build.py never renders notes, so a detected change reached neither the page nor
    # the run. It went into a YAML file and stopped there.
    notes = d.get("notes") or []
    assert not notes, ("watched capability sources need a human re-read: "
                       + "; ".join(notes)
                       + ". Read the source, update the fact in data/monitor.yaml, and re-run "
                         "scripts/refresh_capability.py.")


def check_barriers(d, prev_year):
    """Eurostat isoc_eb_ain2, the module that says why firms do NOT use AI.

    Two of these asserts are unusual, and both date from 17 Aug 2026, when this pull went
    onto the weekly list.

    name_sv is checked because the committed barriers.yaml had been hand-augmented with the
    eight Swedish bar labels after Lydia's review of 11 Aug 2026, and refresh_barriers.py did
    not emit them. Scheduling the script as it then stood would have deleted all eight on the
    first Monday, and build.py falls back with r.get("name_sv", r["name"]), so the Swedish
    sheet, one-pager and social card would have published English bar labels with nothing
    raised anywhere. The labels now live in the generator; this assert is what keeps them
    there, since the failure it guards against is invisible on the page.

    The year assert runs the other way from every other gate in this file. The others let the
    year advance, because catching a new wave is what they are for. A new barrier wave is not
    that: the question's routing changed between 2021, asked of all non-adopters (3,425 firms
    answered), and 2023, gated on E_AI_EC == 1, considered AI but did not adopt (482 firms),
    and Eurostat flags every Swedish 2023 cell as a break in series. Two waves can therefore
    describe two different universes while looking like one series, which is a reading rather
    than a pull. Re-pulling within a wave stays automatic; crossing into a new one stops the
    run and asks for a person.
    """
    rows = d["rows"]
    assert len(rows) == 8, f"{len(rows)} reasons, Eurostat's question carries eight"
    assert all(pct_ok(r.get("share")) and pct_ok(r.get("eu")) for r in rows), \
        "barrier share outside 0-100"
    assert all(r.get("is_se") for r in rows), "rows are no longer the Swedish column"
    unlabelled = [r["name"] for r in rows if not r.get("name_sv")]
    assert not unlabelled, (
        "no Swedish label on: " + "; ".join(unlabelled)
        + ". build.py falls back to the English name, so the Swedish sheet, one-pager and "
          "social card would go out with English bar labels and no error. Restore LABELS_SV "
          "in scripts/refresh_barriers.py.")
    y = int(d["meta"]["year"])
    assert y == prev_year, (
        f"the barrier wave year changed from {prev_year} to {y}, which this run will not "
        "publish unread: the question's routing changed between waves (2021 asked all "
        "non-adopters, 3,425 firms; 2023 gated on E_AI_EC == 1, considered AI but did not "
        "adopt, 482 firms), and Eurostat flags the Swedish 2023 cells as a break in "
        "series, so a new "
        f"wave need not describe the same universe as {prev_year}. Read the status block for "
        f"SE in isoc_eb_ain2 {y}, decide whether the two waves are comparable, then set the "
        "year and update the docstring in scripts/refresh_barriers.py by hand.")


def check_population(d, prev_year):
    """SCB LE0108T82, the population level of the Adoption module.

    The source line is asserted for the same reason name_sv is asserted above. The committed
    file carried an English gloss, "/ ICT use among the population", added on 28 Jul 2026 when
    the Swedish source names were glossed for the English edition, and this generator emitted
    the bare Swedish table name instead. build.py prints the string verbatim in the figure
    footer of both editions, so losing it leaves an English-language reader with a Swedish
    table name and nothing else.

    The year may advance here. The survey year is read off the API rather than fixed in the
    script, and SCB flags no break on T82, so a new wave is exactly what the schedule is for.
    """
    m = d["meta"]
    ages = d["by_age"]
    assert len(ages) >= 5, f"only {len(ages)} age groups (SCB publishes six)"
    assert all(pct_ok(r.get("adoption")) and pct_ok(r.get("prev")) for r in ages), \
        "population share outside 0-100"
    assert all(pct_ok(m.get(k)) for k in ("headline", "headline_first", "men", "women")), \
        "headline or sex split outside 0-100"
    shares = (d.get("purpose_latest") or {}).get("shares") or []
    assert shares, "the purpose block is empty"
    assert all(pct_ok(s.get("pct")) for s in shares), "purpose share outside 0-100"
    assert "ICT use among the population" in m["source"], (
        f"the English gloss is gone from the source line ({m['source']!r}), which the figure "
        "footer prints verbatim on both editions. Restore it in "
        "scripts/refresh_population_ai.py.")
    y = int(m["year"])
    assert prev_year <= y <= prev_year + 5, f"survey wave went from {prev_year} to {y}"


JOBS = [
    ("refresh_cross_country.py", "data/cross_country_adoption.yaml", check_adoption),
    ("refresh_swe_adoption.py", "data/swe_adoption.yaml", check_swe),
    ("refresh_capability.py", "data/capability.yaml", check_capability),
    ("refresh_barriers.py", "data/barriers.yaml", check_barriers),
    ("refresh_population_ai.py", "data/population_ai.yaml", check_population),
]


def main():
    failed = []
    for script, target, gate in JOBS:
        prev_year = int(load(target)["meta"]["year"])   # before the pull; each gate rules on the year
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
