# AI-Econ Lab — website cutover checklist (Google Sites → GitHub Pages)

Move `ai-econlab.com` from Google Sites to a git-tracked, auto-updatable static site **without changing the public address**. The domain stays; only the backend host moves. Google Site is never deleted — it stays live at `sites.google.com/view/ai-econlab/home` as the parachute throughout.

Prepared 2026-07-20. DNS is managed at **Crossnet** (`gamma/zeta.crossnet.se`).

**Naming — three separate strings, only one is public:**
- Public domain (unchanged, no dash): **`ai-econlab.com`** — the only thing visitors, links and citations ever see.
- GitHub org + Pages host (hidden plumbing, with dashes): `ai-econ-lab` / `ai-econ-lab.github.io` — appears only inside a CNAME record, never public.
- Brand wordmark in text: "AI-Econ Lab".

The org's dashes never leak into the address; the domain stays dashless automatically.

---

## Phase 0 — Decisions (settled)
- [ ] Host: **GitHub Pages**, organisation **`ai-econ-lab`** (not personal `Magnus-L`). Free for public repos.
- [ ] Repo name: **`ai-econ-lab.github.io`** (org root site).
- [ ] Canonical host: **apex** `ai-econlab.com` (GitHub auto-redirects `www` → apex).
- [ ] Parachute: Google Site left published; reachable at `sites.google.com/view/ai-econlab/home`.

## Phase 1 — Build & stage (nothing public changes yet)
- [ ] Create the repo `ai-econ-lab.github.io` under the org, **public**.
- [ ] Build the site (design system + homepage + Research/People/Network/About + native `/monitor`).
- [ ] Add `sitemap.xml`, `robots.txt`, per-page `<title>`/meta/canonical/OG, schema.org JSON-LD (Organization, Person, ScholarlyArticle, Dataset for the monitor).
- [ ] Preserve current slugs where content maps 1:1; add redirects (`jekyll-redirect-from`) for changed paths (e.g. old `/aiel-monitor` → `/monitor`).
- [ ] Test everything at the free URL **`https://ai-econ-lab.github.io`** — links, both themes, mobile, the monitor chart.

## Phase 2 — Verify domain ownership (pre-cutover, no visible change)
- [ ] Org → Settings → Pages → **Verify a domain** → GitHub shows a TXT record.
- [ ] At Crossnet, add TXT: host `_github-pages-challenge-ai-econ-lab`, value = (from GitHub). Confirm "Verified".
- [ ] **Lower TTL** on the apex `A` and `www` `CNAME` records to **300s** (so the flip and any rollback propagate in minutes). Do this ≥1 day before the flip.

## Phase 3 — Snapshot the parachute (run at flip time)
- [ ] Re-capture current live records so rollback values are exact:
  ```
  dig +short A ai-econlab.com ; dig +short CNAME www.ai-econlab.com
  ```
  Expected today: `A 213.132.113.199` · `www CNAME ghs.googlehosted.com`.

## Phase 4 — The flip (Crossnet DNS panel)
Change only these; keep the two `google-site-verification` TXT records.

| Record | Host | Before | After |
|---|---|---|---|
| A | `@` | `213.132.113.199` | `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153` |
| AAAA | `@` | (none) | (optional) `2606:50c0:8000::153`, `…8001::153`, `…8002::153`, `…8003::153` |
| CNAME | `www` | `ghs.googlehosted.com` | `ai-econ-lab.github.io` |

- [ ] Confirm Crossnet allows **four A records on the apex** (if not, use ALIAS/ANAME → `ai-econ-lab.github.io`).
- [ ] Flip at a low-traffic hour.

## Phase 5 — Post-flip
- [ ] Repo → Settings → Pages → **Custom domain = `ai-econlab.com`** (writes the `CNAME` file).
- [ ] Wait for the HTTPS padlock (Let's Encrypt; usually minutes, up to ~24h). Then tick **Enforce HTTPS**.
- [ ] Test: `http://` and `https://`, `www` and apex all resolve to the new site; a few old paths redirect correctly.

## Phase 6 — Indexing / SEO
- [ ] Google Search Console (domain already verified via the existing TXT — no re-verification): **Sitemaps → submit `sitemap.xml`**.
- [ ] Confirm titles/descriptions/canonical render; validate JSON-LD (Rich Results Test).
- [ ] Watch Coverage for 2–4 weeks; check that old URLs consolidate, not 404.

## Rollback (any time)
Restore the two records at Crossnet:
```
A     @     213.132.113.199
CNAME www   ghs.googlehosted.com
```
Propagates within the lowered TTL (~5 min). Google Site is still live throughout.

## Phase 7 — Decommission (only after weeks stable)
- [ ] Optional: unpublish or archive the Google Site (or leave it dormant — it costs nothing).
- [ ] Repeat the whole flow for `magnuslodefalk.com` on the **`Magnus-L`** account (check first where the CV repo lives — it may hold the `Magnus-L.github.io` slot).
