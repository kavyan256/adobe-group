---
name: crawl-access-audit
description: >-
  Determine whether AI retrieval agents are permitted to reach and quote a site's
  pages. Parses robots.txt per user-agent to RFC 9309 semantics, separates
  retrieval-blocking agents from training-only ones, and detects noindex, snippet
  suppression (nosnippet / max-snippet:0 / data-nosnippet), canonical faults,
  redirect chains, missing sitemaps and robots.txt rules that bind no crawler. Use
  standalone to answer "can AI assistants reach my site at all?", or as the first
  gate of a full AI-readiness audit.
license: Apache-2.0
allowed-tools: Bash, Read
---

# Crawl & Access Audit (Gate 1)

## When to use

When the question is "can AI assistants reach my site at all?", or as the first gate
of `audit-orchestrator`. If a retrieval agent can't fetch a page, nothing else about
that page matters, and the fix is usually a few lines of robots.txt.

## Inputs

A site bundle from `audit-orchestrator/scripts/bundle.py` (or `audit.py --bundle`),
as a path argument or on stdin.

## Procedure

1. If no page returned readable HTML, emit `A7_site_unreadable` and stop. An
   unreadable site must never come back with zero findings.
2. From the bundle's per-agent robots report, emit `A1_retrieval_agent_blocked` only
   for **retrieval** agents. Blocked training agents (`GPTBot`, `ClaudeBot`,
   `Google-Extended`, …) are named in the evidence as not a defect, and recorded as
   policy in `site_profile.ai_policy`.
3. Per page, read meta robots and `X-Robots-Tag`. `noindex`, or `none` (its
   shorthand) → `A3_noindex`.
   `nosnippet`, `noarchive`, `max-snippet:0` or `data-nosnippet` →
   `A2_snippet_suppressed`: the page stays indexed, but its text can't be quoted.
4. Flag missing or off-domain canonicals on duplicate-prone pages, and content pages
   whose canonical is the homepage (`A5`, heuristic),
   redirect chains over two hops (`A4`), and no discoverable sitemap (`A6`).
5. Flag robots.txt groups naming a truncated token such as `User-agent: Claude`,
   which RFC 9309's exact matching binds to no crawler (`A8`).
6. Where the configuration reads as deliberate — noindex confined to legal, utility
   or search templates (`A3_noindex_utility`), or retrieval agents blocked by name
   with path-scoped rules — set `status: "confirm_intent"` and record why in
   `intent_signals`.

```bash
python3 scripts/check_access.py bundle.json
```

## Output

A JSON array of findings: `check_id`, `title`, `evidence`, `affected_urls`,
`blast_radius`, `confidence`, `suggested_action`, and where relevant `status`,
`intent_signals` and `detail`. The orchestrator assigns severity.

## References

- `references/bot-taxonomy.md` — retrieval vs training agents, and the RFC 9309 rules
- `references/deliberate-vs-defect.md` — when a setting is reported as a question
