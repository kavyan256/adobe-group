# Mechanism checklist

Each row is a problem the scripted checks do not measure. `page_profile.py` matches
the rows with an item name mechanically: every page meeting the threshold appears in
`profile.json` `review_candidates[]`, unless a scripted check already reports it there,
and needs a disposition. A threshold only says the page has the numbers; the "Not a
problem when" column is where judgement comes in. Rows marked *read* have no candidates,
so check them yourself.

Ground rules for every claim:

- Claim only what the crawl shows. Rankings, traffic, what an assistant answers,
  off-site reputation, personalization and the owner's intent are not observable here.
- One page is one page: call a problem site-wide only if every affected page is listed
  with evidence.
- A page meant to be empty or excluded (login, cart, search, legal) is not a defect for
  being so.

Already scripted, so not rows here: soft 404 (A11), meta-refresh redirect (A10), per-bot
noindex and nosnippet (A2, A3), dead internal pages (A9), duplicate or generic titles
(C7), product markup with no offer (C1_product_markup_absent).

## A — Can the crawler get in and reach the real page?

| Item | Threshold | Evidence for a claim | Not a problem when |
|---|---|---|---|
| `wall_instead_of_content` | content role, `words_extracted` < 80, and a password form or a title such as "Sign in", "Access denied", "Verify you are human", "Enable cookies" | the `title` or the form, plus `words_extracted`; hurts visitors too (`hurts: both`) | the page is a login or account page by purpose |
| `content_redirected_to_home` | `redirect_hops` > 0 and `final_url` is the start URL, on a URL whose own path is not `/` | `redirect_hops` and `final_url`, plus a positive assertion such as the page's `title` | the URL is a retired alias the site no longer links to |
| `canonical_points_at_broken_page` | `canonical` names a crawled page that did not return 200 | `canonical eq` that URL on this page, `status ne 200` on the target | — |
| `hreflang_to_failing_page` | an `hreflang` link to a crawled page that did not return 200 | `hreflang contains` that URL, `status ne 200` on the target | — |

## B — Would an assistant pick and quote this page?

| Item | Threshold | Evidence for a claim | Not a problem when |
|---|---|---|---|
| `facts_only_as_pdf` | role pricing, product or about; `links.pdf` nonempty; `words_extracted` < 150 | `links.pdf contains` the PDF, plus `words_extracted` | the page also states the facts in its text |

## C — Can a machine read the fact?

| Item | Threshold | Evidence for a claim | Not a problem when |
|---|---|---|---|
| `main_content_in_iframe` | content role, `iframes` nonempty, `words_extracted` < 100 | `iframes contains` the frame's source, plus `words_extracted` | the iframe is a map, video or form beside the page's real text |
| `content_only_in_noscript` | `noscript_words` > 50, `words_extracted` < 50 | both counts | the noscript text repeats what the page already says |
| `markup_type_contradicts_page` | role pricing or product; `jsonld.types` only article or blogposting | `jsonld.types contains` the article type | the page really is an article about the product |

## D — Do the site's own statements agree, and is the brand unambiguous?

| Item | Threshold | Evidence for a claim | Not a problem when |
|---|---|---|---|
| `brand_name_differs_across_pages` | two or more `og:site_name` values across content pages | `meta.og:site_name eq` each value on one of its pages | a sub-brand section named as such, or the organisation's own abbreviation |
| *read:* contact details disagree | — | `text_contains` phone or address A on one page and a different B on another | the pages label separate offices or departments |
| *read:* stale year on an evergreen page | — | role pricing, product or about, and `title` or `h1` contains a year before last year | an archived article or a dated report |

## F — Is the substance there as readable text?

| Item | Threshold | Evidence for a claim | Not a problem when |
|---|---|---|---|
| `thin_content_page` | role pricing, product or about; `words_extracted` < 80; no payload island, iframe or noscript content | `words_extracted`, plus a positive assertion about what the page does say | the page is short by purpose and still states its one fact |

## On-site — Will a visitor who arrives stay?

| Item | Threshold | Evidence for a claim | Not a problem when |
|---|---|---|---|
| `consent_text_leads_content` | content role; the first 40 words of extracted text mention cookies or consent | `text_contains` the consent phrase; the opening a snippet or visitor gets is the banner (`hurts: both`) | the page is about cookies or consent, or the word describes the product |
| `pricing_answer_not_in_opening` | role pricing, `words_extracted` ≥ 150, no number in the first 120 words | `field title contains` the pricing word, plus `text_contains` what the opening says instead | pricing is quote-based and the opening says so |
| *read:* objections left unanswered | — | role pricing or product; `text_lacks` cancellation, refund, return, delivery and trial terms, plus a positive assertion about what the page sells | a free or non-commercial offering |
| *read:* text in a different language from `lang` | — | `field lang eq` one language, plus `text_contains` a phrase clearly in another | a bilingual page that labels both languages |
