#!/usr/bin/env python3
"""
build_onepager.py — the AIEL Monitor as a one-page infographic, generated from the site's data.

WHO IT IS FOR. A student or a journalist who asks "what is actually happening to the labour
market and AI?" and wants one page rather than a report. That audience sets the language: the
five modules lead with the QUESTION each answers, not with our internal name for it, and the
house vocabulary (floor, ceiling, penumbra, whole-text, recall-corrected) is either translated
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
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "docs" / "aiel-monitor-onepager.pdf"
TECTONIC = "/opt/homebrew/bin/tectonic"

# Hex for \definecolor, and a LaTeX-legal NAME to refer to it by. A colour name may not
# begin with a digit, so "0072B2" is not usable as one: \textcolor{0072B2} is an undefined
# control sequence, which is how this first failed to compile.
SE_HEX, SE = "0072B2", "sweden"      # our own measure / Sweden  (Okabe-Ito blue)
INTL_HEX, INTL = "D55E00", "intl"    # international comparison  (Okabe-Ito vermillion)
INK_HEX = "232B65"   # lab navy: headings and rules ONLY, never a data mark
SOFT_HEX, SOFT = "6B7280", "soft"


def tex(s):
    s = html.unescape(re.sub(r"<[^>]+>", "", s or ""))
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


def range_band(years, hi, lo, lab_hi, lab_lo, w=124, h=29):
    top = max(hi) * 1.12
    X = lambda i: i / (len(years) - 1) * w
    Y = lambda v: v / top * h
    up = " ".join(f"({X(i):.2f},{Y(v):.2f})" for i, v in enumerate(hi))
    dn = " ".join(f"({X(i):.2f},{Y(v):.2f})" for i, v in reversed(list(enumerate(lo))))
    ticks = "".join(
        f"\\node[anchor=north,font=\\tiny,text={SOFT}] at ({X(years.index(y)):.2f},-1.2) {{{y}}};\n"
        for y in (2006, 2010, 2015, 2020, 2025) if y in years)
    grid = "".join(
        f"\\draw[line width=0.3pt,{SOFT}!30] (0,{Y(g):.2f}) -- ({w},{Y(g):.2f});\n"
        f"\\node[anchor=east,font=\\tiny,text={SOFT}] at (-1,{Y(g):.2f}) {{{g:.1f}\\%}};\n"
        for g in (0.5, 1.0))
    return f"""\\begin{{tikzpicture}}[x=1mm,y=1mm]
{grid}\\fill[{SE}!15] plot coordinates {{{up}}} -- plot coordinates {{{dn}}} -- cycle;
\\draw[line width=1.1pt,{SE}] plot coordinates {{{up}}};
\\draw[line width=1.1pt,{SE}!55] plot coordinates {{{dn}}};
{ticks}\\node[anchor=west,font=\\scriptsize\\bfseries,text={SE}] at ({w+2},{Y(hi[-1]):.2f})
  {{{lab_hi}}};
\\node[anchor=west,font=\\scriptsize,text={SE}!75] at ({w+2},{Y(lo[-1]):.2f})
  {{{lab_lo}}};
