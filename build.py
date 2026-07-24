#!/usr/bin/env python3
"""
AI-Econ Lab — static site builder.

Reads data/*.yaml, renders self-contained HTML into docs/ (what GitHub Pages
serves), and writes sitemap.xml, robots.txt, CNAME and .nojekyll. No template
engine and no third-party deps beyond PyYAML — so it runs the same on your Mac
and in CI. Edit the YAML, run `python3 build.py`, commit, push.
"""
from pathlib import Path
import shutil, yaml, html, re, unicodedata, hashlib, datetime

ROOT = Path(__file__).parent
DATA = ROOT / "data"
def load(name): return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))

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
    "cross_country_demand.yaml", "swe_adoption.yaml", "daioe_exposure.yaml",
    "entry_level_squeeze.yaml", "working_conditions.yaml", "akavia.yaml",
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

SITE     = load("site.yaml")
PAPERS   = load("papers.yaml")
PEOPLE   = load("people.yaml")
MONITOR  = load("monitor.yaml")
DAIOE    = load("daioe.yaml")
SEMINARS = load("seminars.yaml")
DAIOE_EXP = load("daioe_exposure.yaml")
NEWS     = load("news.yaml")
CROSS    = load("cross_country.yaml")
ADOPT    = load("cross_country_adoption.yaml")
DEMAND   = load("cross_country_demand.yaml")
WORKCOND = load("working_conditions.yaml")
AKAVIA   = load("akavia.yaml")
RELATED  = load("related_research.yaml")
ELS      = load("entry_level_squeeze.yaml")
SWEAD    = load("swe_adoption.yaml")
# The occupation-search data lives in assets/daioe_occupations.json and is fetched at runtime
# (see app.js occSearch), so it is NOT embedded here. It auto-tracks the latest DAIOE year.

OUT = ROOT / SITE["build"]["out"]
BASE = SITE["brand"]["base_url"].rstrip("/")
h = lambda s: html.escape(str(s), quote=True)   # escape plain-text (titles, names)

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
def masthead(active):
    b = SITE["brand"]
    items = ""
    for n in SITE["nav"]:
        cur = ' aria-current="page"' if (not n.get("cta") and n["href"] == active) else ""
        cls = ' class="cta"' if n.get("cta") else ""
        items += f'<a href="{n["href"]}"{cls}{cur}>{h(n["label"]).replace("&gt;",">")}</a>'
    # Plain substitution, not str.format: the strip is hand-authored HTML and a
    # stray brace in a future entry must not raise.
    reg = "".join(f'<span>{s.replace("{data_updated}", DATA_UPDATED)}</span>'
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
        t = MONITOR["trend"]
        trend_js = (f'<script>window.AIEL_TREND={{years:{t["years"]},values:{t["values"]},'
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
        "isAccessibleForFree":True,"temporalCoverage":"2006/2025",
        "spatialCoverage":"Sweden","url":BASE+"/monitor/"}, ensure_ascii=False)

