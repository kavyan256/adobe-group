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
```

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
| `A5_canonical_problem` | medium | Misattributes credit; rarely fully blocking. |
| `A8_robots_token_unrecognised` | medium | A robots.txt rule that looks active and binds no crawler. |
| `A4_redirect_chain` | low | Wasteful, seldom decisive. |
| `A6_sitemap_missing` | low | Discovery still works through links. |
| `B1_fact_absent` | high | The fact is not in the response at all. |
| `B4_empty_shell` | high | Nothing to extract for a non-rendering fetcher. |
| `B1_fact_script_only` | medium | In the bytes, not in the extracted text: hard to reach, not invisible. |
| `B6_filler_heavy` | low | Extraction works, but returns mostly site-wide boilerplate. |
| `C1_structured_data_invalid` | high | Looks correct, is silently discarded, and nobody notices. |
| `C2_markup_text_contradiction` | high | Contradictory evidence lowers trust in everything else the site says. |
| `C1_structured_data_absent` | medium | Facts may still be readable in prose. |
| `C3_entity_unanchored` | medium | Nothing separates the brand from others sharing its name. |
| `C5_faq_content_unmarked` | medium | Content already in quotable Q&A shape, with nothing saying so. |
| `C6_entity_name_conflict` | medium | Several names for one entity leave a machine no anchor. |
| `X1_low_quotability` | medium | Extractable but not citable: assistants quote passages, not pages. |
| `X2_no_citation_anchor` | low | The page can still be cited as a whole. |
| `D4_internal_contradiction` | high | The same reasoning as `C2`, across pages. |
| `D1_no_date_signals` | medium | Recency cannot be demonstrated. |
| `D3_content_stale` | medium | Superseded claims stay live and quotable. |
| `D5_no_corroboration_hooks` | medium | A claim only the site makes is fragile. |
| `D2_stale_copyright` | low | A cue, not a cause. |
| `E1`, `E3`, `E4`, `E7`, `E9`, `E10` | medium | Engagement risk factors. All are `static_heuristic`, so medium is also their ceiling. |
| `E2`, `E5`, `E6` | low | Real but minor friction. |
| `R_agent_review` | as proposed, at most medium | A reviewer's claim, verified against the crawl but not a tested check, so it is always `static_heuristic`. |

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
broken out in `summary.latent_findings`. The severity counts cover active findings
only.
