#!/usr/bin/env python3
"""
check_vintages.py -- every published module must name the definition it was really built from.

WHY THIS EXISTS. On 19 August 2026 the Monitor moved to v1.5. Flipping DEF_VERSION moved two
of the ten monitor-derived modules; the other eight read cuts of their own, and one of them,
the monthly block, was still built from an older bulk. The site nonetheless stamped "frozen
v1.5" on its footer, because the footer is generated from DEF_VERSION rather than from
anything the data knows about itself. Nothing in either repository could notice.

The same defect had already happened twice in other clothes: the vocabulary chart said
"frozen v1.1" for a day while its composition was v1.4, and the ceiling correction was
measured on a v1 band and applied to a v1.3 ceiling for ten days.

WHAT IT CHECKS. For each module, the definition it CLAIMS in its own source line, against the
definition its input actually carries. Two directions, treated differently:

  OVER-CLAIMING  the module says a newer definition than its data. This FAILS. It is the
                 direction that misleads a reader, and it is what happened on 19 August.
  LAGGING        the module says an older definition than the site's current one, truthfully.
                 This PASSES and is listed. A module may legitimately lag a freeze; what it
                 may not do is hide it.

Modules whose input carries no provenance file declare their vintage here, in DECLARED. That
list is meant to be short and to shrink: a module that writes a provenance sidecar can move to
PROVENANCE and be checked against reality instead of against a promise.

Run:  python3 scripts/check_vintages.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from monitor_root import MONITOR_ROOT, DEF_VERSION, bulk_dir  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# module yaml -> path to a provenance file in the monitor repo, relative to its root.
PROVENANCE = {
    "occupations.yaml":   f"data/{bulk_dir()}/derived/_derived_manifest.json",
    "monthly_demand.yaml": "data/free_cuts/monthly_ai_share_v11.provenance.json",
    "vocabulary.yaml":    "data/candidates/_extract_definition.json",
}

# module yaml -> (declared definition, why it is not checked against a file).
DECLARED = {
    "governance.yaml":          ("v1.2", "refresh_governance.py reads data/bulk_v12 by design."),
    "occupation_tiers.yaml":    ("v1.1", "free_cuts/tier_by_occupation.csv, from the tier classification."),
    "job_quality.yaml":         ("v1.1", "build_job_quality_v11.py reads data/bulk_v11."),
    "entry_level_squeeze.yaml": ("v1.1", "data/entry_level_squeeze.csv, on JobTech API record counts."),
}

CLAIM = re.compile(r"frozen (v\d+(?:\.\d+)?)")


def version_key(v: str) -> tuple:
    return tuple(int(x) for x in v.lstrip("v").split("."))


def claimed(path: Path) -> str | None:
    m = CLAIM.search(path.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def actual_from_provenance(rel: str) -> str | None:
    p = MONITOR_ROOT / rel
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    text = d.get("definition") or d.get("version") or ""
    m = re.match(r"(v\d+(?:\.\d+)?)", str(text))
    return m.group(1) if m else None


def untracked_inputs() -> list[str]:
    """Files the site reads that exist on this disk but are not in the monitor repository.

    THE FAILURE THIS CATCHES. On 19 August the site was pointed at bulk_v15 and every local
    build worked, because the directory was on the machine that produced it. It had never been
    committed, so every CI run failed on a missing series_ssyk4.csv, and the only signal was a
    nightly mail. A check that reads the local filesystem cannot see this; it has to ask git.
    """
    wanted = [f"data/{bulk_dir()}/derived/series_annual.csv",
              f"data/{bulk_dir()}/derived/series_ssyk4.csv",
              f"data/{bulk_dir()}/derived/_derived_manifest.json",
              "data/free_cuts/monthly_ai_share_v11.csv",
              "data/free_cuts/monthly_ai_share_v11.provenance.json",
              "data/diagnostics/term_composition.csv"]
    try:
        out = subprocess.run(["git", "-C", str(MONITOR_ROOT), "ls-files", "--", *wanted],
                             capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return []
    tracked = set(out.stdout.split())
    return [w for w in wanted if w not in tracked]


def main() -> int:
    problems, lagging, unstamped = [], [], []

    for miss in untracked_inputs():
        problems.append(f"{miss} is NOT COMMITTED in the monitor repository. It may exist on "
                        f"this machine; CI checks out the repository, so the refresh will fail "
                        f"there and only there.")

    for name, rel in sorted(PROVENANCE.items()):
        f = DATA / name
        if not f.exists():
            problems.append(f"{name}: missing")
            continue
        says, is_ = claimed(f), actual_from_provenance(rel)
        if is_ is None:
            problems.append(f"{name}: no provenance at {rel}. Rebuild it, or move it to DECLARED "
                            f"with a reason.")
            continue
        if says is None:
            unstamped.append(name)
            continue
        if version_key(says) > version_key(is_):
            problems.append(f"{name}: claims {says} but its input is {is_} ({rel}). "
                            f"OVER-CLAIMING: the page tells the reader a definition the data "
                            f"has not been through.")
        elif version_key(says) < version_key(DEF_VERSION):
            lagging.append(f"{name}: {says}, honestly ({rel})")
        print(f"  {'ok' if says == is_ else '..':4} {name:26} claims {says}, built from {is_}")

    for name, (declared, why) in sorted(DECLARED.items()):
        f = DATA / name
        if not f.exists():
            problems.append(f"{name}: missing")
            continue
        says = claimed(f)
        if says and version_key(says) > version_key(declared):
            problems.append(f"{name}: claims {says}, declared {declared}. {why}")
        elif version_key(declared) < version_key(DEF_VERSION):
            lagging.append(f"{name}: {declared}, declared ({why})")
        print(f"  {'ok' if says else '--':4} {name:26} declared {declared}")

    if problems:
        print("\nFAIL. A published module names a definition its data has not been through:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"\nOK. No module over-claims. Site definition is {DEF_VERSION}.")
    if unstamped:
        print(f"  {len(unstamped)} module(s) carry no 'frozen vX' line: {', '.join(unstamped)}")
    if lagging:
        print(f"\n  {len(lagging)} module(s) lag {DEF_VERSION}, which is allowed and stated on the page:")
        for l in lagging:
            print(f"  - {l}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
