#!/usr/bin/env python3
"""Mock-up: the Monitor with the NORDICS in depth instead of Sweden.

    python3 scripts/mock_nordics.py      -> build/mock/nordics-in-depth.html

A mock, not a page. It is written outside docs/ so it can never be published by accident, it
is linked from nothing, and it exists to answer one question: what would the Monitor look like
if "in depth" meant four countries rather than one?

SCOPE, set by ML on 31 Aug 2026: Eurostat modules only. **No job advertisements and no Akavia**,
because neither has a Nordic counterpart. That is the whole point of the exercise: the modules
that can go Nordic today are the ones Eurostat carries, and the modules that make the Monitor
distinctive are exactly the ones that cannot.

It imports build.py for the real chart function and the real stylesheet, so what you see is
what the Monitor would render, not an impression of it.
"""
import datetime, importlib.util, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("aiel_build", ROOT / "build.py")
B = importlib.util.module_from_spec(spec)
sys.modules["aiel_build"] = B
spec.loader.exec_module(B)                      # safe: build.py only builds under __main__

NORDIC = ["SE", "DK", "NO", "FI", "IS"]
SIZE = json.loads((Path("/private/tmp/claude-502/-Users-mslk/"
                        "1f114a64-5308-4ece-9fea-289e87e8d1bd/scratchpad/nordic_size.json")
                   ).read_text(encoding="utf-8"))


def rows_from(data, key, keep=NORDIC):
    """v1 filtered to the five Nordics. That was wrong: it deletes the comparison rather than
    crowding it, because Sweden at 39% means something against 36 countries and much less
    against four. The site's own pattern is the whole distribution with ONE row highlighted;
    this highlights five. One figure, one state, both scopes, and it prints."""
    out = [{**r, "is_se": r["code"] in keep} for r in data]
    out.sort(key=lambda r: -r[key])
    return out


def nordic_only(data, key, keep=NORDIC):
    out = [{**r, "is_se": r["code"] == "SE"} for r in data if r["code"] in keep]
    out.sort(key=lambda r: -r[key])
    return out


def small_multiples(barplot, xmax=90):
    """Four small panels on a shared axis, one per country, instead of one sixteen-row chart.
    Country times size class is where the Nordic version actually gets messy, and the standard
    answer to a category crossed with a country is small multiples, not a longer chart and not
    a toggle."""
    order = [("GE250", "250+"), ("50-249", "50–249"), ("GE10", "All, 10+"), ("10-49", "10–49")]
    panels = []
    for g in ("DK", "FI", "SE", "NO"):
        rows = []
        for code, label in order:
            cur, prev = SIZE["data"].get(code, {}).get(g, (None, None))
            if cur is None:
                continue
            rows.append({"code": code, "name": label, "adoption": round(cur, 1),
                         "prev": None if prev is None else round(prev, 1), "is_se": g == "SE"})
        chart = barplot(rows, 0, xmax, 0, "adoption", ".1f", what="size classes",
                        cmp_key="prev", series_label="2025", cmp_label="2021")
        panels.append(f'<figure style="margin:0"><figcaption class="kicker" '
                      f'style="margin:0 0 4px">{SIZE["geo"][g]}</figcaption>{chart}</figure>')
    # ONE column, not two. At half width barplot's label gutter and value column are fixed
    # pixels inside a 640-unit viewBox, so the text collides with the bars: the chart function
    # has no compact mode. Full-width panels are taller but correct, and a compact mode is the
    # real fix if this ever ships.
    return ('<div style="display:grid;grid-template-columns:minmax(0,1fr);gap:10px">'
            + "".join(panels) + "</div>")


def sizerows():
    order = [("GE250", "250+ employees"), ("50-249", "50–249 employees"),
             ("GE10", "All firms, 10+"), ("10-49", "10–49 employees")]
    per_country = {}
    for code, label in order:
        for g, (cur, prev) in SIZE["data"].get(code, {}).items():
            if cur is None:
                continue
            per_country.setdefault(g, []).append(
                {"code": f"{g}-{code}", "name": f"{SIZE['geo'][g]}, {label}",
                 "adoption": round(cur, 1), "prev": None if prev is None else round(prev, 1),
                 "is_se": g == "SE"})
    rows = []
    for code, label in order:
        for g in ("DK", "FI", "SE", "NO"):
            for r in per_country.get(g, []):
                if r["code"].endswith(code):
                    rows.append(r)
    return rows


