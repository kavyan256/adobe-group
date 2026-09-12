# Claim format

`claims.json` is `{"claims": [ ... ], "fixes": [ ... ]}` (a bare list of claims
also works). The verifier, `scripts/verify_claims.py`, accepts a claim only if
every rule below holds. It changes nothing in a claim to make it pass: a claim is
merged exactly as written, or rejected with a reason.

## A claim

| Field | Required | Rule |
|---|---|---|
| `title` | yes | 8–160 characters. States the problem and its scale. |
| `why` | yes | 20–600 characters. The mechanism: why this costs being found, quoted or kept. Carried into the report labelled "Reviewer's explanation (not verified)". |
| `mechanism` | yes | `A` `B` `C` `D` `E` `F` (problem statement appendix) or `on-site` |
| `hurts` | yes | `ai_discoverability`, `user_retention` or `both` |
| `severity` | yes | `high`, `medium` or `low`, as you would rate it. Recorded as `proposed_severity`; every merged claim is capped at **low**. When 3 or more pages were crawled, a single-page claim drops one further band. |
| `nearest_check` | yes (may be `null`) | Informational: the scripted `check_id` closest to this claim, or `null`. Duplicates are decided by the orchestrator, not by this field (see below). |
| `affected_urls` | yes | Pages from the crawl that returned readable HTML. |
| `evidence` | yes | 1–8 assertions. Every affected URL must appear in at least one. At least one must be positive (below). |
| `suggested_action` | yes | `summary` (8–200 chars), `how` (1–8 steps), `verify` (how to confirm the fix), `effort` (`low`/`medium`/`high`, default `medium`; ranking treats every claim as medium effort) |

At most **6** claims per audit are verified; later claims are rejected.

**No markup, no external links.** `title`, `why`, `summary`, `how[]` and `verify`
may not contain HTML tags, `javascript:`, or any `http(s)` URL whose host is not
the audited site. The reason is `claim text contains markup or external links`.

**Duplicates.** A claim is dropped when any of its `affected_urls` is already
reported by a scripted finding of the gate its mechanism speaks to: `A` → access;
`B`/`C` → extractability or interpretability; `D` → freshness; `E`, `F`,
`on-site` → engagement. Setting `nearest_check` to `null` does not avoid this.

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
| `field` | `path`, `op`, `value` | the page's profile field satisfies `op` | `eq` `contains` `gt` `lt` `nonempty` are, with the exceptions below |

`field` paths are the keys of a page in `profile.json`, dotted: `status`, `title`,
`canonical`, `final_url`, `redirect_hops`, `robots_directives`, `meta_refresh`,
`meta.og:site_name`, `h1`, `h1.0`, `headings`, `words_extracted`, `noscript_words`,
`jsonld.types`, `jsonld.offers`, `links.internal`, `links.pdf`, `links.tel`, `forms`,
`iframes`, `images.missing_alt`, `hreflang`, `lang`, `role`.

`op`: `eq`, `ne`, `contains` / `lacks` (substring, or any list item),
`gt` / `lt` (numbers), `empty` / `nonempty` (`null`, `""`, `0`, `[]`, `{}` are empty).
`eq` and `ne` compare `null` strictly: `canonical eq "None"` does not match a
missing canonical; write `{"op": "empty"}` instead.

**What counts as positive.** A positive assertion must say something specific
about the page that is wrong or unusual:

- `field` assertions on `url`, `final_url`, `status`, `role`, `content_type` and
  `redirect_hops` are never positive: they say which page this is, not what is
  wrong with it. Use them as supporting assertions.
- `eq null` / `eq ""` is an absence, not positive.
- `nonempty`, `gt` and `lt` never carry a claim on their own (`title nonempty`,
  `words_extracted gt 1` are true of almost any page). Use `eq` or `contains` with a
  value specific to the problem.
