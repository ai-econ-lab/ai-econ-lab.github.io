#!/usr/bin/env python3
"""
AI-Econ Lab — static site builder.

Reads data/*.yaml, renders self-contained HTML into docs/ (what GitHub Pages
serves), and writes sitemap.xml, robots.txt, CNAME and .nojekyll. No template
engine and no third-party deps beyond PyYAML — so it runs the same on your Mac
and in CI. Edit the YAML, run `python3 build.py`, commit, push.
"""
from pathlib import Path
import shutil, yaml, html

ROOT = Path(__file__).parent
DATA = ROOT / "data"
def load(name): return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))

SITE     = load("site.yaml")
PAPERS   = load("papers.yaml")
PEOPLE   = load("people.yaml")
MONITOR  = load("monitor.yaml")
DAIOE    = load("daioe.yaml")
SEMINARS = load("seminars.yaml")

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
      Our flagship public good, <b>AI in Demand</b>, tracks how often Swedish employers ask for AI in their
      job ads, openly and honestly, and updated as the data arrive.</p>
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
      <p>How AI shows up in the Swedish labour market: AI in Demand (live), the DAIOE Explorer (live), and modules
        on AI use and barriers to use in development.</p>
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

def research_rows(limit=None):
    rows = ""
    pubs = [("Published", PAPERS["published"], True), ("Working papers & in review", PAPERS["working"], False)]
    if limit:
        merged = (PAPERS["published"] + PAPERS["working"])[:limit]
        pubs = [("", merged, None)]
    for gname, items, is_pub in pubs:
        if gname: rows += f'<div class="grouphdr">{h(gname)}</div>'
        for p in items:
            badge = "Published" if p["venue"] and ("accepted" in p["venue"].lower() or "online" in p["venue"].lower()
                    or p in PAPERS["published"]) else p["venue"] or "Working paper"
            bcls = " pub" if p in PAPERS["published"] else ""
            tag = h(p["venue"]) if p["venue"] else "Working paper"
            title = h(p["title"])
            if p.get("url"):
                title = f'<a href="{p["url"]}" style="color:inherit">{title}</a>'
            rows += (f'<div class="rrow"><span class="yr tnum">{h(p["year"])}</span>'
                     f'<span><span class="rt">{title}</span><span class="ra">{h(p["authors"])}</span></span>'
                     f'<span class="badge{bcls}">{tag}</span></div>')
    return rows

def paper_count(): return len(PAPERS["published"]) + len(PAPERS["working"])

def research():
    body = f"""<div class="wrap"><div class="pagehead">
  <p class="kicker">Research</p><h2 class="sec">Papers &amp; publications</h2>
  <p class="secintro">Peer-reviewed articles and working papers from the lab and its network. Data-driven measures,
    causal identification, and register-grade evidence on AI and work.</p></div></div>
<div class="wrap"><section style="padding-top:8px"><div class="rows">{research_rows()}</div></section></div>"""
    return shell(f"Research · {SITE['brand']['name']}",
                 "Peer-reviewed articles and working papers on AI and the labour market.",
                 "/research/", body)

def initials(name):
    parts = [p for p in name.replace("-", " ").split() if p]
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else name[:2].upper()

def person_card(m):
    if m.get("photo"):
        avatar = f'<img class="avatar" src="/assets/people/{m["photo"]}" alt="{h(m["name"])}" loading="lazy">'
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

def daioe():
    # The PURE measure. The interactive Explorer lives under the Monitor (it consumes DAIOE + SCB).
    d = DAIOE
    res = "".join(f'<li><a href="{r["href"]}">{h(r["label"])}</a> <span class="mono">· {h(r["note"])}</span></li>'
                  for r in d["resources"])
    body = f"""<div class="wrap"><div class="hero" style="padding-bottom:6px"><div>
  <div class="eyebrow"><span class="dot"></span> {h(d['tagline'])}</div>
  <h1 class="title" style="max-width:16ch">{h(d['headline'])}: how exposed is each job to AI?</h1>
  <p class="lede" style="max-width:60ch">{h(d['lede'])}</p>
  <div class="cta-row"><a class="btn primary" href="{d['resources'][0]['href']}">Download the data →</a>
    <a class="btn ghost" href="/monitor/#daioe-explorer">See it applied in the Monitor</a></div>
</div></div></div>

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
  <p class="secintro">The <a href="/monitor/#daioe-explorer">DAIOE Explorer</a>, part of the AI-Econ Lab Monitor, sets
    Swedish employment by occupation against DAIOE exposure levels, in yearly and monthly views.</p>
</section></div></div>"""
    return shell(f"DAIOE · data-driven AI occupational exposure · {SITE['brand']['name']}",
                 "DAIOE: the lab's open, data-driven measure of occupational AI exposure, mapped across SOC / ISCO / SSYK.",
                 "/daioe/", body, jsonld=daioe_ld())

