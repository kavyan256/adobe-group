# Adobe University Hackathon 2026 — Round 3

## Project
Build an **Agent Skill Marketplace**: a package of one or more skills (agentskills.io SKILL.md format), tied together by `marketplace.json`, with exactly one entrypoint skill. Given a website, the entrypoint audits it for AI-discoverability and on-site-engagement problems and emits a single JSON audit report (findings + prioritized suggested actions).

Full spec: [`adobe_problem_statement.md`](./adobe_problem_statement.md) — read that for exact wording, schema, rubric, and appendix before making design decisions.

## Deadline
**2 weeks from 2026-08-27 → submit by 2026-09-10.**

## Hard constraints (do not violate)
- [ ] Recommend-only — no skill ever modifies a live site; everything read-only/sandboxed.
- [ ] No destructive, authenticated-area, or rate-abusing actions. Respect `robots.txt`.
- [ ] Every skill folder has a valid SKILL.md (agentskills.io spec: YAML frontmatter with name/description/license + body).
- [ ] Marketplace root has `marketplace.json` listing every skill, marking **exactly one** `entrypoint: true`.
- [ ] Audit report JSON includes at minimum: `site`, `audited_at`, `summary` (total_findings + counts by severity), `findings[]` each with `id`, `title`, `severity`, `evidence`, `suggested_action`.
- [ ] Submission zip ≤ 50 MB, no pretrained model weights.
- [ ] Audit runtime < 5 minutes on a standard machine for a typical site.
- [ ] Marketplace is self-contained/portable — no external service needed just to resolve the manifest.
- [ ] No example/test sites are provided — design must generalize, not fit specific sites studied during research.
- [ ] Submission = zip of marketplace root (marketplace.json + all skill folders) + root README.md describing each skill and how the entrypoint composes them.

## Rubric (what's actually graded)
1. Detection accuracy (evidence-backed, few misses/false positives, both discoverability + engagement)
2. Suggested-action quality (correctly targeted, mechanism-sound, prioritized, non-obvious extras)
3. Output design (clear, structured, actionable report a non-expert could act on)
4. Skill-format & engineering hygiene (agentskills.io compliant, well-formed manifest, deterministic, safe)
5. Marketplace composition (genuine separation of concerns, not padding — single skill is fine too)
6. Generalization (works on unseen sites)

## Timeline & Checkpoints

14-day window: **2026-08-27 → 2026-09-10**. Each phase lists what to actually be doing day-to-day, plus a hard checkpoint deliverable due at the end of the phase.

| Dates | Phase | What we should be doing | Checkpoint (must be true by end of phase) |
|---|---|---|---|
| Aug 27 (Day 1) | Setup | Read problem statement, set up tracking docs | ✅ Done — `adobe_problem_statement.md` + `CLAUDE.md` exist |
| Aug 28–30 (Days 2–4) | Field research | Browse real sites; compare ones AI assistants (ChatGPT/Perplexity/Claude w/ web search) cite well vs. ignore/misrepresent; note *why*, tying observations back to Appendix A–F mechanisms — see [`field_research_phase.md`](./field_research_phase.md) for detailed methodology + 3-person task split | Written list of candidate detection signals, each backed by 2–3 real examples, sorted into discoverability vs. engagement |
| Aug 31–Sep 1 (Days 5–6) | Architecture & schema design | Decide skill decomposition (one skill vs. several); design full audit-report JSON schema (superset of the required fields); sketch `marketplace.json`; sketch each skill's SKILL.md frontmatter | Decision recorded in **Decisions** section below; schema finalized; skeleton folders + empty SKILL.md stubs + `marketplace.json` created |
| Sep 2–4 (Days 7–9) | Build: discoverability detection | Implement checks/scripts for crawlability, JS-render gaps, structured data (schema.org/JSON-LD), freshness/corroboration, entity ambiguity | Discoverability checks run end-to-end on at least one real site and produce findings with evidence |
| Sep 5–6 (Days 10–11) | Build: engagement detection + suggested actions | Implement on-site engagement checks; build the mapping from each finding type to a prioritized, mechanism-sound suggested action, plus proactive "beyond the problem" suggestions | Engagement checks working; every finding type has a corresponding suggested-action generator |
| Sep 7 (Day 12) | Build: entrypoint/orchestrator | Wire all skills together via the entrypoint so it composes sub-skill outputs into the single final report matching the schema | Running the entrypoint against a URL produces a complete, schema-valid JSON report |
| Sep 8 (Day 13) | Generalization testing & hardening | Run the full marketplace against ≥3 sites never used during research/dev; hunt false positives/negatives; check runtime (<5 min), zip size (≤50MB), robots.txt compliance, read-only guarantee; fix what breaks | Tested on ≥3 unseen sites with reasonable, evidence-backed output within runtime/size limits |
| Sep 9 (Day 14) | Polish, docs, rubric self-review | Finalize each SKILL.md (progressive disclosure — checklists to `references/`, executable checks to `scripts/`); write root README.md; do a line-by-line pass against Section 4 rubric + Section 5 guardrails | Submission zip assembled and self-reviewed against the rubric; only buffer/last-minute fixes remain |
| Sep 10 | **Submission day** | Final sanity run, re-zip if anything changed, submit | Submitted — built-in 1-day buffer if Sep 8 testing surfaced bigger issues |

