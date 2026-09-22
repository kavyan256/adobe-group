# AI agent taxonomy

Conflating "blocks training" with "blocks citation" produces a critical false
positive against publishers who deliberately allow retrieval while refusing training.

## Retrieval-gating — blocking these removes you from answers

| Agent | Operator | Role |
|---|---|---|
| `OAI-SearchBot` | OpenAI | Builds the ChatGPT Search index |
| `ChatGPT-User` | OpenAI | Live fetch triggered by a user's question |
| `Claude-SearchBot` | Anthropic | Search index |
| `Claude-User` | Anthropic | Live user-initiated fetch |
| `PerplexityBot` | Perplexity | Index |
| `Perplexity-User` | Perplexity | Live user-initiated fetch |
| `Applebot` | Apple | Siri / Spotlight retrieval |
| `Googlebot` | Google | Search index — **also serves AI Overviews and AI Mode** |
| `Bingbot` | Microsoft | Search index — also serves Copilot |

## Training-only — blocking these does NOT affect citation

| Agent | Operator | What it actually gates |
|---|---|---|
| `GPTBot` | OpenAI | Model training corpus |
| `ClaudeBot` | Anthropic | Model training corpus |
| `CCBot` | Common Crawl | A public corpus, not live retrieval |
| `Google-Extended` | Google | Gemini training. **Does not affect Google Search or AI Overviews.** |
| `Applebot-Extended` | Apple | Model training (note: plain `Applebot` is retrieval) |
| `Bytespider` | ByteDance | Training |

## Ambiguous

| Agent | Note |
|---|---|
| `meta-externalagent` | Documentation does not cleanly separate training from retrieval. Reported as an observation with uncertainty flagged. |

## Per-bot page directives

`X-Robots-Tag` and `<meta name="…">` are read per bot, not as one string:

- `<meta name="robots">` and an unscoped `X-Robots-Tag` bind every crawler.
- `<meta name="googlebot">`, `<meta name="bingbot">` and a scoped header
  (`X-Robots-Tag: bingbot: noindex`) bind that crawler only. Both are read: Bing's
  index feeds ChatGPT search and Copilot, so a Bing-only `noindex` still removes
  the page from assistants' answers.
- A directive scoped to a crawler that does not gate assistants
  (`googlebot-news: noindex`, or a training-only token) is recorded in the
  finding's `detail.scoped_to_other_bots` and never fires `A3`.
- `none` counts as `noindex` only as a whole value (`robots: none`, `none, nofollow`);
  the `none` inside `max-image-preview:none` is a different setting.
- `noarchive` is not snippet suppression: it controls cached copies. `A2` fires on
  `nosnippet`, `max-snippet:0`, or `data-nosnippet` around the primary content.

## How this is used

- A blocked **retrieval** agent produces `A1_retrieval_agent_blocked` at
  **critical** when the block is inherited from the wildcard group or catches
  `Googlebot`, `Bingbot` or `OAI-SearchBot`; blocking other retrieval agents by name
  while one stays fully allowed is reported as `confirm_intent` (see
  `deliberate-vs-defect.md`).
- A blocked **training** agent produces **no finding**. It is recorded in
  `site_profile.ai_policy` as a neutral policy observation, with the tradeoff
  stated, so an operator can confirm the choice was deliberate.
- Where both appear, the A1 evidence string explicitly says which of the blocked
  agents are training-only and therefore *not* part of the defect.

## robots.txt parsing notes (RFC 9309)

Python's stdlib `urllib.robotparser` is **not** conformant — it mishandles
wildcard expansion and `Allow`/`Disallow` precedence. `robots.py` implements:

- case-insensitive user-agent product-token matching
- all matching groups merged; the `*` group applies **only** when no specific
  group matches, never additively
- `Allow`/`Disallow` resolved by **longest match** after `*`/`$` expansion, ties
  to `Allow`
- empty `Disallow:` means allow-everything
- `4xx` on robots.txt means allow-all; persistent `5xx`/unreachable is treated as
  disallow-all (conservative)
- product tokens match exactly, so `User-agent: Claude` binds no crawler. A group
  naming a strict prefix of a known token is reported as `A8`; a full token this
  table does not list (such as `Google-CloudVertexBot`) is a real crawler and is left
  alone

The conformance cases are exercised in `tests/`.
