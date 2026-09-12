---
name: fact-extractability-audit
description: >-
  Determine whether the specific facts a site needs to be quoted on — price,
  contact details, what the company is — survive bot-grade text extraction of
  the raw HTML, and whether they are typed unambiguously. Grades every expected
  fact T0–T3 by extraction difficulty, parses hydration payloads
  (__NEXT_DATA__, __NUXT__, Apollo/Redux) to distinguish "invisible" from
  "hard to reach", validates structured data, detects markup-vs-text
  contradictions and conflicting brand names, and scores passage quotability.
  Use standalone to answer "can an assistant actually quote my pricing page?",
  or as gates 2 and 3 of a full AI-readiness audit.
license: Apache-2.0
allowed-tools: Bash, Read
---

# Fact Extractability Audit (Gates 2 & 3)

## When to use

When a site is reachable but assistants still omit it or get its facts wrong. This
explains why a page that looks complete in a browser is empty to a machine. Also
runs as gates 2 and 3 of `audit-orchestrator`.

## Inputs

A site bundle, as a path argument or on stdin. JSON-LD and page text come
pre-normalised in `page["derived"]`; this skill never parses JSON-LD itself.

## Procedure

1. **Grade obligated facts T0–T3.** A page's URL role obligates it to a fact: pricing
   and product pages a price, contact pages a phone number or email (a `tel:` or
   `mailto:` link counts). T0 extracted
   prose, T1 JSON-LD, T2 only in meta tags or a hydration payload, T3 nowhere.
   T3 → `B1_fact_absent`; T2 → `B1_fact_script_only`.
2. **Empty shells.** Under 30 words of extracted text plus a `#root`, `#app`,
   `#__next` or `#__nuxt` mount element → `B4_empty_shell`.
3. **Structured data.** A block that fails `json.loads` → `C1_structured_data_invalid`.
   No JSON-LD on a home, product, pricing, about or blog page →
   `C1_structured_data_absent`.
4. **Contradiction.** A single declared `Offer.price` that matches none of the
   currency-marked prices on the page → `C2_markup_text_contradiction` (heuristic).
5. **Entity.** A homepage without `Organization` + `sameAs` → `C3_entity_unanchored`.
   `Organization.name` and `og:site_name` sharing no words → `C6_entity_name_conflict`.
6. **Quotability.** Three or more question headings with no FAQPage markup →
   `C5_faq_content_unmarked`. Passages opening with an unresolved reference
   ("This means…") → `X1_low_quotability`. Section headings with no `id` →
   `X2_no_citation_anchor`.
7. **Filler.** A 300+ word page where over 45% of the text is sentences repeated on
   most of the site → `B6_filler_heavy`.

```bash
python3 scripts/check_extractability.py bundle.json
```

## Output

A JSON array of findings. B1 findings carry `detail.tier` and a `curl` command that
reproduces the evidence.

## References

- `references/extraction-tiers.md` — the tier model, payload islands, where
  expectations come from, and the declared limits