def daioe_ld():
    return json.dumps({"@context":"https://schema.org","@type":"Dataset","name":"DAIOE — data-driven AI Occupational Exposure",
        "description":DAIOE["lede"],"license":"https://creativecommons.org/licenses/by/4.0/",
        "creator":{"@type":"Organization","name":SITE["brand"]["name"]},"isAccessibleForFree":True,
        "distribution":{"@type":"DataDownload","contentUrl":DAIOE["resources"][0]["href"]},
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
                  f'<div class="num">{t["num"]}</div><div class="lab">{h(t["lab"])}</div>'
                  f'<div class="foot">{h(t["foot"])}</div></div>')
    body = f"""<div class="wrap"><div class="hero"><div class="herogrid">
  <div>
    <div class="eyebrow"><span class="dot"></span> A multi-country, multi-disciplinary research lab</div>
    <h1 class="title">We study how <em>artificial intelligence</em> is reshaping the world of work.</h1>
    <p class="lede">An economics-led, multi-disciplinary research lab at Örebro University and RATIO,
      contributing to the <a href="https://wasp-hs.org">WASP-HS</a> research cluster
      <a href="https://www.aiscaf.se/w/ac/">AISCAF</a>. We combine administrative registers from
      several European countries with job advertisements, surveys and public cross-country data.
      The <b>AIEL Monitor</b> is where
      part of that work becomes public: open indicators on AI and work across countries, with Sweden
      in uncommon depth, updated as the data arrive.</p>
    <div class="cta-row"><a class="btn primary" href="/monitor/">Open the Monitor →</a>
      <a class="btn ghost" href="/monitor/#method">How we measure it</a></div>
    <div class="affil">{affils}</div>
  </div>
  <div class="panel">
    <div class="panelhead"><span class="ttl">AI in Demand · share of Swedish job ads</span>
      <span class="livechip"><i></i>live</span></div>
    <div class="panelbody">
      <p class="psub">Vacancies requesting any AI skill, 2006–2025. About <b>140×</b> higher than twenty years
        ago, and steepest after 2023. Internationally (AI Index / Lightcast, 2025): a median <b>1.9%</b> of
        postings across 22 countries require AI skills, Sweden <b>2.8%</b> on that measure.</p>
      <svg id="trend" viewBox="0 0 640 300" role="img" aria-label="Line chart: AI-in-demand share of Swedish job ads, 2006 to 2025"></svg>
      <div class="legend"><span><i style="background:var(--c1)"></i>Broad · any AI-related term</span>
        <span class="mono" style="color:var(--muted);font-size:11px">╌ 2025 provisional</span></div>
      {figfooter("ai_in_demand_trend.csv", "JobTech / Platsbanken job ads (CC0), 2006–2025 · lexical AI-term list (not DAIOE)", svg_name="ai_in_demand_trend.svg", method_href="/monitor/#method")}
    </div>
  </div>
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
        Rare reach, paired with 10.9M public job ads.</p></div>
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
  <p class="secintro">Type an occupation to see its DAIOE exposure and where it sits among roughly 420 occupations.
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
      <svg id="beeswarm" viewBox="0 0 760 340" role="img" aria-label="Beeswarm of about 420 occupations by generative-AI exposure"></svg>
      <div class="beeaxis"><span>← less exposed</span><span>more exposed →</span></div>
    </div>
    <div class="scrolly-steps">
      <div class="step" data-hl="all"><p>Roughly 420 occupations, each a dot, placed left to right by how exposed they are to generative AI. Hover any dot to name it.</p></div>
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
  <p class="secintro">DAIOE's generative-AI exposure across roughly 420 occupations. Writers, marketers, programmers
    and, yes, economists sit at the very top; hands-on manual, craft and outdoor work sits at the bottom.</p>
  <div class="expgrid">
    <div><div class="exphead"><span class="dotc hi"></span>Most exposed to generative AI</div>
      <div class="expbars">{most}</div></div>
    <div><div class="exphead"><span class="dotc lo"></span>Least exposed</div>
      <div class="expbars">{least}</div></div>
  </div>
  {figfooter("daioe_most_least.csv", f"DAIOE generative-AI v{DAIOE_EXP['year']} · ISCO-08")}
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
    online brown-bag seminar series, part of <a href="https://www.aiscaf.se/w/ac/">AISCAF</a>.</p></div></div>

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
    return shell(f"Events · {SITE['brand']['name']}",
                 "The AIEL conference on AI and white-collar work, and the monthly brown-bag seminar series (part of AISCAF).",
                 "/events/", body)

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
    The current year is shown; select any earlier year to expand it.</p></div></div>
<div class="wrap"><section style="padding-top:8px">{blocks}</section></div>"""
    return shell(f"News · {SITE['brand']['name']}",
                 "News and history of the AI-Econ Lab since 2019: publications, media, grants and events.",
                 "/news/", body)

def figfooter(csv_name, source, svg_name=None, method_href=None):
    """Item 10: download + provenance under a figure. Source states DAIOE variant + year.
    Offers the data (CSV) plus, when the figure has a static SVG, the chart as SVG and PNG
    (PNG is rasterised client-side from the SVG, so no build dependency). method_href, when
    given, appends a link to the fuller method/sources note."""
    dl = f'<a class="figdl" href="/assets/data/{csv_name}" download>↓ Data (CSV)</a>'
    if svg_name:
        dl += (f'<a class="figdl" href="/assets/data/{svg_name}" download>↓ SVG</a>'
               f'<button class="figdl figpng" type="button" data-svg="/assets/data/{svg_name}">↓ PNG</button>')
    meth = f'<a class="figml" href="{h(method_href)}">Method &amp; sources →</a>' if method_href else ""
    return f'<div class="figfoot">{dl}<span class="figsrc">Source: {h(source)}</span>{meth}</div>'

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
    p.append(f'<text class="meanlab" x="{mx:.1f}" y="{top-4}" text-anchor="middle">EU mean</text>')
    for i, r in enumerate(rows):
        y = top + i * rowh + rowh * 0.62
        se = " se" if r["is_se"] else ""
        vx = X(r["exposure"])
        nm = h(r["name"]) + (f" ’{str(r['year'])[-2:]}" if hy and int(r.get("year", hy)) != hy else "")
        p.append(f'<line class="rowguide" x1="{x0}" y1="{y-3:.1f}" x2="{x1}" y2="{y-3:.1f}"/>')
        p.append(f'<text class="dname{se}" x="128" y="{y:.1f}" text-anchor="end">{nm}</text>')
        p.append(f'<circle class="dot{se}" cx="{vx:.1f}" cy="{y-3:.1f}" r="{4.4 if r["is_se"] else 3.1}"/>')
        p.append(f'<text class="dval{se}" x="600" y="{y:.1f}" text-anchor="end">{r["exposure"]:.2f}</text>')
    p.append("</svg>")
    return "".join(p)

def barplot(data, eu_avg, xmax, hy=0, vkey="adoption", vfmt=".0f"):
    """Ranked horizontal bar chart (share; meaningful zero). Bar = latest year; a muted delta
    shows the year-on-year change from the previous wave (when present). Sweden highlighted."""
    rows = data; n = len(rows); hy = int(hy)
    W, rowh, top, bot = 640, 15, 18, 34
    H = top + n * rowh + bot
    x0, x1 = 140, 528
    X = lambda v: x0 + v / xmax * (x1 - x0)
    step = 10 if xmax > 25 else 5 if xmax > 12 else 1
    p = [f'<svg class="rankchart barplot" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Ranked bar chart of firms using AI by country, {n} countries, Sweden highlighted">']
    for t in range(0, int(xmax) + 1, step):
        gx = X(t)
        p.append(f'<line class="grid" x1="{gx:.1f}" y1="{top}" x2="{gx:.1f}" y2="{top+n*rowh}"/>')
        p.append(f'<text class="tick" x="{gx:.1f}" y="{H-13}" text-anchor="middle">{t}%</text>')
    if eu_avg:
        mx = X(eu_avg)
        p.append(f'<line class="meanline" x1="{mx:.1f}" y1="{top-1}" x2="{mx:.1f}" y2="{top+n*rowh}"/>')
        p.append(f'<text class="meanlab" x="{mx:.1f}" y="{top-5}" text-anchor="middle">EU {eu_avg:g}</text>')
    for i, r in enumerate(rows):
        y = top + i * rowh; se = " se" if r["is_se"] else ""
        v = r[vkey]
        nm = h(r["name"]) + (f" ’{str(r['year'])[-2:]}" if hy and int(r.get("year", hy)) != hy else "")
        p.append(f'<text class="dname{se}" x="128" y="{y+rowh*0.72:.1f}" text-anchor="end">{nm}</text>')
        p.append(f'<rect class="bar{se}" x="{x0}" y="{y+rowh*0.26:.1f}" width="{max(1.5,X(v)-x0):.1f}" height="{rowh*0.5:.1f}" rx="2"/>')
        p.append(f'<text class="dval{se}" x="574" y="{y+rowh*0.72:.1f}" text-anchor="end">{v:{vfmt}}</text>')
        if r.get("prev") is not None:
            p.append(f'<text class="ddelta" x="632" y="{y+rowh*0.72:.1f}" text-anchor="end">{v-r["prev"]:+.0f}</text>')
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
    ({h(mt['daioe_version'])}); descriptive, not causal.</p>
  <div class="lensmod">
    <div class="lensbar2"><span class="ll">Gender</span>
      <button class="gbtn on" data-g="all">All</button><button class="gbtn" data-g="women">Women</button><button class="gbtn" data-g="men">Men</button></div>
    <div class="dotwrap">{views}</div>
    <div class="dblegend"><span><i class="lo"></i>least-exposed occupations</span><span><i class="hi"></i>most-exposed occupations</span></div>
  </div>
  {figfooter("working_conditions.csv", f"{mt['wc_source']} × DAIOE {mt['daioe_variant']} {mt['daioe_version']}", svg_name="working_conditions.svg")}
  <p class="prov" style="margin-top:10px">Toggle gender: the control gap is the story. In low-exposure jobs women
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
  <p class="kicker">Module 1 · Exposure · across countries</p>
  <h2 class="sec">How much of each country's work is AI-exposed?</h2>
  <p class="secintro">DAIOE scores every occupation (ISCO-08) for how far generative AI overlaps with its tasks.
    We label the <b>top 25% of occupations</b> by that score the <b>most AI-exposed</b>; the bars show the share of
    each country's jobs in them (Eurostat EU-LFS employment, <b>{h(mt['weight_year'])}</b>; a few countries use their
    latest year, marked ’YY). So <b>{se['share']:.0f}%</b> means about four in ten Swedish jobs sit in the most
    AI-exposed quarter of occupations. <b>Exposure is not displacement</b>: in our panel it predicts occupational
    growth as often as decline, showing only where AI overlaps with the work.</p>
  <div class="dotwrap">{barplot(cc['countries'], mt['mean_share'], xmax, mt['weight_year'], 'share', '.0f')}</div>
  {figfooter("cross_country.csv", src, "cross_country.svg")}
  <div class="depth"><p class="dk">Sweden, in depth</p>
    <p class="secintro" style="margin:0"><b>{se['share']:.0f}%</b> of Swedish jobs are in the most AI-exposed
      occupations (the <b>top 25%</b> by generative-AI exposure), the <b>2nd-highest of {h(mt['n_countries'])}</b>
      countries (EU average {mt['mean_share']:.0f}%).
      The occupation-by-occupation detail lives on the <a href="/daioe/">DAIOE</a> page, and Swedish employment is
      set against exposure over time in the <a href="#occupations-explorer">Occupations Explorer</a> below.</p></div>
  {related_research("exposure")}
