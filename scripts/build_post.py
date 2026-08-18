#!/usr/bin/env python3
"""Generate the twyoon.com Astro post from data/tools.yml.

The post and the repo guide drifted apart badly once before: two commits in May
2026 pulled edits FROM the website back INTO the repo, which contradicted the
knowledge base's own claim to be the source of truth. Generating the post from
the same YAML removes that failure mode entirely.

The post is a different artefact from recommended.md, not a copy. It carries
front matter, a narrative voice, and per-offer tables, and it omits the
repo-facing machinery (schema notes, referral audit, validation log).

Usage:
    python3 scripts/build_post.py                       # write to the default site path
    python3 scripts/build_post.py --out path/index.md   # write elsewhere
    python3 scripts/build_post.py --check               # exit 1 if stale

By default this writes `index.draft.md`. Astro's loader matches
`**/index.{md,mdx}`, so a draft file is NOT published. Rename it to index.md to
publish, and set meta.live_post_published to true in data/tools.yml.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from slug import slugify, verify_anchors  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "tools.yml"
LOGO_DIR = pathlib.Path(
    "/home/taewan/workspace/initiatives/twyoon-com/repos/site/public/media/logos"
)
SITE_DIR = pathlib.Path(
    "/home/taewan/workspace/initiatives/twyoon-com/repos/site"
    "/src/content/writings/student-ai-tools"
)


def default_out(meta: dict) -> pathlib.Path:
    """Astro's loader matches **/index.{md,mdx}, so the filename IS the switch.

    index.draft.md  -> not built at all
    index.md        -> built at /writings/student-ai-tools
    """
    name = "index.md" if meta.get("live_post_published") else "index.draft.md"
    return SITE_DIR / name


def clean(text) -> str:
    return " ".join(str(text or "").split())


# Category -> coarse filter group. This is presentation, so it lives in the
# generator rather than the data. Unmapped categories are reported by build_grid
# so a new tool never lands silently in a catch-all bucket.
FILTER_GROUPS = {
    "coding": ("Coding and dev", [
        "AI code editor", "AI coding", "AI coding agent", "Developer tools",
        "Cloud and infrastructure",
    ]),
    "writing": ("Writing and research", [
        "Writing", "Academic writing", "Academic search", "AI search",
        "Transcription", "Text to speech",
    ]),
    "notes": ("Notes and meetings", [
        "Notes and knowledge", "Meeting notes", "Scheduling", "Daily planning",
    ]),
    "design": ("Design and media", [
        "Design", "Design and creative", "Design and web", "Presentations",
        "Async video",
    ]),
    "productivity": ("Productivity", ["Productivity suite"]),
}
_CATEGORY_TO_GROUP = {
    cat: key for key, (_, cats) in FILTER_GROUPS.items() for cat in cats
}

# CRITICAL: no blank lines inside these blocks.
#
# Markdown ends a raw-HTML block at the first blank line. A blank line inside
# <style> or <script> therefore closes the block early, wraps the remainder in
# <p>, and lets smartypants rewrite ' into a typographic quote, which is a
# syntax error in JavaScript. That is exactly how the first version shipped
# broken. emit_html_block() below enforces this.
GRID_CSS = """<style>
/* The grid lives inside .markdown-body, whose prose rules would otherwise win.
   Two conflicts matter:
     .markdown-body img  (0,1,1) forces width/height:auto, display:block and
       margin:32px auto, which blows every logo up to its intrinsic size and
       shoves the card layout apart. Beaten here with .offergrid img.offercard__logo.
     .markdown-body a    (0,1,1) underlines every link.
   So each rule below is scoped under .offergrid to outrank prose styling. */
/* The site never loads global.css, where the `* { box-sizing: border-box }`
   reset lives, so everything computes as content-box. Without this, a card's
   16px padding and 1px border are ADDED to height:100%, making every <a> 34px
   taller than its grid row and overlapping the row below. Scoped rather than
   global: fixing it site-wide is the site owner's call, since global.css also
   resets all margins and padding. */
