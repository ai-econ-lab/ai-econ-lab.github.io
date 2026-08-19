#!/usr/bin/env python3
"""Fail when the ai-monitor repository has stopped pushing data refreshes into this one.

    python3 scripts/check_upstream_alive.py

WHY THIS EXISTS, AND WHY IT IS SHAPED LIKE THIS. The job-ads half of the Monitor is pushed
here daily by "site data refresh", which lives in ai-econ-lab/labour-market-monitor because
that repository is private and may hold a deploy key for this public one, never the reverse
(site-refresh.yml sets out that direction rule at length).

That leaves this repository unable to read the upstream's workflow runs: doing so would need a
token for a private repository, stored in a public one, which is the arrangement the rule
exists to forbid. So this checks the upstream's EFFECT instead of its state. A refresh commit
arriving here is proof the upstream ran, and it needs no credential at all: this repository is
public and its own commit list is public.

The failure this catches is the silent one. A job that runs and fails goes red and emails; a
job that stops running produces nothing. If the upstream's schedule is disabled, its cron is
edited wrong, its deploy key expires, or GitHub suspends its schedules for inactivity, the
first and only symptom is that the site quietly stops moving -- which is precisely what
happened between 13 and 17 August 2026, and again on the 18th and 19th, unnoticed both times.

The upstream runs the mirror of this check (scripts/check_schedules.py over there), which
watches this repository's workflows. Each side watches the other, because a watchdog that only
watches others has nobody to notice its own silence.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = "ai-econ-lab/ai-econ-lab.github.io"

# The refresh commits are identified by their MESSAGE, not by an author filter. The upstream
# sets `git config user.name "aiel-monitor[bot]"`, which is a git author name and not a GitHub
# account, so ?author=aiel-monitor[bot] matches nothing and the first version of this file
# reported "no commit has ever reached this repository" while several sat in the log. A check
# that always fails gets muted exactly as fast as one that never fires.
MARKER = "Site data refresh from ai-monitor"
BOT_NAME = "aiel-monitor[bot]"
SCAN = 100          # commits to look back through; the refresh is daily, this is months

# The upstream refresh is daily. Two days is one missed run plus a late queue; three misses in
# a row is not weather. Kept generous on purpose: a watchdog that cries on an ordinary Tuesday
# gets muted, and a muted watchdog is worse than none.
MAX_SILENCE = timedelta(days=3)


def main() -> int:
    url = f"https://api.github.com/repos/{REPO}/commits?per_page={SCAN}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "aiel-site-upstream-check",
    })
    # Public repository, so no token is required. One is used when present only to stay clear
    # of the unauthenticated rate limit on a busy runner.
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            commits = json.load(r)
    except (urllib.error.URLError, TimeoutError) as e:
        # Not a finding about the upstream: say so rather than reporting it as dead.
        print(f"check_upstream_alive: cannot reach the API ({e}); skipped.")
        return 0

    refreshes = [c for c in commits
                 if c["commit"]["message"].startswith(MARKER)
                 or c["commit"]["author"]["name"] == BOT_NAME]

    if not refreshes:
        print(f"FAIL. No data refresh from ai-monitor in the last {SCAN} commits to {REPO}.\n"
              f"  The daily 'site data refresh' in ai-econ-lab/labour-market-monitor is what\n"
              f"  pushes them. Check that it is enabled and that SITE_DEPLOY_KEY is set.")
        return 1

    when = datetime.fromisoformat(
        refreshes[0]["commit"]["committer"]["date"].replace("Z", "+00:00"))
    age = datetime.now(timezone.utc) - when
    stamp = when.strftime("%Y-%m-%d %H:%M UTC")

    if age > MAX_SILENCE:
        print(f"FAIL. The last data refresh from ai-monitor landed {stamp}, "
              f"{age.days} days ago (limit {MAX_SILENCE.days}).\n"
              f"  That job is daily. It is not merely failing -- a failing run emails; this is\n"
              f"  the case where nothing runs at all and nothing says so. Check, in\n"
              f"  ai-econ-lab/labour-market-monitor: the Actions tab for a disabled workflow,\n"
              f"  the cron line in site-refresh.yml, SITE_DEPLOY_KEY, and whether the\n"
              f"  repository has been idle long enough for GitHub to suspend its schedules.")
        return 1

    print(f"OK. Last refresh from ai-monitor: {stamp} ({age.days}d {age.seconds // 3600}h ago, "
          f"limit {MAX_SILENCE.days}d).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
