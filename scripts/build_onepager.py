#!/usr/bin/env python3
"""
build_onepager.py — the AIEL Monitor as a one-page infographic, generated from the site's data.

WHO IT IS FOR. A student or a journalist who asks "what is actually happening to the labour
market and AI?" and wants one page rather than a report. That audience sets the language: the
five modules lead with the QUESTION each answers, not with our internal name for it, and the
house vocabulary (floor, ceiling, grey zone, whole-text, recall-corrected) is either translated
or dropped. If a term needs the methods note to parse, it does not belong on this sheet.

DESCRIPTIVE, AND SAYING SO. That reader's first instinct is a causal one: AI is doing this to
jobs. Nothing here supports that and the sheet says so twice, once in the standfirst and once
beneath the Swedish series, in plain words rather than in a hedge.

THE ONE THING THIS MUST NOT DO. A dated sheet invites the reader to think every number on it is
from that date. Almost none are: adoption is annual, the exposure measure is a 2023 vintage,
METR moves a few times a year, and only the Swedish live window moves daily. So the generation
date and the data vintages are separated and differently styled, and the standfirst says which
is which.

SINGLE SOURCE OF TRUTH, ENFORCED. Everything is read from data/monitor.yaml, the same file
build.py renders and check_claims.py polices, and the comparison figures are PARSED out of the
curated prose rather than retyped. If that prose changes shape the parse raises instead of
silently drawing a stale bar. Two copies of a number drift; one copy cannot.

DESIGN NOTES (form, then colour, then validate).
  * The hero is the Swedish range drawn as a filled BAND, not two lines that happen to sit near
    each other. The Monitor's argument is that it reports a range rather than a point, so the
    band is that argument made visible, and it costs no categorical colour because it is one
    thing measured two ways.
  * The comparison panels carry two entities, Sweden against an international benchmark, so
    they take the only categorical pair on the sheet, used identically in every panel. Colour
    follows the entity, never the panel.
  * Palette validated with the checker, not by eye: #0072B2 / #D55E00 passes lightness, chroma,
    CVD separation (dE 21.9 protan), normal-vision separation (31.2) and 3:1 contrast. The lab
    navy #232B65 FAILS the lightness band as a data mark (L 0.318), so it is ink for headings
    and rules only and never a series.
  * Every bar is direct-labelled, so identity never rests on colour alone and the sheet still
    reads when printed in greyscale, which is how a journalist will print it.

Run:  python3 scripts/build_onepager.py              -> docs/aiel-monitor-onepager.pdf
      python3 scripts/build_onepager.py --landscape
"""

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from labels import shorten  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# The frozen definition lives in ONE place. Two source lines here, one English and one
# Swedish, each carried their own 'v1.4' literal and were still on v1.3 when the site had
# reached v1.4. Importing it means a re-freeze cannot leave the one-pager behind again.
from monitor_root import DEF_VERSION  # noqa: E402
DATA = ROOT / "data"
OUT = ROOT / "docs" / "aiel-monitor-onepager.pdf"
# Resolved, never hardcoded. This was "/opt/homebrew/bin/tectonic", one Mac's Homebrew path,
# which cannot exist on the Linux runner that rebuilds the site. There it raised
# FileNotFoundError inside build.py's try/except, which caught it, kept the previous PDF and
# printed "no TeX engine here" — so a sheet that had silently stopped regenerating looked like
# a deliberate skip. $TECTONIC overrides; otherwise PATH, then the known Homebrew locations.
def _find_tectonic() -> str:
    import os
    import shutil
    return (os.environ.get("TECTONIC")
            or shutil.which("tectonic")
            or next((c for c in ("/opt/homebrew/bin/tectonic", "/usr/local/bin/tectonic",
                                 "/usr/bin/tectonic") if Path(c).exists()), ""))


TECTONIC = _find_tectonic()

# Hex for \definecolor, and a LaTeX-legal NAME to refer to it by. A colour name may not
# begin with a digit, so "0072B2" is not usable as one: \textcolor{0072B2} is an undefined
# control sequence, which is how this first failed to compile.
SE_HEX, SE = "0072B2", "sweden"      # our own measure / Sweden  (Okabe-Ito blue)
INTL_HEX, INTL = "D55E00", "intl"    # international comparison  (Okabe-Ito vermillion)
INK_HEX = "232B65"   # lab navy: headings and rules ONLY, never a data mark
SOFT_HEX, SOFT = "4B5563", "soft"   # darkened from 6B7280: this grey carries the small text,
                                    # and small + low-contrast is the worst case for low vision


def tex(s):
    s = html.unescape(re.sub(r"<[^>]+>", "", str(s) if s is not None else ""))
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
                 ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
                 ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")]:
        s = s.replace(a, b)
    return s.replace("−", "$-$").replace("–", "--")


def plain(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or ""))


def grab(pattern, text, what):
    """Parse a figure out of the curated prose, or fail loudly. Never guess, never retype."""
    m = re.search(pattern, plain(text))
    if not m:
        raise SystemExit(
            f"build_onepager: could not read {what} from monitor.yaml.\n"
            f"  pattern: {pattern}\n  text:    {plain(text)[:160]}\n"
            f"  The prose changed shape. Fix the pattern; do not hardcode the number.")
    return [float(g) for g in m.groups()]


def range_band(years, hi, lo, lab_hi, lab_lo, w=118, h=17):
    """The floor-to-ceiling range as a filled band: one entity, two strictnesses, one hue."""
    top = max(hi) * 1.14
    X = lambda i: i / (len(years) - 1) * w
    Y = lambda v: v / top * h
    up = " ".join(f"({X(i):.2f},{Y(v):.2f})" for i, v in enumerate(hi))
    dn = " ".join(f"({X(i):.2f},{Y(v):.2f})" for i, v in reversed(list(enumerate(lo))))
    ticks = "".join(
        f"\\node[anchor=north,font=\\tiny,text={SOFT}] at ({X(years.index(y)):.2f},-1.4) {{{y}}};\n"
        for y in (2006, 2010, 2015, 2020, 2025) if y in years)
    grid = "".join(
        f"\\draw[line width=0.3pt,{SOFT}!25] (0,{Y(g):.2f}) -- ({w},{Y(g):.2f});\n"
        f"\\node[anchor=east,font=\\tiny,text={SOFT}] at (-1.2,{Y(g):.2f}) {{{g:.1f}\\%}};\n"
        for g in (0.5, 1.0))
    return f"""\\begin{{tikzpicture}}[x=1mm,y=1mm]
{grid}\\fill[{SE}!14] plot coordinates {{{up}}} -- plot coordinates {{{dn}}} -- cycle;
\\draw[line width=1.3pt,{SE}] plot coordinates {{{up}}};
\\draw[line width=1.3pt,{SE}!50] plot coordinates {{{dn}}};
\\fill[{SE}] ({w},{Y(hi[-1]):.2f}) circle (0.9);
\\fill[{SE}!50] ({w},{Y(lo[-1]):.2f}) circle (0.9);
{ticks}\\node[anchor=west,font=\\scriptsize\\bfseries,text={SE}] at ({w+2.5},{Y(hi[-1]):.2f})
  {{{lab_hi}}};
\\node[anchor=west,font=\\scriptsize,text={SE}!70] at ({w+2.5},{Y(lo[-1]):.2f})
  {{{lab_lo}}};
\\end{{tikzpicture}}"""


