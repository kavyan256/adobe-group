# Freshness signals and thresholds

Every threshold below is justified by **mechanism**, never by the prevalence of a
property across surveyed sites. Calibrating to a percentile would flag a fixed
fraction of sites by construction, regardless of whether any had a real problem.

## Date signals, in order of reliability

1. `dateModified` / `datePublished` in structured data — explicit and typed
2. `<time datetime="...">` — explicit, machine-readable, human-visible
3. `article:published_time` / `article:modified_time` meta
4. `Last-Modified` response header — often a CDN artefact, weak on its own
5. Sitemap `<lastmod>` — frequently auto-generated and untrustworthy alone
6. Visible date text — human-readable but format-ambiguous

## Thresholds

| Check | Threshold | Mechanism |
|---|---|---|
| `D2_stale_copyright` | footer year < current year − 1 | A stale year is a widely-used freshness cue; it implies the whole site may be unmaintained. One year of grace covers sites updated in January. |
| `D3_content_stale` | newest date > 18 months | Beyond roughly this point, product, pricing and personnel claims have usually drifted. Applied only to `blog` roles, where recency is load-bearing. |
| `D1_no_date_signals` | zero signals on a dated role | A page that cannot demonstrate recency cannot benefit from it. Restricted to `blog` and `home`; a terms page has no natural date. |

## Internal contradiction

Prices are collected from `pricing` and `product` roles and compared as **sets**
across pages. We do not assert which value is correct — we report that the site
disagrees with itself.

This is the strongest freshness check available without external data, because
the evidence is two literal strings from the site's own pages. Inconsistency is
worse than absence: a missing price leaves an assistant with nothing to say; two
contradictory prices leave it with evidence that lowers confidence in everything
else the site publishes.

Marked `heuristic` and `static_heuristic` — a page may legitimately show several
prices (tiers, add-ons, currencies) — so the severity table caps it at medium.

## Corroboration: what we can and cannot measure

**Can (Tier 1, deterministic):** the presence or absence of corroboration
*infrastructure* — `Organization` markup with `sameAs`, a press/news section
linking outward, consistent name/address/phone, a stable citable facts page.
These are verifiable facts about the site itself.

**Cannot, without a search backend (Tier 2):** whether independent third parties
actually agree with a given claim. When `SEARCH_API_KEY` is unset, `D6` appears
in `checks_skipped[]` with its reason and impact. It is never silently omitted
and never guessed at.
