# Extraction tiers, payload islands, and where expectations come from

## The mechanism

Assistant fetchers run the raw response through a boilerplate-stripping text
extractor (Readability / Trafilatura class) before the model sees anything:

```
raw bytes  ->  extractor (drops script, style, nav, header, footer, aside)  ->  model
```

So a fact carried in a hydration payload is present in the *bytes* and absent from
the *text*. Separately, the major AI retrieval agents (`OAI-SearchBot`,
`ChatGPT-User`, `PerplexityBot`, …) do not execute JavaScript; Googlebot is the
outlier that renders. "Renders fine in Chrome, ranks fine in Google, invisible to
assistants" is a real and common state.

## The tiers

| Tier | Where the fact lives | Result |
|---|---|---|
| **T0** | Extracted prose | pass — directly quotable |
| **T1** | JSON-LD | pass — machine-readable by design |
| **T2** | Only in meta tags or a script payload | `B1_fact_script_only`, medium — in the bytes, not the text |
| **T3** | Nowhere in the raw response | `B1_fact_absent`, high — invisible to every non-rendering fetcher |

T2 is what keeps this check from firing across the entire Next.js and Nuxt web, as a
naive "SPA, therefore invisible" rule would. Payloads are parsed before anything
fires, and a fact found only there is reported as *hard to reach*, not *invisible*.

## Payload islands parsed

| Marker | Framework |
|---|---|
| `__NEXT_DATA__` | Next.js (pages router) |
| `self.__next_f.push` | Next.js (app router) |
| `window.__NUXT__` | Nuxt |
| `__APOLLO_STATE__` | Apollo GraphQL |
| `__INITIAL_STATE__` | Redux and similar |
| `<script type="application/json">` | generic embedded data |

## Where expected facts come from

Taking expectations from the site's own structured data would be circular: a site
with no JSON-LD would expect nothing and pass. Expectations come instead from
surfaces that are not under test: **the URL the crawler followed**, then the page's
own title segments, then the homepage link text that points to it.

| Role | Recognised from | Obligated fact (any one satisfies it) |
|---|---|---|
| pricing | `/pricing`, `/plans`, `/subscribe`, `/buy`; a last path segment, title segment or homepage link made only of pricing words and connectors (`/plans-and-pricing`, `/preise`, "Plans & Pricing") | a currency-marked price |
| product | `/product(s)/…`, `/item(s)/…`, `/shop/…`, `/store/…`, `/p/…` | a currency-marked price |
| contact | `/contact`, `/contact-us`, `/get-in-touch`; likewise `/contact-sales`, "Contact us", `/kontakt` | a phone number or an email address |

"Only role words and connectors" is what keeps `/how-to-buy-a-house` from becoming a
pricing page. `/help` and `/support` are deliberately not contact roles; they are
usually documentation hubs.

**Recognising the fact.** A price is a number with a currency marker on either side:
`$49`, `49,00 €`, `CHF 49`, `Rs. 499`, `49 kr`, with either decimal convention. A
phone number needs 7–15 digits in phone-style groups; year pairs (`© 2025 2026`), dates
and bare digit runs are rejected. A visible `tel:` or `mailto:` link counts as T0 even
when its label is "Call us". Where no role applies, a pure client-side shell is still caught
by `B4_empty_shell`. Declared values are checked in the other direction by `C2`: a
JSON-LD price that matches no price shown on the page.

## Declared limits

- A fact fetched by client-side XHR after load, with no server-rendered payload,
  grades T3. That is the right answer for a non-rendering fetcher, but it cannot be
  told apart from a fact that does not exist.
- No layout information: CSS-hidden versus visible text needs a browser.
- The extractor approximates real fetchers, which differ in detail; the fixtures in
  `tests/` pin its behaviour so changes are visible.
- `C2` is conservative. Sale versus list prices, `AggregateOffer`, per-variant prices,
  tax-inclusive display and locale formats (`1.299,00 €`) all legitimately differ
  from one declared price, so it fires only on a single unambiguous value and is
  marked heuristic.