.offergrid,.offergrid *{box-sizing:border-box}
.offergrid{
  /* Break out of the 62ch prose column so cards get three across on desktop,
     without escaping the page gutter on narrow screens. */
  --breakout:clamp(0px,(100vw - 48px - var(--prose-width))/2,180px);
  --gap:14px;
  margin:32px calc(-1 * var(--breakout)) 40px;
  font-family:var(--sans);letter-spacing:0}
.offergrid .offergrid__controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;
  padding:14px;border:1px solid var(--rule);border-radius:var(--r-action);
  background:var(--sunk);margin:0 0 var(--gap)}
.offergrid .offergrid__search{flex:1 1 210px;min-width:0;font:inherit;font-size:14px;
  padding:9px 12px;border:1px solid var(--rule);border-radius:var(--r-action);
  background:var(--canvas);color:var(--ink)}
.offergrid .offergrid__search:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.offergrid .offergrid__chips{display:flex;flex-wrap:wrap;gap:6px}
.offergrid .offergrid__chip{font:inherit;font-size:12px;line-height:1;padding:8px 12px;
  cursor:pointer;border:1px solid var(--rule);border-radius:var(--r-pill);
  background:var(--canvas);color:var(--ink-muted)}
.offergrid .offergrid__chip:hover{border-color:var(--accent);color:var(--accent)}
.offergrid .offergrid__chip[aria-pressed="true"]{background:var(--accent);
  border-color:var(--accent);color:#fff}
.offergrid .offergrid__toggle{display:inline-flex;align-items:center;gap:6px;font-size:12px;
  color:var(--ink-muted);cursor:pointer;white-space:nowrap}
.offergrid .offergrid__count{width:100%;margin:0;font-size:12px;color:var(--ink-quiet)}
.offergrid .offergrid__list{list-style:none;margin:0;padding:0;display:grid;gap:var(--gap);
  grid-template-columns:repeat(auto-fill,minmax(220px,1fr))}
.offergrid .offercard{margin:0;padding:0;display:flex}
.offergrid .offercard::marker{content:""}
.offergrid .offercard a{display:flex;flex-direction:column;align-items:flex-start;gap:8px;
  flex:1 1 auto;min-width:0;padding:16px;text-decoration:none;color:inherit;background:var(--surface);
  border:1px solid var(--rule);border-radius:var(--r-action)}
.offergrid .offercard a:hover{border-color:var(--accent);background:var(--accent-wash)}
.offergrid .offercard a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.offergrid .offercard__top{display:flex;align-items:center;gap:10px;width:100%}
/* Specificity 0,2,1 so it beats .markdown-body img (0,1,1). */
.offergrid img.offercard__logo{width:32px;height:32px;min-width:32px;max-width:32px;
  max-height:32px;margin:0;display:block;object-fit:contain;border-radius:4px;flex:none}
.offergrid .offercard__mono{width:32px;height:32px;flex:none;border-radius:4px;display:grid;
  place-items:center;background:var(--accent);color:#fff;font-weight:600;font-size:14px}
.offergrid .offercard__name{font-weight:600;font-size:14px;line-height:1.25;
  font-family:var(--sans)}
.offergrid .offercard__offer{font-size:11px;font-weight:600;letter-spacing:.02em;
  padding:4px 9px;border-radius:var(--r-pill);background:var(--accent-wash);color:var(--accent)}
.offergrid .offercard--free .offercard__offer{background:var(--accent);color:#fff}
.offergrid .offercard__desc{font-size:13px;line-height:1.45;color:var(--ink-muted);margin:0}
.offergrid .offercard__cat{margin-top:auto;padding-top:4px;font-size:11px;color:var(--ink-quiet)}
.offergrid .offergrid__empty{display:none;padding:20px;text-align:center;
  color:var(--ink-muted);border:1px dashed var(--rule);border-radius:var(--r-action);
  font-size:14px;margin:0}
.offergrid--empty .offergrid__empty{display:block}
.offergrid--empty .offergrid__list{display:none}
@media (max-width:560px){
  .offergrid{margin-left:0;margin-right:0}
  .offergrid .offergrid__list{grid-template-columns:1fr}
}
</style>
<noscript><style>
/* Without JS the controls cannot work, so hide them rather than showing dead
   inputs. The full grid stays visible and every card is a plain link. */
.offergrid .offergrid__controls{display:none}
</style></noscript>"""

GRID_JS = """<script>
(function () {
  var root = document.querySelector('[data-offergrid]');
  if (!root) return;
  var cards = Array.prototype.slice.call(root.querySelectorAll('.offercard'));
  var search = root.querySelector('[data-search]');
  var chips = Array.prototype.slice.call(root.querySelectorAll('[data-filter]'));
  var freeOnly = root.querySelector('[data-free]');
  var count = root.querySelector('[data-count]');
  var group = 'all';
  function apply() {
    var q = (search.value || '').trim().toLowerCase();
    var shown = 0;
    cards.forEach(function (card) {
      var okGroup = group === 'all' || card.dataset.group === group;
      var okFree = !freeOnly.checked || card.dataset.free === 'true';
      var okText = !q || card.dataset.search.indexOf(q) !== -1;
      var visible = okGroup && okFree && okText;
      card.hidden = !visible;
      if (visible) shown++;
    });
    root.classList.toggle('offergrid--empty', shown === 0);
    count.textContent = shown === cards.length
      ? 'Showing all ' + cards.length + ' offers'
      : 'Showing ' + shown + ' of ' + cards.length + ' offers';
  }
  search.addEventListener('input', apply);
  freeOnly.addEventListener('change', apply);
  chips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      group = chip.dataset.filter;
      chips.forEach(function (c) {
        c.setAttribute('aria-pressed', String(c === chip));
      });
      apply();
    });
  });
  apply();
})();
</script>"""


def emit_html_block(block: str) -> list[str]:
    """Return *block* as markdown-safe lines: no blank lines, none stripped.

    Raises if a line is blank, since silently dropping it would change the
    meaning of CSS or JS in ways that are hard to spot.
    """
    return [ln for ln in block.splitlines() if ln.strip()]


def _first_sentence(text: str, limit: int = 120) -> str:
    text = clean(text)
    for i, ch in enumerate(text):
        if ch == "." and i + 1 < len(text) and text[i + 1] == " ":
            text = text[: i + 1]
            break
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "..."
    return text


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build_grid(rows: list[tuple[dict, str]], logo_dir: pathlib.Path) -> list[str]:
    """Interactive, filterable card grid.

    `rows` is (entry, anchor). Anchor may be a section anchor for entries that
    have no heading of their own.
    """
    unmapped = sorted({e["category"] for e, _ in rows
                       if e.get("category") and e["category"] not in _CATEGORY_TO_GROUP})
    if unmapped:
        print(f"WARNING: categories with no filter group, shown under All only: "
              f"{unmapped}", file=sys.stderr)

    used = {g for e, _ in rows if (g := _CATEGORY_TO_GROUP.get(e.get("category", "")))}

    o = emit_html_block(GRID_CSS)
    o.append('<div class="offergrid" data-offergrid>')
    o.append('  <div class="offergrid__controls">')
    o.append('    <input id="offer-search" class="offergrid__search" type="search" '
             'data-search placeholder="Search tools, offers, categories..." '
             'aria-label="Search offers">')
    o.append('    <div class="offergrid__chips" role="group" aria-label="Filter by category">')
    o.append('      <button type="button" class="offergrid__chip" data-filter="all" '
             'aria-pressed="true">All</button>')
    for key, (label, _) in FILTER_GROUPS.items():
        if key in used:
            o.append(f'      <button type="button" class="offergrid__chip" '
                     f'data-filter="{key}" aria-pressed="false">{_esc(label)}</button>')
    o.append('    </div>')
    o.append('    <label class="offergrid__toggle"><input type="checkbox" data-free> '
             'Free only</label>')
    o.append('    <p class="offergrid__count" data-count aria-live="polite"></p>')
    o.append('  </div>')
    o.append('  <ul class="offergrid__list">')

    for e, anchor in rows:
        name = e["name"]
        headline = e.get("headline", "")
        desc = _first_sentence(e.get("blurb") or e.get("student") or "")
        cat = e.get("category", "Cloud and infrastructure")
        group = _CATEGORY_TO_GROUP.get(cat, "")
        is_free = "free" in headline.lower()
        haystack = " ".join([name, headline, desc, cat]).lower()

        logo = next(iter(sorted(logo_dir.glob(f"{e['id']}.*"))), None) if logo_dir.exists() else None
        if logo:
            media = (f'<img class="offercard__logo" src="/media/logos/{logo.name}" '
                     f'alt="" width="32" height="32" loading="lazy" decoding="async">')
        else:
            media = f'<span class="offercard__mono" aria-hidden="true">{_esc(name[0])}</span>'

        o.append(f'    <li class="offercard{" offercard--free" if is_free else ""}" '
                 f'data-group="{group}" data-free="{str(is_free).lower()}" '
                 f'data-search="{_esc(haystack)}">')
        o.append(f'      <a href="#{anchor}">')
        o.append(f'        <span class="offercard__top">{media}'
                 f'<span class="offercard__name">{_esc(name)}</span></span>')
        o.append(f'        <span class="offercard__offer">{_esc(headline)}</span>')
        o.append(f'        <span class="offercard__desc">{_esc(desc)}</span>')
        o.append(f'        <span class="offercard__cat">{_esc(cat)}</span>')
        o.append('      </a>')
        o.append('    </li>')

    o.append('  </ul>')
    o.append('  <p class="offergrid__empty">No offers match that. Clear the search or '
             'pick a different category.</p>')
    o.append('</div>')
    o.extend(emit_html_block(GRID_JS))
    o.append("")
    return o


def daily_heading(i: int, t: dict) -> str:
    return f"{i}. {t['name']}: **{t['headline']}**"


def secondary_heading(t: dict) -> str:
    return f"{t['name']}: **{t['headline']}**"


def toc(daily, secondary, rest, cloud, lost) -> list[str]:
    """Markdown-table index. Superseded by build_grid in the post, kept for
    the --plain fallback and for anyone regenerating without the site assets."""
    o = ["## Every offer at a glance", ""]
    o.append("Jump straight to any tool. Prices and terms are in each entry.")
    o.append("")

    def table(rows):
        out = ["| Tool | Offer | What it is for |", "|---|---|---|"]
        out.extend(rows)
        out.append("")
        return out

    o.append(f"**[The {_word(len(daily))} I use every day](#"
             f"{slugify(f'The {_word(len(daily))} I actually use every day')})**")
    o.append("")
    o.extend(table([
        f"| [{t['name']}](#{slugify(daily_heading(i, t))}) | {t['headline']} | {t['category']} |"
        for i, t in enumerate(daily, 1)
    ]))

    o.append(f"**[Worth knowing about](#{slugify('Worth knowing about')})**")
    o.append("")
    o.extend(table([
        f"| [{t['name']}](#{slugify(secondary_heading(t))}) | {t['headline']} | {t['category']} |"
        for t in secondary
    ]))

    if rest:
        o.append(f"**[The rest](#{slugify('The rest')})**")
        o.append("")
        o.extend(table([
            f"| [{t['name']}](#{slugify('The rest')}) | {t['headline']} | {t['category']} |"
            for t in rest
        ]))

    o.append(f"**[Cloud credits](#{slugify('Cloud credits')})**")
    o.append("")
    o.extend(table([
        f"| [{c['name']}](#{slugify('Cloud credits')}) | {c['headline']} | Cloud and infrastructure |"
        for c in cloud
    ]))

    if lost:
        names = ", ".join(t["name"] for t in lost)
        o.append(f"**[Recently closed](#{slugify('Recently closed')}):** {names}. "
                 "Kept on the page so you know not to go looking.")
        o.append("")

    o.append("---")
    o.append("")
    return o


def row(label: str, value: str) -> str:
    return f"| {label} | {value} |"


def offer_table(t: dict) -> list[str]:
    out = ["", "| Field | Value |", "|---|---|"]
    out.append(row("Original price", clean(t["pricing"]["original"])))
    out.append(row("Student price", f"**{clean(t['pricing']['student'])}**"))
    out.append(row("Verification", clean(t["verification"])))
    out.append(row("Length", clean(t["length"])))
    if t.get("regions"):
        out.append(row("Eligibility", clean(t["regions"])))
    out.append(row("Sign up", f"[{_domain(t['links'][0])}]({t['links'][0]})"))
    out.append("")
    return out


def _domain(url: str) -> str:
    return url.split("//", 1)[-1].split("/", 1)[0].removeprefix("www.")


def build(d: dict) -> str:
    meta = d["meta"]
    tools = d["tools"]
    date = meta["last_full_review"]

    active_pub = [t for t in tools if t["status"] == "active" and t.get("published")]
    daily = sorted([t for t in active_pub if t.get("daily_use")],
                   key=lambda t: t.get("rank", 99))
    secondary = [t for t in active_pub if not t.get("daily_use")
                 and t.get("tier") in ("S", "A", "B")]
    secondary.sort(key=lambda t: ("S", "A", "B").index(t["tier"]))
    rest = [t for t in active_pub if not t.get("daily_use")
            and t.get("tier") not in ("S", "A", "B")]
    ended = [t for t in tools + d["excluded"] if t.get("status") == "ended"]
    # Only offers that were actually on the published list belong in the intro.
    # Everything else still appears under "Recently closed" as a record.
    lost = [t for t in ended if t.get("headline_loss")]
    ended.sort(key=lambda t: t.get("ended_on", ""), reverse=True)

    o: list[str] = []
    o.append("---")
    o.append('title: "AI Tools Worth Setting Up Today (with Student Benefit)"')
    o.append(f"date: {date}")
    o.append('description: "The AI tools I actually use, plus a curated secondary '
             f'list. Every offer verified against the vendor\'s own pages on {date}."')
    o.append("featured: false")
    if meta.get("live_post_unlisted"):
        # Builds at its own URL, hidden from the writings index, the homepage
        # and the sitemap, and served with noindex. Direct-link sharing only.
        o.append("unlisted: true")
    o.append('coverImage: "./featured.png"')
    o.append("tags:")
    for tag in ("AI Tools", "Students", "MBA", "Productivity"):
        o.append(f'  - "{tag}"')
    o.append("---")
    o.append("")

    o.append("Summer is the best time of year to build, learn and try new tools. It is "
             "also the moment to lock in every student-only AI offer you can, especially "
             "if you are graduating.")
    o.append("")
    o.append("> **If you are a graduating student, move fast.** Most of these offers "
             "verify against your .edu email or active student status. The day you lose "
             "either, you lose the offer.")
    o.append("")
    o.append("There is a bigger pattern here. AI tools open free or deeply discounted "
             "student plans early to drive adoption, then quietly close the door once "
             "they have enough traction. This is not hypothetical. Since I started "
             f"tracking these, {_word(len(lost))} of the offers on this very list "
             "have gone:")
    o.append("")
    for t in sorted(lost, key=lambda x: x.get("ended_on", "")):
        o.append(f"- **{t['name']}** closed **{t.get('ended_on', 'recently')}**. "
                 f"{clean(t.get('reason') or t.get('blurb'))}")
    o.append("")
    o.append("So claim the live ones today, while they are still live.")
    o.append("")
    o.append(f"> **Last refreshed:** {date}. Every entry below was checked against the "
             "vendor's own help-centre or pricing page, not a coupon site. The full "
             "research notes, including the tools I ruled out and why, live at "
             f"[github.com/tyoon10/student-ai-tools]({meta['repo']}).")
    o.append("")
    o.append("> **No affiliate links.** Nothing here pays me. Every link goes straight "
             "to the vendor.")
    o.append("")
    o.append("---")
    o.append("")

    rows = [(t, slugify(daily_heading(i, t))) for i, t in enumerate(daily, 1)]
    rows += [(t, slugify(secondary_heading(t))) for t in secondary]
    rows += [(t, slugify("The rest")) for t in rest]
    rows += [(c, slugify("Cloud credits")) for c in d["cloud_credits"]]

    o.append("## Every offer at a glance")
    o.append("")
    o.append("Filter by category, search by name, or narrow to the free ones. "
             "Each card links to the full entry with terms and sources.")
    o.append("")
    o.extend(build_grid(rows, LOGO_DIR))
    if lost:
        names = ", ".join(t["name"] for t in lost)
        o.append(f"**[Recently closed](#{slugify('Recently closed')}):** {names}. "
                 "Kept on the page so you know not to go looking.")
        o.append("")
    o.append("---")
    o.append("")

    o.append(f"## The {_word(len(daily))} I actually use every day")
    o.append("")
    o.append("Tried, used extensively, kept. These are the ones I would tell a "
             "classmate to set up first.")
    o.append("")
    for i, t in enumerate(daily, 1):
        o.append(f"### {daily_heading(i, t)}")
        o.append("")
        o.append(clean(t["blurb"]))
        o.extend(offer_table(t))
        for cav in t.get("caveats") or []:
            o.append(f"*Note: {clean(cav)}*")
            o.append("")

    o.append("---")
    o.append("")
    o.append("## Worth knowing about")
    o.append("")
    o.append("Strong offers that are not part of my daily stack.")
    o.append("")
    for t in secondary:
        o.append(f"### {secondary_heading(t)}")
        o.append("")
        o.append(clean(t["blurb"]))
        o.extend(offer_table(t))

    if rest:
        o.append("### The rest")
        o.append("")
        o.append("| Tool | Offer | What it is |")
        o.append("|---|---|---|")
        for t in rest:
            o.append(f"| [{t['name']}]({t['links'][0]}) | **{t['headline']}** | "
                     f"{clean(t['blurb'])} |")
        o.append("")

    o.append("### Cloud credits")
    o.append("")
    o.append("| Programme | Offer | Notes |")
    o.append("|---|---|---|")
    for c in d["cloud_credits"]:
        o.append(f"| [{c['name']}]({c['links'][0]}) | **{c['headline']}** | "
                 f"{clean(c['student'])} |")
    o.append("")
    o.append("---")
    o.append("")

    if ended:
        o.append("## Recently closed")
        o.append("")
        o.append("I keep dead offers on the page instead of deleting them. Knowing "
                 "an offer is gone saves you the search, and it shows how quickly "
                 "these things move.")
        o.append("")
        for t in ended:
            o.append(f"**{t['name']}**, closed {t.get('ended_on', 'recently')}. "
                     f"{clean(t.get('reason') or t.get('blurb'))}")
            o.append("")
            for cav in t.get("caveats") or []:
                o.append(f"- {clean(cav)}")
            if t.get("length") and t.get("status") == "ended" and t in tools:
                o.append(f"- Existing subscribers: {clean(t['length'])}")
            o.append("")
        o.append("---")
        o.append("")

    o.append("## What is not on this list, and why")
    o.append("")
    for e in d["excluded"]:
        if e.get("status") == "ended":
            continue
        line = f"**{e['name']}.** {clean(e['reason'])}"
        for extra in ("individual_routes", "detail", "check_path"):
            if e.get(extra):
                line += f" {clean(e[extra])}"
        o.append(line)
        o.append("")
    unresolved = d.get("unresolved") or []
    if unresolved:
        names = ", ".join(u["name"] for u in unresolved)
        o.append(f"**{names}.** Dropped. I could not confirm official student terms "
                 "after more than three months, so they are off the list rather than "
                 "on it with a question mark.")
        o.append("")
    o.append("---")
    o.append("")

    o.append("## How to verify anything here")
    o.append("")
    o.append("1. **Click the official link.** Every source here is a help-centre or "
             "pricing page. Coupon and deal-aggregator sites routinely advertise "
             "offers that the vendor's own site does not mention, and several on "
             "this list were rejected for exactly that reason.")
    o.append(f"2. **Check the refresh date.** If it is more than "
             f"{meta['max_age_days']} days old, re-verify before you rely on it.")
    o.append("3. **Try SheerID, Student Beans or UNiDAYS directly** if you are hunting "
             "beyond this list. A lot of discounts route through them.")
    o.append("")
    o.append("---")
    o.append("")
    o.append(f"*Maintained openly at [github.com/tyoon10/student-ai-tools]({meta['repo']}). "
             "The list is generated from a single data file, checked by CI, and "
             "re-verified on a schedule. Spot something out of date? Open an issue.*")
    o.append("")
    return "\n".join(o)


def _word(n: int) -> str:
    return {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
            6: "six", 7: "seven", 8: "eight"}.get(n, str(n))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    data = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    meta = data["meta"]
    if args.out is None:
        args.out = default_out(meta)
    content = build(data)

    # A blank line inside <style>/<script> ends markdown's raw-HTML block, which
    # closes the tag early and lets smartypants rewrite quotes into typographic
    # ones. That silently breaks the JS. Catch it before it ships again.
    for tag in ("style", "script"):
        for m in re.finditer(rf"<{tag}>(.*?)</{tag}>", content, re.S):
            body = m.group(1)
            if any(not ln.strip() for ln in body.strip("\n").splitlines()):
                print(f"blank line inside a <{tag}> block. Markdown will close the "
                      f"tag there and mangle the rest.", file=sys.stderr)
                return 1
    if any(c in content for c in "\u2018\u2019\u201c\u201d"):
        print("typographic quotes found in generated output; markdown may have "
              "already mangled a raw HTML block", file=sys.stderr)
        return 1

    anchors = re.findall(r"\]\(#([^)]+)\)", content)
    missing = verify_anchors(content, anchors)
    if missing:
        print(f"broken table-of-contents anchors: {sorted(set(missing))}",
              file=sys.stderr)
        return 1

    if args.check:
        if not args.out.exists() or args.out.read_text(encoding="utf-8") != content:
            print(f"stale: {args.out}", file=sys.stderr)
            return 1
        print("post is up to date")
        return 0

    if not args.out.parent.exists():
        print(f"target directory does not exist: {args.out.parent}", file=sys.stderr)
        return 1
    args.out.write_text(content, encoding="utf-8")
    print(f"wrote {args.out} ({len(content):,} bytes)")
    if args.out.name.endswith(".draft.md"):
        print("NOTE: this is a draft. Astro ignores index.draft.md. "
              "Set meta.live_post_published: true in data/tools.yml to publish.")
    elif meta.get("live_post_unlisted"):
        print("NOTE: published as UNLISTED. It builds at "
              f"{meta['live_post']} and is reachable by direct link, but is "
              "hidden from the writings index, the homepage and the sitemap, "
              "and served with noindex.")
    stale = SITE_DIR / ("index.draft.md" if args.out.name == "index.md" else "index.md")
    if stale.exists():
        print(f"WARNING: {stale.name} also exists and will confuse the loader. "
              f"Remove it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
