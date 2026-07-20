#!/usr/bin/env python3
"""
AI-Econ Lab — static site builder.

Reads data/*.yaml, renders self-contained HTML into docs/ (what GitHub Pages
serves), and writes sitemap.xml, robots.txt, CNAME and .nojekyll. No template
engine and no third-party deps beyond PyYAML — so it runs the same on your Mac
and in CI. Edit the YAML, run `python3 build.py`, commit, push.
"""
from pathlib import Path
import shutil, yaml, html, re, unicodedata

ROOT = Path(__file__).parent
DATA = ROOT / "data"
def load(name): return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))

SITE     = load("site.yaml")
PAPERS   = load("papers.yaml")
PEOPLE   = load("people.yaml")
MONITOR  = load("monitor.yaml")
DAIOE    = load("daioe.yaml")
SEMINARS = load("seminars.yaml")
DAIOE_EXP = load("daioe_exposure.yaml")
NEWS     = load("news.yaml")
# The occupation-search data lives in assets/daioe_occupations.json and is fetched at runtime
# (see app.js occSearch), so it is NOT embedded here. It auto-tracks the latest DAIOE year.

OUT = ROOT / SITE["build"]["out"]
BASE = SITE["brand"]["base_url"].rstrip("/")
h = lambda s: html.escape(str(s), quote=True)   # escape plain-text (titles, names)

# ── shared chrome ────────────────────────────────────────────────────────────
def masthead(active):
    b = SITE["brand"]
    items = ""
    for n in SITE["nav"]:
        cur = ' aria-current="page"' if (not n.get("cta") and n["href"] == active) else ""
        cls = ' class="cta"' if n.get("cta") else ""
        items += f'<a href="{n["href"]}"{cls}{cur}>{h(n["label"]).replace("&gt;",">")}</a>'
    reg = "".join(f"<span>{s}</span>" for s in SITE["registration"])
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
  <div><h4>Contact</h4><p>{h(SITE['footer']['contact'])}</p></div>
