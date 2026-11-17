#!/usr/bin/env python3
"""SCB NV0116M (AI in enterprises): find the newest table and year instead of pinning them.

Why this exists (17 Nov 2026). SCB published the 2026 wave on 5 Nov 2026 in NEW tables,
because the survey moved from SNI 2007 to SNI 2025 industry codes: `AiTeknikerTypN` (SNI
2007) stops at 2025 and `AiTeknikerTypSNI2025` starts at 2026. The refresh scripts asked
the old table for a hard-coded YEAR = "2025", so every Monday re-pulled 2025, passed its
gate and stayed green while the site was a year behind. Magnus found out on stage at
Chalmers, when the next speaker showed the 2026 figure.

So the year and the table are discovered, never typed:

    latest("AiTeknikerTyp")  -> ("AiTeknikerTypSNI2025", 2026)

`latest` looks at every table in the node whose id starts with the prefix, so a further
reclassification (a new `...SNI20xx` table) is picked up the same way. `share_code`
finds the "share of enterprises, percent" content code, which also changed between the
two tables (000007JC -> 000008LC).
"""
import json
import urllib.request

NODE = "https://api.scb.se/OV0104/v1/doris/en/ssd/START/NV/NV0116/NV0116M"
UA = {"User-Agent": "AIEL-monitor (python-urllib; research use)"}


def _get(url, data=None):
    hdr = dict(UA)
    if data is not None:
        hdr["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=hdr), timeout=60) as r:
        return json.load(r)


def tables():
    """Every table in the node: [{'id', 'text', 'updated'}]."""
    return [{"id": t["id"], "text": t["text"], "updated": t.get("updated", "")}
            for t in _get(NODE) if t.get("type") == "t"]


def meta(table):
    """The table's variables, keyed by code: {code: {'values': [...], 'texts': [...]}}."""
    d = _get(f"{NODE}/{table}")
    return {v["code"]: {"values": v["values"], "texts": v["valueTexts"]} for v in d["variables"]}


def years(table):
    return sorted(int(y) for y in meta(table)["Tid"]["values"])


def latest(prefix):
    """(table id, latest year) over all tables whose id starts with `prefix`; ties go to the
    most recently updated table."""
    best = None
    for t in tables():
        if not t["id"].startswith(prefix):
            continue
        y = max(years(t["id"]))
        key = (y, t["updated"])
        if best is None or key > best[0]:
            best = (key, t["id"], y)
    if best is None:
        raise RuntimeError(f"no SCB NV0116M table starts with {prefix!r}")
    return best[1], best[2]


def share_code(m):
    """The content code for 'share of enterprises, percent' in a table's metadata."""
    cc = m["ContentsCode"]
    for code, text in zip(cc["values"], cc["texts"]):
        if text.lower().startswith("share"):
            return code
    raise RuntimeError(f"no share content code among {cc['texts']}")


def values(table, technique, groups, year):
    """{group code: share} for one technique and one year; groups absent from the table are
    skipped rather than requested (SCB answers 400 to an unknown code)."""
    m = meta(table)
    have = [g for g in groups if g in m["Redovisningsgrupp"]["values"]]
    q = {"query": [
        {"code": "TypAvTeknik", "selection": {"filter": "item", "values": [technique]}},
        {"code": "Redovisningsgrupp", "selection": {"filter": "item", "values": have}},
        {"code": "ContentsCode", "selection": {"filter": "item", "values": [share_code(m)]}},
        {"code": "Tid", "selection": {"filter": "item", "values": [str(year)]}}],
        "response": {"format": "json"}}
    out = {}
    for row in _get(f"{NODE}/{table}", q)["data"]:
        v = row["values"][0]
        if v not in ("..", ".", ""):
            out[row["key"][1]] = float(v)
    return out
