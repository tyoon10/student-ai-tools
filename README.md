# Student AI Tools: Discounts and Free Premium Access

A maintained guide to AI tools with student offers. Verified against the vendors'
own pages, with a `Last checked` date on every published entry.

**Read the guide: [recommended.md](./recommended.md)** ·
Live post: [twyoon.com/post/student-ai-tools](https://twyoon.com/post/student-ai-tools/)

> **No affiliate or referral links.** Every link goes to the vendor's own
> help-centre or pricing page. Referral programmes are documented as facts about
> each tool, not as an invitation to use anyone's link.

## What is in this repo

| Path | What it is |
|---|---|
| [`data/tools.yml`](./data/tools.yml) | **The single source of truth.** Every tool, offer, caveat, source link and check date. The only file you hand-edit. |
| [`recommended.md`](./recommended.md) | Generated. The curated public guide, mirrored to twyoon.com. |
| [`knowledge-base.md`](./knowledge-base.md) | Generated. The full working record, including tools excluded from the public list. |
| [`scripts/`](./scripts) | Build and validation scripts. |

The post at twyoon.com is generated from the same file by `scripts/build_post.py`,
so there are three outputs and still one input.

`recommended.md` and `knowledge-base.md` are both generated from `data/tools.yml`.
That is deliberate. The two files previously drifted apart, and at one point the
website became the de facto source of truth while the repo claimed it was not.
One input, two outputs, no drift.

## Working on it

```bash
pip install pyyaml

python3 scripts/build.py            # regenerate both markdown files
python3 scripts/build.py --check    # fail if they are stale (runs in CI)
python3 scripts/check_freshness.py  # fail if a published entry is over 90 days old
python3 scripts/check_links.py      # probe every outbound URL
python3 scripts/check_schema.py     # validate tools.yml shape (runs in CI)
python3 scripts/build_post.py       # regenerate the twyoon.com post from the same data
```

`scripts/build_post.py` writes the Astro post for twyoon.com. It is generated
from `data/tools.yml` too, so the site and the repo cannot drift apart the way
they did in May 2026. It writes `index.draft.md` by default, which Astro's
loader deliberately ignores; rename it to `index.md` to publish.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the bar an entry has to clear.

## How it stays current

- **Every published entry carries a `Last checked` date**, and CI fails if any of
  them passes 90 days. The rule is enforced, not just stated. Research-backlog
  entries are reported but never block the build.
- **A monthly job probes every outbound link** and opens an issue when one
  genuinely breaks. It distinguishes real rot from help centres that simply
  refuse automated clients, which several vendors do.
- **Ended offers are kept, not deleted.** They move to `status: ended` with the
  date they closed. Knowing an offer is gone is as useful as knowing one exists,
  and it is the honest way to show how fast these things disappear.

## Scope

Aimed at graduate students and early-career professionals looking for
legitimate, individually claimable student offers on AI tools. It is not a
deals-hunter list. The bar is "worth setting up an account for."

Offers that require your university to buy something are not dropped, they are
recorded under `excluded` with a check path, so the question stays answered.

## Licence

Content is [CC BY 4.0](./LICENSE). The scripts are also available under MIT.
Offer terms are facts about third-party products restated from public pages, and
are not warranted to be current. Confirm with the vendor before relying on them.
