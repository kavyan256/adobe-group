# Severity rationale

Severity is a published table plus a few documented modifiers, and the arithmetic
is printed into every finding as `severity_rationale`. Only blast radius and
coverage vary at runtime, and both are banded, so the ordering is stable across
machines.

## The arithmetic

```
base            declared per check (below)
× blast_radius  site_wide 1.0 | template 0.8 | single_page 0.5   (below 0.7 demotes one band)
caps            measurement_basis == static_heuristic -> at most medium
                confidence        == heuristic        -> at most high
                coverage < 3 pages                    -> blast radius not applied
                status            == latent           -> at most low
                status            == confirm_intent   -> at most low
                check_id          == R_agent_review   -> at most low
```

The agent-review cap comes first among the caps, right after blast radius: a claim
is not a tested check, so its ceiling is `low` however the reviewer rated it, and
`severity_rationale` shows `cap(agent_review)-> low` when the cap bit.

A finding that is both deliberate-looking and behind an access blocker is reported
as `latent`, keeping its `intent_signals` alongside `blocked_by`.

## Base severities

Each is justified by mechanism, never by how common the defect is: calibrating to
prevalence would flag a fixed share of sites whatever their actual state.

| Check | Base | Why |
|---|---|---|
| `A1_retrieval_agent_blocked` | critical | Retrieval agents gate citation; nothing downstream can matter. |
| `A3_noindex` | critical | Removes the page from the indexes assistants draw on. |
| `A7_site_unreadable` | critical | No automated client can read anything, so it must never read as "no findings". |
| `A2_snippet_suppressed` | high | The page stays indexed, but its text cannot be quoted. |
| `A3_noindex_utility` | medium | The same fact as `A3`, on templates sites exclude on purpose; reported as `confirm_intent`, so low. |
| `A9_key_page_broken` | high | A pricing, product or contact URL the site itself links answers 404/410/5xx: the fact page does not exist for crawler or visitor. |
| `A5_canonical_problem` | medium | An off-domain or homepage canonical hands the page's credit to another URL. |
| `A8_robots_token_unrecognised` | medium | A robots.txt rule that looks active and binds no crawler. |
| `A9_broken_pages` | medium | Linked or sitemap-listed URLs that error; each is a dead end for both audiences. |
| `A11_soft_404` | medium | HTTP 200 around a not-found page indexes the error as content; heuristic, so never above high. |
| `A5_canonical_missing` | low | No canonical at all: an indexer picks a URL on its own, usually the one it crawled. |
| `A10_meta_refresh` | low | A meta refresh acts as a redirect many fetchers ignore; the fetched stub is what gets indexed. |
| `A4_redirect_chain` | low | Wasteful, seldom decisive. |
| `A6_sitemap_missing` | low | Discovery still works through links. |
| `B1_fact_absent` | high | The fact is not in the response at all. |
| `B4_empty_shell` | high | Nothing to extract for a non-rendering fetcher. |
| `B1_fact_script_only` | medium | In the bytes, not in the extracted text: hard to reach, not invisible. |
| `B6_filler_heavy` | low | Extraction works, but returns mostly site-wide boilerplate. |
| `C1_structured_data_invalid` | high | Looks correct, is silently discarded, and nobody notices. |
| `C2_markup_text_contradiction` | high | Contradictory evidence lowers trust in everything else the site says. |
| `C1_product_markup_absent` | medium | A product page is where structured data carries the fact itself (`Offer.price`); without it the price is prose or nothing. |
| `C3_entity_unanchored` | medium | Nothing separates the brand from others sharing its name. |
| `C6_entity_name_conflict` | medium | Several names for one entity leave a machine no anchor. |
| `C7_title_problem` | medium | The title is the label an index stores and a citation shows; blank, generic or shared, the page has no identity. |
| `C1_structured_data_absent` | low | Facts may still be readable in prose; the indexers that read JSON-LD also read the text. |
| `C5_faq_content_unmarked` | low | Questions without a self-contained answer each: quotable already, just less cleanly. |
| `X1_low_quotability` | low | Extractable but awkward to quote: a style cost, not a gate. |
| `D4_internal_contradiction` | high | The same reasoning as `C2`, across pages. |
| `D1_no_date_signals` | medium | Recency cannot be demonstrated. |
| `D3_content_stale` | low | Age is a prompt to review, not proof the page is wrong; reference material is often old and right. |
| `D2_stale_copyright` | low | A cue, not a cause. |
| `E1_form_friction`, `E1_unlabelled_input`, `E3`, `E4`, `E7`, `E9`, `E10` | medium | Engagement risk factors. All are `static_heuristic`, so medium is also their ceiling. |
| `E11_no_viewport` | medium | The one engagement check that is a plain fact (`static_fact`, `deterministic`): the tag is absent or it is not, and without it phones render the page at desktop width. Medium, not high, because the page is still readable after a pinch-zoom; it is not capped like the other E checks. |
| `E2`, `E5`, `E6`, `E12` | low | Real but minor friction. `E12` (no title/h1, or the homepage h1 repeated) is the weakest heuristic here: a breadcrumb or nav highlight the audit cannot see may already orient the visitor. |
| `R_agent_review` | low (proposed severity recorded, then capped) | A reviewer's claim whose evidence was checked against the crawl; not a tested check, so it is always `static_heuristic` and never above low. |

## Why latent, not suppressed

1. **Suppression sets a second-audit trap.** The owner fixes robots.txt, re-audits,
   and meets a wave of findings nobody warned them about.
2. **robots.txt is per-agent.** A page closed to `OAI-SearchBot` may be open to
   `Claude-User`.
3. **User-initiated fetches still reach blocked pages**, which still need
   extractable facts.

So a finding is latent only when its pages carry noindex, or robots.txt refuses them
to **every** retrieval agent. A site that blocks one assistant is still read by the
rest, and its findings stay active at full severity. Engagement findings are never
latent: robots.txt and noindex do not stop a human visitor.

Latent findings are counted in `summary.total_findings` (always `len(findings)`) and
in the severity counts `summary.{critical,high,medium,low}`, which add up to it;
they are broken out in `summary.latent_findings`, and `summary.active_by_severity`
gives the counts over active findings only.