- Any positive assertion that holds on **every** readable page of the crawl
  (`</html>`, the site name, `lang eq "en"`, a shared header) is rejected outright:
  `evidence is true of every page`.
- Steps, `verify` and the summary may not carry markup, `javascript:`, or links
  off the audited site (absolute, `//host` or bare `www.host`); each step is at
  most 300 characters.
- Known residual: a claim that restates a scripted finding under a *different*
  mechanism letter can slip past duplicate detection. It is capped at low like
  every claim; do not do it on purpose.

**Why one positive assertion is required:** "this page lacks a price" is true of
every page that is not about prices, and "status eq 200" is true of every page
the crawl kept. An absence only means something next to a fact that shows what
is wrong on this page.

## Fixes

`fixes` carries site-specific steps for scripted findings, written in the site's
own words. At most **5** per audit.

| Field | Rule |
|---|---|
| `check_id` | The scripted finding's `check_id` (from `scripted_findings` in the profile). |
| `url` | One of that finding's `affected_urls`, crawled successfully. |
| `quote` | 6–300 characters that appear in the page's extracted or full text. An invented quote rejects the fix. |
| `site_specific` | 1–8 steps for this site. Same no-markup, no-external-links rule as claims. |

A verified fix is merged into the finding as `suggested_action.site_specific[]`
and `suggested_action.grounded_on: {url, quote}`. One fix per finding; a fix
whose `url` the named finding does not report is rejected by the orchestrator.

## Example

```json
{
  "claims": [
    {
      "title": "/pricing puts its plan table inside an iframe",
      "why": "A non-rendering fetcher reads the iframe tag, not the document inside it, so the pricing page has no price to quote.",
      "mechanism": "C",
      "hurts": "ai_discoverability",
      "severity": "high",
      "nearest_check": null,
      "affected_urls": ["https://example.com/pricing"],
      "evidence": [
        {"url": "https://example.com/pricing", "type": "field", "path": "role", "op": "eq", "value": "pricing"},
        {"url": "https://example.com/pricing", "type": "field", "path": "iframes", "op": "contains", "value": "plans.example-widgets.com"},
        {"url": "https://example.com/pricing", "type": "field", "path": "words_extracted", "op": "lt", "value": 100}
      ],
      "suggested_action": {
        "summary": "Render the plan names and prices as HTML on /pricing, and keep the widget for the interactive part.",
        "how": [
          "Add a static table with each plan's name and monthly price above the iframe.",
          "Keep the iframe for the calculator only."
        ],
        "verify": "curl -s https://example.com/pricing shows the plan names and prices in the HTML body.",
        "effort": "medium"
      }
    }
  ],
  "fixes": [
    {
      "check_id": "C5_faq_content_unmarked",
      "url": "https://example.com/",
      "quote": "What does the starter plan include?",
      "site_specific": [
        "Wrap 'What does the starter plan include?' and the paragraph under it in FAQPage JSON-LD.",
        "Keep the answer to one paragraph that stands on its own."
      ]
    }
  ]
}
```

## Common rejections

| Reason | Fix |
|---|---|
| `evidence names a URL that was not crawled` | Use a URL exactly as it appears in `profile.json` `pages[].url`. |
| `evidence does not hold` | The claim is not true of the crawl. Drop it. |
| `every assertion is an absence or an identity field` | Add a positive assertion about a page-specific field or text. |
| `evidence is true of every page` | Pick a value that distinguishes the affected page from the rest. |
| `claim text contains markup or external links` | Plain text only; link only to the audited site. |
| `no evidence is given for affected URL(s)` | Add an assertion per affected URL, or remove the URL. |
| `duplicates scripted check …` | The scripted finding already covers that page for that gate. Drop it. |
| `over the limit of 6 claims` | Keep the six best-evidenced claims. |
| `quote is not on the page` (fix) | Quote the page's own text, from `text_excerpt` or the page. |
| `malformed claim: …` | A field has the wrong type (for example `url` given as a list). Only that claim is rejected. |
