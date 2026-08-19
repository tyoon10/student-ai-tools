#!/usr/bin/env python3
"""Fetch vendor logos for the interactive offer grid.

Marks are used to identify the products being reviewed, which is ordinary
editorial use. Each file is fetched from the vendor's own domain and committed
to the site so the published page makes no third-party requests at load time
and leaks no reader data to the vendors.

Resolution order per domain, best first:
    1. <link rel="icon"> / "shortcut icon" / "apple-touch-icon" / "mask-icon"
       declared in the homepage HTML, preferring SVG, then the largest PNG
    2. well-known paths (/favicon.svg, /apple-touch-icon.png, /favicon.ico)

Anything that cannot be sourced cleanly is reported and left out; the grid
falls back to a monogram tile for those, so a missing logo is never a hole.

Usage:
    python3 scripts/fetch_logos.py            # fetch missing only
    python3 scripts/fetch_logos.py --force    # refetch everything
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "tools.yml"
OUT = pathlib.Path(
    "/home/taewan/workspace/initiatives/twyoon-com/repos/site/public/media/logos"
)

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
TIMEOUT = 20
WELL_KNOWN = ["/favicon.svg", "/apple-touch-icon.png", "/apple-touch-icon-precomposed.png",
              "/favicon-192x192.png", "/favicon-96x96.png", "/favicon.png", "/favicon.ico"]
EXT_BY_TYPE = {"image/svg+xml": ".svg", "image/png": ".png",
               "image/x-icon": ".ico", "image/vnd.microsoft.icon": ".ico",
               "image/jpeg": ".jpg", "image/webp": ".webp"}


def get(url: str, timeout: int = TIMEOUT) -> tuple[bytes, str] | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), r.headers.get("Content-Type", "").split(";")[0].strip()
    except Exception:
        return None


def domain_for(entry: dict) -> str:
    if entry.get("logo_domain"):
        return entry["logo_domain"]
    url = (entry.get("links") or [""])[0]
    return urllib.parse.urlparse(url).netloc


def candidates_from_html(domain: str) -> list[str]:
    res = get(f"https://{domain}/")
    if not res:
        return []
    html = res[0].decode("utf-8", "ignore")
    found: list[tuple[int, str]] = []
    for m in re.finditer(r"<link\b[^>]*>", html, re.I):
        tag = m.group(0)
        rel = (re.search(r'rel=["\']([^"\']+)', tag, re.I) or [None, ""])[1].lower()
        if not any(k in rel for k in ("icon", "mask-icon")):
            continue
        href = (re.search(r'href=["\']([^"\']+)', tag, re.I) or [None, ""])[1]
        if not href:
            continue
        sizes = (re.search(r'sizes=["\'](\d+)', tag, re.I) or [None, "0"])[1]
        score = 0
        if href.lower().endswith(".svg") or "svg" in rel:
            score = 10_000
        else:
            score = int(sizes or 0)
            if "apple-touch" in rel:
                score = max(score, 180)
        found.append((score, urllib.parse.urljoin(f"https://{domain}/", href)))
    return [u for _, u in sorted(found, key=lambda x: -x[0])]


def fetch_one(item: tuple[str, str, str]) -> tuple[str, str, str]:
    tool_id, domain, pinned = item
    if pinned:
        urls = [pinned]
    elif not domain:
        return tool_id, "SKIP", "no domain"
    else:
        urls = []
    urls += candidates_from_html(domain) if not pinned else []
    if not pinned:
        urls += [f"https://{domain}{p}" for p in WELL_KNOWN]
    for url in urls:
        res = get(url)
        if not res:
            continue
        body, ctype = res
        if len(body) < 60:
            continue
        ext = EXT_BY_TYPE.get(ctype)
        if not ext:
            guess = pathlib.Path(urllib.parse.urlparse(url).path).suffix.lower()
            ext = guess if guess in {".svg", ".png", ".ico", ".jpg", ".webp"} else None
        if not ext:
            continue
        if ext == ".svg" and b"<svg" not in body[:2000].lower():
            continue
        OUT.mkdir(parents=True, exist_ok=True)
        for old in OUT.glob(f"{tool_id}.*"):
            old.unlink()
        (OUT / f"{tool_id}{ext}").write_bytes(body)
        return tool_id, "OK", f"{ext} {len(body):,}B from {urllib.parse.urlparse(url).netloc}"
    return tool_id, "FAIL", f"no usable icon at {domain}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    data = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    entries = [t for t in data["tools"]
               if t.get("published") and t.get("status") == "active"]
    entries += [c for c in data["cloud_credits"] if c.get("published")]

    todo = []
    for e in entries:
        if not args.force and list(OUT.glob(f"{e['id']}.*")):
            continue
        todo.append((e["id"], domain_for(e), e.get("logo_url", "")))

    if not todo:
        print("all logos already present")
        return 0

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(fetch_one, todo))

    ok = [r for r in results if r[1] == "OK"]
    bad = [r for r in results if r[1] != "OK"]
    for tool_id, status, note in sorted(results):
        print(f"  {status:<5} {tool_id:<22} {note}")
    print(f"\n{len(ok)}/{len(results)} sourced. "
          f"{len(bad)} will fall back to a monogram tile.")
    if bad:
        print("missing: " + ", ".join(t for t, _, _ in bad))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