**Notes:**
- The research phase (Aug 28–30) is the highest-leverage phase — rubric criterion #1 (Detection accuracy) and #6 (Generalization) both depend on finding *real, repeatable* signals here rather than guessing. Don't shortcut it.
- Don't start writing SKILL.md/scripts before the Sep 1 architecture checkpoint — changing schema/decomposition mid-build is expensive.
- If research (Days 2–4) runs long, borrow from the Sep 1 architecture buffer, not from testing/polish at the end — generalization testing (Sep 8) is what catches overfitting to researched sites and should not be cut.

## Progress Log
*(append dated entries here as work happens)*

- **2026-08-27** — Read full problem statement PDF; transcribed to `adobe_problem_statement.md`; set up this progress tracker. No design/implementation work started yet.
- **2026-09-12** — v3 (`brand-ai-readiness-audit-v2.1/`, commit f0fb27e) reviewed by five independent judge agents; plan published as the "AI-Readiness Audit v4 Plan" artifact. **v4 built in `brand-ai-readiness-audit-v4/`** (submission candidate): verifier hardened and agent claims capped at low, per-bot robots directives, A1 intent fixed, price/date/entity fixes, noise cut (X2, D5 removed), new checks A5_canonical_missing/A9/A10/A11/C7/E11/E12, E1 split, report counts consistent, IDs in ranked order, polite crawler, docs rewritten. 351 offline tests; validator SUBMITTABLE; replays of 9 real sites compared against v3.
- **2026-09-12 (later)** — Final gate: grader + red team re-reviewed v4; fixed www/apex crawl collapse, verifier weak-op/every-page/link-scrub gaps, template-check dedupe, E3 hidden-control FPs (ikea.com, nps.gov), form-only contact pages. 361 tests. **Submission zip built: `submission/brand-ai-readiness-audit.zip`** (170 KB, top folder `brand-ai-readiness-audit`), verified by unzip-and-run. Live checks: basecamp, djangoproject, ikea.com/de, nps.gov all complete 12/12 in 26–40 s.
- **2026-09-12 (evening)** — Agent-in-the-loop demo on in.sennheiser-hearing.com (report in `audit-results/`). Triage found C2 false positives: "Article No. 700403 ₹3,990.00" read as "700403 ₹". Fixed: price tokens read currency-first and currency-last separately; variant offers with the selected price shown no longer fire C2; affected URLs and page counts are distinct. Re-crawl of the offers page: C2 gone, other findings unchanged. 369 tests; zip rebuilt and re-verified. Known, not fixed: tracking parameters kept in URLs, http/https homepage crawled twice, `/agents.md` fetched as a page.
- **2026-09-12 (night)** — Searched 5 unseen sites for agent-review value; The Ritz London run added a verified claim (first sitemap URL redirects to the homepage) and 3 site-specific fixes (`audit-results/`). Checking candidate claims exposed two bugs, now fixed: date patterns used `\b` and missed every ISO datetime (`2023-12-11T14:15:55+00:00`), so D1 fired on correctly dated blog posts (cry.org: 8 false D1 removed) and D3 was blind; engagement checks counted inert `<template>` content (Ritz). 375 tests; zip rebuilt and re-verified.
- **2026-09-12 (late night)** — 100-site evaluation (`eval-runs/2026-09-12-100/`, 100 categories, scripted audit only): no crashes, all reports schema-valid and deterministic, but severe-finding precision ~58%. Fixes: B1 price/contact obligations need commerce evidence and the contact page itself; crawler detects bot-challenge pages (vendor marker only on near-empty pages, found via a false hit on glastonburyfestivals.co.uk); noindex critical only on key pages or most of the crawl. Live re-run in `eval-runs/2026-09-12-100-after-fixes/`: 18 false severe findings removed. Checking every remaining severe finding against raw HTML showed precision is still only 27–55%: network failures and IP blocks reported as site defects, shells on 404/test pages, noindex on alias URLs; one regression (price only in hydration payload, bluebottle). The 100-site test bypassed the agent entirely, so it measured the scripts, not the skill. 398 tests.
- **2026-09-13** — Committed the fixes and evaluation (e48cb96, zip rebuilt and verified). Designed v5 "verdict layer": the agent judges every medium-or-above scripted finding (confirm / downgrade / confirm_intent / not_a_defect) with a reason code and evidence; `verify_verdicts.py` checks the evidence and applies fixed effects. Prototyped outside v4 in `eval-runs/2026-09-13-verdict-prototype/` with pre-registered criteria, 39 dev and 18 blind held-out findings, and 13 verifier controls (all pass). Pilot with headless Claude Code (Sonnet): fnac and supercell judged correctly after two fixes (harness permissions; deliberate_configuration scoped to A2/A3/A5), 122–208 s and ~$0.6 per site. All 63 scored runs failed on the account's monthly spend limit, so v5 is unproven; finish with `run_experiment.sh`. Also found: the URL normaliser strips trailing slashes (tfl, 6 of 12 broken-page URLs). v4 unchanged.
- **2026-09-13 (final)** — Finished and scored the v5 verdict layer, then **rejected it and submitted v4**. v5 judged better (it cleared a real B1 false positive and downgraded an overstated E3 on msf.org) but its agent step measured 268 s on mistral.ai against a 152 s advisory budget, and 302 s on msf.org after per-item checkpointing was added — over the 5-minute ceiling once crawl time counts, with findings that vary between runs. v4's scripted pass is hard-bounded at 280 s in code and replays byte-identical. Submitted `submission/brand-ai-readiness-audit-FINAL.zip` (184 KB, 398 tests, validator SUBMITTABLE, byte-identical to `brand-ai-readiness-audit-v4/`). Report format re-verified on a fresh djangoproject.com crawl: counts, `affected_url_count` and page totals all consistent.
- **2026-09-22** — **Through to Round 4** (`adobe round 4 problem statement.pdf`): a ≤5-minute video (methodology ≤3 min, live run ≤2 min) plus `REPLAY_<TeamName>.txt`, due **2026-09-27 23:59 IST**. The Round 3 package is not resubmitted — judges replay their copy, so the engine must not change. Repo reorganised: everything Round 4 does not need moved to `round3-archive/` (v2.1/v5 trees, `eval-runs/`, `audit-results/`, `docs/`, `tools/`, staging copies).