</section></div></div>"""

def demand_section(tiles, seg):
    """Module 2 — Demand. Headline is the cross-country demand bar; Sweden's live measure is the depth cut."""
    dm = DEMAND; dmt = dm["meta"]
    dxmax = int(max(r["share"] for r in dm["countries"])) + 1  # demand share, tight axis
    return f"""<div class="rule module-sec" id="demand"><div class="wrap"><section>
  <p class="kicker">Module 2 · Demand · across countries</p>
  <h2 class="sec">How much are employers hiring for AI?</h2>
  <p class="secintro">The share of job postings that require AI skills, by country in <b>{h(dmt['year'])}</b>
    ({h(dmt['source'])}), Sweden marked. {h(dmt['note_prev'])} This international series (Lightcast) is a separate
    source from the lab's own Swedish measure below, so their levels are not directly comparable.</p>
  <div class="dotwrap">{barplot(dm['countries'], 0, dxmax, 0, 'share', '.1f')}</div>
  {figfooter("cross_country_demand.csv", f"{dmt['source']}, {dmt['year']} · {dmt['unit']}", "cross_country_demand.svg")}

  <div class="depth" id="ai-in-demand"><p class="dk">Sweden, in depth · our live measure</p>
    <p class="secintro" style="margin:0 0 4px">{h(MONITOR['aiindemand_lede'])} We read every open and historical
      Swedish job ad (JobTech / Platsbanken, 2006–2025, about <b>10.9 million</b>) with a versioned, citable term
      list, so the level and its 140-fold rise since 2006 are reproducible.</p>
    <div class="tiles">{tiles}</div>
    {figfooter("ai_in_demand_trend.csv", "JobTech / Platsbanken job ads (CC0), 2006–2025 · lexical layer (not DAIOE)", svg_name="ai_in_demand_trend.svg")}
    <div class="grouphdr" style="margin-top:26px">Coming next · who is the AI for?
      <span class="preview-flag">◔ {h(MONITOR['segmentation']['flag'])}</span></div>
    <p class="secintro" style="margin-top:4px">{h(MONITOR['segmentation']['intro'])}</p>
    <div class="two" style="grid-template-columns:1fr 1fr 1fr">{seg}</div>
  </div>
  {related_research("demand")}
</section></div></div>"""

