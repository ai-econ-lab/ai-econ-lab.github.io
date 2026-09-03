#!/usr/bin/env python3
"""
AI-Econ Lab — static site builder.

Reads data/*.yaml, renders self-contained HTML into docs/ (what GitHub Pages
serves), and writes sitemap.xml, robots.txt, CNAME and .nojekyll. No template
engine and no third-party deps beyond PyYAML — so it runs the same on your Mac
and in CI. Edit the YAML, run `python3 build.py`, commit, push.
"""
from pathlib import Path
import shutil, sys, yaml, html, re, unicodedata, hashlib, datetime, json

ROOT = Path(__file__).parent
DATA = ROOT / "data"
def load(name): return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))

# ── the frozen definition, in ONE place ──────────────────────────────────────
# Five figure footers and two CSV exports each carried their own "frozen v1.2" literal, so a
# re-freeze meant finding all seven and the monitor served a mix until someone did. Twice it
# was missed. Keep the version and its fingerprint here and interpolate; methods.yaml remains
# the citable record, this is only the label the figures wear.
sys.path.insert(0, str(ROOT / "scripts"))
from monitor_root import DEF_VERSION, DEF_FP, DEF_LABEL  # noqa: E402
from labels import MAX_LABEL_CHARS, shorten  # noqa: E402

# ── data freshness ───────────────────────────────────────────────────────────
# The masthead strip carries an UPDATED stamp next to a "● LIVE" badge, so it has
# to mean the DATA, not the prose. It is derived here rather than typed into
# site.yaml, because a hand-maintained date silently drifts behind the content
# (it sat at 2026-07-21 while eight commits of new data landed on the 22nd).
#
# Only the files that actually carry numbers count. Editing a person's title or
# adding a news item is not a data refresh and must not move this date.
DATA_FILES = [
    "monitor.yaml", "cross_country.yaml", "cross_country_adoption.yaml",
    "cross_country_demand.yaml", "swe_adoption.yaml", "swe_adoption_sector.yaml", "demand_by_sector.yaml",
    "nordic_adoption_size.yaml",
    "daioe_exposure.yaml",
    "entry_level_squeeze.yaml", "working_conditions.yaml", "akavia.yaml",
    "us_adoption_rps.yaml", "population_ai.yaml", "wages.yaml",
    "occupations.yaml", "occupation_tiers.yaml", "barriers.yaml",
    "monthly_demand.yaml", "job_quality.yaml", "governance.yaml",
    "vocabulary.yaml", "capability.yaml",
]

def data_updated():
    """Date the newest of the numeric data files last CHANGED, as YYYY-MM-DD.

    Uses the git commit date, not the filesystem mtime: a fresh clone or a branch
    switch rewrites every mtime, which would make the site claim a refresh that
    never happened. Falls back to mtime only when git is unavailable (and the
    caller should treat that as a soft signal).

    Note this is 'when the series behind the figures last moved', which is a
    different and weaker claim than 'the data are current as of this date'. The
    per-figure `foot:` vintages carry that stronger claim, source by source.
    """
    import subprocess
    present = [f for f in DATA_FILES if (DATA / f).exists()]
    paths = [f"data/{f}" for f in present]

    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=10, check=True).stdout

    try:
        # docs/ is built locally and committed, so build.py always runs BEFORE the
        # commit that carries the data change. An uncommitted edit to a data file
        # therefore means the data moved today, and git log would report the
        # previous refresh -- always one behind.
        if git("status", "--porcelain", "--", *paths).strip():
            return datetime.date.today().isoformat()
        out = git("log", "-1", "--format=%cs", "--", *paths).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", out):
            return out
    except Exception:
        pass
    newest = max((DATA / f).stat().st_mtime for f in present)
    return datetime.date.fromtimestamp(newest).isoformat()

DATA_UPDATED = data_updated()

MONTHS = ("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")
def display_date(iso):
    """'2026-07-22' -> '22 Jul 2026': day-month-year with the month in letters, the
    unambiguous format for an international audience (the all-caps strip renders it
    22 JUL 2026). ISO stays in machine-readable places; this is for copy humans read."""
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month-1]} {d.year}"
DATA_UPDATED_DISPLAY = display_date(DATA_UPDATED)

def sources_checked():
    """Date the weekly source sweep last RAN, or None if the record is missing.

    A different fact from DATA_UPDATED, and the strip needs both. DATA_UPDATED is when a
    series last MOVED; this is when the sources were last ASKED. They come apart exactly when
    the sweep is working and the world is quiet: on 24 Aug 2026 every source was fetched at
    05:17 UTC, all five refreshers returned ok, the run printed "changed: nothing" because
    none of them had published anything new, and the front page went on saying "DATA UPDATED
    20 Aug 2026 - SOURCES CHECKED WEEKLY". Read together those two clauses say the site is
    four days behind, which is the opposite of what had happened.

    Written by scripts/weekly_refresh.py into the watcher's state file, and only from CI, for
    the reason at CI_OWNS_STATE in refresh_capability.py. Absent is normal and not an error:
    the key does not exist until the first sweep after this was added, and a clone that has
    never run one has nothing to report. The caller falls back to the old, weaker wording.
    """
    f = ROOT / "scripts" / "watch_state.json"
    try:
        v = json.loads(f.read_text(encoding="utf-8")).get("sources_checked")
        return v if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else None
    except (OSError, json.JSONDecodeError):
        return None

SOURCES_CHECKED = sources_checked()
# "WEEKLY" is the honest fallback: it is what the strip claimed before the date existed, and
# it stays true whether or not this particular checkout has a record of the last sweep.
SOURCES_CHECKED_DISPLAY = display_date(SOURCES_CHECKED) if SOURCES_CHECKED else "WEEKLY"

SITE     = load("site.yaml")
PAPERS   = load("papers.yaml")
PEOPLE   = load("people.yaml")
MONITOR  = load("monitor.yaml")
DAIOE    = load("daioe.yaml")
SEMINARS = load("seminars.yaml")
DAIOE_EXP = load("daioe_exposure.yaml")
NEWS     = load("news.yaml")
WAGES    = load("wages.yaml")
OCCUP    = load("occupations.yaml")
OCCTIER  = load("occupation_tiers.yaml")
MONTHLY  = load("monthly_demand.yaml")
# The trend is generated (scripts/refresh_trend.py) rather than typed into monitor.yaml,
# and it carries the definition it was built from. See that script for why.
TREND    = load("trend.yaml")

JOBQ     = load("job_quality.yaml")
GOV      = load("governance.yaml")
VOCAB    = load("vocabulary.yaml")
BARRIERS = load("barriers.yaml")
CROSS    = load("cross_country.yaml")
ADOPT    = load("cross_country_adoption.yaml")
DEMAND   = load("cross_country_demand.yaml")
WORKCOND = load("working_conditions.yaml")

# ── the live window, and whether it is still live ────────────────────────────
# data/livewindow.yaml is written by scripts/refresh_livewindow.py from the JobStream store
# and is the preferred source. monitor.yaml's block is the fallback and the last figures that
# were placed by hand; it carries the framing prose either way.
#
# THE BADGE IS DERIVED, because the alternative was tested and failed. site.yaml carried a
# literal "● LIVE" and monitor.yaml a hand-typed `asof`, and on 17 Aug 2026 the site showed
# "● LIVE" beside a window stamped five days earlier, while the daily poll had ingested ads
# every one of those days. Both statements were separately defensible and the pair was not.
# A badge that cannot go out means nothing when it is on.
LIVEWINDOW = dict(MONITOR.get("livewindow") or {})
try:
    LIVEWINDOW.update(load("livewindow.yaml") or {})
except FileNotFoundError:
    pass

def _livewindow_age():
    """Days since the live window's as-of date, or None if it cannot be read."""
    iso = LIVEWINDOW.get("asof_iso")
    try:
        d = (datetime.date.fromisoformat(str(iso)) if iso
             else datetime.datetime.strptime(LIVEWINDOW["asof"], "%d %b %Y").date())
    except (KeyError, ValueError, TypeError):
        return None
    return (datetime.date.today() - d).days

LIVEWINDOW_AGE = _livewindow_age()
# Two days: the poll runs daily at 04:17 UTC and JobStream publishes on the day, so a window
# one day behind is normal operation and two is a single missed run. Three means the feed,
# the emit step or the push has been down since before yesterday, which is a fact about the
# site and not about the labour market.
LIVE_OK = LIVEWINDOW_AGE is not None and LIVEWINDOW_AGE <= 2
# The strip carries THREE clocks and they legitimately differ: the weekly source sweep, the
# date a stamped series last moved, and the daily job-ads window. Until 27 Aug 2026 only the
# first two were dated and the fastest showed as a bare "● LIVE", so a reader comparing
# "SOURCES CHECKED 24 Aug · SERIES LAST MOVED 25 Aug" against today's date saw a site three
# days stale and had nothing on the strip to correct the impression. Magnus read it exactly
# that way twice: on 24 Aug, which is why SOURCES CHECKED gained a date at all, and again on
# 27 Aug, when both dated clocks were correct and the undated one was the current one.
# Dating the badge closes the class rather than the instance: every clock on the strip now
# says when it last moved, so no pair of them can imply staleness the third disproves.
_LW_ASOF = str(LIVEWINDOW.get("asof") or "").strip()
_LW_SUFFIX = f" {_LW_ASOF}" if _LW_ASOF else ""
LIVE_STATUS = (f'<span class="lv">● LIVE FEED{_LW_SUFFIX} · PUBLIC + PARTNER DATA</span>' if LIVE_OK else
               f'<span class="lv stale">◌ FEED DELAYED · WINDOW{_LW_SUFFIX} · PUBLIC + PARTNER DATA</span>')

# Every count the site states about its own corpus and coverage, derived from the file that
# holds it. Typed counts cannot contradict their data anywhere a build can notice, which is
# how the monthly series came to say 16,113,466 while the masthead said 8.1M (13 Aug 2026).
DISTINCT_ADS = f"{MONTHLY['meta']['total_ads'] / 1e6:.1f}M"
RECORD_ADS   = f"{MONTHLY['meta']['total_records'] / 1e6:.1f}M"
N_COUNTRIES  = CROSS['meta']['n_countries']
# The occupation explorer plots assets/daioe_occupations.json, so the count comes from there.
N_OCCUPATIONS = len(json.loads((ROOT / 'assets' / 'daioe_occupations.json')
                              .read_text(encoding='utf-8'))['occ'])

AKAVIA   = load("akavia.yaml")
RELATED  = load("related_research.yaml")
METHODS  = load("methods.yaml")
CAPABILITY = (load("capability.yaml") if (DATA / "capability.yaml").exists()
              else MONITOR["capability"])
ELS      = load("entry_level_squeeze.yaml")
SWEAD    = load("swe_adoption.yaml")
SWESEC   = load("swe_adoption_sector.yaml")   # sibling cut: same table, by industry
DEMSEC   = load("demand_by_sector.yaml")      # OUR ad series on SCB's industry groups
NORDSZ   = load("nordic_adoption_size.yaml")  # the one depth cut that goes Nordic
USRPS    = load("us_adoption_rps.yaml")
POPAI    = load("population_ai.yaml")
# The occupation-search data lives in assets/daioe_occupations.json and is fetched at runtime
# (see app.js occSearch), so it is NOT embedded here. It auto-tracks the latest DAIOE year.

OUT = ROOT / SITE["build"]["out"]
BASE = SITE["brand"]["base_url"].rstrip("/")
h = lambda s: html.escape(str(s), quote=True)   # escape plain-text (titles, names)

def num_html(s):
    """Escape a tile's headline value, keeping only the one bit of markup it may carry.

    Tile values follow a presentational convention: a <span> wraps the unit, so
    "30<span>% of human level</span>" sets the unit smaller than the figure. Everything else
    in the string is data, and capability.yaml is written by refresh_capability.py out of
    external APIs, so it cannot be trusted to be markup-safe.

    The two failure modes are symmetric and both have shipped. Emitting num raw, as the
    overview and monitor tiles did, makes an API field an injection path. Escaping it
    wholesale, as the capability tiles did, printed "30<span>% of human level</span>" on the
    public page as literal text. So: escape everything, then restore the span wrapper alone.
    """
    return (h(s).replace("&lt;span&gt;", "<span>").replace("&lt;/span&gt;", "</span>"))

# Prose helper: escape text but turn [label](url) into a link (for about paragraphs etc.).
_MDLINK = re.compile(r'\[([^\]]+)\]\((https?://[^)\s]+)\)')
def linkify(s):
    out, i = [], 0
    for m in _MDLINK.finditer(s):
        out.append(h(s[i:m.start()]))
        out.append(f'<a href="{h(m.group(2))}">{h(m.group(1))}</a>')
        i = m.end()
    out.append(h(s[i:]))
    return "".join(out)

# Anti-spam e-mail: return (user, domain, obfuscated-display). Rendered with data-attrs;
# app.js assembles a real mailto at runtime so scrapers never see a live address.
def email_bits(addr):
    u, d = addr.split("@")
    return u, d, f'{u} (at) {d.replace(".", " (dot) ")}'

def assetv(rel):   # cache-busting token for a file under the repo root
    p = ROOT / rel
    return hashlib.md5(p.read_bytes()).hexdigest()[:8] if p.exists() else "0"

# ── shared chrome ────────────────────────────────────────────────────────────
def sheet_pair(label="The whole picture, 2 pages (PDF)"):
    """The two-page sheet, with the language as a subordinate choice.

    Two failed designs are worth recording, because both got the hierarchy wrong.

    First, Lydia's review asked for the Swedish edition to be reachable from both "whole
    picture" buttons, and it was: as a second ghost button reading "svenska (PDF)". Two
    adjacent buttons of equal weight read as two different downloads, so the Swedish edition
    looked like an afterthought bolted onto the English one.

    Second, a segmented English/Swedish control fixed that and broke something worse. It made
    the LANGUAGE PICKER the prominent object and demoted the sheet itself to small grey label
    text, so the page shouted the least interesting decision on it. Magnus, 12 Aug: "the whole
    picture is super important but is like hidden while English and Svenska is really large".

    The sheet is the offer, so the sheet is the button. The language is a detail, so it is
    small text beneath, with the current one marked and not a link. "Swedish", not "Svenska":
    this is an English page, the same rule that governs the occupation names.
    """
    return (f'<span class="sheet">'
            f'<a class="btn ghost" href="/aiel-monitor-onepager.pdf">{label} →</a>'
            f'<span class="sheetlang"><a href="/aiel-monitor-onepager.pdf" aria-current="page">English</a>'
            f' · <a href="/aiel-monitor-onepager-sv.pdf">Swedish</a></span>'
            f'</span>')


def masthead(active):
    b = SITE["brand"]
    items = ""
    for n in SITE["nav"]:
        cur = ' aria-current="page"' if (not n.get("cta") and n["href"] == active) else ""
        cls = ' class="cta"' if n.get("cta") else ""
        items += f'<a href="{n["href"]}"{cls}{cur}>{h(n["label"]).replace("&gt;",">")}</a>'
    # Plain substitution, not str.format: the strip is hand-authored HTML and a
    # stray brace in a future entry must not raise.
    # {distinct_ads} is substituted from monthly_demand.yaml, the series that actually counts
    # them. It was typed as "8.1M" until 13 Aug 2026, when the figure beside it on the Monitor
    # page read 16,113,466: the monthly file had been built from a duplicate-poisoned CSV, and
    # nothing could notice, because the two numbers had no common source. A headline count that
    # is typed cannot disagree with its own data loudly enough to be heard.
    reg = "".join(
        f'<span>{s.replace("{data_updated}", DATA_UPDATED_DISPLAY).replace("{distinct_ads}", DISTINCT_ADS)
                    .replace("{sources_checked}", SOURCES_CHECKED_DISPLAY)
                    .replace("{n_countries}", str(N_COUNTRIES)).replace("{live_status}", LIVE_STATUS)}</span>'
        for s in SITE["registration"])
    return f"""<div class="mast"><div class="wrap"><div class="mastbar">
  <a class="brand" href="/"><span class="plaque"><b>{h(b['monogram'])}</b></span>
    <span class="brandtext"><b>{h(b['name'])}</b><small>{h(b['tagline'])}</small></span></a>
  <nav class="top">{items}</nav>
  <button class="tbtn" id="themebtn" aria-label="Toggle colour theme">◐ Theme</button>
</div></div><div class="regstrip"><div class="wrap"><div class="reg">{reg}</div></div></div></div>"""

def footer():
    cols = ""
    for c in SITE["footer"]["columns"]:
        ls = "".join(f'<a href="{l["href"]}">{h(l["label"])}</a>' for l in c["links"])
        cols += f'<div><h4>{h(c["title"])}</h4>{ls}</div>'
    b = SITE["brand"]
    return f"""<footer><div class="wrap"><div class="foot">
  <div><a class="brand" href="/" style="color:var(--navy-ink);margin-bottom:14px">
    <span class="plaque"><b>{h(b['monogram'])}</b></span>
    <span class="brandtext"><b style="color:#fff">{h(b['name'])}</b><small>{h(b['tagline'])}</small></span></a>
    <p>{h(b['description'])}</p></div>
  {cols}
  <div><h4>Contact</h4><a href="/about/#contact">Contact &amp; visit →</a></div>
</div><div class="footend">
  <span>© 2026 {h(b['name'])} · Örebro University &amp; RATIO</span>
  <span>PUBLIC DATA · MONITOR PROTOTYPE · CITE THE VERSION AND DATE</span>
</div></div></footer>"""

def shell(title, desc, path, body, jsonld="", need_chart=False):
    canonical = BASE + path
    trend_js = ""
    if need_chart:
        t = TREND["trend"]
        trend_js = (f'<script>window.AIEL_TREND={{years:{t["years"]},values:{t["values"]},'
                    f'floor:{t.get("floor_values", [])},'
                    f'provisionalFrom:{t["provisionalFrom"]},ymax:{t["ymax"]},yticks:{t["yticks"]}}};</script>')
    ld = f'<script type="application/ld+json">{jsonld}</script>' if jsonld else ""
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{h(title)}</title>
<meta name="description" content="{h(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website"><meta property="og:title" content="{h(title)}">
<meta property="og:description" content="{h(desc)}"><meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{h(SITE['brand']['name'])}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/assets/styles.css?v={assetv('assets/styles.css')}">{ld}
</head><body>
<a class="skip" href="#main">Skip to content</a>
{masthead(path)}
<main id="main">{body}</main>
{footer()}
<div class="tip" id="tip"></div>
{trend_js}<script src="/assets/app.js?v={assetv('assets/app.js')}"></script>
</body></html>"""

# ── JSON-LD ──────────────────────────────────────────────────────────────────
import json
def org_ld():
    b = SITE["brand"]
    return json.dumps({"@context":"https://schema.org","@type":"Organization","name":b["name"],
        "url":BASE,"description":b["description"],
        "parentOrganization":{"@type":"CollegeOrUniversity","name":"Örebro University"}}, ensure_ascii=False)

def dataset_ld():
    return json.dumps({"@context":"https://schema.org","@type":"Dataset","name":"AI in Demand",
        "description":MONITOR["lede"],"license":"https://creativecommons.org/publicdomain/zero/1.0/",
        "creator":{"@type":"Organization","name":SITE["brand"]["name"]},
        "isAccessibleForFree":True,"temporalCoverage":"2006/2026",
        "spatialCoverage":"Sweden","url":BASE+"/monitor/"}, ensure_ascii=False)

def daioe_ld():
    return json.dumps({"@context":"https://schema.org","@type":"Dataset","name":"DAIOE — data-driven AI Occupational Exposure",
        "description":DAIOE["lede"],"license":"https://creativecommons.org/licenses/by/4.0/",
        "creator":{"@type":"Organization","name":SITE["brand"]["name"]},"isAccessibleForFree":True,
        # encodingFormat is required on a DataDownload and was missing, which Search Console
        # reported on 16 Aug 2026. The repository publishes each vintage in three formats, so
        # all three are declared rather than guessing at one. contentUrl is the repository
        # landing page, which is where a human starts; the formats say what they will find.
        "distribution":{"@type":"DataDownload","contentUrl":DAIOE["resources"][0]["href"],
                        "encodingFormat":["text/csv",
                                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                          "application/x-stata-dta"]},
        "url":BASE+"/daioe/"}, ensure_ascii=False)

def people_ld():
    ppl = [{"@type":"Person","name":m["name"],"jobTitle":m["role"],
            **({"url":m["url"]} if m.get("url") else {})}
           for g in PEOPLE["groups"] for m in g["members"]]
    return json.dumps({"@context":"https://schema.org","@type":"ItemList",
        "itemListElement":[{"@type":"ListItem","position":i+1,"item":p} for i,p in enumerate(ppl)]},
        ensure_ascii=False)

# ── pages ────────────────────────────────────────────────────────────────────
def home():
    b, m = SITE["brand"], MONITOR
    affils = "".join(f"<span>{h(a)}</span>" for a in SITE["affiliations"])
    tiles = ""
    for t in m["tiles"]:
        cls = f' {t["cls"]}' if t["cls"] else ""
        tiles += (f'<div class="tile{cls}"><div class="stripe"></div>'
                  f'<div class="num">{num_html(t["num"])}</div><div class="lab">{h(t["lab"])}</div>'
                  f'<div class="foot">{h(t["foot"])}</div></div>')
    body = f"""<div class="wrap"><div class="hero"><div class="herogrid">
  <div>
    <div class="eyebrow"><span class="dot"></span> A multi-country, multi-disciplinary research lab</div>
    <h1 class="title">We study how <em>artificial intelligence</em> is reshaping the world of work.</h1>
    <!-- NOT "part of AISCAF" and NOT "contributing to" it. The lab was founded in 2019 and the
         cluster began in September 2025, so "part of" implies the cluster came first and that
         the lab sits inside it; "contributing to" errs the other way, putting the lab outside
         and hiding that the cluster funds Lydia, Yifan and part of Magnus's time. State the two
         facts and the date instead, and let no preposition carry what it cannot.
         NOTE the seminar series is a different case: it IS formally part of AISCAF from autumn
         2025, and the events page and seminars.yaml say so correctly. Do not "harmonise" those
         to match this. -->
    <p class="lede">An economics-led, multi-disciplinary research lab at Örebro University and RATIO,
      founded in 2019. Örebro is a node of <a href="https://www.aiscaf.se/w/ac/">AISCAF</a>,
      the <a href="https://wasp-hs.org">WASP-HS</a> research cluster.
      We combine administrative registers from
      several European countries with job advertisements, surveys and public cross-country data.
      The <b>AIEL Monitor</b> is where
      part of that work becomes public: open indicators on AI and work across countries, with Sweden
      in depth, updated as the data arrive.</p>
    <div class="cta-row"><a class="btn primary" href="/monitor/">Open the Monitor →</a>
      {sheet_pair()}</div>
    <div class="cta-row"><a class="btn ghost" href="/monitor/methods/">How we measure it</a></div>
    <div class="affil">{affils}</div>
  </div>
  {hero_exposure_panel("/monitor/#method", "/monitor/#exposure")}
</div></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">What the lab is</p>
  <h2 class="sec">A research lab first.</h2>
  <p class="secintro">The monitor is our measurement infrastructure made public: the same data and measures our
    own research runs on. We work across countries on public data and international comparisons, and, rarely for
    any lab, on linked employer–employee register data in several of them: deepest in Sweden, reaching Denmark,
    Portugal and Germany, and expanding to more. Economists work alongside sociologists, business scholars and computer
    scientists, because a labour market changed by AI cannot be read from one discipline or one country alone.</p>
  <div class="pillars">
    <div class="pillar"><div class="n">01 · DATA</div><h3>Register-grade evidence</h3>
      <p>Linked employer–employee register data at population scale in Sweden: annual, with 4-digit occupations
        (LISA), and monthly individual employment (AGI); plus comparable access in a handful of other countries.
        Rare reach, paired with {DISTINCT_ADS} distinct public job ads ({RECORD_ADS} ad records).</p></div>
    <div class="pillar"><div class="n">02 · REACH</div><h3>Multi-country</h3>
      <p>Register-level in Sweden, Denmark, Portugal and Germany, with more countries planned; 30-plus via EU-LFS
        and international job-ad data for external validity.</p></div>
    <div class="pillar"><div class="n">03 · LENS</div><h3>Multi-disciplinary</h3>
      <p>Economics, sociology, business administration and computer science, partly through the
        <a href="https://wasp-hs.org">WASP-HS</a> cluster <a href="https://www.aiscaf.se/w/ac/">AISCAF</a>,
        co-led with Uppsala and Stockholm.</p></div>
    <div class="pillar"><div class="n">04 · OUTPUT</div><h3>Open public goods</h3>
      <p>Peer-reviewed research, plus citable, versioned public tools: the AIEL Monitor and the DAIOE
        exposure measure and Explorer.</p></div>
  </div>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">Flagship · The AIEL Monitor</p>
  <h2 class="sec">Sweden, in depth: four things the live job-ad data show.</h2>
  <p class="secintro">One of the monitor's country cuts, read from Sweden's public job-ad stream (JobTech / Platsbanken).
    Every figure is measured from the ad text with a versioned, citable term list. Where something is not yet
    measured, we say so.</p>
  <div style="margin-top:22px">{sweden_trend_panel("/monitor/#method", "AI in Demand · share of Swedish job ads")}</div>
  <div class="tiles">{tiles}</div>
  <div class="two">
    <div class="prod"><div class="tag">The Monitor · public data</div><h3>The AI-Econ Lab Monitor</h3>
      <p>How AI shows up in the labour market: AI in Demand (live), the Occupations Explorer (live), AI exposure across countries (live), and
        modules on adoption, augmentation and barriers in development.</p>
      <a class="go" href="/monitor/">Open the monitor →</a></div>
    <div class="prod"><div class="tag">The measure · open &amp; versioned</div><h3>DAIOE</h3>
      <p>Our data-driven AI Occupational Exposure measure, published openly and mapped across SOC / ISCO / SSYK so
        others can join it onto their own data.</p>
      <a class="go" href="/daioe/">Explore DAIOE →</a></div>
  </div>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">Research</p><h2 class="sec">Selected recent work.</h2>
  <div class="rows">{research_rows(limit=4)}</div>
  <p style="margin-top:20px"><a class="mono" style="font-size:12.5px" href="/research/">All {paper_count()} papers →</a></p>
</section></div></div>"""
    return shell(f"{b['name']} · measuring AI and the future of work", b["description"], "/",
                 body, jsonld=org_ld(), need_chart=True)

def paper_row(p, detail):
    primary = p["links"][0]["url"] if p.get("links") else ""
    title = h(p["title"])
    if primary: title = f'<a href="{primary}" style="color:inherit">{title}</a>'
    bcls = " pub" if p in PAPERS["published"] else ""
    tag = h(p["venue"]) if p.get("venue") else "Working paper"
    det = ""
    if detail and (p.get("abstract") or p.get("coverage") or p.get("links")):
        parts = ""
        if p.get("abstract"):
            parts += f'<p class="pab">{h(p["abstract"])}</p>'
        if p.get("coverage"):
            covs = ""
            for c in p["coverage"]:
                nm = c["name"] if isinstance(c, dict) else c
                if isinstance(c, dict) and c.get("url"):
                    covs += f'<a class="lchip" href="{c["url"]}">{h(nm)}</a>'
                else:
                    covs += f'<span class="lchip nolink">{h(nm)}</span>'
            parts += f'<p class="pmeta2"><span class="lbl">In the media</span> {covs}</p>'
        if p.get("links"):
            chips = "".join(f'<a class="lchip" href="{l["url"]}">{h(l["label"])}</a>' for l in p["links"])
            parts += f'<p class="plinks"><span class="lbl">Versions &amp; links</span> {chips}</p>'
        det = f'<details class="pdetail"><summary>Details</summary><div class="pbody">{parts}</div></details>'
    return (f'<div class="rrow"><span class="yr tnum">{h(p["year"])}</span>'
            f'<span><span class="rt">{title}</span><span class="ra">{h(p["authors"])}</span>{det}</span>'
            f'<span class="badge{bcls}">{tag}</span></div>')

def research_rows(limit=None, detail=False):
    if limit:
        merged = (PAPERS["published"] + PAPERS["working"])[:limit]
        return "".join(paper_row(p, detail) for p in merged)
    out = ""
    for gname, items in [("Published", PAPERS["published"]), ("Working papers & in review", PAPERS["working"])]:
        out += f'<div class="grouphdr">{h(gname)}</div>' + "".join(paper_row(p, detail) for p in items)
    return out

def paper_count(): return len(PAPERS["published"]) + len(PAPERS["working"])

def research():
    body = f"""<div class="wrap"><div class="pagehead">
  <p class="kicker">Research</p><h2 class="sec">Papers &amp; publications</h2>
  <p class="secintro">Peer-reviewed articles and working papers from the lab and its network. Data-driven measures,
    causal identification, and register-grade evidence on AI and work.</p></div></div>
