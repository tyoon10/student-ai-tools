# Contributing

Corrections are the most useful thing you can send. Offers on this list change
without notice, and a stale entry is worse than no entry.

## Report something out of date

[Open an issue](https://github.com/tyoon10/student-ai-tools/issues/new) with:

- which tool
- what the page says now
- a link to the vendor's own help-centre or pricing page

Screenshots help when a vendor blocks automated checks, which several do.

## Editing the content

**Do not edit `recommended.md` or `knowledge-base.md` directly.** Both are
generated. Your changes will be overwritten by the next build, and CI will fail
the drift check.

Everything lives in [`data/tools.yml`](./data/tools.yml). To make a change:

```bash
pip install pyyaml

# 1. edit data/tools.yml
# 2. bump that entry's last_checked to the date you verified it
# 3. rebuild
python3 scripts/build.py

# 4. confirm the checks pass
python3 scripts/check_schema.py
python3 scripts/check_freshness.py
python3 scripts/check_links.py

# 5. if the published post needs updating too
python3 scripts/build_post.py
```

Commit `data/tools.yml` together with the regenerated markdown.

## The bar for inclusion

An entry only goes on the public list if all of these hold:

1. **Individually claimable.** If it needs your university to buy something, it
   belongs in `excluded` with a check path, not on the list.
2. **Documented by the vendor.** The source must be the vendor's own help centre
   or pricing page. Deal-aggregator and coupon sites are not sources.
3. **Verified, with a date.** Set `last_checked` to the day you actually looked.
   CI fails if anything published is older than 90 days.
4. **Honest about confidence.** If you could not confirm a number, say so in a
   caveat and set `confidence: medium` or `low`. Several vendors block automated
   checks; that is a caveat, not a reason to guess.

Offers that end are moved to `status: ended` rather than deleted. Knowing an
offer is gone is as useful as knowing one exists.

## No affiliate links

This guide carries no affiliate or referral links, and pull requests adding them
will be declined. Referral programmes are documented as facts about each tool.
That distinction is the whole point of the list being trustworthy.
