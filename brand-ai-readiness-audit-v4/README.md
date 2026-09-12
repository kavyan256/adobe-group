# Brand AI-Readiness Audit — Agent Skill Marketplace

Point it at a website. It reports why AI assistants can't reach, read or correctly
quote the site, and why visitors who arrive don't stay, as one prioritized JSON
report of findings and suggested actions.

**Read-only and recommend-only:** GET requests only, robots.txt honoured, and
nothing on the audited site is ever changed.

## Quick start

The full audit is two passes: the scripted checks, then an agent review of the same
crawl. Work in a directory outside the marketplace (`WORK/`).

```bash
pip install -r requirements.txt

# pass 1: crawl once, run the scripted checks, keep the bundle
python3 skills/audit-orchestrator/scripts/audit.py https://example.com \
    --max-pages 12 --bundle WORK/bundle.json -o WORK/report.json

# pass 2: the agent reviews a profile of the crawl and writes claims + fixes
python3 skills/agent-review-audit/scripts/page_profile.py WORK/bundle.json WORK/report.json > WORK/profile.json
#   ... write WORK/claims.json (skills/agent-review-audit/SKILL.md) ...
python3 skills/audit-orchestrator/scripts/audit.py --replay WORK/bundle.json \
    --agent-claims WORK/claims.json -o WORK/report.json
```

Pass 1 took 10–40 s on the sites we tried (the crawl dominates: pages are fetched
at least 1 s apart); it is bounded at 280 s whatever the site does. Pass 2 adds no
network time — it replays the saved bundle. The agent's own reading of the profile
is the only unbounded step, and `SKILL.md` asks for about two minutes.

Scripted checks only, in one line:

```bash
python3 skills/audit-orchestrator/scripts/audit.py https://example.com -o report.json
```

## The skills

A page must clear three ordered gates before an assistant can cite it: the crawler
must be **let in**, must be able to **read** the page, and must be able to **pick out
the fact**. On top of that sit whether the fact is **current and consistent**, and
whether a visitor who lands can **act**. One skill per concern:

| Skill | Concern | Checks |
|---|---|---|
| `audit-orchestrator` *(entrypoint)* | Crawl once, run the others, compose the report | — |
| `crawl-access-audit` | Gate 1: can retrieval agents reach and quote the page? | A1–A8 (robots per agent, noindex, snippet suppression, canonicals, sitemaps, robots tokens), A9 broken and key pages, A10 meta refresh, A11 soft 404 |
| `fact-extractability-audit` | Gates 2–3: does the fact survive text extraction, and is it unambiguous? | B1, B4, B6, C1–C3, C5–C7, X1 |
| `freshness-corroboration-audit` | Is it current and self-consistent? | D1–D4 |
| `engagement-audit` | Can a visitor who arrives act? | E1–E7, E9–E12 |
| `agent-review-audit` | What did the scripted checks miss? An agent reviews the crawl and writes claims and site-specific fixes; a verifier admits only those whose evidence is on the crawled pages | R (`R_agent_review`) |

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
   └──────────────► merge · mark latent · severity · rank ──► report.json
