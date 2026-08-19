#!/usr/bin/env python3
"""Enforce the freshness rule the README promises.

Anything shown on the public list (published: true) must have been checked
within meta.max_age_days. Backlog entries that never reach the public list are
reported but do not fail the run, so a long research tail cannot block CI.

Usage:
    python3 scripts/check_freshness.py [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "tools.yml"


def entries(data: dict):
    for section in ("tools", "cloud_credits", "excluded"):
        for item in data.get(section) or []:
            if "last_checked" in item:
                yield section, item


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", help="override today's date, for testing")
    args = ap.parse_args()

    data = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    max_age = int(data["meta"]["max_age_days"])
    today = (dt.date.fromisoformat(args.today) if args.today
             else dt.date.today())

    failures, warnings = [], []
    for section, item in entries(data):
        checked = dt.date.fromisoformat(str(item["last_checked"]))
        age = (today - checked).days
        row = (item["name"], section, item["last_checked"], age)
        if age > max_age:
            (failures if item.get("published") else warnings).append(row)

    if warnings:
        print(f"stale but not published ({len(warnings)}), not blocking:")
        for name, section, checked, age in sorted(warnings, key=lambda r: -r[3]):
            print(f"  {age:>4}d  {name} [{section}] last checked {checked}")
        print()

    if failures:
        print(f"FAIL: {len(failures)} published entr"
              f"{'y is' if len(failures) == 1 else 'ies are'} older than "
              f"{max_age} days:", file=sys.stderr)
        for name, section, checked, age in sorted(failures, key=lambda r: -r[3]):
            print(f"  {age:>4}d  {name} [{section}] last checked {checked}",
                  file=sys.stderr)
        print("\nRe-verify against the vendor page, then bump last_checked in "
              "data/tools.yml and rebuild.", file=sys.stderr)
        return 1

    total = sum(1 for _ in entries(data))
    print(f"OK: all {total} dated entries within the {max_age}-day rule "
          f"(as of {today}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
