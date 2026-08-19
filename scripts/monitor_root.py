"""Where the ai-monitor working tree is. Import this; never hardcode the path again.

Nine refresh scripts each opened their source file at

    Path.home() / "Documents/Workspace/lab-infrastructure/ai-monitor" / ...

which is one particular laptop. The consequence was structural rather than cosmetic: those
nine modules are every job-ads figure the Monitor publishes -- the monthly series, occupations
and their tiers, wages, vocabulary, job quality, working conditions, the entry-level squeeze,
governance -- and none of them could run on a GitHub runner, where `$HOME` holds no Workspace.
So the weekly Action refreshed the three sources that happened to be pure API pulls (Eurostat,
SCB, Epoch) and silently could not touch the other nine, and the site's Swedish half moved
only when Magnus ran a script by hand. Between 13 and 17 August 2026 it did not move at all,
while the daily poll ingested advertisements every one of those days.

$AI_MONITOR_ROOT overrides; the old path stays the default, so a laptop run needs no
environment and behaves exactly as before.
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_ROOT = Path.home() / "Documents/Workspace/lab-infrastructure/ai-monitor"


def monitor_root() -> Path:
    """The ai-monitor checkout, from $AI_MONITOR_ROOT or the usual local path.

    Fails with the fix in the message rather than a bare FileNotFoundError three frames
    later on a path the reader has to reverse-engineer.
    """
    raw = os.environ.get("AI_MONITOR_ROOT")
    root = Path(raw).expanduser() if raw else DEFAULT_ROOT
    if not root.is_dir():
        raise SystemExit(
            f"ai-monitor checkout not found at {root}\n"
            + (f"  ($AI_MONITOR_ROOT is set to {raw!r})\n" if raw else
               "  (no $AI_MONITOR_ROOT set, so the default local path was used)\n")
            + "Set AI_MONITOR_ROOT to the ai-econ-lab/labour-market-monitor checkout.")
    return root


def __getattr__(name):
    """Resolve MONITOR_ROOT on first use, not at import.

    The definition constants below live in this module too, and build.py imports ONLY those:
    it never opens the ai-monitor tree. Resolving the checkout at import time therefore made
    build.py refuse to run wherever that tree is absent, which is every GitHub runner --
    the "site data refresh" job died on 19 Aug 2026 at `python3 build.py`, one day after the
    constants moved here. A module must not demand what its importer does not use.
    """
    if name == "MONITOR_ROOT":
        return monitor_root()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ── the frozen definition, in ONE place ──────────────────────────────────────────────
# build.py already carried DEF_VERSION/DEF_FP with a comment explaining that five figure
# footers and two CSV exports had each held their own "frozen v1.2" literal, so a re-freeze
# meant finding all seven and the Monitor served a mix until someone did. The fix was made in
# build.py only, and four literals survived outside it: two figure footers reached v1.4 while
# occupations.yaml, the one-pager's source line and refresh_occupations.py still said v1.3.
# So the same defect recurred at the next freeze, one layer out. It lives here now, where both
# build.py and the refresh scripts can import it.
DEF_VERSION = "v1.4"
DEF_FP = "0bebeebaf6ffea26"
DEF_LABEL = f"frozen {DEF_VERSION} term list"


def bulk_dir() -> str:
    """The derived-series directory matching DEF_VERSION, e.g. 'bulk_v14'.

    Derived rather than typed for the same reason: a refresh script pointed at the previous
    freeze's directory reads a series the site no longer claims to publish, and nothing in the
    output says so.
    """
    return "bulk_v" + DEF_VERSION.lstrip("v").replace(".", "")
