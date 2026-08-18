#!/usr/bin/env python3
"""Check every outbound URL in data/tools.yml.

Vendor help centres routinely block non-browser clients, so a bare 403 is not
evidence of a dead link. This script separates the two:

    BROKEN     404, 410 or 5xx. Real rot. Fails the run.
    BLOCKED    401/403/429. The bot was refused. Reported, does not fail.
    UNREACHED  DNS failure, timeout, connection reset. Reported, does not fail.
    OK         2xx or 3xx.

Usage:
    python3 scripts/check_links.py           # human-readable report
    python3 scripts/check_links.py --md      # markdown, for a CI issue body
"""
from __future__ import annotations

import argparse
import pathlib
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "tools.yml"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
TIMEOUT = 25
BROKEN_CODES = {404, 410}
BLOCKED_CODES = {401, 403, 429}


def collect_urls(node, acc: dict[str, set[str]], label: str = "root") -> None:
    """Walk the YAML tree and map every URL to the entry name it came from."""
    if isinstance(node, dict):
        name = node.get("name") or node.get("id") or label
        for key, value in node.items():
            collect_urls(value, acc, name if key != "meta" else label)
    elif isinstance(node, list):
        for item in node:
            collect_urls(item, acc, label)
    elif isinstance(node, str) and node.startswith("http"):
        acc.setdefault(node.strip().rstrip(".,;:"), set()).add(label)


def probe(url: str) -> tuple[str, int | None, str]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            return "OK", resp.status, ""
    except urllib.error.HTTPError as e:
        if e.code in BROKEN_CODES or e.code >= 500:
            return "BROKEN", e.code, e.reason or ""
        if e.code in BLOCKED_CODES:
            return "BLOCKED", e.code, e.reason or ""
        return "OK", e.code, e.reason or ""
    except Exception as e:  # DNS, TLS, timeout, reset
        return "UNREACHED", None, type(e).__name__


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", action="store_true", help="emit a markdown report")
    args = ap.parse_args()

    data = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    owners: dict[str, set[str]] = {}
    collect_urls(data, owners)

    # The live post URL is aspirational until the draft is promoted to index.md.
    # Skip it while unpublished, but say so rather than hiding the exclusion.
    meta = data.get("meta", {})
    skipped = None
    if not meta.get("live_post_published") and meta.get("live_post") in owners:
        skipped = meta["live_post"]
        owners.pop(skipped)

    urls = sorted(owners)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(probe, urls))

    buckets: dict[str, list[tuple[str, int | None, str]]] = {
        "BROKEN": [], "UNREACHED": [], "BLOCKED": [], "OK": []}
    for url, (state, code, note) in zip(urls, results):
        buckets[state].append((url, code, note))

    if args.md:
        print(f"Checked **{len(urls)}** links from `data/tools.yml`.")
        if skipped:
            print()
            print(f"> Skipped `{skipped}` (meta.live_post): the post is not "
                  f"published yet, so this URL is expected to 404.")
        print()
        print(f"- OK: {len(buckets['OK'])}")
        print(f"- Blocked to bots (not rot): {len(buckets['BLOCKED'])}")
        print(f"- Unreachable: {len(buckets['UNREACHED'])}")
        print(f"- **Broken: {len(buckets['BROKEN'])}**")
        for state in ("BROKEN", "UNREACHED"):
            if buckets[state]:
                print()
                print(f"### {state}")
                for url, code, note in buckets[state]:
                    who = ", ".join(sorted(owners[url]))
                    print(f"- `{code or note}` {url} (used by: {who})")
    else:
        for state in ("BROKEN", "UNREACHED", "BLOCKED"):
            if not buckets[state]:
                continue
            print(f"\n== {state} ({len(buckets[state])}) ==")
            for url, code, note in buckets[state]:
                who = ", ".join(sorted(owners[url]))
                print(f"  {code or note:>10}  {url}  [{who}]")
        if skipped:
            print(f"\nskipped (unpublished live_post, expected 404): {skipped}")
        print(f"\n{len(buckets['OK'])}/{len(urls)} OK, "
              f"{len(buckets['BLOCKED'])} blocked, "
              f"{len(buckets['UNREACHED'])} unreachable, "
              f"{len(buckets['BROKEN'])} broken")

    return 1 if buckets["BROKEN"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