## Decisions
*(record architecture/skill-decomposition choices here as they're made, with rationale)*

- **v4 ships, not v5.** The rubric scores accuracy, but runtime is a pass/fail gate and Round 4 flags nondeterminism for a second review. v5 traded a hard guarantee for a scored improvement; v4 keeps both the guarantee and a deterministic replay. v5 is kept in `round3-archive/` for reference.
- **Round 4 changes nothing in the engine.** `brand-ai-readiness-audit-v4/` is frozen; verify it against `submission/brand-ai-readiness-audit-FINAL.zip` before recording. Anything the judges' replay needs must be in that package or typed into `REPLAY_<TeamName>.txt`, since only the video and that file are submitted.

- **One folder per version, v4 is the one to zip** (`brand-ai-readiness-audit-v4/`; v2.1 = v3, `-before-v3` and `-before-compress` are restore points). Zip its contents with the top folder named `brand-ai-readiness-audit`.
- **Scripts measure, the agent judges, a script verifies.** Deterministic scripts do every check that can be measured; the agent's `agent-review-audit` claims enter `findings[]` only after `verify_claims.py` confirms their evidence against the crawl, and are capped at low. Rationale: the rubric scores both "few misses" and "few false positives" plus "deterministic".
- **No headless browser, search backend or LLM API calls** — size, self-containment and determinism rules; what needs them is listed under "Not assessed" in every report.

## TODO / Next Steps
- [ ] **Field research**: find real websites AI assistants cite well vs. poorly/ignore; identify concrete, repeatable signals (not one-off site quirks).
- [ ] **Design detection checks** for off-site discoverability (crawlability, JS-render gaps, structured data, freshness/corroboration, entity ambiguity — see appendix A–D).
- [ ] **Design detection checks** for on-site engagement (why visitors who arrive don't stay).
- [ ] **Design suggested-action logic**: map each finding to a correct, specific, prioritized fix; include proactive suggestions beyond detected defects.
- [ ] **Decide marketplace decomposition**: one skill vs. several (e.g. crawl-render-audit, freshness-corroboration, engagement-audit, orchestrator) — decompose only if it reflects genuine separation of concerns.
- [ ] **Define audit report schema** (superset of the required minimum fields).
- [ ] **Write SKILL.md** for each skill (name/description/license frontmatter + When to use / Inputs / Procedure / Output), keeping detailed checklists in `references/` and executable checks in `scripts/`.
- [ ] **Write `marketplace.json`** manifest with exactly one entrypoint.
- [ ] **Implement scripts** (crawling/fetching, structured-data parsing, robots.txt checks, freshness/corroboration lookups, engagement heuristics) — read-only only.
- [ ] **Test generalization** on multiple unseen sites (not ones from the research phase) to sanity-check the checks aren't overfit.
- [ ] **Verify runtime** < 5 min per typical site.
- [ ] **Verify zip size** ≤ 50MB, no model weights bundled.
- [ ] **Write root README.md** describing each skill and how the entrypoint composes them.
- [ ] **Final validation pass** against the rubric before zipping/submitting.
