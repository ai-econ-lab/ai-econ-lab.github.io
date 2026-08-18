#!/usr/bin/env python3
"""
check_links.py — every internal link in the built site must resolve to a built file.

WHY. The job-quality figure offered `job_quality_v11.csv` for download while build.py wrote
`job_quality.csv`: the `_v11` suffix belongs to the SOURCE file in the ai-monitor repo and
leaked into a public href. Every reader who clicked it got a 404, and it stood long enough
for Google Search Console to report "Blocked due to other 4xx issue" against ai-econlab.com
on 7 August 2026. A dead download on a page whose whole pitch is that anyone can check the
work is worse than a missing one.

Nothing could have caught it: check_claims.py polices what the page CLAIMS, not whether what
it offers exists. This is the other half.

Checks every href and src in docs/*.html that points inside the site, plus every <loc> in
sitemap.xml. External links are not fetched: this runs in CI on every build and must not
depend on the network or on someone else's uptime.

Run:  python3 scripts/check_links.py
"""
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

DOCS = Path(__file__).resolve().parent.parent / "docs"

# Emitted by the host, not by build.py, so they are absent from docs/ and are not broken.
ALLOW = {"/CNAME"}


def resolves(path: str) -> bool | None:
    """True/False for a site-internal path; None when the link is not ours to check."""
    path = path.split("#")[0].split("?")[0]
    if not path.startswith("/") or path in ALLOW:
        return None
    rel = path.lstrip("/")
    if not rel:
        rel = "index.html"
    return any(c.exists() for c in (DOCS / rel, DOCS / rel / "index.html",
                                    DOCS / (rel + ".html"),
                                    DOCS / (rel.rstrip("/") + "/index.html")))


def main() -> int:
    if not DOCS.is_dir():
        sys.exit(f"check_links: no built site at {DOCS}. Run build.py first.")
    bad: dict[str, set[str]] = {}
    pages = sorted(DOCS.rglob("*.html"))
    for f in pages:
        html = f.read_text(encoding="utf-8", errors="replace")
        for href in re.findall(r'(?:href|src)="([^"]+)"', html):
            if resolves(href) is False:
                bad.setdefault(href, set()).add(str(f.relative_to(DOCS)))
    sm = DOCS / "sitemap.xml"
    if sm.exists():
        for loc in re.findall(r"<loc>([^<]+)</loc>", sm.read_text(encoding="utf-8")):
            if resolves(urlparse(loc).path) is False:
                bad.setdefault(loc, set()).add("sitemap.xml")
    if bad:
        print(f"check_links: {len(bad)} internal link(s) do not resolve:", file=sys.stderr)
        for href, srcs in sorted(bad.items()):
            print(f"  {href}\n      linked from: {', '.join(sorted(srcs))}", file=sys.stderr)
        return 1
    n = sum(len(re.findall(r'(?:href|src)="/', f.read_text(encoding='utf-8', errors='replace')))
            for f in pages)
    print(f"check_links: {n} internal links across {len(pages)} pages all resolve, "
          f"and every sitemap entry has a file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
