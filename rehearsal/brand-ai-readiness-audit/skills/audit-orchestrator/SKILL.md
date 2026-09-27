---
name: audit-orchestrator
description: >-
  Audit any website for AI-discoverability and on-site-engagement problems, and
  emit a single prioritized JSON report. Detects retrieval-agent blocks, facts
  that do not survive text extraction, missing or contradictory structured data,
  entity ambiguity, staleness, and on-site engagement risk factors. Use when
  diagnosing why a brand is missing or misrepresented in AI assistants, or why
  visitors who arrive from an AI answer do not stay. This is the marketplace
  entrypoint: it performs the single crawl, invokes the four scripted audit skills and the agent review
  skills, and composes their findings into one report.
license: Apache-2.0
allowed-tools: Bash Read Write
compatibility: Python 3.10+, httpx, beautifulsoup4
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
| `--max-pages N` | no | Crawl budget, default 20. Use 12 when an agent review will follow. |
| `--bundle PATH` | no | Save the fetched site bundle; the agent review reads it. |
| `--replay PATH` | no | Re-run the analysis over a saved bundle, with no network. |
| `--agent-claims PATH` | no | Claims and fixes from `agent-review-audit`, checked against the bundle and merged if they hold. |
| `-o PATH` | no | Write the report here instead of stdout. |

Work in a directory outside the marketplace folder (`WORK/` below).

## Procedure

Steps 1, 4 and 5 run scripts; 2, 3 and 6 are yours. Inside `audit.py` one run
does the rest: it crawls once (`scripts/bundle.py`, robots.txt to RFC 9309, no
JavaScript, truthful User-Agent, 280 s budget), runs the four scripted skills as
separate processes on the bundle, marks findings behind a total access block as
`latent`, derives severity from `scripts/model.py`, ranks, and writes one report.

1. **Run the scripted audit and keep the bundle.**
   ```bash
   python3 skills/audit-orchestrator/scripts/audit.py https://example.com \
       --max-pages 12 --bundle WORK/bundle.json -o WORK/report.json
   ```
   A skill that fails or times out lands in `checks_skipped[]`, never silently.
2. **Read `WORK/report.json` before anything else:** `summary.headline`,
   `summary.run_status` (`partial`, `blocked` or `failed` means findings are a
   sample, or that access is the whole story), `coverage.pages_ok`, and
   `checks_skipped[]` (what was *not* looked at, and why).
3. **Triage doubtful findings.** For each finding you are unsure about, open the
   owning skill's `SKILL.md` and read its "Interpreting results" section:
   `crawl-access-audit` for A*, `fact-extractability-audit` for B*/C*/X*,
   `freshness-corroboration-audit` for D*, `engagement-audit` for E*. Note every
   finding with `status: "confirm_intent"`: it looks deliberate and is a question
   for the owner, not an accusation.
4. **Run the agent review** (`agent-review-audit/SKILL.md`): profile the bundle,
   write up to 6 claims with evidence the verifier can check, then re-run on the
   same bundle. Only claims whose evidence holds and that repeat no scripted finding
   are merged, at most `low`, labelled `source: agent_review`.
   ```bash
   python3 skills/agent-review-audit/scripts/page_profile.py WORK/bundle.json WORK/report.json > WORK/profile.json
   # write WORK/claims.json
   python3 skills/audit-orchestrator/scripts/audit.py --replay WORK/bundle.json \
       --agent-claims WORK/claims.json -o WORK/report.json
   ```
   Skipping this step is allowed; the report then says `agent_review.status: "not_run"`.
5. **Write site-specific fixes** for the top scripted findings in the same
   `claims.json`, under `fixes`: each quotes text that is really on the affected
   page and gives steps for *this* site. They are merged into the finding's
   `suggested_action.site_specific` only when the quote is found on that page.
   (`agent-review-audit/references/claim-format.md`, "Fixes".)
6. **Present the result** in this order: the headline; the top three
   `prioritized_actions[]` with their evidence; what `latent` means (real, but
   hidden behind an access block until that is fixed) and what `confirm_intent`
   means (confirm with the owner before acting); then the Not-assessed list from
   `limits[]` and `checks_skipped[]`, so nobody reads "no finding" as "no problem".

## Output

One JSON report: the required `site`, `audited_at`, `summary` and `findings[]`
(`id`, `title`, `severity`, `evidence`, `suggested_action`), plus `hurts`, `status`,
`severity_rationale`, `source` (`scripted` or `agent_review`), `prioritized_actions[]`,
`proactive_recommendations[]`, `already_in_place[]`, `coverage`, `checks_skipped[]`,
`agent_review` and `limits[]`. Findings are ordered by severity band, then priority;
ids follow that order. `summary.{critical,high,medium,low}` count every finding and
add up to `total_findings`; `summary.active_by_severity` counts active ones only.

## References

- `references/report-schema.md` — the report, field by field
- `references/severity-rationale.md` — every base severity, and why
- `references/jsonld-normalisation.md` — the one parse every skill reads