def adoption_section():
    """Module 3 — Adoption. Cross-country firm AI-adoption (Eurostat), Sweden by firm size as depth cut."""
    ad = ADOPT; amt = ad["meta"]
    se = next(r for r in ad["countries"] if r["is_se"])
    swm = SWEAD["meta"]; sm = {r["code"]: r["adoption"] for r in SWEAD["sizes"]}
    swxmax = 10 * (max(r["adoption"] for r in SWEAD["sizes"]) // 10 + 1)    # round up to 10
    xmax = 5 * (int(max(r["adoption"] for r in ad["countries"]) // 5) + 1)  # round up to 5
    return f"""<div class="rule module-sec" id="adoption"><div class="wrap"><section>
  <p class="kicker">Module 3 · Adoption · across countries</p>
  <h2 class="sec">How widely have firms actually adopted AI?</h2>
  <p class="secintro">Exposure is potential; adoption is what firms have done. The share of enterprises using at
    least one AI technology (<b>{h(amt['year'])}</b>, {h(amt['source'])}), with the year-on-year change since
    {h(amt['prev_year'])} shown as <b>+pp</b>. Adoption is climbing fast: the EU average rose from 8% in 2023 to
    {h(amt['eu_avg'])}% in {h(amt['year'])}. Exposure and adoption need not line up across countries.</p>
  <div class="dotwrap">{barplot(ad['countries'], amt['eu_avg'], xmax, amt['year'])}</div>
  {figfooter("cross_country_adoption.csv", f"{amt['source']}, {amt['year']} (change vs {amt['prev_year']}) · {amt['unit']}", "cross_country_adoption.svg")}
  <div class="depth"><p class="dk">Sweden, in depth · by firm size</p>
    <p class="secintro" style="margin:0 0 14px">Sweden is among the EU leaders at <b>{se['adoption']:g}%</b> in
      {h(amt['year'])}, up from {se['prev']:g}% a year earlier (Eurostat). SCB's firm survey decomposes that headline
      by size: adoption climbs steeply with the size of the firm, from <b>{sm['10-49']}%</b> of small firms
      (10–49 employees) to <b>{sm['250-']}%</b> of large ones (250+), every class up sharply since {h(swm['prev_year'])}.
      The all-firms figure ({sm['Tot250']}%, highlighted) is the same number the cross-country bar shows.</p>
    <div class="dotwrap">{barplot(SWEAD['sizes'], amt['eu_avg'], swxmax, 0, 'adoption', '.0f')}</div>
    {figfooter("swe_adoption.csv", f"{swm['source']}, {swm['year']} (change vs {swm['prev_year']}) · {swm['unit']}; EU average {amt['eu_avg']:g}% (Eurostat)", svg_name="swe_adoption.svg")}
  </div>
  {akavia_workers_block()}
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


def akavia_workers_block():
    """Adoption depth, worker side. Firm surveys count employers; this counts people."""
    a = AKAVIA; m = a["meta"]; tr = a["trend"]
    prof = a["by_profession"]; sec = a["by_sector"]
    xmax = 10 * (max(r["adoption"] for r in prof) // 10 + 1)
    first, last = tr["values"][0], tr["values"][-1]
    return f"""<div class="depth"><p class="dk">Sweden, in depth · by worker</p>
    <p class="secintro" style="margin:0 0 14px">Firm surveys count employers who have started. This counts
      people: the share of professionals who use AI in their own work rose from <b>{first}%</b> in
      {h(tr['labels'][0])} to <b>{last}%</b> in {h(tr['labels'][-1])}, and daily use went from 3% to 22% over
      the same period, so the shift is in intensity as much as reach. Nearly everyone now works somewhere AI
      is used at all ({a['org_use']['y2024']}% in 2024, {a['org_use']['y2025']}% in {h(m['year'])}). The spread
      by profession is wide and narrowing: communicators are near saturation while lawyers remain furthest
      behind, and central government trails the private sector by
      {sec[0]['adoption'] - sec[-1]['adoption']}pp. Men {a['by_sex']['men']}%, women {a['by_sex']['women']}%.</p>
    <div class="dotwrap">{barplot(prof, 0, xmax, 0, 'adoption', '.0f')}</div>
    {figfooter("akavia_ai_use.csv", f"{m['source']}, {m['first_year']}–{m['year']}; own processing. Bars {m['year']}, change vs {m['first_year']}. {m['population']}", svg_name="akavia_ai_use.svg")}
    <p class="prov" style="margin-top:10px">Data shared with the lab by
      <a href="{m['url']}">Akavia</a>. {h(m['caveat'])}</p>
  </div>"""

def akavia_outcomes_block():
    """Outcomes: governance trailing use, the training gap, and who pays for the tools."""
    a = AKAVIA; m = a["meta"]; g = a["governance"]; tg = a["training"]; sh = a["shadow"]
    used = a["used_for"]
    gap = g["use"][-1] - g["policy"][-1]
    rows = "".join(
        f"<tr><td>{h(l)}</td><td>{u}%</td><td>{p}%</td><td>{s}%</td></tr>"
        for l, u, p, s in zip(g["labels"], g["use"], g["policy"], g["strategy"]))
    uf = "".join(f"<li><b>{r['value']}%</b> {h(r['label'].lower())}</li>" for r in used)
    return f"""<div class="grouphdr" id="akavia-governance" style="margin-top:36px">Use, governance and who pays</div>
  <p class="secintro" style="margin-top:4px">Among Swedish professional-union members, workplace governance runs
    well behind actual use. In {h(m['year'])}, {g['use'][-1]}% used AI at work while only {g['policy'][-1]}% knew
    of a policy and {g['strategy'][-1]}% of a strategy, a gap of <b>{gap}pp</b>. The figures say <i>knows of</i>
    rather than <i>has</i>: about a fifth answer that they do not know, which is counted here as not knowing of
    one. Training runs the same way: {tg['wants_last']}% want to develop their AI skills, {tg['offered_last']}%
    have been offered it by an employer, against {tg['wants_first']}% and {tg['offered_first']}% in
    {h(m['first_year'])}.</p>
  <table class="minitab"><thead><tr><th>Wave</th><th>Uses AI</th><th>Knows of a policy</th><th>Knows of a strategy</th></tr></thead><tbody>{rows}</tbody></table>
  <p class="secintro" style="margin-top:14px">What the work actually is, among users in {h(m['year'])}:</p>
  <ul class="tight">{uf}</ul>
  <p class="secintro" style="margin-top:14px">And who provides the tools. Among those using <b>standalone</b> AI
    tools, not among all workers, <b>{sh['private_account']}%</b> have a private e-mail account connected to a
    work AI tool, the employer pays for {sh['employer_pays']}% and {sh['self_pays']}% pay themselves. The
    denominator matters here and is easy to overstate.</p>
  {figfooter("akavia_governance.csv", f"{m['source']}, {m['first_year']}–{m['year']}; own processing. {m['population']}")}
  <p class="prov" style="margin-top:10px">Data shared with the lab by
    <a href="{m['url']}">Akavia</a>. {h(m['caveat'])}</p>"""

def outcomes_section(explorers):
    """Module 4 — Outcomes. Occupations Explorer + working conditions + entry-level squeeze (all live)."""
    em = ELS["meta"]
    return f"""<div class="rule module-sec" id="outcomes"><div class="wrap"><section>
  <p class="kicker">Module 4 · Outcomes</p>
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
  <p class="secintro" style="margin-top:4px">In the most AI-exposed occupations, a smaller share of openings ask for
    no prior experience than in the least-exposed occupations, every year since {h(em['first_year'])}, and the gap has
    widened from −{abs(em['gap_first'])}pp to <b>−{abs(em['gap_last'])}pp in {h(em['last_year'])}</b>. An independent,
    ad-based echo of the Canaries finding; descriptive, not causal (less-exposed work skews lower-skill, so part of the
    level gap is structural, the widening is the signal). The same entry-level pattern appears in the international AI
    "canaries" literature on young workers, though no directly comparable cross-country series exists yet.</p>
  <div class="dotwrap">{squeeze_svg(ELS)}</div>
  <div class="dblegend"><span><i class="lo"></i>least-exposed occupations</span><span><i class="hi"></i>most-exposed occupations</span></div>
  {figfooter("entry_level_squeeze.csv", f"{em['source']} × DAIOE {em['daioe_variant']} {em['daioe_version']}", svg_name="entry_level_squeeze.svg")}
  {related_research("outcomes")}
</section></div></div>"""

def stat_overview():
    """Overview-first landing: one door per spine module. Whole picture in ~20s; detail one click down."""
    cards = ""
    for o in MONITOR["overview"]:
        cls = f' {o["cls"]}' if o["cls"] else ""
        cards += (f'<a class="ovcard{cls}" href="{o["anchor"]}"><div class="stripe"></div>'
                  f'<div class="ok">{h(o["k"])}</div><div class="onum">{o["num"]}</div>'
                  f'<div class="olab">{h(o["lab"])}</div>'
                  f'<div class="ofoot"><span>{h(o["foot"])}</span><span class="go">Open →</span></div></a>')
    return f"""<div class="rule" id="overview"><div class="wrap"><section>
  <p class="kicker">The whole picture, in one glance</p>
  <h2 class="sec">Four questions about AI and work.</h2>
  <p class="secintro">Exposure, demand, adoption and outcomes: one European headline each, with Sweden as the depth
    cut inside every module. Every figure is public and dated; open a card to jump to the module.</p>
  <div class="ovgrid">{cards}</div>
</section></div></div>"""

def subnav():
    """Sticky spine nav under the masthead; scrollspy in app.js marks the active module."""
    items = [("#exposure", "Exposure"), ("#demand", "Demand"),
             ("#adoption", "Adoption"), ("#outcomes", "Outcomes")]
    links = "".join(f'<a href="{a}" data-spy="{a[1:]}">{t}</a>' for a, t in items)
    return f'<nav class="subnav" aria-label="Monitor modules"><div class="wrap">{links}</div></nav>'

def monitor():
    m = MONITOR
    tiles = ""
    for t in m["tiles"]:
        cls = f' {t["cls"]}' if t["cls"] else ""
        tiles += (f'<div class="tile{cls}"><div class="stripe"></div><div class="num">{t["num"]}</div>'
                  f'<div class="lab">{h(t["lab"])}</div><div class="foot">{h(t["foot"])}</div></div>')
    seg = ""
    for c in m["segmentation"]["cards"]:
        seg += (f'<div class="prod"><h3><span style="display:inline-block;width:11px;height:11px;border-radius:3px;'
                f'background:var({c["color"]});margin-right:8px"></span>{h(c["name"])}</h3><p>{h(c["text"])}</p></div>')
    caveats = "".join(f"<li>{c}</li>" for c in m["caveats"])
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
  <div><div class="eyebrow"><span class="dot"></span> Public monitor · international first, Sweden in depth · updated as the data arrive</div>
    <h1 class="title">{h(m['headline'])}</h1>
    <p class="lede">{h(m['lede'])}</p>
    <div class="cta-row"><a class="btn primary" href="#exposure">See it across countries →</a>
      <a class="btn ghost" href="/monitor/brief/">Monthly brief (PDF) →</a>
      <a class="btn ghost" href="#method">How we measure it</a></div></div>
  <div class="panel"><div class="panelhead"><span class="ttl">AI in Demand · share of Swedish job ads</span>
    <span class="livechip"><i></i>live</span></div>
    <div class="panelbody"><p class="psub">Vacancies requesting any AI skill, 2006–2025. About <b>140×</b> higher than twenty years
        ago, and steepest after 2023. Internationally (AI Index / Lightcast, 2025): a median <b>1.9%</b> of
        postings across 22 countries require AI skills, Sweden <b>2.8%</b> on that measure.</p>
      <svg id="trend" viewBox="0 0 640 300" role="img" aria-label="AI-in-demand share of Swedish job ads, 2006 to 2025"></svg>
      <div class="legend"><span><i style="background:var(--c1)"></i>Broad · any AI-related term</span>
        <span class="mono" style="color:var(--muted);font-size:11px">╌ 2025 provisional</span></div>
      {figfooter("ai_in_demand_trend.csv", "JobTech / Platsbanken job ads (CC0), 2006–2025 · lexical AI-term list (not DAIOE)", svg_name="ai_in_demand_trend.svg", method_href="#method")}</div></div>
</div></div></div>

{stat_overview()}

{subnav()}

{exposure_section()}

{demand_section(tiles, seg)}

{adoption_section()}

{outcomes_section(explorers)}

<div class="rule" id="method"><div class="wrap"><section>
  <p class="kicker">How to read this</p>
  <h2 class="sec">What we measure, and what we don't yet.</h2>
  <div class="prose" style="margin-top:16px">
    <p>The measure runs on public data with one named exception. The Swedish demand series reads every open and historical
      advertisement in Sweden's public job board (Platsbanken / JobTech), 2006–2025: about <b>10.9 million ads</b>.
      An ad counts as AI-in-demand when its text requests an AI skill, matched by a versioned, citable term list
      (Swedish and English); a semantic layer, now training, will catch AI ads that use no listed term. Exposure,
      adoption and cross-country demand come from DAIOE (generative-AI, v2023), Eurostat and the Stanford AI Index.</p>
    <p>The exception is the worker-side layer, which comes from
      <a href="https://www.akavia.se/politik-paverkan/sakomraden/ai-digitalisering/">Akavia</a>, a Swedish
      professional union that surveys its members through a web panel and shares the de-identified results with
      the lab. We publish aggregated figures with attribution and keep the underlying records private; cells
      below 50 respondents are never shown. Akavia does not fund the lab and does not see results before
      publication. The processing, and any error in it, is ours.</p>
    <h3>Caveats, in plain sight</h3><ul style="color:var(--ink-2);font-size:14px;line-height:1.6">{caveats}</ul>
    <h3>How to cite</h3>
    <p>The monitor is a citable public good. Please cite the specific version and date, and the underlying source
      shown in each figure's footer (for example DAIOE generative-AI v2023, or Eurostat 2025).</p>
    <p class="citebox">AI-Econ Lab (2026). AIEL Monitor: [module]. Örebro University and Ratio. [source and version
      from the figure footer]. Accessed [date], https://ai-econ-lab.github.io/monitor/</p>
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
    return shell(f"About &amp; contact · {SITE['brand']['name']}", SITE["brand"]["description"], "/about/", body)

def brief(lang="en"):
    """Monthly one-page 'AIEL Monitor Brief' (English + Swedish): an auto-generated snapshot (the
    four spine headline numbers), the always-fresh vacancy pulse, a themed deep-dive that rotates
    through the spine month by month, and the latest lab news. Same data as the site; print-to-PDF
    ready. The news items are shown in their original (English) wording in both editions."""
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

    t = MONITOR["trend"]                                  # the pulse: the always-fresh vacancy series
    cc = CROSS; dm = DEMAND; smd = {r["code"]: r["adoption"] for r in SWEAD["sizes"]}
    n_ctry = cc["meta"]["n_countries"]; dver = cc["meta"]["daioe_version"]
    se_share = next(r["share"] for r in cc["countries"] if r["is_se"]); eu_share = cc["meta"]["mean_share"]
    CAL = load("brief_calendar.yaml")["months"]            # confirmed 12-month theme calendar
    cm = CAL.get(today.month, {"theme": "exposure", "title_en": "AI exposure across Europe",
                               "title_sv": "AI-exponering i Europa"})
    theme = cm["theme"]                                    # which built chart+takeaway to show
    titles = {theme: (cm["title_sv"] if sv else cm["title_en"])}   # displayed monthly theme
    takeaways = {
        "exposure": L(
            f"{se_share:.0f}% of Swedish jobs are in the most AI-exposed occupations (the top 25% of occupations by "
            f"DAIOE generative-AI exposure), 2nd-highest of {n_ctry} countries; the EU average is {eu_share:.0f}%. "
            f"Exposure marks where AI overlaps with the work, not displacement.",
            f"{se_share:.0f}% av de svenska jobben finns i de mest AI-exponerade yrkena (den mest exponerade "
            f"fjärdedelen, topp 25% efter DAIOE generativ AI-exponering), näst högst av {n_ctry} länder; EU-snittet är "
            f"{eu_share:.0f}%. Exponering visar var AI överlappar med arbetet, inte förträngning."),
        "demand": L(
            "Demand roughly doubled in a year for most countries (Sweden 1.3% in 2024 to 2.8% in 2025). The Swedish "
            "live job-ad measure is the pulse shown above.",
            "Efterfrågan ungefär fördubblades på ett år i de flesta länder (Sverige 1,3% 2024 till 2,8% 2025). Den "
            "svenska livemätningen av jobbannonser är pulsen ovan."),
        "adoption": L(
            f"Adoption climbs steeply with firm size, from {smd['10-49']}% of small firms (10–49 employees) to "
            f"{smd['250-']}% of large ones (250+) in {SWEAD['meta']['year']}, every class up sharply since {SWEAD['meta']['prev_year']}.",
            f"Användningen ökar brant med företagsstorlek, från {smd['10-49']}% av småföretagen (10–49 anställda) till "
            f"{smd['250-']}% av de stora (250+) {SWEAD['meta']['year']}, alla storleksklasser kraftigt upp sedan {SWEAD['meta']['prev_year']}."),
        "outcomes": L(
            f"In the most AI-exposed occupations, entry-level openings are a smaller share of vacancies than in the "
            f"least-exposed, a gap widening from −{abs(ELS['meta']['gap_first'])}pp to −{abs(ELS['meta']['gap_last'])}pp "
            f"in {ELS['meta']['last_year']}. Descriptive, not causal.",
            f"I de mest AI-exponerade yrkena utgör instegsjobb en mindre andel av annonserna än i de minst exponerade, "
            f"ett gap som vuxit från −{svn(abs(ELS['meta']['gap_first']))} till −{svn(abs(ELS['meta']['gap_last']))} "
            f"procentenheter {ELS['meta']['last_year']}. Beskrivande, inte kausalt."),
    }
    srcs = {
        "exposure": L(f"DAIOE generative-AI {dver} × Eurostat EU-LFS {cc['meta']['weight_year']}",
                      f"DAIOE generativ AI {dver} × Eurostat AKU {cc['meta']['weight_year']}"),
        "demand": f"{dm['meta']['source']}, {dm['meta']['year']}",
        "adoption": L(f"{SWEAD['meta']['source']}, {SWEAD['meta']['year']}",
                      f"SCB, IT-användning i företag (NV0116), {SWEAD['meta']['year']}"),
        "outcomes": L(f"{ELS['meta']['source']} × DAIOE {ELS['meta']['daioe_variant']} {ELS['meta']['daioe_version']}",
                      f"{ELS['meta']['source']} × DAIOE generativ AI {ELS['meta']['daioe_version']}"),
    }
    if theme == "exposure":
        th_chart = barplot(cc["countries"], eu_share, 10 * (int(max(r["share"] for r in cc["countries"]) // 10) + 1),
                           cc["meta"]["weight_year"], "share", ".0f")
    elif theme == "demand":
        th_chart = barplot(dm["countries"], 0, int(max(r["share"] for r in dm["countries"])) + 1, 0, "share", ".1f")
    elif theme == "adoption":
        th_chart = barplot(SWEAD["sizes"], ADOPT["meta"]["eu_avg"], 10 * (max(r["adoption"] for r in SWEAD["sizes"]) // 10 + 1), 0, "adoption", ".0f")
    else:
        th_chart = squeeze_svg(ELS)
    th_title = titles[theme]

    KSV = {"Exposure": "Exponering", "Demand": "Efterfrågan", "Adoption": "Användning", "Outcomes": "Utfall"}
    LABSV = {"Exposure": "av de europeiska jobben finns i den mest AI-exponerade fjärdedelen av yrkena (topp 25% efter generativ AI-exponering); Sverige 39%, näst högst av 36",
             "Demand": "medianandel jobbannonser som kräver AI i 22 länder 2025 (Stanford AI Index); Sverige 2,8%",
             "Adoption": "av EU:s företag använde AI 2025, upp från 8% 2023 (Eurostat); Sverige 35%, bland de ledande",
             "Outcomes": "Sveriges instegsklämma: färre instegsjobb i de mest AI-exponerade yrkena sedan 2020; mönstret syns även internationellt"}
    cards = ""                                            # at a glance: the four spine numbers
    for o in MONITOR["overview"]:
        cls = f' {o["cls"]}' if o["cls"] else ""
        k = KSV[o["k"]] if sv else o["k"]
        lab = LABSV[o["k"]] if sv else o["lab"]
        foot = o["foot"].replace("live", "löpande") if sv else o["foot"]
        cards += (f'<div class="bstat{cls}"><span class="stripe"></span><div class="bk">{h(k)}</div>'
                  f'<div class="bnum">{o["num"]}</div><div class="blab">{h(lab)}</div>'
                  f'<div class="bfoot">{h(foot)}</div></div>')

    flat = [(yr["year"], it) for yr in NEWS["years"] for it in yr["items"]]   # newest first
    news_html = ""
    for yr, it in flat[:5]:
        links = "".join(f'<a class="lchip" href="{l["url"]}">{h(l["label"])}</a>' for l in it.get("links", []))
        lr = f' <span class="nlinks">{links}</span>' if links else ""
        news_html += f'<li><span class="bnd">{h(it["date"])} {h(yr)}</span> {it["text"]}{lr}</li>'

    en_cur = '' if sv else ' aria-current="page"'
    sv_cur = ' aria-current="page"' if sv else ''
    subscribe = f'<a class="btn ghost" href="{sub}">{L("Subscribe monthly","Prenumerera")}</a>' if sub else ""
    total = SWEAD["meta"]["total"]; eu_adopt = ADOPT["meta"]["eu_avg"]
    pulse_p = L(
        f"Across the EU, firm AI adoption is climbing fast: the average reached <b>{eu_adopt:.0f}%</b> of enterprises in "
        f"{ADOPT['meta']['year']}, up from 8% in 2023 (Eurostat). Sweden is well above, at <b>{total}%</b>, and its "
        f"workforce ranks 2nd of {n_ctry} on generative-AI exposure. The series that moves every month is the Swedish "
        f"depth cut below, the share of vacancies asking for an AI skill, 2006–2025, now about "
        f"<b>{t['values'][-1]:.2f}%</b> ({t['years'][-1]}, provisional), roughly <b>140×</b> its level twenty years ago.",
        f"I hela EU ökar företagens AI-användning snabbt: genomsnittet nådde <b>{eu_adopt:.0f}%</b> av företagen "
        f"{ADOPT['meta']['year']}, upp från 8% 2023 (Eurostat). Sverige ligger klart över, med <b>{total}%</b>, och "
        f"arbetskraften är näst mest exponerad för generativ AI av {n_ctry} länder. Serien som rör sig varje månad är den "
        f"svenska fördjupningen nedan, andelen lediga jobb som efterfrågar en AI-kompetens, 2006–2025, nu omkring "
        f"<b>{svn(round(t['values'][-1], 2))}%</b> ({t['years'][-1]}, preliminärt), ungefär <b>140×</b> nivån för tjugo år sedan.")

    body = f"""<div class="wrap brief"><article class="briefsheet">
  <header class="bhead">
    <div><p class="kicker">{L("AIEL Monitor · monthly brief","AIEL Monitor · månadsbrev")} · {issue}</p>
      <h1 class="btitle">{L("AI and the labour market","AI och arbetsmarknaden")} — {mname} {today.year}</h1>
      <p class="bsub">{L("A monthly snapshot from the AI-Econ Lab: international, with Sweden in depth, on public data.", "En månatlig ögonblicksbild från AI-Econ Lab: internationell, med Sverige på djupet, byggd på öppna data.")}
        {L("In focus this month","I fokus denna månad")}: {h(th_title)}.</p></div>
    <div class="bactions">
      <button class="btn primary" id="printbrief" type="button">{L("↓ Download PDF","↓ Ladda ner PDF")}</button>
      {subscribe}
      <span class="blang"><a href="/monitor/brief/"{en_cur}>EN</a> · <a href="/monitor/brief/sv/"{sv_cur}>SV</a></span>
      <a class="bback" href="/monitor/">{L("← the live monitor","← den levande monitorn")}</a></div>
  </header>

  <section class="bsec"><h2 class="bh2">{L("At a glance","I korthet")}</h2>
    <div class="bstats">{cards}</div></section>

  <section class="bsec"><h2 class="bh2">{L("The pulse · Sweden in international context","Pulsen · Sverige i internationellt sammanhang")}</h2>
    <p class="bp">{pulse_p}</p>
    <div class="bchart">{trend_svg(t)}</div>
    <p class="bsrc">{L("International benchmark","Internationell jämförelse")} (AI Index / Lightcast, 2025): {L("AI skills are required in a median 1.9% of postings across 22 countries; Sweden 2.8% on that measure. Not directly comparable to the Swedish JobTech series above (a narrower, live measure).","AI-kompetens krävs i medianen 1,9% av annonserna i 22 länder; Sverige 2,8% på det måttet. Ej direkt jämförbart med den svenska JobTech-serien ovan (ett smalare, löpande mått).")}</p></section>

  <section class="bsec"><h2 class="bh2">{L("In focus","I fokus")} · {h(th_title)}</h2>
    <p class="bp">{takeaways[theme]}</p>
    <div class="bchart">{th_chart}</div>
    <p class="bsrc">{L("Source","Källa")}: {h(srcs[theme])}. {L("Full method at","Fullständig metod på")} ai-econ-lab.github.io/monitor/#method.</p></section>

  <section class="bsec bnews"><h2 class="bh2">{L("Lab news","Nyheter från labbet")}</h2>
    <ul class="blist">{news_html}</ul></section>

  <footer class="bfooter">
    <span>AI-Econ Lab · AIEL Monitor · {issue}. {L("Public data; cite the version and date.","Öppna data; ange version och datum vid citering.")}</span>
    <span>ai-econ-lab.github.io/monitor</span></footer>
</article></div>"""
    return shell(f"{L('AIEL Monitor Brief','AIEL Monitor-brief')} — {mname} {today.year} · {SITE['brand']['name']}",
                 L(f"A monthly one-page snapshot of AI in the labour market from the AI-Econ Lab: {mname} {today.year}.",
                   f"En månatlig ögonblicksbild av AI på arbetsmarknaden från AI-Econ Lab: {mname} {today.year}."),
                 "/monitor/brief/sv/" if sv else "/monitor/brief/", body)

# ── write ────────────────────────────────────────────────────────────────────
PAGES = {"index.html": home(), "monitor/index.html": monitor(), "daioe/index.html": daioe(),
         "monitor/brief/index.html": brief("en"), "monitor/brief/sv/index.html": brief("sv"),
         "research/index.html": research(), "people/index.html": people(),
         "events/index.html": events(), "news/index.html": news(), "about/index.html": about()}

def chart_standalone(svg):
    """Self-contained SVG for download (inline light-theme styles; no page CSS). Dot or bar chart."""
    style = ('<style>.rankchart{font-family:ui-monospace,Menlo,monospace}svg{background:#ffffff}'
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
             '.sqband{fill:#0072b2;opacity:.10}.sqlo{fill:none;stroke:#9a9a9a;stroke-width:2}'
             '.sqhi{fill:none;stroke:#0072b2;stroke-width:2.6}.sqdot.lo{fill:#9a9a9a}.sqdot.hi{fill:#0072b2}'
             '.sqval{font-size:11px;font-weight:700}.sqval.lo{fill:#9a9a9a}.sqval.hi{fill:#0072b2}'
             # working-conditions dumbbell
             '.dumb{display:block}.dbtrack{stroke:#d9d5cd;stroke-width:3}.dblo{fill:#9a9a9a}.dbhi{fill:#0072b2}</style>')
    s = svg.replace('<svg class="rankchart', '<svg xmlns="http://www.w3.org/2000/svg" class="rankchart', 1)
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
        chart_standalone(barplot(CROSS["countries"], CROSS["meta"]["mean_share"], _ccx, CROSS["meta"]["weight_year"], "share", ".0f")), encoding="utf-8")
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
    with (d / "working_conditions.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f); w.writerow(["condition", "gender", "pct_least_exposed_occ", "pct_most_exposed_occ", "daioe", "wc_year"])
        for c in WORKCOND["conditions"]:
            for g in ("all", "women", "men"):
                w.writerow([c["label"], g, c[g]["lo"], c[g]["hi"], WORKCOND["meta"]["daioe_version"], WORKCOND["meta"]["wc_year"]])
    with (d / "akavia_ai_use.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["cut", "group", "pct_using_ai_2025", "pct_using_ai_2023",
                    "ci_low_2025", "ci_high_2025", "respondents_2025", "source"])
        for cut, key in (("profession", "by_profession"), ("sector", "by_sector")):
            for r in AKAVIA[key]:
                w.writerow([cut, r["name"], r["adoption"], r["prev"], r["lo"], r["hi"],
                            r["n"], AKAVIA["meta"]["source"]])
        for lab, v in zip(AKAVIA["trend"]["labels"], AKAVIA["trend"]["values"]):
            w.writerow(["all", lab, v, "", "", "", "", AKAVIA["meta"]["source"]])
    _akx = 10 * (max(r["adoption"] for r in AKAVIA["by_profession"]) // 10 + 1)
    (d / "akavia_ai_use.svg").write_text(
        chart_standalone(barplot(AKAVIA["by_profession"], 0, _akx, 0, "adoption", ".0f")),
        encoding="utf-8")
    with (d / "akavia_governance.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["wave", "pct_uses_ai", "pct_knows_of_policy", "pct_knows_of_strategy"])
        g = AKAVIA["governance"]
        for row in zip(g["labels"], g["use"], g["policy"], g["strategy"]):
            w.writerow(list(row))
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
    t = MONITOR["trend"]
    with (d / "ai_in_demand_trend.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f); w.writerow(["year", "ai_ad_share_pct"])
        for y, v in zip(t["years"], t["values"]): w.writerow([y, v])
    (d / "ai_in_demand_trend.svg").write_text(chart_standalone(trend_svg(t)), encoding="utf-8")
    with (d / "entry_level_squeeze.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["year", "entry_level_share_least_exposed_pct", "entry_level_share_most_exposed_pct", "gap_pp"])
        for r in ELS["series"]: w.writerow([r["year"], r["low"], r["high"], r["gap"]])
    (d / "entry_level_squeeze.svg").write_text(chart_standalone(squeeze_svg(ELS)), encoding="utf-8")
    (d / "working_conditions.svg").write_text(
        chart_standalone(dumbbell_svg(WORKCOND["conditions"], "all", active=True)), encoding="utf-8")
    with (d / "swe_adoption.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["firm_size", "pct_using_ai", "year", "pct_prev_wave", "prev_year"])
        for r in SWEAD["sizes"]:
            w.writerow([r["name"], r["adoption"], SWEAD["meta"]["year"], r.get("prev", ""), SWEAD["meta"]["prev_year"]])
    _swxmax = 10 * (max(r["adoption"] for r in SWEAD["sizes"]) // 10 + 1)
    (d / "swe_adoption.svg").write_text(
        chart_standalone(barplot(SWEAD["sizes"], ADOPT["meta"]["eu_avg"], _swxmax, 0, "adoption", ".0f")), encoding="utf-8")

def build():
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
    urls = ["/", "/monitor/", "/daioe/", "/research/", "/people/", "/events/", "/news/", "/about/"]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append(f"<url><loc>{BASE}{u}</loc><changefreq>monthly</changefreq></url>")
    sm.append("</urlset>")
    (OUT / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")
    print(f"Built {len(PAGES)} pages + sitemap/robots/CNAME into {OUT}/")
    print(f"  papers: {paper_count()} · people: {sum(len(g['members']) for g in PEOPLE['groups'])}")

if __name__ == "__main__":
    build()
