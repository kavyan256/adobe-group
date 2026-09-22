---
name: freshness-corroboration-audit
description: >-
  Assess whether a site's facts are current, internally consistent, and
  corroborable. Checks machine-readable date signals, stale copyright and ageing
  content, contradictory prices across a site's own pages, and the presence of
  corroboration infrastructure (Organization sameAs links, press pages,
  consistent naming). Use standalone to answer "why do assistants repeat outdated
  or wrong facts about us?", or as the trust layer of a full AI-readiness audit.
license: Apache-2.0
allowed-tools: Bash, Read
---

# Freshness & Corroboration Audit

## When to use

Standalone, when a site *is* being cited but the content of the citation is wrong
— an old price, a departed CEO, a discontinued product — or when a brand is
routinely confused with something else of the same name.

## The reasoning this skill encodes

Machines treat a fact as more trustworthy when many independent sources say the
same thing. A claim that lives in exactly one place is fragile; one repeated
consistently across unrelated sources is far more likely to be believed and
repeated back. Two failure modes follow.

### Failure mode 1 — contradiction

**Inconsistency is worse than absence.** A missing price leaves an assistant with
nothing to say. Two different prices on two of your own pages leave it with
contradictory evidence, which lowers confidence in *everything else* you publish.
`D4_internal_contradiction` detects this entirely within the site, needs no
external data, and is threshold-free: the evidence is two literal strings that
disagree.

### Failure mode 2 — no means of corroboration

You cannot make third parties agree with you on demand, but you can control
whether agreement is *possible to establish*:

- `Organization` markup with `sameAs` pointing at Wikidata, LinkedIn, Crunchbase —
  this is what disambiguates you from others sharing your name
- a press page linking outward to independent coverage
- a stable, citable facts page third parties can quote verbatim
- name, address and phone stated identically everywhere

`D5_no_corroboration_hooks` detects the absence of this infrastructure. That is a
verifiable fact about the site itself, and it is the honest thing to measure.

### The limit we refuse to fake

True cross-web corroboration — *"do three independent sources agree on this
price?"* — requires a search backend this marketplace does not assume. Rather
than approximate it and present a guess as evidence, the skill runs two tiers:

- **Tier 1** (always, deterministic): the infrastructure checks above.
- **Tier 2** (`D6`, key-gated): real third-party verification, executed only when
  `SEARCH_API_KEY` is configured.

When Tier 2 cannot run it appears in `checks_skipped[]` with its reason and its
impact. It is never silently omitted. A declared limitation is engineering
maturity; a fabricated corroboration claim would be a false positive waiting to
be caught.

## Inputs

A site bundle, as a path argument or on stdin.

## Procedure

1. Gather date signals per page: `<time datetime>`, article published/modified
   meta, `Last-Modified`, sitemap `lastmod`, and dates inside structured data.
2. Emit `D1_no_date_signals` where a dated page type carries none; emit
   `D3_content_stale` where the newest signal exceeds 18 months.
3. Emit `D2_stale_copyright` where the footer year is more than a year behind.
4. Collect prices from pricing/product pages and emit `D4_internal_contradiction`
   where they disagree.
5. Check for `sameAs` and a press/news section; emit `D5_no_corroboration_hooks`.
6. Attempt Tier 2 only if `SEARCH_API_KEY` is set; otherwise record the skip.

```bash
python3 scripts/check_freshness.py bundle.json
SEARCH_API_KEY=... python3 scripts/check_freshness.py bundle.json   # enables D6
```

## Output

A JSON object with `findings` and `checks_skipped` arrays.

## Known false-positive risks, and how they are contained

- **Undated pages are not universally a defect.** A terms-of-service or contact
  page has no natural date. `D1` fires only for roles where recency is
  load-bearing (blog, home).
- **Price collection is `heuristic`** and capped accordingly: a page may
  legitimately show several prices (tiers, add-ons, currencies). `D4` compares
  sets across pages rather than asserting a single correct value, and is marked
  `static_heuristic` so the severity table caps it at medium.
- **Staleness is not decay for reference content.** An 18-month-old
  documentation page may be perfectly current. The finding says "not updated in
  N months", which is a fact, and leaves the judgement to the operator.

## References

- `references/freshness-signals.md` — the full signal list and thresholds, each
  justified by mechanism rather than by prevalence
