#!/usr/bin/env python3
"""
build_social.py — one square card for social media, generated from the Monitor's own data.

WHY A SEPARATE ARTEFACT. The lab's communication rule asks every paper and release for a
"standalone figure that works without context": something a reader meets in a feed, with no
surrounding page, no caption they will read, and about two seconds of attention. The two-page
sheet cannot do that job. It is A4, it is dense on purpose, and it renders as an unreadable
grey rectangle at thumbnail size.

WHY THIS FIGURE. The occupations module answers the question people actually ask, and answers
it with a contrast rather than a level: the occupations that ask for AI most often are small and
academic, while three of the largest occupations on the Swedish job board ask for it in exactly
none of their advertisements. A single number ("2.8% of ads") invites the reader to argue about
the number. A contrast invites them to look.

DESIGN. Portrait 4:5, because that is what a phone gives most room to. Everything direct-labelled,
so it survives being resized, screenshotted and reposted. Same palette, same font and the same
provenance discipline as the sheet: the figures are read from data/occupations.yaml, never typed,
and the source line and the address travel with the picture, since the picture will be separated
from the post that carried it.

Run:  python3 scripts/build_social.py          -> docs/social/aiel-occupations.png (+ .pdf)
      python3 scripts/build_social.py --sv
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "docs" / "social"
TECTONIC = "/opt/homebrew/bin/tectonic"
# 1200x1500 at 254 dpi. LinkedIn allows 1:1 and 4:5 in the feed and gives 4:5 more vertical
# room on a phone, which is where the post will be read. A square was tried first and the
# figure needed 114mm inside its 106mm: 4:5 buys the 30mm rather than cutting an occupation.

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_onepager import INK_HEX, INTL, INTL_HEX, SE, SE_HEX, SOFT, SOFT_HEX, tex  # noqa: E402

COPY = {
    "en": dict(
        kicker="AIEL MONITOR · SWEDEN {year}",
        title="Which jobs ask for AI skills?",
        sub="Share of an occupation's advertisements asking for AI skills in the role",
        hi="Asks most often",
        lo="And in none of these",
        close="Demand is real and concentrated: most of the labour market is not asked at all.",
        ads="{n} ads",
        src="JobTech / Platsbanken job ads (CC0), distinct advertisements, {year}",
    ),
    "sv": dict(
        kicker="AIEL MONITOR · SVERIGE {year}",
        title="Vilka jobb efterfrågar AI-kompetens?",
        sub="Andel av yrkets annonser som efterfrågar AI-kompetens i tjänsten",
        hi="Efterfrågar oftast",
        lo="Och i ingen av dessa",
        close="Efterfrågan är verklig och koncentrerad: de flesta får inte frågan alls.",
        ads="{n} annonser",   # n is pre-formatted below
        src="JobTech / Platsbanken (CC0), distinkta annonser, {year}",
    ),
}


def bars(rows, namekey, w=26, n=5):
    """The occupations that ask most often, as a narrow ranked column.

    Two columns rather than one long list. A single stacked column of six bars, three zero rows
    and a closing line needed 147mm of height inside a 106mm square: a square has width to spend
    and no height at all, and the whole figure is a CONTRAST, which reads better side by side
    than stacked. Four rows, not six, for the same reason.
    """
    rows = rows[:n]
    top = max(r["share"] for r in rows) * 1.03
    bw, gap, lab = 4.0, 8.4, 4.0
    s = "\\begin{tikzpicture}[x=1mm,y=1mm]\n"
    for i, r in enumerate(reversed(rows)):
        y = i * (bw + gap)
        L = max(r["share"] / top * w, 0.6)
        s += (f"\\fill[{SOFT}!12,rounded corners=0.5pt] (0,{y}) rectangle ({w},{y+bw});\n"
              f"\\fill[{SE},rounded corners=0.5pt] (0,{y}) rectangle ({L:.2f},{y+bw});\n"
              f"\\node[anchor=west,font=\\small\\bfseries,text=ink] at ({w+1.6},{y+bw/2:.2f}) "
              f"{{{r['share']:.1f}\\%}};\n"
              f"\\node[anchor=south west,font=\\scriptsize,text=ink,align=left,text width=54mm] "
              f"at (0,{y+bw+0.4}) {{{tex(r[namekey])}}};\n")
    return s + "\\end{tikzpicture}"


def fmt_n(n, lang="en"):
    """Thousands separated the way each language does it: a comma in English, a thin space in
    Swedish. The sv card first read "15842 annonser" because the English format string carried
    the separator and the Swedish one did not."""
    return f"{n:,}" if lang == "en" else f"{n:,}".replace(",", "\\,")


def zero_rows(rows, namekey, C, lang='en'):
    """The three largest occupations that ask in none of their advertisements."""
    out = []
    for r in rows:
        name = tex(r[namekey]).split(";")[0].split(",")[0]
        out.append(f"{{\\large\\bfseries\\textcolor{{{INTL}}}{{0.0\\%}}}}\\\\[0.4mm]\n"
                   f"{{\\scriptsize\\textcolor{{ink}}{{{name}}}}}\\\\[0.4mm]\n"
                   f"{{\\scriptsize\\textcolor{{{SOFT}}}{{{C['ads'].format(n=fmt_n(r['ads'], lang))}}}}}")
    return "\\\\[4.6mm]\n".join(out)


def main():
    lang = "sv" if "--sv" in sys.argv else "en"
    C = COPY[lang]
    occ = yaml.safe_load((DATA / "occupations.yaml").read_text(encoding="utf-8"))
    namekey = "name_sv" if lang == "sv" else "name"
    if any(namekey not in r for r in occ["top"] + occ["zero"]):
        namekey = "label"
    year = occ["meta"]["year"]

    doc = rf"""\documentclass[11pt]{{article}}
