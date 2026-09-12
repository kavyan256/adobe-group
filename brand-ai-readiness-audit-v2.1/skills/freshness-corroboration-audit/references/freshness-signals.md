# Freshness signals and thresholds

Every threshold is justified by **mechanism**, never by prevalence: calibrating to a
percentile of surveyed sites would flag a fixed share of sites whatever their state.

## Date signals read

1. `datePublished`, `dateModified`, `dateCreated` or `uploadDate` in JSON-LD
2. `<time datetime="…">`
3. Meta tags whose name or property contains `published_time`, `modified_time` or
   `date`
4. The `Last-Modified` response header — often a CDN artefact, weak on its own

## Thresholds

| Check | Threshold | Mechanism |
|---|---|---|
| `D1_no_date_signals` | no date signal on a blog, news or article page | A page that cannot demonstrate recency cannot benefit from it. Home, legal and contact pages have no natural date and are not checked. |
| `D3_content_stale` | newest date older than 18 months, on those same pages | By then product, pricing and personnel claims have usually drifted. Reference content can be older and still current, so the finding states the age and leaves the judgement to the owner. |
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

## Corroboration

- **Checked on the site:** whether any page links to a press, newsroom or news
  section pointing at independent coverage (`D5`), and whether the homepage anchors
  the brand with `Organization` `sameAs` links (`C3`, in `fact-extractability-audit`).
- **Not checked:** whether independent third parties actually agree with a claim.
  That needs a search backend, so `D6_cross_web_corroboration` is always listed in
  `checks_skipped[]` and never guessed at.