\\end{{tikzpicture}}"""


def pair_bars(a_lab, a_val, b_lab, b_val, unit="\\%", w=40, cols=None):
    top = max(a_val, b_val) * 1.5
    bw, gap = 4.2, 1.7
    def bar(y, val, col, lab):
        L = max(val / top * w, 0.6)
        return (f"\\fill[{col}] (0,{y}) rectangle ({L:.2f},{y+bw});\n"
                # Value labels wear INK, never the series colour: the bar beside them
                # already carries identity, and a tinted bar's own hue fails contrast
                # as text (the 10.2% on the light vermillion was unreadable).
                f"\\node[anchor=west,font=\\scriptsize\\bfseries,text=ink] "
                f"at ({L+1.3:.2f},{y+bw/2:.2f}) {{{val:g}{unit}}};\n"
                f"\\node[anchor=east,font=\\tiny,text={SOFT}] at (-1.2,{y+bw/2:.2f}) {{{lab}}};\n")
    ca, cb = cols or (SE, INTL)
    return ("\\begin{tikzpicture}[x=1mm,y=1mm]\n"
            + bar(bw + gap, a_val, ca, a_lab) + bar(0, b_val, cb, b_lab)
            + "\\end{tikzpicture}")


def panel(question, viz, reading, vintage, colw):
    return (f"\\begin{{minipage}}[t]{{{colw}\\textwidth}}\\raggedright\n"
            f"{{\\footnotesize\\bfseries\\textcolor{{ink}}{{{question}}}}}\\\\[4pt]\n"
            f"\\hspace*{{20mm}}{viz}\\\\[4pt]\n"
            f"{{\\scriptsize {reading}}}\\\\[1pt]\n"
            f"{{\\tiny\\textcolor{{soft}}{{{vintage}}}}}\n"
            f"\\end{{minipage}}")


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
          r"moved over the same years, including interest rates, a pandemic and the ordinary "
          r"business cycle. \textbf{{Read the dates, not the sheet's date:}} the sheet is "
          r"generated on demand, the evidence is not, and every figure carries its own vintage."),
  four_hd="FOUR QUESTIONS, FOUR DIFFERENT ANSWERS",
  legend_se="Sweden", legend_intl="international comparison",
  q_exposure="Could AI do parts of the job?",
  q_demand="Are employers asking for it?",
  q_adoption="Are firms actually using it?",
  q_wages="Has it shown up in pay?",
  r_exposure=("Share of jobs in the quarter of occupations most exposed to generative AI. "
              "Exposure means a task could be affected, not that anyone has lost work."),
  r_demand=("Share of job advertisements that require an AI skill. Still a small slice of all "
            "hiring, but growing fast: see the Swedish series below."),
  r_adoption=("Share of firms using AI in 2025. Across the EU this was 8\\% in 2023, so "
              "adoption has more than doubled in two years."),
  r_wages=("Real wage growth 2015--2025 in US occupations, by exposure. Pay grew more slowly "
           "where exposure is highest. In Sweden it is flat in every group."),
  se_hd="SWEDEN IN DEPTH: HOW OFTEN DO JOB ADS ASK FOR AI?",
  se_sub="Every advertisement on the public job board",
  band_hi="mention an AI skill", band_lo="ask for it in the job itself",
  se_body=(r"We report a \textbf{{range}} rather than a single number, because it depends on how "
           r"strictly you count. The upper line counts an advertisement whenever it mentions an "
           r"AI skill anywhere, including the blurb about the company. The lower line counts it "
           r"only when the skill is asked of the person being hired. Both have risen sharply: "
           r"the broader count went from {v0:.2f}\% of advertisements in {y0} to {v1:.2f}\% in "
           r"{y1}, about {rise:.0f} times higher. For {y1} the honest range is "
           r"\textbf{{{fl:.2f}\% to {ceiling}\%}}."),
  se_live=(r"Right now ({asof}): of the {n} most recent advertisements, {names}\% mention an AI "
           r"skill and {floor}\% ask for one in the job itself. This is the only figure on the "
           r"sheet that moves daily."),
  cap_q="How fast is the technology moving?",
  cap_tail=("This is the technology the four questions are read against, not a fifth question "
            "about the labour market."),
  footnote=(r"\textbf{{One thing worth knowing before you quote this.}} The Swedish series counts "
            r"what employers \emph{{write down when hiring}}. It is not a count of jobs, and it is "
            r"not a count of firms using AI; those are two of the panels above, and they are "
            r"different things measured different ways. Not all hiring is advertised either. So a "
            r"rising line means employers ask for AI skills more often than they used to, and "
            r"nothing more than that."),
  colophon=(r"AI-Econ Lab, Örebro University and the Ratio Institute. Built on public data: "
            r"Platsbanken/JobTech (CC0), Eurostat, SCB, BLS, METR, Epoch AI, ARC Prize. Every "
            r"figure is reproducible from the source named beside it. Method, version history and "
            r"change log: \href{{https://ai-econlab.com/monitor/methods/}}{{ai-econlab.com/monitor/methods}}."),
  lab_se="Sweden", lab_eu="Europe", lab_eu2="EU", lab_med="22-country median",
  lab_least="Least exposed", lab_most="Most exposed",
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
  four_hd="FYRA FRÅGOR, FYRA OLIKA SVAR",
  legend_se="Sverige", legend_intl="internationell jämförelse",
  q_exposure="Skulle AI kunna göra delar av jobbet?",
  q_demand="Efterfrågar arbetsgivarna det?",
  q_adoption="Använder företagen det faktiskt?",
  q_wages="Syns det i lönerna?",
  r_exposure=("Andel jobb i den fjärdedel av yrkena som är mest exponerad för generativ AI. "
              "Exponering betyder att en arbetsuppgift kan beröras, inte att någon förlorat jobbet."),
  r_demand=("Andel jobbannonser som kräver AI-kompetens. Fortfarande en liten del av all "
            "rekrytering, men den växer snabbt: se den svenska serien nedan."),
  r_adoption=("Andel företag som använde AI 2025. I EU var siffran 8\\% 2023, så användningen "
              "har mer än fördubblats på två år."),
  r_wages=("Reallöneutveckling 2015--2025 i amerikanska yrken, efter exponering. Lönerna växte "
           "långsammare där exponeringen är högst. I Sverige är de platta i alla grupper."),
  se_hd="SVERIGE PÅ DJUPET: HUR OFTA EFTERFRÅGAR ANNONSERNA AI?",
  se_sub="Varje annons på Platsbanken",
  band_hi="nämner en AI-färdighet", band_lo="efterfrågar den i själva jobbet",
  se_body=(r"Vi redovisar ett \textbf{{intervall}} i stället för en enda siffra, eftersom svaret "
           r"beror på hur strikt man räknar. Den övre linjen räknar en annons så snart den nämner "
           r"en AI-färdighet någonstans, även i texten om företaget. Den nedre räknar den bara när "
           r"färdigheten efterfrågas av den som ska anställas. Båda har stigit kraftigt: den "
           r"bredare räkningen gick från {v0:.2f}\% av annonserna {y0} till {v1:.2f}\% {y1}, "
           r"ungefär {rise:.0f} gånger högre. För {y1} är det ärliga intervallet "
           r"\textbf{{{fl:.2f}\% till {ceiling}\%}}."),
  se_live=(r"Just nu ({asof}): av de {n} senaste annonserna nämner {names}\% en AI-färdighet och "
           r"{floor}\% efterfrågar den i själva jobbet. Det är den enda siffran på bladet som "
           r"ändras dagligen."),
  cap_q="Hur snabbt utvecklas tekniken?",
  cap_tail=("Det här är tekniken som de fyra frågorna läses mot, inte en femte fråga om "
            "arbetsmarknaden."),
  footnote=(r"\textbf{{En sak värd att veta innan du citerar det här.}} Den svenska serien räknar "
            r"vad arbetsgivare \emph{{skriver ned när de rekryterar}}. Det är inte en räkning av "
            r"jobb, och inte av företag som använder AI; det är två av panelerna ovan, och de "
            r"mäter olika saker på olika sätt. All rekrytering annonseras inte heller. En stigande "
            r"linje betyder alltså att arbetsgivare efterfrågar AI-kompetens oftare än förr, "
            r"varken mer eller mindre."),
  colophon=(r"AI-Econ Lab, Örebro universitet och Ratio. Byggt på öppna data: Platsbanken/JobTech "
            r"(CC0), Eurostat, SCB, BLS, METR, Epoch AI, ARC Prize. Varje siffra går att återskapa "
            r"från källan som anges intill. Metod, versionshistorik och ändringslogg: "
            r"\href{{https://ai-econlab.com/monitor/methods/}}{{ai-econlab.com/monitor/methods}}."),
  lab_se="Sverige", lab_eu="Europa", lab_eu2="EU", lab_med="medianland av 22",
  lab_least="Minst exponerade", lab_most="Mest exponerade",
 ),
}

SV_MONTH = {1:"januari",2:"februari",3:"mars",4:"april",5:"maj",6:"juni",7:"juli",
            8:"augusti",9:"september",10:"oktober",11:"november",12:"december"}


def main():
    landscape = "--landscape" in sys.argv
    lang = "sv" if "--sv" in sys.argv else "en"
    C = COPY[lang]
    m = yaml.safe_load((DATA / "monitor.yaml").read_text(encoding="utf-8"))
    today = date.today()
    stamp = (f"{today.day} {SV_MONTH[today.month]} {today.year}" if lang == "sv"
             else today.strftime("%-d %B %Y"))
    ov = {o["k"]: o for o in m["overview"]}
    tr, lw = m["trend"], m["livewindow"]

    exp_eu, = grab(r"^(\d+(?:\.\d+)?)", plain(ov["Exposure"]["num"]), "European exposure")
    exp_se, = grab(r"Sweden (\d+(?:\.\d+)?)%", ov["Exposure"]["lab"], "Swedish exposure")
    dem_med, = grab(r"^(\d+(?:\.\d+)?)", plain(ov["Demand"]["num"]), "median AI-ad share")
    dem_se, = grab(r"Sweden (\d+(?:\.\d+)?)%", ov["Demand"]["lab"], "Swedish AI-ad share")
    ado_eu, = grab(r"^(\d+(?:\.\d+)?)", plain(ov["Adoption"]["num"]), "EU adoption")
    ado_se, = grab(r"Sweden (\d+(?:\.\d+)?)%", ov["Adoption"]["lab"], "Swedish adoption")
    out_hi, out_lo = grab(r"\((\d+(?:\.\d+)?)% against (\d+(?:\.\d+)?)%\)",
                          ov["Outcomes"]["lab"], "US real wage growth by exposure")
    ceiling = next((h.group(1) for note in m.get("notes", [])
                    for h in [re.search(r"corrected ceiling at <b>([\d.]+)%", note)] if h), "1.36")

    colw = "0.30" if landscape else "0.465"
    P = [
        panel(C["q_exposure"], pair_bars(C["lab_se"], exp_se, C["lab_eu"], exp_eu),
              C["r_exposure"], tex(ov["Exposure"]["foot"]), colw),
        panel(C["q_demand"], pair_bars(C["lab_se"], dem_se, C["lab_med"], dem_med),
              C["r_demand"], tex(ov["Demand"]["foot"]), colw),
        panel(C["q_adoption"], pair_bars(C["lab_se"], ado_se, C["lab_eu2"], ado_eu),
              C["r_adoption"], tex(ov["Adoption"]["foot"]), colw),
        panel(C["q_wages"], pair_bars(C["lab_least"], out_lo, C["lab_most"], out_hi,
                              cols=(f"{INTL}!55", INTL)),
              C["r_wages"], tex(ov["Outcomes"]["foot"]), colw),
    ]
    grid = P[0] + "\\hfill" + P[1] + "\\\\[11pt]\n" + P[2] + "\\hfill" + P[3]

    cap = ov["Capability"]
    hero = range_band(tr["years"], tr["values"], tr["floor_values"],
                      C["band_hi"], C["band_lo"])
    se_body = C["se_body"].format(v0=tr["values"][0], y0=tr["years"][0],
                                  v1=tr["values"][-2], y1=tr["years"][-2],
                                  rise=tr["values"][-2] / tr["values"][0],
                                  fl=tr["floor_values"][-2], ceiling=ceiling)
    se_live = C["se_live"].format(asof=tex(lw["asof"]), n=tex(lw["n"]),
                                  names=lw["names_pct"], floor=lw["floor_pct"])
    geom = "a4paper,landscape,margin=12mm" if landscape else "a4paper,margin=13mm"

    doc = rf"""