\usepackage{{fontspec}}
\usepackage[paperwidth=120mm,paperheight=150mm,margin=8mm]{{geometry}}
\usepackage{{xcolor}}
\usepackage{{tikz}}
\pagestyle{{empty}}\setlength{{\parindent}}{{0pt}}
\setmainfont{{Avenir Next}}[UprightFont={{* Regular}}, BoldFont={{* Demi Bold}},
  ItalicFont={{* Italic}}]
\definecolor{{ink}}{{HTML}}{{{INK_HEX}}}
\definecolor{{{SOFT}}}{{HTML}}{{{SOFT_HEX}}}
\definecolor{{{SE}}}{{HTML}}{{{SE_HEX}}}
\definecolor{{{INTL}}}{{HTML}}{{{INTL_HEX}}}
\definecolor{{hair}}{{HTML}}{{D9DCE1}}
\begin{{document}}

{{\scriptsize\textcolor{{{SOFT}}}{{{C['kicker'].format(year=year)}}}}}\hfill
{{\scriptsize\bfseries\textcolor{{{SE}}}{{ai-econlab.com}}}}\\[1.2mm]
{{\Large\bfseries\textcolor{{ink}}{{{C['title']}}}}}\\[1.4mm]
{{\footnotesize\textcolor{{{SOFT}}}{{{C['sub']}}}}}\\[1.8mm]
\textcolor{{ink}}{{\rule{{\textwidth}}{{1.2pt}}}}\\[2.4mm]

\noindent\begin{{minipage}}[t]{{0.53\textwidth}}
{{\footnotesize\bfseries\textcolor{{{SOFT}}}{{{C['hi'].upper()}}}}}\\[3.4mm]
{bars(occ['top'], namekey)}
\end{{minipage}}\hfill
\begin{{minipage}}[t]{{0.42\textwidth}}
{{\footnotesize\bfseries\textcolor{{{SOFT}}}{{{C['lo'].upper()}}}}}\\[3.4mm]
{zero_rows(occ['zero'], namekey, C, lang)}
\end{{minipage}}\\[4mm]

\textcolor{{hair}}{{\rule{{\textwidth}}{{0.6pt}}}}\\[2mm]
{{\small\textcolor{{ink}}{{{C['close']}}}}}\\[1.8mm]
{{\tiny\textcolor{{{SOFT}}}{{{C['src'].format(year=year)}}}}}
\end{{document}}
"""
    suffix = "" if lang == "en" else "-sv"
    OUT.mkdir(parents=True, exist_ok=True)
    pdf = OUT / f"aiel-occupations{suffix}.pdf"
    png = OUT / f"aiel-occupations{suffix}.png"
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "social.tex"
        src.write_text(doc, encoding="utf-8")
        r = subprocess.run([TECTONIC, "--outdir", td, str(src)], capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write((r.stdout + r.stderr)[-3000:])
            raise SystemExit("tectonic failed")
        pages = subprocess.run(["pdfinfo", str(Path(td) / "social.pdf")],
                              capture_output=True, text=True).stdout
        n_pages = int(re.search(r"^Pages:\s+(\d+)", pages, re.M).group(1))
        if n_pages != 1:
            raise SystemExit(f"build_social: {lang} came out at {n_pages} pages. The card's\n"
                             f"  whole point is that it is one image; shorten the copy.")
        shutil.copy2(Path(td) / "social.pdf", pdf)
        # 120mm square at 254 dpi = 1200px, the feed's native card size
        subprocess.run(["pdftoppm", "-r", "254", "-png", "-singlefile",
                        str(pdf), str(png.with_suffix(""))], check=True)
    print(f"wrote {png.relative_to(ROOT)} and {pdf.relative_to(ROOT)} ({lang})")


if __name__ == "__main__":
    main()
