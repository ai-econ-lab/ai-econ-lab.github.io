#!/usr/bin/env python3
"""Standalone social image of a brief's chart, EN and SV, for LinkedIn and X (1200x675 PNG).

    python3 scripts/brief_social_card.py --month 2026-10

Why (29 Sep 2026, Depenbusch-style review of the October brief): a chart that travels as a
screenshot loses everything outside the image, so the card carries its own title, unit, source
and the lab's name. It reuses the brief's own chart markup, taken from the built brief page, so
the card can never drift from the brief. Rebuilds the site for the month, renders, restores.
"""
import argparse, functools, http.server, os, re, socketserver, subprocess, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

TITLES = {"en": ("Swedish job ads mention AI far more often than they ask for AI skills",
                 "Share of all job advertisements on Platsbanken, 2016 to June {y}",
                 "Source: JobTech / Platsbanken. AI-Econ Lab, AIEL Monitor {m}. ai-econlab.com/monitor"),
          "sv": ("Svenska jobbannonser nämner AI betydligt oftare än de efterfrågar AI-kompetens",
                 "Andel av alla jobbannonser på Platsbanken, 2016 till juni {y}",
                 "Källa: JobTech / Platsbanken. AI-Econ Lab, AIEL Monitor {m}. ai-econlab.com/monitor")}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--month", required=True); a = ap.parse_args()
    env = {**os.environ, "BRIEF_MONTH_OVERRIDE": a.month}
    subprocess.run([sys.executable, "build.py"], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    docs = ROOT / "docs"; out = ROOT / "build" / "social"; out.mkdir(parents=True, exist_ok=True)
    card_dir = docs / "_card"; card_dir.mkdir(exist_ok=True)
    y = a.month[:4]
    for lang, rel in (("en", "monitor/brief/index.html"), ("sv", "monitor/brief/sv/index.html")):
        page = (docs / rel).read_text(encoding="utf-8")
        svg = re.search(r'<div class="bchart">(<svg.*?</svg>)', page, re.S).group(1)
        # The card's subtitle carries the unit; drop the chart's own axis caption so it is not said twice.
        svg = re.sub(r'<text[^>]*>(Share of all job advertisements on Platsbanken|Andel av alla jobbannonser på Platsbanken)</text>', '', svg)
        title, sub, src = (t.format(y=y, m=a.month) for t in TITLES[lang])
        html = f"""<!doctype html><html lang="{lang}" data-theme="light"><head><meta charset="utf-8">
<link rel="stylesheet" href="/assets/styles.css"><style>
html,body{{margin:0;background:#fff}} .card{{width:1200px;height:675px;box-sizing:border-box;padding:44px 56px 30px;
display:flex;flex-direction:column;font-family:var(--sans,system-ui)}}
.k{{font-family:var(--mono);font-size:15px;letter-spacing:.12em;text-transform:uppercase;color:var(--c1)}}
.t{{font-family:var(--serif);font-size:38px;line-height:1.15;font-weight:600;margin:10px 0 4px;color:#111}}
.s{{font-size:18px;color:#555;margin-bottom:10px}} .c{{flex:1;display:flex;align-items:center}}
.c svg{{width:100%;height:auto;max-height:420px}} .f{{font-family:var(--mono);font-size:14px;color:#666;margin-top:8px}}
</style></head><body><div class="card"><div class="k">AI-Econ Lab · AIEL Monitor</div>
<div class="t">{title}</div><div class="s">{sub}</div><div class="c">{svg}</div><div class="f">{src}</div></div></body></html>"""
        (card_dir / f"{lang}.html").write_text(html, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(docs))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler); port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        for lang in ("en", "sv"):
            png = out / f"aiel-monitor-brief-{a.month.replace('-', '')}-card{'' if lang == 'en' else '-sv'}.png"
            if png.exists(): png.unlink()
            with tempfile.TemporaryDirectory() as td:
                proc = subprocess.Popen([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                                         f"--user-data-dir={td}", "--window-size=1200,675",
                                         "--force-device-scale-factor=2", f"--screenshot={png}",
                                         f"http://127.0.0.1:{port}/_card/{lang}.html"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for _ in range(60):
                    time.sleep(1)
                    if png.exists() and png.stat().st_size > 20000: break
                proc.kill(); proc.wait()
            print("wrote", png)
    finally:
        httpd.shutdown()
        for f in card_dir.iterdir(): f.unlink()
        card_dir.rmdir()
        subprocess.run([sys.executable, "build.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)

if __name__ == "__main__":
    main()
