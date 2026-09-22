# Brand AI-Readiness Audit — Agent Skill Marketplace

Point it at a website. It reports why AI assistants can't reach, read or correctly
quote the site, and why visitors who arrive don't stay, as one prioritized JSON
report of findings and suggested actions.

**Read-only and recommend-only:** GET requests only, robots.txt honoured, and
nothing on the audited site is ever changed.

```bash
pip install -r requirements.txt
python3 skills/audit-orchestrator/scripts/audit.py https://example.com -o report.json
```

## The skills

A page must clear three ordered gates before an assistant can cite it: the crawler
must be **let in**, must be able to **read** the page, and must be able to **pick out
the fact**. On top of that sit whether the fact is **current and corroborated**, and
whether a visitor who lands can **act**. One skill per concern:

| Skill | Concern | Checks |
|---|---|---|
| `audit-orchestrator` *(entrypoint)* | Crawl once, run the others, compose the report | — |
| `crawl-access-audit` | Gate 1: can retrieval agents reach and quote the page? | A1–A8 |
| `fact-extractability-audit` | Gates 2–3: does the fact survive text extraction, and is it unambiguous? | B1, B4, B6, C1–C3, C5–C6, X1–X2 |
| `freshness-corroboration-audit` | Is it current, self-consistent and corroborable? | D1–D5 |
| `engagement-audit` | Can a visitor who arrives act? | E1–E7, E9–E10 |
| `agent-review-audit` | What did the scripted checks miss? An agent reviews the crawl and writes claims; a verifier admits only those whose evidence holds | R (`R_agent_review`) |

## How the entrypoint composes them

```
audit.py <url>
   │
   ├── bundle.py ──► site bundle (one crawl, no JS, truthful UA, robots honoured,
   │                  JSON-LD and page text normalised once)
   │        ┌─────────────┬─────────────┬──────────────┐
   │        ▼             ▼             ▼              ▼
   │   crawl-access  extractability  freshness   engagement      (separate processes)
   │        └─────────────┴──────┬──────┴──────────────┘
   │                             ▼
   └──────────────► merge · mark latent · severity · prioritize ──► report.json
```

Each sub-skill reads the bundle as data and imports nothing from the others, so
every skill folder also runs on its own:
`python3 skills/<skill>/scripts/check_*.py bundle.json` (make a bundle with
`audit.py <url> --bundle bundle.json`). Because JSON-LD and text are parsed once, in
the crawl layer, two skills cannot disagree about what a page says.

**Beyond the fixed checks.** A list of checks misses whatever it does not list, so
`agent-review-audit` adds a second pass. The agent running the audit reads a compact
profile of the same bundle (`page_profile.py`), walks a mechanism checklist, and writes
each problem it sees as a claim with evidence assertions. The entrypoint then re-runs
on the saved bundle with `--agent-claims`: `verify_claims.py` checks every assertion
against the crawled pages, rejects any claim that does not hold, needs a page that was
not crawled, or only asserts absences, and drops claims that repeat a scripted finding.
What survives is merged as `source: agent_review`, heuristic and capped at medium.

```
audit.py <url> --bundle b.json ──► page_profile.py ──► agent writes claims.json
audit.py --replay b.json --agent-claims claims.json ──► verify_claims.py ──► merged report
```

## The report

The required `site`, `audited_at`, `summary` and `findings[]` (`id`, `title`,
`severity`, `evidence`, `suggested_action`), plus what a non-expert needs to act:

- **`hurts`** on every finding — `ai_discoverability`, `user_retention` or `both` —
  counted in `summary.by_hurts`
- **`suggested_action.how[]`** (concrete steps) and **`verify`** (how to confirm the fix)
- **`prioritized_actions[]`**, ranked by severity × confidence ÷ effort
- **`proactive_recommendations[]`**, only ones the site doesn't already satisfy; the
  rest appear in `already_in_place[]` with the evidence
- **`severity_rationale`**, the arithmetic behind each severity
- **`status`**: `latent` (real, but hidden behind an access block) or `confirm_intent`
  (looks deliberate, so asked rather than asserted) — both capped at low
- **`checks_skipped[]`** and **`limits[]`**, so "found nothing" is never confused with
  "could not look"
- **`source`** on every finding (`scripted` or `agent_review`), and an **`agent_review`**
  block recording claims submitted, verified, merged and rejected, each rejection with
  its reason

Field by field: `skills/audit-orchestrator/references/report-schema.md`.

## Design decisions

- **No headless browser.** The major AI retrieval agents don't execute JavaScript, so
  each expected fact is graded by the form it takes in the raw response (T0 prose to T3
  absent), and hydration payloads are parsed before a page is called invisible. A
  browser would also break the 50 MB budget and determinism.
  See `fact-extractability-audit/references/extraction-tiers.md`.
- **Blocking training is not blocking citation.** `GPTBot` or `Google-Extended` blocks
  don't affect whether assistants cite you; only retrieval agents (`OAI-SearchBot`,
  `Claude-User`, `PerplexityBot`, …) produce a finding. robots.txt is parsed to
  RFC 9309. See `crawl-access-audit/references/bot-taxonomy.md`.
- **Deliberate is not defective.** noindex confined to legal pages, or AI agents
  blocked by name, is reported as a question; noindex on the pricing page stays
  critical. See `crawl-access-audit/references/deliberate-vs-defect.md`.
- **Severity is a published table**, adjusted only by blast radius and capped for
  heuristic, latent and deliberate-looking findings.
  See `audit-orchestrator/references/severity-rationale.md`.
- **The agent proposes, a script decides.** Letting a language model write findings
  directly would catch more and invent more. Agent claims enter the report only after
  a deterministic verifier confirms their evidence, so recall rises without admitting
  findings nobody can check. See `agent-review-audit/references/claim-format.md`.

## What a site crawl cannot see

- **Personalization** happens inside the assistant, from the user's own context; any
  site-side score would be invented. The site-side lever — self-contained, quotable
  facts — is what the extraction and quotability (X1) checks measure.
- **Email summarisation** isn't observable from a website. Its transferable mechanism,
  substance carried in non-text or buried in filler, is checked on-page (E4, B6).
- **Cross-web corroboration (D6)** needs a search backend and is always listed in
  `checks_skipped[]`. On-site corroboration hooks are checked (C3 `sameAs`, D5 press).
- **Colour contrast and Core Web Vitals** need a browser or field data; both are
  listed in `checks_skipped[]` with the tool that can measure them.

## Guarantees

- Truthful User-Agent (`AIReadinessAudit/1.0`); never impersonates a crawler.
- robots.txt honoured for that UA, including sitemaps; `Crawl-delay` respected up to
  2 s, beyond which the page budget shrinks instead.
- Pages are requested at least 1 s apart, and the crawl stops at the first HTTP 429 or
  503, so a rate-limited site is never pushed harder.
- Whole run bounded at 280 s, inside the 5-minute limit.
- Analysis is deterministic for a fixed bundle (`--replay`), and for a fixed bundle plus
  claims file. Which claims an agent writes can vary between runs; every claim that
  reaches the report has been verified against the crawl.
- Python 3.10+ with `httpx` and `beautifulsoup4`; no model weights, no browser,
  well under 1 MB.

## Tests

`python3 tests/run_tests.py` — no network. Covers RFC 9309 conformance, extraction
tiers, JSON-LD normalisation, severity-table integrity, and end-to-end replays of
fixture sites.
