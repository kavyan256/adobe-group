# Mechanism checklist for agent review

Walk this in order. Each item names the profile fields to read, the evidence that
proves it, and when it is **not** a problem. Items are the problems the scripted
checks do not measure; anything in `scripted_findings` is already covered.

Ground rules:

- Claim only what the crawl shows. Rankings, traffic, what an assistant actually
  answers, off-site reputation, personalization (mechanism E) and the owner's
  intent are not observable here — never claim them.
- One page is one page. Do not call a problem site-wide unless every affected
  page is listed with evidence.
- A page that is supposed to be empty or excluded (login, cart, search, legal) is
  not a defect for being so.

## A — Can the crawler get in and reach the real page?

| Item | Look at | Evidence | Not a problem when |
|---|---|---|---|
| **Soft 404** | `status`, `title`, `h1` | `status eq 200` + `title` or `h1` `contains` "not found" / "404" / "no longer available" | a search page reporting no results |
| **Wall instead of content** | `role`, `words_extracted`, `forms[].has_password`, `title`, `h1` | `role eq` a content role + `words_extracted lt 80` + a password form, or a title such as "Sign in", "Access denied", "Verify you are human", "Enable cookies" | the page's role is `utility` |
| **Content page redirected to the homepage** | `redirect_hops`, `final_url` | `redirect_hops gt 0` + `final_url eq` the start URL, on a URL whose own path is not `/` | the URL is a known retired alias |
| **Meta-refresh redirect** | `meta_refresh` | `meta_refresh contains "url="` | a refresh with no target on a live-updating page |
| **Bot-specific noindex or nosnippet** | `robots_directives` | an entry such as `bingbot: noindex` or `gptbot: nosnippet` (scripts read only `robots`, `googlebot` and the header) | the named bot is a training-only crawler |
| **Canonical pointing at a broken page** | `canonical` on page P, `status` on page Q | `canonical eq` Q's URL on P + `status ne 200` on Q (both crawled) | Q was not crawled — then there is no evidence |
| **hreflang to a page that fails** | `hreflang` on P, `status` on Q | `hreflang contains` Q's URL + `status ne 200` on Q | Q was not crawled |

## B — Would an assistant pick and quote this page?

| Item | Look at | Evidence | Not a problem when |
|---|---|---|---|
| **Several pages share one title** | `title` across pages | `title eq` the same string on 3+ URLs | paginated archives with page numbers elsewhere |
| **Facts published only as PDFs** | `links.pdf`, `words_extracted`, `role` | `role eq` pricing/product/about + `links.pdf nonempty` + `words_extracted lt 150` | the page also states the facts in its text |

## C — Can a machine read the fact?

| Item | Look at | Evidence | Not a problem when |
|---|---|---|---|
| **Main content inside an iframe** | `iframes`, `words_extracted`, `role` | `iframes nonempty` + `words_extracted lt 100` on a content role | the iframe is a map or video beside real text |
| **Content only in `<noscript>`** | `noscript_words`, `words_extracted` | `noscript_words gt 50` + `words_extracted lt 50` | noscript holds only a tracking pixel |
| **Product markup with no offer** | `jsonld.types`, `jsonld.offers`, `role` | `role eq product` + `jsonld.types contains "product"` + `jsonld.offers empty` | the product is genuinely not for sale ("contact us") and the text says so |
| **Markup type contradicts the page** | `jsonld.types`, `role` | `role eq pricing`/`product` + `jsonld.types` only `article`/`blogposting` | the page really is an article about the product |

## D — Do the site's own statements agree, and is the brand unambiguous?

| Item | Look at | Evidence | Not a problem when |
|---|---|---|---|
| **Contact details disagree across pages** | text of contact/about/home pages | `text_contains` phone or address A on one page + `text_contains` a different B on another | the pages label separate offices or departments |
| **Brand name differs across pages** | `meta.og:site_name`, `title` | `field eq` name X on one page + `field eq` name Y on another | a sub-brand section named as such |
| **Stale year on an evergreen page** | `title`, `h1`, `role` | `role eq` pricing/product/about + `title` or `h1` `contains` a year before last year | an archived article or a dated report |

## F — Is the substance there as readable text?

| Item | Look at | Evidence | Not a problem when |
|---|---|---|---|
| **Thin content page** | `role`, `words_extracted`, `payload_islands` | content role + `words_extracted lt 80` + `payload_islands empty` (a script-heavy shell is B4's finding) | a contact page that is legitimately short and has its contact route |

## On-site engagement

| Item | Look at | Evidence | Not a problem when |
|---|---|---|---|
| **Linked pages that are dead** | `status` | `status eq 404`/`410`/`500` on a crawled internal URL (the crawl reached it from the sitemap or homepage) | the URL is deliberately gone and nothing links to it — if unsure, do not claim |
| **Content gated behind a login** | `forms[].has_password`, `role`, `words_extracted` | pricing/product/about page + password form + `words_extracted lt 80` | the role is `utility` |