</div><div class="footend">
  <span>© 2026 {h(b['name'])} · Örebro University &amp; RATIO</span>
  <span>DATA JobTech / Platsbanken (CC0) · MONITOR PROTOTYPE · NOT FOR CITATION</span>
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
<link rel="stylesheet" href="/assets/styles.css">{ld}
</head><body>
<a class="skip" href="#main">Skip to content</a>
{masthead(path)}
<main id="main">{body}</main>
{footer()}
<div class="tip" id="tip"></div>
{trend_js}<script src="/assets/app.js"></script>
</body></html>"""

# ── JSON-LD ──────────────────────────────────────────────────────────────────
import json
def org_ld():
    b = SITE["brand"]
    return json.dumps({"@context":"https://schema.org","@type":"Organization","name":b["name"],
        "url":BASE,"description":b["description"],
        "parentOrganization":{"@type":"CollegeOrUniversity","name":"Örebro University"},
        "memberOf":{"@type":"Organization","name":"WASP-HS AISCAF"}}, ensure_ascii=False)

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
    <h1 class="title">We measure how <em>artificial intelligence</em> is reshaping the world of work.</h1>
    <p class="lede">An economics-led lab at Örebro University and RATIO, part of the WASP-HS AISCAF cluster.
      Our flagship public good, the <b>AIEL Monitor</b>, tracks how AI is moving through the Swedish
      labour market, openly and honestly, updated as the data arrive.</p>
    <div class="cta-row"><a class="btn primary" href="/monitor/">Open AI in Demand →</a>
      <a class="btn ghost" href="/monitor/#method">How we measure it</a></div>
    <div class="affil">{affils}</div>
  </div>
  <div class="panel">
    <div class="panelhead"><span class="ttl">AI in Demand · share of Swedish job ads</span>
      <span class="livechip"><i></i>live</span></div>
    <div class="panelbody">
      <p class="psub">Vacancies requesting any AI skill, 2006–2025. About <b>140×</b> higher than twenty years
        ago, and steepest after 2023.</p>
      <svg id="trend" viewBox="0 0 640 300" role="img" aria-label="Line chart: AI-in-demand share of Swedish job ads, 2006 to 2025"></svg>
      <div class="legend"><span><i style="background:var(--c1)"></i>Broad · any AI-related term</span>
        <span class="mono" style="color:var(--muted);font-size:11px">╌ 2025 provisional</span></div>
    </div>
  </div>
</div></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">What the lab is</p>
  <h2 class="sec">A research lab first; the monitor is how we show our work in public.</h2>
  <p class="secintro">We combine unique Swedish administrative registers with public job-ad data and international
    comparisons. Economists work alongside sociologists, business scholars and computer scientists, because a
    labour market changed by AI cannot be read from one discipline or one country alone.</p>
  <div class="pillars">
    <div class="pillar"><div class="n">01 · DATA</div><h3>Register-grade evidence</h3>
      <p>Population-wide, employer–employee-linked Swedish registers (LISA, AGI) with monthly frequency and
        4-digit occupations, paired with 10.9M public job ads.</p></div>
    <div class="pillar"><div class="n">02 · REACH</div><h3>Multi-country</h3>
      <p>Sweden at register depth; Denmark, Portugal and Germany through partners; 30 countries via EU-LFS for
        external validity.</p></div>
    <div class="pillar"><div class="n">03 · LENS</div><h3>Multi-disciplinary</h3>
      <p>Economics, sociology, business administration and computer science, inside the WASP-HS AISCAF cluster
        and its 10-university network.</p></div>
    <div class="pillar"><div class="n">04 · OUTPUT</div><h3>Open public goods</h3>
      <p>Peer-reviewed research, plus citable, versioned public tools: the AI in Demand monitor and the DAIOE
        exposure measure and Explorer.</p></div>
  </div>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">Flagship · AI in Demand</p>
  <h2 class="sec">Four things the Swedish job market is telling us right now.</h2>
  <p class="secintro">Every figure is measured from the ad text with a versioned, citable term list. Where
    something is not yet measured, we say so.</p>
  <div class="tiles">{tiles}</div>
  <div class="two">
    <div class="prod"><div class="tag">The Monitor · public data</div><h3>The AI-Econ Lab Monitor</h3>
      <p>How AI shows up in the Swedish labour market: AI in Demand (live), the Occupations Explorer (live), and
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
    """Auto-detect assets/people/<slug>.<ext>; drop a correctly named file and it appears."""
    for ext in ("jpg", "jpeg", "png", "webp"):
        if (ROOT / "assets" / "people" / f"{pslug(name)}.{ext}").exists():
            return f"{pslug(name)}.{ext}"
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
    Generative AI by default; switch the sub-domain to compare. This is the measure behind Die Zeit's
    &ldquo;Wie ersetzbar ist Ihr Job?&rdquo; interactive.</p>
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
    seasons = ""
    for season in s["seasons"]:
        rows = ""
        for e in season["seminars"]:
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
            rows += (f'<div class="semrow"><span class="yr tnum">{h(e["date"])}</span>'
                     f'<span><span class="rt">{speaker}{aff}</span><span class="ra">{title}</span></span></div>')
        seasons += f'<div class="grouphdr">{h(season["name"])}</div><div class="rows semlist">{rows}</div>'
    past = "".join(f'<div class="confrow"><span class="yr tnum">{h(c["year"])}</span>'
                   f'<span class="rd">{h(c["note"])}</span></div>' for c in s["conferences"]["past"])
    nx = s["conferences"]["next"]
    body = f"""<div class="wrap"><div class="pagehead">
  <p class="kicker">Events</p><h2 class="sec">Seminars &amp; conferences</h2>
  <p class="secintro">{h(ser['intro'])}</p></div></div>

<div class="rule" id="conference-2028"><div class="wrap"><section style="padding-top:20px">
  <p class="kicker">Next conference</p>
  <h2 class="sec">{h(nx['title'])}: {h(nx['theme'])}.</h2>
  <p class="secintro">{h(nx['when'])} · {h(nx['where'])}. {h(nx['note'])}</p>
  <div class="grouphdr" style="margin-top:24px">Earlier conferences</div>
  <div class="rows">{past}</div>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">Seminar series</p>
  <h2 class="sec">{h(ser['title'])}.</h2>
  <div class="two" style="grid-template-columns:1.5fr 1fr;align-items:start;margin-top:8px">
    <div>{seasons}</div>
    <div class="card"><div class="charttitle" style="margin-bottom:8px">Attending</div>
      <ul class="reslist">{fmt}</ul>
      <p style="margin:12px 0 0"><a class="btn ghost" style="font-size:12px" href="{ser['zoom']}">Join on Zoom →</a></p>
      <p class="psub" style="margin-top:12px">Contact: {h(ser['contact'])}</p></div>
  </div>
