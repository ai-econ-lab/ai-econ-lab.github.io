# Monitor chart review: the Depenbusch lens

**Date:** 2026-08-01
**Scope:** `docs/monitor/index.html` as rendered by `python3 build.py`. 18 SVGs reviewed.
**Rubric:** the `dataviz` skill (form first, colour by job, validate, mark specs, legend and
accessibility pass), read through Morgan Depenbusch's recurring question: does the chart deliver
the "so what" on its own, or is the prose carrying a chart that failed?
**Method note:** the skill's `scripts/validate_palette.js` is missing from this install, so the
colour checks below were computed rather than eyeballed, with a local OKLab plus
Brettel/Viénot dichromat simulation (`scratchpad/cvd.py`). Numbers are OKLab ΔE ×100.

Magnus asked specifically for comprehension and legends, so legends are treated as a first-class
subject throughout and lead sections 1 and 2.

---

## What already works

Worth stating plainly, because it narrows the list.

- **Every figure ships its own data.** CSV, SVG, PNG and a 4× slide PNG on almost every chart.
  This is a genuine text alternative and better than most public monitors manage.
- **Source, unit and vintage under every chart.** `figsrc` consistently states the source,
  the year, and the counting unit ("distinct advertisements"). The `fignext` line telling the
  reader when the figure next updates is unusually good practice.
