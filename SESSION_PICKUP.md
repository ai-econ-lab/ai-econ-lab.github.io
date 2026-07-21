# Session Pickup — 2026-07-21 (retrofit shipped)
**Project:** AI-Econ Lab website / AIEL Monitor (`websites/ai-econ-lab.github.io/`, repo `ai-econ-lab/ai-econ-lab.github.io`, GitHub Pages `main` `/docs`, LIVE at https://ai-econ-lab.github.io/)

## DONE + LIVE — overview-first landing + reframe into the 4-module spine (commit 035bf51)
The IA retrofit (locked blueprint `reference_monitor_ia.md`) is built, verified light+dark, pushed, and Pages-built:
- **Overview landing** (`stat_overview()`): four stat 'doors' — Exposure #2/36 · Demand 2.1% · Adoption 35% · Outcomes -5.3pp — each a headline number + freshness + anchor. Replaces the old "What the monitor tracks" list. Data in `monitor.yaml` `overview:`.
- **Spine** = Exposure · Demand · Adoption · Outcomes. `cross_country_section()` split into `exposure_section()` / `demand_section()` / `adoption_section()`; `working_conditions_section()` → `working_conditions_block()` now nested under Outcomes with the Occupations Explorer and the entry-level-squeeze preview. Each module leads with an international-first chart and carries a "Sweden, in depth" panel (`.depth`).
- **Sticky sub-nav** (`subnav()` + scrollspy in app.js): active module via IntersectionObserver; `--mast-h` measured so it pins under the variable-height masthead. `main [id]{scroll-margin-top:196px}` clears the 187px sticky chrome (verified: jumped kicker lands at 263px).
- **Hero reframed** international-first; trend panel relabelled the Swedish depth measure; registration strip multi-source (JobTech · Eurostat · AI Index · SCB · EU-LFS). Method section names all public sources.
- Backward-compatible anchors kept (`#ai-in-demand`, `#occupations-explorer`, `#working-conditions`). All figure CSV/SVG downloads emit as before.

### One verification note (not a bug)
Anchor jumps rely on the pre-existing `html{scroll-behavior:smooth}`. The automation Chrome used to verify silently DROPS all CSS-smooth scrolls (reduced-motion was off; only `behavior:'instant'` moved). With `scroll-behavior:auto` forced, native hash-nav lands perfectly (scrollY 4577, kicker 263px). So real browsers are fine; this was an automation-only quirk, and it is pre-existing, not introduced here.

## PENDING NEXT (from the IA + BUILD-view-a-item10)
- **Per-module Geography lens toggle** (literal World↔Sweden switch) where data supports it — the reframe is currently achieved *structurally* (international-first order + "Sweden, in depth" panels), which satisfies item-6; a toggle widget like the working-conditions Gender lens is the next increment, not required by this retrofit.
- **View B / Adoption depth**: a Swedish firm/worker AI-adoption chart from SCB (currently a roadmap note in the Adoption "Sweden, in depth" panel).
- **AI-in-Demand across countries** (book Fig 8 is already View C/Demand headline; consider deepening).
- Age lens (Same-Storm "different boats"); entry-level squeeze full series (wire the `lab-infrastructure/ai-monitor` `entry_level_squeeze.csv` in); monitor.yaml refresh after next pipeline rerun; 2 missing lab abstracts; TIISA 2021 programme; **lab DNS cutover on hold per Magnus — do NOT flip.** (Personal-site DNS for magnuslodefalk.com now points to Pages, per the watcher.)

## Build/deploy recipe
edit YAML/`build.py` → `python3 build.py` → `git add -A && git commit` (**author MUST be noreply `12813525+Magnus-L@users.noreply.github.com`** — already the repo default; Gmail is push-blocked) → `git push` → org Pages rebuilds ~1 min (poll `gh api repos/ai-econ-lab/ai-econ-lab.github.io/pages/builds/latest`) → verify live. CSS/JS cache-busted with `?v=<md5>` via `assetv()`.

## Hard rules
Every DAIOE figure states variant (generative-AI) + year (v2023); every stat states its year; no dashes in prose (house style); British spelling; exposure ≠ displacement (descriptive framing). Don't over-scale: retrofit into the spine + lenses + overview, never add a loose section or a new page.
