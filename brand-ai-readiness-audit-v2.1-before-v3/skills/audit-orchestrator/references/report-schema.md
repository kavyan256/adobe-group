# Report schema, field by field

The formal schema is `schema/audit-report.schema.json`. This file explains the
intent behind the fields beyond the required minimum.

## Required by the specification

| Field | Notes |
|---|---|
| `site` | Host of the audited site |
| `audited_at` | UTC ISO-8601 |
| `summary.total_findings` | Always equals `len(findings[])`. Split into `summary.active_findings` and `summary.latent_findings` — see below |
| `summary.{critical,high,medium,low}` | Counts by severity, active only |
| `findings[].id` | `F-001`… assigned after deterministic sorting |
| `findings[].title` | One line, states the defect and its scale |
| `findings[].severity` | Derived from the published table |
| `findings[].evidence` | Must name what was checked, what was found, and how to reproduce it |
| `findings[].suggested_action` | `summary` + `priority`, plus `effort`, `how[]`, `verify` |

**Note on `total_findings`:** it always equals `len(findings)`, so any external
validator agrees with the array. The split matters for urgency: a latent finding
is real but currently unobservable (its access blocker must be fixed first), so
`active_findings` is the number the operator can act on today and the severity
counts cover active findings only. All three numbers are always present.

## Superset fields, and why each exists

| Field | Why |
|---|---|
| `severity_rationale` | The arithmetic behind the severity, printed so a reader can audit it rather than trust it |
| `hurts` + `summary.by_hurts` | Plain-language tag for non-experts: `ai_discoverability` (assistants can't find, read or cite it), `user_retention` (visitors who arrive don't stay), or `both`. Derived from `gate`; alt text, filler and promise/payoff mismatch are `both` |
| `gate` | Which of the ordered gates failed — access, extractability, interpretability, freshness, engagement |
| `mechanism` | Which background mechanism the finding is rooted in |
| `confidence` | `deterministic` (a literal string was present or absent) vs `heuristic` |
| `measurement_basis` | `static_fact` vs `static_heuristic`; the latter is capped at medium |
| `blast_radius` | `site_wide` / `template` / `single_page` — banded, never a raw ratio |
| `status` + `blocked_by` | Latent findings, with the *agents* affected named |
| `affected_urls` + `affected_url_count` | Findings are deduped by check type across URLs, so one finding carries many URLs rather than flooding the report |
| `coverage` + `run_status` | A truncated crawl can never masquerade as a clean one |
| `checks_skipped[]` | Distinguishes "we looked and found nothing" from "we could not look" — the failure mode that makes audit tools untrustworthy |
| `prioritized_actions[]` | Ranked by `severity × confidence ÷ effort`, latent demoted |
| `proactive_recommendations[]` | Improvements worth making even where no defect was detected, kept structurally separate from findings so they are never confused with them. **Conditioned on the site**: each carries `applies_because` naming what was probed (`/llms.txt`, robots.txt agent groups, FAQPage / sameAs markup, hydration payloads) |
| `already_in_place[]` | The proactive recommendations this site already satisfies, with the evidence — so the reader sees the list was checked, not pasted |
| `limits[]` | What this audit structurally cannot see |

## Design rules

- **Dedupe by check type**, not by URL. Forty pages missing structured data is
  one finding with `affected_url_count: 40`, not forty findings.
- **Evidence must be reproducible.** Where possible it includes the `curl` or
  `grep` that confirms it.
- **Every action carries `verify`.** A fix nobody can confirm is not actionable.
