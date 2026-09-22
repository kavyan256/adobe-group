---
name: fact-extractability-audit
description: >-
  Determine whether the specific facts a site needs to be quoted on — price,
  contact details, what the company does — survive bot-grade text extraction of
  the raw HTML, and whether they are typed unambiguously. Grades every expected
  fact T0–T3 by extraction difficulty, parses hydration payloads
  (__NEXT_DATA__, __NUXT__, Apollo/Redux) to distinguish "invisible" from
  "hard to reach", validates structured data, detects markup-vs-text
  contradictions, and scores passage quotability. Use standalone to answer "can
  an assistant actually quote my pricing page?", or as gates 2 and 3 of a full
  AI-readiness audit.
license: Apache-2.0
allowed-tools: Bash, Read
---

# Fact Extractability Audit (Gates 2 & 3)

## When to use

Standalone, when a site is reachable but assistants still get its facts wrong or
omit it from answers. This is the skill that explains *why a page that looks
perfect in a browser is empty to a machine.*

## The reasoning this skill encodes

### What an assistant actually reads

Assistant fetchers run a two-stage pipeline: raw bytes, then a
boilerplate-stripping text extractor (Readability/Trafilatura class) that
converts HTML to text **before the model sees anything**. That stage discards
`<script>`, `<style>`, `nav` and `footer` by construction.

Critically: **the major AI retrieval agents do not execute JavaScript.**
`GPTBot`, `OAI-SearchBot`, `ChatGPT-User`, `ClaudeBot`, `PerplexityBot` and
`Bytespider` all fetch raw HTML. Googlebot is the outlier that renders. This
makes *"renders fine in Chrome, ranks fine in Google, invisible to assistants"* a
real and common state.

### Why we do not need a headless browser

The obvious design is to diff raw HTML against a rendered DOM. We deliberately
reject it. The rendered DOM was never the *measurement* — it was only a *fact
source*, and a browser cannot ship inside the size budget, cannot run offline,
and introduces the nondeterminism that would falsify our determinism claim.

Instead we ask an absolute question that needs one HTTP GET:

> **In what form does each expected fact exist in the raw response?**

| Tier | Where the fact lives | Verdict |
|---|---|---|
| **T0** | Visible prose or a heading | pass — directly quotable |
| **T1** | JSON-LD / microdata / RDFa | pass — machine-readable by design |
| **T2** | *Only* inside a script payload | **medium** — present in the bytes, absent from the text |
| **T3** | Absent from the raw bytes entirely | **high** — genuinely invisible |

**The T2 tier is the honest core of this design.** A naive audit that reports
"SPA, therefore invisible" false-positives across the entire Next.js and Nuxt
web, because hydration payloads frequently *do* carry the facts in extractable
form. We parse those payloads before firing. Where a fact is found only in
`__NEXT_DATA__`, that is the single strongest piece of evidence this marketplace
can produce — and it is reported as *hard to reach*, not as *invisible*.

### Where expected facts come from — and why this is not circular

Sourcing expectations only from structured data would make the check strongest on
exactly the sites that need it least. Two independent sources are combined:

1. **Declared literals** — values the site itself asserts, in JSON-LD, OG/meta,
   `<title>`, `<noscript>`, sitemap entries, and parsed payload islands. Test:
   does the literal also reach T0? *Catches: the fact exists in bytes but not text.*
2. **Role obligations** — derived from the URL slug and `<title>`, surfaces that
   are **not under test**. A page at `/pricing` is committing to contain a
   currency-and-numeral token; `/contact` to a contact method. *Catches: the fact
   does not exist at all.*

Where neither source applies — a pure client-side shell with no title, nav or
payload — empty-shell detection covers the gap, narrowly scoped to a `<body>`
containing a single mount element and fewer than 30 words.

### Beyond presence: can the fact be *quoted*?

Assistants quote **passages**, not pages. A paragraph opening *"This means…"* or
*"Our platform…"* loses its subject the moment it is lifted out of context, so it
cannot be cited even though it is perfectly extractable. `X1_low_quotability`
flags passages that open with unresolved anaphora. `X2_no_citation_anchor` checks
whether headings carry stable `id`s, which determines whether an assistant can
link to a *location* rather than to the homepage.

## Structured data comes pre-normalised

This skill does not parse JSON-LD. It reads `page["derived"]["jsonld"]` from the
bundle, where `@graph` is already flattened, `@type` is already a list of bare
lowercase names, and nested entities are already hoisted while remaining
readable in place. Page text likewise comes from `page["derived"]["text"]`, in
two defined forms (`extracted` and `full`).

One parser means the skills cannot contradict each other about what a page says.
See `../audit-orchestrator/references/jsonld-normalisation.md`. Given a bundle
that predates this contract, the JSON-LD-dependent checks are reported in
`checks_skipped[]` rather than approximated.

Checks added in 2.1: `C5_faq_content_unmarked` (question headings with no FAQPage
markup), `C6_entity_name_conflict` (`Organization.name` and `og:site_name`
disagree), and `B6_filler_heavy` (extraction succeeds but returns mostly
site-wide boilerplate).

## Inputs

A site bundle, as a path argument or on stdin.

## Procedure

1. For each page, produce three views of the same response: **extracted prose**
   (boilerplate stripped), **structured data**, and **payload islands**.
2. For each fact obligated by the page's role, grade T0–T3 and emit
   `B1_fact_absent` (T3) or `B1_fact_script_only` (T2).
3. Detect empty shells (`B4`) and facts locked in unlabelled images (`B5`).
4. Validate structured data (`C1`) — malformed JSON is a separate, higher-severity
   finding than absent markup, because it looks correct while providing nothing.
5. Compare declared prices against visible text (`C2`), conservatively.
6. Check homepage entity anchoring via `Organization` + `sameAs` (`C3`).
7. Score quotability (`X1`) and citation anchors (`X2`).

```bash
python3 scripts/check_extractability.py bundle.json
```

## Output

A JSON array of findings, each carrying the tier in `detail.tier` and an evidence
string a reader can reproduce with `curl`.

## Known limits, declared rather than hidden

- **Facts fetched by client-side XHR after load, with no server-rendered
  payload, are invisible to this method.** They will grade T3, which is the right
  answer for a non-rendering fetcher, but we cannot distinguish "absent" from
  "arrives later via API". This is a real false-negative surface.
- **No layout information.** CSS-hidden versus visible, above-the-fold position,
  and computed styles all require a browser.
- **The contradiction check is deliberately conservative** (`C2`). Sale-vs-list
  pricing, `AggregateOffer`, per-variant prices, tax-inclusive display and locale
  formats (`1.299,00 €`) all legitimately differ from a single declared `price`.
  We fire only on a single unambiguous declared value whose digits appear nowhere
  in the visible text, and mark the finding `heuristic`.
- **Our extractor approximates real fetchers' boilerplate rules.** They differ in
  detail; the fixture suite in `tests/` pins our behaviour so changes are visible.

## References

- `references/extraction-tiers.md` — the tier model, payload island formats, and
  the non-circularity argument in full