</section></div></div>"""
    return shell(f"Events · {SITE['brand']['name']}",
                 "The AIEL conference series and the monthly brown-bag seminar series (part of WASP-HS AISCAF).",
                 "/events/", body)

def news():
    blocks = ""
    for yr in NEWS["years"]:
        items = "".join(f'<div class="nrow"><span class="yr tnum">{h(it["date"])}</span>'
                        f'<span class="ntext">{it["text"]}</span></div>' for it in yr["items"])
        blocks += f'<div class="grouphdr">{h(yr["year"])}</div><div class="rows">{items}</div>'
    body = f"""<div class="wrap"><div class="pagehead">
  <p class="kicker">News</p><h2 class="sec">What the lab has been up to</h2>
  <p class="secintro">Publications, media, grants, conferences and people, since the lab was initiated in 2019.</p></div></div>
<div class="wrap"><section style="padding-top:8px">{blocks}</section></div>"""
    return shell(f"News · {SITE['brand']['name']}",
                 "News and history of the AI-Econ Lab since 2019: publications, media, grants and events.",
                 "/news/", body)

def monitor():
    m = MONITOR
    mods = ""
    STCHIP = {"live":"● live", "next":"◑ next", "planned":"◔ planned", "someday":"◌ someday"}
    for mod in m["modules"]:
        live = mod["status"] == "live"
        anchor = {"AI in Demand": "#ai-in-demand", "Occupations Explorer": "#occupations-explorer"}.get(mod["name"], "")
        chip = f'<span class="mstatus {"live" if live else "planned"}">{STCHIP.get(mod["status"],mod["status"])}</span>'
        name = f'<a href="{anchor}">{h(mod["name"])}</a>' if anchor else h(mod["name"])
        mods += (f'<div class="module {"on" if live else "off"}"><div class="mtop"><h3>{name}</h3>{chip}</div>'
                 f'<p>{h(mod["desc"])}</p></div>')
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
  <div><div class="eyebrow"><span class="dot"></span> Public monitor · updated as the data arrive</div>
    <h1 class="title">{h(m['headline'])}</h1>
    <p class="lede">{h(m['lede'])}</p>
    <div class="cta-row"><a class="btn primary" href="#ai-in-demand">See AI in Demand →</a>
      <a class="btn ghost" href="#occupations-explorer">Open the Occupations Explorer</a></div></div>
  <div class="panel"><div class="panelhead"><span class="ttl">AI in Demand · share of Swedish job ads</span>
    <span class="livechip"><i></i>live</span></div>
    <div class="panelbody"><p class="psub">Broad measure, any AI-related term, 2006–2025.</p>
      <svg id="trend" viewBox="0 0 640 300" role="img" aria-label="AI-in-demand share of Swedish job ads, 2006 to 2025"></svg>
      <div class="legend"><span><i style="background:var(--c1)"></i>Broad · any AI-related term</span>
        <span class="mono" style="color:var(--muted);font-size:11px">╌ 2025 provisional</span></div></div></div>
</div></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">What the monitor tracks</p>
  <h2 class="sec">Several views on AI in the Swedish labour market.</h2>
  <p class="secintro">Two modules are live today; more are in development. Everything runs on public data, so it can be
    citable and refreshed without any funder's data.</p>
  <div class="modules">{mods}</div>
</section></div></div>

<div class="rule" id="ai-in-demand"><div class="wrap"><section>
  <p class="kicker">Module · live</p>
  <h2 class="sec">AI in Demand.</h2>
  <p class="secintro">{h(m['aiindemand_lede'])}</p>
  <div class="tiles">{tiles}</div>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">AI in Demand · coming next</p>
  <h2 class="sec" style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">Who is the AI for?
    <span class="preview-flag">◔ {h(m['segmentation']['flag'])}</span></h2>
  <p class="secintro">{h(m['segmentation']['intro'])}</p>
  <div class="two" style="grid-template-columns:1fr 1fr 1fr">{seg}</div>
</section></div></div>

<div class="rule" id="occupations-explorer"><div class="wrap"><section>
  <p class="kicker">Module · live</p>
  <h2 class="sec">Occupations Explorer.</h2>
  <p class="secintro">Swedish employment by occupation over time (and, soon, by region), with
    <a href="/daioe/">DAIOE</a> AI-exposure overlaid. Built and maintained in-house; yearly and monthly views.</p>
  <div class="explorers">{explorers}</div>
</section></div></div>

<div class="rule" id="method"><div class="wrap"><section>
  <p class="kicker">How to read this</p>
  <h2 class="sec">What we measure, and what we don't yet.</h2>
  <div class="prose" style="margin-top:16px">
    <p>The AI in Demand module reads every open and historical advertisement in Sweden's public job board
      (Platsbanken / JobTech), 2006–2025: about <b>10.9 million ads</b>. An ad counts as AI-in-demand when its text
      requests an AI skill, matched by a versioned, citable term list (Swedish and English). A semantic layer, now
      training, will catch AI ads that use no listed term.</p>
    <h3>Caveats, in plain sight</h3><ul style="color:var(--ink-2);font-size:14px;line-height:1.6">{caveats}</ul>
  </div>
</section></div></div>"""
    return shell(f"The AI-Econ Lab Monitor · {SITE['brand']['name']}",
                 "A public monitor of AI in the Swedish labour market: demand, use and barriers, on public data.",
                 "/monitor/", body, jsonld=dataset_ld(), need_chart=True)