```

Each sub-skill reads the bundle as data and imports nothing from the others, so
every skill folder also runs on its own against a bundle produced by
`audit-orchestrator`: `python3 skills/<skill>/scripts/check_*.py bundle.json`
(make a bundle with `audit.py <url> --bundle bundle.json`). Because JSON-LD and
text are parsed once, in the crawl layer, two skills cannot disagree about what a
page says.

**Beyond the fixed checks.** A list of checks misses whatever it does not list, so
`agent-review-audit` adds a second pass. The agent running the audit reads a compact
profile of the same bundle (`page_profile.py`), walks a mechanism checklist, and writes
each problem it sees as a claim with evidence assertions. The entrypoint then re-runs
on the saved bundle with `--agent-claims`: `verify_claims.py` checks every assertion
against the crawled pages and rejects any claim that does not hold, needs a page that
was not crawled, rests only on absences or identity fields (`status eq 200`), uses
evidence true of every page, or carries markup or off-site links; the orchestrator
then drops claims that repeat a scripted finding on the same pages. What survives is
merged as `source: agent_review`, heuristic, **capped at low severity**, with the
reviewer's reasoning labelled "not verified" and the checked assertions labelled
separately. The same file may carry up to five **fixes**: site-specific steps for a
scripted finding, each grounded on a quote that must be found on the affected page.

```
audit.py <url> --bundle b.json ──► page_profile.py ──► agent writes claims.json
audit.py --replay b.json --agent-claims claims.json ──► verify_claims.py ──► merged report
```

## The report

The required `site`, `audited_at`, `summary` and `findings[]` (`id`, `title`,
`severity`, `evidence`, `suggested_action`), plus what a non-expert needs to act:

- **`summary.{critical,high,medium,low}`** count every finding and add up to
  `total_findings`; **`summary.active_by_severity`** counts the ones to act on today
- **`hurts`** on every finding — `ai_discoverability`, `user_retention` or `both` —
  counted in `summary.by_hurts`
- **`suggested_action.how[]`** (concrete steps), **`verify`** (how to confirm the fix),
  and where an agent review supplied one, **`site_specific[]`** grounded on a quote
  from the page
- **`findings[]` ordered** by severity band, then `severity × confidence ÷ effort`, with
  ids in that order; **`prioritized_actions[]`** is the top of the same list
- **`proactive_recommendations[]`**, only ones the site doesn't already satisfy; the
  rest appear in `already_in_place[]` with the evidence
- **`severity_rationale`**, the arithmetic behind each severity
- **`status`**: `latent` (real, but hidden behind an access block) or `confirm_intent`
  (looks deliberate, so asked rather than asserted) — both capped at low
- **`checks_skipped[]`** and **`limits[]`**, each written "Not assessed: … Reason: …
  How to check it yourself: …", so "found nothing" is never confused with "could not look"
- **`source`** on every finding (`scripted` or `agent_review`), and an **`agent_review`**
  block recording claims and fixes submitted, verified, merged and rejected, each
  rejection with its reason

Field by field: `skills/audit-orchestrator/references/report-schema.md`.

## Design decisions

- **No headless browser.** The major AI retrieval agents don't execute JavaScript, so
  each expected fact is graded by the form it takes in the raw response (T0 prose to T3
  absent), and hydration payloads are parsed before a page is called invisible. A
  browser would also break the 50 MB budget and determinism.
  See `fact-extractability-audit/references/extraction-tiers.md`.
- **Sub-skills carry their own scripts.** The original design said code-free
  sub-skills; each now ships the checks it owns, so a check is reviewable next to the
  SKILL.md that explains it. They read a bundle produced by the orchestrator and
  import nothing from each other.
- **Blocking training is not blocking citation.** `GPTBot` or `Google-Extended` blocks
  don't affect whether assistants cite you; only retrieval agents (`OAI-SearchBot`,
  `Claude-User`, `PerplexityBot`, …) produce a finding. robots.txt is parsed to
  RFC 9309. See `crawl-access-audit/references/bot-taxonomy.md`.
- **Deliberate is not defective.** noindex confined to legal pages, or AI agents
  blocked by name, is reported as a question; noindex on the pricing page stays
  critical. See `crawl-access-audit/references/deliberate-vs-defect.md`.
- **Severity is a published table**, adjusted only by blast radius and capped for
  heuristic, latent, deliberate-looking and agent-review findings.
  See `audit-orchestrator/references/severity-rationale.md`.
- **The agent proposes, a script decides.** Letting a language model write findings
  directly would catch more and invent more. Agent claims enter the report only after
  a deterministic verifier has checked their evidence against the crawl, and even then
  at most `low`: recall rises without admitting findings nobody can check.
  See `agent-review-audit/references/claim-format.md`.

## What a site crawl cannot see

- **Personalization** happens inside the assistant, from the user's own context; any
  site-side score would be invented. The site-side lever — self-contained, quotable
  facts — is what the extraction and quotability (X1) checks measure.
- **Email summarisation** isn't observable from a website. Its transferable mechanism,
  substance carried in non-text or buried in filler, is checked on-page (E4, B6).
- **Cross-web corroboration (D6)** needs a search backend and is always listed in
  `checks_skipped[]`. The on-site half — an Organization node with `sameAs` links that
  third parties can corroborate against — is checked by C3 and, where absent, raised by
  the "citable facts page" proactive recommendation.
- **Colour contrast, Core Web Vitals, behaviour metrics, copy quality and anything
  behind a login** need a browser, field data or a person; each is listed in
  `checks_skipped[]` and `limits[]` with how to check it yourself.

## Guarantees

- Truthful User-Agent (`AIReadinessAudit/1.0`); never impersonates a crawler.
- robots.txt honoured for that UA, including sitemaps and the `llms.txt` probe;
  `Crawl-delay` respected up to 2 s, beyond which the page budget shrinks instead.
- Every request — robots.txt, sitemaps, `llms.txt`, pages — is at least 1 s after the
  previous one. The crawl stops at the first HTTP 429, and at a 503 on the start URL
  or a second consecutive 503, so a site shedding load is never pushed harder.
- The sitemap walk has its own 30 s budget inside the 200 s crawl deadline; the whole
  run is bounded at 280 s, inside the 5-minute limit.
- Analysis is deterministic for a fixed bundle (`--replay`), and for a fixed bundle plus
  claims file. Which claims an agent writes can vary between runs; every claim that
  reaches the report has had its evidence checked against the crawl.
- Python 3.10+ with `httpx` and `beautifulsoup4`; no model weights, no browser,
  well under 1 MB.

## Tests

`python3 tests/run_tests.py` — no network. Covers RFC 9309 conformance, extraction
tiers, JSON-LD normalisation, severity-table integrity, crawler safety edges against a
fake HTTP client, the reviewers' adversarial claim files, and end-to-end replays of
fixture sites. `tools/validate_submission.py` (outside the marketplace) checks the
package: manifest, SKILL.md compliance, report conformance, determinism, size.
