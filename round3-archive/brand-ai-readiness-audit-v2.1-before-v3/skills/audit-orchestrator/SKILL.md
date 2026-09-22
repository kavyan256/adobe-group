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
3. **Mark latent findings.** A finding whose pages sit behind a retrieval-agent block
   or noindex gets `status: "latent"` and a `blocked_by` naming the agents. It is kept,
   so fixing the blocker never reveals a wave of findings nobody mentioned.
4. **Derive severity** from the table in `scripts/model.py`
   (`references/severity-rationale.md`), and tag what each finding `hurts`.
5. **Prioritize** by severity × confidence ÷ effort, demoting latent and
   confirm-intent findings, and add the proactive recommendations the site does not
   already satisfy.
6. **Emit one report** matching `../../schema/audit-report.schema.json`.

```bash
python3 scripts/audit.py https://example.com -o report.json
python3 scripts/audit.py --replay bundle.json -o report.json   # deterministic re-run
```

## Output

One JSON report: the required `site`, `audited_at`, `summary` and `findings[]`
(`id`, `title`, `severity`, `evidence`, `suggested_action`), plus `hurts`, `status`,
`severity_rationale`, `prioritized_actions[]`, `proactive_recommendations[]`,
`already_in_place[]`, `coverage`, `checks_skipped[]` and `limits[]`.

## References

- `references/report-schema.md` — the report, field by field
- `references/severity-rationale.md` — every base severity, and why
- `references/jsonld-normalisation.md` — the one parse every skill reads