def about():
    c = SITE["contact"]; bk = SITE["book"]
    labdesc = "".join(f"<p>{h(p)}</p>" for p in SITE["about_paras"])
    clinks = "".join(f'<a href="{l["href"]}">{h(l["label"])}</a> ' for l in c.get("links", []))
    body = f"""<div class="wrap"><div class="pagehead">
  <p class="kicker">About</p><h2 class="sec">An economics-led lab on AI and the future of work</h2></div>
<section style="padding-top:14px"><div class="prose">
  <p>The AI-Econ Lab, at Örebro University and the Ratio Institute, studies how artificial intelligence is
    reshaping labour markets, particularly for white-collar and service work. Alongside peer-reviewed research we
    build open, citable public goods (the <a href="/monitor/">AIEL Monitor</a> and the <a href="/daioe/">DAIOE</a>
    exposure measure), so evidence on AI and work reaches policymakers, journalists and the public, not only
    specialists.</p>
</div></section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">The lab</p><h2 class="sec">Who we are.</h2>
  <div class="prose" style="margin-top:14px">{labdesc}</div>
</section></div></div>

<div class="rule"><div class="wrap"><section>
  <p class="kicker">Book</p>
  <h2 class="sec">{h(bk['title'])}.</h2>
  <p class="secintro">{h(bk['author'])} · {h(bk['year'])} · {h(bk['publisher'])}. {h(bk['note'])}</p>
</section></div></div>

<div class="rule" id="contact"><div class="wrap"><section>
  <p class="kicker">Contact &amp; visit</p><h2 class="sec">Get in touch.</h2>
  <div class="two" style="grid-template-columns:1fr 1fr;margin-top:18px">
    <div class="prose">
      <p>{h(c['invite'])}</p>
      <p>{clinks}</p>
    </div>
    <div class="card">
      <p style="margin:0 0 8px"><span class="lbl">E-mail</span> <a href="mailto:{c['email']}">{h(c['email'])}</a></p>
      <p style="margin:0 0 8px"><span class="lbl">Phone</span> {h(c['phone'])}</p>
      <p style="margin:0"><span class="lbl">Post</span> {h(c['address'])}</p>
    </div>
  </div>
</section></div></div>"""
    return shell(f"About &amp; contact · {SITE['brand']['name']}", SITE["brand"]["description"], "/about/", body)

# ── write ────────────────────────────────────────────────────────────────────
PAGES = {"index.html": home(), "monitor/index.html": monitor(), "daioe/index.html": daioe(),
         "research/index.html": research(), "people/index.html": people(),
         "events/index.html": events(), "news/index.html": news(), "about/index.html": about()}

def build():
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for name, htmlstr in PAGES.items():
        p = OUT / name; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(htmlstr, encoding="utf-8")
    shutil.copytree(ROOT / "assets", OUT / "assets")   # recurses into assets/people/ etc.
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
