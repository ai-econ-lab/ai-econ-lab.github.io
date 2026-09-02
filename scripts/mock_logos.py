#!/usr/bin/env python3
"""Mock-up: where the AISCAF and WASP-HS marks could sit on the Monitor.

    python3 scripts/mock_logos.py    -> build/mock/logo-placement.html

Four options, same two marks, so the choice is visual rather than described. Written outside
docs/ so it cannot be published by accident.

THE CONSTRAINT THAT DRIVES ALL FOUR. The two marks have very different proportions: WASP-HS is
1679x134, about 12.5:1, and AISCAF is 2034x468, about 4.3:1. Set to the same HEIGHT, WASP-HS
becomes three times wider and swamps the row. Set to the same WIDTH, AISCAF becomes three times
taller. Neither is a design; both are what happens when you forget to look. So every option
below sizes them to equal CAP HEIGHT, which is what the eye actually compares, and that means
WASP-HS is set smaller in height than AISCAF and still ends up wider.

The second constraint is honesty about relationships. Örebro University and Ratio are where the
work is done; WASP-HS funds AISCAF; AISCAF is the cluster the lab contributes to. A row of four
equal marks would say they are four sponsors, which is wrong, and CLAUDE.md is explicit that
AISCAF must never be presented as something it is not.
"""
import datetime, importlib.util, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("aiel_build", ROOT / "build.py")
B = importlib.util.module_from_spec(spec); sys.modules["aiel_build"] = B
spec.loader.exec_module(B)

L = f"{ROOT}/assets/logos"
WASP_B = f"{L}/WASP-HS_Logotype_Blue_Full_Name.png"
WASP_W = f"{L}/WASP-HS_Logotype_White_Full_Name.png"
# Julia sent a transparent, dark-ink AISCAF mark on 31 Aug 2026. The deck copy used before
# was a dark PLAQUE and rendered as a black box on the white page; that is what this fixes.
AISCAF = f"{L}/aiscaf_dark_ink.png"
AISCAF_W = f"{L}/aiscaf_white_ink.png"

# Equal cap height: AISCAF's wordmark is roughly 3.5x the cap height of WASP-HS's at equal
# image height, so WASP-HS is given the greater image height to compensate.
CAP = 'style="height:{h}px;width:auto;display:block"'


def opt(n, title, why, html, note=""):
    return f"""<section class="bsec"><h2 class="bh2">{n} &middot; {title}</h2>
  <p class="bp">{why}</p>
  <div style="border:1px solid var(--hair);border-radius:8px;padding:22px;margin:14px 0">{html}</div>
  {f'<p class="bsrc">{note}</p>' if note else ''}</section>"""