def seminars():
    s = SEMINARS; ser = s["series"]
    fmt = "".join(f"<li>{h(x)}</li>" for x in ser["format"])
    ups = ""
    for e in s["upcoming"]:
        ups += (f'<div class="semrow"><span class="yr tnum">{h(e["date"])}</span>'
                f'<span><span class="rt">{h(e["speaker"])}</span><span class="ra">{h(e["topic"])}</span></span></div>')
    past = "".join(f'<div class="confrow"><span class="yr tnum">{h(c["year"])}</span>'
                   f'<span class="rd">{h(c["note"])}</span></div>' for c in s["conferences"]["past"])
    nx = s["conferences"]["next"]
    body = f"""<div class="wrap"><div class="pagehead">
  <p class="kicker">Seminars &amp; events</p><h2 class="sec">{h(ser['title'])}</h2>
  <p class="secintro">{h(ser['intro'])}</p></div></div>
<div class="wrap"><section style="padding-top:6px">
  <div class="two" style="grid-template-columns:1.3fr 1fr;align-items:start">
    <div><div class="grouphdr">Upcoming &amp; recent</div><div class="rows">{ups}</div></div>
    <div class="card"><div class="charttitle" style="margin-bottom:8px">Format</div>
      <ul class="reslist">{fmt}</ul>
      <p class="psub" style="margin-top:12px">Contact: {h(ser['contact'])}</p></div>
  </div>
</section></div>
<div class="rule"><div class="wrap"><section>
  <p class="kicker">Conference series</p>
  <h2 class="sec">{h(nx['title'])} · {h(nx['when'])} · {h(nx['where'])}.</h2>
  <p class="secintro">{h(nx['note'])}</p>
  <div class="grouphdr" style="margin-top:24px">Earlier conferences</div>
  <div class="rows">{past}</div>
</section></div></div>"""
    return shell(f"Seminars &amp; conferences · {SITE['brand']['name']}",
                 "The AIEL brown-bag seminar series (part of WASP-HS AISCAF) and the AIEL conference series.",
                 "/seminars/", body)

def monitor():
    m = MONITOR
    mods = ""
    for mod in m["modules"]:
        live = mod["status"] == "live"
        anchor = {"AI in Demand": "#ai-in-demand", "DAIOE Explorer": "#daioe-explorer"}.get(mod["name"], "")
        chip = ('<span class="mstatus live">● live</span>' if live else '<span class="mstatus planned">◔ planned</span>')
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
      <a class="btn ghost" href="#daioe-explorer">Open the DAIOE Explorer</a></div></div>
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

<div class="rule" id="daioe-explorer"><div class="wrap"><section>
  <p class="kicker">Module · live</p>
  <h2 class="sec">DAIOE Explorer.</h2>
  <p class="secintro">Swedish employment by occupation set against <a href="/daioe/">DAIOE</a> AI-exposure levels
    (built and maintained in-house). Yearly and monthly views.</p>
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
    body = f"""<div class="wrap"><div class="pagehead">
  <p class="kicker">About</p><h2 class="sec">An economics-led lab on AI and the future of work</h2></div>
<section style="padding-top:14px"><div class="prose">
  <p>The AI-Econ Lab, at Örebro University and the Ratio Institute, studies how artificial intelligence is
    reshaping labour markets, particularly for white-collar and service work. We are part of the WASP-HS
    <b>AISCAF</b> cluster (AI, Structural Change and the Future of Work) and its ten-university network.</p>
  <p>Our work combines unique Swedish administrative registers with public job-ad data and international
    comparisons across Denmark, Portugal, Germany and beyond. We are deliberately multi-disciplinary: economists
    work alongside sociologists, business scholars and computer scientists.</p>
  <p>Alongside peer-reviewed research we build open, citable public goods (the <a href="/monitor/">AI in Demand</a>
    monitor and the <a href="{SITE['links']['explorer']}">DAIOE</a> occupational-exposure measure), so that
    evidence on AI and work is available to policymakers, journalists and the public, not only to specialists.</p>
  <h3>Contact</h3>
  <p>{h(SITE['footer']['contact'])}<br>Seminars and conferences are announced through the lab and the AISCAF
    seminar series.</p>
</div></section></div>"""
    return shell(f"About · {SITE['brand']['name']}", SITE["brand"]["description"], "/about/", body)

# ── write ────────────────────────────────────────────────────────────────────
PAGES = {"index.html": home(), "monitor/index.html": monitor(), "daioe/index.html": daioe(),
         "research/index.html": research(), "people/index.html": people(),
         "seminars/index.html": seminars(), "about/index.html": about()}

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
    urls = ["/", "/monitor/", "/daioe/", "/research/", "/people/", "/seminars/", "/about/"]
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
