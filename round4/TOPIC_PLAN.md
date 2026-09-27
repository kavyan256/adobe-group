# What to talk about — derived from the Round 4 brief

## Step 1. What the brief actually asks for

**Part 1 (≤ 3 min) — the brief's three questions, in its words**
- R1 *How you discovered the findings*: the field research; what separates sites
  AI assistants cite well from ones they ignore or misrepresent; how that was
  distilled into concrete, repeatable checks
- R2 *How you assigned severities*: the logic that decides how much each problem
  hurts discoverability or engagement
- R3 *How you derived the suggested actions*: why each fix is mechanism-sound,
  and how they're prioritised
- R4 Every claim anchored to the code (narration that can't be traced earns nothing)

**Part 2 (≤ 2 min) — must-haves**
- R5 URL typed on camera; one real, continuous run
- R6 The agent visibly invoking the entrypoint, fetching, reasoning
- R7 One finding drilled into: real evidence → severity → suggested fix; show fixes sorted by impact
- R8 Harness and model said aloud
- R9 One line confirming it's the Round 3 entrypoint, not a hardcoded demo

**Scoring (out of 100)**
- Reasoning, Part 1 — **35**: sound, *non-obvious*, traceable to code
- Live behaviour, Part 2 — **35**: real, evidence-backed findings; few misses, few false positives
- Reproducibility, quality and hygiene — **30**: judges replay and reach the same
  substance; findings hold on a URL *they* choose; **deterministic**

**Gates (override the score)**: fabricated findings or a spliced run → bottom;
judges can't reproduce → "ran-blocked"; replay differs materially from the video → second review

**Also in the brief**: read-only, robots.txt respected, same engine as Round 3
(section 7). The public statement asks for an interface where users "explore,
interact, gain meaningful insights"; section 7 says a CLI agent session satisfies it.

## Step 2. Every topic we could cover

Seconds are spoken time at a normal pace. "Where" is the best place for it.

| # | Topic | Brief item | Verdict | Where | ~sec |
|---|---|---|---|---|---|
| T1 | What separates cited from ignored or misrepresented sites (can't get in / can't find the fact; stale, contradictory, ambiguous brand) | R1 | **MUST** | P1 | 12 |
| T2 | Facts graded by *where* they live: visible text passes, hidden script data medium, missing high. Stops us calling every JavaScript site invisible | R1, non-obvious | **MUST** | P1 | 14 |
| T3 | Training bots vs answer bots: blocking GPTBot doesn't stop citation, so only answer bots are flagged | R1, non-obvious | IMPORTANT | P1 | 8 |
| T4 | Field testing: 100 real sites, serious findings checked by hand, each false alarm became a rule (bot-challenge pages, legal pages kept out of search) | R1 "field research", few false positives | **MUST** | P1 | 16 |
| T5 | "43 checks, 40 fired across 100 sites" | coverage | SKIP | — | 6 |
| T6 | Engagement side: what stops a visitor who arrives from acting | R2 "or engagement" | IMPORTANT | P1 | 6 |
| T7 | Base level from where the chain breaks: critical / high / medium / low, each with its reason | R2 | **MUST** | P1 | 18 |
| T8 | Levels set by mechanism, never by how common the problem is (no grading on a curve) | R2, non-obvious | IMPORTANT | P1 | 7 |
| T9 | Spread: a problem on one page drops a level | R2 "how much it hurts" | **MUST** | P1 | 5 |
| T10 | Caps: rules of thumb max medium; hidden behind a bigger block or looks deliberate → max low; AI → max low | R2 | **MUST** | P1 | 11 |
| T11 | Why "hidden behind a block" isn't deleted (the owner would meet a wave of surprises after unblocking) | R2 detail | SKIP | — | 8 |
| T12 | Every finding says whether it hurts discovery, visitors or both | R2 wording | IMPORTANT | P1 | 4 |
| T13 | Every finding prints its own severity arithmetic | R4, trust | IMPORTANT | **P2** (shown live in 2.8) | 0 |
| T14 | Each fix targets the measured cause, with a "how to confirm it worked" step | R3 "mechanism-sound" | **MUST** | P1 | 7 |
| T15 | AI can add site-specific fix steps only by quoting real page text (Qualcomm example) | R3, non-obvious | IMPORTANT | P1 | 10 |
| T16 | Prioritising: levels first, then impact over effort, so cosmetic never beats a blocker | R3 "prioritised" | **MUST** | P1 | 8 |
| T17 | Proactive suggestions only for what the site doesn't already do | extra | SKIP | — | 8 |
| T18 | The one rule: scripts measure, the AI judges, a script verifies | framing | IMPORTANT | P1 opening | 6 |
| T19 | Crawl once, parse once, so no two checks can disagree | determinism | merge into T24 | P1 | 0 |
| T20 | The verifier's rules in detail (uncrawled pages, true of every page, absence-only, duplicates) | integrity gate | SKIP detail; one clause in T26 | P1 | 0 |
| T21 | AI value example: blender.org press releases "modified in 2024" | non-obvious | SKIP | P2 shows AI value live (2.9) | 10 |
| T22 | 8 of 8 AI-added findings held up when checked by hand | evidence | IMPORTANT | P1 | 5 |
| T23 | "Found nothing" is never "couldn't look": the Not-assessed list | few false positives | IMPORTANT | **P2** (the agent prints it) | 0 |
| T24 | Why repeatable: same answer twice, or you can't tell if the fix worked | 30-pt criterion, gate | **MUST** | P1 | 8 |
| T25 | How: crawl saved once, every check reads the same copy, the table sets severity, never the AI | 30-pt criterion | **MUST** | P1 | 8 |
| T26 | We tried letting the AI re-judge severity; it varied between runs and was too slow, so it can only add verified, low findings | non-obvious, honest | IMPORTANT | P1 | 12 |
| T27 | Proof: two live crawls gave identical findings; AI varies only in wording | 30-pt criterion | **MUST** | P1 | 7 |
| T28 | Whole run capped at 280 seconds | hygiene | IMPORTANT | P1 | 4 |
| T29 | Replay file, pinned versions, no-LLM fallback | 30-pt criterion | SKIP in video | REPLAY file does it | 8 |
| T30 | Read-only, robots.txt, polite crawler | section 7 | SKIP in P1 | P2 one phrase | 5 |
| T31 | Report designed for a non-expert: headline → what to fix first → what it couldn't check | public statement "insights" | IMPORTANT | **P2** (one line in 2.6) | 0 |
| T32 | Our measured precision on scripted severe findings (27–55%) | — | SKIP (don't volunteer; answer straight if asked) | — | — |

## Step 3. Time check

| | seconds |
|---|---|
| MUST topics (T1, T2, T4, T7, T9, T10, T14, T16, T24, T25, T27) | 114 |
| IMPORTANT topics kept in Part 1 (T3, T6, T8, T12, T15, T18, T22, T26, T28) | 62 |
| **Part 1 total** | **~176 s ≈ 2:56** |
| Part 1 cap | 180 s |

It fits, but only just: IMPORTANT topics that the live run shows anyway (T13, T21,
T23, T31) were moved to Part 2, which costs nothing there because the screen does
the work. If Part 1 runs long when read aloud, drop in this order:
T12 → T28 → T3 → T15.