<div class="wrap"><section style="padding-top:8px"><div class="rows">{research_rows(detail=True)}</div></section></div>"""
    return shell(f"Research · {SITE['brand']['name']}",
                 "Peer-reviewed articles and working papers on AI and the labour market.",
                 "/research/", body)

def initials(name):
    parts = [p for p in name.replace("-", " ").split() if p]
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else name[:2].upper()

def pslug(name):
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().replace("ø", "o")
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")

def photo_for(name):
    """Auto-detect assets/people/<slug>.<ext>; drop a correctly named file and it appears.
    Appends ?v=<hash> so browsers refetch when a photo's content changes (no stale cache)."""
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = ROOT / "assets" / "people" / f"{pslug(name)}.{ext}"
        if p.exists():
            v = hashlib.md5(p.read_bytes()).hexdigest()[:8]
            return f"{pslug(name)}.{ext}?v={v}"
    return None

def person_card(m):
    photo = m.get("photo") or photo_for(m["name"])
    if photo:
        avatar = f'<img class="avatar" src="/assets/people/{photo}" alt="{h(m["name"])}" loading="lazy" width="52" height="52">'
    else:
        avatar = f'<span class="avatar mono" aria-hidden="true">{h(initials(m["name"]))}</span>'
    role = f'<div class="role">{h(m["role"])}</div>' if m.get("role") else ""
    link = f'<a class="pl" href="{m["url"]}">Profile →</a>' if m.get("url") else ""
    bio = (f'<details class="bio"><summary>Read more</summary><p>{h(m["bio"])}</p></details>'
           if m.get("bio") else "")
    return (f'<div class="person">{avatar}<div class="pmeta"><h3>{h(m["name"])}</h3>{role}'
            f'<div class="aff">{h(m["aff"])}</div>{bio}{link}</div></div>')

def people():
    blocks = ""
    for g in PEOPLE["groups"]:
        cards = "".join(person_card(m) for m in g["members"])
        blocks += f'<div class="grouphdr">{h(g["name"])}</div><div class="people">{cards}</div>'
    body = f"""<div class="wrap"><div class="pagehead">
  <p class="kicker">People</p><h2 class="sec">The lab &amp; its network</h2>
  <p class="secintro">Economists, statisticians, computer scientists and business scholars across Sweden, Denmark,
    Portugal, Germany and Switzerland. Select any name to read more.</p></div></div>
<div class="wrap"><section style="padding-top:8px">{blocks}</section></div>"""
    return shell(f"People · {SITE['brand']['name']}",
                 "The AI-Econ Lab team and its international, multi-disciplinary network.",
                 "/people/", body, jsonld=people_ld())

def exposure_bars(items, cls):
    mx = DAIOE_EXP["most"][0]["score"]
    out = ""
    for it in items:
        w = max(4, it["score"] / mx * 100)
        out += (f'<div class="exprow"><span class="expocc">{h(it["occ"])}</span>'
                f'<span class="expval tnum">{it["score"]:.2f}</span>'
                f'<div class="expbarwrap"><div class="expbar {cls}" style="width:{w:.1f}%"></div></div></div>')
    return out

def daioe():
    # The PURE measure. The interactive Explorer lives under the Monitor (it consumes DAIOE + SCB).
    d = DAIOE
    res = "".join(f'<li><a href="{r["href"]}">{h(r["label"])}</a> <span class="mono">· {h(r["note"])}</span></li>'
                  for r in d["resources"])
    faq = "".join(f'<details class="faq"><summary>{h(q["q"])}</summary><p>{h(q["a"])}</p></details>'
                  for q in d.get("faq", []))
    most = exposure_bars(DAIOE_EXP["most"], "hi")
    least = exposure_bars(list(reversed(DAIOE_EXP["least"])), "lo")
    body = f"""<div class="wrap"><div class="hero" style="padding-bottom:6px"><div>
  <div class="eyebrow"><span class="dot"></span> {h(d['tagline'])}</div>
  <h1 class="title" style="max-width:16ch">{h(d['headline'])}: how exposed is each job to AI?</h1>
  <p class="lede" style="max-width:60ch">{h(d['lede'])}</p>
  <div class="cta-row"><a class="btn primary" href="{d['resources'][0]['href']}">Download the data →</a>
    <a class="btn ghost" href="/monitor/#occupations-explorer">See it applied in the Monitor</a></div>
</div></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">How exposed is your job?</p>
  <h2 class="sec">Find your occupation.</h2>
  <p class="secintro">Type an occupation to see its DAIOE exposure and where it sits among roughly {N_OCCUPATIONS} occupations.
    Generative AI by default; switch the sub-domain to compare.
    <a class="mono" style="font-size:12px;white-space:nowrap" href="https://www.zeit.de/wirtschaft/2026-05/automatisierungsrisiko-arbeitnehmer-ki-arbeitsmarkt-bedrohung">As featured in Die Zeit ↗</a></p>
  <div class="occtool">
    <div class="occrow1">
      <div class="occsearchbox">
        <input id="occsearch" type="text" autocomplete="off" aria-label="Search occupation"
          placeholder="e.g. Economists, Software developers, Roofers…">
        <div id="occsugg" class="occsugg" role="listbox"></div>
      </div>
      <label class="occdomwrap">Sub-domain<select id="occdom" aria-label="DAIOE sub-domain"></select></label>
    </div>
    <div id="occresult" class="occresult" aria-live="polite"></div>
  </div>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">The whole landscape · generative AI, {DAIOE_EXP['year']}</p>
  <h2 class="sec">Every occupation, placed by its exposure.</h2>
  <div class="scrolly">
    <div class="scrolly-chart">
      <svg id="beeswarm" viewBox="0 0 760 340" role="img" aria-label="Beeswarm of about {N_OCCUPATIONS} occupations by generative-AI exposure"></svg>
      <div class="beeaxis"><span>← less exposed</span><span>more exposed →</span></div>
    </div>
    <div class="scrolly-steps">
      <div class="step" data-hl="all"><p>Roughly {N_OCCUPATIONS} occupations, each a dot, placed left to right by how exposed they are to generative AI. Hover any dot to name it.</p></div>
      <div class="step" data-hl="hi"><p><b>The exposed end is desk work.</b> Writers, programmers, analysts, marketers and, yes, economists cluster on the right.</p></div>
      <div class="step" data-hl="lo"><p><b>The other end is hands and bodies.</b> Care, craft, construction, cleaning and farming sit on the left, where generative AI reaches least.</p></div>
      <div class="step" data-hl="hi"><p><b>It cuts against intuition.</b> The more schooling a job needs, the more exposed it tends to be. Exposure is not replacement, but the pattern is stark.</p></div>
    </div>
  </div>
  <p class="prov" style="margin-top:8px">Source: DAIOE v{DAIOE_EXP['year']} · ISCO-08. Look up your own job in the search above.</p>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">The named extremes · generative AI, {DAIOE_EXP['year']}</p>
  <h2 class="sec">Where generative AI reaches, and where it doesn't.</h2>
  <p class="secintro">DAIOE's generative-AI exposure across roughly {N_OCCUPATIONS} occupations. Writers, marketers, programmers
    and, yes, economists sit at the very top; hands-on manual, craft and outdoor work sits at the bottom.</p>
  <div class="expgrid">
    <div><div class="exphead"><span class="dotc hi"></span>Most exposed to generative AI</div>
      <div class="expbars">{most}</div></div>
    <div><div class="exphead"><span class="dotc lo"></span>Least exposed</div>
      <div class="expbars">{least}</div></div>
  </div>
  {figfooter("daioe_most_least.csv", f"DAIOE generative-AI v{DAIOE_EXP['year']} · ISCO-08", next_up="with the DAIOE v2024 release")}
  <p class="prov" style="margin-top:16px">Source: DAIOE v{DAIOE_EXP['year']} · ISCO-08 · higher score = more exposed.
    Explore every occupation in the <a href="/monitor/#occupations-explorer">Occupations Explorer</a>.</p>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">The measure</p>
  <h2 class="sec">Data-driven, not expert-guessed.</h2>
  <p class="secintro">DAIOE scores each occupation's exposure to AI from data, and publishes those scores openly and with
    versions, mapped across the US (SOC), international (ISCO) and Swedish (SSYK) classifications, so others can join
    it straight onto their own data.</p>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">Use it in your own work</p>
  <h2 class="sec">Open data &amp; crosswalks.</h2>
  <ul class="reslist">{res}</ul>
  <p class="secintro" style="margin-top:18px">Introduced and validated in the working paper
    &ldquo;{h(d['paper']['title'])}&rdquo;. See <a href="/research/">Research</a>.</p>
</section></div></div>

<div class="rule" id="faq"><div class="wrap"><section>
  <p class="kicker">FAQ</p>
  <h2 class="sec">What DAIOE is, and isn't.</h2>
  <div class="faqlist">{faq}</div>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">See it live</p>
  <h2 class="sec">DAIOE in the Monitor.</h2>
  <p class="secintro">The <a href="/monitor/#occupations-explorer">Occupations Explorer</a>, part of the AIEL Monitor, sets
    Swedish employment by occupation against DAIOE exposure levels, in yearly and monthly views.</p>
</section></div></div>"""
    return shell(f"DAIOE · data-driven AI occupational exposure · {SITE['brand']['name']}",
                 "DAIOE: the lab's open, data-driven measure of occupational AI exposure, mapped across SOC / ISCO / SSYK.",
                 "/daioe/", body, jsonld=daioe_ld())

def events():
    s = SEMINARS; ser = s["series"]
    fmt = "".join(f"<li>{h(x)}</li>" for x in ser["format"])
    def surname(name): return name.split("&")[0].strip().split()[-1] if name and name != "TBD" else name
    def sem_row(e):
        spk_url = next((l["url"] for l in e.get("links", []) if l["label"] != "Paper"), "")
        paper_url = next((l["url"] for l in e.get("links", []) if l["label"] == "Paper"), "")
        speaker = h(e["speaker"])
        if spk_url:   # link the presenter's own name (surname), not a "Speaker" chip
            speaker = speaker.replace(h(surname(e["speaker"])), f'<a href="{spk_url}">{h(surname(e["speaker"]))}</a>', 1)
        aff = f' <span class="saff">{h(e["affil"])}</span>' if e.get("affil") else ""
        if e["title"] and e["title"] != "TBD":
            title = f'<a href="{paper_url}">{h(e["title"])}</a>' if paper_url else h(e["title"])
        else:
            title = '<span class="tbd">To be announced</span>'
        return (f'<div class="semrow"><span class="yr tnum">{h(e["date"])}</span>'
                f'<span><span class="rt">{speaker}{aff}</span><span class="ra">{title}</span></span></div>')
    # Only forthcoming seminars are shown; the rest go behind a toggle (ISO dates sort chronologically).
    today = datetime.date.today().isoformat()
    allsem = [e for season in s["seasons"] for e in season["seminars"]]
    upcoming = sorted((e for e in allsem if e["date"] >= today), key=lambda e: e["date"])
    past = sorted((e for e in allsem if e["date"] < today), key=lambda e: e["date"], reverse=True)
    up_html = "".join(sem_row(e) for e in upcoming) or '<p class="psub">No seminars scheduled just now; the series resumes after the summer.</p>'
    prev_block = (f'<details class="yearblock"><summary>Previous seminars ({len(past)})</summary>'
                  f'<div class="rows semlist">{"".join(sem_row(e) for e in past)}</div></details>') if past else ""
    def cfp_link(c):
        out = ""
        if c.get("cfp"): out += f' <a class="lchip" href="{c["cfp"]}">Call for papers</a>'
        if c.get("programme"): out += f' <a class="lchip" href="{c["programme"]}">Programme</a>'
        return out
    past_conf = ""
    for c in s["conferences"]["past"]:
        past_conf += (f'<div class="confentry"><div class="confhd"><span class="confedition">{h(c["edition"])} conference</span>'
                 f'<span class="yr tnum">{h(c["when"])}</span></div>'
                 f'<div class="conftitle">{h(c["title"])}</div>'
                 f'<div class="confmeta">{h(c["where"])}. {h(c["note"])}{cfp_link(c)}</div></div>')
    nx = s["conferences"]["next"]
    nxdetails = "".join(f"<li>{h(x)}</li>" for x in nx["details"])
    kv = assetv("assets/conferences/katrinelund.jpg")
    body = f"""<div class="wrap"><div class="pagehead">
  <p class="kicker">Events</p><h2 class="sec">Conference &amp; seminars</h2>
  <p class="secintro">The lab runs two things. Its flagship is an annual, interdisciplinary conference on AI and
    white-collar work, held since 2020 at Katrinelund on Lake Hjälmaren near Örebro. Alongside it runs a monthly
    online brown-bag seminar series, part of <a href="https://www.aiscaf.se/w/ac/">AISCAF</a>.
    For publications, media, grants and people since 2019, see the <a href="/news/">news archive</a>.</p></div></div>

<div class="rule" id="conference-2028"><div class="wrap"><section style="padding-top:20px">
  <p class="kicker">Flagship · next conference · {h(nx['edition'])} AIEL conference</p>
  <h2 class="sec">{h(nx['title'])}.</h2>
  <div class="conf2028">
    <div>
      <p class="secintro">{h(nx['when'])} · {h(nx['where'])}. Hosted by {h(nx['hosts'])}. Organisers: {h(nx['organisers'])}.</p>
      <ul class="reslist" style="margin-top:12px">{nxdetails}</ul>
    </div>
    <figure class="confphoto">
      <img src="/assets/conferences/katrinelund.jpg?v={kv}" alt="Katrinelund conference venue on Lake Hjälmaren near Örebro" loading="lazy">
      <figcaption>Katrinelund, on Lake Hjälmaren near Örebro, has hosted the conference since 2020.</figcaption>
    </figure>
  </div>
  <div class="grouphdr" style="margin-top:30px">Earlier conferences</div>
  {past_conf}
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">Seminar series</p>
  <h2 class="sec">{h(ser['title'])}.</h2>
  <p class="secintro" style="max-width:72ch">{h(ser['intro'])}</p>
  <div class="two" style="grid-template-columns:1.5fr 1fr;align-items:start;margin-top:14px">
    <div>
      <div class="grouphdr">Upcoming</div>
      <div class="rows semlist">{up_html}</div>
      {prev_block}
    </div>
    <div class="card"><div class="charttitle" style="margin-bottom:8px">Attending</div>
      <ul class="reslist">{fmt}</ul>
      <p style="margin:12px 0 0"><a class="btn ghost" style="font-size:12px" href="{ser['zoom']}">Join on Zoom →</a></p>
      <p class="psub" style="margin-top:12px">Contact: {h(ser['contact'])}</p></div>
  </div>
</section></div></div>"""
    body += recent_news_block()
    return shell(f"Events & news · {SITE['brand']['name']}",
                 "The AIEL conference on AI and white-collar work, the monthly brown-bag seminar series "
                 "(part of AISCAF), and recent lab news.",
                 "/events/", body)


def recent_news_block(n=8):
    """The newest news items, shown on the Events page.

    Merging Events and News into one nav entry (Schroeder's review) pointed that entry at
    /events/, which holds only the conference and the seminar series. News then had no route
    from the navigation at all, which Magnus caught the same day. Showing the latest items
    here makes the merged label honest, while the full archive keeps its own page and its
    permalinks: a summary, not a second copy of the archive.
    """
    items = []
    for yr in NEWS["years"]:                     # newest year first
        for it in yr["items"]:
            items.append((yr["year"], it))
            if len(items) >= n:
                break
        if len(items) >= n:
            break
    rows = ""
    for year, it in items:
        links = "".join(f'<a class="lchip" href="{l["url"]}">{h(l["label"])}</a>'
                        for l in it.get("links", []))
        linkrow = f' <span class="nlinks">{links}</span>' if links else ""
        rows += (f'<div class="nrow"><span class="yr tnum">{h(it["date"])} {h(year)}</span>'
                 f'<span class="ntext">{it["text"]}{linkrow}</span></div>')
    return f"""
<div class="rule"><div class="wrap"><section>
  <p class="kicker">News</p>
  <h2 class="sec">Latest from the lab.</h2>
  <p class="secintro">Publications, media, grants and people. The {len(items)} most recent items;
    the full record since 2019 is in the <a href="/news/">news archive</a>.</p>
  <div class="rows" style="margin-top:18px">{rows}</div>
  <p style="margin-top:20px"><a class="mono" style="font-size:12.5px" href="/news/">All news since 2019 →</a></p>
</section></div></div>"""

def news():
    def nrow(it):
        links = "".join(f'<a class="lchip" href="{l["url"]}">{h(l["label"])}</a>' for l in it.get("links", []))
        linkrow = f' <span class="nlinks">{links}</span>' if links else ""
        return (f'<div class="nrow"><span class="yr tnum">{h(it["date"])}</span>'
                f'<span class="ntext">{it["text"]}{linkrow}</span></div>')
    blocks = ""
    for i, yr in enumerate(NEWS["years"]):   # newest year first; only it is open
        items = "".join(nrow(it) for it in yr["items"])
        if i == 0:
            blocks += f'<div class="grouphdr">{h(yr["year"])}</div><div class="rows">{items}</div>'
        else:
            blocks += (f'<details class="yearblock"><summary>{h(yr["year"])}</summary>'
                       f'<div class="rows">{items}</div></details>')
    body = f"""<div class="wrap"><div class="pagehead">
  <p class="kicker">News</p><h2 class="sec">What the lab has been up to</h2>
  <p class="secintro">Publications, media, grants, conferences and people, since the lab was initiated in 2019.
    The current year is shown; select any earlier year to expand it.
    For the annual conference and the seminar series, see <a href="/events/">events</a>.</p></div></div>
<div class="wrap"><section style="padding-top:8px">{blocks}</section></div>"""
    return shell(f"News · {SITE['brand']['name']}",
                 "News and history of the AI-Econ Lab since 2019: publications, media, grants and events.",
                 "/news/", body)

def note(visible, method, label="How this is counted"):
    """Split a caveat: what changes the reading stays visible, how it was computed collapses.

    The page carried 39 blocks over 180 characters, the longest 926, and each earned its place
    by defending a claim against a real objection. The problem was never that they were wrong,
    it was that a reader meets the hedging before the finding, so the page reads as less
    confident than its evidence.

    The split rule is deliberately NOT about length. `visible` is the caveat that changes how
    you read the number -- "this cannot separate AI from the rate cycle" belongs there and must
    never collapse. `method` is the caveat explaining how the number was made: denominators,
    display gates, comparison groups, which a reader wants on demand rather than in the way.

    Nothing is removed. The text stays in the DOM for search and screen readers, <details> is
    keyboard-accessible by default, and the print stylesheet expands it so a PDF loses nothing.
    """
    if not method:
        return f'<p class="secintro">{visible}</p>\n'
    return (f'<p class="secintro">{visible}</p>\n'
            f'<details class="note"><summary>{h(label)}</summary><p>{method}</p></details>\n')


def akavia_provenance(m):
    """Provenance plus the split caveat, rendered identically wherever Akavia data appear.

    The full caveat ran to 225 words and was printed verbatim in two places, so a reader met a
    wall twice and the second time learned nothing. What changes the reading stays visible; the
    panel mechanics collapse behind a summary, exactly as note() prescribes. One function so the
    two sites cannot drift apart.
    """
    vis = (f'Data shared with the lab by <a href="{m["url"]}">Akavia</a>. {h(m["caveat"])}')
    meth = h(m.get("caveat_method", ""))
    if not meth:
        return f'<p class="prov" style="margin-top:10px">{vis}</p>'
    return (f'<p class="prov" style="margin-top:10px">{vis}</p>\n'
            f'<details class="note"><summary>About the Akavia panel</summary>'
            f'<p>{meth}</p></details>')


# ---- one convention for authoring the split -------------------------------------------------
# note() above is the renderer and predates this. What was missing was a way to AUTHOR the split
# inside a single paragraph: copy carries a marker, everything before [[note]] stays visible and
# everything after folds away. Moving one marker moves one sentence, which is reviewable, and
# removing every marker restores the page exactly. It delegates to note() rather than emitting
# its own <details>, so there is one renderer and the two cannot drift apart.
NOTE_MARK = "[[note]]"

def folded(txt, cls="secintro", style="", label=None):
    """Author a paragraph with an inline [[note]] marker; render it through note()."""
    st = f' style="{style}"' if style else ""
    if NOTE_MARK not in txt:
        return f'<p class="{cls}"{st}>{txt}</p>'
    if label is None:
        raise ValueError(
            "folded(): every disclosure needs a label that names what is inside it. The page's own "
            "convention is specific ('Where the dip goes when you count each advertisement once'); "
            "a catch-all makes the reader guess, and 'How to read this' puts the problem on the "
            "reader rather than on the measurement (Magnus, 13 Aug 2026).")
    lead, rest = [x.strip() for x in txt.split(NOTE_MARK, 1)]
    if not rest:
        return f'<p class="{cls}"{st}>{lead}</p>'
    return note(lead, rest, label=label).replace('<p class="secintro">', f'<p class="{cls}"{st}>', 1)


def figfooter(csv_name, source, svg_name=None, method_href=None, next_up=None):
    """Item 10: download + provenance under a figure. Source states DAIOE variant + year.
    Offers the data (CSV) plus, when the figure has a static SVG, the chart as SVG and PNG
    (PNG is rasterised client-side from the SVG, so no build dependency). method_href, when
    given, appends a link to the fuller method/sources note. next_up states when the figure's
    source is next expected to move (release-calendar practice, per module: sources publish on
    their own cadences, so there is no single site-wide next date)."""
    dl = f'<a class="figdl" href="/assets/data/{csv_name}" download>↓ Data (CSV)</a>'
    if svg_name:
        dl += (f'<a class="figdl" href="/assets/data/{svg_name}" download>↓ SVG</a>'
               f'<button class="figdl figpng" type="button" data-svg="/assets/data/{svg_name}">↓ PNG</button>'
               f'<button class="figdl figpng" type="button" data-svg="/assets/data/{svg_name}" data-scale="4" '
               f'title="High-resolution PNG on a white ground, sized for Beamer and PowerPoint slides">↓ PNG (slides)</button>')
    nxt = f'<span class="fignext">Next: {h(next_up)}</span>' if next_up else ""
    meth = f'<a class="figml" href="{h(method_href)}">Method &amp; sources →</a>' if method_href else ""
    return f'<div class="figfoot">{dl}<span class="figsrc">Source: {h(source)}</span>{nxt}{meth}</div>'

def dotplot(cc):
    """Server-rendered ranked dot plot (Cleveland) — dots, not bars, since the index is
    compressed and a bar would imply a false zero baseline. Sweden highlighted; mean marked."""
    rows = cc["countries"]; n = len(rows)
    hy = int(cc["meta"].get("weight_year", 0))
    W, rowh, top, bot = 640, 16, 16, 34
    H = top + n * rowh + bot
    xmin, xmax, x0, x1 = 1.65, 2.25, 140, 560
    X = lambda v: x0 + (v - xmin) / (xmax - xmin) * (x1 - x0)
    p = [f'<svg class="rankchart dotplot" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Ranked dot plot of employment-weighted AI exposure by country, {n} countries, Sweden highlighted">']
    for t in (1.7, 1.8, 1.9, 2.0, 2.1, 2.2):
        gx = X(t)
        p.append(f'<line class="grid" x1="{gx:.1f}" y1="{top}" x2="{gx:.1f}" y2="{top+n*rowh}"/>')
        p.append(f'<text class="tick" x="{gx:.1f}" y="{H-14}" text-anchor="middle">{t:.1f}</text>')
    mx = X(cc["meta"]["mean"])
    p.append(f'<line class="meanline" x1="{mx:.1f}" y1="{top-1}" x2="{mx:.1f}" y2="{top+n*rowh}"/>')
    p.append(f'<text class="meanlab" x="{mx:.1f}" y="{top-4}" text-anchor="middle">'
             f'{cc["meta"]["n_countries"]}-country mean</text>')
    # This gutter is a fixed 128px and the canvas does not grow with it, so a long label here
    # is CLIPPED, silently, the way barplot's used to be. Country names have never come close,
    # but "has never happened" is not a guarantee: shortening to what the gutter can actually
    # show turns a future clip into a marked abbreviation. ~6.2px per character at 10px mono.
    dot_limit = int((128 - 10) / 6.2)
    for i, r in enumerate(rows):
        y = top + i * rowh + rowh * 0.62
        se = " se" if r["is_se"] else ""
        vx = X(r["exposure"])
        full = str(r["name"])
        disp = shorten(full, limit=dot_limit)
        nm = h(disp) + (f" ’{str(r['year'])[-2:]}" if hy and int(r.get("year", hy)) != hy else "")
        tip = f"<title>{h(full)}</title>" if disp != full else ""
        p.append(f'<line class="rowguide" x1="{x0}" y1="{y-3:.1f}" x2="{x1}" y2="{y-3:.1f}"/>')
        p.append(f'<text class="dname{se}" x="128" y="{y:.1f}" text-anchor="end">{tip}{nm}</text>')
        p.append(f'<circle class="dot{se}" cx="{vx:.1f}" cy="{y-3:.1f}" r="{4.4 if r["is_se"] else 3.1}"/>')
        p.append(f'<text class="dval{se}" x="600" y="{y:.1f}" text-anchor="end">{r["exposure"]:.2f}</text>')
    p.append("</svg>")
    return "".join(p)


# The Nordic set, for the weaker highlight tier on the country charts. Iceland is here even
# though the adoption table has no row for it: a country missing from a source is missing, and
# the flag should not quietly differ between two charts.
NORDIC = {"SE", "DK", "NO", "FI", "IS"}


def nordic(rows):
    """Tag rows for the second highlight tier without touching is_se."""
    return [dict(r, is_nordic=r.get("code") in NORDIC) for r in rows]

