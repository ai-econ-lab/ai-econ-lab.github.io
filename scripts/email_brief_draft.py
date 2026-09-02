#!/usr/bin/env python3
"""Monthly AIEL Monitor Brief draft, emailed to Magnus for review two weeks ahead.

Run by .github/workflows/monthly-brief-draft.yml in the month-end window (and manually). Builds NEXT
month's brief (both languages) via build.py's BRIEF_MONTH_OVERRIDE, extracts the readable
text, and emails it to Magnus over Gmail SMTP using the GMAIL_APP_PASSWORD repo secret.
Nothing is published — Magnus reviews, replies "go", and the issue is posted to Substack.

STANDING SUBSTACK SETTINGS FOR EVERY ISSUE (decided 2 Sep 2026, do not re-litigate monthly).
Substack does not offer a publication-wide default for either of these, so both are chosen in
the publish dialog on each post and both default back to the wrong value:

  * Allow comments from ... -> "No one (disable comments)". Substack defaults to Everyone.
    A comment thread is a moderation duty nobody at the lab is going to carry, and the brief
    is a closed argument whose limits are stated inside the issue. Feedback goes to e-mail;
    the route is on the lab's contact page. Do NOT reach for the publication-wide toggle in
    Settings -> Community instead: that one switch kills comments, likes AND restacks, and
    restacks are how a post travels beyond our own list.

  * Delivery "Send via email and the Substack app" -> unchecked, while the comms hold stands
    (briefs publish but are not promoted until the joint launch with the Oskar and Leo
    report). Substack both pre-checks this and asks a second time after you uncheck it.

STANDING CLOSING BLOCK FOR EVERY ISSUE (added 2 Sep 2026). The Substack post is typed by hand
and drifted from the page: the August issue promised "Subscribers can reply to any issue by
email", which cannot be true while delivery is unchecked, and it predated the institution and
funder line. Both were corrected on the live August post. Every issue now ends with these two
paragraphs, matching the page footer:

    AI-Econ Lab . AIEL Monitor . YYYY-MM. Public data; cite the version and date. The full
    Monitor is at ai-econlab.com/monitor. Feedback is welcome at ai-econlab.com/about/#contact.

    Orebro University and RATIO. Orebro is one of AISCAF's three nodes; the cluster, financed
    by WASP-HS, funds part of the lab's team.

The feedback route is the contact page, never "reply to this email": with delivery unchecked
there is no e-mail to reply to.
"""
import os, re, html, json, smtplib, subprocess, calendar
from datetime import date
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TO = FROM = "mlodefalk@gmail.com"

# --- day guard ---
# The workflow fires DAILY rather than monthly, and this guard decides whether to
# proceed. That inversion is deliberate: GitHub drops rare cron schedules under load,
# and on 28 Jul 2026 the monthly `0 7 28 * *` schedule simply never ran. A missed
# monthly fire is expensive here, because the next one is a month later, by which
# time the issue it was drafting has already published. A daily run costs ~16s and
# exits immediately on 30 days out of 31.
# Firing on one nominated day is still one point of failure: on 27 Aug 2026 GitHub dropped
# every scheduled run in both repositories for a day, which on the 28th would have cost the
# September issue outright. So the window is the last three days of the month and the send
# is deduplicated on the month being drafted, exactly the shape the seminar reminder uses
# (three chances, sent_log.json). The first day that fires does the work; the rest see the
# month already logged and exit. Short months keep three chances because the window is
# measured back from the month's end, so February opens on the 26th rather than losing two.
TARGET_DAY = 28
SENT_LOG = ROOT / ".github" / "brief_sent.json"

t = date.today()
_last_day = calendar.monthrange(t.year, t.month)[1]
_window_opens = min(TARGET_DAY, _last_day - 2)
# Set by the workflow from its `force` input, never from the event name: see the comment
# on BRIEF_FORCE there. A watchdog dispatch must still respect the window.
_forced = os.environ.get("BRIEF_FORCE") == "1"

