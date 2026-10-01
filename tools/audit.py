#!/usr/bin/env python3
"""Crawl the deployed site and audit indexing readiness."""
import json, re, sys, urllib.request, urllib.error, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import os
BASE = os.environ.get("SITE_BASE", "https://paycheck-calculator-2026.okou.app").rstrip("/")

def get(url, method="GET"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "Mozilla/5.0 (compatible; site-audit/1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), ""
    except Exception as e:
        return 0, {"error": str(e)}, ""

def analyse(path):
    url = BASE + path
    status, headers, html = get(url)
    out = {"path": path, "status": status, "xrobots": headers.get("X-Robots-Tag", ""),
           "ctype": headers.get("Content-Type", ""), "cors": headers.get("Access-Control-Allow-Origin", "")}
    if status != 200:
        return out
    def one(pat):
        m = re.search(pat, html, re.S | re.I)
        return m.group(1).strip() if m else ""
    out["title"] = one(r"<title>(.*?)</title>")
    out["desc"] = one(r'<meta name="description" content="(.*?)"')
    out["canonical"] = one(r'<link rel="canonical" href="(.*?)"')
    out["robots_meta"] = one(r'<meta name="robots" content="(.*?)"')
    out["h1"] = len(re.findall(r"<h1[ >]", html, re.I))
    out["h2"] = len(re.findall(r"<h2[ >]", html, re.I))
    out["jsonld_blocks"] = len(re.findall(r'application/ld\+json', html))
    bad = 0
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            json.loads(block)
        except Exception:
            bad += 1
    out["jsonld_invalid"] = bad
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    out["words"] = len([w for w in re.split(r"\s+", text) if w.strip()])
    out["internal_links"] = len(set(re.findall(r'href="([a-z0-9\-]+\.html)"', html)))
    out["imgs_no_alt"] = len(re.findall(r"<img(?![^>]*alt=)", html))
    return out

def main():
    _, _, sm = get(BASE + "/sitemap.xml")
    paths = [u.replace(BASE, "") or "/" for u in re.findall(r"<loc>(.*?)</loc>", sm)]
    with ThreadPoolExecutor(max_workers=12) as ex:
        rows = list(ex.map(analyse, paths))
    json.dump(rows, open("tools/audit-results.json", "w"), indent=1)

    problems = []
    for r in rows:
        p = r["path"]
        if r["status"] != 200:
            problems.append((p, "HTTP " + str(r["status"])))
            continue
        if r["xrobots"] and "noindex" in r["xrobots"].lower():
            problems.append((p, "X-Robots-Tag: " + r["xrobots"]))
        if "noindex" in (r["robots_meta"] or "").lower():
            problems.append((p, "meta robots noindex"))
        if not r["canonical"]:
            problems.append((p, "missing canonical"))
        elif r["canonical"].rstrip("/") != (BASE + ("" if p == "/" else p)).rstrip("/"):
            problems.append((p, "canonical mismatch: " + r["canonical"]))
        if r["h1"] != 1:
            problems.append((p, "h1 count = %d" % r["h1"]))
        if len(r["title"]) > 62:
            problems.append((p, "title %d chars" % len(r["title"])))
        if not (70 <= len(r["desc"]) <= 165):
            problems.append((p, "description %d chars" % len(r["desc"])))
        if r["jsonld_invalid"]:
            problems.append((p, "invalid JSON-LD blocks: %d" % r["jsonld_invalid"]))
        if r["words"] < 250:
            problems.append((p, "thin: %d words" % r["words"]))
        if r["internal_links"] < 5:
            problems.append((p, "only %d internal links" % r["internal_links"]))

    titles = {}
    descs = {}
    for r in rows:
        if r["status"] == 200:
            titles.setdefault(r["title"], []).append(r["path"])
            descs.setdefault(r["desc"], []).append(r["path"])
    dup_titles = {k: v for k, v in titles.items() if len(v) > 1}
    dup_descs = {k: v for k, v in descs.items() if len(v) > 1}

    print("pages crawled:", len(rows))
    print("status codes:", {s: sum(1 for r in rows if r["status"] == s) for s in sorted({r["status"] for r in rows})})
    ws = sorted(r["words"] for r in rows if r["status"] == 200)
    print("words min/median/max:", ws[0], ws[len(ws)//2], ws[-1])
    print("duplicate titles:", len(dup_titles), "| duplicate descriptions:", len(dup_descs))
    print("pages with JSON-LD:", sum(1 for r in rows if r.get("jsonld_blocks")))
    print("\nPROBLEMS (%d):" % len(problems))
    for p, why in problems[:40]:
        print("  ", p, "→", why)
    for k, v in list(dup_titles.items())[:6]:
        print("  DUP TITLE:", k[:60], "→", v[:4])
    for k, v in list(dup_descs.items())[:6]:
        print("  DUP DESC:", k[:60], "→", v[:4])

if __name__ == "__main__":
    main()