# ---- one drawing per data job, rather than the same bar pair four times ------------------
# The four questions are not four instances of the same measurement, and drawing them alike
# hid that. Exposure and adoption are shares of a population, so they get a 0-100 track that
# shows the share IS a minority. Adoption also has a time dimension (the EU was at 8% in 2023),
# which a single bar threw away, so its earlier value is drawn as a ghost tick. Demand is a
# share too but two orders smaller, so it gets its own scale with the ceiling stated. Wages is
# a gap between two groups, and the gap is the finding, so it is a dumbbell.

def _row(y, val, col, lab, track, w, bw=5.0, ghost=None, ghost_above=False):
    L = max(val / track * w, 0.8)
    s = (f"\\fill[{SOFT}!12,rounded corners=0.6pt] (0,{y}) rectangle ({w},{y+bw});\n"
         f"\\fill[{col},rounded corners=0.6pt] (0,{y}) rectangle ({L:.2f},{y+bw});\n"
         f"\\node[anchor=west,font=\\small\\bfseries,text=ink] at ({w+2.2},{y+bw/2:.2f}) "
         f"{{{val:g}\\%}};\n"
         f"\\node[anchor=east,font=\\tiny,text={SOFT}] at (-1.6,{y+bw/2:.2f}) {{{lab}}};\n")
    if ghost is not None:
        g = ghost / track * w
        # The tick carries no number. Labelling only the lower one was the asymmetry this card
        # had; labelling both means putting the upper label above its bar, which grows the card
        # past the page. The reading text names the wave the ticks mark, which is what the
        # reader needs, and two unlabelled ticks at least compare like with like.
        s += f"\\draw[line width=0.8pt,{SOFT}!70] ({g:.2f},{y-1.0}) -- ({g:.2f},{y+bw+0.4});\n"
    return s


def share_bars(a_lab, a_val, b_lab, b_val, w=44, track=100, ghost=None, ghost_a=None,
               note=None):
    """Two bars on one track. `ghost_a`/`ghost` are the previous wave's values, drawn as a tick.

    Both bars get a tick or neither: the adoption card used to mark only the international bar,
    so a reader saw the EU double and could not see whether Sweden was moving at all, which is
    the more interesting half of that comparison. Both ticks must be the SAME wave; marking
    Sweden's 2024 against the EU's 2023 would compare two different windows in one picture."""
    s = "\\begin{tikzpicture}[x=1mm,y=1mm]\n"
    s += _row(7.2, a_val, SE, a_lab, track, w, ghost=ghost_a, ghost_above=True)
    s += _row(0, b_val, INTL, b_lab, track, w, ghost=ghost)
    # The ghost tick already occupies the space under the lower bar, and the two collided.
    # The scale note is the one that yields: the 0-100 track is visually identical to the card
    # beside it, which states the convention.
    if note and ghost is None:
        s += (f"\\node[anchor=north west,font=\\tiny,text={SOFT}] at (0,-1.6) {{{note}}};\n")
    return s + "\\end{tikzpicture}"


def dumbbell(rows, w=44):
    """Two countries, one shared scale, the GAP within each as the mark.

    Sweden and the United States answer this question with opposite signs, so the marks CROSS:
    in Sweden the most-exposed third is the right-hand dot, in the United States it is the left.
    A fixed left-to-right reading of "most, then least" would therefore be wrong for one of the
    two rows, which is why the exposure group is carried by the dot's FILL (solid = most exposed,
    hollow = least) and not by its position. Fill also survives greyscale, which position-plus-
    colour would not.

    One scale for both rows, deliberately. Giving Sweden its own axis would blow +0.9 against
    -0.8 up to the width of the card and manufacture a Swedish gap out of rounding noise; on the
    shared scale the two Swedish dots sit almost on top of each other, which IS the finding.

    rows: [(country_label, colour, most_exposed, least_exposed), ...]
    """
    sign = lambda v: (f"+{v:g}" if v >= 0 else f"$-${abs(v):g}")
    vals = [v for r in rows for v in r[2:]]
    lo, hi = min(vals + [0]), max(vals)
    span = (hi - lo) * 1.06 or 1
    X = lambda v: (v - lo + (hi - lo) * 0.03) / span * w
    gap, y0 = 5.2, 0.0
    s = "\\begin{tikzpicture}[x=1mm,y=1mm]\n"
    for i, (lab, col, most, least) in enumerate(rows):
        y = y0 + (len(rows) - 1 - i) * gap
        xm, xl = X(most), X(least)
        s += (f"\\draw[line width=0.4pt,{SOFT}!25] (0,{y}) -- ({w},{y});\n"
              f"\\draw[line width=1.9pt,{col}!45] ({min(xm, xl):.2f},{y}) -- ({max(xm, xl):.2f},{y});\n"
              f"\\fill[white] ({xl:.2f},{y}) circle (1.35);\n"
              f"\\draw[line width=0.9pt,{col}] ({xl:.2f},{y}) circle (1.35);\n"
              f"\\fill[{col}] ({xm:.2f},{y}) circle (1.35);\n"
              f"\\node[anchor=east,font=\\tiny,text={SOFT}] at (-1.6,{y}) {{{lab}}};\n"
              f"\\node[anchor=west,font=\\scriptsize\\bfseries,text=ink] at ({w+2.0},{y}) "
              f"{{{sign(most)}\\%}};\n"
              f"\\node[anchor=west,font=\\scriptsize,text={SOFT}] at ({w+11.5},{y}) "
              f"{{{sign(least)}\\%}};\n")
    return s + "\\end{tikzpicture}"


