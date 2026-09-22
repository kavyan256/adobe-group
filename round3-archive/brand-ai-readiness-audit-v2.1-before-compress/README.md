# Brand AI-Readiness Audit — Agent Skill Marketplace

Point it at a website. It reports why AI assistants can't find, can't quote, or
get the facts wrong about that site — and why visitors who do arrive can't act —
as one prioritized JSON report of findings plus suggested actions.

**Read-only and recommend-only.** No skill in this marketplace modifies a live
site. Everything is a GET request; nothing touches authenticated areas.

```bash
pip install -r requirements.txt
python3 skills/audit-orchestrator/scripts/audit.py https://example.com -o report.json
```

---

## The skills, and how the entrypoint composes them

A page must clear three ordered, blocking gates before an assistant can cite it:
the crawler must be **let in**, must be able to **read** the page, and must be
able to **pick out the specific fact**. Two further concerns hang off the end —
whether the fact is *current and corroborable*, and whether a visitor who arrives
can *act*. The decomposition follows that structure.

| Skill | Concern | Runs standalone to answer |
|---|---|---|
| **`audit-orchestrator`** *(entrypoint)* | Crawl once, compose everything | — |
| `crawl-access-audit` | **Gate 1** — robots.txt per agent, noindex, snippet suppression, canonicals, sitemap | *"Can AI assistants reach my site at all?"* |
| `fact-extractability-audit` | **Gates 2 & 3** — does the fact survive text extraction, and is it typed unambiguously? | *"Can an assistant actually quote my pricing page?"* |
| `freshness-corroboration-audit` | Currency, self-consistency, corroborability | *"Why do assistants repeat outdated facts about us?"* |
| `engagement-audit` | On-site risk factors | *"Why don't visitors who arrive act?"* |

**How composition works.** The entrypoint performs a single polite crawl and
writes a normalised **site bundle** (parsed robots.txt, sitemap, and the raw
response for each page). It then invokes each specialist skill as a separate
process, passing the bundle, and each returns its own findings array. The
entrypoint merges them, marks blocked-but-real findings as `latent`, derives
severity from a published table, prioritizes, and emits one report.

This is why the sub-skills contain no shared library and never import from each
other or from the entrypoint: **each skill folder is independently installable
and runnable on its own**, which is what makes the decomposition real rather than
cosmetic.

```
audit.py <url>
   │
   ├── bundle.py ──► site bundle (one crawl, no JS, truthful UA, robots honoured)
   │                      │
   │        ┌─────────────┼─────────────┬──────────────┐
   │        ▼             ▼             ▼              ▼
   │   crawl-access  extractability  freshness   engagement
   │        │             │             │              │
   │        └─────────────┴──────┬──────┴──────────────┘
   │                             ▼
   └──────────────────► merge · latent · severity · prioritize ──► report.json
```

**One parse, then judgement.** The crawl layer also *normalises* what it fetched:
JSON-LD (`@graph` flattened, list-valued `@type` handled, nested entities hoisted)
and page text (two defined notions — `extracted`, what a readability extractor
keeps, and `full`, which retains chrome). Every skill reads those fields; no skill
parses JSON-LD or strips tags itself.

This is what makes the decomposition safe. In an earlier version each skill
parsed independently, and the skills disagreed *inside a single report*: one
finding asserted a site published no `Organization` `sameAs` links while the same
report listed those links under "already in place". Two parsers cannot be held in
agreement by discipline. One parser cannot disagree with itself. Skills still
consume data rather than code, so each folder remains standalone-installable.
See `skills/audit-orchestrator/references/jsonld-normalisation.md`.

---

## Deliberate configuration is not a defect

Some settings are choices. A site that keeps its terms of service out of the
index, or blocks training crawlers by name while allowing retrieval agents, has
made a decision — not a mistake. An audit that opens by telling the reader to
undo something they remember doing on purpose has spent its credibility before
its first real finding.

