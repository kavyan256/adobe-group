---
name: freshness-corroboration-audit
description: >-
  Assess whether a site's facts are current and internally consistent. Checks
  machine-readable date signals (JSON-LD, <time>, meta tags, the Last-Modified
  header), stale copyright and ageing articles, and contradictory prices for the
  same product across a site's own pages. Runs on its own against a bundle from
  audit-orchestrator to answer "why do assistants repeat outdated or wrong facts
  about us?", or as the trust layer of a full AI-readiness audit.
license: Apache-2.0
allowed-tools: Bash Read
compatibility: Python 3.10+, httpx, beautifulsoup4
---

# Freshness & Corroboration Audit

## When to use

When a site is cited but the citation is out of date or wrong — an old price, a
departed CEO — or as the trust layer of `audit-orchestrator`. Machines believe a
claim that is recent, consistent, and repeated by independent sources.

## Inputs

A site bundle, as a path argument or on stdin. The clock is the bundle's
`audited_at`, so replaying a bundle gives the same verdicts on any day.

## Procedure

1. Collect date signals per page: `<time datetime>`, published/modified meta tags,
   the `Last-Modified` header (RFC 1123, parsed to a date), and JSON-LD date
   properties.
2. A blog, news or article page with no date signal → `D1_no_date_signals`; one whose
   newest date is over 18 months old → `D3_content_stale`. The section's own index
   page (`/blog`, `/news`, `/articles`) is a listing, not an article, and is skipped
   by both.
3. A footer copyright year more than a year behind → `D2_stale_copyright`.
4. The same product, matched by the sku or name in its Product markup, declared at
   different prices on different pages → `D4_internal_contradiction` (heuristic).
   Prices are read with the same parser as `fact-extractability-audit`, so
   `1,29,999` and `1.299,00` compare as numbers. A site that disagrees with itself
   is worse than one that says nothing.
5. Record `D6_cross_web_corroboration` in `checks_skipped[]`: whether third parties
   agree needs a search backend, and it is never guessed at. On-site corroboration
   hooks are not a finding here: a missing `sameAs` is C3's, and the orchestrator's
   proactive "citable facts page" recommendation covers the rest.

```bash
python3 scripts/check_freshness.py bundle.json
```

## Output

`{"findings": [...], "checks_skipped": [...]}`

## Interpreting results

- `D3_content_stale` is a prompt to review, not a verdict: a reference article can be
  three years old and still right. If the page is evergreen, keep it at low and
  suggest a reviewed `dateModified` rather than a rewrite.
- `D1` on a page the role detector called `blog` because of a `/news/` path that is
  really a product-updates listing or a category page is a false positive; drop it.
- `D4` fires on the same `name` at two prices: a bundle, a variant or a sale price
  legitimately differs. Read both pages before repeating it; see
  `references/freshness-signals.md`.
- `D2` on a single-page site with a hand-written footer is real but trivial; never
  let it lead the report.

## References

- `references/freshness-signals.md` — the signals read, the thresholds, and why each
  is set where it is