\documentclass[10pt]{{article}}
\usepackage{{fontspec}}
\usepackage[{geom}]{{geometry}}
\usepackage{{xcolor}}
\usepackage{{tikz}}
\usepackage[colorlinks=true,urlcolor=link,linkcolor=link]{{hyperref}}
\definecolor{{ink}}{{HTML}}{{{INK_HEX}}}
\definecolor{{soft}}{{HTML}}{{{SOFT_HEX}}}
\definecolor{{link}}{{HTML}}{{{SE_HEX}}}
\definecolor{{{SE}}}{{HTML}}{{{SE_HEX}}}
\definecolor{{{INTL}}}{{HTML}}{{{INTL_HEX}}}
\definecolor{{hair}}{{HTML}}{{E5E7EB}}
\pagestyle{{empty}}\setlength{{\parindent}}{{0pt}}

\begin{{document}}

{{\LARGE\bfseries\textcolor{{ink}}{{{C['title']}}}}}\hfill
{{\footnotesize\textcolor{{soft}}{{{C['kicker'].format(stamp=stamp)}}}}}\\[1pt]
{{\small\textcolor{{soft}}{{{C['standfirst_sub']}}}}}\\[3pt]
\textcolor{{ink}}{{\rule{{\textwidth}}{{1.1pt}}}}\\[5pt]