So findings that look deliberate are reported with the same evidence but a
different posture: `status: "confirm_intent"`, phrased as a question, capped at
`low`, and excluded from the headline. The reasoning is printed in
`intent_signals` so a reader who disagrees can see exactly what drove it.

The classifier has to discriminate, not merely soften. noindex confined to legal
and utility templates reads as deliberate; noindex on the homepage and the
pricing page stays `critical`. Both cases are pinned by fixtures in the test
suite. See `skills/crawl-access-audit/references/deliberate-vs-defect.md`.

---

## Which mechanisms this covers — including the ones it does not

Every report carries a `mechanism_coverage[]` block, generated from the severity
table itself so it cannot drift from what actually runs. Two entries say the
audit does not cover them:

- **Personalization (E)** happens inside the assistant, from context the user
  brings to the conversation. Nothing in a site's HTML determines it, so a
  site-side "personalization score" would be fabricated. The site-side lever is
  that each page state a self-contained, unambiguous fact — which is what the
  quotability and extraction-tier checks measure.
- **Email summarisation (F)** is not observable from a website. The transferable
  mechanism — substance carried in non-text, or buried under filler — is audited
  on-page as `B5_fact_locked_in_image` and `B6_filler_heavy`.

Naming what an audit cannot see is part of reporting honestly, alongside
`checks_skipped[]` (which records, with reasons, that colour contrast and Core
Web Vitals need a browser and field data respectively) and `limits[]`.

---

## Three design decisions worth explaining

### 1. No headless browser — and the audit is stronger for it

The obvious design diffs raw HTML against a rendered DOM to find JS-render gaps.
We reject it. A bundled Chromium is ~270–380 MB against a 50 MB budget, a runtime
download would break portability, and rendering is the single largest source of
nondeterminism.

More importantly, **the rendered DOM was never the measurement — only a fact
source.** Assistant fetchers run raw bytes through a boilerplate-stripping text
extractor that discards `<script>` *by construction*, and the major AI retrieval
agents don't execute JavaScript at all. So we ask an absolute question needing
one HTTP GET:

> **In what form does each expected fact exist in the raw response?**

| Tier | Where the fact lives | Verdict |
|---|---|---|
| T0 | visible prose or a heading | pass |
| T1 | JSON-LD / microdata | pass |
| T2 | *only* inside a script payload | **medium** — in the bytes, absent from the text |
| T3 | absent from the raw bytes | **high** — genuinely invisible |

We parse `__NEXT_DATA__`, `self.__next_f`, `__NUXT__`, Apollo and Redux payloads
*before* firing. That matters: a naive "SPA therefore invisible" check
false-positives across the entire Next.js and Nuxt web. Where a price is found
only in `__NEXT_DATA__`, that's the strongest evidence this marketplace produces
— and it's reported as *hard to reach*, not *invisible*.

### 2. Blocking a training crawler is not a discoverability defect

The most damaging false positive in this problem space is treating every "AI bot"
in robots.txt as equivalent. `GPTBot`, `ClaudeBot`, `CCBot`, `Google-Extended`,
`Applebot-Extended` and `Bytespider` gate **model training**. Blocking them has
no effect on whether you're cited — blocking `Google-Extended` doesn't affect
Google Search or AI Overviews, which are served from the Googlebot index.

The agents that gate citation are different ones: `OAI-SearchBot`,
`ChatGPT-User`, `Claude-SearchBot`, `Claude-User`, `PerplexityBot`,
`Perplexity-User`, `Applebot`, `Googlebot`, `Bingbot`.

A publisher blocking training while allowing retrieval has made a coherent,
deliberate choice. We fire a finding **only** for retrieval agents; training
blocks are reported as neutral policy in `site_profile.ai_policy`.

We also parse robots.txt ourselves to RFC 9309 semantics, because Python's
stdlib `urllib.robotparser` mishandles wildcards and `Allow` precedence — and a
blocking finding is only as trustworthy as its parser.

### 3. Severity is a published table, not a formula

