# ai-econ-lab.github.io — AI-Econ Lab website

Static site for the AI-Econ Lab, with the **AI in Demand** monitor as the flagship.
Data-driven and auto-updatable (the CV model): edit YAML, run `build.py`, push.

## Purpose
Replace the Google Sites site at `ai-econlab.com` with a git-tracked static site that
carries a proper lab design system and hosts the monitor natively. Domain unchanged;
only the host moves (see `notes/migration-cutover-checklist.md`).

## Build
```bash
python3 build.py          # renders data/ + assets/ -> docs/
```
No dependencies beyond PyYAML. GitHub Pages serves from `main` branch, `/docs` folder.

## Structure
- `data/*.yaml` — all content: `site.yaml` (nav/brand/footer), `papers.yaml`, `people.yaml`, `monitor.yaml`.
- `assets/` — `styles.css` (the design system: navy #232b65 + Okabe–Ito data ramp), `app.js` (theme + chart).
- `build.py` — renders every page + sitemap/robots/CNAME. Edit content in YAML, not in HTML.
- `docs/` — build output (committed; what Pages serves). Do not hand-edit.
- `notes/` — migration checklist and planning docs.

## Update workflow (run order)
1. Edit the relevant `data/*.yaml`.
2. `python3 build.py`
3. `git add -A && git commit -m "…" && git push` → Pages redeploys.
(A `/website` skill will wrap steps 2–3, like `/cv`.)

## Automated freshness (monitor-refresh Action, Mondays 05:17 UTC)
Two tiers, so every source update is captured but nothing publishes unverified:
- **Auto-apply** — `scripts/weekly_refresh.py`: Eurostat firm adoption + SCB
  firm-size adoption are pulled, pass sanity gates (bounds, country counts, the
  wave year must not regress), the site rebuilds and commits. A failed gate
  restores the file from git and turns the run red (GitHub emails).
- **Watchers** — `scripts/check_sources.py`: AI Index (annual, April), DAIOE
  dataset releases, EU-LFS years, SCB AMU waves. A new release opens a GitHub
  issue with the update recipe; state in `scripts/watch_state.json` flags each
  event once. Akavia has no watcher (partner hands the data over): process the
  new wave manually, reconcile with Akavia's published figures, update
  `data/akavia.yaml`, rebuild.
The masthead's "SOURCES CHECKED WEEKLY" claim rests on this Action — remove the
claim if the Action is disabled. When DAIOE becomes an annually auto-updated
index, promote its watcher to the auto-apply tier and sync with its release
cycle (re-export the exposure chart, occupation search and View A weights).

## Deploy / domain
- Preview: `https://ai-econ-lab.github.io` (while `build.emit_cname: false`).
- Go-live: set `build.emit_cname: true`, rebuild, push, then flip DNS at Crossnet
  per `notes/migration-cutover-checklist.md`. Canonical host = `ai-econlab.com`.

## Status
v1 built 2026-07-20. Content ported from the live Google Sites site — **verify papers &
people before the DNS flip**. Explorer URL in `site.yaml` is a placeholder (confirm HF Space).