def barplot(data, eu_avg, xmax, hy=0, vkey="adoption", vfmt=".0f", what="countries",
            mean_label="EU27", cmp_key=None, cmp_label="", series_label="", lang="en"):
    """Ranked horizontal bar chart (share; meaningful zero). Bar = latest year; a muted delta
    shows the year-on-year change from the previous wave (when present). Sweden highlighted.

    mean_label names the reference line's population and DEFAULTS TO EU27, because every caller
    that takes the default draws Eurostat's EU27_2020 aggregate. Pass it whenever the line is
    something else. It was defaulted to "EU" until 12 Aug 2026, and the exposure charts, whose
    line is the mean over 36 EU-LFS countries including Switzerland, the UK and Turkey,
    inherited it in four places and told the reader they were looking at an EU average.

    The label gutter is sized to the longest label. It used to be a fixed 128px, which was
    fine for country names but silently CLIPPED longer ones: Akavia's official profession
    titles ("Communication professionals", "Business professionals and economists") ran off
    the left of the viewBox and rendered as "ication professionals". Labels are 10px in the
    mono face, so ~0.62em per character is a safe advance width; the gutter grows and the
    bars shorten rather than anything being cut.

    That fix carried a `min(300, ...)` cap, which quietly reintroduced the very defect the
    paragraph above says it removed: any label past ~46 characters was clipped again, exactly
    as before, and the cap's own comment ("so bars stay readable") described a trade-off that
    was never made -- nothing shortened the bars, the label was simply cut. It survived
    because only one label in the whole dataset is that long: SCB's "Assistant nurses, home
    care, home nursing, elderly care and habilitation" (72 chars) rendered on the live site as
    "care, home nursing, elderly care and habilitation", losing the occupation's actual name.

    So the gutter is now uncapped and the CANVAS grows with it instead. W is no longer a
    constant; every x to the right of the gutter is measured from W, which keeps the plotting
    area exactly 216px and the right-hand columns exactly where they were for every existing
    chart (all of which sit under the old 300px cap and are therefore byte-identical), while a
    long label widens the viewBox rather than losing characters. A wider viewBox scales down
    inside the same container, which is a visible, self-announcing trade; clipping is not.

    THAT TRADE TURNED OUT TO BE A BAD ONE ON A PHONE, which is where most readers are. The
    72-character nursing title pushed the viewBox to 796, so the gutter took 57 per cent of
    the width; scaled into a portrait screen the reader got a column of titles and a sliver of
    chart, all of it too small to read. Neither clipping nor growing was the answer: the title
    was simply too long to print in full beside a bar.

    Labels are shortened for display now (scripts/labels.py, the way a statistical agency
    does it: keep the head, drop the enumeration, mark it "etc." or "m.m."), and the full
    official title goes into a <title> child of the text element, so hover and assistive
    technology still read it. The CSV exports keep the full title too: a data file has no
    width to run out of. The uncapped gutter stays as the backstop for anything the shortener
    cannot help, and with a 36-character cap the canvas is back to a constant 640."""
    rows = data; n = len(rows); hy = int(hy)
    rowh, top, bot = 15, 18, 34
    H = top + n * rowh + bot
    short = {str(r["name"]): shorten(str(r["name"]), lang) for r in rows}
    longest = max((len(v) for v in short.values()), default=0)
    gutter = max(128, int(longest * 10 * 0.62) + 10)
    W = 640 + max(0, gutter - 300)      # grow the canvas, never the clip
    x0, x1 = gutter + 12, W - 112
    X = lambda v: x0 + v / xmax * (x1 - x0)
    step = 10 if xmax > 25 else 5 if xmax > 12 else 1
    p = [f'<svg class="rankchart barplot" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Ranked bar chart, {n} {h(what)}, latest value with change since the previous wave">']
    # A paired chart without a key is a puzzle: two colours and no way to tell which is which.
    if cmp_key:
        gap = int(x0 + 13 + len(series_label) * 6.2 + 10)
        # PLAIN bar, not `bar se`. It was `se`, so the legend showed blue for the current year
        # while almost every bar rendered grey, and blue separately meant "highlighted row":
        # one colour, two meanings, with the legend backing the wrong one. Yifan caught it on
        # the September brief. In comparison mode the bars now carry no colour highlight at all
        # and the emphasis moves to the row LABEL, so the chart has two colours and each means
        # exactly one thing.
        p.append(f'<rect class="bar" x="{x0}" y="4" width="9" height="7" rx="2"/>'
                 f'<text class="tick" x="{x0+13}" y="10.5">{h(series_label)}</text>'
                 f'<rect class="barcmp" x="{gap}" y="4" width="9" height="7" rx="2"/>'
                 f'<text class="tick" x="{gap+13}" y="10.5">{h(cmp_label)}</text>')
    # The delta column carried bare numbers, so "+32" could be read as per cent or as percentage
    # points. It is percentage points. A header rather than a suffix on every row, which would
    # widen the column for no gain.
    if not cmp_key and any(r.get("prev") is not None for r in data):
        # Spelled out in Swedish: "pp" is an English abbreviation and "pe" would be guessed at.
        unit = "procentenheter" if lang == "sv" else "pp"
        p.append(f'<text class="tick" x="{W-8}" y="10.5" text-anchor="end">{unit}</text>')
    elif cmp_key:
        # The right-hand column carries the comparison YEAR's value, not a change. Unlabelled it
        # reads as a mystery number beside the bar: "88  31" tells you nothing about what 31 is.
        p.append(f'<text class="tick" x="{W-8}" y="10.5" text-anchor="end">{h(cmp_label)}</text>')
    for t in range(0, int(xmax) + 1, step):
        gx = X(t)
        p.append(f'<line class="grid" x1="{gx:.1f}" y1="{top}" x2="{gx:.1f}" y2="{top+n*rowh}"/>')
        p.append(f'<text class="tick" x="{gx:.1f}" y="{H-13}" text-anchor="middle">{t}%</text>')
    if eu_avg:
        mx = X(eu_avg)
        p.append(f'<line class="meanline" x1="{mx:.1f}" y1="{top-1}" x2="{mx:.1f}" y2="{top+n*rowh}"/>')
        # The reference line is not always the EU average. Two callers pass a SWEDISH figure
        # (the national floor on the occupations cut, the national rate on the population cut),
        # and hardcoding "EU" printed "EU 0.52" and "EU 42" over Sweden's own numbers -- on a
        # chart whose caption directly beneath said "the line marks the national figure".
        p.append(f'<text class="meanlab" x="{mx:.1f}" y="{top-5}" text-anchor="middle">'
                 f'{h(mean_label)} {eu_avg:g}</text>')
    for i, r in enumerate(rows):
        # Two highlight tiers. `is_se` stays Sweden-only, because three call sites do
        # next(r for r in countries if r["is_se"]) and would break on a second match.
        # `is_nordic` is the weaker tier: visible, but never mistaken for Sweden.
        y = top + i * rowh
        se = " se" if r["is_se"] else (" nordic" if r.get("is_nordic") else "")
        v = r[vkey]
        full = str(r["name"])
        suffix = f" ’{str(r['year'])[-2:]}" if hy and int(r.get("year", hy)) != hy else ""
        nm = h(short[full]) + suffix
        # The official title, in full, for hover and for assistive technology. Only when the
        # display label actually differs -- an identical <title> on every row is noise that
        # screen readers read out twice.
        tip = f"<title>{h(full)}</title>" if short[full] != full else ""
        p.append(f'<text class="dname{se}" x="{gutter}" y="{y+rowh*0.72:.1f}" '
                 f'text-anchor="end">{tip}{nm}</text>')
        if cmp_key and r.get(cmp_key) is not None:
            cv = r[cmp_key]
            p.append(f'<rect class="barcmp" x="{x0}" y="{y+rowh*0.16:.1f}" '
                     f'width="{max(1.5,X(cv)-x0):.1f}" height="{rowh*0.30:.1f}" rx="2"/>')
            p.append(f'<rect class="bar" x="{x0}" y="{y+rowh*0.52:.1f}" '
                     f'width="{max(1.5,X(v)-x0):.1f}" height="{rowh*0.30:.1f}" rx="2"/>')
            p.append(f'<text class="dvalcmp" x="{W-8}" y="{y+rowh*0.72:.1f}" text-anchor="end">{cv:{vfmt}}</text>')
        else:
            # In comparison mode a row with no earlier value still lands here, and it used to
            # keep the blue highlight while every neighbouring row was grey-and-orange. That is
            # the mixed rendering Yifan saw: within one chart, blue meant "the current year" on
            # some rows and "the highlighted row" on others. In comparison mode the bars carry
            # no highlight at all; the emphasis lives in the row label.
            _c = "bar" if cmp_key else f"bar{se}"
            p.append(f'<rect class="{_c}" x="{x0}" y="{y+rowh*0.26:.1f}" width="{max(1.5,X(v)-x0):.1f}" height="{rowh*0.5:.1f}" rx="2"/>')
        p.append(f'<text class="dval{se}" x="{W-66}" y="{y+rowh*0.72:.1f}" text-anchor="end">{v:{vfmt}}</text>')
        # The delta column and the comparison value both sit at x = W-8, so drawing both puts
        # one on top of the other. When a comparison series is shown the change is already IN
        # the chart as a second bar, so the delta column is redundant as well as illegible.
        if not cmp_key and r.get("prev") is not None:
            p.append(f'<text class="ddelta" x="{W-8}" y="{y+rowh*0.72:.1f}" text-anchor="end">{v-r["prev"]:+.0f}</text>')
    p.append("</svg>")
    return "".join(p)

def dumbbell_svg(conds, gkey, active=False):
    """Least- vs most-AI-exposed occupations across working-condition indicators (one gender)."""
    n = len(conds); W, rowh, top, bot = 640, 38, 16, 32
    H = top + n * rowh + bot; x0, x1 = 205, 556
    X = lambda v: x0 + v / 100 * (x1 - x0)
    on = " on" if active else ""
    p = [f'<svg class="rankchart dumb{on}" data-g="{gkey}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Working conditions in least- vs most-AI-exposed occupations, {gkey}">']
    for t in (0, 25, 50, 75, 100):
        gx = X(t)
        p.append(f'<line class="grid" x1="{gx:.1f}" y1="{top}" x2="{gx:.1f}" y2="{top+n*rowh}"/>')
        p.append(f'<text class="tick" x="{gx:.1f}" y="{H-13}" text-anchor="middle">{t}%</text>')
    for i, c in enumerate(conds):
        y = top + i * rowh + rowh * 0.5
        d = c[gkey]; lo, hi = d["lo"], d["hi"]
        p.append(f'<text class="dname" x="192" y="{y+3.5:.1f}" text-anchor="end">{h(c["label"])}</text>')
        p.append(f'<line class="dbtrack" x1="{X(lo):.1f}" y1="{y:.1f}" x2="{X(hi):.1f}" y2="{y:.1f}"/>')
        p.append(f'<circle class="dblo" cx="{X(lo):.1f}" cy="{y:.1f}" r="4"/>')
        p.append(f'<circle class="dbhi" cx="{X(hi):.1f}" cy="{y:.1f}" r="5.5"/>')
        p.append(f'<text class="dval" x="632" y="{y+3.5:.1f}" text-anchor="end">{lo:.0f}→{hi:.0f}</text>')
    p.append("</svg>")
    return "".join(p)

def trend_svg(t):
    """Server-rendered static version of the AI-in-Demand trend (the hero panel is JS-drawn;
    this is the downloadable twin). Solid line to the last final year, dashed to the provisional year."""
    ys = t["years"]; vs = t["values"]; ymax = t["ymax"]; pf = int(t["provisionalFrom"]); n = len(ys)
    W, H = 640, 300
    x0, x1, top, bot = 46, 606, 22, 262
    X = lambda i: x0 + i / (n - 1) * (x1 - x0)
    Y = lambda v: bot - v / ymax * (bot - top)
    pts = [(X(i), Y(vs[i])) for i in range(n)]
    p = [f'<svg class="rankchart trend" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="AI in demand, share of Swedish job ads, {ys[0]} to {ys[-1]}">']
    for tk in t["yticks"]:
        gy = Y(tk)
        p.append(f'<line class="grid" x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}"/>')
        p.append(f'<text class="tick" x="{x0-6}" y="{gy+3.5:.1f}" text-anchor="end">{tk:g}%</text>')
    for i, yr in enumerate(ys):
        if yr % 3 == 0 or i == n - 1:
            p.append(f'<text class="tick" x="{X(i):.1f}" y="{H-8}" text-anchor="middle">{yr}</text>')
    area = " ".join(f'{x:.1f},{y:.1f}' for x, y in pts[:pf]) if pf else ""
    if pf:
        area = f'{pts[0][0]:.1f},{Y(0):.1f} ' + area + f' {pts[pf-1][0]:.1f},{Y(0):.1f}'
        p.append(f'<polygon class="trendarea" points="{area}"/>')
        p.append(f'<polyline class="trendline" points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in pts[:pf])}"/>')
    p.append(f'<polyline class="trenddash" points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in pts[pf-1:])}"/>')
    fv = t.get("floor_values")
    if fv and len(fv) == n:
        fpts = [(X(i), Y(fv[i])) for i in range(n)]
        p.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in fpts[:pf])}" '
                 f'fill="none" stroke="var(--c2)" stroke-width="2"/>')
        p.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in fpts[pf-1:])}" '
                 f'fill="none" stroke="var(--c2)" stroke-width="2" stroke-dasharray="4 3"/>')
    lx, ly = pts[-1]
    p.append(f'<circle class="trenddot" cx="{lx:.1f}" cy="{ly:.1f}" r="4"/>')
    p.append(f'<text class="trendval" x="{lx-6:.1f}" y="{ly-8:.1f}" text-anchor="end">{vs[-1]:.2f}%</text>')
    p.append("</svg>")
    return "".join(p)

def squeeze_svg(els):
    """Two-line time series: the entry-level share of openings in least- vs most-AI-exposed
    occupations. The vertical gap between the lines is the 'squeeze'; it widens over time."""
    s = els["series"]; ymax = int(els["meta"]["ymax"]); n = len(s)
    W, H = 640, 292
    x0, x1, top, bot = 60, 540, 22, 250
    X = lambda i: x0 + i / (n - 1) * (x1 - x0)
    Y = lambda v: bot - v / ymax * (bot - top)
    p = [f'<svg class="rankchart squeeze" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Entry-level share of job openings in least- versus most-AI-exposed occupations, '
         f'{s[0]["year"]} to {s[-1]["year"]}, with a widening gap">']
    for t in range(0, ymax + 1, 10):
        gy = Y(t)
        p.append(f'<line class="grid" x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}"/>')
        p.append(f'<text class="tick" x="{x0-8}" y="{gy+3.5:.1f}" text-anchor="end">{t}%</text>')
    for i, r in enumerate(s):
        p.append(f'<text class="tick" x="{X(i):.1f}" y="{H-12}" text-anchor="middle">{r["year"]}</text>')
    band = " ".join(f'{X(i):.1f},{Y(r["low"]):.1f}' for i, r in enumerate(s))
    band += " " + " ".join(f'{X(i):.1f},{Y(r["high"]):.1f}' for i, r in reversed(list(enumerate(s))))
    p.append(f'<polygon class="sqband" points="{band}"/>')
    lo_pts = " ".join(f'{X(i):.1f},{Y(r["low"]):.1f}' for i, r in enumerate(s))
    hi_pts = " ".join(f'{X(i):.1f},{Y(r["high"]):.1f}' for i, r in enumerate(s))
    p.append(f'<polyline class="sqlo" points="{lo_pts}"/>')
    p.append(f'<polyline class="sqhi" points="{hi_pts}"/>')
    for i, r in enumerate(s):
        p.append(f'<circle class="sqdot lo" cx="{X(i):.1f}" cy="{Y(r["low"]):.1f}" r="2.7"/>')
        p.append(f'<circle class="sqdot hi" cx="{X(i):.1f}" cy="{Y(r["high"]):.1f}" r="2.7"/>')
    last = s[-1]; xl = X(n - 1)
    p.append(f'<text class="sqval lo" x="{xl+8:.1f}" y="{Y(last["low"])+3:.1f}">{last["low"]:.0f}%</text>')
    p.append(f'<text class="sqval hi" x="{xl+8:.1f}" y="{Y(last["high"])+3:.1f}">{last["high"]:.0f}%</text>')
    p.append("</svg>")
    return "".join(p)

def working_conditions_block():
    """Working-environment view (dumbbell + gender lens). A sub-view inside the Outcomes module."""
    w = WORKCOND; mt = w["meta"]; conds = w["conditions"]
    views = "".join(dumbbell_svg(conds, g, active=(g == "all")) for g in ("all", "women", "men"))
    return f"""<div class="grouphdr" id="working-conditions" style="margin-top:36px">Working conditions and AI exposure</div>
  <p class="secintro" style="margin-top:4px">More AI-exposed occupations are the classic "active job": more mentally demanding, but with
    <b>more control</b> over one's work; harder to switch off after hours, yet more meaningful and markedly more
    positive about technology. Public survey data by occupation, set against DAIOE {h(mt['daioe_variant'])}
    ({h(mt['daioe_version'])}); descriptive, not causal, and a single cross-section: more-exposed work is also
    more qualified work, so part of every gap here is occupational composition rather than anything AI does.</p>
  <div class="lensmod">
    <div class="lensbar2"><span class="ll">Gender</span>
      <button class="gbtn on" data-g="all">All</button><button class="gbtn" data-g="women">Women</button><button class="gbtn" data-g="men">Men</button></div>
    <div class="dotwrap">{views}</div>
    <div class="dblegend"><span><i class="lo"></i>least-exposed occupations</span><span><i class="hi"></i>most-exposed occupations</span></div>
  </div>
  {figfooter("working_conditions.csv", f"{mt['wc_source']} × DAIOE {mt['daioe_variant']} {mt['daioe_version']}", svg_name="working_conditions.svg", next_up="with SCB's next work-environment survey wave")}
  <p class="prov" style="margin-top:10px">Toggle gender: the control gap narrows as exposure rises. In low-exposure jobs women
    report far less influence than men (56% vs 68%); in high-exposure jobs it nearly closes (74% vs 78%).</p>"""

