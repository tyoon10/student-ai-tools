#!/usr/bin/env python3
"""Generate recommended.md and knowledge-base.md from data/tools.yml.

Usage:
    python3 scripts/build.py           # write the files
    python3 scripts/build.py --check   # exit 1 if the files are out of date

data/tools.yml is the only hand-edited source of tool facts. Editing the
generated markdown directly will be reverted by the next build, and CI will
fail the drift check.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "tools.yml"
RECOMMENDED = ROOT / "recommended.md"
KNOWLEDGE_BASE = ROOT / "knowledge-base.md"

BANNER = (
    "<!-- GENERATED FILE. Do not edit by hand.\n"
    "     Source: data/tools.yml   Rebuild: python3 scripts/build.py -->\n"
)

# Tiers that earn a full write-up in recommended.md rather than a one-line bullet.
FULL_ENTRY_TIERS = ("S", "A", "B")

TIER_LABELS = {
    "S": ("Tier S", "Ubiquitous, mainstream AI tools"),
    "A": ("Tier A", "Major, widely adopted tools"),
    "B": ("Tier B", "Category leaders in popular niches"),
    "C": ("Tier C", "Specialty and growing"),
    "D": ("Tier D", "Niche, lower general awareness"),
}


def clean(text) -> str:
    """Collapse folded-scalar whitespace into a single line."""
    if text is None:
        return ""
    return " ".join(str(text).split())


def links_block(urls, indent="- ") -> list[str]:
    return [f"{indent}{u}" for u in (urls or [])]


# ---------------------------------------------------------------------------
# recommended.md
# ---------------------------------------------------------------------------

def build_recommended(d: dict) -> str:
    meta = d["meta"]
    tools = d["tools"]
    out: list[str] = [BANNER]

    out.append("# AI Tools Worth Setting Up Today (with Student Benefit)")
    out.append("")
    live_dates = [t["last_checked"] for t in tools if t.get("published")]
    live_dates += [c["last_checked"] for c in d["cloud_credits"] if c.get("published")]
    span = (f"on {min(live_dates)}" if min(live_dates) == max(live_dates)
            else f"between {min(live_dates)} and {max(live_dates)}")
    out.append(
        "The AI tools I actually use, plus a curated secondary list. "
        f"Every offer on this list was checked against the vendor's own pages {span}."
    )
    out.append("")
    out.append(f"- **Last refreshed:** {meta['last_full_review']}")
    out.append("- **Full research notes:** [knowledge-base.md](./knowledge-base.md)")
    out.append(f"- **Live post:** [twyoon.com/post/student-ai-tools]({meta['live_post']})")
    out.append(f"- **Disclosure:** {clean(meta['affiliate_policy'])}")
    out.append("")
    out.append("---")
    out.append("")
    out.append(
        "Summer is the best time of year to build, learn and try new tools. "
        "It is also the moment to lock in every student-only AI offer you can, "
        "especially if you are graduating."
    )
    out.append("")
    out.append(
        "> **If you are a graduating student, move fast.** Most of these offers verify "
        "against your .edu email or active student status. The day you lose either, "
        "you lose the offer."
    )
    out.append("")

    # Urgency framing, driven by whatever is actually in `ended` state.
    ended = [t for t in tools + d["excluded"] if t.get("status") == "ended"]
    out.append(
        "There is a bigger pattern at work. AI tools open free or deeply discounted "
        "student plans early to drive adoption, then quietly close the door once they "
        f"have enough traction. {_number_word(len(ended)).capitalize()} "
        f"{'offer' if len(ended) == 1 else 'offers'} tracked here "
        f"{'has' if len(ended) == 1 else 'have'} already gone that way:"
    )
    out.append("")
    for t in sorted(ended, key=lambda x: x.get("ended_on", "")):
        out.append(
            f"- **{t['name']}** closed on **{t.get('ended_on', 'an unannounced date')}**. "
            f"{clean(t.get('reason') or t.get('blurb'))}"
        )
    out.append("")
    out.append("So claim the live ones today, while they are still live.")
    out.append("")
    out.append("---")
    out.append("")

    # Daily use
    daily = sorted(
        [t for t in tools if t.get("daily_use") and t["status"] == "active"],
        key=lambda t: t.get("rank", 99),
    )
    out.append(f"## The {_number_word(len(daily))} I actually use every day")
    out.append("")
    out.append("Tried, used extensively, kept.")
    out.append("")
    for i, t in enumerate(daily, 1):
        out.extend(_recommended_entry(t, f"{i}. {t['name']} ({t['headline']})"))
    out.append("---")
    out.append("")

    # Worth knowing about: active, published, not daily use, top two tiers.
    secondary = [
        t for t in tools
        if t["status"] == "active" and t.get("published") and not t.get("daily_use")
        and t.get("tier") in FULL_ENTRY_TIERS
    ]
    secondary.sort(key=lambda t: FULL_ENTRY_TIERS.index(t["tier"]))
    out.append("## Worth knowing about")
    out.append("")
    out.append("Strong offers, just not in my daily stack.")
    out.append("")
    for t in secondary:
        out.extend(_recommended_entry(t, f"{t['name']} ({t['headline']})"))

    # Compact remainder
    rest = [
        t for t in tools
        if t["status"] == "active" and t.get("published") and not t.get("daily_use")
        and t.get("tier") not in FULL_ENTRY_TIERS
    ]
    if rest:
        out.append("### The rest")
        out.append("")
        for t in rest:
            out.append(
                f"- **{t['name']}** ({t['headline']}). {clean(t['blurb'])} {t['links'][0]}"
            )
        out.append("")

    # Cloud credits
    out.append("### Cloud credits")
    out.append("")
    for c in d["cloud_credits"]:
        out.append(f"- **{c['name']}** ({c['headline']}). {clean(c['student'])} {c['links'][0]}")
    out.append("")
    out.append("---")
    out.append("")

    # Recently closed
    if ended:
        out.append("## Recently closed (kept here on purpose)")
        out.append("")
        out.append(
            "Offers are removed from the live list but not deleted from the record. "
            "Knowing an offer is gone is as useful as knowing one exists."
        )
        out.append("")
        for t in sorted(ended, key=lambda x: x.get("ended_on", ""), reverse=True):
            out.append(f"### {t['name']} (closed {t.get('ended_on', 'date unknown')})")
            out.append("")
            out.append(clean(t.get("reason") or t.get("blurb")))
            out.append("")
            for cav in t.get("caveats") or []:
                out.append(f"- {clean(cav)}")
            if t.get("length"):
                out.append(f"- Existing subscribers: {clean(t['length'])}")
            out.append(f"- Source: {t['links'][0]}")
            out.append("")
        out.append("---")
        out.append("")

    # Not on the list
    out.append("## What is *not* on this list (and why)")
    out.append("")
    for e in d["excluded"]:
        if e.get("status") == "ended":
            continue
        line = f"- **{e['name']}**. {clean(e['reason'])}"
        if e.get("individual_routes"):
            line += f" {clean(e['individual_routes'])}"
        elif e.get("detail"):
            line += f" {clean(e['detail'])}"
        if e.get("check_path"):
            line += f" {clean(e['check_path'])}"
        out.append(line)
    unresolved = d.get("unresolved") or []
    if unresolved:
        names = ", ".join(u["name"] for u in unresolved)
        out.append(
            f"- **{names}**. Dropped. Official student terms could not be confirmed after "
            "more than three months of trying, so they are excluded rather than listed "
            "on a maybe."
        )
    out.append("")
    out.append("---")
    out.append("")

    out.append("## How to verify anything here")
    out.append("")
    out.append("1. **Click the official link.** These are help-centre and pricing pages, not deal-aggregator sites.")
    out.append(f"2. **Check the refresh date at the top.** If it is more than {meta['max_age_days']} days old, re-verify before sharing.")
    out.append("3. **Try SheerID, Student Beans or UNiDAYS directly** if you are hunting beyond this list. Many discounts route through them.")
    out.append("")
    out.append("---")
    out.append("")

    out.append("## Changelog")
    out.append("")
    for block in d["changelog"]:
        for entry in block["entries"]:
            out.append(f"- **{block['date']}** {clean(entry)}")
    out.append("")
    out.append("---")
    out.append("")
    out.append(
        f"*Maintained by {meta['maintainer']}. Source repo: [github.com/tyoon10/student-ai-tools]({meta['repo']}). "
        "Spot something out of date? Open an issue.*"
    )
    out.append("")
    return "\n".join(out)


def _recommended_entry(t: dict, heading: str) -> list[str]:
    out = [f"### {heading}", ""]
    out.append(clean(t["blurb"]))
    out.append("")
    out.append(f"- Sign up: {t['links'][0]}")
    out.append(f"- Verification: {clean(t['verification'])}")
    if t.get("length"):
        out.append(f"- Length: {clean(t['length'])}")
    if t.get("regions"):
        out.append(f"- Eligibility: {clean(t['regions'])}")
    for cav in t.get("caveats") or []:
        out.append(f"- Note: {clean(cav)}")
    out.append("")
    img = t.get("image")
    if img:
        out.append(f"![{img['alt']}]({img['src']})")
        out.append("")
        out.append(f"*{clean(img['caption'])}*")
        out.append("")
    return out


def _number_word(n: int) -> str:
    return {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
            6: "six", 7: "seven", 8: "eight"}.get(n, str(n))


# ---------------------------------------------------------------------------
# knowledge-base.md
# ---------------------------------------------------------------------------

def build_knowledge_base(d: dict) -> str:
    meta = d["meta"]
    out: list[str] = [BANNER]

    out.append("# Student AI Tools: Knowledge Base")
    out.append("")
    out.append(
        "The full working record behind the public list. Every tool evaluated, with "
        "claim records and verification notes. The curated public list lives in "
        "[recommended.md](./recommended.md)."
    )
    out.append("")
    out.append(f"- **Last full review:** {meta['last_full_review']}")
    out.append(f"- **Previous reviews:** {', '.join(meta['previous_reviews'])}")
    out.append("- **Source of truth:** `data/tools.yml`. This file and `recommended.md` are both generated from it, so the two can no longer drift apart.")
    out.append(f"- **Disclosure:** {clean(meta['affiliate_policy'])}")
    out.append("")

    out.append("## Per-entry schema")
    out.append("")
    out.append("For each validated tool:")
    out.append("")
    for i, line in enumerate([
        "**Status**: active, ended, institutional, none or unverified.",
        "**Offered tier and pricing**: original price against student price.",
        "**Included features**: what the student tier actually unlocks.",
        "**Effective length**: duration, renewal behaviour, re-verification cadence.",
        "**Verification method**: SheerID, .edu email, GitHub Education and so on.",
        "**Regions**: where the offer is claimable, when the vendor restricts it.",
        "**Caveats**: the things that bite people.",
        "**Referral programme**: whether one exists and who benefits. Recorded as a fact about the tool, not as a prompt to share a link.",
        "**Official source links**: direct help-centre or pricing URLs.",
        "**Last checked** and **Confidence**.",
    ], 1):
        out.append(f"{i}. {line}")
    out.append("")

    # Tier ranking
    out.append(f"## Popularity tier ranking ({meta['last_full_review']})")
    out.append("")
    out.append(
        "Ranked by general 2026 mindshare weighted toward grad-student relevance. This "
        "ordering drives what makes the short list. Tier does not track student-offer "
        "quality, which is a separate axis: some Tier S tools have weak offers and some "
        "Tier C tools have very strong ones."
    )
    out.append("")
    out.append("Scope: tools with a validated or formerly validated student offer. Referral-only tools sit on their own axis further down and never compete for a slot here.")
    out.append("")
    n = 1
    for tier in ("S", "A", "B", "C", "D"):
        members = [t for t in d["tools"] if t.get("tier") == tier]
        members += [e for e in d["excluded"] if e.get("tier") == tier]
        if not members:
            continue
        label, desc = TIER_LABELS[tier]
        out.append(f"### {label}: {desc}")
        for t in members:
            note = ""
            if t["status"] == "ended":
                note = f" *Offer closed {t.get('ended_on', '')}.*"
            elif t["status"] == "institutional":
                note = " *Institutional access only.*"
            out.append(f"{n}. **{t['name']}**: {clean(t.get('blurb') or t.get('reason'))[:160]}{note}")
            n += 1
        out.append("")

    # Full entries
    out.append("## Individual-claimable offers")
    out.append("")
    for t in d["tools"]:
        out.extend(_kb_entry(t))

    out.append("## AI-adjacent cloud credits")
    out.append("")
    for c in d["cloud_credits"]:
        out.append(f"### {c['name']}")
        out.append("")
        out.append(f"- Status: {c['status']}")
        out.append(f"- Student offer: {clean(c['student'])}")
        if c.get("extras"):
            out.append(f"- Also included: {clean(c['extras'])}")
        out.append(f"- Effective length: {clean(c['length'])}")
        out.append(f"- Verification: {clean(c['verification'])}")
        out.append(f"- Referral programme: **{c['referral']['status']}**. {clean(c['referral']['detail'])}")
        out.append("- Sources:")
        out.extend(links_block(c["links"], indent="  - "))
        out.append(f"- Last checked: {c['last_checked']} | Confidence: {c['confidence']}")
        out.append("")

    out.append("## Excluded: institutional only, or no student offer")
    out.append("")
    for e in d["excluded"]:
        out.append(f"### {e['name']}")
        out.append("")
        out.append(f"- Status: {e['status']}")
        out.append(f"- Reason: {clean(e['reason'])}")
        if e.get("detail"):
            out.append(f"- Detail: {clean(e['detail'])}")
        if e.get("individual_routes"):
            out.append(f"- Individual routes: {clean(e['individual_routes'])}")
        if e.get("check_path"):
            out.append(f"- Check path: {clean(e['check_path'])}")
        out.append("- Sources:")
        out.extend(links_block(e["links"], indent="  - "))
        out.append(f"- Last checked: {e['last_checked']} | Confidence: {e['confidence']}")
        out.append("")

    out.append("## Dropped: unresolved after repeated attempts")
    out.append("")
    out.append(
        "These sat in a pending state for more than three months. A maybe is worse than "
        "an omission on a list people act on, so they are out until a vendor publishes "
        "terms or confirms them in writing."
    )
    out.append("")
    for u in d["unresolved"]:
        out.append(f"- **{u['name']}** (opened {u['opened']}). {clean(u['reason'])} {clean(u['resolution'])}")
    out.append("")

    # Referral axis
    rt = d["referral_tools"]
    out.append(f"## Peer-referral programmes (secondary axis, audited {rt['audited']})")
    out.append("")
    out.append(
        "A separate audit targeting tools where both parties receive a defined benefit. "
        "These are **not** validated for student discounts, so they do not appear on the "
        "public list. Recorded here as reference, not as a recommendation to farm credits."
    )
    out.append("")
    out.append(f"**Bar to qualify:** {clean(rt['bar'])}")
    out.append("")
    out.append("| Tool | Category | Referrer gets | Referee gets | Confidence |")
    out.append("|---|---|---|---|---|")
    for e in rt["entries"]:
        out.append(
            f"| **{e['name']}** | {e['category']} | {clean(e['referrer'])} | "
            f"{clean(e['referee'])} | {e['confidence']} |"
        )
    out.append("")
    out.append("Caveats and sources:")
    out.append("")
    for e in rt["entries"]:
        out.append(f"- **{e['name']}**: {clean(e['caveats'])} Source: {e['link']}")
    out.append("")

    ro = d["ruled_out"]
    out.append(f"## Probed and ruled out (audited {ro['audited']})")
    out.append("")
    out.append("Listed so they are not re-probed every cycle.")
    out.append("")
    for e in ro["entries"]:
        out.append(f"- **{e['name']}**: {clean(e['reason'])}")
    out.append("")

    out.append("## Backlog")
    out.append("")
    for b in d["backlog"]:
        out.append(f"- {clean(b)}")
    out.append("")

    out.append("## Validation log")
    out.append("")
    for block in d["changelog"]:
        for entry in block["entries"]:
            out.append(f"- **{block['date']}** {clean(entry)}")
    out.append("")
    return "\n".join(out)


def _kb_entry(t: dict) -> list[str]:
    out = [f"### {t['name']}: {t['offer']}", ""]
    status_note = {
        "ended": f"**Status: ENDED {t.get('ended_on', '')}.** Closed to new sign-ups.",
        "active": "Status: active.",
    }.get(t["status"], f"Status: {t['status']}.")
    out.append(status_note)
    out.append("")
    out.append(f"- Category: {t['category']} | Tier: {t.get('tier', 'n/a')}")
    out.append(f"- Original pricing: {clean(t['pricing']['original'])}")
    out.append(f"- Student pricing: {clean(t['pricing']['student'])}")
    out.append(f"- Included features: {clean(t['features'])}")
    out.append(f"- Effective length: {clean(t['length'])}")
    out.append(f"- Verification: {clean(t['verification'])}")
    if t.get("regions"):
        out.append(f"- Regions: {clean(t['regions'])}")
    for cav in t.get("caveats") or []:
        out.append(f"- Caveat: {clean(cav)}")
    out.append(f"- Referral programme: **{t['referral']['status']}**. {clean(t['referral']['detail'])}")
    out.append("- Official sources:")
    out.extend(links_block(t["links"], indent="  - "))
    if t["referral"].get("links"):
        out.append("- Referral sources:")
        out.extend(links_block(t["referral"]["links"], indent="  - "))
    out.append(f"- Last checked: {t['last_checked']} | Confidence: {t['confidence']}")
    out.append("")
    return out


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if generated files are stale")
    args = ap.parse_args()

    data = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    targets = {
        RECOMMENDED: build_recommended(data),
        KNOWLEDGE_BASE: build_knowledge_base(data),
    }

    if args.check:
        stale = [p.name for p, content in targets.items()
                 if not p.exists() or p.read_text(encoding="utf-8") != content]
        if stale:
            print(f"stale generated files: {', '.join(stale)}", file=sys.stderr)
            print("run: python3 scripts/build.py", file=sys.stderr)
            return 1
        print("generated files are up to date")
        return 0

    for path, content in targets.items():
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({len(content):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
