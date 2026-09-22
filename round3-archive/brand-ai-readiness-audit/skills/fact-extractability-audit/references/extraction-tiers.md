# Extraction tiers, payload islands, and the non-circularity argument

## The mechanism

Assistant fetchers run a two-stage pipeline:

```
raw bytes  ->  boilerplate-stripping text extractor  ->  model
                (Readability / Trafilatura class)
```

Stage two discards `<script>`, `<style>`, `nav`, `header`, `footer` and `aside`
**by construction**. So a fact carried in a hydration payload is present in the
*bytes* and absent from the *text*. **Present-in-bytes is not
present-to-the-assistant.**

Separately: the major AI retrieval agents do **not** execute JavaScript.
`GPTBot`, `OAI-SearchBot`, `ChatGPT-User`, `ClaudeBot`, `PerplexityBot` and
`Bytespider` fetch raw HTML. Googlebot is the outlier that renders. This is why
"renders fine in Chrome, ranks fine in Google, invisible to assistants" is a real
and common state.

## The tiers

| Tier | Where the fact lives | Verdict | Reasoning |
|---|---|---|---|
| **T0** | Visible prose or a heading | pass | Directly quotable |
| **T1** | JSON-LD / microdata / RDFa | pass | Survives extraction; machine-readable by design |
| **T2** | Only inside a script payload | medium | In the bytes, but no assistant reliably parses escape-chunked hydration blobs |
| **T3** | Absent from raw bytes entirely | high | Genuinely invisible to every non-rendering fetcher |

### Why T2 exists, and why it is only medium

A naive audit reports "SPA, therefore invisible". That false-positives across the
entire Next.js and Nuxt web, because hydration payloads frequently *do* carry the
facts. Parsing them before firing is a precision advantage — and being honest
that T2 is *hard to reach* rather than *invisible* is what keeps the finding
defensible.

## Payload islands parsed

| Marker | Framework |
|---|---|
| `__NEXT_DATA__` | Next.js (pages router) |
| `self.__next_f.push` | Next.js (app router, escape-chunked) |
| `window.__NUXT__` | Nuxt |
| `__APOLLO_STATE__` | Apollo GraphQL |
| `window.__INITIAL_STATE__` | Redux and similar |
| `<script type="application/json">` | generic embedded data |

## Where expected facts come from — the non-circularity argument

Sourcing expectations only from structured data would be **circular**: a site
with no JSON-LD yields no expected facts, so the check silently passes on exactly
the worst sites. Two independent sources are therefore combined.

### Source 1 — declared literals

Values the site itself asserts, in JSON-LD, OG/Twitter meta, `<title>`,
`<noscript>`, sitemap entries and payload islands. Test: does the literal also
reach T0? **Catches: the fact exists in bytes but not in text.**

On a typical Next.js commerce site the JSON-LD is server-rendered into `<head>`
while the price `<div>` is client-rendered — so this fires exactly where it should.

### Source 2 — role obligations

Derived from surfaces that are **not under test**: the URL slug we crawled, the
`<title>`, and inbound internal anchor text.

| Role (from URL/title) | Obligated fact |
|---|---|
| `/pricing`, `/plans` | a currency + numeral token |
| `/product/…`, `/shop/…` | a price |
| `/contact`, `/support` | a phone number or email address |

A page asserting "Pricing" is a commitment to contain a price. **Catches: the
fact does not exist at all.**

### Source 3 — the fallback

Where neither applies (a pure client-side shell with no title, nav or payload),
empty-shell detection covers the gap, narrowly scoped: `<body>` containing a
single mount element (`#root`, `#app`, `#__next`, `#__nuxt`) with fewer than 30
words of extractable text. Near-zero false-positive rate.

## Declared limits

- Facts fetched by client-side XHR *after* load with no server-rendered payload
  grade T3. That is the correct answer for a non-rendering fetcher, but we cannot
  distinguish "absent" from "arrives later via API" — a real false-negative surface.
- No layout information: CSS-hidden vs visible, viewport position and computed
  styles all require a browser.
- Our extractor approximates real fetchers' boilerplate rules; they differ in
  detail. `tests/fixtures/` pins our behaviour so drift is visible.
