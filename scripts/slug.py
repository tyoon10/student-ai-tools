"""Heading-anchor slugs matching github-slugger.

Both renderers this project targets use github-slugger: Astro assigns heading
ids with it, and GitHub does the same for markdown viewed in the repo. Matching
its behaviour here means a table of contents generated from the data links to
anchors that actually exist in both outputs.

Shared rather than duplicated per script, because two copies of a slug rule is
exactly the kind of drift this repo already got bitten by once.
"""
from __future__ import annotations

import re

_MARKDOWN_EMPHASIS = re.compile(r"\*\*|__|\*|`")
_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# github-slugger strips everything that is not a word char, whitespace or hyphen.
_STRIP = re.compile(r"[^\w\s-]", re.UNICODE)
_SPACES = re.compile(r"\s+")


def slugify(heading: str) -> str:
    """Convert heading *text* (markdown allowed) into its anchor slug."""
    text = _MARKDOWN_LINK.sub(r"\1", heading)
    text = _MARKDOWN_EMPHASIS.sub("", text)
    text = text.strip().lower()
    text = _STRIP.sub("", text)
    return _SPACES.sub("-", text).strip("-")


def verify_anchors(markdown: str, anchors: list[str]) -> list[str]:
    """Return anchors that have no matching heading in *markdown*.

    Guards the table of contents against silently rotting when a heading is
    reworded. Callers should treat a non-empty result as a build failure.
    """
    headings = set()
    for line in markdown.splitlines():
        m = re.match(r"^#{1,6}\s+(.*?)\s*$", line)
        if m:
            headings.add(slugify(m.group(1)))
    return [a for a in anchors if a not in headings]