def card(question, viz, reading, vintage, colw, grp="A", srclab=""):
    """A tinted card. tcolorbox rather than a tikz node: a node with `text width` that contains
    another tikzpicture does not measure it, so the bars escaped the card and every card grew
    to a different height. tcolorbox handles nested content and measures it.

    Height comes from `equal height group`, not a hand-set `height=`. A fixed height was tried
    first and is a trap: the two languages set the same four readings in different numbers of
    lines, so any value that fits English clips Swedish (or the reverse), and the overflow is
    silent, escaping *behind* the card below it rather than raising an error. The group makes
    both cards in a row as tall as the taller one's own content, so nothing can be clipped by
    construction. It costs a second LaTeX pass (heights go via the .aux), which tectonic runs
    on its own. Pass a different group per row, not one group for all four."""
    return (f"\\begin{{minipage}}[t]{{{colw}\\textwidth}}\n"
            f"\\begin{{tcolorbox}}[enhanced,arc=1.4mm,"
            f"colback={SOFT}!6,colframe={SOFT}!6,boxrule=0pt,left=3.4mm,right=3.4mm,"
            f"top=2.2mm,bottom=2.0mm,valign=top]\n"
            f"{{\\footnotesize\\bfseries\\textcolor{{ink}}{{{question}}}}}\n\n"
            f"\\vspace{{1.9mm}}\n\\hspace*{{11mm}}{viz}\n\n"
            f"\\vspace{{1.9mm}}\n{{\\scriptsize {reading}}}\n\n"
            f"\\vspace{{1mm}}\n{{\\tiny\\textcolor{{soft}}{{{srclab}}}{{{vintage}}}}}\n"
            f"\\end{{tcolorbox}}\\end{{minipage}}")


# ---- page two -----------------------------------------------------------------------------

def rank_bars(rows, key, w=23, n=6, lang="en"):
    """Ranked shares. One hue: these are all the same entity (Swedish occupations), so the
    ordering carries the message and a categorical palette would only add noise.

    Labels are shortened (scripts/labels.py). A sheet has no hover to fall back on, so the
    trade is real here in a way it is not on the site; it is made anyway, because the
    alternative on a 23mm bar column is a title that wraps across three lines and pushes the
    layout off its two pages. The full titles are on the site and in the CSV the footer names."""
    rows = rows[:n]
    top = max(r["share"] for r in rows) * 1.05
    bw, gap = 3.4, 1.5
    s = "\\begin{tikzpicture}[x=1mm,y=1mm]\n"
    for i, r in enumerate(reversed(rows)):
        y = i * (bw + gap)
        L = max(r["share"] / top * w, 0.5)
        s += (f"\\fill[{SE},rounded corners=0.5pt] (0,{y}) rectangle ({L:.2f},{y+bw});\n"
              f"\\node[anchor=west,font=\\scriptsize\\bfseries,text=ink] at ({L+1.4:.2f},{y+bw/2:.2f}) "
              f"{{{r['share']:.1f}\\%}};\n"
              f"\\node[anchor=east,font=\\tiny,text=ink] at (-1.4,{y+bw/2:.2f}) "
              f"{{{tex(shorten(str(r[key]), lang))}}};\n")
    return s + "\\end{tikzpicture}"


def zero_rows(rows, key, C, n=3, lang="en"):
    """The occupations that ask for AI in NONE of their advertisements. Deliberately NOT a
    chart: a bar of length zero communicates nothing, and the point is the advertisement
    volume sitting behind the zero."""
    out = []
    for r in rows[:n]:
        out.append(f"{{\\scriptsize\\bfseries\\textcolor{{ink}}{{0.0\\%}}}}~"
                   f"{{\\scriptsize {tex(shorten(str(r[key]), lang))}}}~"
                   f"{{\\tiny\\textcolor{{soft}}{{({r['ads']:,} {C['ads_word']})}}}}")
    return "\\\\[1.3mm]\n".join(out)


def barrier_bars(rows, namekey="name", w=20, n=6):
    """Sweden against the EU, same hue mapping as page one.

    namekey selects the label language. The Swedish sheet shipped with English bar labels
    ("Lack of relevant expertise") because this drew r["name"] unconditionally, so the swap is
    made here and a missing translation raises rather than falling back silently."""
    rows = rows[:n]
    missing = [r["name"] for r in rows if not r.get(namekey)]
    if missing:
        raise SystemExit("barriers: no " + namekey + " for " + "; ".join(missing))
    top = max(max(r["share"], r["eu"]) for r in rows) * 1.08
    bw, gap, grp = 2.5, 0.7, 3.4
    s = "\\begin{tikzpicture}[x=1mm,y=1mm]\n"
    for i, r in enumerate(reversed(rows)):
        y = i * (2 * bw + gap + grp)
        for j, (val, col) in enumerate(((r["eu"], INTL), (r["share"], SE))):
            yy = y + j * (bw + gap)
            L = max(val / top * w, 0.4)
            s += (f"\\fill[{col}] (0,{yy}) rectangle ({L:.2f},{yy+bw});\n"
                  f"\\node[anchor=west,font=\\tiny,text=ink] at ({L+1:.2f},{yy+bw/2:.2f}) "
                  f"{{{val:g}}};\n")
        s += (f"\\node[anchor=east,font=\\tiny,text=ink,align=right,text width=32mm] "
              f"at (-1.4,{y+bw+gap/2:.2f}) {{{tex(r[namekey])}}};\n")
    return s + "\\end{tikzpicture}"


def chips(items, n=8):
    return "  ".join(f"\\colorbox{{{SOFT}!10}}{{\\vphantom{{Ag}}{tex(i)}}}" for i in items[:n])


