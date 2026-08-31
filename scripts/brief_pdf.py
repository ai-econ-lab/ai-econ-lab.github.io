#!/usr/bin/env python3
"""Render a built brief page to a real PDF.

    python3 scripts/brief_pdf.py                       # both languages, current month
    python3 scripts/brief_pdf.py --month 2026-09       # a specific issue

Why this exists (31 Aug 2026). The brief's "Download PDF" button calls the reader's own print
dialogue, so no PDF ever existed as a file: it could not be attached to the review mail, read on
a phone, or archived. ML asked for the PDF in the same mail as the draft, on the reasoning that
checking a brief means seeing what people will print.

It renders the built page rather than re-typesetting it, so the PDF IS the page: same charts,
same layout, and the print stylesheet at assets/styles.css line ~572 already hides the masthead,
the buttons and the site footer. That stylesheet also now carries `@page { size: A4 }`, because
Chrome's headless default is US letter.

The page is served over HTTP, not opened as file://, because it links its stylesheet by absolute
path (/assets/styles.css). Opened from disk that link resolves to the filesystem root and the PDF
comes out completely unstyled, which is a silent failure: you get a plausible two-page document
with none of the design.
"""
import argparse, functools, http.server, os, socketserver, subprocess, sys, tempfile, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = next((p for p in [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome", "/usr/bin/chromium",
] if Path(p).exists()), None)


def serve(directory):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", help="YYYY-MM; rebuilds the site for that issue first")
    # NOT docs/: build.py does `shutil.rmtree(OUT)` at the top of every run, so anything
    # written into docs/ by a separate script disappears on the next build. The one-pager
    # survives only because build.py generates it itself. Discovered the hard way, 31 Aug 2026.
    ap.add_argument("--outdir", default=str(ROOT / "build" / "briefs"))
    a = ap.parse_args()

    if not CHROME:
        raise SystemExit("brief_pdf: no Chrome or Chromium found. This is a MISSING TOOL, not a "
                         "reason to ship the brief without its PDF.")

    if a.month:
        env = {**os.environ, "BRIEF_MONTH_OVERRIDE": a.month}
        subprocess.run([sys.executable, "build.py"], cwd=ROOT, env=env, check=True,
                       stdout=subprocess.DEVNULL)

    docs = ROOT / "docs"
    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    httpd, port = serve(docs)
    stamp = (a.month or "current").replace("-", "")
    written = []
    try:
        for lang, rel in [("en", "monitor/brief/index.html"), ("sv", "monitor/brief/sv/index.html")]:
            if not (docs / rel).exists():
                continue
            out = Path(a.outdir) / f"aiel-monitor-brief-{stamp}{'' if lang == 'en' else '-sv'}.pdf"
            # Chrome writes the PDF and then does NOT exit in this mode, so a plain
            # subprocess.run blocks for ever and the second language never renders. Give it a
            # deadline and judge by the artefact: if the file is there, the render worked.
            with tempfile.TemporaryDirectory() as td:
                if out.exists():
                    out.unlink()
                cmd = [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                       "--virtual-time-budget=10000", f"--user-data-dir={td}",
                       f"--print-to-pdf={out}", f"http://127.0.0.1:{port}/{rel}"]
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Poll for the artefact rather than for the process. Waiting on the process hangs
                # for the full timeout every time, which turned a 40-second job into minutes and
                # meant the second language never ran.
                for _ in range(90):
                    time.sleep(1)
                    if out.exists() and out.stat().st_size > 50_000:
                        break
                proc.kill()
                proc.wait()
                if not out.exists():
                    raise SystemExit(f"brief_pdf: Chrome produced no file for {lang}.")
            info = subprocess.run(["pdfinfo", str(out)], capture_output=True, text=True).stdout
            pages = next((l.split()[1] for l in info.splitlines() if l.startswith("Pages:")), "?")
            size = next((l for l in info.splitlines() if l.startswith("Page size:")), "")
            # An unstyled render is the failure this script exists to prevent, and it is silent:
            # a page with no stylesheet still produces a valid PDF. The styled brief is 3-6 pages
            # and A4; the unstyled one is 2 and letter. Fail loudly rather than attach it.
            if "595" not in size:
                raise SystemExit(f"brief_pdf: {out.name} came out {size.strip()}, not A4. The "
                                 f"stylesheet almost certainly did not load.")
            written.append(out)
            print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size/1024:.0f} kB, {lang}, "
                  f"{pages} pages, {size.split(':',1)[1].strip()})")
    finally:
        httpd.shutdown()
    if not written:
        raise SystemExit("brief_pdf: nothing rendered; build the site first.")


if __name__ == "__main__":
    main()