def main():
    # The new mark is a roundel plus a small strapline, 1.3:1, so its wordmark occupies a
    # fraction of the image height. Matching IMAGE height to WASP-HS makes AISCAF look tiny;
    # these numbers match the two WORDMARKS, which is what a reader actually compares.
    a = f'<img src="{AISCAF}" alt="AISCAF" {CAP.format(h=56)}>'
    w = f'<img src="{WASP_B}" alt="WASP-HS" {CAP.format(h=15)}>'
    w_small = f'<img src="{WASP_B}" alt="WASP-HS" {CAP.format(h=11)}>'
    a_small = f'<img src="{AISCAF}" alt="AISCAF" {CAP.format(h=40)}>'

    o1 = (f'<p style="font:600 11px/1.4 var(--mono,monospace);letter-spacing:.08em;'
          f'text-transform:uppercase;color:var(--ink-faint);margin:0 0 12px">Part of</p>'
          f'<div style="display:flex;align-items:center;gap:34px;flex-wrap:wrap">{a}{w}</div>')

    o2 = (f'<div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;'
          f'font-size:13px;color:var(--ink-2)">'
          f'<span>The AI-Econ Lab contributes to</span>{a_small}'
          f'<span>, a research cluster financed by</span>{w_small}</div>')

    o3 = (f'<div style="display:grid;gap:10px;max-width:380px">'
          f'<div style="display:flex;align-items:center;gap:12px">{a}'
          f'<span style="font-size:12px;color:var(--ink-faint)">cluster</span></div>'
          f'<div style="display:flex;align-items:center;gap:12px">{w}'
          f'<span style="font-size:12px;color:var(--ink-faint)">funder</span></div></div>')

    o4 = (f'<div style="background:#232b65;border-radius:6px;padding:20px 22px">'
          f'<p style="font:600 11px/1.4 monospace;letter-spacing:.08em;text-transform:uppercase;'
          f'color:rgba(255,255,255,.62);margin:0 0 12px">Part of</p>'
          f'<div style="display:flex;align-items:center;gap:34px;flex-wrap:wrap">'
          f'<img src="{AISCAF_W}" alt="AISCAF" {CAP.format(h=56)}>'
          f'<img src="{WASP_W}" alt="WASP-HS" {CAP.format(h=17)}></div></div>')

    body = f"""<div class="wrap brief"><article class="briefsheet">
  <header class="bhead"><div>
    <p class="kicker">AIEL MONITOR &middot; MOCK-UP &middot; LOGO PLACEMENT</p>
    <h1 class="btitle">Where the AISCAF and WASP-HS marks go</h1>
    <p class="bsub">Four options, same two marks, so the choice is visual. Nothing is placed on
      the live site. Every option sets the two to equal <b>cap height</b>, not equal image
      height: WASP-HS is 12.5:1 and AISCAF 4.3:1, so matching image heights makes WASP-HS three
      times wider and it swamps the row.</p></div></header>

  {opt(1, "Footer strip, &ldquo;Part of&rdquo;",
       "The plainest answer. A quiet label, then the two marks, at the foot of the Monitor above "
       "the citation line. It reads as attribution rather than sponsorship, and it does not "
       "compete with the data.",
       o1,
       "My recommendation. Least weight, correct relationship, works on every page without a "
       "layout change.")}

  {opt(2, "Inline in a sentence",
       "The marks set into a line of prose that states the relationship in words: the lab "
       "contributes to AISCAF, which WASP-HS finances. The most accurate option, because it is "
       "the only one that says what the relationship IS.",
       o2,
       "Strongest on accuracy, weakest visually: small marks in running text are hard to set "
       "well and reproduce badly in print.")}

  {opt(3, "Stacked, labelled",
       "Each mark on its own line with a one-word role. Solves the proportion problem entirely, "
       "since the two never sit side by side, and removes any suggestion that they are "
       "equivalent.",
       o3,
       "Takes vertical space, and the labels risk looking like a form. Good on an About page, "
       "heavy in a footer.")}

  {opt(4, "Navy plaque, white marks",
       "The same strip as option 1 on the lab's brand navy (#232b65), using the white WASP-HS "
       "file. Gives the marks a deliberate home rather than letting them float on the page "
       "background.",
       o4,
       "Handsome, but it introduces a second dark block to a page that has none, and it commits "
       "the AISCAF file to looking right on navy, which needs checking at full size.")}

  <section class="bsec"><h2 class="bh2">What none of these settles</h2>
    <p class="bp"><b>Örebro University and Ratio are not here.</b> They are where the work is
      done, which is a different relationship from a cluster and its funder, and putting all four
      in one row would say they are four sponsors. If institutional marks are wanted too, they
      belong in a separate line with their own wording, not in this strip.</p>
    <p class="bp"><b>Placement is not permission to promote.</b> The comms hold stands: the
      Monitor and the briefs publish, nothing is promoted until the joint launch with the Oskar
      and Leo report. Hanna Nordin has said she will be ready then.</p>
    <p class="bp"><b>Vectors exist if wanted.</b> Hanna offered vectorised WASP-HS files. At
      1679px the raster is ample for the web; ask if the mark is ever set large in print.</p>
  </section>

  <footer class="bfooter"><span>AI&ndash;Econ Lab &middot; MOCK-UP, not published &middot;
    built {datetime.date.today().isoformat()}</span></footer></article></div>"""

    html = B.shell("Logo placement (mock-up) · AI-Econ Lab",
                   "Four placements for the AISCAF and WASP-HS marks on the AIEL Monitor.",
                   "/monitor/", body)
    html = html.replace('href="/assets/', f'href="{ROOT}/docs/assets/').replace(
        'src="/assets/', f'src="{ROOT}/docs/assets/')
    out = ROOT / "build" / "mock" / "logo-placement.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
