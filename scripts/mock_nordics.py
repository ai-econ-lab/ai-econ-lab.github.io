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
    out = []
    for r in data:
        if r["code"] in keep:
            out.append({**r, "name": r["name"], "is_se": r["code"] == "SE"})
    out.sort(key=lambda r: -r[key])
    return out


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
    exp = rows_from(B.CROSS["countries"], "share")
    ado = rows_from(B.ADOPT["countries"], "adoption")
    szr = sizerows()

    c_exp = B.barplot(exp, 0, 10 * (int(max(r["share"] for r in exp) // 10) + 1),
                      B.CROSS["meta"]["weight_year"], "share", ".0f", what="Nordic countries",
                      mean_label="")
    c_ado = B.barplot(ado, B.ADOPT["meta"]["eu_avg"],
                      10 * (int(max(r["adoption"] for r in ado) // 10) + 1), 0,
                      "adoption", ".0f", what="Nordic countries")
    c_size = B.barplot(szr, 0, 90, 0, "adoption", ".1f", what="country and size class",
                       cmp_key="prev", series_label="2025", cmp_label="2021")

    body = f"""<div class="wrap brief"><article class="briefsheet">
  <header class="bhead"><div>
    <p class="kicker">AIEL MONITOR &middot; MOCK-UP &middot; NORDICS IN DEPTH</p>
    <h1 class="btitle">AI and the labour market, the Nordics</h1>
    <p class="bsub">A mock-up, not a page. What the Monitor would look like if
      &ldquo;in depth&rdquo; meant Sweden, Denmark, Norway, Finland and Iceland.
      Eurostat modules only: no job advertisements, no Akavia.</p>
  </div></header>

  <section class="bsec"><h2 class="bh2">1 &middot; Exposure &mdash; all five, today</h2>
    <p class="bp">Share of employment in the most AI-exposed occupations. Iceland is present,
      which it is not in any other module. Nothing new has to be built: this is
      <code>cross_country.yaml</code> filtered to five rows.</p>
    <div class="bchart">{c_exp}</div>
    <p class="bsrc">Source: Eurostat LFS &times; Eloundou et al. exposure, {B.CROSS['meta']['weight_year']}.</p></section>

  <section class="bsec"><h2 class="bh2">2 &middot; Adoption &mdash; four of five</h2>
    <p class="bp">Enterprises using at least one AI technology. <b>Iceland is absent from
      Eurostat&rsquo;s AI table entirely</b>, so the Nordic set is four here and five above.
      Sweden is third, behind Denmark and Finland.</p>
    <div class="bchart">{c_ado}</div>
    <p class="bsrc">Source: Eurostat isoc_eb_ai, {B.ADOPT['meta']['year']}.</p></section>

  <section class="bsec"><h2 class="bh2">3 &middot; The depth cut that survives: firm size</h2>
    <p class="bp">This is the one Swedish &ldquo;in depth&rdquo; chart that goes Nordic for free.
      Eurostat carries the size classes for all four countries and back to 2021, so the
      September finding can be told four times over. Sweden grew fastest of the four,
      from 9.9% to 35.0% among firms with ten or more employees, a factor of 3.5 against
      Denmark&rsquo;s 1.8, and is still third.</p>
    <div class="bchart">{c_size}</div>
    <p class="bsrc">Source: Eurostat isoc_eb_ai, 2025 against 2021, by size class.</p></section>

  <section class="bsec"><h2 class="bh2">4 &middot; What is missing, and why it matters</h2>
    <p class="bp"><b>Adoption by industry.</b> Eurostat publishes one NACE value only, the
      all-activities aggregate. September&rsquo;s sector chart exists because SCB publishes it
      nationally. There is no Nordic version of it unless DST, SSB and Tilastokeskus each
      publish their own, which is a check nobody has run.</p>
    <p class="bp"><b>Demand, from job advertisements.</b> Sweden only, and deliberately out of
      scope here. This is the module nothing in Eurostat can replace.</p>
    <p class="bp"><b>Outcomes, the entry-level margin.</b> Sweden only, from the registers.</p>
    <p class="bp"><b>The worker survey.</b> Akavia, Sweden only, out of scope here.</p>
    <p class="bp">So a Nordic Monitor built today would be broader and shallower: five countries
      on exposure, four on adoption and firm size, one on everything that makes the Monitor
      worth reading. That is the case for keeping the subtitle until a second country has a
      demand series.</p></section>

  <footer class="bfooter"><span>AI&ndash;Econ Lab &middot; AIEL Monitor &middot; MOCK-UP, not published
    &middot; built {datetime.date.today().isoformat()}</span></footer>
</article></div>"""

    html = B.shell("Nordics in depth (mock-up) · AI-Econ Lab",
                   "A mock-up of the AIEL Monitor with the Nordics in depth.",
                   "/monitor/", body)
    out = ROOT / "build" / "mock" / "nordics-in-depth.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    # The mock lives outside docs/, so the stylesheet's absolute path would not resolve when
    # the file is opened directly. Point it at the built copy instead.
    html = html.replace('href="/assets/', f'href="{ROOT}/docs/assets/')
    html = html.replace('src="/assets/', f'src="{ROOT}/docs/assets/')
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} kB)")


if __name__ == "__main__":
    main()
