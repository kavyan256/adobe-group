---
name: crawl-access-audit
description: >-
  Determine whether AI retrieval agents are permitted to reach and quote a site's
  pages. Parses robots.txt per user-agent to RFC 9309 semantics, separates
  retrieval-blocking agents from training-only ones, and detects noindex, snippet
  suppression (nosnippet / max-snippet:0 / data-nosnippet), canonical faults,
  redirect chains and missing sitemaps. Use standalone to answer "can AI
  assistants reach my site at all?", or as the first gate of a full AI-readiness
  audit.
license: Apache-2.0
allowed-tools: Bash, Read
---

# Crawl & Access Audit (Gate 1)

## When to use

Standalone, when the question is narrow: *"Are AI assistants allowed to fetch my
pages?"* This is worth running alone because it is the cheapest, highest-leverage
check in the whole space — if the answer is no, nothing else about the site
matters, and the fix is usually a three-line robots.txt edit.

Also runs as the first gate of `audit-orchestrator`.

## The reasoning this skill encodes

A page must clear three ordered gates to be citable: the crawler must be **let
in**, must be able to **read** the page, and must be able to **pick out the
fact**. This skill owns the first. A failure here makes every later gate
unobservable, which is why access findings carry the highest base severities.

### The distinction that matters most: retrieval vs. training

The single most common mistake in this problem space — and the one that produces
the worst false positive — is treating every "AI bot" in robots.txt as equivalent.
They are not:

| Class | Agents | What blocking them does |
|---|---|---|
| **Retrieval** | `OAI-SearchBot`, `ChatGPT-User`, `Claude-SearchBot`, `Claude-User`, `PerplexityBot`, `Perplexity-User`, `Applebot`, `Googlebot`, `Bingbot` | **Removes you from answers.** These fetch or index pages in order to answer a user. |
| **Training** | `GPTBot`, `ClaudeBot`, `CCBot`, `Google-Extended`, `Applebot-Extended`, `Bytespider` | **Nothing, for citation.** These gather corpora for model training. Blocking them is a licensing posture. |

Blocking `Google-Extended` does not affect Google Search or AI Overviews, which
are served from the Googlebot index. `CCBot` is Common Crawl — a corpus, not live
retrieval. A publisher who blocks training while allowing retrieval has made a
coherent, deliberate choice, and **reporting that as a discoverability defect is
a false positive.**

This skill therefore reports training-agent blocks as neutral policy in
`site_profile.ai_policy`, with no severity, and fires a finding **only** when a
retrieval agent is blocked.

### Why we parse robots.txt ourselves

Python's `urllib.robotparser` is not RFC 9309-conformant: it mishandles wildcard
expansion and `Allow`/`Disallow` precedence. A Gate-1 blocking finding is only as
trustworthy as its parser, so `audit-orchestrator/scripts/robots.py` implements
the specified semantics — group merging, `*` never applying additively when a
specific group matches, longest-match precedence with ties going to `Allow`,
`4xx` meaning allow-all and persistent `5xx` meaning disallow-all.

### Snippet suppression — the non-obvious one

`nosnippet`, `data-nosnippet`, `max-snippet:0` and `noarchive` suppress a page's
*text* from AI answers **while leaving the page fully indexed**. A page can pass
every other check in this marketplace and still be structurally unquotable.
Header-observable, deterministic, and almost always unintentional.

## Inputs

A site bundle produced by `audit-orchestrator/scripts/bundle.py`, as a file path
argument or on stdin.

## Procedure

1. If no page returned readable HTML, emit `A7_site_unreadable` (critical) and
   stop. **A blocked site must never yield zero findings** — that would hand an
   unreadable site a clean bill of health, the most damaging possible output.
2. Read the per-agent robots report from the bundle. Emit `A1` only for
   retrieval-class agents that are fully or partially blocked; name any blocked
   training agents in the evidence as explicitly *not* a defect.
3. Per page, inspect meta robots and `X-Robots-Tag` for `noindex` (`A3`) and for
   snippet suppressors (`A2`).
4. Check canonical links (`A5`) and redirect chains longer than two hops (`A4`).
5. Check that a parsable sitemap was discovered (`A6`).

```bash
python3 scripts/check_access.py bundle.json
```

## Output

A JSON array of finding objects: `check_id`, `title`, `evidence`,
`affected_urls`, `blast_radius`, `confidence`, `suggested_action`. Severity is
assigned by the orchestrator from the shared table, so this skill's output stays
composable.

Two findings carry `status: "confirm_intent"` when the configuration reads as
deliberate rather than broken -- `A3_noindex_utility` (noindex confined to
legal/utility/search templates) and `A1_retrieval_agent_blocked` where every
blocking rule names its agent explicitly. Those are reported as a question to
confirm, capped at `low`, with the reasoning in `intent_signals`. The rules are
published in `references/deliberate-vs-defect.md`.

`A8_robots_token_unrecognised` reports a `User-agent:` group naming a token no
crawler answers to. RFC 9309 compares full product tokens exactly, so a group
written `User-agent: Claude` binds nothing -- it looks active in the file and
does nothing.

## Known false-positive risks, and how they are contained

- **UA-differential testing is deliberately limited.** Comparing a Chrome
  user-agent against a bot user-agent produces differences on nearly every real
  site — CDN bot management, rate limiting, geo variance, `Vary` negotiation, A/B
  tests. We compare status *class* only, never body content, and treat 429/503 as
  inconclusive rather than as a finding.
- **We never spoof an agent's user-agent** to test its access. Beyond being
  impersonation, claiming to be `GPTBot` would bind this auditor to `GPTBot`'s
  robots rules. Bot policy is determined by *parsing*, which costs zero requests.
- **Canonical checks are marked `heuristic`**, since legitimate cross-domain
  canonicals exist.

## References

- `references/bot-taxonomy.md` — the full agent table with sources
