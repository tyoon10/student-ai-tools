#!/usr/bin/env python3
"""Validate the shape of data/tools.yml.

This exists because of a real bug. Entries were originally written as YAML flow
mappings:

    - {name: Mem.ai, reason: Invitations are for collaboration, not rewarded referrals.}

The unquoted comma ends the value, so YAML parsed the remainder as a THIRD key
with a null value. The reason silently truncated to "Invitations are for
collaboration", which inverts its meaning, and the truncation was published for
months. Seven entries were affected.

Nothing crashed, so only a shape check catches it. Rules enforced:
  - no key anywhere may have a null value (the phantom-key signature)
  - fixed-shape sections must have exactly their expected keys
  - every tool carries the fields build.py dereferences
  - status and confidence values stay inside their enums
  - dates parse, and links look like URLs

Usage: python3 scripts/check_schema.py
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "tools.yml"

TOOL_REQUIRED = {"id", "name", "offer", "category", "status", "published",
                 "headline", "blurb", "pricing", "features", "length",
                 "verification", "referral", "links", "last_checked", "confidence"}
STATUSES = {"active", "ended", "institutional", "none", "unverified"}
CONFIDENCES = {"high", "medium", "low"}
REFERRAL_STATUSES = {"two-sided", "asymmetric", "campaign-gated", "affiliate-only",
                     "b2b", "discontinued", "none", "unclear"}
RULED_OUT_KEYS = {"name", "reason"}
REFERRAL_KEYS = {"id", "name", "category", "referrer", "referee", "caveats",
                 "link", "confidence"}

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def find_null_keys(node, path: str = "") -> None:
    """A null value almost always means a comma split a flow mapping."""
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{path}.{k}" if path else str(k)
            if v is None:
                err(f"null value at {here!r}. Likely an unquoted comma inside a "
                    f"YAML flow mapping splitting one value into a phantom key.")
            find_null_keys(v, here)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            find_null_keys(item, f"{path}[{i}]")


def check_date(value, where: str) -> None:
    try:
        dt.date.fromisoformat(str(value))
    except ValueError:
        err(f"{where}: {value!r} is not an ISO date (YYYY-MM-DD)")


def check_links(links, where: str) -> None:
    if not links:
        err(f"{where}: no links")
        return
    for u in links:
        if not str(u).startswith("http"):
            err(f"{where}: {u!r} does not look like a URL")


def main() -> int:
    data = yaml.safe_load(DATA.read_text(encoding="utf-8"))

    find_null_keys(data)

    seen_ids: set[str] = set()
    for t in data.get("tools") or []:
        name = t.get("name", "<unnamed>")
        missing = TOOL_REQUIRED - set(t)
        if missing:
            err(f"tool {name!r}: missing {sorted(missing)}")
        if t.get("id") in seen_ids:
            err(f"duplicate tool id {t.get('id')!r}")
        seen_ids.add(t.get("id"))
        if t.get("status") not in STATUSES:
            err(f"tool {name!r}: status {t.get('status')!r} not in {sorted(STATUSES)}")
        if t.get("confidence") not in CONFIDENCES:
            err(f"tool {name!r}: confidence {t.get('confidence')!r} not in {sorted(CONFIDENCES)}")
        ref = t.get("referral") or {}
        if ref.get("status") not in REFERRAL_STATUSES:
            err(f"tool {name!r}: referral.status {ref.get('status')!r} invalid")
        if t.get("status") == "ended" and not t.get("ended_on"):
            err(f"tool {name!r}: status is 'ended' but ended_on is missing")
        pricing = t.get("pricing") or {}
        for k in ("original", "student"):
            if not pricing.get(k):
                err(f"tool {name!r}: pricing.{k} missing")
        check_date(t.get("last_checked"), f"tool {name!r} last_checked")
        check_links(t.get("links"), f"tool {name!r}")

    for section, keyset in (("ruled_out", RULED_OUT_KEYS),
                            ("referral_tools", REFERRAL_KEYS)):
        for e in (data.get(section) or {}).get("entries") or []:
            got = set(e)
            if got != keyset:
                err(f"{section} entry {e.get('name', e)!r}: keys {sorted(got)} "
                    f"!= expected {sorted(keyset)}")

    for c in data.get("cloud_credits") or []:
        check_date(c.get("last_checked"), f"cloud_credit {c.get('name')!r} last_checked")
        check_links(c.get("links"), f"cloud_credit {c.get('name')!r}")
    for e in data.get("excluded") or []:
        check_date(e.get("last_checked"), f"excluded {e.get('name')!r} last_checked")
        check_links(e.get("links"), f"excluded {e.get('name')!r}")

    if errors:
        print(f"FAIL: {len(errors)} schema problem(s) in data/tools.yml:",
              file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    n = (len(data.get("tools") or []) + len(data.get("cloud_credits") or [])
         + len(data.get("excluded") or []))
    print(f"OK: schema valid across {n} dated entries, "
          f"{len(data['ruled_out']['entries'])} ruled-out and "
          f"{len(data['referral_tools']['entries'])} referral entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