def exposure_section():
    """Module 1 — Exposure. Interpretable metric: the share of a country's jobs in the most
    AI-exposed occupations (top DAIOE genai tercile), rather than an abstract mean score."""
    cc = CROSS; mt = cc["meta"]
    se = next(r for r in cc["countries"] if r["is_se"])
    xmax = 10 * (int(max(r["share"] for r in cc["countries"]) // 10) + 1)
    src = (f'DAIOE {mt["variant"]} {mt["daioe_version"]}; most-exposed = top 25% of occupations × Eurostat EU-LFS '
           f'employment {mt["weight_year"]} (a few countries: latest available, marked ’YY)')
    return f"""<div class="rule module-sec" id="exposure"><div class="wrap"><section>
  <p class="kicker">Module 1 · Exposure · which jobs sit in AI’s path</p>
  <h2 class="sec">How much of each country's work is AI-exposed?</h2>
  {folded(f"""<b>{se['share']:.0f}%</b> of Swedish jobs, about four in ten, sit in the most AI-exposed quarter of occupations, and <b>exposure is not displacement</b>: it marks where AI overlaps with the work, not what follows from it. [[note]] DAIOE scores every occupation (ISCO-08) for how far generative AI overlaps with its tasks. We label the <b>top 25% of occupations</b> by that score the most AI-exposed; the bars show the share of each country's jobs in them (Eurostat EU-LFS employment, <b>{h(mt['weight_year'])}</b>; a few countries use their latest year, marked ’YY). On displacement: in the lab's own firm-level panel for Sweden, Denmark and Portugal, exposure shows no robust association with total firm employment, and within firms what it predicts is a shift away from clerical and administrative work rather than broad job loss (AI Unboxed and Jobs, linked below). Where movement has appeared so far, it is in who gets hired rather than in how many: the most exposed occupations hire fewer
    young workers (the Outcomes module below, and the Same Storm, Different Boats paper).""", label="How exposure is measured, and what it says about displacement")}
  <div class="dotwrap">{barplot(nordic(cc['countries']), mt['mean_share'], xmax, mt['weight_year'], 'share', '.0f', mean_label=f"{mt['n_countries']}-country")}</div>
  {figfooter("cross_country.csv", src, "cross_country.svg", next_up="with the DAIOE v2024 release")}
  <div class="depth"><p class="dk">Sweden, in depth</p>
    <p class="secintro" style="margin:0"><b>{se['share']:.0f}%</b> of Swedish jobs are in the most AI-exposed
      occupations (the <b>top 25%</b> by generative-AI exposure), the <b>2nd-highest of {h(mt['n_countries'])}</b>
      countries (mean {mt['mean_share']:.0f}%, seven of them outside the EU). The rank depends on where the line is drawn: Sweden is
      2nd at this quarter cut and at a 30% cut, 3rd at a third, and 5th if only the top 20% of occupations
      count, so read it as among the most exposed rather than as a precise placing.
      The occupation-by-occupation detail lives on the <a href="/daioe/">DAIOE</a> page, and Swedish employment is
      set against exposure over time in the <a href="#occupations-explorer">Occupations Explorer</a> below.</p></div>
  {related_research("exposure")}
</section></div></div>"""

def hero_exposure_panel(method_href, all_href):
    """Compact cross-country exposure chart for the hero. Added 4 Aug 2026.

    Both heroes used to open on the Swedish job-ad series, which taught the eye that this
    is a Swedish site before the reader reached the cards that say international headline,
    Sweden inside. The positioning line ("international context, Sweden in depth") was a
    claim the layout did not support. This figure carries it in one image: the reader sees
    a ranked field of countries and their eye lands on the highlighted Swedish bar.

    Only the leading dozen appear here. The full ranking is ~590px tall and would unbalance
    the hero grid, so it stays in Module 1 and this panel links to it. The caption says
    "among the highest", never a rank: Sweden's placing moves between 2nd and 5th depending
    on where the exposure cut is drawn, and that sensitivity is stated in Module 1."""
    cc = CROSS; mt = cc["meta"]
    rows = cc["countries"][:12]
    se = next(r for r in cc["countries"] if r["is_se"])
    xmax = 10 * (int(max(r["share"] for r in rows) // 10) + 1)
    src = (f'DAIOE {mt["variant"]} {mt["daioe_version"]} × Eurostat EU-LFS employment {mt["weight_year"]} · '
           f'{mt["n_countries"]} countries, leading 12 shown')
    return f"""<div class="panel">
    <div class="panelhead"><span class="ttl">AI exposure · share of jobs in the most exposed occupations</span>
      <span class="vint">{h(mt['n_countries'])} countries</span></div>
    <div class="panelbody">
      <p class="psub"><b>{se['share']:.0f}%</b> of Swedish jobs sit in the most AI-exposed quarter of occupations,
        among the highest of {h(mt['n_countries'])} countries (mean {mt['mean_share']:.0f}%). Exposure marks
        where AI overlaps with the work, not what follows from it.</p>
      <div class="dotwrap">{barplot(rows, mt['mean_share'], xmax, mt['weight_year'], 'share', '.0f', mean_label=f"{mt['n_countries']}-country")}</div>
      {figfooter("cross_country.csv", src, "cross_country.svg", method_href=method_href)}
      <p style="margin:12px 0 0"><a class="mono" style="font-size:12px" href="{all_href}">All {h(mt['n_countries'])} countries →</a></p>
    </div></div>"""

def sweden_trend_panel(method_href, title="Sweden, in depth · AI in Demand · share of Swedish job ads"):
    """The Swedish AI-in-Demand series. Moved out of the hero on 4 Aug 2026 and placed
    directly beneath it, where it reads as what it is: the depth cut that follows the
    international opener, and the one series here no other country's monitor can produce.

    The title is overridable because on the home page this panel sits under a heading that
    already says "Sweden, in depth", and repeating it two lines apart reads as an oversight."""
    # The headline sentence is computed from the same trend data the chart draws, never typed
    # in: hardcoded values here survived two freezes unchanged (still v1.1's 1.07%/0.52% after
    # the v1.3 move) until an external reviewer caught the mismatch against the stat tiles.
    t = TREND["trend"]; pf = t["provisionalFrom"]
    yr_c, ai_c, fl_c = t["years"][pf - 1], t["values"][pf - 1], t["floor_values"][pf - 1]
    yr_p, ai_p, fl_p = t["years"][-1], t["values"][-1], t["floor_values"][-1]
    tm = TREND["meta"]
    return f"""<div class="panel">
    <div class="panelhead"><span class="ttl">{h(title)}</span>
      <span class="livechip"><i></i>live</span></div>
    <div class="panelbody"><p class="psub">Ads naming a specific AI skill anywhere in the ad reached <b>{ai_c:.2f}%</b> in {yr_c},
        {tm["multiple"]:.0f} times the pooled {h(tm["base_years"]).replace("-", "\u2013")} level; the strict floor, ads asking for AI in the job's own requirements, reached
        <b>{fl_c:.2f}%</b>. Both set records in the post-2023 rebound, with generative-AI skills now 27% of the demand,
        and {yr_p} so far runs higher still ({ai_p:.2f}%, floor {fl_p:.2f}%, provisional).</p>
      <svg id="trend" viewBox="0 0 640 300" role="img" aria-label="Share of Swedish job ads naming or asking for AI skills, 2006 onwards"></svg>
      <div class="legend"><span><i style="background:var(--c1)"></i>Names an AI skill</span>
        <span><i style="background:var(--c2)"></i>Asks for AI in the role (floor)</span>
        <span class="mono" style="color:var(--muted);font-size:11px">╌ newest point provisional</span></div>
      {figfooter("ai_in_demand_trend.csv", f"JobTech / Platsbanken job ads (CC0), 2006 onwards · {h(tm['definition'])} term list · distinct advertisements", svg_name="ai_in_demand_trend.svg", method_href=method_href, next_up="tier split: built, integrated or simply used")}</div></div>"""

def livewindow_block():
    """The live 60-day window as its own labelled instrument. Never a point on the archive
    line: the JobStream flow is a different subset of ads and runs higher in level (splice
    check 2026-07-24), so the honest presentation is side-by-side, not spliced.

    The first sentence is COMPOSED from the figures, not stored beside them. It used to be one
    hand-written `sentence:` carrying "32,022", "1.57" and "0.80" as literal characters, which
    meant a refresh that advanced `asof` would have moved the date over three frozen numbers --
    strictly worse than being visibly stale, because the staleness would no longer show. The
    framing that follows is genuine prose about the two instruments and stays in monitor.yaml
    as `note`; it makes no numeric claim, so it does not need generating.

    When the window is behind, the block says so in the chip rather than dropping the numbers:
    a figure with an honest old date is worth more to a reader than a gap."""
    lw = LIVEWINDOW
    if not lw or lw.get("n") is None:
        return ""
    n = f"{int(lw['n']):,}"
    lead = (f"Of the {n} most recent job ads, {float(lw['names_pct']):.2f}% name a specific AI "
            f"skill and {float(lw['floor_pct']):.2f}% ask for one in the job itself")
    ci = ""
    if lw.get("names_ci") and lw.get("floor_ci"):
        nlo, nhi = lw["names_ci"]; flo, fhi = lw["floor_ci"]
        ci = (f" (95% intervals {float(nlo):.2f}–{float(nhi):.2f} and "
              f"{float(flo):.2f}–{float(fhi):.2f})")
    note = lw.get("note") or ""
    age = LIVEWINDOW_AGE
    chip = (f"last {int(lw.get('window_days', 60))} days, as of {h(str(lw['asof']))}"
            if LIVE_OK else
            f"last {int(lw.get('window_days', 60))} days, as of {h(str(lw['asof']))} · "
            f"not refreshed for {age} days")
    cls = "livechip" if LIVE_OK else "livechip stale"
    return f"""<div class="grouphdr" style="margin-top:26px">Right now · the live feed
      <span class="{cls}"><i></i>{chip}</span></div>
    <p class="secintro" style="margin-top:4px">{h(lead + ci + ".")} {h(note)}</p>"""


def titles_block():
    """Top occupation names among AI-skill ads + taxonomy-level churn (newcomers/cooled).
    Free-text titles (true neologisms) wait for the extraction layer; keep the flag honest."""
    tt = MONITOR.get("titles")
    if not tt:
        return ""
    tops = "".join(
        f'<div class="prod"><h3>{y["year"]}</h3><p>{h(" · ".join(y["items"]))}</p></div>'
        for y in tt["top"])
    def lst(block):
        return (f'<div class="prod"><h3>{h(block["label"])}</h3>'
                f'<p>{h(", ".join(block["items"]))}</p></div>')
    return f"""<div class="grouphdr" style="margin-top:26px">Who asks? Top advertisement titles
      <span class="preview-flag">◔ {h(tt['flag'])}</span></div>
    <p class="secintro" style="margin-top:4px">{h(tt['intro'])}</p>
    <div class="two" style="grid-template-columns:1fr 1fr 1fr">{tops}</div>
    <div class="two" style="grid-template-columns:1fr 1fr;margin-top:10px">{lst(tt['newcomers'])}{lst(tt['cooled'])}</div>
    <p class="psub" style="margin-top:6px">{h(tt['caveat'])}</p>"""



def monthly_svg(md):
    """The AI-skill share of Swedish vacancies at monthly resolution, 2006 to now.

    Faint line = the raw month, which is genuinely noisy (Swedish hiring collapses every July
    and again in December). Bold line = the 12-month trailing mean. Both are drawn because
    showing only the smoothed line would hide how little weight one month carries."""
    s = md["series"]; n = len(s); ymax = md["meta"]["ymax"]
    W, H = 640, 300
    x0, x1, top, bot = 46, 606, 22, 256
    X = lambda i: x0 + i / (n - 1) * (x1 - x0)
    Y = lambda v: bot - min(v, ymax) / ymax * (bot - top)
    p = [f'<svg class="rankchart monthly" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Share of Swedish job ads requiring an AI skill, by month, '
         f'{md["meta"]["first"]} to {md["meta"]["last"]}">']
    v = 0.0
    while v <= ymax + 1e-9:
        gy = Y(v)
        p.append(f'<line class="grid" x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}"/>')
        p.append(f'<text class="tick" x="{x0-6}" y="{gy+3.5:.1f}" text-anchor="end">{v:g}%</text>')
        v += 0.5
    for i, r in enumerate(s):
        yy, mm = r["m"].split("-")
        if mm == "01" and int(yy) % 3 == 0:
            p.append(f'<text class="tick" x="{X(i):.1f}" y="{H-8}" text-anchor="middle">{yy}</text>')
    # November 2022 is dated, not claimed: the marker says when the tool arrived, nothing about cause.
    for i, r in enumerate(s):
        if r["m"] == "2022-11":
            p.append(f'<line x1="{X(i):.1f}" y1="{top}" x2="{X(i):.1f}" y2="{bot}" '
                     f'stroke="var(--ink)" stroke-width="1" stroke-dasharray="3 3" opacity=".35"/>')
            p.append(f'<text class="tick" x="{X(i)+5:.1f}" y="{top+10}" text-anchor="start" '
                     f'opacity=".65">ChatGPT released</text>')
            break
    raw = " ".join(f'{X(i):.1f},{Y(r["ai"]):.1f}' for i, r in enumerate(s))
    p.append(f'<polyline points="{raw}" fill="none" stroke="var(--c1)" stroke-width="1" opacity=".32"/>')
    for key, colour in (("floor_ma", "var(--c2)"), ("ai_ma", "var(--c1)")):
        pts = " ".join(f'{X(i):.1f},{Y(r[key]):.1f}' for i, r in enumerate(s))
        p.append(f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="2.2"/>')
    lx, ly = X(n - 1), Y(s[-1]["ai_ma"])
    p.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="var(--c1)"/>')
    p.append(f'<text class="trendval" x="{lx-6:.1f}" y="{ly-9:.1f}" text-anchor="end">'
             f'{md["meta"]["last_ma"]:.2f}%</text>')
    p.append("</svg>")
    return "".join(p)


def monthly_block():
    """The annual series at monthly cadence: what turns a yearbook into a tracker."""
    m = MONTHLY["meta"]
    return (f'<div class="grouphdr" style="margin-top:26px">Month by month, {h(m["first"])} to '
            f'{h(m["last"])}</div>\n'
            f'<p class="secintro" style="margin-top:4px">The same measure at monthly resolution, '
            f'{m["n_months"]} months built on <b>{m["total_ads"]:,}</b> distinct advertisements. The faint line is the raw '
            f'month and the bold lines are 12-month trailing means: broad AI demand in blue, the narrower '
            f'skill floor in orange. A single month carries little weight, because Swedish hiring falls '
            f'sharply every July and again in December, so the trend is the line to read. The broad measure '
            f'now stands at <b>{m["last_ma"]:.2f}%</b> on that basis, against '
            f'<b>{m["last_floor_ma"]:.2f}%</b> for the floor.</p>\n'
            # The two-lines explainer sits with this chart (moved 12 Aug 2026, Lydia's review):
            # it had floated between the stat tiles and this section, two scrolls from either
            # chart that actually draws the two lines.
            + f'<p class="psub" style="margin-top:6px">{h(MONITOR["captions"]["guard"])}</p>\n'
            + note(
                '<b>This chart, like the whole Monitor, counts each distinct advertisement once.</b> '
                'That matters for the 2022 to 2023 dip: Swedish employers, mostly staffing, care and '
                'door-to-door sales agencies, repost the same advertisement many times, and that practice '
                'grew sharply and then receded. Counted this way the share drifts 7% from 2021 to 2023, '
                'against the 30% collapse a raw record count shows. The rise since 2024 survives either way.',
                'Repeat postings are 13% of all records in 2008, 33% in 2021, 49% in 2023 and 29% in 2025. '
                'Because AI ads are repeated at about half that rate, the denominator swells faster than the '
                'numerator exactly when the dip appears. On distinct advertisements the share runs 0.81% in '
                '2021, 0.78% in 2022 and 0.75% in 2023; the raw-record series is kept alongside as the '
                'robustness line. Total advertisement volume also fell over the same period as hiring cooled '
                'with the rate rises that began in April 2022 (the downturn our Same Storm, Different Boats '
                'paper works with), so the denominator moves with the cycle as well.',
                'Where the dip goes when you count each advertisement once')
            + f'<div class="dotwrap">{monthly_svg(MONTHLY)}</div>\n'
            # Three lines on the flagship chart were identified only in prose, by colour name.
            # A legend beats "the blue line" for anyone reading out of order, printing, or
            # colour-blind; the faint raw series needed naming most, since it is the one a
            # reader mistakes for noise in the data rather than in hiring.
            + '<div class="dblegend">'
              '<span><i style="background:var(--c1)"></i>names an AI skill, 12-month mean</span>'
              '<span><i style="background:var(--c2)"></i>asks for it in the role (floor), 12-month mean</span>'
              '<span><i style="background:var(--c1);opacity:.32"></i>single month, unsmoothed</span>'
              '</div>\n'
            + figfooter("monthly_ai_share.csv",
                        # The monthly block states the definition IT was built from, which is
                        # not necessarily the site's. DEF_LABEL here is what let a v1.4 monthly
                        # series be published under a v1.5 footer on 19 Aug 2026.
                        f'{h(m["source"])}, {h(m["first"])} to {h(m["last"])} · '
                        f'{h(m.get("definition", DEF_LABEL))} term list · distinct advertisements',
                        "monthly_ai_demand.svg"))


def jobquality_svg(jq):
    """Three gap lines in percentage points: AI-skill ads minus everything else, on full-time,
    permanent and regular employment. Zero is drawn heavy, because the permanent line crosses it."""
    s = jq["series"]; n = len(s)
    lo, hi = jq["meta"]["ymin"], jq["meta"]["ymax"]
    W, H = 640, 300
    x0, x1, top, bot = 52, 522, 24, 254
    X = lambda i: x0 + i / (n - 1) * (x1 - x0)
    Y = lambda v: bot - (v - lo) / (hi - lo) * (bot - top)
    p = [f'<svg class="rankchart jobq" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Gap in percentage points between AI-skill job ads and all other ads on '
         f'full-time, permanent and regular employment, {s[0]["year"]} to {s[-1]["year"]}">']
    t = lo - (lo % 5)
    while t <= hi:
        gy = Y(t)
        p.append(f'<line class="grid" x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}"/>')
        p.append(f'<text class="tick" x="{x0-7}" y="{gy+3.5:.1f}" text-anchor="end">{t:+g}</text>'.replace(">+0<", ">0<"))
        t += 5
    zy = Y(0)
    p.append(f'<line x1="{x0}" y1="{zy:.1f}" x2="{x1}" y2="{zy:.1f}" stroke="var(--ink)" '
             f'stroke-width="1.4" opacity=".55"/>')
    for i, r in enumerate(s):
        p.append(f'<text class="tick" x="{X(i):.1f}" y="{H-10}" text-anchor="middle">{r["year"]}</text>')
    for key, colour, lab in (("ft_gap", "var(--c1)", "full-time"),
                             ("pm_gap", "var(--c2)", "permanent"),
                             ("rg_gap", "var(--c3)", "regular")):
        pts = " ".join(f'{X(i):.1f},{Y(r[key]):.1f}' for i, r in enumerate(s))
        p.append(f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="2.4"/>')
        ly = Y(s[-1][key])
        p.append(f'<circle cx="{X(n-1):.1f}" cy="{ly:.1f}" r="3.5" fill="{colour}"/>')
        p.append(f'<text class="tick" x="{X(n-1)+7:.1f}" y="{ly+3.5:.1f}" text-anchor="start" '
                 f'fill="{colour}">{lab} {s[-1][key]:+.0f}</text>')
    p.append("</svg>")
    return "".join(p)


def jobquality_block():
    """Job quality in AI-skill ads: the premium is narrowing, and on contracts it has reversed."""
    m = JOBQ["meta"]
    return (f'<div class="grouphdr" style="margin-top:26px">Are AI jobs better jobs?</div>\n'
            f'<p class="secintro" style="margin-top:4px">Job ads carry structured fields describing the post '
            f'itself, so we can ask whether a vacancy that requires an AI skill offers better terms than '
            f'everything else advertised the same year. The chart shows the gap in percentage points, '
            f'AI-skill ads minus all other ads, on three measures.</p>\n'
            f'<div class="dotwrap">{jobquality_svg(JOBQ)}</div>\n'
            + note(
                f'AI-skill posts have always been more often full-time, but the advantage is closing: '
                f'<b>{m["ft_gap_first"]:+.0f}pp</b> in {m["first_year"]} against '
                f'<b>{m["ft_gap_last"]:+.0f}pp</b> in {m["last_year"]}. On permanent contracts the advantage '
                f'has not merely narrowed, it has <b>reversed</b>: AI-skill ads were '
                f'{m["pm_gap_first"]:+.0f}pp more often open-ended in {m["first_year"]}, and '
                f'{m["pm_gap_last"]:+.0f}pp less often by {m["last_year"]}. Read this as description, not as '
                f'a finding about what AI does to job quality: <b>composition alone could produce the whole '
                f'reversal</b>, and nothing here holds occupation fixed.',
                f'The series crossed zero in {m["pm_flip_year"]}. It does not compare like with like, because '
                f'AI-skill ads sit in different occupations from the average vacancy and AI demand has been '
                f'spreading out of a specialist niche into ordinary hiring over exactly this period. What the '
                f'series does survive is deduplication: counting each advertisement once rather than once per '
                f'posting moves every gap by under 2pp, so it is not an artefact of employers reposting.',
                'Why composition could explain this, and what it survives')
            # job_quality.csv, not job_quality_v11.csv. The _v11 name is the SOURCE file in
            # the ai-monitor repo (data/free_cuts/job_quality_v11.csv); this footer offers a
            # public download, and the export below writes job_quality.csv. The two names
            # diverged, so every reader who clicked it got a 404 and Search Console reported
            # "Blocked due to other 4xx issue" on 7 Aug 2026. scripts/check_links.py now fails
            # the build on any internal link that does not resolve.
            + figfooter("job_quality.csv",
                        f'{h(m["source"])}, {m["first_year"]} to {m["last_year"]} · complete years only'
                        f' · distinct advertisements',
                        "job_quality.svg"))


def governance_svg(g):
    """Counts, not shares: the band is small enough that a share hides the shape."""
    s = g["series"]; n = len(s); ymax = g["meta"]["ymax"]
    # H allows two label rows below the plot: the year, and the part-year note under it.
    W, H = 640, 276
    x0, x1, top, bot = 52, 560, 22, 214
    bw = (x1 - x0) / n * 0.62
    Y = lambda v: bot - v / ymax * (bot - top)
    p = [f'<svg class="rankchart gov" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Job ads in the AI governance and compliance band, '
         f'{s[0]["year"]} to {s[-1]["year"]}">']
    for t in range(0, ymax + 1, 50):
        gy = Y(t)
        p.append(f'<line class="grid" x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}"/>')
        p.append(f'<text class="tick" x="{x0-7}" y="{gy+3.5:.1f}" text-anchor="end">{t}</text>')
    for i, r in enumerate(s):
        cx = x0 + (i + 0.5) * (x1 - x0) / n
        y = Y(r["n"])
        partial = r.get("partial")
        p.append(f'<rect x="{cx-bw/2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bot-y:.1f}" '
                 f'fill="var(--c1)"{' opacity="0.55"' if partial else ''}/>')
        p.append(f'<text class="tick" x="{cx:.1f}" y="{y-5:.1f}" text-anchor="middle">{r["n"]}</text>')
        p.append(f'<text class="tick" x="{cx:.1f}" y="{H-28}" text-anchor="middle">'
                 f'{r["year"]}{"*" if partial else ""}</text>')
        if partial:
            # A half-year bar drawn at full height, taller than the full year before it, needs
            # to say so inside the figure: the asterisk had no key anywhere on the page. It sits
            # UNDER THE YEAR it annotates. It used to sit at the top of the plot, where it
            # collided with the value label of any bar tall enough to reach it -- which the 2026
            # bar was, exactly (Magnus, 4 Aug).
            p.append(f'<text class="tick" x="{cx:.1f}" y="{H-13}" text-anchor="middle" '
                     f'style="font-size:8.5px">part-year (H1)</text>')
    p.append("</svg>")
    return "".join(p)


def governance_block():
    m = GOV["meta"]
    return ('<div class="grouphdr" style="margin-top:26px">How fast is AI-governance language '
            'entering job ads?</div>\n'
            '<p class="secintro" style="margin-top:4px">A separate band counts ads that mention '
            'the vocabulary of AI <b>governance</b>: responsible AI, AI ethics, AI safety, AI '
            'governance and the AI Act. It has been computed since the series began and never '
            'shown. There were none in '
            f'2018 and {m["last_n"]} in the whole of {m["last_year"]}; the first half of 2026 '
            f'alone has <b>{m["h1_2026_n"]}</b>, which is {m["h1_2026_pct"]:.1f}% of all AI ads '
            f'against {m["last_pct"]:.1f}% across {m["last_year"]} as a whole: the share has nearly '
            'doubled in half a year.</p>\n'
            + note(
                '<b>Read this as language, not as jobs.</b> Unlike our headline series, this band '
                'counts any mention rather than a requirement of the role, and <b>a hand-check of every '
                'ad in the 2026 band found that 95% mention governance only in passing</b>, usually an '
                'employer\u2019s boilerplate about building responsible AI in posts for engineers, project '
                'managers and designers. What is rising fast is how often the language of AI regulation '
                'appears in Swedish hiring copy, which is worth knowing. It is not a count of governance '
                'jobs, and we do not have one.',
                'Only ten of those ads name governance in the headline. The hand-check read the 199 '
                'RECORDS in the band; the chart plots the 185 distinct advertisements they reduce to, '
                'a difference of 14 repeat postings. The hand-check called 33 of the 199 repeats, which '
                'is more than the deduplication finds, because it recognised as the same posting some '
                'advertisements that differ in headline, employer name or opening text \u2014 the fields '
                'the dedup key uses. The published figure is therefore the conservative one.',
                'What the hand-check of all 199 ads found')
            + f'<div class="dotwrap">{governance_svg(GOV)}</div>\n'
            + figfooter("ai_governance.csv",
                        f'{h(m["source"])}, {m["first_year"]} to first half of 2026'
                        f' · distinct advertisements',
                        "ai_governance.svg"))


def vocabulary_svg(v):
    """Four families as a share of all term hits, period by period. The point of the chart is
    that the early periods are dominated by words nobody uses now."""
    s = v["series"]; n = len(s)
    W, H = 640, 300
    x0, x1, top, bot = 46, 486, 22, 252
    ymax = 70
    X = lambda i: x0 + i / (n - 1) * (x1 - x0)
    Y = lambda val: bot - min(val, ymax) / ymax * (bot - top)
    p = [f'<svg class="rankchart vocab" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Share of AI term matches by vocabulary family, {s[0]["p"]} to {s[-1]["p"]}">']
    for t in range(0, ymax + 1, 10):
        gy = Y(t)
        p.append(f'<line class="grid" x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}"/>')
        p.append(f'<text class="tick" x="{x0-6}" y="{gy+3.5:.1f}" text-anchor="end">{t}%</text>')
    for i, r in enumerate(s):
        if r["p"].isdigit() and int(r["p"]) % 4 == 0:
            p.append(f'<text class="tick" x="{X(i):.1f}" y="{H-8}" text-anchor="middle">{r["p"]}</text>')
    # Five families since 19 Aug 2026. autonomy was the ENTIRE unplotted residual -- true
    # "other" is 0.0% in every period -- so the caption's "up to 17% fall outside these four
    # families" was a sentence about one named thing the chart declined to name. Its shape is a
    # finding: 17.2% of term hits in 2016, 0.9% by 2026-Q2, displaced by ML and then generative.
    lines = (("ml", "var(--c1)", "machine learning"),
             ("early", "var(--c2)", "early terms"),
             ("genai", "var(--c3)", "generative"),
             ("generic", "var(--c4)", "\u0022AI\u0022 itself"),
             ("autonomy", "var(--warn)", "robotics & autonomy"))
    for key, colour, _ in lines:
        pts = " ".join(f'{X(i):.1f},{Y(r[key]):.1f}' for i, r in enumerate(s))
        p.append(f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="2.2"/>')
        p.append(f'<circle cx="{X(n-1):.1f}" cy="{Y(s[-1][key]):.1f}" r="3.5" fill="{colour}"/>')
    # end labels collide when two families finish at a similar level; push them apart
    placed = []
    for key, colour, lab in sorted(lines, key=lambda L: Y(s[-1][L[0]])):
        ly = Y(s[-1][key])
        while any(abs(ly - q) < 12 for q in placed):
            ly += 12
        placed.append(ly)
        p.append(f'<text class="tick" x="{X(n-1)+7:.1f}" y="{ly+3.5:.1f}" text-anchor="start" '
                 f'fill="{colour}">{lab}</text>')
    p.append("</svg>")
    return "".join(p)


def vocabulary_block():
    m = VOCAB["meta"]
    return ('<div class="grouphdr" style="margin-top:26px">Is this a 2026 word list applied '
            'backwards?</div>\n'
            '<p class="secintro" style="margin-top:4px">The standing objection to any long AI '
            'series is that today\u2019s vocabulary is being read into yesterday\u2019s ads. The '
            'ads answer it. In 2006 the words were '
            f'<b>{m["early_first"]:.0f}%</b> data mining, expert systems and their kin, terms '
            f'almost nobody advertises for now ({m["early_last"]:.1f}% in the latest period). '
            'Machine-learning vocabulary took over from about 2016, and the generative vocabulary '
            f'is absent before 2022 and is <b>{m["genai_last"]:.0f}%</b> of all term matches '
            'today. The list is not anachronistic; the language turned over, and the measure '
            'follows it.</p>\n'
            f'<div class="dotwrap">{vocabulary_svg(VOCAB)}</div>\n'
            '<p class="psub" style="margin-top:6px">Shares of '
            f'{m["total_term_hits"]:,} term matches, in five families that between them account '
            'for every match. For display, product '
            'names and words with an older everyday sense are counted only from the year they '
            'acquired their AI meaning, so the chart does not show a 2006 ad matching a model '
            'released in 2023; the published series is frozen and unchanged.</p>\n'
            + figfooter("vocabulary.csv", f'{h(m["source"])}, {m["first"]} to {m["last"]}',
                        "vocabulary.svg"))


def occupations_block():
    """Where AI demand actually sits. The national share is an average over a very skewed
    distribution; this is the distribution. Reuses barplot with the national floor as the
    reference line, so every bar is read against the headline number."""
    o = OCCUP
    m = o["meta"]
    xmax = int(max(r["share"] for r in o["top"])) + 1
    bars = barplot(o["top"] + o["zero"], m["national"], xmax, 0, "share", ".1f",
                   mean_label="Sweden")
    return f"""<div class="grouphdr" id="occupations" style="margin-top:30px">Where the demand sits
      <span class="preview-flag">◔ Occupations · {h(str(m['year']))}</span></div>
    <p class="secintro" style="margin-top:4px">{h(o['lede'])}</p>
    <div class="dotwrap">{bars}</div>
    <p class="psub" style="margin-top:6px">{h(o['caveat'])} The line marks the national figure,
      {m['national']}%.</p>
    {figfooter("occupations_ai_demand.csv", f"{h(m['source'])} · {h(str(m['year']))}",
               svg_name="occupations_ai_demand.svg",
               next_up="annually, with the JobTech year files")}"""


def occupation_tiers_block():
    """The builder/integrator/user split cut by occupation. A compact table rather than a chart:
    three shares per row that deliberately do not sum to 100, which a stacked bar would hide."""
    t = OCCTIER; m = t["meta"]
    # Same shortening as the charts, and for the same reader: five columns and a 43-character
    # title in the first one leaves the numbers nothing to sit in on a phone. A cell can wrap
    # where an SVG label cannot, so this is a smaller problem than the chart's -- but it is
    # the same problem, and a title attribute keeps the official label one hover away.
    def _cell(name):
        short = shorten(name)
        return (f'<td title="{h(name)}">{h(short)}</td>' if short != name
                else f'<td>{h(name)}</td>')

    body = "".join(
        f'<tr>{_cell(str(r["name"]))}<td>{r["n"]}</td><td>{r["builder"]}%</td>'
        f'<td>{r["integrator"]}%</td><td>{r["user"]}%</td></tr>' for r in t["rows"])
    return f"""<div class="grouphdr" id="occupation-tiers" style="margin-top:30px">Who is the AI for, by occupation
      <span class="preview-flag">◔ Classifier · {h(str(m['year']))}</span></div>
    <p class="secintro" style="margin-top:4px">{h(t['lede'])}</p>
    <table class="minitab"><thead><tr><th>Occupation</th><th>AI ads</th><th>Builds</th>
      <th>Integrates</th><th>Uses</th></tr></thead><tbody>{body}</tbody></table>
    <p class="psub" style="margin-top:6px">{h(t['caveat'])} {h(m['validation'])}.</p>
    {figfooter("occupation_tiers.csv", f"{h(m['source'])} · {h(str(m['year']))}",
               next_up="annually, with the JobTech year files")}"""

def demand_section(tiles, seg):
    """Module 2 — Demand. Headline is the cross-country demand bar; Sweden's live measure is the depth cut."""
    dm = DEMAND; dmt = dm["meta"]
    dxmax = int(max(r["share"] for r in dm["countries"])) + 1  # demand share, tight axis
    return f"""<div class="rule module-sec" id="demand"><div class="wrap"><section>
  <p class="kicker">Module 2 · Demand · what employers ask for</p>
  <h2 class="sec">How much are employers hiring for AI?</h2>
  <p class="secintro">The share of job postings that require AI skills, by country in <b>{h(dmt['year'])}</b>
    ({h(dmt['source'])}), Sweden marked. {h(dmt['note_prev'])} This international series (Lightcast) is a separate
    source from the lab's own Swedish measure below, so their levels are not directly comparable.</p>
  <div class="dotwrap">{barplot(dm['countries'], 0, dxmax, 0, 'share', '.1f')}</div>
  {figfooter("cross_country_demand.csv", f"{dmt['source']}, {dmt['year']} · {dmt['unit']}", "cross_country_demand.svg", next_up="Stanford AI Index 2027 (spring 2027)")}


  <div class="depth" id="ai-in-demand"><p class="dk">Sweden, in depth · our live measure</p>
    {folded(f"""{h(MONITOR['aiindemand_lede'])} We read every open and historical Swedish job ad """
             f"""(JobTech / Platsbanken, 2006 onwards) with a versioned, citable term list, so the level and its """
             f"""{TREND['meta']['multiple']:.0f}-fold rise from the pooled """
             f"""{TREND['meta']['base_years'].replace('-', '\u2013')} base to """
             f"""{TREND['meta']['last_full_year']} are reproducible. [[note]] Employers repost, so the archive holds """
             f"""<b>{RECORD_ADS[:-1]} million</b> records but <b>{DISTINCT_ADS[:-1]} million</b> distinct """
             f"""advertisements; we count each advertisement once. Two corrections since the first release both """
             f"""raised the rise rather than lowered it: repeat postings inflated the denominator, and a handful """
             f"""of early ads matched product names that did not yet exist.""", style="margin:0 0 4px", label="How the advertisements are read, and the two corrections since")}
    {folded(f"""{h(MONITOR['captions']['scope'].split('.', 1)[1].split('.')[0])}.[[note]]"""
             f"""{h('.'.join(MONITOR['captions']['scope'].split('.')[2:]))}""", cls="psub",
             style="margin:8px 0 0", label="What this measures, and what it does not")}
    <div class="tiles">{tiles}</div>
    {figfooter("ai_in_demand_trend.csv", f"JobTech / Platsbanken job ads (CC0), 2006 onwards · {TREND['meta']['definition']} term list · distinct advertisements", svg_name="ai_in_demand_trend.svg", next_up="tier split: built, integrated or simply used")}
    {monthly_block()}
    {livewindow_block()}
    {occupations_block()}
    {occupation_tiers_block()}
    {governance_block()}
    {vocabulary_block()}
    {titles_block()}
    <div class="grouphdr" style="margin-top:26px">Coming next · who is the AI for?
      <span class="preview-flag">◔ {h(MONITOR['segmentation']['flag'])}</span></div>
    <p class="secintro" style="margin-top:4px">{h(MONITOR['segmentation']['intro'])}</p>
    <div class="two" style="grid-template-columns:1fr 1fr 1fr">{seg}</div>
  </div>
  {related_research("demand")}
</section></div></div>"""


def nordic_size_panels():
    """The firm-size cut across the Nordics, as four small multiples on a shared axis.

    Four panels, not one sixteen-row chart. Country crossed with size class is where a Nordic
    version actually gets messy, and stacking every row in one chart makes the within-country
    gradient unreadable while adding nothing. Panels keep the countries comparable because the
    axis does not move, and unlike a toggle they survive print.

    Full width, one per row: barplot sizes its label gutter and value column in fixed pixels
    inside a 640-unit viewBox, so at half width the text collides with the bars. A compact mode
    is the proper fix; until it exists, full width is the correct one.
    """
    xmax = 10 * (int(max(z["adoption"] for c in NORDSZ["countries"] for z in c["sizes"]) // 10) + 1)
    out = []
    for c in NORDSZ["countries"]:
        chart = barplot(c["sizes"], 0, xmax, 0, "adoption", ".1f", what="size classes",
                        cmp_key="prev", series_label=str(NORDSZ["meta"]["year"]),
                        cmp_label=str(NORDSZ["meta"]["prev_year"]))
        mark = ' style="font-weight:700"' if c["is_se"] else ""
        out.append(f'<figure style="margin:0 0 6px"><figcaption class="dk"{mark}>'
                   f'{h(c["name"])} · {c["headline"]:g}%</figcaption>{chart}</figure>')
    return "".join(out)

def adoption_section():
    """Module 3 — Adoption. Cross-country firm AI-adoption (Eurostat), then two depth cuts:
    Sweden by firm size from SCB, and the Nordics by firm size from Eurostat."""
    ad = ADOPT; amt = ad["meta"]
    se = next(r for r in ad["countries"] if r["is_se"])
    swm = SWEAD["meta"]; sm = {r["code"]: r["adoption"] for r in SWEAD["sizes"]}
    swxmax = 10 * (max(r["adoption"] for r in SWEAD["sizes"]) // 10 + 1)    # round up to 10
    xmax = 5 * (int(max(r["adoption"] for r in ad["countries"]) // 5) + 1)  # round up to 5
    return f"""<div class="rule module-sec" id="adoption"><div class="wrap"><section>
  <p class="kicker">Module 3 · Adoption · who is actually using it</p>
  <h2 class="sec">How widely has AI actually been adopted?</h2>
  <p class="secintro">Exposure is potential; adoption is what firms have done. Adoption is climbing fast: the EU
    average rose from 8% in 2023 to {h(amt['eu_avg'])}% in {h(amt['year'])}, and exposure and adoption need not
    line up across countries.</p>
  <details class="note"><summary>Three levels, three denominators</summary>
    <p><b>Three levels, three denominators.</b> Firms adopt, workers use AI at work, and the population uses it at
    all. Each is measured on a different population, so the three are never set side by side here. Firms come first below, then workers, then the population. The weakest of
    the three is the worker level: Sweden has no representative public statistic for the share of employed people
    who use AI at work, so what we can show is a professional-union panel, labelled as such.</p>
    <p>The bars are the share of enterprises using at least one AI technology, with the year-on-year change since
    {h(amt['prev_year'])} shown as <b>+pp</b>.</p></details>
  <div class="dotwrap">{barplot(nordic(ad['countries']), amt['eu_avg'], xmax, amt['year'])}</div>
  {figfooter("cross_country_adoption.csv", f"{amt['source']}, {amt['year']} (change vs {amt['prev_year']}) · {amt['unit']}", "cross_country_adoption.svg", next_up="Eurostat 2026 wave (expected around year-end)")}
  <div class="depth"><p class="dk">Sweden, in depth · by firm size</p>
    <p class="secintro" style="margin:0 0 14px">Sweden is among the EU leaders at <b>{se['adoption']:g}%</b> in
      {h(amt['year'])}, and adoption climbs steeply with the size of the firm, from <b>{sm['10-49']}%</b> of small
      firms to <b>{sm['250-']}%</b> of large ones. <b>The headline ({sm['Tot250']}%) is a figure for firms with ten
      or more employees</b>, and among the smallest firms adoption is roughly half that, which is worth knowing
      before it is read as a national rate.</p>
    <details class="note"><summary>Why the headline stops at ten employees</summary>
      <p>Eurostat's population stops at ten employees and it publishes no EU figure for anything smaller. SCB
      surveys firms from no employees upward, so the three rows below the headline are ones almost no other country
      can show: Sweden was one of two countries reporting the 0–9 class to Eurostat for {h(swm['year'])}.</p>
      <p>The highlighted row is the same number the cross-country bar above shows. Every class is up sharply since
      {h(swm['prev_year'])}.</p></details>
    <div class="dotwrap">{barplot(SWEAD['sizes'], sm['Tot250'], swxmax, 0, 'adoption', '.0f', what='firm-size classes', mean_label='Sweden 10+')}</div>
    {figfooter("swe_adoption.csv", f"{swm['source']}, {swm['year']} (change vs {swm['prev_year']}) · {swm['unit']}; reference line is the Swedish 10+ headline, {sm['Tot250']}%", svg_name="swe_adoption.svg", next_up="with SCB's next ICT-in-enterprises wave")}
  </div>
  <div class="depth"><p class="dk">The Nordics, in depth · by firm size</p>
    <p class="secintro" style="margin:0 0 14px">This is the one depth cut that goes Nordic, because Eurostat
      publishes the size classes for every country and back to {h(NORDSZ['meta']['prev_year'])}. Sweden is
      <b>third of the four</b> and grew fastest, from {next(z['prev'] for c in NORDSZ['countries'] if c['is_se'] for z in c['sizes'] if z['code']=='GE10')}%
      to {next(z['adoption'] for c in NORDSZ['countries'] if c['is_se'] for z in c['sizes'] if z['code']=='GE10')}%
      among firms with ten or more employees, against Denmark's rise from
      {next(z['prev'] for c in NORDSZ['countries'] if c['code']=='DK' for z in c['sizes'] if z['code']=='GE10')}%
      to {next(z['adoption'] for c in NORDSZ['countries'] if c['code']=='DK' for z in c['sizes'] if z['code']=='GE10')}%.
      Growing fastest and still behind is the pattern to read here, and it holds in every size class.</p>
    <details class="note"><summary>Why four countries, and why size and not industry</summary>
      <p><b>Iceland has no row in Eurostat's AI table</b>, though it is in the exposure module above. A country
      missing from a source is missing, so it is absent here rather than shown as a gap.</p>
      <p><b>Adoption by industry cannot go Nordic.</b> Eurostat publishes a single all-activities NACE
      aggregate; the industry cut on this site comes from SCB's national release. There is no Nordic equivalent
      unless DST, SSB and Tilastokeskus each publish their own.</p>
      <p>The axis is shared across the four panels, so the countries stay comparable; the highlighted row in each
      is that country's 10+ headline, the same figure the cross-country bar above shows.</p></details>
    {nordic_size_panels()}
    {figfooter("nordic_adoption_size.csv", f"{NORDSZ['meta']['source']}, {NORDSZ['meta']['year']} against {NORDSZ['meta']['prev_year']} · {NORDSZ['meta']['unit']}", next_up="Eurostat 2026 wave (expected around year-end)")}
  </div>
  {akavia_workers_block()}
  {akavia_movement_block()}
  {population_block()}
  {related_research("adoption")}
</section></div></div>"""

def related_research(module):
    """Lab research related to a module. Related, not derived: a paper can date
    while the theme stays live, and only DAIOE is genuinely a derivation."""
    items = RELATED.get(module) or []
    if not items:
        return ""
    lis = "".join(
        f'<li><a href="{i["url"]}">{h(i["title"])}</a> · <span class="rw">{h(i["where"])}</span>'
        f' · {h(i["note"])}</li>' for i in items)
    return (f'<div class="related"><p class="rl">Related research from the lab</p>'
            f'<ul class="tight">{lis}</ul></div>')


def akavia_movement_svg(mv):
    """Two rows: where the same people moved on the scale, and their level before and after.

    Deliberately not a Sankey. The finding is one-directional and almost entirely one-way
    traffic, and a flow diagram would spend most of its ink on ribbons of near-zero width."""
    W, H = 640, 132
    x0, x1 = 205, 556
    X = lambda v: x0 + v / 100 * (x1 - x0)
    seg = [("more", mv["more_often"]["value"], "Uses AI more often"),
           ("same", mv["unchanged"]["value"], "As often as before"),
           ("less", mv["less_often"]["value"], "Less often")]
    p = [f'<svg class="rankchart mvchart" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Within-person change in AI use, {h(mv["period"])}">']
    for t in (0, 25, 50, 75, 100):
        gx = X(t)
        p.append(f'<line class="grid" x1="{gx:.1f}" y1="14" x2="{gx:.1f}" y2="100"/>')
        p.append(f'<text class="tick" x="{gx:.1f}" y="{H-10}" text-anchor="middle">{t}%</text>')
    # Row 1: the movement, stacked, on everyone who answered in both rounds.
    y, hgt, cursor = 22, 26, 0.0
    p.append(f'<text class="dname" x="192" y="{y+17:.1f}" text-anchor="end">Direction of change</text>')
    for cls, v, label in seg:
        w = X(cursor + v) - X(cursor)
        p.append(f'<rect class="mv{cls}" x="{X(cursor):.1f}" y="{y}" width="{max(w, 0.6):.1f}" '
                 f'height="{hgt}" rx="2"><title>{h(label)}: {v}%</title></rect>')
        if v >= 8:
            # White reads on the two saturated segments; the neutral middle is too light for it.
            tone = " dark" if cls == "same" else ""
            p.append(f'<text class="mvlab{tone}" x="{X(cursor) + w / 2:.1f}" y="{y + 17:.1f}" '
                     f'text-anchor="middle">{v}%</text>')
        cursor += v
    # Row 2: the level among those same people, start and end.
    y2 = 80
    a, b = mv["regular_use"]["from"], mv["regular_use"]["to"]
    p.append(f'<text class="dname" x="192" y="{y2+3.5:.1f}" text-anchor="end">Regular use, same people</text>')
    p.append(f'<line class="dbtrack" x1="{X(a):.1f}" y1="{y2:.1f}" x2="{X(b):.1f}" y2="{y2:.1f}"/>')
    p.append(f'<circle class="dblo" cx="{X(a):.1f}" cy="{y2:.1f}" r="4"><title>{h(mv["period"].split(" to ")[0])}: {a}%</title></circle>')
    p.append(f'<circle class="dbhi" cx="{X(b):.1f}" cy="{y2:.1f}" r="5.5"><title>{h(mv["period"].split(" to ")[-1])}: {b}%</title></circle>')
    p.append(f'<text class="dval" x="632" y="{y2+3.5:.1f}" text-anchor="end">{a}→{b}</text>')
    p.append("</svg>")
    return "".join(p)


def akavia_movement_block():
    """The one thing a panel can say and a repeated cross-section cannot.

    Every other number in this module is a level: how many used AI this round, how many the
    round before. A rise is consistent with several different worlds and the levels cannot
    tell them apart. These are the same respondents in both rounds."""
    a = AKAVIA; m = a["meta"]; mv = a.get("movement")
    if not mv:
        return ""
    ac = mv["attrition_check"]
    return f"""<div class="depth"><p class="dk">Sweden, in depth · the same people, twice</p>
    {folded(f"""A rising level can mean new users arriving or existing users using AI more, and the """
             f"""rounds above cannot tell them apart. Following the <b>same {mv['more_often']['n']:,} """
             f"""respondents</b> from {h(mv['period'])} can: of those who used AI <b>never</b> in the first """
             f"""round, <b>{mv['started']['value']}% had started</b> by the second, while only """
             f"""<b>{mv['stopped']['value']}%</b> of the earlier users had stopped. The traffic is almost all """
             f"""one way. [[note]] These are linked respondents who answered the question in both rounds, """
             f"""weighted on {h(mv['weighted_on'])}. Two rounds out of six can be compared this way: the rest """
             f"""ask the question differently, and a change measured across a rewrite is the rewrite. """
             f"""Following people means following the ones who answered twice, so the base is smaller than a """
             f"""round and not identical to it: regular use among them was {ac['linked_regular_from']}% at the """
             f"""start against {ac['full_wave_regular_from']}% in the full round, and """
             f"""{ac['linked_regular_to']}% against {ac['full_wave_regular_to']}% at the end. Close, but the """
             f"""gap is real and the numbers here are not adjusted for it.""",
             style="margin:0 0 14px", label="Which rounds can be followed, and who is in the base")}
    <div class="dotwrap">{akavia_movement_svg(mv)}</div>
    <div class="dblegend mvlegend"><span><i class="more"></i>More often</span>
      <span><i class="same"></i>Unchanged</span><span><i class="less"></i>Less often</span>
      <span><i class="start"></i>{h(mv['period'].split(' to ')[0])}</span>
      <span><i class="end"></i>{h(mv['period'].split(' to ')[-1])}</span></div>
    <p class="psub" style="margin-top:4px">Bars are everyone who answered in both rounds
      ({mv['more_often']['n']:,} people). The two subgroup figures rest on smaller bases:
      {mv['started']['n']:,} who reported never using AI in the first round, {mv['stopped']['n']:,} who
      reported using it.</p>
    {figfooter("akavia_movement.csv", f"{m['source']}, {h(mv['period'])}; own processing. Linked respondents answering in both rounds. {m['population']}", svg_name="akavia_movement.svg", next_up="with the next Akavia panel wave")}
  </div>"""


def akavia_workers_block():
    """Adoption depth, worker side. Firm surveys count employers; this counts people."""
    a = AKAVIA; m = a["meta"]; tr = a["trend"]
    prof = a["by_profession"]; sec = a["by_sector"]
    xmax = 10 * (max(r["adoption"] for r in prof) // 10 + 1)
    cp = tr["clean_pair"]
    thin = min(prof, key=lambda r: r["n"])
    return f"""<div class="depth"><p class="dk">Sweden, in depth · by worker</p>
    {folded(f"""Firm surveys count employers who have started; this counts people. The share of professionals """
             f"""using AI <b>daily or weekly</b> went from <b>{cp['from_value']}%</b> in {h(cp['from'])} to """
             f"""<b>{cp['to_value']}%</b> in {h(cp['to'])}, and the spread by profession is wide: communication """
             f"""professionals are furthest ahead and lawyers furthest behind. [[note]] The two rounds quoted are """
             f"""the only two that asked the question the same way, and it is Akavia's own threshold. Counting any """
             f"""use at all, however occasional, gives {tr['any_use'][-1]}% on the same round. Nearly everyone now """
             f"""works somewhere AI is used at all ({a['org_use']['y2024']}% in 2024, """
             f"""{a['org_use']['y2025']}% in 2025). Central government trails the private sector by """
             f"""{sec[0]['adoption'] - sec[-1]['adoption']}pp. Men {a['by_sex']['men']}%, women """
             f"""{a['by_sex']['women']}%.""", style="margin:0 0 14px", label="Which rounds compare like with like")}
    <div class="dotwrap">{barplot(prof, 0, xmax, 0, 'adoption', '.0f', what='professions')}</div>
    <p class="psub" style="margin-top:4px">Bars are {h(cp['to'])}, with the change measured against
      {h(cp['from'])}, the one earlier round that asked the question identically. Cell sizes differ a great
      deal: {h(thin['name'].lower())} rest on {thin['n']} respondents ({thin['lo']}–{thin['hi']}% interval),
      against {max(r['n'] for r in prof)} for the largest group.</p>
    {figfooter("akavia_ai_use.csv", f"{m['source']}, {m['first_year']}–{m['year']}; own processing. Bars {h(cp['to'])}, change vs {h(cp['from'])}. {m['population']}", svg_name="akavia_ai_use.svg", next_up="with the next Akavia panel wave")}
    {us_rps_line()}
    {akavia_provenance(m)}
  </div>"""


def us_rps_line():
    """One international reference line for the worker-side numbers, at the same level of
    measurement. Deliberately NOT a module and never set beside the firm-adoption bars:
    those count enterprises, these count people, and the comparison a reader makes unaided
    is the wrong one. Data and caveats: data/us_adoption_rps.yaml."""
    u = USRPS; m = u["meta"]; w = u["values"]["work_last_week"]
    # Reordered 12 Aug 2026 (Lydia's review): opening with "there is no representative figure"
    # read as a verdict on the Akavia numbers above rather than as the preface to the US
    # comparison that follows. Say what the Swedish number is first, then bring in the US rate.
    return (f'<p class="secintro" style="margin:12px 0 0">The Swedish number above is one '
            f'professional union\'s members; no representative Swedish figure exists at this '
            f'level. The nearest comparison is American: <b>{w["pct"]:g}%</b> of employed adults '
            f'used generative AI for work in the reference week '
            f'(<a href="{m["url"]}">{h(m["source"])}</a>, {h(m["vintage"])}), a whole-workforce '
            f'rate. Sweden publishes no equivalent: the national survey asks about work-related '
            f'use but counts it across the whole population rather than the employed. That gap is '
            f'the reason this level is the module\'s weakest, and a thing worth measuring rather '
            f'than citing. {h(m["caveat"])}</p>')


def _pop_age_rows():
    """Age rows for barplot(), which highlights a row via is_se. No row is highlighted
    here: these are age groups, not countries."""
    return [dict(r, name=r["group"], is_se=False) for r in POPAI["by_age"]]


def population_block():
    """Adoption depth, population side. Firm surveys count employers and the Akavia panel
    counts one profession; this counts everybody, from official statistics with published
    margins of error -- the strongest instrument in the module."""
    m = POPAI["meta"]; ages = POPAI["by_age"]
    u = USRPS["values"]["any_use"]; um = USRPS["meta"]
    xmax = 10 * (max(r["adoption"] for r in ages) // 10 + 1)
    swing = ages[0]["adoption"] - ages[-1]["adoption"]
    gap_now = m["men"] - m["women"]
    gap_then = m["men_first"] - m["women_first"]
    return f"""<div class="depth"><p class="dk">Sweden, in depth · by person</p>
    {folded(f"""The share of <b>everyone</b> aged 16–74 who has used generative AI at all rose from <b>{m['headline_first']:g}%</b> in {h(m['first_year'])} to <b>{m['headline']:g}%</b> in {h(m['year'])} (±{m['headline_moe']:g}), and age divides it far more than anything else: {ages[0]['adoption']:g}% of {h(ages[0]['group'])}-year-olds against {ages[-1]['adoption']:g}% of {h(ages[-1]['group'])}s, a {swing:g}-point span. [[note]] Broadest of the three levels: at work or outside it, from SCB's population survey, a probability sample with published margins of error, which makes it the firmest number in the module. The gap between men and women
      is narrowing, from {gap_then:g} points in {h(m['first_year'])} to {gap_now:g}
      ({m['men']:g}% against {m['women']:g}%). Figures refer to the {h(m['reference_period'])}.""", style="margin:0 0 14px", label="What the population survey covers, and how firm it is")}
    <div class="dotwrap">{barplot(_pop_age_rows(), m['headline'], xmax, 0, 'adoption', '.0f', what='age groups', mean_label='Sweden')}</div>
    {figfooter("population_ai.csv", f"{m['source']}, {m['first_year']}–{m['year']} · {m['unit']}; bars {m['year']}, change vs {m['first_year']}. {m['design']}", svg_name="population_ai.svg", next_up="with SCB's next ICT-use survey wave")}
    {folded(f"""The US counterpart at this level is <b>{u['pct']:g}%</b> """
             f"""(<a href="{um['url']}">{h(um['source'])}</a>, {h(um['vintage'])}), which is a reference point """
             f"""rather than a ranking. [[note]] It covers ages 18–64 where SCB covers 16–74, and Swedish """
             f"""65–74-year-olds use generative AI far less ({ages[-1]['adoption']:g}%), which pulls the Swedish """
             f"""figure down relative to a US-style base.""", style="margin:12px 0 0", label="Why this is a reference point and not a ranking")}
  </div>"""


def _break_reason(reason):
    """The config's reason, trimmed to the sentences a reader of the page needs.

    concepts.yaml writes for whoever maintains the pipeline: it names wave ids, dates the
    discovery and says what was checked. The page needs what changed and why it matters, so the
    housekeeping clauses are dropped rather than reworded, and nothing is added.
    """
    import re as _re
    keep = []
    for sentence in _re.split(r"(?<=[.]) +", str(reason)):
        low = sentence.lower()
        if low.startswith(("surfaced", "note this is published", "both declared")):
            continue
        if "concepts.yaml" in low or "data/akavia.yaml" in low:
            continue
        keep.append(sentence.strip())
    return " ".join(keep)[:400]


def akavia_policy_flow_block():
    """The governance half of the panel: the same people, asked again two years later.

    The table above is four levels. A level rising from 30% to 50% is consistent with employers
    adopting policies, with members moving to employers that had one, and with members simply
    finding out. Linked respondents separate those. Every sentence here says KNOWS, because that
    is what the indicator counts: "vet ej" is coded as not-known-to-exist, so a member moving
    from no to yes came to know of a policy, which is not the same claim as an employer
    introducing one and is the only one these data support.
    """
    mg = AKAVIA.get("movement_governance")
    if not mg:
        return ""
    g, l, lv, ac = mg["gained"], mg["lost"], mg["level"], mg["attrition_check"]
    return f"""<div class="depth" style="margin-top:22px"><p class="dk">The same people, on governance</p>
    {folded(f"""Of the <b>{g['n']:,} members who did not know of an AI policy at their workplace</b> in """
             f"""{h(mg['period'].split(' to ')[0])}, <b>{g['value']}% knew of one</b> by """
             f"""{h(mg['period'].split(' to ')[-1])} ({g['lo']}–{g['hi']}%). Of the {l['n']:,} who did know, """
             f"""{l['value']}% no longer did ({l['lo']}–{l['hi']}%). Across all {lv['n']:,} who answered in """
             f"""both rounds the share went {lv['from']}% to {lv['to']}%. [[note]] These count """
             f"""<b>knowing of</b> a policy, not employers having one: a member who answers that they do """
             f"""not know is counted as not knowing of one, so a move from no to yes is a member who came """
             f"""to know, which can mean their employer introduced a policy, that they changed employer, """
             f"""or that they found out about one that already existed. The reverse move can equally mean """
             f"""a job change or a policy nobody has mentioned since. Linked respondents who answered in """
             f"""both rounds, weighted on {h(mg['weighted_on'])}. This base tracks the rounds it comes """
             f"""from closely: {ac['linked_from']}% against {ac['full_wave_from']}% at the start and """
             f"""{ac['linked_to']}% against {ac['full_wave_to']}% at the end.""",
             style="margin:0 0 10px", label="What this counts, and who is in the base")}
    {figfooter("akavia_policy_flow.csv", f"{AKAVIA['meta']['source']}, {h(mg['period'])}; own processing. Linked respondents answering in both rounds. {AKAVIA['meta']['population']}", next_up="with the next Akavia panel wave")}
  </div>"""


def akavia_outcomes_block():
    """Outcomes: governance trailing use, the training gap, and who pays for the tools."""
    a = AKAVIA; m = a["meta"]; g = a["governance"]; tg = a["training"]; sh = a["shadow"]
    used = a["used_for"]
    gap = g["use"][-1] - g["policy"][-1]
    # Mark where a series crosses a change of instrument. The break list is generated by
    # survey-db from the comparability declarations in concepts.yaml; a value on the far side of
    # one is real and is shown, but it is not continuous with the values above it, and a table
    # that says nothing invites exactly the reading the caveat exists to prevent.
    breaks = (g.get("breaks_after") or {})
    notes = (g.get("break_notes") or {})
    first_new = {k: {n["first_on_new_instrument"] for n in v} for k, v in notes.items()}

    def cell(series, label, value):
        mark = "<sup>†</sup>" if label in first_new.get(series, set()) else ""
        cls = ' class="brk"' if mark else ""
        return f"<td{cls}>{value}%{mark}</td>"

    rows = "".join(
        f"<tr><td>{h(l)}</td>{cell('use', l, u)}{cell('policy', l, p)}{cell('strategy', l, s)}</tr>"
        for l, u, p, s in zip(g["labels"], g["use"], g["policy"], g["strategy"]))
    # The note is AUTHORED in data/akavia.yaml, not derived: concepts.yaml writes its reasons
    # for whoever maintains the pipeline, naming wave ids and answer codes, which is not page
    # prose. What is derived is WHERE the break falls, which is the part that must not drift.
    footnotes = "".join(
        f'<p class="brknote">† {h(n.get("page_note") or _break_reason(n["reason"]))}</p>'
        for series, ns in notes.items() for n in ns)
    uf = "".join(f"<li><b>{r['value']}%</b> {h(r['label'].lower())}</li>" for r in used)
    # The governance arrays run a wave behind the headline trend (they stop at May 2025 while
    # `trend` reaches May 2026), so the vintage must come from THIS block's own labels. Taking
    # it from meta['year'] printed a May 2025 observation as "In 2026".
    gy = g["labels"][-1]
    # Same trap, second instance. akavia.yaml carries `universe` for the shadow-AI block but
    # NOT for used_for, so the vintage is lost between the survey-db export (which records
    # "AI users, May 2025") and this page, and meta['year'] filled the gap with 2026. Assert a
    # vintage only when the data file actually carries one; otherwise say nothing.
    # PROPER FIX, upstream: have export_monitor.py carry what_ai_is_used_for's universe into
    # the site feed the way it already does for shadow_ai.
    uv = f", {h(a['used_for_universe'])}" if a.get("used_for_universe") else ""
    return f"""<div class="grouphdr" id="akavia-governance" style="margin-top:36px">Use, governance and who pays</div>
  <p class="secintro" style="margin-top:4px">Among Swedish professional-union members, workplace governance runs
    well behind actual use. In {h(gy)}, {g['use'][-1]}% used AI at work while only {g['policy'][-1]}% knew
    of a policy and {g['strategy'][-1]}% of a strategy, a gap of <b>{gap}pp</b>. The figures say <i>knows of</i>
    rather than <i>has</i>: about a fifth answer that they do not know, which is counted here as not knowing of
    one. Training runs the same way: {tg['wants_last']}% want to develop their AI skills, {tg['offered_last']}%
    have been offered it by an employer, against {tg['wants_first']}% and {tg['offered_first']}% in
    {h(m['first_year'])}.</p>
  <table class="minitab"><thead><tr><th>Wave</th><th>Uses AI</th><th>Knows of a policy</th><th>Knows of a strategy</th></tr></thead><tbody>{rows}</tbody></table>
  {footnotes}
  {akavia_policy_flow_block()}
  <p class="secintro" style="margin-top:14px">What the work actually is, among AI users{uv}:</p>
  <ul class="tight">{uf}</ul>
  {folded(f"""And who provides the tools: <b>{sh['private_account']}%</b> have a private e-mail account """
           f"""connected to a work AI tool, the employer pays for {sh['employer_pays']}% and """
           f"""{sh['self_pays']}% pay themselves. [[note]] Those shares are among workers using """
           f"""<b>standalone</b> AI tools, not among all workers, so they describe a subset and not the """
           f"""workforce.""", style="margin-top:14px", label="Who these percentages are of")}
  {figfooter("akavia_governance.csv", f"{m['source']}, {m['first_year']}–{m['year']}; own processing. {m['population']}", next_up="with the next Akavia panel wave")}
  {akavia_provenance(m)}"""

def outcomes_section(explorers):
    """Module 4 — Outcomes. Occupations Explorer + working conditions + entry-level squeeze (all live)."""
    em = ELS["meta"]
    return f"""<div class="rule module-sec" id="outcomes"><div class="wrap"><section>
  <p class="kicker">Module 4 · Outcomes · what happens to jobs and pay</p>
  <h2 class="sec">What does it mean for jobs and job quality?</h2>
  <p class="secintro">Exposure and demand are inputs; outcomes are what happens to workers. Three views: employment
    by occupation, working conditions, and the entry-level "canaries" signal on vacancies.</p>

  <div class="grouphdr" id="occupations-explorer" style="margin-top:26px">Employment by occupation</div>
  <p class="secintro" style="margin-top:4px">Swedish employment by occupation over time (and, soon, by region), with
    <a href="/daioe/">DAIOE</a> AI-exposure overlaid. Built and maintained in-house; yearly and monthly views.</p>
  <div class="explorers">{explorers}</div>

  {working_conditions_block()}

  {akavia_outcomes_block()}

  <div class="grouphdr" style="margin-top:36px">Entry-level squeeze</div>
  {note(
    f"""In the most AI-exposed occupations, a smaller share of openings ask for no prior experience than in the
    least-exposed occupations, every year since {h(em['first_year'])}, and the gap has widened from
    −{abs(em['gap_first'])}pp to <b>−{abs(em['gap_last'])}pp in {h(em['last_year'])}</b>. This is consistent with the
    canaries finding of our Same Storm, Different Boats study (the most AI-exposed occupations hire fewer young
    workers, the labour market's canaries in the coal mine), but it is not independent evidence for it, and
    <b>this module counts ad records rather than distinct advertisements</b>.""",
    f"""Entry-level hiring is more cyclical than experienced
    hiring, the tightening cycle that began in April 2022 fell hardest on exactly these occupations, and this series
    starts in 2020 with no pre-pandemic baseline, so it cannot separate AI from the cycle. It counts records because
    it reads totals from the JobTech API, which cannot be deduplicated; elsewhere on this page, counting
    records rather than advertisements manufactured an artefact of about thirty points.
    The Same Storm paper can separate them, because it observes employers and workers\u2019 ages and identifies
    within employers. Descriptive throughout: less-exposed work also skews lower-skill, so part of the level gap is
    structural. The same entry-level pattern appears in the international AI &quot;canaries&quot; literature on young
    workers, though no directly comparable cross-country series exists yet.""",
    "How this is counted, and what it cannot show")}
  <div class="dotwrap">{squeeze_svg(ELS)}</div>
  <div class="dblegend"><span><i class="lo"></i>least-exposed occupations</span><span><i class="hi"></i>most-exposed occupations</span></div>
  {figfooter("entry_level_squeeze.csv", f"{em['source']} × DAIOE {em['daioe_variant']} {em['daioe_version']} · ad records, not distinct advertisements (see the note)", svg_name="entry_level_squeeze.svg", next_up="annually, with the JobTech year files")}
  {jobquality_block()}
  {wages_block()}
  {related_research("outcomes")}
</section></div></div>"""


WAGE_COLORS = {"high": "var(--c2)", "mid": "var(--c4, #cc79a7)", "low": "var(--c3)"}
WAGE_LABELS = {"high": "most exposed", "mid": "middle", "low": "least exposed"}
SHORT = {"high": "most", "mid": "mid", "low": "least"}


def wages_svg(c):
    """Three-line indexed wage series (high/mid/low DAIOE-exposure terciles), one country.
    Same visual grammar as squeeze_svg; index base 100 = first year."""
    srs = c["series"]; n = len(srs)
    vals = [r[g] for r in srs for g in ("high", "mid", "low")]
    lo10 = 10 * (int(min(vals)) // 10)
    hi10 = 10 * (int(max(vals)) // 10 + 1)
    W, H = 640, 292
    x0, x1, top, bot = 60, 560, 22, 250
    X = lambda i: x0 + i / (n - 1) * (x1 - x0)
    Y = lambda v: bot - (v - lo10) / (hi10 - lo10) * (bot - top)
    p = [f'<svg class="rankchart squeeze" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Median wage by AI-exposure tercile, {c["label"]}, indexed to 100 in {c["base_year"]}">']
    for t in range(lo10, hi10 + 1, 10):
        gy = Y(t)
        p.append(f'<line class="grid" x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}"/>')
        p.append(f'<text class="tick" x="{x0-6}" y="{gy+3.5:.1f}" text-anchor="end">{t}</text>')
    for i, r in enumerate(srs):
        if r["year"] % 2 == 0 or i == n - 1:
            p.append(f'<text class="tick" x="{X(i):.1f}" y="{H-8}" text-anchor="middle">{r["year"]}</text>')
    colors, labels = WAGE_COLORS, WAGE_LABELS
    for g in ("low", "mid", "high"):
        pts = " ".join(f'{X(i):.1f},{Y(r[g]):.1f}' for i, r in enumerate(srs))
        p.append(f'<polyline points="{pts}" fill="none" stroke="{colors[g]}" stroke-width="2.2"/>')
        ey = Y(srs[-1][g])
        p.append(f'<text class="tick" x="{x1+5}" y="{ey:.1f}" '
                 f'fill="{colors[g]}">{srs[-1][g]:.0f}</text>')
        p.append(f'<text class="tick" x="{x1+5}" y="{ey+10:.1f}" '
                 f'fill="{colors[g]}" style="font-size:9px">{SHORT[g]}</text>')
    p.append("</svg>")
    return "".join(p)

def wages_block():
    """Outcomes sub-module: pay by AI-exposure tercile (Sweden + US charts, EU one-liner)."""
    w = WAGES
    charts = ""
    for c in w["countries"]:
        charts += (f'<div><p class="secintro" style="margin:0 0 4px;font-weight:600">{h(c["label"])}</p>'
                   f'<div class="dotwrap">{wages_svg(c)}</div>'
                   f'<p class="psub" style="margin-top:4px">{h(c["source"])}</p></div>')
    cavs = " ".join(f'<li>{cv}</li>' for cv in w["caveats"])
    return f"""<div class="grouphdr" id="wages" style="margin-top:36px">Wages in AI-exposed occupations</div>
  {folded(f'<b>{h(w["headline"].split(".")[0])}.</b>[[note]] {h(".".join(w["headline"].split(".")[1:]).strip())} '
          f'{h(w["intro"])}', style="margin-top:4px",
          label="How the thirds are cut, and the country detail")}
  <div class="two" style="grid-template-columns:1fr 1fr">{charts}</div>
  <div class="dblegend">{"".join(f'<span><i style="background:{WAGE_COLORS[g]}"></i>{WAGE_LABELS[g]} third</span>' for g in ("high", "mid", "low"))}</div>
  <p class="psub">{h(w["eu_line"])}</p>
  <ul style="color:var(--ink-2);font-size:13px;line-height:1.55">{cavs}</ul>
  {figfooter("wages_exposure.csv", "SCB wage structure statistics · BLS OEWS · Eurostat SES × DAIOE genAI v2023", svg_name="wages_sweden.svg", next_up="SCB and OEWS annual releases (spring 2027)")}
"""

def capability_section():
    """Module 5 (minor) — AI capability: how fast the technology itself moves. External
    series, summarised; capability in work-relevant units feeds DAIOE Track B."""
    # Generated by scripts/refresh_capability.py; monitor.yaml stays the hand-maintained
    # source for the watched facts, and is the fallback if the refresher has never run.
    c = CAPABILITY
    tiles = "".join(
        f'<div class="tile"><div class="stripe"></div><div class="num">{num_html(t["num"])}</div>'
        f'<div class="lab">{h(t["lab"])}</div><div class="foot">{h(t["foot"])}</div></div>'
        for t in c["facts"])
    links = " · ".join(f'<a href="{h(l["url"])}">{h(l["label"])}</a>' for l in c["links"])
    return f"""<div class="rule module-sec" id="capability"><div class="wrap"><section>
  <p class="kicker">Module 5 · Capability · what the technology can do <span class="preview-flag">◔ {h(c["flag"])}</span></p>
  <h2 class="sec">How fast is the technology itself moving?</h2>
  <p class="secintro">{h(c["intro"])}</p>
  <div class="tiles">{tiles}</div>
  <p class="psub" style="margin-top:8px">Sources: {links}. {h(c["caveat"])}</p>
  <p class="secintro" style="margin:22px 0 0"><b>The whole picture on one page.</b>
    A dated infographic with all five modules, generated from this page's own data:
    <a href="/aiel-monitor-onepager.pdf">download the two-page sheet (PDF)</a>, or the
    <a href="/aiel-monitor-onepager-sv.pdf">Swedish edition</a>. The figures on it come from different
    years and survey waves, so each states its own year.</p>
</section></div></div>"""

def stat_overview():
    """Overview-first landing: one door per spine module. Whole picture in ~20s; detail one click down.

    Entries marked role: driver are NOT questions about the labour market, they are the
    technology the four are measured against, and they render as a full-width band rather than
    as another card. Before 4 Aug 2026 capability sat in the grid as a fifth peer, which
    put five cards under a sentence promising four questions."""
    cards = ""
    for o in MONITOR["overview"]:
        if o.get("role") == "driver":
            continue
        cls = f' {o["cls"]}' if o["cls"] else ""
        cards += (f'<a class="ovcard{cls}" href="{o["anchor"]}"><div class="stripe"></div>'
                  f'<div class="ok">{h(o["k"])}</div><div class="onum">{o["num"]}</div>'
                  f'<div class="olab">{h(o["lab"])}</div>'
                  f'<div class="ofoot"><span>{h(o["foot"])}</span><span class="go">Open →</span></div></a>')
    band = ""
    for o in MONITOR["overview"]:
        if o.get("role") != "driver":
            continue
        band += (f'<a class="driverband" href="{o["anchor"]}">'
                 f'<div class="dnum">{o["num"]}</div>'
                 f'<div class="dbody"><div class="dk">{h(o["k"])} · the technology itself, tracked separately</div>'
                 f'<p>{h(o["lab"])}</p></div>'
                 f'<div class="dfoot"><span>{h(o["foot"])}</span><span class="go">Open →</span></div></a>')
    return f"""<div class="rule" id="overview"><div class="wrap"><section>
  <p class="kicker">The whole picture, in one glance</p>
  <h2 class="sec">From what the technology can do to what happens to jobs and pay.</h2>
  <p class="secintro">The four modules follow one chain. Exposure asks which jobs sit in AI's path; demand asks
    what employers are actually hiring for; adoption asks who is using AI in practice; outcomes asks what happens
    to employment, entry-level hiring and wages. A fifth band, Capability, tracks the technology itself: it
    measures what AI can do rather than the labour market, which is why it sits apart below the four. One
    international headline each, with Sweden as the depth cut inside every module. Every figure is
    public and dated; open a card to jump to the module.</p>
  <div class="ovgrid">{cards}</div>
  {band}
</section></div></div>"""

def subnav():
    """Sticky spine nav under the masthead; scrollspy in app.js marks the active module."""
    items = [("#exposure", "Exposure"), ("#demand", "Demand"),
             ("#adoption", "Adoption"), ("#outcomes", "Outcomes"),
             ("#capability", "Capability")]
    links = "".join(f'<a href="{a}" data-spy="{a[1:]}">{t}</a>' for a, t in items)
    return f'<nav class="subnav" aria-label="Monitor modules"><div class="wrap">{links}</div></nav>'


def partner_mark(stem, h_px, alt):
    """One partner logo, as the theme-swapped pair of <img> the CSS expects.

    Module level since 2 Sep 2026 because the brief footer needs the same marks as the Monitor
    strip, and two copies of this markup would drift: the trimmed filenames and the
    dark-ink/light-ink class pair are the two things that must not be got wrong (see
    docs/assets/logos/README.md, "Trim the padding, or the mark disappears").

    h_px sizes the WORDMARK, not the image: WASP-HS is 12.5:1 and the trimmed AISCAF mark 3:1,
    so equal image heights make one of them far too small. Callers pass different numbers.
    """
    st = f"height:{h_px}px;width:auto"
    return (f'<img class="logo-dark-ink" src="/assets/logos/{stem}_dark_ink_trim.png" '
            f'alt="{alt}" style="{st}">'
            f'<img class="logo-light-ink" src="/assets/logos/{stem}_light_ink_trim.png" '
            f'alt="{alt}" style="{st}">')


def partner_strip():
    """The "Part of" strip: AISCAF and WASP-HS at the foot of the Monitor.

    Consent is on record: Magnus asked Christofer (WASP-HS) on 28 Aug 2026 whether both marks
    could go on the Monitor, and Hanna Nordin sent the official files on 1 Sep. Julia sent the
    AISCAF files the same week.

    THREE THINGS THIS MARKUP IS DOING, none of them obvious:

    1. TWO FILES PER MARK, swapped by theme in CSS. The AISCAF mark is drawn in #2e2e2e, so on
       the dark palette it is black on near-black and effectively disappears. A single file
       cannot serve both themes.
    2. THE TRIMMED FILES. Julia's PNGs are 561x427 with the ink in the top 185 rows, so 57 per
       cent of the canvas is transparent padding and a CSS height on the untrimmed file renders
       a mark half the size asked for.
    3. SIZED ON THE WORDMARKS, not on image height. WASP-HS is 12.5:1 and the trimmed AISCAF
       mark 3:1; matching image heights makes one of them far too small either way round.

    "Part of" rather than a row of sponsor logos, because that is the true relationship: the lab
    contributes to AISCAF, WASP-HS finances the cluster. Örebro and Ratio are deliberately NOT
    here; they are where the work is done, which is a different thing, and putting all four in
    one row would say there are four sponsors.
    """
    mark = partner_mark
    # NOT "Part of". The lab was initiated in 2019 and AISCAF in September 2025, and the lab
    # is not inside the cluster: Örebro is a node, and the cluster funds part of the team.
    # "Part of" claims the first thing and implies the cluster came first; "contributes to",
    # which the About page used to say, errs the other way and hides the funding entirely.
    # Stating the two facts and the date lets a preposition stop doing work it cannot do.
    return (f'<div class="partner-strip">'
            f'<p class="kicker" style="margin:0 0 12px">Research cluster and funder</p>'
            f'<div style="display:flex;align-items:center;gap:34px;flex-wrap:wrap">'
            f'{mark("aiscaf", 30, "AISCAF")}{mark("wasphs", 15, "WASP-HS")}</div>'
            f'<p class="psub" style="margin:10px 0 0;font-size:12.5px">AI-Econ Lab, since 2019 · '
            f'Örebro University and Ratio. Örebro is one of AISCAF\'s three nodes; the cluster, '
            f'financed by WASP-HS, funds part of the lab\'s team.</p></div>')

def monitor():
    m = MONITOR
    tiles = ""
    for t in m["tiles"]:
        cls = f' {t["cls"]}' if t["cls"] else ""
        tiles += (f'<div class="tile{cls}"><div class="stripe"></div><div class="num">{num_html(t["num"])}</div>'
                  f'<div class="lab">{h(t["lab"])}</div><div class="foot">{h(t["foot"])}</div></div>')
    seg = ""
    for c in m["segmentation"]["cards"]:
        seg += (f'<div class="prod"><h3><span style="display:inline-block;width:11px;height:11px;border-radius:3px;'
                f'background:var({c["color"]});margin-right:8px"></span>{h(c["name"])}</h3><p>{h(c["text"])}</p></div>')
    # The caveat prose lives in monitor.yaml and cannot carry an f-string, so it uses the
    # same placeholder convention as the masthead and is substituted here. It states both
    # corpus counts in one sentence, which is exactly the kind of figure that goes stale.
    def _fill(txt):
        return (txt.replace("{records_m}", RECORD_ADS[:-1])
                   .replace("{distinct_m}", DISTINCT_ADS[:-1]))
    caveats = "".join(f"<li>{_fill(c)}</li>" for c in m["caveats"])
    explorers = ""
    for e in DAIOE["explorers"]:
        explorers += f"""<div class="explorer">
  <div class="charthead"><div class="charttitle">{h(e['name'])}</div>
    <a class="mono" style="font-size:12px" href="{e['open']}">Open full ↗</a></div>
  <p class="psub" style="margin:2px 0 10px">{h(e['desc'])}</p>
  <div class="embedwrap"><iframe src="{e['embed']}" title="{h(e['name'])}" loading="lazy"
    referrerpolicy="no-referrer" sandbox="allow-scripts allow-same-origin allow-forms allow-popups"></iframe></div>
</div>"""
    body = f"""<div class="wrap"><div class="hero" style="padding-bottom:10px"><div class="herogrid">
  <div><div class="eyebrow"><span class="dot"></span> Public monitor · international context, Sweden in depth · updated as the data arrive</div>
    <h1 class="title">{h(m['headline'])}</h1>
    <p class="lede">{h(m['lede'])}</p>
    <!-- A byline, not a paragraph. The first version put three lines of credit ABOVE the H1,
         where it competed with the headline and read as the page's opening statement. The
         footer strip carries the full two-facts wording; here one line is enough to make the
         association visible in the first screen, which was the whole point. -->
    <p class="psub" style="margin:8px 0 0;font-size:12.5px;opacity:.85">AI-Econ Lab, since 2019 ·
      Örebro University and Ratio · Örebro is a node of
      <a href="https://www.aiscaf.se/w/ac/">AISCAF</a>, financed by
      <a href="https://wasp-hs.org">WASP-HS</a></p>
    <div class="cta-row"><a class="btn primary" href="#exposure">See it across countries →</a>
      {sheet_pair()}
      <a class="btn ghost" href="/monitor/brief/">Monthly brief (PDF) →</a></div>
    <div class="cta-row"><a class="btn ghost" href="/monitor/methods/">How we measure it</a></div></div>
  {hero_exposure_panel("#method", "#exposure")}
</div></div></div>

<div class="wrap" style="padding-bottom:6px">{sweden_trend_panel("#method")}</div>

{stat_overview()}

{subnav()}

{exposure_section()}

{demand_section(tiles, seg)}

{adoption_section()}

{outcomes_section(explorers)}

{capability_section()}

<div class="rule" id="method"><div class="wrap"><section>
  <p class="kicker">Method · sources, versions and limits</p>
  <h2 class="sec">What we measure, and what we don't yet.</h2>
  <div class="prose" style="margin-top:16px">
    <p>The measure runs on public data with one exception, described below. The Swedish demand series reads every
      open and historical advertisement in Sweden's public job board (Platsbanken), 2006 onwards. An ad counts
      when its text names an AI skill; the stricter floor counts it only when the skill sits in the role's own
      tasks or requirements. The term list behind the measure is versioned and kept current against new AI
      vocabulary, and every chart states which version produced it. Every figure here can be downloaded as data,
      and the advertisements behind the Swedish series are public and openly licensed, so the series can be
      rebuilt from source. The <a href="/monitor/methods/">methods page</a> documents the estimand, the
      lexicon layer by layer with its published sources, the full version history with fingerprints, and the
      validation figures for each freeze; it also states plainly what is not yet published. Exposure, adoption
      and cross-country demand come from DAIOE, Eurostat and the Stanford AI Index.</p>
    <p>The exception is the worker-side layer, which comes from
      <a href="https://www.akavia.se/politik-paverkan/sakomraden/ai-digitalisering/">Akavia</a>, a Swedish
      professional union that surveys its members through a web panel and shares the de-identified results with
      the lab. We publish aggregated figures with attribution and keep the underlying records private; cells
      below 50 respondents are never shown. Akavia does not fund the lab and does not see results before
      publication. The processing, and any error in it, is ours.</p>
    <h3>Nordic coverage, as of September 2026</h3>
    <p>The country charts highlight the Nordics, and how far the Nordic frame reaches differs by
      module, so the state is set out here rather than implied. <b>Exposure</b> covers all five:
      Sweden, Denmark, Norway, Finland and Iceland. <b>Adoption</b> and the firm-size cut cover
      four; Iceland has no row in Eurostat's AI table. <b>Adoption by industry</b> is Sweden only,
      because Eurostat publishes a single all-activities aggregate and the industry breakdown comes
      from SCB's national release. <b>Demand</b>, from job advertisements, and the <b>entry-level
      outcomes</b> from the registers are Sweden only, as is the worker survey. Danish and
      Norwegian advertisement sources are under assessment; a second country enters the demand
      series only when its coverage has been measured, not when access has been arranged.</p>
    <h3>Caveats, in plain sight</h3><ul style="color:var(--ink-2);font-size:14px;line-height:1.6">{caveats}</ul>
    <h3>How to cite</h3>
    <p>The monitor is a citable public good. Please cite the specific version and date, and the underlying source
      shown in each figure's footer (for example DAIOE generative-AI v2023, or Eurostat 2025).</p>
    <p class="citebox">AI-Econ Lab (2026). AIEL Monitor: [module]. Örebro University and Ratio. [source and version
      from the figure footer]. Accessed [date], https://ai-econlab.com/monitor/</p>
    {partner_strip()}
  </div>
</section></div></div>"""
    return shell(f"The AI-Econ Lab Monitor · {SITE['brand']['name']}",
                 "A public monitor of AI in the Swedish labour market: demand, use and barriers, on public data.",
                 "/monitor/", body, jsonld=dataset_ld(), need_chart=True)

def about():
    c = SITE["contact"]; bk = SITE["book"]
    eu, ed, eobf = email_bits(c["email"])
    labdesc = "".join(f"<p>{linkify(p)}</p>" for p in SITE["about_paras"])
    clinks = "".join(f'<a href="{l["href"]}">{h(l["label"])}</a> ' for l in c.get("links", []))
    booktitle = f'<a href="{bk["url"]}">{h(bk["title"])}</a>' if bk.get("url") else h(bk["title"])
    booklink = f' <a class="lchip" href="{bk["url"]}">View the book →</a>' if bk.get("url") else ""
    partners = "".join(
        f'<li><b>{h(p["name"])}</b>' +
        (f' (<a href="{p["url"]}">site</a>)' if p.get("url") else "") +
        f' · {h(p["what"])}</li>' for p in SITE.get("data_partners", []))
    sup = SITE.get("support") or {}
    supgroups = ""
    for g in sup.get("groups", []):
        lis = "".join(f"<li>{h(i)}</li>" for i in g["items"])
        supgroups += (f'<div><div class="grouphdr">{h(g["kind"])}</div>'
                      f'<p class="psub" style="margin:0 0 8px">{h(g["note"])}</p>'
                      f'<ul class="tight" style="font-size:13.5px;color:var(--ink-2)">{lis}</ul></div>')
    body = f"""<div class="wrap"><div class="pagehead">
  <p class="kicker">About</p><h2 class="sec">An economics-led lab on AI and the future of work</h2></div>
<section style="padding-top:14px"><div class="prose">
  <p>The AI-Econ Lab studies how artificial intelligence is reshaping labour markets across countries,
    particularly for white-collar and service work, combining international comparisons with uncommonly broad
    access to linked register data: deepest in Sweden, reaching Denmark, Portugal and Germany, and expanding.
    Based at Örebro University and the Ratio Institute, we pair peer-reviewed research with open, citable public
    goods (the <a href="/monitor/">AIEL Monitor</a> and the <a href="/daioe/">DAIOE</a> exposure measure), so
    evidence on AI and work reaches policymakers, journalists and the public, not only specialists.</p>
</div></section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">The lab</p><h2 class="sec">Who we are.</h2>
  <div class="prose" style="margin-top:14px">{labdesc}</div>
</section></div></div>

<div class="rule" id="support"><div class="wrap"><section>
  <p class="kicker">Support · as of {h(sup.get("asof", ""))}</p>
  <h2 class="sec">Who funds the work.</h2>
  <p class="secintro">Hosts, grants and data partners are three different things, and we keep them apart.
    An independence claim is only worth as much as the disclosure it follows.</p>
  <div class="two" style="grid-template-columns:repeat(auto-fit,minmax(240px,1fr));margin-top:20px">{supgroups}</div>
  <div class="depth" style="margin-top:26px"><p class="dk">Independence</p>
    <p class="secintro" style="margin:0">{h(sup.get("statement", ""))}</p></div>
</section></div></div>

<div class="rule" id="data-partners"><div class="wrap"><section>
  <p class="kicker">Data partners</p><h2 class="sec">Who shares data with us.</h2>
  <p class="secintro">Several organisations give the lab access to data they collect themselves. None of them
    fund the lab, none of them see our results before publication, and listing them implies no endorsement.
    Where we publish figures from their data we say so on the figure, state what we did to it, and keep the
    underlying records private.</p>
  <div class="prose" style="margin-top:12px"><ul class="tight">{partners}</ul></div>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">Book</p>
  <h2 class="sec">{booktitle}.</h2>
  <p class="secintro">{h(bk['author'])} · {h(bk['year'])} · {h(bk['publisher'])}. {h(bk['note'])}{booklink}</p>
</section></div></div>

<div class="rule" id="contact"><div class="wrap"><section>
  <p class="kicker">Contact &amp; visit</p><h2 class="sec">Get in touch.</h2>
  <div class="two" style="grid-template-columns:1fr 1fr;margin-top:18px">
    <div class="prose">
      <p>{h(c['invite'])}</p>
      <p>{clinks}</p>
    </div>
    <div class="card">
      <p style="margin:0 0 8px"><span class="lbl">E-mail</span> <a class="email" data-u="{h(eu)}" data-d="{h(ed)}" data-reveal="keep" href="#contact">{h(eobf)}</a></p>
      <p style="margin:0 0 8px"><span class="lbl">Phone</span> {h(c['phone'])}</p>
      <p style="margin:0"><span class="lbl">Post</span> {h(c['address'])}</p>
    </div>
  </div>
</section></div></div>"""
    # Plain "&" here, not "&amp;". shell() runs the title through h(), so a pre-escaped
    # ampersand was escaped twice and the browser tab read "About &amp; contact".
    return shell(f"About & contact · {SITE['brand']['name']}", SITE["brand"]["description"], "/about/", body)

def brief(lang="en"):
    """Monthly one-page 'AIEL Monitor Brief' (English + Swedish): the month's argument in three
    moves, a question, the chart that answers it, and what the answer cannot show, on a theme that
    rotates through the spine month by month. Same data as the site; print-to-PDF ready.

    The snapshot cards, the vacancy pulse and the lab-news block were removed on 12 Aug 2026
    (see the rebuild note below): the Monitor landing page already carries them, so a brief that
    restated them was three quarters not about its own theme. Confirmed for the September issue
    by ML on 2 Sep 2026. Do not reintroduce them without a decision on record."""
    from datetime import date
    import os as _os
    today = date.today()
    _ov = _os.environ.get("BRIEF_MONTH_OVERRIDE")     # "YYYY-MM" to draft a specific issue (monthly Action)
    if _ov:
        _y, _m = _ov.split("-"); today = date(int(_y), int(_m), 1)
    sv = lang == "sv"
    def L(en, se): return se if sv else en
    def svn(x): return str(x).replace(".", ",") if sv else str(x)
    MO = {"en": ["January", "February", "March", "April", "May", "June", "July", "August",
                 "September", "October", "November", "December"],
          "sv": ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti",
                 "september", "oktober", "november", "december"]}
    mname = MO[lang][today.month - 1]; issue = f"{today.year}-{today.month:02d}"
    sub = SITE.get("brief_subscribe", "")

    cc = CROSS; dm = DEMAND; smd = {r["code"]: r["adoption"] for r in SWEAD["sizes"]}
    # Sector cut beside the size cut, read from the generated file for the same reason:
    # a typed figure went stale through two freezes once already.
    secd = {r["code"]: r["adoption"] for r in SWESEC["sectors"]}
    # The September finding, computed rather than asserted. The month used to claim that size
    # matters more than sector, which the same table refutes; the honest and more interesting
    # story is what has happened to the spread since 2021. Rows without a 2021 value (the
    # "other services" group) are excluded from the change arithmetic, not silently treated
    # as zero.
    _sec = [r for r in SWESEC["sectors"] if r["code"] != "TotSNI"]
    _sec_prev = [r for r in _sec if r.get("prev")]
    _hi = max(_sec, key=lambda r: r["adoption"])
    _lo = min(_sec, key=lambda r: r["adoption"])
    _gap_now = _hi["adoption"] - _lo["adoption"]
    _gap_then = _hi["prev"] - _lo["prev"]
    _gap_x = _gap_now / _gap_then
    _ratio_now, _ratio_then = _hi["adoption"] / _lo["adoption"], _hi["prev"] / _lo["prev"]
    _fastest = max(_sec_prev, key=lambda r: r["adoption"] / r["prev"])
    _fast_x = _fastest["adoption"] / _fastest["prev"]
    _hi_x = _hi["adoption"] / _hi["prev"]
    def _nm(r):
        return (r["name_sv"] if sv else r["name_en"]).lower()

    # The coda: our own advertisement series on the same industry rows. Only the groups with
    # enough AI advertisements to estimate are named; five of nine are not, and a chart with
    # nine bars where five are noise would be worse than no chart. Prose, and only the contrast
    # the counts support.
    _dm = {r["code"]: r for r in DEMSEC["sectors"] if r["estimable"]}
    _d_hi = max(_dm.values(), key=lambda r: r["demand"])
    _mfg, _svc = _dm.get("10-33"), _dm.get("69-75, 77-82, 95.1")
    _swap = _mfg["demand"] / _svc["demand"] if _mfg and _svc else None
    _ad = {r["code"]: r["adoption"] for r in SWESEC["sectors"]}
    tr = TREND["trend"]            # our own Swedish series: the floor-to-ceiling range
    n_ctry = cc["meta"]["n_countries"]; dver = cc["meta"]["daioe_version"]
    se_share = next(r["share"] for r in cc["countries"] if r["is_se"])
    # NOT an EU average: the set is 36 EU-LFS countries, seven of them outside the EU.
    ctry_mean = cc["meta"]["mean_share"]
    CAL = load("brief_calendar.yaml")["months"]            # confirmed 12-month theme calendar
    cm = CAL.get(today.month, {"theme": "exposure", "title_en": "AI exposure across Europe",
                               "title_sv": "AI-exponering i Europa"})
    theme = cm["theme"]                                    # which built chart+takeaway to show
    titles = {theme: (cm["title_sv"] if sv else cm["title_en"])}   # displayed monthly theme
    # EU first, Sweden in depth: the house order, and Magnus's steer for this theme. Every
    # figure below is picked from the data rather than typed, and the EU ordering is read
    # separately because it is not identical to the Swedish one.
    b_rows = BARRIERS["rows"]
    b_eu_top = max(b_rows, key=lambda r: r["eu"])
    b_eu_low = min(b_rows, key=lambda r: r["eu"])
    b_cost = next(r for r in b_rows if r["name"].lower().startswith("cost"))
    b_se_top = max(b_rows, key=lambda r: r["share"])
    # Levels moved out of this prose on 12 Aug 2026 and into the chart alone. The share is of ALL
    # enterprises, while since 2023 only firms that considered AI and declined are asked, so a
    # level lifted out of the sentence ("7.8% of firms lack AI skills") is wrong in a way the
    # sentence could not prevent. The RANKING survives both that break and the country
    # comparison, because every reason shares a denominator, so the ranking is what the prose
    # asserts and the chart carries the numbers.
    b_eu_rank = sorted(b_rows, key=lambda r: -r["eu"])
    b_se_rank = sorted(b_rows, key=lambda r: -r["share"])
    b_cost_rank = b_eu_rank.index(b_cost) + 1
    b_n = len(b_rows)
    # "Sweden has the same ordering" was in this paragraph for months and is not true: the two
    # rankings agree at the top, at the bottom and on cost, but the three data and legal reasons
    # in between swap around. Now that the sentence asserts a ranking and nothing else, that
    # matters, so the claim is checked. If a vintage changes the pattern the build stops here
    # and the sentence gets rewritten, rather than quietly asserting something false.
    _agree = [i for i, (a, b) in enumerate(zip(b_eu_rank, b_se_rank)) if a["name"] == b["name"]]
    _mid = {r["name"] for r in b_eu_rank[1:4]} == {r["name"] for r in b_se_rank[1:4]}
    if _agree != [0, 4, 5, 6, 7] or not _mid:
        raise SystemExit(
            "brief: the EU and Swedish barrier rankings no longer agree at the top, the bottom "
            "and on cost with only the three middle reasons swapping.\n"
            f"  EU: {[r['name'] for r in b_eu_rank]}\n"
            f"  SE: {[r['name'] for r in b_se_rank]}\n"
            "  Rewrite the sentence in takeaways['barriers']; do not relax this check.")
    takeaways = {
        "exposure": L(
            f"{se_share:.0f}% of Swedish jobs are in the most AI-exposed occupations (the top 25% of occupations by "
            f"DAIOE generative-AI exposure), among the highest of {n_ctry} countries; the mean across "
            f"them is {ctry_mean:.0f}%. The placing depends on where the line is drawn, from 2nd at this quarter cut to 5th "
            f"if only the top 20% of occupations count. Exposure marks where AI overlaps with the work, not "
            f"displacement.",
            f"{se_share:.0f}% av de svenska jobben finns i de mest AI-exponerade yrkena (den mest exponerade "
            f"fjärdedelen, topp 25% efter DAIOE generativ AI-exponering), bland de högsta av {n_ctry} länder; "
            f"snittet över dem är {ctry_mean:.0f}%. Placeringen beror på var gränsen dras, från 2:a vid fjärdedelsgränsen "
            f"till 5:e om bara de 20 procent mest exponerade yrkena räknas. Exponering visar var AI överlappar med "
            f"arbetet, inte förträngning."),
        "demand": L(
            "Demand roughly doubled in a year for most countries (Sweden 1.3% in 2024 to 2.8% in 2025). The Swedish "
            "live job-ad measure is the pulse shown above.",
            "Efterfrågan ungefär fördubblades på ett år i de flesta länder (Sverige 1,3% 2024 till 2,8% 2025). Den "
            "svenska livemätningen av jobbannonser är pulsen ovan."),
        "adoption": L(
            f"Adoption climbs steeply with firm size: {smd['10-49']}% among small firms (10–49 employees) "
            f"against {smd['250-']}% among large ones (250+) in {SWEAD['meta']['year']}, and every size class has risen since {SWEAD['meta']['prev_year']}. "
            f"The industries that adopted least are growing "
            f"fastest in proportional terms and falling further behind all the same: "
            f"{_nm(_fastest)} multiplied its adoption by {_fast_x:.1f} since "
            f"{SWESEC['meta']['prev_year']}, against {_hi_x:.1f} for {_nm(_hi)}, and yet the distance "
            f"between highest and lowest industry widened from {_gap_then} to {_gap_now} percentage "
            f"points. The industries behind are running to stay in place.",
            f"Användningen ökar brant med företagsstorlek: {smd['10-49']}% bland småföretagen (10–49 anställda) "
            f"mot {smd['250-']}% bland de stora (250+) {SWEAD['meta']['year']}, och varje storleksklass har ökat sedan {SWEAD['meta']['prev_year']}. "
            f"De branscher som använde minst AI växer snabbast "
            f"relativt sett och halkar ändå efter: {_nm(_fastest)} har {svn(round(_fast_x,1))}-faldigat "
            f"sin användning sedan {SWESEC['meta']['prev_year']}, mot {svn(round(_hi_x,1))} för "
            f"{_nm(_hi)}, och ändå "
            f"har avståndet mellan högsta och lägsta bransch vuxit från {_gap_then} till {_gap_now} "
            f"procentenheter. Branscherna som ligger efter springer för att stå still."),
        "barriers": L(
            f"Across the EU the obstacle enterprises name most often is people, not money: a lack of "
            f"relevant expertise ranks first of {b_n}, cost only {b_cost_rank}th, and \u201cAI is simply not "
            f"useful to us\u201d last. Sweden puts the same reason first and the same one last, with cost in "
            f"the same place; only the data and legal reasons in between swap around. Read the ranking "
            f"rather than the levels, "
            f"because the levels are shares of all enterprises while since 2023 the question is put only to "
            f"firms that considered AI and decided against it, which Eurostat flags as a break; the chart "
            f"carries them for anyone who wants them. These are therefore the obstacles of firms that engaged "
            f"with the question; the larger group never entered it, and the interesting puzzle is "
            f"why most never consider AI at all.",
            f"I EU är hindret företagen oftast nämner kompetens, inte pengar: brist på relevant kompetens "
            f"rankas först av {b_n}, kostnad först på {b_cost_rank}:e plats, och \u201dAI är inte användbart "
            f"för oss\u201d sist. Sverige sätter samma skäl först och samma sist, med kostnad på samma plats; "
            f"bara data- och juridikskälen däremellan byter inbördes ordning. Läs rangordningen snarare "
            f"än nivåerna: nivåerna "
            f"är andelar av samtliga företag samtidigt som frågan sedan 2023 bara ställs till företag som "
            f"övervägt AI och valt bort det, vilket Eurostat flaggar som ett brott. Diagrammet bär nivåerna "
            f"för den som vill ha dem. Det är alltså hindren hos de företag som tagit sig an frågan; den "
            f"större gruppen kom aldrig in i den, och det intressanta pusslet är varför de flesta "
            f"aldrig överväger AI."),
        "outcomes": L(
            f"In the most AI-exposed occupations, entry-level openings are a smaller share of vacancies than in the "
            f"least-exposed, a gap widening from −{abs(ELS['meta']['gap_first'])}pp to −{abs(ELS['meta']['gap_last'])}pp "
            f"in {ELS['meta']['last_year']}. Descriptive: entry-level hiring is also more cyclical, and "
            f"the tightening cycle hit these occupations hardest, so this cannot separate AI from the cycle.",
            f"I de mest AI-exponerade yrkena utgör instegsjobb en mindre andel av annonserna än i de minst exponerade, "
            f"ett gap som vuxit från −{svn(abs(ELS['meta']['gap_first']))} till −{svn(abs(ELS['meta']['gap_last']))} "
            f"procentenheter {ELS['meta']['last_year']}. Beskrivande: instegsjobb är också mer konjunkturkänsliga, "
            f"och räntehöjningarna slog hårdast mot just dessa yrken, så AI går inte att skilja från konjunkturen här."),
    }
    srcs = {
        "exposure": L(f"DAIOE generative-AI {dver} × Eurostat EU-LFS {cc['meta']['weight_year']}",
                      f"DAIOE generativ AI {dver} × Eurostat AKU {cc['meta']['weight_year']}"),
        "demand": f"{dm['meta']['source']}, {dm['meta']['year']}",
        "adoption": L(f"{SWEAD['meta']['source']}, {SWEAD['meta']['year']}",
                      f"SCB, IT-användning i företag (NV0116), {SWEAD['meta']['year']}"),
        "barriers": L(f"{BARRIERS['meta']['source']}, {BARRIERS['meta']['year']}",
                      f"Eurostat, isoc_eb_ain2, {BARRIERS['meta']['year']}"),
        "outcomes": L(f"{ELS['meta']['source']} × DAIOE {ELS['meta']['daioe_variant']} {ELS['meta']['daioe_version']}",
                      f"{ELS['meta']['source']} × DAIOE generativ AI {ELS['meta']['daioe_version']}"),
    }

    # Where a chart needs one sentence of reading instruction, it goes on the source line
    # rather than into the argument, which is a one-page budget.
    srcnotes = {
        "adoption": L(
            " * No 2021 figure is published for these rows.",
            " * Inget värde för 2021 publiceras för dessa rader."),
    }

    # ── the month's argument ──────────────────────────────────────────────────────────────
    # REBUILT 12 Aug 2026, on Magnus's reading of the August issue. The brief used to open
    # with the four spine numbers and a Sweden-in-international-context paragraph, both of
    # which the Monitor landing page already carries, then give the month's actual theme one
    # paragraph, then close with lab news. Three quarters of it was therefore either the
    # Monitor restated or not about the theme at all. A brief that restates the thing it links
    # to has no reason to exist, so this is now only the month's argument, in three moves:
    # the question, the chart that answers it, and what the answer cannot show. No spine
    # cards, no pulse, no news.
    #
    # `setups` poses the question and `limits` states the honest boundary; `takeaways` above
    # already held the finding. Every figure is read from the data files, never typed in: the
    # demand lede carried v1.1 numbers for two freezes because it was typed, which is the
    # defect this pattern exists to prevent.
    import statistics as _stats
    total_se = SWEAD["meta"]["total"]; eu_adopt = ADOPT["meta"]["eu_avg"]
    dem_med = _stats.median(r["share"] for r in dm["countries"])
    se_dem = next(r["share"] for r in dm["countries"] if r.get("is_se"))
    # The METR task-horizon tile, read from the generated file rather than restated. Matched on
    # the source name at the head of the footnote, the same way the facts loop below matches it.
    metr_h = next((f["num"] for f in CAPABILITY["facts"]
                   if f["foot"].split("·")[0].strip().lower().startswith("metr")), "12–17 h")
    # The tile says "12–17 h" because a tile has no room for a word; prose does.
    metr_en = metr_h.replace(" h", " hours"); metr_sv = metr_h.replace(" h", " timmar")
    epoch_x = CAPABILITY["meta"]["epoch_multiple"]
    # Multiple-response, and asked of ALL enterprises, so the shares cannot be divided between
    # non-adopters. What they DO bound is the share of non-adopters naming any obstacle at all:
    # even if no firm named two, the sum over reasons is the ceiling.
    b_sum = sum(r["share"] for r in BARRIERS["rows"])
    nonad = 100 - total_se
    b_ceiling = b_sum / nonad * 100

    setups = {
        "exposure": L(
            "Which jobs sit closest to what today's AI can already do? Exposure measures the overlap "
            "between an occupation's tasks and the capabilities of generative AI, occupation by "
            "occupation, then weights it by how many people actually hold those jobs in each country. "
            "It is a map of where AI meets the work.",
            "Vilka jobb ligger närmast det som dagens AI redan klarar? Exponering mäter överlappet "
            "mellan ett yrkes uppgifter och generativ AI:s förmågor, yrke för yrke, och viktas sedan "
            "med hur många som faktiskt har de jobben i varje land. Det är en karta över var AI möter "
            "arbetet."),
        "demand": L(
            "Exposure is what AI could touch. Demand is what employers actually ask for, written down "
            "in their own advertisements, and it is the one series here that moves month by month.",
            "Exponering är vad AI skulle kunna beröra. Efterfrågan är vad arbetsgivarna faktiskt ber "
            "om, skrivet i deras egna annonser, och det är den enda serien här som rör sig månad för "
            "månad."),
        "adoption": L(
            "Which firms have actually started using AI, and which have not? Adoption is measured by "
            f"a survey of firms. Every industry uses far more AI than it did in {SWESEC['meta']['prev_year']}, "
            f"so the interesting question is no longer who has started but whether the ones that "
            f"started late are catching up.",
            "Vilka företag har faktiskt börjat använda AI, och vilka har inte? Användningen mäts "
            f"genom en enkät till företagen. Varje bransch använder betydligt mer AI än {SWESEC['meta']['prev_year']}, "
            f"så den intressanta frågan är inte längre vilka som har börjat utan om de som började "
            f"sent hinner i kapp."),
        "barriers": L(
            f"Capability is no longer the obvious constraint. Frontier AI agents now finish tasks "
            f"of up to {metr_en} of human-expert work about half the time, and that length has been "
            f"doubling roughly every four months. Experiments on assigned tasks find real gains: "
            f"15% more customer-support issues resolved per hour in one firm (Brynjolfsson, Li and "
            f"Raymond, 2025); 40% less time and 18% higher quality on professional writing (Noy and "
            f"Zhang, 2023); 12% more consulting tasks, 25% faster, but 19% less accurately on a task "
            f"chosen outside the frontier (Dell'Acqua et al., 2026). Those are narrow "
            f"tasks, set by a researcher and marked against a known standard. Reorganising complex "
            f"work inside a going concern is a different problem, and the evidence that AI pays at "
            f"the level of the firm is much thinner. Yet in {ADOPT['meta']['year']} only "
            f"{eu_adopt:.0f}% of EU enterprises used AI, {total_se}% in Sweden. So why does a "
            f"technology that performs this well on assigned tasks see so little use? Eurostat put "
            f"the question to firms across the EU.",
            f"Förmågan är inte längre den självklara begränsningen. Dagens AI-agenter klarar "
            f"uppgifter på upp till {metr_sv} mänskligt expertarbete ungefär hälften av gångerna, "
            f"och den längden har ungefär fördubblats var fjärde månad. Experiment på tilldelade "
            f"uppgifter visar verkliga vinster: 15% fler kundärenden lösta per timme i ett företag "
            f"(Brynjolfsson, Li och Raymond, 2025); 40% kortare tid och 18% högre kvalitet på "
            f"professionellt skrivande (Noy och Zhang, 2023); 12% fler konsultuppgifter, 25% "
            f"snabbare, men 19% mindre träffsäkert på en uppgift vald utanför det AI behärskar "
            f"(Dell'Acqua m.fl., 2026). Det är avgränsade uppgifter, satta av en forskare "
            f"och bedömda mot en känd måttstock. Att organisera om komplext arbete i en pågående "
            f"verksamhet är ett annat problem, och underlaget för att AI lönar sig på företagsnivå "
            f"är betydligt tunnare. Ändå använde bara {svn(round(eu_adopt))}% av EU:s företag AI "
            f"{ADOPT['meta']['year']}, {total_se}% i Sverige. Varför används då en teknik som "
            f"presterar så här bra på tilldelade uppgifter fortfarande så lite? Eurostat ställde "
            f"frågan till företag i hela EU."),
        "outcomes": L(
            "If AI were already reshaping work, it should show up in what happens to jobs and pay. So "
            "far the clearest signal is not in wages but in who gets hired.",
            "Om AI redan formade om arbetet borde det synas i vad som händer med jobb och löner. "
            "Hittills är den tydligaste signalen inte lönerna utan vem som blir anställd."),
    }
    extras = {
        "adoption": L(
            f"Using AI and hiring for it are "
            f"different decisions, and the same industries do not make both. In our own "
            f"advertisement data, manufacturing asks for a named AI skill {_swap:.0f} times as "
            f"often as the other service industries, {_mfg['demand']}% of its advertisements "
            f"against {_svc['demand']}%, even though SCB records the service firms as the heavier "
            f"users, {_ad['69-75, 77-82, 95.1']}% against {_ad['10-33']}%. One possible explanation: "
            f"manufacturing more often builds its own AI tools and must hire for them, while "
            f"service firms use tools that already exist.",
            f"Att använda AI och att anställa för "
            f"det är olika beslut, och det är inte samma branscher som fattar båda. I våra egna "
            f"annonsdata efterfrågar tillverkningsindustrin en namngiven AI-kompetens {svn(round(_swap))} "
            f"gånger så ofta som de övriga tjänsteföretagen, {svn(_mfg['demand'])}% av annonserna "
            f"mot {svn(_svc['demand'])}%, trots att SCB registrerar tjänsteföretagen som de "
            f"flitigare användarna, {_ad['69-75, 77-82, 95.1']}% mot {_ad['10-33']}%. En möjlig "
            f"förklaring är att tillverkningsindustrin oftare bygger egna AI-verktyg och därför "
            f"behöver rekrytera, medan tjänsteföretagen använder redan framtagna verktyg."),
        "barriers": L(
            "Eurostat surveys the business economy, so the public sector is absent from the chart, "
            "and in Sweden that is a large omission. Our report for the Expert Group on Public "
            "Economics found about a quarter of central government authorities and municipalities "
            "using AI against more than sixty per cent of the regions, with AI concentrated in "
            "administrative support rather than core services. The obstacle named there is "
            "competence again, with a detail the business survey cannot give: the gap is among "
            "leaders as much as among employees. Source: a self-selected Akavia member panel of "
            "1,729 public-sector professionals, May 2024, our own processing.",
            "Eurostat undersöker näringslivet, så offentlig sektor saknas i diagrammet, och i "
            "Sverige är det en stor lucka. Vår ESO-rapport fann att omkring en fjärdedel av de "
            "statliga myndigheterna och kommunerna använder AI, mot över sextio procent av "
            "regionerna, och att AI framför allt används i administrativt stöd snarare än i "
            "kärnverksamheten. Hindret som nämns är kompetens även där, med en precisering som "
            "företagsundersökningen inte kan ge: bristen finns hos ledningen lika mycket som hos "
            "medarbetarna. Källa: Akavias självselekterade medlemspanel med 1 729 "
            "offentliganställda, maj 2024, egen bearbetning."),
    }
    # Section headings carry the month's argument rather than naming the slot they sit in.
    # A reader who skims three headings should come away with the finding, not with
    # "question / data / caveat", which is true of every issue and therefore says nothing.
    # Keyed by theme, like setups, takeaways and limits, so the twelve-month calendar cannot
    # drift from them; a theme without an entry falls back to the old generic labels.
    heads = {
        "barriers": (L("Why so few firms use AI", "Varför så få företag använder AI"),
                     L("Skills, not money", "Kompetens, inte pengar"),
                     L("The ranking travels, the levels do not",
                       "Rangordningen bär, inte nivåerna")),
        "exposure": (L("Which jobs sit closest to AI", "Vilka jobb ligger närmast AI"),
                     L("Sweden is among the most exposed", "Sverige är bland de mest exponerade"),
                     L("Exposure is not displacement", "Exponering är inte förträngning")),
        "demand": (L("What employers actually ask for", "Vad arbetsgivarna faktiskt ber om"),
                   L("Demand is rising and still small",
                     "Efterfrågan stiger och är fortfarande liten"),
                   L("The advertised margin, not demand itself",
                     "Den annonserade marginalen, inte efterfrågan")),
        "adoption": (L("Are the laggards catching up?", "Hinner eftersläntrarna i kapp?"),
                     L("Catching up, and falling behind", "Hinner i kapp, och halkar efter"),
                     L("Use is not intensity", "Användning är inte omfattning")),
        "outcomes": (L("Where AI would show up first", "Där AI skulle synas först"),
                     L("The signal is in hiring, not pay",
                       "Signalen finns i anställandet, inte lönerna"),
                     L("Descriptive, not causal", "Beskrivande, inte kausalt")),
    }
    h_q, h_find, h_lim = heads.get(theme, (L("The question", "Frågan"),
                                           L("What the data show", "Vad data visar"),
                                           L("What it does not show", "Vad det inte visar")))
    limits = {
        "exposure": L(
            "Exposure says nothing about whether AI substitutes for a worker or assists one, and the "
            "country ranking shifts with where the cut is drawn.",
            "Exponering säger ingenting om huruvida AI ersätter eller hjälper den som arbetar, och "
            "ländernas ordning ändras med var gränsen dras."),
        "demand": L(
            "This is the advertised margin of demand, not demand itself: not all hiring is advertised, "
            "and a rising line says employers ask for AI skills more often than they did, not that AI "
            "created or removed a job.",
            "Detta är den annonserade delen av efterfrågan, inte efterfrågan i sig: allt anställande "
            "annonseras inte, och en stigande linje betyder att arbetsgivarna oftare efterfrågar "
            "AI-kompetens, inte att AI skapat eller tagit bort ett jobb."),
        "adoption": L(
            # Shortened on Yifan's review of the September brief: the original ran to five
            # sentences of caveat, three of which were about how to read a gap. This says the
            # two things a reader must not get wrong and stops.
            "These numbers are what firms report in a survey: whether they use AI at all, not how "
            "much they use it, and not an independent measurement of either. The "
            "job-advertisement data measure something else again: whether firms are hiring for "
            "specific AI skills. The two should be compared with care.",
            "Talen är vad företagen uppger i en enkät: om de använder AI över huvud taget, inte "
            "hur mycket, och inte en oberoende mätning av något av det. Annonsdata mäter något "
            "annat: om företagen anställer för specifika AI-kompetenser. De två bör jämföras med "
            "försiktighet."),
        "barriers": L(
            f"Read this as how widespread each obstacle is, not as a division of non-adopters "
            f"between causes. Eurostat allows several answers, so the shares do not sum to a total "
            f"and cannot be rebased onto the {nonad:.0f}% of Swedish firms not using AI. The levels "
            f"are not comparable across years, and for Sweden not across the 2023 break. Nor is any "
            f"of this cut by firm size, where the variation sits: in Sweden {smd['10-49']}% of firms "
            f"with 10 to 49 employees use AI against {smd['250-']}% of those with 250 or more. An "
            f"obstacle named is also not a benefit forgone: the survey records what firms say "
            f"stopped them, not whether adopting would have paid.",
            f"Läs detta som hur utbrett varje hinder är, inte som en uppdelning av dem som avstår "
            f"efter orsak. Eurostat tillåter flera svar, så andelarna summerar inte till en helhet "
            f"och kan inte räknas om till de {svn(round(nonad))}% av de svenska företagen som inte "
            f"använder AI. Nivåerna är inte jämförbara mellan år, och för Sverige inte heller över "
            f"brottet 2023. Ingenting är dessutom uppdelat efter företagsstorlek, där variationen "
            f"finns: i Sverige använder {smd['10-49']}% av företagen med 10 till 49 anställda AI mot "
            f"{smd['250-']}% av dem med 250 eller fler. Ett nämnt hinder är inte heller en utebliven "
            f"vinst: undersökningen registrerar vad företagen uppger stoppade dem, inte om det hade "
            f"lönat sig att införa AI."),
        "outcomes": L(
            "Descriptive, not causal. Entry-level hiring is also more cyclical, and the tightening "
            "cycle hit these occupations hardest, so this cannot separate AI from the cycle.",
            "Beskrivande, inte kausalt. Instegsjobb är dessutom mer konjunkturkänsliga, och "
            "räntehöjningarna slog hårdast mot just dessa yrken, så AI går inte att skilja från "
            "konjunkturen här."),
    }

    if theme == "exposure":
        th_chart = barplot(nordic(cc["countries"]), ctry_mean, 10 * (int(max(r["share"] for r in cc["countries"]) // 10) + 1),
                           cc["meta"]["weight_year"], "share", ".0f",
                           mean_label=f'{cc["meta"]["n_countries"]}-country')
    elif theme == "demand":
        th_chart = barplot(dm["countries"], 0, int(max(r["share"] for r in dm["countries"])) + 1, 0, "share", ".1f")
    elif theme == "barriers":
        # The SV edition must not carry English bar labels (the one-pager shipped with the same
        # class of bug); rows with a name_sv swap it in, others fall back to the English name.
        rows_b = ([{**r, "name": r.get("name_sv", r["name"])} for r in BARRIERS["rows"]]
                  if sv else BARRIERS["rows"])
        # Sweden against the EU on the same rows, because the finding now leads with the EU.
        # lang follows the sheet, so a shortened Swedish label is marked "m.m." and not "etc.".
        # The same omission put English bar labels on the Swedish sheet once already; see
        # build_onepager.py::barrier_bars.
        th_chart = barplot(rows_b, 0,
                           int(max(max(r["share"], r["eu"]) for r in BARRIERS["rows"])) + 1, 0,
                           "share", ".1f", what="reasons", cmp_key="eu",
                           series_label=L("Sweden","Sverige"), cmp_label="EU",
                           lang="sv" if sv else "en")
    elif theme == "adoption":
        # Two charts, not one. The month is about both cuts, and the sector cut is the one that
        # carries the finding: the spread across industries is wider than the spread across size
        # classes, on the same SCB survey and the same year. Sector rows carry name_en/name_sv,
        # so the Swedish sheet swaps the label the same way the barriers branch does; English
        # bar labels on a Swedish sheet have shipped once already.
        _secmax = 10 * (max(r["adoption"] for r in SWESEC["sectors"]) // 10 + 1)
        rows_s = [{**r, "name": (r["name_sv"] if sv else r["name_en"])} for r in SWESEC["sectors"]]
        # The size rows had the same defect and nobody had caught it: the Swedish brief was
        # rendering "250+ employees" and "Headline: 10+" on a Swedish sheet. name_sv added to
        # swe_adoption.yaml on 31 Aug 2026; swap it in here the same way.
        # Lydia's SV proofread, 3 Sep 2026: four bars carry no pp change and the sheet did not
        # say why. SCB publishes no 2021 value for the three micro classes or for the 10+ total
        # (verified against the API, 3 Sep), so the gap is the source's, not ours. Mark those
        # rows and explain the mark on the source line.
        rows_z = [{**r, "name": ((r.get("name_sv") or r["name"]) if sv else r["name"])
                                + ("" if r.get("prev") is not None else "*")}
                  for r in SWEAD["sizes"]]
        th_chart = (
            barplot(rows_z, ADOPT["meta"]["eu_avg"],
                    10 * (max(r["adoption"] for r in SWEAD["sizes"]) // 10 + 1), 0,
                    "adoption", ".0f", what="firm-size classes", lang="sv" if sv else "en")
            + f'<p class="secintro" style="margin:18px 0 6px">'
              f'{L("And by industry, on the same survey and the same year.", "Och per bransch, samma undersökning och samma år.")}</p>'
            + barplot(rows_s, 0, _secmax, 0, "adoption", ".0f", what="industries",
                      cmp_key="prev", series_label=str(SWESEC["meta"]["year"]),
                      cmp_label=str(SWESEC["meta"]["prev_year"]), lang="sv" if sv else "en"))
    else:
        th_chart = squeeze_svg(ELS)
    th_title = titles[theme]

    en_cur = '' if sv else ' aria-current="page"'
    sv_cur = ' aria-current="page"' if sv else ''
    subscribe = f'<a class="btn ghost" href="{sub}">{L("Subscribe monthly","Prenumerera")}</a>' if sub else ""

    body = f"""<div class="wrap brief"><article class="briefsheet">
  <header class="bhead">
    <div><p class="kicker">{L("AIEL Monitor · monthly brief","AIEL Monitor · månadsbrev")} · {issue}</p>
      <h1 class="btitle">{L("AI and the labour market","AI och arbetsmarknaden")}, {mname} {today.year}</h1>
      <p class="bsub">{L("A monthly snapshot from the AI-Econ Lab: international, with Sweden in depth, on public data.", "En månatlig ögonblicksbild från AI-Econ Lab: internationell, med Sverige på djupet, byggd på öppna data.")}
        {L("In focus this month","I fokus denna månad")}: {h(th_title)}.</p></div>
    <div class="bactions">
      <button class="btn primary" id="printbrief" type="button">{L("↓ Download PDF","↓ Ladda ner PDF")}</button>
      {subscribe}
      <span class="blang"><a href="/monitor/brief/"{en_cur}>EN</a> · <a href="/monitor/brief/sv/"{sv_cur}>SV</a></span>
      <a class="bback" href="/monitor/">{L("← the live monitor","← den levande monitorn")}</a></div>
  </header>

  <section class="bsec"><h2 class="bh2">{h(h_q)}</h2>
    <p class="bp">{setups[theme]}</p></section>

  <section class="bsec"><h2 class="bh2">{h(h_find)}</h2>
    <div class="bchart">{th_chart}</div>
    <p class="bp">{takeaways[theme]}</p>
    {f'<p class="bp">{extras[theme]}</p>' if theme in extras else ''}
    <p class="bsrc">{L("Source","Källa")}: {h(srcs[theme])}. {L("Full method at","Fullständig metod på")} ai-econlab.com/monitor/#method.{h(srcnotes.get(theme, ""))}</p></section>

  <section class="bsec bsec--note"><h2 class="bh2">{h(h_lim)}</h2>
    <p class="bp">{limits[theme]}</p></section>

  <footer class="bfooter">
    <div class="bfoot-row">
      <span>AI-Econ Lab · AIEL Monitor · {issue}. {L("Public data; cite the version and date.","Öppna data; ange version och datum vid citering.")}</span>
      <span>ai-econlab.com/monitor</span>
    </div>
    <div class="bpartner">
      <div class="bpartner-marks">{partner_mark("aiscaf", 18, "AISCAF")}{partner_mark("wasphs", 9, "WASP-HS")}</div>
      <span>{L("Örebro University and RATIO. Örebro is one of AISCAF&#39;s three nodes; the cluster, financed by WASP-HS, funds part of the lab&#39;s team.",
                "Örebro universitet och RATIO. Örebro är en av AISCAF:s tre noder; klustret, som finansieras av WASP-HS, avlönar en del av labbets medarbetare.")}</span>
    </div></footer>
</article></div>"""
    return shell(f"{L('AIEL Monitor Brief','AIEL Monitor-brief')}, {mname} {today.year} · {SITE['brand']['name']}",
                 L(f"A monthly one-page snapshot of AI in the labour market from the AI-Econ Lab: {mname} {today.year}.",
                   f"En månatlig ögonblicksbild av AI på arbetsmarknaden från AI-Econ Lab: {mname} {today.year}."),
                 "/monitor/brief/sv/" if sv else "/monitor/brief/", body)

# ── write ────────────────────────────────────────────────────────────────────
def methods():
    """Public documentation of the Swedish demand definition. Added 4 Aug 2026.

    Exists because the Monitor's method paragraph used to end "available on request" on a
    page selling checkability. The honest inventory in the status block is the point of the
    page: what is published, and what is not yet, each stated plainly. Do not quietly drop
    the pending list once items land, move them to the published list."""
    md = METHODS
    bounds = "".join(f'<div class="prod"><h3>{h(b["k"])}</h3><p>{h(b["what"])}</p></div>'
                     for b in md["bounds"])
    layers = "".join(f'<tr><td><b>{h(l["name"])}</b></td><td class="tnum">{h(l["n"])}</td>'
                     f'<td>{h(l["source"])}</td></tr>' for l in md["lexicon"]["layers"])
    vers = ""
    for v in md["versions"]:
        chg = "".join(f"<li>{h(c)}</li>" for c in v["changes"])
        chip = '<span class="vint" style="margin:0">current</span>' if v.get("current") else ""
        vers += f"""<div class="vblock">
      <div class="vhead"><span class="vname">{h(v["version"])}</span>
        <span class="vmeta">frozen {h(v["frozen"])} · fingerprint <code>{h(v["fingerprint"])}</code></span>{chip}</div>
      <p class="secintro" style="margin:8px 0 0;max-width:80ch">{h(v["summary"])}</p>
      <ul class="reslist" style="margin-top:10px">{chg}</ul>
      <p class="psub" style="margin-top:10px"><b>Validation.</b> {h(v["validation"])}</p>
      <p class="psub" style="margin-top:6px">{h(v["note"])}</p></div>"""
    pub = "".join(f"<li>{h(x)}</li>" for x in md["status"]["published"])
    pend = "".join(f"<li>{h(x)}</li>" for x in md["status"]["pending"])
    refs = "".join(f"<li>{h(r)}</li>" for r in md["references"])
    body = f"""<div class="wrap"><div class="pagehead">
  <p class="kicker">The AIEL Monitor · methods</p><h2 class="sec">{h(md["headline"])}</h2>
  <p class="secintro">{h(md["lede"])}</p></div></div>

<div class="wrap"><section style="padding-top:4px">
  <div class="depth"><p class="dk">What we are measuring</p>
    <p class="secintro" style="margin:0"><b>{h(md["estimand"]["target"])}</b> {h(md["estimand"]["not"])}</p>
    <p class="secintro" style="margin:10px 0 0">{h(md["estimand"]["naming"])}</p></div>
</section></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">A range, not a point</p>
  <h2 class="sec">Floor, ceiling, and the gap between them.</h2>
  <div class="two" style="grid-template-columns:1fr 1fr 1fr">{bounds}</div>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">The lexicon</p>
  <h2 class="sec">Where the words come from.</h2>
  <p class="secintro">{h(md["lexicon"]["intro"])}</p>
  <div class="tblwrap" style="margin-top:18px"><table class="dtable">
    <thead><tr><th>Layer</th><th>Size</th><th>Source</th></tr></thead>
    <tbody>{layers}</tbody></table></div>
  <p class="secintro" style="margin-top:18px"><b>Admission discipline.</b> {h(md["lexicon"]["admission"])}</p>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">Version history</p>
  <h2 class="sec">Every published figure names the version that produced it.</h2>
  {vers}
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">Public checkability</p>
  <h2 class="sec">What is published, and what is not yet.</h2>
  <div class="two">
    <div><div class="grouphdr">Published</div>
      <ul class="reslist">{pub}</ul></div>
    <div><div class="grouphdr">Not yet published</div>
      <ul class="reslist">{pend}</ul></div>
  </div>
  <p class="secintro" style="margin-top:22px"><b>On external benchmarks.</b> {h(md["benchmark_logic"])}</p>
  <p class="secintro" style="margin-top:14px"><b>Who funds this.</b> The Monitor has no dedicated funder.
    The grants and institutions behind the research it is built from are listed in full on the
    <a href="{md.get("funding_href", "/about/#support")}">support disclosure</a>.</p>
</section></div></div>

<div class="wrap"><section>
  <div class="grouphdr">How to cite</div>
  <p class="citebox">{h(md["cite"])}</p>
  <div class="grouphdr" style="margin-top:24px">References</div>
  <ul class="reslist">{refs}</ul>
  <p style="margin-top:22px"><a class="mono" style="font-size:12.5px" href="/monitor/">← Back to the Monitor</a></p>
</section></div>"""
    return shell(f"Methods · The AIEL Monitor · {SITE['brand']['name']}",
                 "How the AIEL Monitor measures advertised AI-skill demand: estimand, lexicon sources, "
                 "version history with fingerprints, and validation.",
                 "/monitor/methods/", body)

def redirect(dest):
    """A bare stub for a retired URL that other people's archives still point at.

    The seminar reminder mails carry a link to the series page, and every reminder already
    sitting in a recipient's mailbox points at /seminars, which this site has no route for:
    since the 14 Aug 2026 DNS cutover that path has returned 404. A stub costs one file and
    keeps those links alive. Meta-refresh moves the browser, canonical tells the crawler where
    the content really is, noindex stops the stub competing with the real page in search, and
    the visible link covers anyone whose browser ignores the refresh.
    """
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta http-equiv="refresh" content="0; url={dest}">'
            f'<link rel="canonical" href="{BASE}{dest}">'
            '<meta name="robots" content="noindex,follow">'
            '<title>Moved</title></head>'
            f'<body><p>This page has moved to <a href="{dest}">{dest}</a>.</p></body></html>')


PAGES = {"index.html": home(), "monitor/index.html": monitor(), "daioe/index.html": daioe(),
         "monitor/methods/index.html": methods(),
         "monitor/brief/index.html": brief("en"), "monitor/brief/sv/index.html": brief("sv"),
         "research/index.html": research(), "people/index.html": people(),
         "events/index.html": events(), "news/index.html": news(), "about/index.html": about(),
         # Retired route kept alive for the reminder mails already in people's archives.
         # Deliberately absent from sitemap.xml: a redirect stub is not a page to index.
         "seminars/index.html": redirect("/events/")}

def chart_standalone(svg, title=None, source=None):
    """Self-contained SVG for download (inline light-theme styles; no page CSS).

    TITLE AND SOURCE TRAVEL WITH THE FILE. These downloads are what end up in other people's
    slides and papers, detached from the page that explains them, so a figure that leaves here
    unlabelled is a figure that gets attributed to nobody and dated to nothing. The band is
    appended below the plot and the viewBox grown to fit, so no existing geometry moves.
    """
    style = ('<style>:root{--c1:#0072b2;--c2:#d55e00;--c3:#009e73;--c4:#cc79a7;--ink:#161d2b}'  # monthly series draws with var(); the page CSS is not present in a downloaded file
             '.rankchart{font-family:ui-monospace,Menlo,monospace}svg{background:#ffffff}'
             '.grid,.rowguide{stroke:#e7e4dd}.rowguide{opacity:.6}'
             '.meanline{stroke:#8a8a8a;stroke-dasharray:3 3}.meanlab,.tick{fill:#6d6a63;font-size:9px}'
             '.dname{fill:#3f3d39;font-size:10px}.dname.se{fill:#0072b2;font-weight:700}'
             '.dot{fill:#9a9a9a}.dot.se{fill:#0072b2}.bar{fill:#9a9a9a}.bar.se{fill:#0072b2}'
             '.dval{fill:#6d6a63;font-size:9.5px}.dval.se{fill:#0072b2;font-weight:700}'
             '.ddelta{fill:#6d6a63;font-size:8.5px}'
             # trend line
             '.trendarea{fill:#0072b2;opacity:.08}.trendline,.trenddash{fill:none;stroke:#0072b2;stroke-width:2}'
             '.trenddash{stroke-dasharray:4 3}.trenddot{fill:#0072b2}.trendval{fill:#0072b2;font-size:11px;font-weight:700}'
             # entry-level squeeze
             '.sqband{fill:#0072b2;opacity:.10}.sqlo{fill:none;stroke:#009e73;stroke-width:2}'
             '.sqhi{fill:none;stroke:#0072b2;stroke-width:2.6}.sqdot.lo{fill:#009e73}.sqdot.hi{fill:#0072b2}'
             '.sqval{font-size:11px;font-weight:700}.sqval.lo{fill:#009e73}.sqval.hi{fill:#0072b2}'
             # working-conditions dumbbell
             '.dumb{display:block}.dbtrack{stroke:#d9d5cd;stroke-width:3}.dblo{fill:#009e73}.dbhi{fill:#0072b2}</style>')
    style = style.replace('</style>',
                          '.figttl{fill:#161d2b;font-size:12px;font-weight:700}'
                          '.figsrc{fill:#6d6a63;font-size:8.5px}</style>')
    s = svg.replace('<svg class="rankchart', '<svg xmlns="http://www.w3.org/2000/svg" class="rankchart', 1)
    if title or source:
        m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', s)
        if m:
            w, hgt = float(m.group(1)), float(m.group(2))
            band = 20 if title else 0
            band += 13 if source else 0
            parts = []
            y = hgt + 14
            if title:
                parts.append(f'<text class="figttl" x="8" y="{y:.0f}">{h(title)}</text>')
                y += 13
            if source:
                parts.append(f'<text class="figsrc" x="8" y="{y:.0f}">{h(source)}</text>')
            s = s.replace(m.group(0), f'viewBox="0 0 {w:g} {hgt + band:g}"', 1)
            s = s.replace("</svg>", "".join(parts) + "</svg>", 1)
    i = s.index(">") + 1
    return s[:i] + style + s[i:]

def emit_data(out):
    """Item 10: write the CSVs (and the View-A SVG) that the figure footers link to."""
    import csv as _csv
    d = out / "assets" / "data"; d.mkdir(parents=True, exist_ok=True)
    with (d / "cross_country.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f); w.writerow(["code", "country", "top_tier_share_pct", "daioe_genai_score", "emp_coverage_pct", "lfs_year"])
        for r in CROSS["countries"]: w.writerow([r["code"], r["name"], r["share"], r["exposure"], r["coverage"], r["year"]])
    _ccx = 10 * (int(max(r["share"] for r in CROSS["countries"]) // 10) + 1)
    (d / "cross_country.svg").write_text(
        chart_standalone(barplot(CROSS["countries"], CROSS["meta"]["mean_share"], _ccx,
                                 CROSS["meta"]["weight_year"], "share", ".0f",
                                 mean_label=f'{CROSS["meta"]["n_countries"]}-country')), encoding="utf-8")
    with (d / "cross_country_adoption.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f); w.writerow(["code", "country", "pct_using_ai", "year", "pct_prev_wave", "prev_year"])
        for r in ADOPT["countries"]:
            w.writerow([r["code"], r["name"], r["adoption"], r["year"], r.get("prev", ""), ADOPT["meta"]["prev_year"]])
    _xmax = 5 * (int(max(r["adoption"] for r in ADOPT["countries"]) // 5) + 1)
    (d / "cross_country_adoption.svg").write_text(
        chart_standalone(barplot(ADOPT["countries"], ADOPT["meta"]["eu_avg"], _xmax, ADOPT["meta"]["year"])), encoding="utf-8")
    with (d / "cross_country_demand.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f); w.writerow(["country", "pct_job_postings_requiring_ai", "year"])
        for r in DEMAND["countries"]: w.writerow([r["name"], r["share"], r["year"]])
    _dxmax = int(max(r["share"] for r in DEMAND["countries"])) + 1
    (d / "cross_country_demand.svg").write_text(
        chart_standalone(barplot(DEMAND["countries"], 0, _dxmax, 0, "share", ".1f")), encoding="utf-8")
    with (d / "vocabulary.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["period", "pct_machine_learning", "pct_early_era", "pct_generative",
                    "pct_generic_ai", "pct_other", "term_matches"])
        for r in VOCAB["series"]:
            w.writerow([r["p"], r["ml"], r["early"], r["genai"], r["generic"], r["other"], r["n"]])
    (d / "vocabulary.svg").write_text(chart_standalone(vocabulary_svg(VOCAB), "What words the AI ads use, by era",
                                                             f'JobTech historical job ads (CC0) · distinct advertisements · {VOCAB["meta"]["first"]}-{VOCAB["meta"]["last"]} · AI-Econ Lab'), encoding="utf-8")
    with (d / "ai_governance.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f); w.writerow(["year", "governance_ads", "pct_of_ai_ads", "partial_year"])
        for r in GOV["series"]:
            w.writerow([r["year"], r["n"], r["pct_of_ai"], int(bool(r.get("partial")))])
    (d / "ai_governance.svg").write_text(chart_standalone(governance_svg(GOV), "Ads mentioning AI-governance language, Sweden",
                                                                "JobTech historical job ads (CC0) · distinct advertisements · AI-Econ Lab"), encoding="utf-8")
    with (d / "job_quality.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["year", "pct_full_time_ai", "pct_full_time_other", "gap_pp_full_time",
                    "pct_permanent_ai", "pct_permanent_other", "gap_pp_permanent",
                    "pct_regular_ai", "pct_regular_other", "gap_pp_regular", "n_ai_ads"])
        for r in JOBQ["series"]:
            w.writerow([r["year"], r["ft_ai"], r["ft_other"], r["ft_gap"],
                        r["pm_ai"], r["pm_other"], r["pm_gap"],
                        r["rg_ai"], r["rg_other"], r["rg_gap"], r["n_ai"]])
    (d / "job_quality.svg").write_text(chart_standalone(jobquality_svg(JOBQ), "Job quality gap: AI-skill ads minus all others",
                                                             "JobTech historical job ads (CC0) · distinct advertisements · AI-Econ Lab"), encoding="utf-8")
    with (d / "monthly_ai_share.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["year_month", "ads", "ai_any_pct", "ai_any_pct_12m_mean",
                    "floor_pct", "floor_pct_12m_mean"])
        for r in MONTHLY["series"]:
            w.writerow([r["m"], r["ads"], r["ai"], r["ai_ma"], r["floor"], r["floor_ma"]])
    (d / "monthly_ai_demand.svg").write_text(chart_standalone(monthly_svg(MONTHLY), "Swedish job ads asking for an AI skill, monthly",
                         f'JobTech historical job ads (CC0) · {MONTHLY["meta"].get("definition", f"frozen {DEF_VERSION}")} · distinct advertisements · {MONTHLY["meta"]["first"]}-{MONTHLY["meta"]["last"]} · AI-Econ Lab'), encoding="utf-8")
    with (d / "working_conditions.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f); w.writerow(["condition", "gender", "pct_least_exposed_occ", "pct_most_exposed_occ", "daioe", "wc_year"])
        for c in WORKCOND["conditions"]:
            for g in ("all", "women", "men"):
                w.writerow([c["label"], g, c[g]["lo"], c[g]["hi"], WORKCOND["meta"]["daioe_version"], WORKCOND["meta"]["wc_year"]])
    with (d / "akavia_ai_use.csv").open("w", newline="", encoding="utf-8") as f:
        # WAVE LABELS ARE DERIVED, NEVER TYPED. This header read pct_using_ai_2025 /
        # pct_using_ai_2023 while the values under it had been moved to May 2026 and May 2024,
        # so the published download asserted a 2025-vs-2023 comparison -- which is precisely the
        # cross-wording-break comparison the page's own prose disavows. The bars and the
        # comparator move whenever a wave lands; the header did not, because it was a string.
        _ak = AKAVIA["trend"]
        _now, _prev = _ak["clean_pair"]["to"], _ak["clean_pair"]["from"]
        _slug = lambda lab: lab.lower().replace(" ", "_")
        w = _csv.writer(f)
        # comparable_with_previous marks the wording breaks the trend crosses. Without it the
        # five rows read as one series, which is the misreading the caveat exists to prevent
        # and which a downloaded file carries no caveat to prevent.
        w.writerow(["cut", "group", f"pct_using_ai_{_slug(_now)}", f"pct_using_ai_{_slug(_prev)}",
                    "ci_low", "ci_high", "respondents", "comparable_with_previous", "source"])
        for cut, key in (("profession", "by_profession"), ("sector", "by_sector")):
            for r in AKAVIA[key]:
                w.writerow([cut, r["name"], r["adoption"], r["prev"], r["lo"], r["hi"],
                            r["n"], "yes", AKAVIA["meta"]["source"]])
        breaks = set(_ak.get("breaks_after") or [])
        prev_lab = None
        for lab, v in zip(_ak["labels"], _ak["values"]):
            cmp_ = "" if prev_lab is None else ("no" if prev_lab in breaks else "yes")
            w.writerow(["all", lab, v, "", "", "", "", cmp_, AKAVIA["meta"]["source"]])
            prev_lab = lab
    if AKAVIA.get("movement_governance"):
        _mg = AKAVIA["movement_governance"]
        with (d / "akavia_policy_flow.csv").open("w", newline="", encoding="utf-8") as f:
            w = _csv.writer(f)
            w.writerow(["measure", "pct", "ci_low", "ci_high", "respondents", "base",
                        "counts", "period", "weighted_on", "source"])
            for key, base in (
                    ("gained", "linked respondents who did NOT know of a policy in the first round"),
                    ("lost", "linked respondents who DID know of a policy in the first round")):
                r = _mg[key]
                w.writerow([key, r["value"], r["lo"], r["hi"], r["n"], base, _mg["counts"],
                            _mg["period"], _mg["weighted_on"], AKAVIA["meta"]["source"]])
            for key, lab in (("from", "level_start"), ("to", "level_end")):
                w.writerow([lab, _mg["level"][key], "", "", _mg["level"]["n"],
                            "linked respondents answering in both rounds", _mg["counts"],
                            _mg["period"], _mg["weighted_on"], AKAVIA["meta"]["source"]])
            for k, v in _mg["attrition_check"].items():
                w.writerow([f"context_{k}", v, "", "", "",
                            "context: linked subsample against the full round", _mg["counts"],
                            _mg["period"], _mg["weighted_on"], AKAVIA["meta"]["source"]])
    if AKAVIA.get("movement"):
        _mv = AKAVIA["movement"]
        with (d / "akavia_movement.csv").open("w", newline="", encoding="utf-8") as f:
            w = _csv.writer(f)
            # Each measure states its own base: "started" and "stopped" sit on subgroups of the
            # linked sample, not on the round, and a download without that reads as one base.
            w.writerow(["measure", "pct", "respondents", "base", "period", "weighted_on", "source"])
            _base = {"started": "linked respondents who reported never using AI in the first round",
                     "stopped": "linked respondents who reported using AI in the first round"}
            for k in ("started", "stopped", "more_often", "unchanged", "less_often"):
                w.writerow([k, _mv[k]["value"], _mv[k]["n"],
                            _base.get(k, "linked respondents answering in both rounds"),
                            _mv["period"], _mv["weighted_on"], AKAVIA["meta"]["source"]])
            for k, lab in (("from", "regular_use_start"), ("to", "regular_use_end")):
                w.writerow([lab, _mv["regular_use"][k], _mv["more_often"]["n"],
                            "linked respondents answering in both rounds",
                            _mv["period"], _mv["weighted_on"], AKAVIA["meta"]["source"]])
            _ac = _mv["attrition_check"]
            for k, v in _ac.items():
                w.writerow([f"context_{k}", v, "", "context: linked subsample against the full round",
                            _mv["period"], _mv["weighted_on"], AKAVIA["meta"]["source"]])
        (d / "akavia_movement.svg").write_text(
            chart_standalone(akavia_movement_svg(_mv)), encoding="utf-8")
    _akx = 10 * (max(r["adoption"] for r in AKAVIA["by_profession"]) // 10 + 1)
    (d / "akavia_ai_use.svg").write_text(
        chart_standalone(barplot(AKAVIA["by_profession"], 0, _akx, 0, "adoption", ".0f", what="professions")),
        encoding="utf-8")
    with (d / "population_ai.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        pm = POPAI["meta"]
        w.writerow(["group", f"pct_using_genai_{pm['year']}", "moe_pp",
                    f"pct_using_genai_{pm['first_year']}", "unit", "source"])
        w.writerow(["all 16-74", pm["headline"], pm["headline_moe"], pm["headline_first"],
                    pm["unit"], pm["source"]])
        w.writerow(["men 16-74", pm["men"], "", pm["men_first"], pm["unit"], pm["source"]])
        w.writerow(["women 16-74", pm["women"], "", pm["women_first"], pm["unit"], pm["source"]])
        for r in POPAI["by_age"]:
            w.writerow([r["group"], r["adoption"], r["moe"], r["prev"], pm["unit"], pm["source"]])
    _popx = 10 * (max(r["adoption"] for r in POPAI["by_age"]) // 10 + 1)
    (d / "population_ai.svg").write_text(
        chart_standalone(barplot(_pop_age_rows(), POPAI["meta"]["headline"], _popx, 0,
                                 "adoption", ".0f", what="age groups",
                                 mean_label="Sweden")),
        encoding="utf-8")
    with (d / "akavia_governance.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        # The break column travels with the download. A file carries no footnote, and the four
        # rows otherwise read as one series, which is the misreading the page marks.
        w.writerow(["wave", "pct_uses_ai", "pct_knows_of_policy", "pct_knows_of_strategy",
                    "strategy_comparable_with_previous"])
        g = AKAVIA["governance"]
        _sbreaks = set((g.get("breaks_after") or {}).get("strategy") or [])
        _prev = None
        for row in zip(g["labels"], g["use"], g["policy"], g["strategy"]):
            # Blank on the first row: there is no previous wave to be comparable with.
            cmp_ = "" if _prev is None else ("no" if _prev in _sbreaks else "yes")
            w.writerow(list(row) + [cmp_])
            _prev = row[0]
        w.writerow([])
        w.writerow(["indicator", "pct", "universe", ""])
        s = AKAVIA["shadow"]
        for k in ("private_account", "employer_pays", "self_pays"):
            w.writerow([k, s[k], s["universe"], ""])
        for r in AKAVIA["used_for"]:
            w.writerow([f"used_for_{r['label']}", r["value"], "AI users", ""])

    with (d / "daioe_most_least.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f); w.writerow(["occupation", "daioe_genai_score", "group", "daioe_version"])
        for it in DAIOE_EXP["most"]:  w.writerow([it["occ"], it["score"], "most_exposed", f"v{DAIOE_EXP['year']}"])
        for it in DAIOE_EXP["least"]: w.writerow([it["occ"], it["score"], "least_exposed", f"v{DAIOE_EXP['year']}"])
    t = TREND["trend"]
    with (d / "ai_in_demand_trend.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["year", "names_ai_skill_pct", "asks_for_ai_in_role_pct", "definition"])
        fv = t.get("floor_values") or [""] * len(t["years"])
        for y, v, fl in zip(t["years"], t["values"], fv):
            w.writerow([y, v, fl, f"{TREND['meta']['definition']} fp {TREND['meta']['def_fp']} · distinct advertisements"])
    (d / "ai_in_demand_trend.svg").write_text(chart_standalone(trend_svg(t), "Swedish job ads naming an AI skill, 2006 onwards",
                                                                 f"JobTech / Platsbanken job ads (CC0) · {TREND['meta']['definition']} · distinct advertisements · AI-Econ Lab"), encoding="utf-8")
    with (d / "entry_level_squeeze.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["year", "entry_level_share_least_exposed_pct", "entry_level_share_most_exposed_pct", "gap_pp"])
        for r in ELS["series"]: w.writerow([r["year"], r["low"], r["high"], r["gap"]])
    (d / "entry_level_squeeze.svg").write_text(chart_standalone(squeeze_svg(ELS), "Entry-level openings by AI-exposure tercile, Sweden",
                                                                    "JobTech / Platsbanken (CC0) x DAIOE genAI v2023 · ad records, not distinct advertisements · AI-Econ Lab"), encoding="utf-8")
    (d / "working_conditions.svg").write_text(
        chart_standalone(dumbbell_svg(WORKCOND["conditions"], "all", active=True)), encoding="utf-8")
    with (d / "wages_exposure.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["country", "year", "exposure_tercile", "wage_index_base100"])
        for c in WAGES["countries"]:
            for r in c["series"]:
                for g in ("high", "mid", "low"):
                    w.writerow([c["key"], r["year"], g, r[g]])
    for c in WAGES["countries"]:
        (d / f"wages_{c['key']}.svg").write_text(
            chart_standalone(wages_svg(c), f"Median wage by AI-exposure tercile, {c['label']}",
                             f"{c['source']} · AI-Econ Lab"), encoding="utf-8")
    with (d / "occupation_tiers.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        # occupation is the official title, always in full: a data file has no width to run
        # out of, and a download that quietly abbreviated its key would be worse than useless
        # for joining. occupation_short is what the charts print, given for every row rather
        # than only the long ones, so the column can be used without a fallback.
        w.writerow(["occupation", "occupation_short", "ai_ads", "builds_pct", "integrates_pct",
                    "uses_pct", "year"])
        for r in OCCTIER["rows"]:
            w.writerow([r["name"], shorten(str(r["name"])), r["n"], r["builder"], r["integrator"],
                        r["user"], OCCTIER["meta"]["year"]])
    with (d / "occupations_ai_demand.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        # Full official title, the Swedish title the employment service uses, and the display
        # label the charts print. See the tiers export above for why the full title stays.
        w.writerow(["occupation", "occupation_sv", "occupation_short", "asks_for_ai_in_role_pct",
                    "advertisements", "year", "group"])
        for grp in ("top", "zero"):
            for r in OCCUP[grp]:
                w.writerow([r["name"], r.get("name_sv", ""), shorten(str(r["name"])),
                            r["share"], r["ads"], OCCUP["meta"]["year"], grp])
    _occx = int(max(r["share"] for r in OCCUP["top"])) + 1
    (d / "occupations_ai_demand.svg").write_text(
        chart_standalone(barplot(OCCUP["top"] + OCCUP["zero"], OCCUP["meta"]["national"],
                                 _occx, 0, "share", ".1f",
                                 mean_label="Sweden")), encoding="utf-8")
    with (d / "swe_adoption.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["firm_size", "pct_using_ai", "year", "pct_prev_wave", "prev_year"])
        for r in SWEAD["sizes"]:
            w.writerow([r["name"], r["adoption"], SWEAD["meta"]["year"], r.get("prev", ""), SWEAD["meta"]["prev_year"]])
    with (d / "nordic_adoption_size.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["country", "firm_size", "pct_using_ai", "year", "pct_prev_wave", "prev_year"])
        for c in NORDSZ["countries"]:
            for z in c["sizes"]:
                w.writerow([c["name"], z["name"], z["adoption"], NORDSZ["meta"]["year"],
                            z.get("prev") if z.get("prev") is not None else "",
                            NORDSZ["meta"]["prev_year"]])
    _swxmax = 10 * (max(r["adoption"] for r in SWEAD["sizes"]) // 10 + 1)
    (d / "swe_adoption.svg").write_text(
        chart_standalone(barplot(SWEAD["sizes"], SWEAD["meta"]["total"], _swxmax, 0, "adoption", ".0f",
                                 what="firm-size classes", mean_label="Sweden 10+")), encoding="utf-8")

ONEPAGERS = ("aiel-monitor-onepager.pdf", "aiel-monitor-onepager-sv.pdf")


def build():
    # CARRY THE ONE-PAGER PDFS ACROSS THE WIPE. build() deletes OUT and regenerates the sheets
    # at the end through LaTeX, which only exists on Magnus's Mac (build_onepager.py hardcodes
    # /opt/homebrew/bin/tectonic). On the GitHub runner that step fails softly, so the wipe was
    # the whole story: the PDFs vanished from docs/, `git add -A` committed the deletion, and
    # the six links to them from the homepage and the Monitor page went dead. That is precisely
    # what happened on 12 Aug 2026, two days before the launch, having sat latent since the
    # sheets were added on the 10th. Keeping the previous bytes means a machine that cannot
    # rebuild the sheet republishes the last good one instead of removing it.
    carried = {n: (OUT / n).read_bytes() for n in ONEPAGERS if (OUT / n).exists()}
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for name, htmlstr in PAGES.items():
        p = OUT / name; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(htmlstr, encoding="utf-8")
    shutil.copytree(ROOT / "assets", OUT / "assets")   # recurses into assets/people/ etc.
    emit_data(OUT)   # item 10: downloadable CSVs + View-A SVG
    # infra
    if SITE["build"].get("emit_cname"):   # only at DNS-flip time; otherwise github.io stays previewable
        (OUT / "CNAME").write_text(SITE["brand"]["domain"] + "\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    urls = ["/", "/monitor/", "/monitor/methods/", "/daioe/", "/research/", "/people/", "/events/", "/news/", "/about/"]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append(f"<url><loc>{BASE}{u}</loc><changefreq>monthly</changefreq></url>")
    sm.append("</urlset>")
    (OUT / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")
    # The one-pager is regenerated HERE, at the end of the build, because build() starts by
    # deleting OUT: a PDF written before it is silently wiped, which is exactly what happened
    # the first time. Generating it inside the build also means its "sheet generated" date is
    # always the date the site was last built, which is what the download promises. A failure
    # is reported but does not take the site down: a missing PDF is a broken link, a failed
    # build is no site at all.
    try:
        import subprocess
        for args in ([], ["--sv"]):
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_onepager.py")] + args,
                               capture_output=True, text=True)
            if r.returncode == 0:
                print("  " + (r.stdout.strip() or "built"))
                continue
            # build_onepager writes tectonic's OWN diagnostics to stderr, trimmed to the last
            # 3500 characters, and then raises SystemExit("tectonic failed"). Printing only
            # `stderr.splitlines()[-1]` therefore kept the two words and threw away the part
            # that says why. On 24 Aug 2026 the nightly refresh failed here on a runner where
            # `tectonic --version` had just printed 0.17.0 one step earlier, so the engine was
            # plainly present -- and the log held nothing but "tectonic failed", twice. The
            # cause could not be diagnosed from the run at all, only guessed at, which is the
            # opposite of what the line beneath it promises when it says "the message above
            # says why". Print the whole thing; a build log is not the place to be terse.
            print(f"  one-pager ({args[0] if args else '--en'}) FAILED, exit {r.returncode}:")
            for line in ((r.stderr.strip() or r.stdout.strip() or "(no output)").splitlines()):
                print(f"    | {line}")
    except Exception as e:                                    # noqa: BLE001
        print(f"  one-pager NOT built: {e}")
    # Whatever the generator managed, no sheet that existed before this build may be missing
    # after it. A stale sheet is a dated download; a deleted one is a 404 on the front page.
    for name, blob in carried.items():
        if not (OUT / name).exists():
            (OUT / name).write_bytes(blob)
            print(f"  {name}: NOT REGENERATED — kept the previous sheet. The message above "
                  f"says why; it is not necessarily a missing TeX engine, which is what this "
                  f"line used to assert without checking.")

    print(f"Built {len(PAGES)} pages + sitemap/robots/CNAME into {OUT}/")
    print(f"  papers: {paper_count()} · people: {sum(len(g['members']) for g in PEOPLE['groups'])}")

if __name__ == "__main__":
    build()