# Copy lives here, in both languages, so the layout below has no English baked into it.
# International first, Sweden in depth second: that is the site's own ordering principle
# ("International-first headline number each; Sweden is the depth cut inside the module"),
# and the sheet follows it rather than leading with the number we happen to own.
COPY = {
 "en": dict(
  title="AI and the labour market",
  kicker="AIEL Monitor · sheet generated {stamp}",
  standfirst_sub="What the evidence shows, internationally and for Sweden in depth",
  caveat=(r"\textbf{{This page describes; it does not explain.}} Everything here is measured, "
          r"but none of it shows that AI \emph{{caused}} what you are looking at. Other things "
          r"moved over the same years: interest rates, a pandemic, the ordinary business cycle. "
          r"\textbf{{Read the dates, not the sheet's date:}} the sheet is generated on demand, "
          r"the evidence is not, and every figure carries its own vintage."),
  # "four different answers" editorialised that they conflict. State the structure, not a
  # reading of it.
  four_hd="FOUR QUESTIONS, MEASURED SEPARATELY",
  legend_se="Sweden", legend_intl="international comparison",
  # Was "Could AI do parts of the job?", which imports the automation reading. Exposure is a
  # property of an occupation's tasks and is silent on whether AI substitutes or assists;
  # our own pages insist exposure is not displacement, so the question must not say it is.
  q_exposure="How exposed are jobs to AI?",
  q_demand="How often do employers ask for AI skills?",
  # "actually" implied a gap between claim and reality that we have not measured.
  q_adoption="How many firms use AI?",
  # "Has it shown up in pay?" presupposes an effect that ought to appear, which is a causal
  # claim on a descriptive sheet.
  q_wages="What has happened to pay?",
  r_exposure=("Jobs in the most AI-exposed quarter of occupations. Exposure describes "
              "applicability, not who loses work."),
  r_demand=("Advertisements asking for an AI skill: a small part of hiring. The Swedish "
            "series in the figure below is stricter and reads lower."),
  r_adoption=("Firms with 10 or more persons employed, 2025; the tick marks the 2024 wave. "
              "Smaller firms are not in this survey."),
  r_wages=("Real wage growth by exposure, most exposed in bold. No Swedish gap; the US "
           "gap runs the other way."),
  se_hd="SWEDEN IN DEPTH: HOW OFTEN DO JOB ADS ASK FOR AI?",
  se_sub="Every advertisement on the public job board",
  src_label="Source: ",
  se_src=f"JobTech / Platsbanken job ads (CC0), frozen {DEF_VERSION} term list, distinct advertisements",
  band_hi="mention an AI skill", band_lo="ask for it in the job itself",
  se_body=(r"A \textbf{{range}}, not a single number: the upper line counts an advertisement that "
           r"mentions an AI skill anywhere, the lower one only when the skill is asked of the "
           r"person being hired. Both rose steeply. The broader count went from {v0:.2f}\% of "
           r"advertisements in {y0} to {v1:.2f}\% in {y1}, about {rise:.0f} times as high, and the "
           r"{y1} range is \textbf{{{fl:.2f}\% to {ceiling}\%}}. Both lines rest on a term list and "
           r"cover only the AI demand that words reveal."),
  se_live=(r"Right now ({asof}): of the {n} most recent advertisements, {names}\% mention an AI "
           r"skill and {floor}\% ask for one in the job itself. This is the only figure on the "
           r"sheet that moves daily."),
  cap_q="How capable are AI systems?", cap_cond="at 50\\% success",
  # Taken from the copy table, NOT from monitor.yaml: the yaml is English-only, so pulling
  # cap["lab"] straight through left a full English sentence in the middle of the Swedish
  # sheet. Source lines below it stay in English on purpose, being citations.
  cap_lab=("the longest human-expert tasks frontier AI agents complete; the length has been "
           "doubling every 4--6 months"),
  cap_tail=("This is the technology the four questions are read against, not a fifth question "
            "about the labour market."),
  footnote=(r"\textbf{{Before you quote this.}} The Swedish series counts what employers "
            r"\emph{{write down when hiring}}: not jobs, and not firms using AI, two of the panels "
            r"above. Not all hiring is advertised. A rising line means only that employers ask "
            r"for AI skills more often."),
  colophon=(r"AI-Econ Lab, Örebro University and the Ratio Institute. Public data throughout; every "
            r"figure is reproducible from the source beside it. Method: "
            r"\href{{https://ai-econlab.com/monitor/methods/}}{{ai-econlab.com/monitor/methods}}."),
  lab_se="Sweden", lab_eu="36-country mean", lab_eu2="EU27", lab_med="22-country median",
  lab_us="US",
  lab_least="Least exposed", lab_most="Most exposed",
  of_all_jobs="bar spans all jobs", of_all_ads="bar spans 0--4\\% of ads",
  of_all_firms="bar spans all surveyed firms",
  p2_hd="WHERE THE DEMAND ACTUALLY SITS",
  p2_sub="Swedish occupations, 2025, ranked by the share of their advertisements asking for AI",
  p2_top="Asks most often",
  p2_zero="And in none of these",
  p2_zero_note=("These are among the largest occupations on the board. The demand is real and it "
                "is concentrated: most of the labour market is not being asked for AI at all."),
  ads_word="ads",
  words_hd="IN THE EMPLOYERS' OWN WORDS",
  words_sub="Advertisement headlines, as written",
  words_top="Most common:",
  words_new="New titles appearing",
  words_cooled="Titles that stopped clearing the bar",
  words_note=("One entry is a measurement artefact worth naming: medical secretary (medicinsk "
              "sekreterare) appears because those advertisements mention speech-recognition "
              "software, which our classifier judges to be a tool the job uses rather than an "
              "AI skill it asks for."),
  bar_hd="OBSTACLES FIRMS NAME",
  bar_sub="Per cent of all firms with 10+ persons employed, 2025",
  bar_note=("Shares are of every firm in the survey, not of non-adopters, so they do not sum "
            "to anything. "
            "Sweden is below the EU on every barrier, which is partly mechanical: the more "
            "firms already use AI, the fewer are left to be asked why they do not. Not "
            "comparable with 2021: Eurostat flags a break in the Swedish series."),
  gaps_hd="WHAT THIS CANNOT SEE",
  gaps=[("No task-level data.", "We see what employers write in advertisements, not how work is "
         "actually done, nor how tasks and responsibilities shift inside a job that keeps its name."),
        ("Not all hiring is advertised.", "This is the advertised margin. Occupations that hire "
         "through networks or internal moves are under-represented, and that varies by sector."),
        ("One job board.", "Platsbanken is large and stable but it is not the whole market, and "
         "its reach has fallen somewhat relative to surveyed vacancies since 2006."),
        ("Validated on one year.", "Precision and recall are measured on 2024 advertisements. "
         "An early-period check covering 2006 to 2013 is drawn and not yet done."),
        ("Exposure is not displacement.", "The exposure measure on page one describes tasks AI "
         "could affect. It is not a prediction that anyone loses work.")],
  p2_kicker="page 2 of 2",
  pdftitle="AI and the labour market — AIEL Monitor one-pager",
  a11y=("Hard to read? Every figure is on the web page as selectable text at any zoom, with "
        "the numbers as CSV: ai-econlab.com/monitor."),
 ),
 "sv": dict(
  title="AI och arbetsmarknaden",
  kicker="AIEL Monitor · blad genererat {stamp}",
  standfirst_sub="Vad underlaget visar, internationellt och för Sverige på djupet",
  caveat=(r"\textbf{{Den här sidan beskriver, den förklarar inte.}} Allt här är uppmätt, men "
          r"ingenting visar att AI \emph{{orsakat}} det du ser. Annat har rört sig under samma år: "
          r"räntor, en pandemi och en vanlig konjunktur. \textbf{{Läs datumen, inte bladets "
          r"datum:}} bladet skapas när du hämtar det, men underlaget gör det inte, och varje "
          r"siffra bär sitt eget årtal."),
  four_hd="FYRA FRÅGOR, MÄTTA VAR FÖR SIG",
  legend_se="Sverige", legend_intl="internationell jämförelse",
  q_exposure="Hur exponerade är jobben för AI?",
  q_demand="Hur ofta efterfrågar arbetsgivare AI-kompetens?",
  q_adoption="Hur många företag använder AI?",
  q_wages="Vad har hänt med lönerna?",
  r_exposure=("Jobb i den mest AI-exponerade fjärdedelen av yrkena. Exponering beskriver "
              "tillämpbarhet, inte vem som förlorar arbete."),
  r_demand=("Annonser som kräver AI-kompetens: en liten del av rekryteringen. Serien "
            "i figuren nedan är striktare och ligger lägre."),
  r_adoption=("Företag med minst 10 sysselsatta, 2025; strecket visar 2024. Mindre företag "
              "ingår inte i undersökningen."),
  r_wages=("Reallöner efter exponering, mest exponerade i fetstil. Inget svenskt gap; det "
           "amerikanska går åt andra hållet."),
  se_hd="SVERIGE PÅ DJUPET: HUR OFTA EFTERFRÅGAR ANNONSERNA AI?",
  se_sub="Baserat på samtliga annonser på Platsbanken",
  src_label="Källa: ",
  se_src=f"JobTech / Platsbanken (CC0), fryst termlista {DEF_VERSION}, distinkta annonser",
  band_hi="nämner en AI-färdighet", band_lo="efterfrågar den i själva jobbet",
  se_body=(r"Ett \textbf{{intervall}}, inte en enda siffra: den övre linjen räknar en annons som "
           r"nämner en AI-färdighet någonstans, den nedre bara när färdigheten efterfrågas av den "
           r"som ska anställas. Båda har stigit kraftigt. Den bredare räkningen gick från "
           r"{v0:.2f}\% av annonserna {y0} till {v1:.2f}\% {y1}, ungefär {rise:.0f} gånger så mycket, "
           r"och intervallet för {y1} är \textbf{{{fl:.2f}\% till {ceiling}\%}}. Båda linjerna vilar "
           r"på en termlista och rymmer bara den AI-efterfrågan som orden visar."),
  se_live=(r"Just nu ({asof}): av de {n} senaste annonserna nämner {names}\% en AI-färdighet och "
           r"{floor}\% efterfrågar den i själva jobbet. Det är den enda siffran på bladet som "
           r"ändras dagligen."),
  cap_q="Hur kapabla är AI-systemen?", cap_cond="vid 50\\% träffsäkerhet",
  cap_lab=("de längsta expertuppgifter som AI-agenter klarar; längden har fördubblats var "
           "fjärde till sjätte månad"),
  cap_tail=("Det här är tekniken som de fyra frågorna läses mot, inte en femte fråga om "
            "arbetsmarknaden."),
  footnote=(r"\textbf{{Innan du citerar det här.}} Den svenska serien räknar vad arbetsgivare "
            r"\emph{{skriver ned när de rekryterar}}: inte jobb, och inte företag som använder AI, "
            r"två av panelerna ovan. All rekrytering annonseras inte. En stigande linje betyder "
            r"bara att arbetsgivare efterfrågar AI-kompetens oftare än förr."),
  colophon=(r"AI-Econ Lab, Örebro universitet och Ratio. Öppna data genomgående; varje siffra går "
            r"att återskapa från källan intill. Metod: \href{{https://ai-econlab.com/monitor/methods/}}{{ai-econlab.com/monitor/methods}}."),
  lab_se="Sverige", lab_eu="36-landssnitt", lab_eu2="EU27", lab_med="medianland av 22",
  lab_us="USA",
  lab_least="Minst exponerade", lab_most="Mest exponerade",
  of_all_jobs="stapeln rymmer alla jobb", of_all_ads="stapeln rymmer 0--4\\% av annonserna",
  of_all_firms="stapeln rymmer alla undersökta företag",
  p2_hd="VAR EFTERFRÅGAN FAKTISKT FINNS",
  p2_sub="Svenska yrken 2025, rangordnade efter andelen annonser som efterfrågar AI",
  p2_top="Efterfrågar oftast",
  p2_zero="Och i ingen av dessa",
  p2_zero_note=("Det här är några av de största yrkena på Platsbanken. Efterfrågan är verklig och "
                "koncentrerad: största delen av arbetsmarknaden får inte frågan alls."),
  ads_word="annonser",
  words_hd="MED ARBETSGIVARNAS EGNA ORD",
  words_sub="Annonsrubriker, så som de skrevs",
  words_top="Vanligast:",
  words_new="Nya titlar som dyker upp",
  words_cooled="Titlar som inte längre når över tröskeln",
  words_note=("En post är en mätartefakt värd att nämna: medicinsk sekreterare dyker upp för att "
              "de annonserna nämner taligenkänningsprogram, vilket vår klassificerare bedömer som "
              "ett verktyg jobbet använder snarare än en AI-färdighet det efterfrågar."),
  bar_hd="HINDER SOM FÖRETAGEN ANGER",
  bar_sub="Procent av alla företag med minst 10 sysselsatta, 2025",
  bar_note=("Andelarna avser alla företag i undersökningen, inte bara de som avstått, så de "
            "summerar inte till något. Sverige ligger under EU på varje hinder, vilket delvis är mekaniskt: ju "
            "fler som redan använder AI, desto färre återstår att fråga varför de inte gör "
            "det. Inte jämförbart med 2021: Eurostat flaggar ett serieavbrott."),
  gaps_hd="VAD DET HÄR INTE KAN SE",
  gaps=[("Inga data om arbetsuppgifter.", "Vi ser vad arbetsgivare skriver i annonser, inte hur "
         "arbetet faktiskt utförs, och inte hur uppgifter och ansvar förskjuts inom ett yrke som "
         "behåller sitt namn."),
        ("All rekrytering annonseras inte.", "Det här är den annonserade marginalen. Yrken som "
         "rekryterar via nätverk eller internt är underrepresenterade, och det varierar mellan "
         "branscher."),
        ("Endast en annonskälla.", "Platsbanken är stor och stabil men inte hela marknaden, och dess "
         "räckvidd har minskat något i förhållande till mätta vakanser sedan 2006."),
        ("Validerat på ett år.", "Precision och täckning är uppmätta på annonser från 2024. En "
         "kontroll av 2006 till 2013 är uttagen men ännu inte gjord."),
        ("Exponering är inte ersättning.", "Exponeringsmåttet på sidan ett beskriver uppgifter "
         "som AI kan påverka. Det är ingen förutsägelse om att någon förlorar arbete.")],
  p2_kicker="sida 2 av 2",
  pdftitle="AI och arbetsmarknaden — AIEL Monitor, ett blad",
  a11y=("Svårt att läsa? Varje siffra finns på webbsidan som markerbar text i valfri "
        "förstoring, med data som CSV: ai-econlab.com/monitor."),
 ),
}

