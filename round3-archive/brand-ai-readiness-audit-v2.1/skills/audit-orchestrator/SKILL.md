---
name: audit-orchestrator
description: >-
  Audit any website for AI-discoverability and on-site-engagement problems, and
  emit a single prioritized JSON report. Detects retrieval-agent blocks, facts
  that do not survive text extraction, missing or contradictory structured data,
  entity ambiguity, staleness, and on-site engagement risk factors. Use when
  diagnosing why a brand is missing or misrepresented in AI assistants, or why
  visitors who arrive from an AI answer do not stay. This is the marketplace
  entrypoint: it performs the single crawl, invokes the four specialist audit
  skills, and composes their findings into one report.
license: Apache-2.0
allowed-tools: Bash, Read, Write
---

# Audit Orchestrator (marketplace entrypoint)

## When to use

When someone asks why ChatGPT, Perplexity or Claude doesn't mention their site or
gets its facts wrong, why visitors arriving from AI answers don't stay, or simply
asks for an AI-readiness audit. Never use it to change a site: everything here is
read-only and recommend-only.

## Inputs

| Input | Required | Notes |
|---|---|---|
| `url` | yes | Site or page URL; `https://` is assumed. |
| `--max-pages N` | no | Crawl budget, default 20. |
| `--bundle PATH` | no | Also save the fetched site bundle. |
| `--replay PATH` | no | Re-run the analysis over a saved bundle, with no network. |
| `--agent-claims PATH` | no | Claims from `agent-review-audit`; verified against the bundle and merged if they hold. |
| `-o PATH` | no | Write the report here instead of stdout. |

## Procedure

1. **Fetch once.** `scripts/bundle.py` reads robots.txt (RFC 9309, `scripts/robots.py`),
   walks the sitemap, and fetches up to `max-pages` pages in a deterministic order,
   with a truthful User-Agent, no JavaScript, and a 280 s budget. JSON-LD and page
   text are normalised here, once (`references/jsonld-normalisation.md`).
2. **Run each specialist skill** as a separate process on the bundle:
   `crawl-access-audit`, `fact-extractability-audit`, `freshness-corroboration-audit`,
   `engagement-audit`. A skill that fails or times out is recorded in
   `checks_skipped[]`, never silently dropped.
3. **Look for what the scripts missed.** Follow `agent-review-audit/SKILL.md`: review
   the crawl's profile, write claims, and re-run with `--replay` and `--agent-claims`.
   The verifier merges only claims whose evidence holds and that do not repeat a
   scripted finding; the outcome is recorded in `agent_review`. If no review runs,
   the report says so in `checks_skipped[]`.
4. **Mark latent findings.** A finding whose pages are refused to *every* retrieval
   agent, or carry noindex, gets `status: "latent"` and a `blocked_by` naming the
   agents. It is kept, so fixing the blocker never reveals a wave of findings nobody
   mentioned. Engagement findings are never latent.
5. **Derive severity** from the table in `scripts/model.py`
   (`references/severity-rationale.md`), and tag what each finding `hurts`.
6. **Prioritize** by severity × confidence ÷ effort, demoting latent and
   confirm-intent findings, and add the proactive recommendations the site does not
   already satisfy.
7. **Emit one report** matching `../../schema/audit-report.schema.json`.

```bash
python3 scripts/audit.py https://example.com --bundle work/bundle.json -o work/report.json
python3 scripts/audit.py --replay work/bundle.json --agent-claims work/claims.json -o report.json
```

## Output

One JSON report: the required `site`, `audited_at`, `summary` and `findings[]`
(`id`, `title`, `severity`, `evidence`, `suggested_action`), plus `hurts`, `status`,
`severity_rationale`, `source` (`scripted` or `agent_review`), `prioritized_actions[]`,
`proactive_recommendations[]`, `already_in_place[]`, `coverage`, `checks_skipped[]`,
`agent_review` and `limits[]`.

## References

- `references/report-schema.md` — the report, field by field
- `references/severity-rationale.md` — every base severity, and why
- `references/jsonld-normalisation.md` — the one parse every skill reads
