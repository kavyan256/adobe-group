# Report schema, field by field

The formal schema is `schema/audit-report.schema.json`. This file explains the
intent behind the fields beyond the required minimum.

## Required by the specification

| Field | Notes |
|---|---|
| `site` | Host of the audited site |
| `audited_at` | UTC ISO-8601 |
| `summary.total_findings` | Always equals `len(findings[])` |
| `summary.{critical,high,medium,low}` | Counts by severity over **every** finding, whatever its status; with `summary.info` they add up to `total_findings` |
| `findings[].id` | `F-001`… assigned **after** ranking, so the ids read top-down in report order |
| `findings[].title` | One line, states the defect and its scale |
| `findings[].severity` | Derived from the published table |
| `findings[].evidence` | Must name what was checked, what was found, and how to reproduce it |
| `findings[].suggested_action` | `summary` + `priority`, plus `effort`, `how[]`, `verify`, and when an agent review supplied one, `site_specific[]` + `grounded_on` |

**Note on the counts:** `total_findings` always equals `len(findings)` and the
four severity counts add up to it, so any external validator agrees with the
array. Urgency is a separate split: a latent finding is real but currently
unobservable (its access blocker must be fixed first) and a confirm-intent finding
looks deliberate, so `summary.active_findings` is the number the operator can act
on today and `summary.active_by_severity` gives the same four counts over active
findings only.

## Order

`findings[]` and `prioritized_actions[]` share one order: severity band first
(critical > high > medium > low > info), then `priority_score` within the band
(`severity × confidence × status ÷ effort`, latent and confirm-intent demoted; an
agent-review claim counts as medium effort whatever the reviewer wrote), then
`check_id` as a stable tie-break.

## Superset fields, and why each exists

| Field | Why |
|---|---|
| `severity_rationale` | The arithmetic behind the severity, printed so a reader can audit it rather than trust it |
| `hurts` + `summary.by_hurts` | Plain-language tag for non-experts: `ai_discoverability` (assistants can't find, read or cite it), `user_retention` (visitors who arrive don't stay), or `both`. Derived from `gate`; alt text, filler, promise/payoff mismatch, markup contradicting the page, broken pages and title problems are `both` |
| `gate` | Which of the ordered gates failed — access, extractability, interpretability, freshness, engagement (or `review` for an agent claim) |
| `mechanism` | Which background mechanism the finding is rooted in |
| `confidence` | `deterministic` (a literal string was present or absent) vs `heuristic` |
| `measurement_basis` | `static_fact` vs `static_heuristic`; the latter is capped at medium |
| `blast_radius` | `site_wide` / `template` / `single_page` — banded, never a raw ratio |
| `status` + `blocked_by` | Latent findings, with the *agents* affected named |
| `affected_urls` + `affected_url_count` | Findings are deduped by check type across URLs, so one finding carries many URLs rather than flooding the report |
| `coverage` + `run_status` | A truncated crawl can never masquerade as a clean one |
| `checks_skipped[]` | Distinguishes "we looked and found nothing" from "we could not look" — the failure mode that makes audit tools untrustworthy. Entries are written "Not assessed: … Reason: … How to check it yourself: …" |
| `prioritized_actions[]` | The top 15 findings in report order, with score, effort and the one-line action |
| `proactive_recommendations[]` | Improvements worth making even where no defect was detected, kept structurally separate from findings so they are never confused with them. **Conditioned on the site**: each carries `applies_because` naming what was probed (`/llms.txt`, robots.txt agent groups, FAQPage / Organization sameAs markup, hydration payloads, the homepage's opening copy, in-content links on deep pages) |
| `already_in_place[]` | The proactive recommendations this site already satisfies, with the evidence — so the reader sees the list was checked, not pasted |
| `limits[]` | What this audit structurally cannot see, in the same "Not assessed / Reason / How to check it yourself" form |
| `source` | `scripted` (a tested check with a published severity) or `agent_review` (a reviewer's claim whose evidence was checked against the crawl; heuristic, at most **low**) |
| `suggested_action.site_specific[]` + `grounded_on` | Steps an agent review wrote for this site, admitted only because `grounded_on.quote` was found on `grounded_on.url`, a page the finding reports |
| `agent_review` | `status` (`not_run` / `run` / `failed`), claims and fixes submitted, verified and merged, and every rejected claim or fix with its reason — so a reader can see what the review proposed and why some of it was not accepted |

## Design rules

- **Dedupe by check type**, not by URL. Forty pages missing structured data is
  one finding with `affected_url_count: 40`, not forty findings.
- **Evidence must be reproducible.** Where possible it includes the `curl` or
  `grep` that confirms it. An agent-review finding's evidence keeps the
  reviewer's reasoning and the checked assertions apart, each labelled.
- **Every action carries `verify`.** A fix nobody can confirm is not actionable.
