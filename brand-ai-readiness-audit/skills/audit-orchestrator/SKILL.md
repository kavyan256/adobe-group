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

Use this skill when someone asks any of:

- "Why doesn't ChatGPT / Perplexity / Claude mention my site?"
- "Why does an AI assistant say the wrong thing about my product or pricing?"
- "People find us through AI answers but don't stick around — why?"
- "Audit my site for AI readiness."

Do **not** use this skill to change a website. Everything here is read-only and
recommend-only; it never modifies the site under audit.

## Inputs

| Input | Required | Notes |
|---|---|---|
| `url` | yes | Site or page URL. Scheme optional; `https://` is assumed. |
| `--max-pages N` | no | Crawl budget, default 20. |
| `--bundle PATH` | no | Save the fetched site bundle for later replay. |
| `--replay PATH` | no | Re-run the whole analysis over a saved bundle, no network. |
| `-o PATH` | no | Write the report here instead of stdout. |

## Procedure

1. **Fetch once.** Run `scripts/bundle.py` to build a *site bundle*: robots.txt
   parsed per user-agent, sitemap discovered, and up to `max-pages` pages fetched
   with a truthful identifying User-Agent, no JavaScript executed. The crawl
   frontier is deterministic (sitemap order, then lexicographic BFS) and the run
   carries a global deadline with graceful partial results.
2. **Invoke each specialist skill** as a separate process, passing the bundle
   path. Each returns its own findings array. They never import from each other
   or from this skill, so every skill folder stays independently installable:
   - `crawl-access-audit` — can a retrieval agent reach the page?
   - `fact-extractability-audit` — does the specific fact survive text extraction,
     and is it typed unambiguously?
   - `freshness-corroboration-audit` — is it current, self-consistent, corroborable?
   - `engagement-audit` — will a visitor who lands here be able to act?
3. **Mark latent findings.** Where an access-gate failure makes a downstream
   finding unobservable, set `status: "latent"` and record `blocked_by` naming
   *which agents* are affected. Never delete the finding — see
   `references/severity-rationale.md` for why suppression is the wrong call.
4. **Derive severity** from the published table in `scripts/model.py`, and write
   the arithmetic into each finding's `severity_rationale`.
5. **Prioritize** by `severity × confidence ÷ effort`, demoting latent findings.
6. **Emit one report** against the schema in `../../schema/audit-report.schema.json`,
   including `checks_skipped[]` with reasons and a `limits` block.

```bash
python3 scripts/audit.py https://example.com -o report.json
python3 scripts/audit.py https://example.com --bundle b.json -o report.json
python3 scripts/audit.py --replay b.json -o report.json   # deterministic re-run
```

## Output

A single JSON audit report. It is a **superset** of the required schema:
`site`, `audited_at`, `summary{total_findings, critical, high, medium, low}`, and
`findings[]` each with `id`, `title`, `severity`, `evidence`, `suggested_action`.

Added beyond the minimum:

- `severity_rationale` — the arithmetic behind the severity, auditable line by line
- `gate`, `mechanism`, `confidence`, `measurement_basis`, `blast_radius`
- `status` (`active`/`latent`) and `blocked_by`
- `coverage` and `run_status` — so a truncated crawl can never look like a clean one
- `checks_skipped[]` with the reason and the impact of each omission
- `prioritized_actions[]` and `proactive_recommendations[]`
- `limits` — what this audit structurally cannot see

## Guarantees

- **Read-only.** GET requests only. Never touches authenticated areas.
- **Truthful identity.** The auditor identifies itself as `AIReadinessAudit/1.0`
  and never impersonates `GPTBot` or any other agent. Claiming another agent's
  user-agent would bind us to that agent's robots rules and would be
  impersonation.
- **robots.txt is honoured** for our own user-agent, with `Crawl-delay` respected
  up to 2 s (beyond that we reduce page count rather than exceed the time budget).
- **Runtime** is bounded by a 240 s deadline inside the 5-minute limit.
- **Determinism**: the analysis layer is deterministic for a fixed bundle.
  Network observation is not, and we say so rather than claiming otherwise.
  `--replay` gives a byte-stable re-run.

## References

- `references/severity-rationale.md` — every base severity, and why
- `references/report-schema.md` — field-by-field description of the output
