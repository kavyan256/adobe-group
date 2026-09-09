# Severity rationale

Severity is a **published table plus two documented modifiers**, not a formula.

An earlier design proposed `severity = f(gate_position, blast_radius, confidence)`
and called it a derivation. It was not one: `gate_position` and `confidence` are
both *constants per check type* — gate is fixed by which check fired, confidence
by whether the check is deterministic — so the function collapsed to
`table[check_type] × blast_radius`, i.e. a lookup table with extra steps.

We ship the table explicitly instead, and print the arithmetic into every finding
as `severity_rationale` so a reader can audit it line by line. An auditable table
you can defend beats a formula you cannot specify.

## The arithmetic

```
base            declared per check (below)
× blast_radius  site_wide 1.0 | template 0.8 | single_page 0.5   (banded, never a raw float)
caps            measurement_basis == static_heuristic -> at most medium
                confidence        == heuristic        -> may never reach critical
                coverage < 3 pages                    -> no blast-radius escalation
                status            == latent           -> at most low
```

Only `blast_radius` and `coverage` are genuine runtime terms. Severity consumes
**banded** values only, never raw floats — this is what keeps the ordering stable
across machines.

## Base severities, each justified by mechanism

Thresholds here are justified by *mechanism*, never by a percentile of observed
sites. A defect that happens to be near-universal is still a defect; a good
practice that happens to be rare is still good practice. Calibrating against
prevalence would flag a fixed fraction of sites by construction.

| Check | Base | Why |
|---|---|---|
| `A1_retrieval_agent_blocked` | critical | Gate 1 failure for agents that gate citation. Nothing downstream can matter. |
| `A3_noindex` | critical | Removes the page from the indexes assistants draw on. |
| `A7_site_unreadable` | critical | No automated client can read anything. Must never be reported as "no findings". |
| `A2_snippet_suppressed` | high | Page stays indexed but its text cannot be quoted — a silent, near-total loss of citability. |
| `A5_canonical_problem` | medium | Misattributes credit; rarely fully blocking. |
| `A4_redirect_chain` | low | Wasteful and occasionally lossy, seldom decisive. |
| `A6_sitemap_missing` | low | Discovery still works via links. |
| `B1_fact_absent` | high | The fact does not exist in the response at all. Directly causes wrong or missing answers. |
| `B1_fact_script_only` | medium | Present in bytes, absent from extracted text. Hard to reach, not impossible — deliberately *not* rated high. |
| `B4_empty_shell` | high | No extractable content whatsoever for a non-rendering fetcher. |
| `B5_fact_locked_in_image` | medium | Recoverable only by OCR, which retrieval agents do not perform. |
| `B6_filler_heavy` | low | Degrades summary quality without preventing extraction. |
| `C1_structured_data_invalid` | high | Worse than absent: it looks correct, is silently discarded, and nobody notices. |
| `C1_structured_data_absent` | medium | Facts may still be readable in prose. |
| `C2_markup_text_contradiction` | high | Contradictory evidence lowers confidence in everything else the site publishes. |
| `C3_entity_unanchored` | medium | Enables mistaken identity where names collide. |
| `X1_low_quotability` | medium | Extractable but not citable — assistants quote passages, not pages. |
| `X2_no_citation_anchor` | low | Reduces deep-linking; page can still be cited whole. |
| `D4_internal_contradiction` | high | Same reasoning as C2, across pages. |
| `D1_no_date_signals` | medium | Recency cannot be demonstrated. |
| `D3_content_stale` | medium | Superseded claims stay live and quotable. |
| `D5_no_corroboration_hooks` | medium | Isolated claims are fragile. |
| `D2_stale_copyright` | low | A cue, not a cause. |
| `E*` (all engagement) | low–medium | All are `static_heuristic` and therefore capped at medium regardless of base. |

## Why latent, not suppressed

An earlier design suppressed downstream findings on a blocked URL as "moot". That
is wrong for three reasons:

1. **It creates a second-audit trap.** The operator fixes robots.txt, re-audits,
   and meets a wave of findings nobody warned them about — which reads as an
   unreliable tool.
2. **robots.txt is per-user-agent.** A page disallowed to `OAI-SearchBot` may be
   wide open to `Claude-User`. Suppression assumes a single crawler.
3. **User-initiated fetches still reach the page.** A blocked page may still be
   fetched and still needs extractable facts.

So downstream findings are emitted with `status: "latent"`, a `blocked_by` object
naming *which agents* are affected, severity capped at low, and exclusion from
`summary.total_findings` (counted in `summary.latent_findings` instead). The
report surfaces them under "what you will face after fixing the blockers".
