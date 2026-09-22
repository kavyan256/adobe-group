---
name: fact-extractability-audit
description: >-
  Determine whether the specific facts a site needs to be quoted on — price,
  contact details, what the company is — survive bot-grade text extraction of
  the raw HTML, and whether they are typed unambiguously. Grades every expected
  fact T0–T3 by extraction difficulty, parses hydration payloads
  (__NEXT_DATA__, __NUXT__, Apollo/Redux) to distinguish "invisible" from
  "hard to reach", validates structured data, detects markup-vs-text
  contradictions, conflicting brand names and missing or duplicated titles, and
  scores passage quotability. Runs on its own against a bundle from
  audit-orchestrator to answer "can an assistant actually quote my pricing
  page?", or as gates 2 and 3 of a full AI-readiness audit.
license: Apache-2.0
allowed-tools: Bash Read
compatibility: Python 3.10+, httpx, beautifulsoup4
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

1. **Grade obligated facts T0–T3.** A page's role obligates it to a fact, but only with
   evidence: pricing and product pages a price when the page shows it sells something
   (Product/Offer markup, a cart form, a price on the page, a pricing URL or title);
   the contact page itself (not a directory or sub-page) a phone number or email (a
   `tel:` or `mailto:` link counts). T0 visible
   text, T1 JSON-LD, T2 only in meta tags or a hydration payload, T3 nowhere.
   T3 → `B1_fact_absent`; T2 → `B1_fact_script_only`.
2. **Empty shells.** Under 30 words of extracted text plus a `#root`, `#app`,
   `#__next` or `#__nuxt` mount element → `B4_empty_shell`.
3. **Structured data.** A block that fails `json.loads` → `C1_structured_data_invalid`.
   A product page that shows it sells something (a cart form, `og:type product` or a
   visible price) but has no `Product` node → `C1_product_markup_absent` (medium: that
   is where the price itself should be typed). No JSON-LD at all on a home, pricing,
   about or blog page → `C1_structured_data_absent` (low).
4. **Contradiction.** A single declared `Offer.price` that matches none of the
   currency-marked prices on the page → `C2_markup_text_contradiction` (heuristic).
   Prices are read with one parser: `$1,299.00`, `1.299,00`, `49,00` and `₹1,29,999`
   all compare as numbers.
5. **Entity.** No crawled page declares an organisation-like node (`Organization`
   and its subtypes, `LocalBusiness` and its subtypes such as `Restaurant`, `Store`,
   `Dentist`) with `sameAs` → `C3_entity_unanchored`. `Organization.name` and
   `og:site_name` sharing no words → `C6_entity_name_conflict`.
6. **Titles.** A `<title>` that is missing, empty, a CMS default (`Home`, `Untitled`,
   `Document`…) or identical on three or more crawled pages → `C7_title_problem`.
7. **Quotability.** Three or more question headings on a non-article page with no
   FAQPage markup pairing each with a self-contained answer →
   `C5_faq_content_unmarked`. Passages opening with an unresolved reference ("This
   means…") → `X1_low_quotability`.
8. **Filler.** A 300+ word page where over 45% of the text is sentences repeated on
   most of the site → `B6_filler_heavy`.

```bash
python3 scripts/check_extractability.py bundle.json
```

## Output

A JSON array of findings. B1 findings carry `detail.tier` and a `curl` command that
reproduces the evidence.

## Interpreting results

- `B1_fact_absent` on a pricing page that says "contact sales" is correct as measured
  and wrong as advice: the fact is deliberately absent. Mark it `confirm_intent`. A
  contact page that offers a form but no phone/email already arrives as
  `confirm_intent` at low; leave it unless the owner wants to be quotable.
- `B1` on a page whose role came from a title segment or link label (see
  `references/extraction-tiers.md`) deserves a look at the URL: a "Pricing" link to a
  comparison article carries no obligation.
- `C2` and `D4` are heuristic by design: sale versus list price, variants and
  tax-inclusive display all differ legitimately. Read the page before repeating them.
- `C7` "shared title" on a paginated listing (`/blog?page=2`) is the template
  working as intended; downgrade to low.
- `C3` is silent whenever any page carries `sameAs` on an organisation-like node, so a
  `C3` next to an `already_in_place` entry about `sameAs` means the anchor is on a
  `Person` or `WebSite` node instead: report it as a note, not a defect.

## References

- `references/extraction-tiers.md` — the tier model, payload islands, where
  expectations come from, and the declared limits