An earlier draft computed `severity = f(gate, blast_radius, confidence)`. On
inspection `gate` and `confidence` are constants per check type, so the function
collapsed to `table[check] × blast_radius` — a lookup table with extra steps.

We ship the table explicitly and print the arithmetic into every finding:

```
"severity_rationale": "base=high (access/A2_snippet_suppressed);
                       blast=template x0.8 -> demoted to medium => medium"
```

Blocked findings are marked **`latent`**, never suppressed. Suppression would
mean the operator fixes robots.txt, re-audits, and meets a wave of findings
nobody warned them about. And since robots is *per-user-agent*, `blocked_by`
names exactly which agents are affected.

---

## What the report contains

Beyond the required `site` / `audited_at` / `summary` / `findings[]`:

- `severity_rationale` — auditable arithmetic, not a black box
- `status` + `blocked_by` — latent findings and what's blocking them
- `confidence`, `measurement_basis`, `blast_radius`, `gate`, `mechanism`
- `coverage` + `run_status` — a truncated crawl can never look like a clean one
- **`checks_skipped[]`** — with reason and impact. This distinguishes *"we looked
  and found nothing"* from *"we couldn't look"*, which is the failure mode that
  makes audit tools untrustworthy
- `prioritized_actions[]` — ranked by `severity × confidence ÷ effort`
- `proactive_recommendations[]` — improvements worth making even with no defect,
  **conditioned on the site**: `/llms.txt` is probed, robots.txt agent groups,
  FAQPage / `sameAs` markup and hydration payloads are checked, and anything the
  site already does moves to `already_in_place[]` with its evidence
- `limits[]` — what this audit structurally cannot see

Every suggested action carries `how[]` (concrete steps) and `verify` (how to
confirm the fix worked). A fix nobody can confirm isn't actionable.

---

## What this deliberately does not do

Stated plainly, because a declared limitation beats a fabricated measurement:

| Not done | Why |
|---|---|
| Cross-web corroboration | Needs a search backend. Runs only with `SEARCH_API_KEY`; otherwise appears in `checks_skipped[]`. We detect the *absence of corroboration infrastructure* instead, which is verifiable. |
| Colour contrast | Needs computed styles, therefore a browser. The most unarguable number we give up — reported as skipped, with the right tool named. |
| Core Web Vitals | Field metrics at p75. A synthetic fetch isn't a measurement, and **INP can't be measured synthetically at all**. |
| Consent-banner flagging | Consent notices are legally mandated. Flagging their presence would be a false positive on nearly every EU-facing site. |
| Bounce rate | Conflates satisfied and dissatisfied exits. For AI-sourced traffic the click is usually *verification* — a 15-second visit is often the win. |
| Action-verb CTA detection | An English verb list fails on every non-English site. We test for interactive affordance structurally instead. |

---

## Guarantees

- **Truthful identity** — identifies as `AIReadinessAudit/1.0`, never impersonates
  `GPTBot` or any other agent. Claiming another agent's UA would bind us to its
  robots rules and would be impersonation.
- **robots.txt honoured** for our own UA; `Crawl-delay` respected up to 2 s, and
  beyond that we reduce page count rather than exceed the time budget.
- **Runtime** bounded by a 240 s deadline inside the 5-minute limit.
- **Determinism** — the analysis layer is deterministic for a fixed bundle; every
  collection is sorted by an explicit key and severity consumes only banded
  values. Network observation is not deterministic, and we say so rather than
  claiming otherwise. `--replay` gives a byte-stable re-run.

## Requirements

Python 3.10+, `httpx`, `beautifulsoup4` (pinned in `requirements.txt`). No model weights, no browser,
no network services. Total package well under 1 MB.

## Tests

```bash
python3 tests/run_tests.py
```

Covers RFC 9309 parser conformance (including the `*`-group precedence case the
stdlib gets wrong) and end-to-end extraction tiering against a fixture where the
same price sits at T0, T2 and T3 on three otherwise-identical pages.
