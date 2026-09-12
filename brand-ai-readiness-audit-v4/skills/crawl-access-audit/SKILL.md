---
name: crawl-access-audit
description: >-
  Determine whether AI retrieval agents are permitted to reach and quote a site's
  pages. Parses robots.txt per user-agent to RFC 9309 semantics, separates
  retrieval-blocking agents from training-only ones, reads per-bot meta robots and
  X-Robots-Tag directives, and detects noindex, snippet suppression (nosnippet /
  max-snippet:0 / data-nosnippet on content), canonical faults, redirect chains,
  broken and soft-404 pages, meta-refresh redirects, missing sitemaps and
  robots.txt rules that bind no crawler. Runs on its own against a bundle from
  audit-orchestrator to answer "can AI assistants reach my site at all?", or as
  the first gate of a full AI-readiness audit.
license: Apache-2.0
allowed-tools: Bash Read
compatibility: Python 3.10+, httpx, beautifulsoup4
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
   unreadable site must never come back with zero findings. The evidence says which
   of three things happened: robots.txt could not be fetched (treated as
   disallow-all), robots.txt disallows our user-agent, or the server refused us.
2. From the bundle's per-agent robots report, emit `A1_retrieval_agent_blocked` only
   for **retrieval** agents. Blocked training agents (`GPTBot`, `ClaudeBot`,
   `Google-Extended`, …) are named in the evidence as not a defect, and recorded as
   policy in `site_profile.ai_policy`.
3. Per page, read `X-Robots-Tag` and every `<meta name="robots|<bot>">`, scoped per
   bot. Only directives aimed at an unscoped tag, `googlebot`, `bingbot` or a
   retrieval agent count; `googlebot-news: noindex` is recorded in `detail`, not
   fired. `noindex`, or `none` as a whole value → `A3_noindex`. `nosnippet`,
   `max-snippet:0`, or `data-nosnippet` wrapping the h1, `<main>`/`<article>` or the
   first substantial paragraph → `A2_snippet_suppressed`. `noarchive` controls cached
   copies, not quoting, and is ignored.
4. Canonicals: off-domain (`www.` and bare host are the same site) or pointing a
   content page at the homepage → `A5_canonical_problem`; none at all on a product,
   pricing or blog page → `A5_canonical_missing` (low). Redirect chains over two
   hops → `A4`; no discoverable sitemap → `A6`.
5. Flag robots.txt groups naming a truncated token such as `User-agent: Claude`,
   which RFC 9309's exact matching binds to no crawler (`A8`).
6. Pages the crawl reached that answered 404/410/5xx → `A9_broken_pages`, or
   `A9_key_page_broken` when one is a pricing, product or contact page (401/403/429
   and transport errors are excluded; those are refusals, covered by A7). A
   `<meta http-equiv="refresh">` to another URL → `A10_meta_refresh`. HTTP 200 whose
   title or h1 reads as a not-found page → `A11_soft_404` (heuristic).
7. Where the configuration reads as deliberate — noindex confined to legal, utility
   or search templates (`A3_noindex_utility`), or retrieval agents blocked by name
   while another stays fully allowed — set `status: "confirm_intent"` and record why
   in `intent_signals`.

```bash
python3 scripts/check_access.py bundle.json
```

## Output

A JSON array of findings: `check_id`, `title`, `evidence`, `affected_urls`,
`blast_radius`, `confidence`, `suggested_action`, and where relevant `status`,
`intent_signals` and `detail`. The orchestrator assigns severity.

## Interpreting results

- `A1` at `active`/critical means a wildcard rule, or a block on Googlebot, Bingbot or
  OAI-SearchBot. If the owner names those agents on purpose, downgrade to
  `confirm_intent` yourself; the rules are in `references/deliberate-vs-defect.md`.
- `A3_noindex` on a page that is plainly a login, search or thank-you screen the role
  detector missed is `A3_noindex_utility` in all but name: mark it `confirm_intent`.
- `A11_soft_404` matches wording only. An article *about* 404 pages, or a product
  named "404", is a false positive; drop it after a glance at the page.
- `A9` on a URL the sitemap lists but nothing links is real but cheap to fix; on a
  URL only the crawl invented (a parsed `href` fragment) it is not a finding at all.
- `A2` from `data-nosnippet` is decided by where the attribute sits; if the wrapper is
  a consent dialog that happens to contain the h1, downgrade to low.

## References

- `references/bot-taxonomy.md` — retrieval vs training agents, per-bot directive
  scoping, and the RFC 9309 rules
- `references/deliberate-vs-defect.md` — when a setting is reported as a question
