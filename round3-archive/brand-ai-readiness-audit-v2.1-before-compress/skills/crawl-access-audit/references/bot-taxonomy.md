# AI agent taxonomy

The single most important table in this marketplace. Conflating "blocks training"
with "blocks citation" produces a high-severity false positive against publishers
who deliberately allow retrieval while refusing training — exactly the
sophisticated operators most likely to be spot-checked.

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

## How this is used

- A blocked **retrieval** agent produces `A1_retrieval_agent_blocked` at
  **critical**.
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

The conformance cases are exercised in `tests/`.
