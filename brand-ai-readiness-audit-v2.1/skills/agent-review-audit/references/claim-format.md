# Claim format

`claims.json` is `{"claims": [ ... ]}` (a bare list also works). The verifier,
`scripts/verify_claims.py`, accepts a claim only if every rule below holds. It
changes nothing in a claim to make it pass: a claim is merged exactly as written,
or rejected with a reason.

## A claim

| Field | Required | Rule |
|---|---|---|
| `title` | yes | 8–160 characters. States the problem and its scale. |
| `why` | yes | 20–600 characters. The mechanism: why this costs being found, quoted or kept. |
| `mechanism` | yes | `A` `B` `C` `D` `E` `F` (problem statement appendix) or `on-site` |
| `hurts` | yes | `ai_discoverability`, `user_retention` or `both` |
| `severity` | yes | `high`, `medium` or `low`. Capped at medium when merged; single-page claims drop one band. |
| `nearest_check` | yes (may be `null`) | The scripted `check_id` this claim **restates**, or `null`. If that check already fired on the same pages, the claim is dropped as a duplicate. Name a check only when the claim is the same problem, not merely nearby. |
| `affected_urls` | yes | Pages from the crawl that returned readable HTML. |
| `evidence` | yes | 1–8 assertions. Every affected URL must appear in at least one. At least one must be positive. |
| `suggested_action` | yes | `summary` (8–200 chars), `how` (list of steps), `verify` (how to confirm the fix), `effort` (`low`/`medium`/`high`, default `medium`) |

At most 12 claims per audit are verified; later claims are rejected.

## Evidence assertions

Every assertion names a crawled `url`. Text comparisons ignore case and collapse
whitespace.

| `type` | Other fields | Holds when | Positive? |
|---|---|---|---|
| `html_contains` | `value` (≥6 chars) | the raw HTML contains `value` | yes |
| `html_lacks` | `value` (≥3 chars) | the raw HTML does not contain `value` | no |
| `text_contains` | `value` (≥6 chars), `scope` `extracted`\|`full` | the page text contains `value` | yes |
| `text_lacks` | `value` (≥3 chars), `scope` | the page text does not contain `value` | no |
| `header_contains` | `header`, `value` (≥6 chars) | that response header contains `value` | yes |
| `field` | `path`, `op`, `value` | the page's profile field satisfies `op` | `eq` `contains` `gt` `lt` `nonempty` are |

`field` paths are the keys of a page in `profile.json`, dotted: `status`, `title`,
`canonical`, `final_url`, `redirect_hops`, `robots_directives`, `meta_refresh`,
`meta.og:site_name`, `h1`, `h1.0`, `headings`, `words_extracted`, `noscript_words`,
`jsonld.types`, `jsonld.offers`, `links.internal`, `links.pdf`, `links.tel`, `forms`,
`iframes`, `images.missing_alt`, `hreflang`, `lang`, `role`.

`op`: `eq`, `ne`, `contains` / `lacks` (substring, or any list item),
`gt` / `lt` (numbers), `empty` / `nonempty` (`null`, `""`, `0`, `[]`, `{}` are empty).

**Why one positive assertion is required:** "this page lacks a price" is true of
every page that is not about prices. An absence only means something next to a
fact that says what the page is — its role, its title, its status.

## Example

```json
{
  "claims": [
    {
      "title": "/pricing answers HTTP 200 with a 'page not found' page",
      "why": "A soft 404 returns success, so crawlers keep an error page where the pricing page should be and have no price to quote.",
      "mechanism": "A",
      "hurts": "ai_discoverability",
      "severity": "high",
      "nearest_check": null,
      "affected_urls": ["https://example.com/pricing"],
      "evidence": [
        {"url": "https://example.com/pricing", "type": "field", "path": "status", "op": "eq", "value": 200},
        {"url": "https://example.com/pricing", "type": "field", "path": "title", "op": "contains", "value": "page not found"}
      ],
      "suggested_action": {
        "summary": "Serve the real pricing page at /pricing, or return 404 and redirect to the right URL.",
        "how": [
          "Find why the pricing route renders the not-found template while answering 200.",
          "If the page moved, 301-redirect the old URL to the new one."
        ],
        "verify": "curl -s https://example.com/pricing shows the pricing heading, and a missing URL returns 404.",
        "effort": "low"
      }
    }
  ]
}
```

## Common rejections

| Reason | Fix |
|---|---|
| `evidence names a URL that was not crawled` | Use a URL exactly as it appears in `profile.json` `pages[].url`. |
| `evidence does not hold` | The claim is not true of the crawl. Drop it. |
| `every assertion is an absence` | Add a positive assertion stating what the page is. |
| `no evidence is given for affected URL(s)` | Add an assertion per affected URL, or remove the URL. |
| `duplicates scripted check …` | The scripted finding already covers it. Drop it. |
