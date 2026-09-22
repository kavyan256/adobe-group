---
name: freshness-corroboration-audit
description: >-
  Assess whether a site's facts are current, internally consistent, and
  corroborable. Checks machine-readable date signals, stale copyright and ageing
  articles, contradictory prices across a site's own pages, and whether the site
  links out to independent press coverage. Use standalone to answer "why do
  assistants repeat outdated or wrong facts about us?", or as the trust layer of
  a full AI-readiness audit.
license: Apache-2.0
allowed-tools: Bash, Read
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
   the `Last-Modified` header, and JSON-LD date properties.
2. A blog, news or article page with no date signal → `D1_no_date_signals`; one whose
   newest date is over 18 months old → `D3_content_stale`.
3. A footer copyright year more than a year behind → `D2_stale_copyright`.
4. Pricing or product pages showing different sets of prices →
   `D4_internal_contradiction` (heuristic). A site that disagrees with itself is worse
   than one that says nothing.
5. No crawled page links to a press, newsroom or news section →
   `D5_no_corroboration_hooks`. A missing `sameAs` is reported once, as C3, by
   `fact-extractability-audit`.
6. Record `D6_cross_web_corroboration` in `checks_skipped[]`: whether third parties
   agree needs a search backend, and it is never guessed at.

```bash
python3 scripts/check_freshness.py bundle.json
```

## Output

`{"findings": [...], "checks_skipped": [...]}`

## References

- `references/freshness-signals.md` — the signals read, the thresholds, and why each
  is set where it is
