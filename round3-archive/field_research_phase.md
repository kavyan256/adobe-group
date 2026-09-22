# Field Research Phase — Detailed Plan (Aug 28–30)

Goal: find real websites AI assistants cite/quote well vs. ones they ignore or misrepresent, and distill *why* into concrete, repeatable detection signals — not one-off site quirks. This is the highest-leverage phase (drives rubric criteria #1 Detection accuracy and #6 Generalization). Everything here should end up as evidence-backed entries in the shared findings log (template at the bottom), which feeds directly into the Aug 31–Sep 1 architecture/schema design.

**Ground rule:** we are never told which sites will be used for grading, and none of our researched sites will be graded on. So the output of this phase is not "facts about specific sites" — it's **patterns**: "sites with property X consistently get cited / consistently get ignored." Every candidate signal needs ≥2–3 independent examples before it counts.

---

## 1. Why this phase matters

Per the problem statement's appendix, an AI assistant's answer is shaped by (map every observation back to one of these):

- **A. Crawl/read/extract chain** — a page must be (1) crawlable, (2) machine-readable, (3) have the specific fact extractable, or it might as well not exist.
- **B. Source selection** — assistants that browse live pick sources that are easy to reach, read, and quote from.
- **C. Machine readability** — JS-rendered-only content, non-text-locked facts (images/PDFs/video) are often invisible to machines even when visible to humans.
- **D. Cross-web agreement** — a fact repeated consistently across independent sources is trusted more than a fact living in one place; ambiguous entity names (shared brand names) cause misidentification.
- **E. Personalization/context** — same question, different users, can get different answers based on prior context — largely outside our control, but worth noting as a source of variance when comparing results.
- **F. Summarization drop-off** — content buried in non-text or surrounded by filler tends to get dropped from AI-generated summaries (more relevant to on-site/email content than site auditing, but the same "is the important fact in clean, extractable text" logic applies to on-site engagement too).

The research task is to go find real instances of each mechanism succeeding or failing, and to separately investigate the **on-site engagement** half (why a visitor who does land on a page bounces) — which the appendix doesn't cover in as much depth, so this needs more original investigation.

---

## 2. Two halves of the problem — split research accordingly

1. **Off-site discoverability** — why a brand/page isn't found or cited by AI assistants at all, or is found but misrepresented.
2. **On-site engagement** — why a visitor who *does* arrive from a search/AI citation doesn't stay, doesn't convert, or leaves confused.

Both halves need real examples with evidence. Don't over-invest in one and skip the other — the rubric grades both equally.

---

## 3. Method — how to actually research this

For each site you pick, run this loop:

1. **Pick a query** an AI assistant might get asked about the site's domain/brand (e.g. "best noise-cancelling headphones under $200", "does [brand] ship internationally", "what's [brand]'s return policy").
2. **Ask the query to 2–3 AI assistants that browse the live web** (e.g. ChatGPT with search, Perplexity, Claude with web search). Note: which sites got cited, which got paraphrased vs. quoted, which brands were missing entirely despite being obviously relevant.
3. **For a cited site**: open the actual page(s) the assistant used as a source. Inspect:
   - View page source (`curl` or "View Source", not just rendered DOM) — is the key fact present in raw HTML, or only after JS runs?
   - Check for structured data: search for `application/ld+json`, `itemscope`/`itemprop` (microdata), OpenGraph tags.
   - Check `robots.txt` for crawl blocks.
   - Note how directly the fact is stated (one clear sentence vs. buried in a table/image/PDF).
4. **For a plausible-but-missing site**: do the same inspection and note what's *different* — is JS-rendering required? No structured data? Fact only in an image or PDF? Contradictory info across pages? Same brand name collides with something else on the web?
5. **Cross-check agreement**: for a specific factual claim (price, policy, feature), search the wider web (not just the brand's own site) — is the claim corroborated by 3rd parties, or does it only exist on the brand's own page? Does it look stale (old dates, outdated pricing) or contradicted elsewhere?
6. **For on-site engagement**: actually land on the page as a fresh visitor would (via the cited link) and evaluate: Is it obvious what the page/company is and what to do next within a few seconds? Is there a clear next action? Does the page context orient a visitor with no prior context (no assumption they came from a specific ad/campaign)? Compare a site that "feels" engaging vs. one that feels confusing/dead-end, and try to name the *specific, observable* reason, not a vibe.
7. **Log every observation** in the shared findings doc immediately — do not rely on memory. Use the template in Section 6.

Do this across a **deliberately varied sample**: different industries (e-commerce, SaaS, local business, media/publisher, nonprofit), different site sizes (small business vs. large brand), different tech stacks if identifiable (obviously JS-heavy SPA vs. server-rendered). Variety is what prevents overfitting to one type of site.

---

## 4. Task distribution — 3 people

Aim for ~15–20 sites total investigated across the team by end of Day 3 (Aug 30), each backed by concrete evidence (screenshots, page-source snippets, query/response transcripts).

### Person A — Off-site discoverability: crawl & machine-readability
**Focus:** Appendix A, B, C (crawl access, source selection, machine "readability" of pages).

- Pick 6–8 diverse sites/brands. For each, run 2–3 AI-assistant queries relevant to that brand and record whether/how it was cited.
- For sites that got cited well: inspect raw HTML, structured data, robots.txt, page load behavior (JS-dependent vs. not). Record what's present.
- For sites that got ignored/missed despite being relevant: same inspection, record what's missing or broken.
- Deliverable: a table of sites with citation outcome + technical readability findings, plus a first-draft list of 4–6 candidate "discoverability" detection signals (e.g. "no JSON-LD product markup," "critical facts only render after JS," "robots.txt blocks key paths," "content only exists as image/PDF").

### Person B — Off-site discoverability: trust, freshness & entity clarity
**Focus:** Appendix D (cross-web agreement, entity ambiguity), plus staleness/freshness.

- Pick 6–8 diverse sites/brands (can overlap with Person A's list for cross-referencing, but should include some new ones).
- For a specific factual claim on each site (pricing, policy, specs, dates), check corroboration across independent 3rd-party sources (review sites, news, forums, other brand mentions). Note agreement vs. isolated/contradicted claims.
- Check for staleness signals: outdated copyright years, old blog/news dates, deprecated product info still live, broken/moved pages.
- Check for entity ambiguity: does the brand share a name with something else online (a different company, a common word, a person)? Does the site do anything to disambiguate itself (clear "About," consistent naming, structured `sameAs`/`Organization` schema linking to verified profiles)?
- Deliverable: a table of sites with corroboration/freshness/ambiguity findings, plus a first-draft list of 4–6 candidate "trust/freshness/entity" detection signals.

### Person C — On-site engagement + synthesis lead
**Focus:** the on-site engagement half (less covered by the appendix — more original investigation), and pulling everyone's findings together into the shared log.

- Pick 6–8 sites (ideally including some from A's and B's lists, landing on the actual pages an AI assistant would cite/link to) and evaluate them as a cold visitor: clarity of what the page/company offers, obvious next action, orientation without assumed context, navigation dead-ends, mobile-friendliness if relevant, page load/broken elements.
- Compare pairs of similar sites (one that "feels" engaging, one that doesn't) and force yourself to name the *specific, observable* difference (not "bad design") — e.g. "no visible call-to-action above the fold," "page requires 3 clicks to find pricing," "landing page doesn't state what the product does in the first sentence."
- Deliverable: a table of sites with engagement findings, plus a first-draft list of 4–6 candidate "engagement" detection signals.
- **End-of-Day-3 responsibility:** merge A's, B's, and your own findings into one consolidated `research_findings.md` (or shared doc), dedupe overlapping signals, and produce the final categorized signal list (discoverability vs. engagement) that Days 5–6 architecture design will consume.

### Cross-cutting rules for all three
- Every candidate signal must cite ≥2–3 concrete examples (URL/screenshot/query-response snippet) before it's promoted to the shared list — single anecdotes don't count.
- Don't record *which* sites you used anywhere that will ship in the submission — the deliverable is the pattern, not the site list (per the problem statement: sites studied aren't graded and shouldn't be baked in as hardcoded checks).
- Sync briefly at the end of each day (even async, in the shared doc) to avoid all three converging on the same handful of obvious sites — steer toward variety.

---

## 5. Timing within the 3 days

| Day | All 3 people |
|---|---|
| Aug 28 | Independent research per assigned focus area (Sections above). Log raw observations continuously. |
| Aug 29 | Continue research; start looking for patterns across your own examples (not just single anecdotes); flag interesting/surprising finds to the group. |
| Aug 30 | Morning: finish any remaining site investigation. Afternoon: Person C merges all findings into the consolidated signal list; group reviews together, resolves overlaps/disagreements, and finalizes the categorized list that feeds into architecture design (Aug 31). |

---

## 6. Findings log template (use per site investigated)

```
### Site: [describe generically, e.g. "mid-size DTC e-commerce brand" — don't need the real name in the shared summary if avoiding hardcoding, but keep it in your raw notes for verification]
Investigated by: [A/B/C]
Query used: "..."
Assistant(s) used: [ChatGPT / Perplexity / Claude...]
Outcome: [cited & quoted accurately / cited & misrepresented / not cited despite relevance]

Technical observations:
- Robots.txt: [open / blocks paths: ...]
- Structured data: [none / JSON-LD present for: ... / microdata / OpenGraph only]
- JS dependency: [content in raw HTML / requires JS render for key facts]
- Freshness signals: [dates found, staleness indicators]
- Cross-web corroboration: [claim confirmed by N independent sources / isolated to own site / contradicted]
- Entity ambiguity: [none / name collides with: ...]
- On-site engagement (if applicable): [clarity of offer, next-action visibility, orientation, dead-ends]

Candidate signal(s) this supports: [name the pattern, e.g. "missing Product JSON-LD correlates with non-citation"]
```

---

## 7. Output of this phase

A single consolidated, deduped list of candidate detection signals split into:
- **Discoverability signals** (with sub-tags: crawl-access / machine-readability / structured-data / freshness-corroboration / entity-ambiguity)
- **Engagement signals**

Each signal: a one-line description, the mechanism it's rooted in (which appendix concept, or "original engagement finding"), and 2–3 supporting examples. This list is what Days 5–6 (architecture & schema design) will turn into actual skill checks — see `CLAUDE.md` → Timeline & Checkpoints.
