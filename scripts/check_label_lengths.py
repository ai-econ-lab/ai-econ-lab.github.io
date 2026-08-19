#!/usr/bin/env python3
"""Fail when a chart label does not fit its gutter, or when the gutter eats the chart.

    python3 scripts/check_label_lengths.py [docs]

WHY. Two defects, the same cause, found a year apart in the same function.

  clipped   the label gutter was a fixed 128px, then capped at 300px, so any label past ~46
            characters was cut. SCB's "Assistant nurses, home care, home nursing, elderly care
            and habilitation" rendered on the live site as "care, home nursing, elderly care
            and habilitation" -- the occupation's actual name gone, and nothing said so.
  crowded   the cap was removed and the CANVAS grown instead, which fixed the clipping and
            replaced it with a worse problem for most readers: that one title pushed the
            viewBox to 796px, giving the gutter 57 per cent of the width. On a phone in
            portrait the whole SVG scales to the container, so the reader saw a column of
            titles and a sliver of chart.

Both were invisible to every check that existed, because both produce valid HTML, a valid
SVG, and a page that builds clean. What they break is legibility, so that is what this
measures, on the BUILT output rather than on the data.

  RULE 1  a label must fit its own gutter. A `dname` is anchored at the gutter's right edge
          and runs leftwards, so `chars * ADVANCE` must not exceed x. This catches clipping in
          any chart, including ones not written yet, and needs to know nothing about which
          chart it is looking at.
  RULE 2  the gutter must not take more than MAX_GUTTER_SHARE of the viewBox. This is the
          crowding rule, and it is the one the phone cares about.

ADVANCE is 6.2px: the labels are 10px in the mono face, and build.py sizes its gutters with
the same constant. Being wrong about it in the safe direction only makes this check stricter.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ADVANCE = 6.2                 # px per character, 10px mono, as build.py assumes
MAX_GUTTER_SHARE = 0.45       # of the viewBox width
SLACK = 2.0                   # px, so a label that fits exactly is not a failure

SVG_RE = re.compile(r'<svg class="rankchart[^"]*"[^>]*viewBox="0 0 ([\d.]+) ([\d.]+)"[^>]*>(.*?)</svg>',
                    re.S)
NAME_RE = re.compile(r'<text class="dname[^"]*"[^>]*\sx="([\d.]+)"[^>]*>(.*?)</text>', re.S)
TITLE_RE = re.compile(r"<title>.*?</title>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def text_of(node: str) -> str:
    """The visible label: the <title> child is for hover and screen readers, not the canvas."""
    node = TITLE_RE.sub("", node)
    node = TAG_RE.sub("", node)
    # html.unescape, not a hand-rolled list of five entities: the first version of this file
    # used one, missed &#x27;, and reported "Can&#x27;t switch off after work" as 30 characters
    # instead of 27 -- a clip that was not happening, on the one chart nothing had changed.
    return html.unescape(node).strip()


def check_file(path: Path) -> list[str]:
    problems: list[str] = []
    src = path.read_text(encoding="utf-8", errors="replace")
    for w_s, _h, body in SVG_RE.findall(src):
        width = float(w_s)
        gutter = 0.0
        for x_s, node in NAME_RE.findall(body):
            x = float(x_s)
            gutter = max(gutter, x)
            label = text_of(node)
            need = len(label) * ADVANCE
            if need > x + SLACK:
                problems.append(
                    f"{path.name}: {label!r} needs {need:.0f}px and has {x:.0f}px "
                    f"-- clipped by {need - x:.0f}px")
        if gutter and gutter / width > MAX_GUTTER_SHARE:
            problems.append(
                f"{path.name}: gutter is {gutter:.0f}px of a {width:.0f}px viewBox "
                f"({gutter / width:.0%}, limit {MAX_GUTTER_SHARE:.0%}) -- the labels are "
                f"crowding out the chart. Shorten them (scripts/labels.py), do not widen it.")
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent / "docs"
    if not root.is_dir():
        print(f"check_label_lengths: {root} not found. Run build.py first.")
        return 2

    files = sorted(list(root.rglob("*.html")) + list(root.rglob("*.svg")))
    problems: list[str] = []
    charts = 0
    for f in files:
        src = f.read_text(encoding="utf-8", errors="replace")
        charts += len(SVG_RE.findall(src))
        problems += check_file(f)

    print(f"{len(files)} files · {charts} charts · advance {ADVANCE}px/char · "
          f"gutter limit {MAX_GUTTER_SHARE:.0%}")
    if problems:
        print(f"\nFAIL. {len(problems)} label problem(s):")
        for p in dict.fromkeys(problems):
            print("  " + p)
        return 1
    print("\nOK. Every label fits its gutter, and no gutter crowds its chart.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
