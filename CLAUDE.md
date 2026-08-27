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

## Decisions
*(record architecture/skill-decomposition choices here as they're made, with rationale)*

- *(none yet)*

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