# The month this run would draft, which is the deduplication key. Stable across every day
# of the window, so the 29th knows the 28th already did the work.
_ny, _nm = (t.year + 1, 1) if t.month == 12 else (t.year, t.month + 1)
TARGET_MONTH = f"{_ny}-{_nm:02d}"


def _sent_months():
    try:
        return json.loads(SENT_LOG.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return []


if not _forced:
    if t.day < _window_opens:
        print(f"Window opens on the {_window_opens}th (today is the {t.day}), nothing to draft.")
        raise SystemExit(0)
    if TARGET_MONTH in _sent_months():
        print(f"The {TARGET_MONTH} draft already went out this window, nothing to do.")
        raise SystemExit(0)

# --- next month (roll Dec -> Jan) ---
ny, nm = (t.year + 1, 1) if t.month == 12 else (t.year, t.month + 1)
mname = calendar.month_name[nm]
override = f"{ny}-{nm:02d}"

# --- build next month's brief (EN + SV) ---
env = {**os.environ, "BRIEF_MONTH_OVERRIDE": override}
subprocess.run(["python3", "build.py"], cwd=ROOT, env=env, check=True)


def brief_text(rel):
    s = (ROOT / rel).read_text(encoding="utf-8")
    m = re.search(r'<article class="briefsheet">(.*?)</article>', s, re.S)
    s = m.group(1) if m else s
    s = re.sub(r"<svg.*?</svg>", " [chart] ", s, flags=re.S)      # drop chart internals
    s = re.sub(r"<[^>]+>", " ", s)                                # strip remaining tags
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return s.strip()


en = brief_text("docs/monitor/brief/index.html")
sv = brief_text("docs/monitor/brief/sv/index.html")
bar = "=" * 60

body = f"""Draft of the AIEL Monitor Brief for {mname} {ny}, for your review before publication.

Auto-generated by the monthly GitHub Action. Read both versions; reply "go" (or with edits)
and Claude will publish it to Substack. Nothing is published automatically.

{bar}
ENGLISH
{bar}
{en}

{bar}
SVENSKA
{bar}
{sv}

{bar}
CHECK BEFORE PUBLISHING
{bar}
- Are the headline numbers current? (Some sources refresh on their own cadence.)
- Issue-1 content candidates from the 24 Jul 2026 rebuild (20-year arc / genAI share /
  title newcomers): lab-infrastructure/ai-monitor/notes/brief-issue1-content-candidates_2026-07-24.md
- Does this month's in-focus theme have its own chart yet, or is it using a placeholder?
  (See data/brief_calendar.yaml; themes leaning on Akavia need that source live.)
- Read the Swedish closely and flag anything that reads translated.
- Lab news at the bottom: still accurate, anything to add?

Live format reference: https://ai-econ-lab.github.io/monitor/brief/ (EN) and /sv/ (SV).
"""

msg = MIMEText(body, "plain", "utf-8")
msg["Subject"] = f"AIEL Monitor Brief draft — {mname} {ny} (for review)"
msg["From"], msg["To"] = FROM, TO

pw = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")   # app passwords display with spaces
with smtplib.SMTP("smtp.gmail.com", 587, timeout=60) as s:
    s.starttls()
    s.login(FROM, pw)
    s.send_message(msg)
print(f"Sent {mname} {ny} draft to {TO} ({len(en)} EN chars, {len(sv)} SV chars).")

# Written only after the SMTP send returned, so a failed send leaves the window open and
# tomorrow tries again. The workflow commits this file; it is state, not site content,
# which is why it sits beside the workflow rather than in data/.
_log = _sent_months()
if TARGET_MONTH not in _log:
    _log.append(TARGET_MONTH)
    SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    SENT_LOG.write_text(json.dumps(_log[-24:], indent=2) + "\n", encoding="utf-8")
    print(f"Logged {TARGET_MONTH} in {SENT_LOG.relative_to(ROOT)}.")
