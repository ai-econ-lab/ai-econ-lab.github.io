# Session Pickup — 2026-07-21 18:00
**Project:** AI-Econ Lab website / AIEL Monitor (`websites/ai-econ-lab.github.io/`, repo `ai-econ-lab/ai-econ-lab.github.io`, GitHub Pages `main` `/docs`, LIVE at https://ai-econ-lab.github.io/)

## Where We Were
Just finished **item 1 — the "Working conditions & AI exposure" module** (first module built the new way, with a working gender lens), and Magnus said **"go ahead with the overview-first and reframe retrofit."** That is the next build. It's structural, not new content: give the Monitor an **overview-first landing** and reorganise the existing charts into the **4-module spine × cross-cutting lenses** pattern, with **Geography defaulting to World** (which is the Sweden→international reframe, item 6).

## The design to implement (LOCKED — see memory `reference_monitor_ia.md`, blueprint artifact 1abb98cf)
- **Overview-first landing:** the Monitor front page = 4 headline numbers + trend + freshness, one per module, each a door (anchor) into the module. Whole picture in ~20s; detail one click down.
- **Spine = 4 modules, stays four:** Exposure · Demand · Adoption · Outcomes. Sticky sub-nav. Existing work slots in (skills → Demand; canaries + working-conditions → Outcomes; DAIOE keeps its own page as the measure).
- **Lenses (per-module, only where data supports, 2–4 per screen):** Geography (default **World** → international-first, **Sweden = depth cut**), Gender, Education, Age; Sector/Firm-size where data has them; **blue/white-collar = grouping/colour, NOT a filter**.
- **Module template:** kicker → question → lens bar → headline chart → "Sweden, in depth" panel → source (variant+year) + downloads. (Working-conditions module is the reference implementation.)

## Key Files
- `build.py` — the whole site. Monitor is `monitor()`; home is `home()`. Current monitor order: hero → "What the monitor tracks" (modules list from `monitor.yaml`) → AI-in-Demand module (+figfooter) → segmentation preview → Occupations Explorer → **`cross_country_section()`** (Views A/B/C) → **`working_conditions_section()`** → method. Reusable: `figfooter()`, `dumbbell_svg()`, `barplot()`/`dotplot()` (`.rankchart`), `chart_standalone()`, `assetv()` (cache-bust), `emit_data()` (CSVs/SVGs).
- **Module/lens PATTERN to copy:** `working_conditions_section()` + `dumbbell_svg()` + the `.lensmod`/`.lensbar2`/`.gbtn`/`.dumb.on` markup + the lens-toggle IIFE in `assets/app.js`. New lensed modules follow this (server-render one chart variant per lens value, JS toggles `.on`).
- `data/monitor.yaml` — modules list, tiles, trend, segmentation, aiindemand_lede, headline, lede. Overview numbers can come from here + the cross-country/working-conditions yamls.
- `data/{cross_country,cross_country_adoption,cross_country_demand,working_conditions}.yaml` — the new module data (+ their `scripts/refresh_*.py`).
- `assets/styles.css` — design system; new blocks appended near the bottom (dotplot/barplot/dumbbell/lens/figfoot/conf2028/yearblock/nlinks).
- `assets/app.js` — theme toggle, email de-obfuscation, chart JS (trend/beeswarm/occ-search), **lens toggle**.

## Exact Next Steps (in order)
1. **Overview landing.** Add an `overview()` block near the top of `monitor()` (after the hero, likely replacing/absorbing the "What the monitor tracks" list): 4 stat cards — **Exposure · Demand · Adoption · Outcomes** — each a headline number + freshness + `<a href="#anchor">`. Reuse the `.tile`/`.prod` card CSS. Numbers: exposure (a DAIOE headline, e.g. "economists p78"), demand (AI-in-Demand latest ≈2.1%), adoption (Eurostat SE 35% 2025), outcomes (entry-level −5.5% or the working-conditions active-job line).
2. **Reframe the hero + strip international-first.** Hero currently "…the Swedish labour market." Change to: "how AI is reshaping work — internationally, via a portable measure (DAIOE) and public data, and in unusual depth for Sweden (registers + job ads + work environment)." The registration strip's JobTech becomes one source among several. Name the company kept (AI Index, Eurostat, LISER/SkiLMeeT).
3. **Group into the 4-module spine** with consistent section headers + a sticky sub-nav (Exposure/Demand/Adoption/Outcomes). Put the cross-country views under their families (exposure View A under Exposure; adoption View B under Adoption; demand View C under Demand); Occupations Explorer + working-conditions + (future canaries) under Outcomes. Each Sweden-only chart gets framed as the "Sweden, in depth" cut.
4. Verify (screenshot the overview + a retrofitted module, light+dark), commit, push, confirm Pages build.

## Context the Next Session Needs
- **Build/deploy recipe:** edit YAML/`build.py` → `python3 build.py` → `git add -A && git commit` (**author MUST be noreply `12813525+Magnus-L@users.noreply.github.com`** — Gmail is push-blocked) → `git push` → org Pages rebuilds in ~1 min (poll `gh api repos/ai-econ-lab/ai-econ-lab.github.io/pages/builds/latest`) → verify live. CSS/JS are cache-busted with `?v=<md5>` via `assetv()` — critical, or returning visitors see stale styles.
- **Hard rules:** every DAIOE figure states variant (generative-AI) + year (v2023); every stat states its year; freshest data always (refresh scripts exist for cross-country/working-conditions). No dashes in prose (house style). British spelling. Exposure ≠ displacement (descriptive framing).
- **Strategy frame:** keep the monitor public-data/positioning, NOT a heavy funded build (AFA strategy doc). Gender + age = the *Same Storm* "different boats" heterogeneity lenses.
- **DNS:** personal-site cutover emailed to Crossnet (watcher running); lab cutover on hold per Magnus. Don't flip lab DNS.
- Don't over-scale — Magnus's worry is overwhelm; the IA (spine + lenses + overview) is the answer, so retrofit into it rather than appending more loose sections.

## Pickup Prompt
Paste this to resume:

> Read SESSION_PICKUP.md in websites/ai-econ-lab.github.io/. We were interrupted mid-session (auto-compact). Pick up the AIEL Monitor **overview-first landing + reframe retrofit**, starting with step 1 (the overview landing block in build.py's monitor()). Follow the locked IA in memory reference_monitor_ia.md.