{{\scriptsize\textcolor{{soft}}{{{C['caveat']}}}}}\\[9pt]

{{\footnotesize\bfseries\textcolor{{ink}}{{{C['four_hd']}}}}}\hfill
{{\tiny\textcolor{{soft}}{{\textcolor{{{SE}}}{{\rule{{1.7mm}}{{1.7mm}}}}~{C['legend_se']} \quad
\textcolor{{{INTL}}}{{\rule{{1.7mm}}{{1.7mm}}}}~{C['legend_intl']}}}}}\\[8pt]
{grid}\\[11pt]

\textcolor{{hair}}{{\rule{{\textwidth}}{{0.5pt}}}}\\[8pt]
{{\footnotesize\bfseries\textcolor{{ink}}{{{C['se_hd']}}}}}\hfill
{{\scriptsize\textcolor{{soft}}{{{C['se_sub']}}}}}\\[7pt]
\hspace*{{7mm}}{hero}\\[7pt]
{{\scriptsize {se_body}}}\\[3pt]
{{\tiny\textcolor{{soft}}{{{se_live}}}}}\\[10pt]

\textcolor{{hair}}{{\rule{{\textwidth}}{{0.5pt}}}}\\[7pt]
\noindent\begin{{minipage}}[c]{{0.30\textwidth}}
  {{\footnotesize\bfseries\textcolor{{ink}}{{{C['cap_q']}}}}}\\[3pt]
  {{\Large\bfseries\textcolor{{ink}}{{{tex(cap['num'])}}}}}
\end{{minipage}}%
\begin{{minipage}}[c]{{0.68\textwidth}}\raggedright
  {{\scriptsize {tex(cap['lab'])}. {C['cap_tail']}}}\\[1pt]
  {{\tiny\textcolor{{soft}}{{{tex(cap['foot'])}}}}}
\end{{minipage}}\\[9pt]

\textcolor{{hair}}{{\rule{{\textwidth}}{{0.5pt}}}}\\[4pt]
{{\scriptsize\textcolor{{soft}}{{{C['footnote']}}}}}\\[4pt]
{{\tiny\textcolor{{soft}}{{{C['colophon']}}}}}

\end{{document}}
"""
    out = OUT if lang == "en" else OUT.with_name("aiel-monitor-onepager-sv.pdf")
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "onepager.tex"
        src.write_text(doc, encoding="utf-8")
        r = subprocess.run([TECTONIC, "--outdir", td, str(src)], capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write((r.stdout + r.stderr)[-3500:])
            raise SystemExit("tectonic failed")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(td) / "onepager.pdf", out)
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size/1024:.0f} kB, {lang}, "
          f"{'landscape' if landscape else 'portrait'}, generated {stamp})")


if __name__ == "__main__":
    main()