- **`jobquality_svg` is the strongest chart on the page.** Direct end-labels carrying both name
  and value ("full-time +10", "permanent -6"), a zero line drawn heavier than the grid
  (`stroke-width="1.4" opacity=".55"` against the grid's hairline), and a real
  percentage-point scale with signed ticks. It reads without the prose. It is also the only
  chart that survives greyscale, precisely because the labels do the identifying rather than
  the colour (see §5).
- **`vocabulary_svg` has proper direct labels with collision avoidance** (build.py:1148-1150).
  Four series, each named at its own line end.
- **Charts scroll rather than shrink.** `.dotwrap{overflow-x:auto}` with
  `.rankchart{min-width:520px}` (assets/styles.css:334-335) is exactly the right small-width
  behaviour, and matches the skill's rule that wide content scrolls in its own container.
- **The hero panel legend is a model of the form**: adjacent to the chart, plain language, and
  it explains the dash convention (`╌ newest point provisional`), which most legends forget.
- **Progressive disclosure of caveats** via `<details class="note">` keeps the charts clean
  without burying the limitation. Depenbusch would approve; so would a referee.
- **Zero baselines are honest.** Every share chart starts at 0. No truncated bar axes anywhere.

---

## Severity 1: charts that cannot be read without the prose, or that mislead

### 1.1 Wage terciles: the legend names three colours, two of which are not in the chart

**Charts:** "Wages in AI-exposed occupations", Sweden and United States (`wages_svg`, two SVGs).

The legend rendered under both charts is:

```html
<div class="dblegend"><span><i class="hi"></i>most AI-exposed third</span>
<span style="color:var(--c4,#cc79a7)">— middle</span>
<span><i class="lo"></i>least exposed</span></div>
```

`.dblegend i.hi` resolves to `var(--c1)`, blue. `.dblegend i.lo` resolves to `var(--muted)`,
grey (assets/styles.css:376). But the lines are drawn from a different dictionary
(build.py:1489):

```python
colors = {"high": "var(--c2)", "mid": "var(--c4, #cc79a7)", "low": "var(--c3)"}
```

So the chart contains an **orange** line, a **pink** line and a **green** line, and the legend
offers **blue**, pink and **grey**. Two of the three keys point at colours that appear nowhere
in the figure. Only "middle" matches.

This is not cosmetic. In the US panel the top line ends at 149 and the bottom at 140, and the
prose states the finding as "in the United States they [most exposed] grew more slowly than the
least exposed (40% against 49%)". The top line is therefore the **least**-exposed third. A
reader who cannot use the legend will fall back on the natural assumption that the top line is
the "most exposed" one and take the headline finding **exactly backwards**. The chart currently
depends entirely on the reader trusting the bold sentence above it, which is the failure mode
this review is looking for.

**Fix (build.py:1512),** swatches that carry the real colours:

```html
<div class="dblegend"><span><i style="background:var(--c2)"></i>most AI-exposed third</span>
<span><i style="background:var(--c4,#cc79a7)"></i>middle</span>
<span><i style="background:var(--c3)"></i>least exposed</span></div>
```

**Better fix,** and the code already anticipates it: build.py:1490 defines
`labels = {"high": "most exposed", "mid": "middle", "low": "least exposed"}` and then never
uses it. Direct-label the line ends at build.py:1494-1495, appending `labels[g]` to the value
so the end reads "least exposed 149" rather than a bare "149". Then the legend becomes
redundant on both panels and the figure survives being exported as a slide PNG, which is the
form in which it will actually travel. Print the names on the Sweden panel only if the US panel
gets crowded.

### 1.2 "EU 0.52" and "EU 42" label the Swedish figure as European

**Charts:** "Where the demand sits" (occupations, 12 bars) and "Sweden, in depth · by person"
(population by age, 6 bars).

`barplot` hardcodes the mean-line label (build.py:734):

```python
p.append(f'<text class="meanlab" ... >EU {eu_avg:g}</text>')
```

Three callers pass something that is not an EU average:

| Chart | Call site | Renders | Actually is |
|---|---|---|---|
| Occupations | build.py:1192 `barplot(..., m["national"], ...)` | `EU 0.52` | Sweden's national AI-demand floor |
| Population by age | build.py:1378 `barplot(..., m['headline'], ...)` | `EU 42` | Sweden's 2025 population rate |
| Firm size | build.py:1286 | `EU 19.9` | genuinely the EU average (fine) |

The occupations caption underneath even contradicts the chart: "The line marks the national
figure, 0.52%." A reader who trusts the mark over the caption concludes that Swedish doctoral
students are 27 times the European average, from a chart that contains no European data at all.
The population chart is worse, because "EU 42" sits on a purely Swedish age breakdown and is
plausible enough as an EU number that nobody would question it.

**Fix:** give `barplot` a `mean_label="EU"` parameter and interpolate it at build.py:734
(`>{mean_label} {eu_avg:g}<`). Pass `mean_label="Sweden"` at build.py:1192 and build.py:1378,
and at the two matching standalone-SVG call sites, build.py:1998 and build.py:2057, which
export the same defect into the downloadable files.

### 1.3 The monthly chart has three lines and no legend at all

**Chart:** "Month by month, 2006-01 to 2026-06" (`monthly_svg`).

The rendered SVG is followed straight by `figfoot`. There is no `<div class="legend">`. Series
identity lives only in the paragraph above:

> "The faint line is the raw month and the bold lines are 12-month trailing means: broad AI
> demand in blue, the narrower skill floor in orange."

That is identification by **colour name in prose**, which is the thing the skill rules out for
two or more series, and it fails outright for a colour-blind reader, in greyscale, and in every
context where the figure is separated from the page. The figure has a "PNG (slides)" button
directly beneath it, so separation from the page is the expected case, not the edge case.

Note that the hero panel two lines up already has the correct legend for the same two series:

```html
<div class="legend"><span><i style="background:var(--c1)"></i>Names an AI skill</span>
<span><i style="background:var(--c2)"></i>Asks for AI in the role (floor)</span></div>
```

**Fix:** in `monthly_block` (build.py:994), emit that same legend markup after the SVG, plus a
third entry for the faint raw line. Then delete the colour names from the prose at
build.py:976-977, since the legend will carry it and the sentence can go back to being about
seasonality. Note the raw line is drawn in `var(--c1)` at `opacity=".32"` and is the raw version
of the **broad** series only; there is no raw line for the floor. The legend should say so
("faint: single month, broad measure"), because the current asymmetry is invisible and
unexplained.

### 1.4 The governance bar chart draws half a year at full height

**Chart:** "How fast is AI-governance language entering job ads?" (`governance_svg`).

The 2026 bar is the tallest in the chart at 185, against 156 for the whole of 2025. It covers
six months. The only cues are `opacity="0.55"` on the rect and an asterisk in the tick label
(`2026*`), and **the asterisk has no key anywhere in or under the figure**. The `figsrc` says
"2018 to first half of 2026", which a careful reader could connect, but the visual claim made
by the tallest bar in the chart, standing on the same baseline and the same width as eight full
years, is that 2026 already beat 2025. The prose is careful ("the first half of 2026 alone");
the chart is not, and the chart is what gets screenshotted.

This is the clearest case on the page of a chart type fighting its data: a count-per-year bar
chart cannot host a part-year without either annualising it or marking the partial bar
unmistakably.

**Fix (build.py:1084-1088),** cheapest version that is honest: keep the faded bar, add an
in-chart note anchored near it, `<text class="tick">* Jan–Jun only</text>`, and hatch the
partial bar rather than fading it, since a 0.55 opacity fill still reads as a solid taller bar.
The stronger version is to draw the 2026 bar in two parts, the observed half solid and the
remainder of the year as an open outline, so the eye compares like with like. Either way the
partial-period rule should live in `governance_svg` rather than in the paragraph.

---

## Severity 2: legends and colour, specifically

### 2.1 Grey against blue fails the normal-vision floor, and dies completely in greyscale

This is the single most consequential palette finding, and it hits the two charts whose entire
purpose is a two-group comparison: the **entry-level squeeze** (`.sqlo` grey, `.sqhi` blue,
assets/styles.css:387-388) and the **working-conditions dumbbell** (`.dblo` grey, `.dbhi` blue,
assets/styles.css:371). Both share the `dblegend` grey/blue key.

Computed, not eyeballed:

| Pair | Normal ΔE | Deuteranopia | Protanopia | Greyscale (ΔL) |
|---|---|---|---|---|
| `--c1` / `--muted`, light | **10.6** | 27.1 | 8.9 | **1.2** |
| `--c1` / `--muted`, dark | **12.2** | 22.2 | 9.7 | n/a |

The skill's hard floor for normal vision is 15, and it is explicit that a normal-vision failure
is the one case a secondary encoding does **not** excuse. Both modes fail it. The greyscale
separation of 1.2 means that in any printed or greyscale copy the two lines of the entry-level
squeeze chart are the same colour, and the "PNG (slides)" export on that figure is the route by
which that copy gets made. Magnus's own house rule in CLAUDE.md asks for grayscale-friendly
figures, so this fails the lab's standard as well as the skill's.

The dumbbell partly compensates with radius (`r="4"` low against `r="5.5"` high) and with the
`52→63` value labels; the squeeze chart compensates only with stroke width (2 against 2.6),
which is not a distinguishable encoding at 520px.

**Fix:** re-step the pair. Replacing `--muted` with `--c2` (orange) in `.sqlo`, `.sqdot.lo`,
`.sqval.lo`, `.dumb .dblo` and `.dblegend i.lo` gives `--c1`/`--c2` at ΔE 31.2 normal, 48.5
deuteranopia, 24.0 protanopia: a clean pass on every check. Greyscale ΔL is still only 8.9,
so pair the recolour with direct labels at the line ends of the squeeze chart ("least exposed
33%", "most exposed 28%") in place of the current bare `33%` / `28%`, and greyscale is covered
too. This is a five-line CSS change plus two label strings in `squeeze_svg`.

### 2.2 The `dblegend` mixes swatch shapes and one entry has no swatch

In the wage legend the first and third entries are `<i>` circles and the middle is a coloured
em-dash character, `<span style="color:var(--c4)">— middle</span>`. Three series, two different
legend grammars, and the odd one out is a text glyph whose colour is doing all the work. It also
puts a stray dash into a house style that avoids them. Use the same `<i>` swatch for all three
(covered by the fix in §1.1).

Separately, `.dblegend i` is a 9px circle while the lines it explains are 2.2px strokes.
`.legend i` (the hero legend) is an 11×3px bar, which correctly mimics a line. For the line
charts the bar form is the right swatch; keep circles for the dumbbell, where the marks really
are dots.

### 2.3 Where colour is the only key, name it; where labels exist, colour can relax

The computed matrix explains why the page splits so cleanly into good and bad charts:

| Pair (light) | Normal | Deuter | Protan | Greyscale ΔL |
|---|---|---|---|---|
| c1/c2 blue/orange | 31.2 | 48.5 | 24.0 | 8.9 |
| c1/c3 blue/green | 18.7 | 35.1 | 18.3 | 8.8 |
| c2/c3 orange/green | 25.8 | 14.8 | 11.5 | **0.2** |
| c3/c4 green/pink | 25.4 | 10.5 | 8.2 | 6.0 |
| c4/muted, dark mode | 12.1 | **3.5** | **4.2** | n/a |

Okabe–Ito holds up well for colour vision: every categorical pair clears the ΔE 8 target except
c3/c4 under protanopia at 8.2, which is marginal. The real weakness is **greyscale**: orange and
green are the same lightness (ΔL 0.2). The vocabulary chart and the job-quality chart both use
that pair and both survive anyway, because they direct-label. The squeeze chart, the dumbbell
and the wage charts do not label, and do not survive. The rule to adopt is simply: **any chart
whose series are identified only by a legend needs direct labels too.**

One genuine failure in the matrix: `--c4` against `--muted` in **dark mode** at ΔE 3.5
deuteranopia and 4.2 protanopia, below the hard floor of 6. That pair is currently adjacent in
the wage legend (pink "middle" beside grey "least exposed"). Fixing §1.1 removes it.

---

## Severity 3: titles and takeaways

### 3.1 The squeeze chart never draws the number it exists to show

**Chart:** "Entry-level squeeze" (`squeeze_svg`).

The headline everywhere else on the page is **−5.3pp**: the overview card, the tile row, and the
section prose. The chart shows two lines at 33% and 28% inside a 0 to 40% window, and a
`sqband` polygon filled at 10% opacity between them. The gap, which is the entire finding, is
never measured on the figure. A reader has to subtract two end labels themselves, and the band
is too faint to read as a quantity.

**Fix (`squeeze_svg`, around build.py:836):** annotate the final gap. A vertical tick between
the two 2025 endpoints with the label `−5.3pp gap` (and optionally the 2020 value `−3.1pp` at
the left) turns the chart from "two lines that drift" into "the gap widened, and here is by how
much". Given the band polygon already exists, this is a handful of lines.

### 3.2 No chart carries its own title or takeaway

Every chart on the page depends on the surrounding `grouphdr` and `secintro` for its subject.
Nothing inside any SVG says what it shows. That is defensible on the page, where the heading is
right there, but the page ships `↓ SVG`, `↓ PNG` and `↓ PNG (slides)` on every figure, and the
`chart_standalone()` wrapper (build.py:1891) adds only a colour-token style block. So every
downloaded figure arrives with no title, no source, and in the failing cases no working legend.
These files are the ones that end up in Beamer decks and press emails.

**Fix:** add a `<title>` line and a small source line to `chart_standalone()` at build.py:1891,
taking the text from the `figsrc` string the page already builds. One change, and every export
inherits it. The Depenbusch point applies with force here: a leader receiving the PNG needs the
interpretation, and the interpretation currently stays behind on the web page.

### 3.3 The job-quality chart never states its unit or which direction is good

`jobquality_svg` is otherwise the best chart on the page, but its y-axis ticks read
`-10 -5 0 +5 +10 +15 +20` with no unit anywhere in the plot area. "Percentage points, AI-skill
ads minus all other ads" is in the prose and in the aria-label but not in the figure. Nor does
anything say that above zero is the AI-skill advantage and below zero is the deficit, which is
the whole reason the permanent line crossing zero in 2023 matters.

**Fix:** an axis caption at the top of the plot, `pp gap vs all other ads`, plus two faint
anchor words at the zero line, `AI-skill ads better ↑` and `worse ↓`. Roughly three lines in
`jobquality_svg` after build.py:1020.

---

## Severity 4: accessibility

### 4.1 Three aria-labels describe a change column that is not in the chart

`barplot` hardcodes its aria-label (build.py:726):

```python
aria-label="Ranked bar chart, {n} {what}, latest value with change since the previous wave"
```

Audited against the rendered SVGs:

| Chart | aria-label says | `ddelta` marks present |
|---|---|---|
| Exposure, 36 countries | "with change since the previous wave" | **0** |
| Demand, 22 countries | "with change since the previous wave" | **0** |
| Occupations | "12 **countries**, with change..." | **0** |
| Adoption, 33 countries | ditto | 33 |
| Firm size, 4 classes | ditto | 3 (one row silently has none) |
| Professions, 6 | ditto | 6 |
| Age groups, 6 | ditto | 6 |

A screen-reader user is told three times about a comparison that is not there, and the
occupations chart is announced as showing twelve **countries** when its rows are Swedish
occupations (the caller at build.py:1192 omits the `what=` argument that the other Swedish
charts pass).

More fundamentally: **no `barplot` aria-label names what is being measured.** "Ranked bar chart,
36 countries, latest value" conveys nothing about AI exposure, shares, or Sweden. The
non-`barplot` charts do much better ("Share of AI term matches by vocabulary family, 2006 to
2026-Q2"), which shows the house knows how to write these.

**Fix:** give `barplot` a required `measure` string, build the label as
`f"{measure}, ranked, {n} {what}"`, and append `", with change since {prev}"` only when
`any(r.get("prev") is not None for r in rows)`. Pass `what='occupations'` at build.py:1192.

### 4.2 The hero chart is empty in the HTML and has no fallback

The most prominent figure on the page ships as:

```html
<svg id="trend" viewBox="0 0 640 300" role="img" aria-label="Share of Swedish job ads naming or asking for AI skills, 2006 onwards"></svg>
```

It is populated by `window.drawTrend()` in app.js:39-95. With JavaScript unavailable, a blocked
script, or a failed `AIEL_TREND` payload, the reader gets a headline claiming "1.07% ... twenty-one
times the 2006 level", an empty 640×300 box, and a legend describing two lines that do not exist.
Every other chart on the page is server-rendered and degrades perfectly, which makes this the
odd one out rather than a design choice.

**Fix:** render the annual trend server-side like the rest (the data is already in `data/`), and
let app.js attach only the hover layer to the existing marks rather than generating the geometry.
Failing that, a `<noscript>` with the static SVG.

### 4.3 The monthly aria-label uses the wrong series definition

```
aria-label="Share of Swedish job ads requiring an AI skill, by month, 2006-01 to 2026-06"
```

The bold blue line is the **broad** measure, ads that *name* an AI skill; "requiring" is the
page's own word for the strict floor, the orange line. The page is deliberate about this
distinction ("We name the series by what the employer does, never by what the job is ... We
deliberately avoid the phrase 'AI jobs'"), so the aria-label quietly breaks the naming
discipline for exactly the readers who cannot see which line is which. Fix at build.py:936:
"Share of Swedish job ads naming an AI skill, and the stricter floor asking for it in the role,
by month".

### 4.4 The delta column has no header, no unit, and no minus sign

`ddelta` values render at `x="632"` with no column heading anywhere. A reader sees `+14` beside
Denmark's `42` and cannot tell whether that is 14 percentage points, 14 per cent, or 14
something else; only the `figsrc` says "(change vs 2024)". Greece renders `-1` with a
hyphen-minus rather than a true minus (`−`), and no negative value is distinguished by colour or
weight from the positives, so a decline reads as one more entry in a column of increases.

**Fix (build.py:743):** emit `{v-r["prev"]:+.0f}`.replace("-", "−"), add a column header above
the first row ("vs 2024, pp"), and give negatives a `ddelta neg` class. On the firm-size chart,
"All firms (10+)" has no delta while the other three do, leaving an unexplained hole in the
column; either supply the 2021 value or print a muted "n/a".

### 4.5 No hover layer on any server-rendered chart

Per the skill, an HTML/SVG chart should ship a tooltip by default. Only the hero trend chart has
one (app.js:86-94), and even that reports the broad series only, never the floor line drawn
beside it. This is a real gap but ranks below everything above, and the universal CSV download
partially covers the "I need the exact number" case. If only one chart gets a tooltip, make it
the cross-country exposure chart, where 36 rows share one axis.

---

## Severity 5: smaller things, worth a pass

- **The Akavia governance table contradicted the sentence above it. Already fixed mid-review.**
  At the build I reviewed, the prose read "In 2026, 77% used AI at work while only 50% knew of a
  policy" while the table's last row was labelled **May 2025** with exactly 77 / 50 / 38: the
  sentence took its year from `m['year']` and the numbers from `g['use'][-1]`, whose label in
  `data/akavia.yaml:127` is "May 2025". A concurrent session changed `akavia_outcomes_block` to
  use `g["labels"][-1]` (build.py:1398-1403) at 19:53 on 2026-08-01, which is the right shape of
  fix: it removes the class of bug rather than the instance, so the sentence can never drift from
  the table again. The page now reads "In May 2025". **That change is uncommitted in the working
  tree**, along with the rebuilt `docs/monitor/index.html`; it is not mine and I have left it
  alone. Worth committing separately.
- **The Akavia profession bars show no uncertainty**, though the note directly beneath gives
  "communication professionals rest on 80 respondents (71–93% interval)". An 82% bar drawn with
  the same authority as one resting on 1,202 respondents overstates its own precision. Whiskers,
  or at minimum a muted n beside each label.
- **Wage chart labels are too small at half width.** Both wage SVGs sit in a `1fr 1fr` grid, so
  a 640-unit viewBox renders at roughly 520px and 9px ticks land near 7px. The end values
  (132 / 135 / 134) are the only in-chart identification and are the least legible text on the
  page. Direct labels (§1.1) will need a larger `font-size` than the `tick` class provides.
- **Direct labels are painted in the series colour** (`fill="{colour}"` in `vocabulary_svg`,
  `jobquality_svg`, `wages_svg`), against the skill's rule that text wears text tokens and a
  swatch beside it carries identity. Low priority: it is legible, conventional for line-end
  labels, and the contrast is adequate. Note it, do not chase it.
- **The firm-size chart draws the EU all-firm average (19.9) across Swedish size classes.**
  The label is accurate, but comparing an all-firm EU average to a Swedish "250+ employees" bar
  is not like-for-like, and the mean line invites exactly that. Consider labelling it
  "EU, all firms" so the mismatch is on the page.
- **SVGs use `role="img"` plus `aria-label` only**, with no `<title>`/`<desc>` children. Support
  is adequate in current AT, and the fix in §3.2 adds `<title>` to the exports anyway.

---

## Suggested order of work

| # | Fix | Where | Size |
|---|---|---|---|
| 1 | Wage legend colours, then direct-label the terciles | build.py:1512, 1489-1495 | one line, then ~4 |
| 2 | `mean_label` parameter so "EU" stops labelling Swedish figures | build.py:734, 1192, 1378, 1987, 2046 | ~6 lines |
| 3 | Legend under the monthly chart | build.py:994 | one block, copy the hero legend |
| 4 | Mark the 2026 governance bar as a half-year, in-chart | build.py:1084-1088 | ~4 lines |
| 5 | Re-step `.sqlo`/`.dblo` grey to `--c2`, add end labels | assets/styles.css:371,376,387-391 + `squeeze_svg` | ~7 lines |
| 6 | aria-labels: name the measure, drop the phantom change clause | build.py:726, 1192 | ~4 lines |
| 7 | Annotate the −5.3pp gap on the squeeze chart | `squeeze_svg` | ~4 lines |
| 8 | `<title>` and source line in `chart_standalone()` | build.py:1891 | ~3 lines, fixes every export |
| 9 | Server-render the hero trend, or add `<noscript>` | build.py + app.js:39 | larger |
| 10 | Delta column header, true minus, negative styling | build.py:743 | ~3 lines |

Items 1, 2 and 4 change what a reader concludes and should not wait. Items 3, 5 and 6 are the
comprehension and legend core of Magnus's request. Item 8 is the highest leverage per line on
the list, because it repairs every downloadable figure at once.
