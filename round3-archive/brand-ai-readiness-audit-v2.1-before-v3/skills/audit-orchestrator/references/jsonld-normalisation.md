# JSON-LD normalisation

Every skill in this marketplace reads structured data from one place:
`page["derived"]["jsonld"]`, produced once by `scripts/bundle.py::normalise_jsonld`.
No skill parses JSON-LD itself.

## Why it lives in the crawl layer

Parsing is the crawl layer's job; judging is the skills'. With each skill parsing on
its own, one report both claimed a site had no `sameAs` links and listed those links
as already in place. One parser cannot disagree with itself. Skills still consume
data, not code, so each one runs standalone on a bundle.

## What normalisation does

| Input shape | Handling |
|---|---|
| Multiple `<script type="application/ld+json">` tags | Merged into one node stream; `block_count` records how many. |
| Top-level array | Flattened. |
| `{"@context":…, "@graph":[…]}` | `@graph` members are hoisted into the stream. The wrapper is kept only if it carries properties of its own — Yoast and RankMath emit a bare wrapper. |
| Nested entities (`Product.offers`, `WebPage.publisher`) | Collected into the stream **and** left in place inside the parent, so a check can still read `product["offers"]["price"]` structurally. Depth capped at 6, nodes at 300. |
| `"@type": "Organization"` | `types: ["organization"]` |
| `"@type": ["Organization","Corporation"]` | `types: ["corporation","organization"]` |
| `"@type": "http://schema.org/Organization"` or `"schema:Organization"` | `types: ["organization"]` |
| Missing `@type` | `types: []`; the node is not treated as an entity. |
| Script with a comment or CDATA child | Read with `get_text()`, wrapper stripped. `tag.string` is `None` whenever the element has more than one child node, and reading it silently produced an empty object. |

`@type` is never rewritten inside `props` — a check that wants the original sees
the original.

## What "malformed" means

**Malformed means `json.loads` raised. Nothing else.**

Not malformed: an unknown `@type`, a missing required property, a non-schema.org
vocabulary, an `@graph` with unexpected members. An empty block is *inert*, not
broken, and is counted separately as `empty_blocks`.

This definition is narrow on purpose, because `C1_structured_data_invalid` is a
`high` severity finding. Telling a site its markup is broken when it merely uses
a vocabulary we do not recognise is the kind of false positive that costs a
reader's trust in every other finding in the report.

## Derived aggregates

`types_present`, `sameas`, `dates` and `text` are all computed from the same flat
node stream, so no two consumers can hold different views of one page.
