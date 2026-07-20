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

## Deploy / domain
- Preview: `https://ai-econ-lab.github.io` (while `build.emit_cname: false`).
- Go-live: set `build.emit_cname: true`, rebuild, push, then flip DNS at Crossnet
  per `notes/migration-cutover-checklist.md`. Canonical host = `ai-econlab.com`.

## Status
v1 built 2026-07-20. Content ported from the live Google Sites site — **verify papers &
people before the DNS flip**. Explorer URL in `site.yaml` is a placeholder (confirm HF Space).