SV_MONTH = {1:"januari",2:"februari",3:"mars",4:"april",5:"maj",6:"juni",7:"juli",
            8:"augusti",9:"september",10:"oktober",11:"november",12:"december"}


def main():
    landscape = "--landscape" in sys.argv
    lang = "sv" if "--sv" in sys.argv else "en"
    big = "--large" in sys.argv
    C = COPY[lang]
    m = yaml.safe_load((DATA / "monitor.yaml").read_text(encoding="utf-8"))
    today = date.today()
    stamp = (f"{today.day} {SV_MONTH[today.month]} {today.year}" if lang == "sv"
             else today.strftime("%-d %B %Y"))
    ov = {o["k"]: o for o in m["overview"]}
    tr = m["trend"]
    # Same precedence as build.py: monitor.yaml carries the fallback and the framing, and the
    # generated file overrides the figures when it exists. Without this the one-pager would
    # keep printing the hand-placed fallback while the website showed the refreshed window.
    lw = dict(m["livewindow"])
    lw_gen = DATA / "livewindow.yaml"
    if lw_gen.exists():
        lw.update(yaml.safe_load(lw_gen.read_text(encoding="utf-8")) or {})
    occ = yaml.safe_load((DATA / "occupations.yaml").read_text(encoding="utf-8"))
    bar = yaml.safe_load((DATA / "barriers.yaml").read_text(encoding="utf-8"))
    ado = yaml.safe_load((DATA / "cross_country_adoption.yaml").read_text(encoding="utf-8"))
    wag = yaml.safe_load((DATA / "wages.yaml").read_text(encoding="utf-8"))
    ttl = m["titles"]
    namekey = "name_sv" if lang == "sv" else "name"

    exp_eu, = grab(r"^(\d+(?:\.\d+)?)", plain(ov["Exposure"]["num"]), "European exposure")
    exp_se, = grab(r"Sweden (\d+(?:\.\d+)?)%", ov["Exposure"]["lab"], "Swedish exposure")
    dem_med, = grab(r"^(\d+(?:\.\d+)?)", plain(ov["Demand"]["num"]), "median AI-ad share")
    dem_se, = grab(r"Sweden (\d+(?:\.\d+)?)%", ov["Demand"]["lab"], "Swedish AI-ad share")
    ado_eu, = grab(r"^(\d+(?:\.\d+)?)", plain(ov["Adoption"]["num"]), "EU adoption")
    ado_se, = grab(r"Sweden (\d+(?:\.\d+)?)%", ov["Adoption"]["lab"], "Swedish adoption")
    # Previous wave for BOTH bars, read from the cross-country file so the two ticks are the
    # same year by construction. The overview prose still quotes 2023 for the EU, which is a
    # different (and older) window; that is why this no longer parses it.
    adm = ado["meta"]
    ado_prev = adm["eu_avg_prev"]
    ado_prev_se = next(r["prev"] for r in ado["countries"] if r.get("is_se"))
    if ado_prev is None or ado_prev_se is None:
        raise SystemExit("build_onepager: cross_country_adoption.yaml has no previous wave for "
                         "the EU or for Sweden, so the adoption card cannot mark both bars. "
                         "Rerun scripts/refresh_cross_country.py.")
    out_hi, out_lo = grab(r"\((\d+(?:\.\d+)?)% against (\d+(?:\.\d+)?)%\)",
                          ov["Outcomes"]["lab"], "US real wage growth by exposure")
    # The Swedish pair is parsed out of wages.yaml's own headline for the same reason every
    # other figure on this sheet is parsed rather than typed: a second copy drifts.
    se_hi, se_lo = grab(r"most exposed ([+-]?\d+(?:\.\d+)?) per cent, middle [+-]?[\d.]+, "
                        r"least ([+-]?\d+(?:\.\d+)?)",
                        wag["headline"], "Swedish real wage growth by exposure")
    # The corrected ceiling is parsed out of the caveat that publishes it, for the same reason
    # every other figure here is parsed: a second copy drifts. It drifted. This read used to
    # look in m["notes"], a key monitor.yaml has never had, so it always fell through to a
    # typed "1.36" — the PRE-correction ceiling, still being printed after the four-period
    # correction moved the published figure to 1.27 on 17 Aug 2026. No silent fallback now.
    ceiling = next((h.group(1) for note in m["caveats"]
                    for h in [re.search(r"corrected (?:\d{4} )?ceiling at <b>([\d.]+)%",
                                        note)] if h), None)
    if ceiling is None:
        raise SystemExit("build_onepager: no caveat in monitor.yaml states the corrected "
                         "ceiling ('corrected [YYYY] ceiling at <b>N%'). The sheet will not print a "
                         "typed-in ceiling; fix the caveat or the pattern.")

    # se_src is copy so the Swedish sheet can say it in Swedish, but the English one must stay
    # the data's own wording; assert rather than let the two drift apart silently.
    if COPY["en"]["se_src"] != occ["meta"]["source"]:
        raise SystemExit("build_onepager: COPY['en']['se_src'] no longer matches "
                         "occupations.yaml meta.source. Update the copy, not the data.")
    colw = "0.31" if landscape else "0.485"
    cards = [
        card(C["q_exposure"],
             share_bars(C["lab_se"], exp_se, C["lab_eu"], exp_eu, note=C["of_all_jobs"]),
             C["r_exposure"], tex(ov["Exposure"]["foot"]), colw, "A", srclab=C["src_label"]),
        card(C["q_demand"],
             share_bars(C["lab_se"], dem_se, C["lab_med"], dem_med, track=4, note=C["of_all_ads"]),
             C["r_demand"], tex(ov["Demand"]["foot"]), colw, "A", srclab=C["src_label"]),
        card(C["q_adoption"],
             share_bars(C["lab_se"], ado_se, C["lab_eu2"], ado_eu, ghost=ado_prev,
                        ghost_a=ado_prev_se,
                        note=C["of_all_firms"]),
             C["r_adoption"], tex(ov["Adoption"]["foot"]), colw, "B", srclab=C["src_label"]),
        card(C["q_wages"], dumbbell([(C["lab_se"], SE, se_hi, se_lo),
                                    (C["lab_us"], INTL, out_hi, out_lo)]),
             C["r_wages"], tex(ov["Outcomes"]["foot"]), colw, "B", srclab=C["src_label"]),
    ]
    grid = (cards[0] + "\\hfill" + cards[1] + "\\\\[2.6mm]\n"
            + cards[2] + "\\hfill" + cards[3])

    cap = ov["Capability"]
    hero = range_band(tr["years"], tr["values"], tr["floor_values"], C["band_hi"], C["band_lo"])
    se_body = C["se_body"].format(v0=tr["values"][0], y0=tr["years"][0],
                                  v1=tr["values"][-2], y1=tr["years"][-2],
                                  rise=tr["values"][-2] / tr["values"][0],
                                  fl=tr["floor_values"][-2], ceiling=ceiling)
    # Same source and same formatting as the website's live-window block. `n` used to be the
    # string "32,022" in monitor.yaml and is now an integer in the generated file, so the
    # thousands separator is applied here rather than being typed into the data; and the two
    # percentages are printed to the same 2 dp as the page, which they previously were only
    # because someone had typed them that way.
    se_live = C["se_live"].format(asof=tex(str(lw["asof"])), n=f"{int(lw['n']):,}",
                                  names=f"{float(lw['names_pct']):.2f}",
                                  floor=f"{float(lw['floor_pct']):.2f}")
    gaps = "\\\\[1.6mm]\n".join(
        f"{{\\scriptsize\\bfseries\\textcolor{{ink}}{{{tex(h)}}}}} "
        f"{{\\scriptsize\\textcolor{{soft}}{{{tex(b)}}}}}" for h, b in C["gaps"])
    page2 = rf"""
\newpage
{{\large\bfseries\textcolor{{ink}}{{{C['title']}}}}}\hfill
{{\scriptsize\textcolor{{soft}}{{{C['p2_kicker']} · \textcolor{{{SE}}}{{\textbf{{ai-econlab.com}}}}}}}}\\[1.4mm]
\textcolor{{ink}}{{\rule{{\textwidth}}{{1.4pt}}}}\\[2.8mm]

{{\normalsize\bfseries\textcolor{{ink}}{{{C['p2_hd']}}}}}\hfill
{{\scriptsize\textcolor{{soft}}{{{C['p2_sub']}}}}}\\[3mm]
\noindent\begin{{minipage}}[t]{{0.50\textwidth}}
  {{\footnotesize\bfseries\textcolor{{ink}}{{{C['p2_top']}}}}}\\[3mm]
  \hspace*{{26mm}}{rank_bars(occ['top'], namekey, lang=lang)}
\end{{minipage}}\hfill
\begin{{minipage}}[t]{{0.44\textwidth}}
  {{\footnotesize\bfseries\textcolor{{ink}}{{{C['p2_zero']}}}}}\\[3mm]
  {zero_rows(occ['zero'], namekey, C, lang=lang)}\\[3mm]
  {{\scriptsize\textcolor{{soft}}{{{C['p2_zero_note']}}}}}
\end{{minipage}}\\[3.5mm]
{{\tiny\textcolor{{soft}}{{{C['se_src']}}}}}\\[3mm]

\textcolor{{hair}}{{\rule{{\textwidth}}{{0.6pt}}}}\\[4mm]
\noindent\begin{{minipage}}[t]{{0.47\textwidth}}
  {{\normalsize\bfseries\textcolor{{ink}}{{{C['bar_hd']}}}}}\\[1mm]
  {{\scriptsize\textcolor{{soft}}{{{C['bar_sub']}}}}}\\[1.4mm]
  {{\tiny\textcolor{{soft}}{{\textcolor{{{SE}}}{{\rule{{2mm}}{{2mm}}}}~{C['legend_se']} \quad
  \textcolor{{{INTL}}}{{\rule{{2mm}}{{2mm}}}}~EU}}}}\\[3mm]
  \hspace*{{33mm}}{barrier_bars(bar['rows'], 'name_sv' if lang == 'sv' else 'name')}\\[3.4mm]
  {{\scriptsize\textcolor{{soft}}{{{C['bar_note']}}}}}
\end{{minipage}}\hfill
\begin{{minipage}}[t]{{0.49\textwidth}}
  {{\normalsize\bfseries\textcolor{{ink}}{{{C['words_hd']}}}}}\\[1mm]
  {{\scriptsize\textcolor{{soft}}{{{C['words_sub']}}}}}\\[3.4mm]
  {{\scriptsize\bfseries\textcolor{{ink}}{{{C['words_top']}}}}}
  {{\scriptsize\bfseries\textcolor{{ink}}{{{tex(ttl['top'][0]['year'])}}}}}
  {{\scriptsize {tex(' · '.join(ttl['top'][0]['items']))}}}\\[2.6mm]
  {{\scriptsize\bfseries\textcolor{{ink}}{{{C['words_new']}}}}}\\[1.6mm]
  {chips(ttl['newcomers']['items'], 6)}\\[2.6mm]
  {{\scriptsize\bfseries\textcolor{{ink}}{{{C['words_cooled']}}}}}\\[1.6mm]
  {chips(ttl['cooled']['items'], 5)}\\[3mm]
  {{\scriptsize\textcolor{{soft}}{{{C['words_note']}}}}}
\end{{minipage}}\\[3mm]

\textcolor{{hair}}{{\rule{{\textwidth}}{{0.6pt}}}}\\[2.4mm]
{{\normalsize\bfseries\textcolor{{ink}}{{{C['gaps_hd']}}}}}\\[2.2mm]
{gaps}\\[2mm]
{{\scriptsize\textcolor{{soft}}{{{C['a11y']} \quad {C['colophon']}}}}}
"""

    geom = "a4paper,landscape,margin=10mm" if landscape else "a4paper,margin=10mm"
    base = "12pt" if big else "11pt"

    doc = rf"""
\documentclass[{base}]{{article}}
\usepackage{{fontspec}}
\usepackage[{geom}]{{geometry}}
\usepackage{{xcolor}}
\usepackage{{tikz}}
\usetikzlibrary{{calc}}
\usepackage[most]{{tcolorbox}}
\usepackage[colorlinks=true,urlcolor=link,linkcolor=link,
            pdftitle={{{C['pdftitle']}}},pdfauthor={{AI-Econ Lab}},
            pdflang={{{'sv-SE' if lang == 'sv' else 'en-GB'}}},
            pdfsubject={{{C['standfirst_sub']}}}]{{hyperref}}

% Not the LaTeX default: a serif academic face was signalling "working paper" on a sheet meant
% for a student or a journalist, and a humanist sans is also the more legible choice at the
% small sizes the vintages need.
%
% That requirement used to be met by \setmainfont{{Avenir Next}}, which is a macOS SYSTEM font,
% so the sheet could only ever be typeset on one laptop. Nothing said so: build.py caught the
% failure, kept the committed PDF and carried on, and the guard in build-check.yml that was
% meant to catch exactly that tested `find -newermt '-30 minutes'` against files a fresh
% checkout had just stamped, so it could not fail. Meanwhile the sheet prints live-window
% figures in its body text -- "of the 33,066 most recent advertisements, 1.32%% mention an AI
% skill" -- and those move DAILY. Seven of the nine live-window refreshes before 24 Aug 2026
% left both PDFs untouched, so the public download disagreed with the page above its own link
% on most days of the week.
%
% Lato comes from the TeX Live bundle tectonic fetches for itself, so the sheet now typesets
% anywhere and regenerates with every refresh. It is SIL OFL, so nothing is redistributed
% here that may not be. The website never used Avenir either -- its --sans is the reader's
% own system font -- so nothing shared with the site changed.
\usepackage[default]{{lato}}

\definecolor{{ink}}{{HTML}}{{{INK_HEX}}}
\definecolor{{soft}}{{HTML}}{{{SOFT_HEX}}}
\definecolor{{link}}{{HTML}}{{{SE_HEX}}}
\definecolor{{{SE}}}{{HTML}}{{{SE_HEX}}}
\definecolor{{{INTL}}}{{HTML}}{{{INTL_HEX}}}
\definecolor{{hair}}{{HTML}}{{D9DCE1}}
\pagestyle{{empty}}\setlength{{\parindent}}{{0pt}}

\begin{{document}}

{{\LARGE\bfseries\textcolor{{ink}}{{{C['title']}}}}}\hfill
\raisebox{{2mm}}{{\parbox{{64mm}}{{\raggedleft
  {{\footnotesize\bfseries\textcolor{{{SE}}}{{ai-econlab.com}}}}\\[0.4mm]
  {{\scriptsize\textcolor{{soft}}{{{C['kicker'].format(stamp=stamp)}}}}}}}}}\\[0.6mm]
{{\normalsize\textcolor{{soft}}{{{C['standfirst_sub']}}}}}\\[2mm]
\textcolor{{ink}}{{\rule{{\textwidth}}{{1.4pt}}}}\\[2.2mm]

{{\scriptsize\textcolor{{soft}}{{{C['caveat']}}}}}\\[2mm]

{{\normalsize\bfseries\textcolor{{ink}}{{{C['four_hd']}}}}}\hfill
{{\scriptsize\textcolor{{soft}}{{\textcolor{{{SE}}}{{\rule{{2.2mm}}{{2.2mm}}}}~{C['legend_se']}
\quad \textcolor{{{INTL}}}{{\rule{{2.2mm}}{{2.2mm}}}}~{C['legend_intl']}}}}}\\[2.8mm]
{grid}\\[1.6mm]

{{\normalsize\bfseries\textcolor{{ink}}{{{C['se_hd']}}}}}\hfill
{{\scriptsize\textcolor{{soft}}{{{C['se_sub']}}}}}\\[2.2mm]
\hspace*{{9mm}}{hero}\\[2mm]
{{\scriptsize {se_body}}}\\[1.6mm]
{{\scriptsize\textcolor{{soft}}{{{se_live}}}}}\\[1.2mm]
{{\tiny\textcolor{{soft}}{{{C['se_src']}}}}}\\[2.4mm]

\textcolor{{hair}}{{\rule{{\textwidth}}{{0.6pt}}}}\\[1.8mm]
\noindent\begin{{minipage}}[c]{{0.32\textwidth}}
  {{\footnotesize\bfseries\textcolor{{ink}}{{{C['cap_q']}}}}}\\[1.4mm]
  {{\LARGE\bfseries\textcolor{{ink}}{{{tex(cap['num'])}}}}}\\[0.4mm]
  {{\scriptsize\textcolor{{soft}}{{{C['cap_cond']}}}}}
\end{{minipage}}%
\begin{{minipage}}[c]{{0.66\textwidth}}\raggedright
  {{\scriptsize {C['cap_lab']}. {C['cap_tail']}}}\\[0.8mm]
  {{\scriptsize\textcolor{{soft}}{{{tex(cap['foot'])}}}}}
\end{{minipage}}\\[2mm]

\textcolor{{hair}}{{\rule{{\textwidth}}{{0.6pt}}}}\\[2mm]
{{\scriptsize\textcolor{{soft}}{{{C['footnote']}}}}}
{page2}
\end{{document}}
"""
    suffix = {"en": "", "sv": "-sv"}[lang] + ("-large" if big else "")
    out = OUT.with_name(f"aiel-monitor-onepager{suffix}.pdf")
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "onepager.tex"
        src.write_text(doc, encoding="utf-8")
        if os.environ.get("AIEL_DUMP_TEX"):   # debugging aid: keep the generated source
            Path(os.environ["AIEL_DUMP_TEX"]).with_suffix(f".{lang}.tex").write_text(doc, "utf-8")
        if not TECTONIC:
            raise SystemExit(
                "build_onepager: no tectonic on PATH and none at the usual locations, so the "
                "sheet cannot be typeset. Install it, or set $TECTONIC. This is a MISSING "
                "TOOL, not a reason to ship yesterday's PDF.")
        r = subprocess.run([TECTONIC, "--outdir", td, str(src)], capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write((r.stdout + r.stderr)[-3500:])
            raise SystemExit("tectonic failed")
        # The sheet is a TWO-page sheet and its whole promise is that it fits. Page one holds
        # the four questions, the Swedish series and the capability anchor; page two holds the
        # occupations, the barriers and the vocabulary. A third page means something overflowed,
        # which is silent in LaTeX and easy to miss when only one language is rebuilt. Fail here
        # instead of shipping it: the two languages set the same copy in different numbers of
        # lines, so a Swedish-only overflow is the normal way this breaks.
        pages = int(re.search(r"^Pages:\s+(\d+)", subprocess.run(
            ["pdfinfo", str(Path(td) / "onepager.pdf")], capture_output=True, text=True
        ).stdout, re.M).group(1))
        if pages != 2 and not (big or landscape):
            raise SystemExit(
                f"build_onepager: {lang} came out at {pages} pages, not 2. Something overflowed.\n"
                f"  Find it with:  pdftotext -f 3 -l 3 -layout <pdf> -\n"
                f"  Then shorten that copy, or take the millimetres out of the page-one gaps.")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(td) / "onepager.pdf", out)
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size/1024:.0f} kB, {lang}, "
          f"{pages} pages, {'landscape' if landscape else 'portrait'}"
          f"{', large print' if big else ''}, {stamp})")


if __name__ == "__main__":
    main()
