# Freshness signals and thresholds

Every threshold is justified by **mechanism**, never by prevalence: calibrating to a
percentile of surveyed sites would flag a fixed share of sites whatever their state.

## Date signals read

1. `datePublished`, `dateModified`, `dateCreated` or `uploadDate` in JSON-LD
2. `<time datetime="…">`
3. Meta tags whose name or property contains `published_time`, `modified_time` or
   `date`
4. The `Last-Modified` response header — RFC 1123, parsed with the standard library
   and fed in as a date. Often a CDN artefact, so weak on its own, but a page that
   carries only this is still dated for D1's purposes

## Thresholds

| Check | Threshold | Mechanism |
|---|---|---|
| `D1_no_date_signals` | no date signal on a blog, news or article page | A page that cannot demonstrate recency cannot benefit from it. Home, legal and contact pages have no natural date and are not checked; neither is the section's own index page (`/blog`, `/news`), which is a listing. |
| `D3_content_stale` | newest date older than 18 months, on those same pages | By then product, pricing and personnel claims have usually drifted. Reference content can be older and still current, so the finding is low, states the age, and asks for a review: update `dateModified` if still accurate, mark it archived if not. |
| `D2_stale_copyright` | footer year before the current year − 1 | A stale year suggests the whole site is unmaintained. One year of grace covers sites updated in January. |

## Internal contradiction (D4)

Only the **same item** can contradict itself. Items are matched by the `sku`, `gtin`,
`mpn` or, failing those, `name` in their `Product` markup, and D4 fires when one item
is declared at different prices on different pages. Two different products at two
different prices are a catalogue, not a contradiction — comparing every page's price
set, as an earlier version did, flagged every shop with more than one product.
`AggregateOffer` ranges are skipped. The finding does not claim which value is right,
only that the site disagrees with itself. Sale prices and variants can still differ
legitimately, so D4 is `heuristic` and capped at medium.

Declared prices go through the same `_as_number` as the visible prices in
`fact-extractability-audit` (the function is copied verbatim, since skills do not
import each other): `"1,299.00"`, `"1.299,00"`, `"49,00"` and `"1,29,999"` all
become the number they display, so a locale never manufactures a contradiction.

## Corroboration

- **Checked on the site:** whether any crawled page anchors the brand with `sameAs`
  on an organisation-like node (`C3`, in `fact-extractability-audit`).
- **Not a finding:** the absence of a press page or a citable facts page. An earlier
  version reported it as `D5_no_corroboration_hooks`, which fired on nearly every
  small site and duplicated the orchestrator's proactive "Publish a stable, citable
  facts page" recommendation. That recommendation, conditioned on whether `sameAs` is
  already published, now carries the advice on its own.
- **Not checked:** whether independent third parties actually agree with a claim.
  That needs a search backend, so `D6_cross_web_corroboration` is always listed in
  `checks_skipped[]` and never guessed at.