def main():
    exp_all, ado_all = rows_from(B.CROSS["countries"], "share"), rows_from(B.ADOPT["countries"], "adoption")
    exp_few, ado_few = nordic_only(B.CROSS["countries"], "share"), nordic_only(B.ADOPT["countries"], "adoption")

    c_exp = B.barplot(exp_all, 0, 10 * (int(max(r["share"] for r in exp_all) // 10) + 1),
                      B.CROSS["meta"]["weight_year"], "share", ".0f", what="countries")
    c_exp_few = B.barplot(exp_few, 0, 10 * (int(max(r["share"] for r in exp_few) // 10) + 1),
                          B.CROSS["meta"]["weight_year"], "share", ".0f", what="Nordic countries",
                          mean_label="")
    c_ado = B.barplot(ado_all, B.ADOPT["meta"]["eu_avg"],
                      10 * (int(max(r["adoption"] for r in ado_all) // 10) + 1), 0,
                      "adoption", ".0f", what="countries")
    c_size_flat = B.barplot(sizerows(), 0, 90, 0, "adoption", ".1f",
                            what="country and size class", cmp_key="prev",
                            series_label="2025", cmp_label="2021")
    c_size_sm = small_multiples(B.barplot)

    body = f"""<div class="wrap brief"><article class="briefsheet">
  <header class="bhead"><div>
    <p class="kicker">AIEL MONITOR &middot; MOCK-UP v2 &middot; NORDICS IN DEPTH</p>
    <h1 class="btitle">Two ways to make it Nordic</h1>
    <p class="bsub">Each figure is shown both ways so the choice is visible. Eurostat modules
      only: no job advertisements, no Akavia. A mock-up, published nowhere.</p>
  </div></header>

  <section class="bsec"><h2 class="bh2">1 &middot; Exposure &mdash; filter, or highlight?</h2>
    <p class="bp"><b>v1 filtered to five rows.</b> Compact, and it throws the comparison away:
      Sweden&rsquo;s 39% means something against thirty-six countries and much less against four.</p>
    <div class="bchart">{c_exp_few}</div>
    <p class="bp"><b>v2 keeps all {len(exp_all)} and highlights the five.</b> This is the
      site&rsquo;s existing pattern with five rows lit instead of one. Both scopes, one figure,
      one state, and it prints. No toggle needed.</p>
    <div class="bchart">{c_exp}</div>
    <p class="bsrc">Source: Eurostat LFS &times; Eloundou et al. exposure, {B.CROSS['meta']['weight_year']}.</p></section>

  <section class="bsec"><h2 class="bh2">2 &middot; Adoption, the same way</h2>
    <p class="bp">{len(ado_all)} countries, the five lit. Iceland is absent from Eurostat&rsquo;s
      AI table entirely, so only four light up here against five above. Sweden is third of the
      Nordics, behind Denmark and Finland, which a five-row chart shows and a
      thirty-three-row chart also shows, with the EU spread as well.</p>
    <div class="bchart">{c_ado}</div>
    <p class="bsrc">Source: Eurostat isoc_eb_ai, {B.ADOPT['meta']['year']}.</p></section>

  <section class="bsec"><h2 class="bh2">3 &middot; Firm size &mdash; where it really does get messy</h2>
    <p class="bp"><b>One chart, sixteen rows.</b> Country crossed with size class. This is the
      figure that prompted the question, and the objection is right.</p>
    <div class="bchart">{c_size_flat}</div>
    <p class="bp"><b>Small multiples, four panels on a shared axis.</b> Same data. The
      within-country gradient is legible again, and the countries stay comparable because the
      axis does not move. This is the standard answer to a category crossed with a country, and
      unlike a toggle it survives print.</p>
    <div class="bchart">{c_size_sm}</div>
    <p class="bsrc">Source: Eurostat isoc_eb_ai, 2025 against 2021, by size class.
      Sweden grew fastest of the four, 9.9% to 35.0% among firms with ten or more employees,
      a factor of 3.5 against Denmark&rsquo;s 1.8, and is still third.</p></section>

  <section class="bsec"><h2 class="bh2">4 &middot; What still cannot go Nordic</h2>
    <p class="bp"><b>Adoption by industry.</b> Eurostat publishes one NACE value, the
      all-activities aggregate. September&rsquo;s sector chart exists because SCB publishes it
      nationally. No Nordic version unless DST, SSB and Tilastokeskus each publish their own.</p>
    <p class="bp"><b>Demand, from job advertisements.</b> Sweden only. Norway is the cheapest
      second country, not Denmark: NAV&rsquo;s feed is open with a free key and claims the
      majority of publicly advertised postings, while Jobnet needs a signed agreement and a
      commercial platform is acknowledged to be bigger in Denmark.</p>
    <p class="bp"><b>Outcomes, the entry-level margin.</b> Sweden only, from the registers.
      <b>The worker survey.</b> Akavia, Sweden only.</p>
    <p class="bp">So the recommendation is unchanged by the redesign: highlight rather than
      filter, small multiples rather than a toggle, and keep &ldquo;Sweden in depth&rdquo; until
      a second country has a demand series.</p></section>

  <footer class="bfooter"><span>AI&ndash;Econ Lab &middot; AIEL Monitor &middot; MOCK-UP v2, not published
    &middot; built {datetime.date.today().isoformat()}</span></footer>
</article></div>"""

    html = B.shell("Nordics in depth, mock-up v2 · AI-Econ Lab",
                   "Two ways to make the AIEL Monitor Nordic, shown side by side.",
                   "/monitor/", body)
    out = ROOT / "build" / "mock" / "nordics-in-depth-v2.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    html = html.replace('href="/assets/', f'href="{ROOT}/docs/assets/')
    html = html.replace('src="/assets/', f'src="{ROOT}/docs/assets/')
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} kB)")


if __name__ == "__main__":
    main()
