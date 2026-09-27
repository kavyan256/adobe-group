# Round 4 brief, line by line, answered from the project record

Built 2026-09-24. Every important line of `adobe round 4 problem statement.pdf` is
quoted exactly, followed by what the project record says about it.

**Sources mined:** the 12 git commits; `CLAUDE.md` progress log; the shipped engine
`brand-ai-readiness-audit-v4/` (code, SKILL.md files, references, 398 tests);
`round3-archive/docs/architecture_v2.html` (the design decision record);
`round3-archive/eval-runs/` (the 100-site evaluation, before and after fixes, and
the v5 pre-registered experiment); `round3-archive/audit-results/` (Sennheiser, Ritz);
`round3-archive/field_research_phase.md`; the Round 3 brief
(`adobe_problem_statement.md`); Round 4 screening (`demo-screening/`, 15 sites);
the four Round 4 rehearsal sessions and their transcripts; `round4/REPLAY_404Error.txt`
and the clean-install tests run on 2026-09-23.

**Status marks:** ✅ answered with evidence · ⚠️ answered, with a risk to manage ·
❌ gap: no evidence in the record

---

## §1 What Round 4 is

### "Round 4 asks you to show it works, live, and prove it is reproducible." ✅
- **Works, live:** four full-skill rehearsal sessions on 2026-09-23 (arduino.cc ×2,
  blender.org, ghost.org). All `complete`, 12/12 pages each, crawl 21–35 s.
- **Reproducible:** two separate live crawls of arduino.cc gave identical scripted
  findings, severities and order (22.1 s and 22.3 s). The two full agent runs gave
  identical scripted findings, coverage (12/12, 76 URLs), headline, counts and ranks
  1–5, and the agent layer found the same two problems in different words.
- In Round 3: 100-site run, 0 crashes, 100/100 schema-valid, every saved crawl
  replayed twice with identical output.

### "…your (unchanged) Round 3 submission and a small reproduction manifest so we can re-run your demo themselves and corroborate every finding." ✅
- Submitted zip: `submission/brand-ai-readiness-audit-FINAL.zip`, 184 KB,
  sha256 `22aa9491490fac0bef88c7f1767ac551a625ea78c081e42313fb1b230dc94f14`.
- Byte-identical to `brand-ai-readiness-audit-v4/` (checked with `diff -rq` several
  times, most recently 2026-09-23), and identical to the copy on GitHub (commit
  22b8122, extracted and compared).
- Manifest: `round4/REPLAY_404Error.txt` (six labeled fields).

### "You do not need to build a graphical user interface… The 'interface' is the agent interaction itself — not a web app." ✅
- Decision recorded: no GUI. The Round 3 local verification UI (`tools/audit_ui.py`,
  commit 80ea75c) was deliberately left out of the zip and archived.
- The interaction is the agent session: step 6 of `audit-orchestrator/SKILL.md`
  fixes the presentation order (headline → top three actions with evidence →
  what `latent` and `confirm_intent` mean → the Not-assessed list), and follow-up
  questions are answered from the report.

## §2 What you submit

### "A recorded video (≤ 5 minutes, hard cap)" / "REPLAY_YourTeamName.txt" ✅
- Team name 404 Error → `REPLAY_404Error.txt` (no space in the filename).
- Script: `round4/VIDEO_SCRIPT_v4.md`. Topic plan: `round4/TOPIC_PLAN.md`.

### "The live run in your video must exercise that same submitted marketplace; if the engine shown differs … the submission fails on integrity grounds." ✅
- The rehearsal folder was unzipped from the submitted zip. After four agent
  sessions with write access, it is still identical to v4 (excluding `WORK*`).
- Plan for filming: a fresh unzip, with `sha256sum` shown on camera.
- `brand-ai-readiness-audit-v4/` has not changed since 2026-09-13.

### "Judges will replay your demo on their own machine, including on a website they choose, not only the URLs you used." ⚠️
- What a judge-chosen URL will meet (100-site run, after fixes): 69 complete,
  13 partial, 14 failed, 4 blocked. **About 1 in 5 sites gives no substantive audit**,
  mostly bot-challenge or 403 pages. The tool reports these honestly
  (`run_status`, *"Site serves a bot-challenge page to automated clients"*)
  instead of inventing findings.
- Findings per readable site: median 4, p90 8, max 14. Runtime median 31 s, max
  139 s (hard cap 280 s in code, `bundle.py:63`).
- Round 4 screening hit the same pattern: of 15 candidate sites, 7 were blocked or
  failed (swiggy, zomato, meesho, archlinux, gutenberg, openlibrary, instructables,
  plus sonos and raspberrypi.com on bot challenges).

## §3 The video

### "Part 1 — methodology: ≤ 3 minutes / Part 2 — trial run: ≤ 2 minutes" ✅
- v4 script: Part 1 ≈ 2:54 at a normal pace, with a pre-decided cut order.
  Part 2 ≈ 1:58.

### "You may crop out the uninteresting parts… What you may not do is splice together a run that did not happen" ✅
- Measured session lengths (from transcripts): 5.9, 8.8, 2.8 and 2.7 minutes,
  including permission prompts. So Part 2 must be trimmed, never spliced.
- Rule in the script: a failed or partial crawl means a whole new take.

### Part 1 — "How you discovered the findings — the field research behind your signals: what separates websites that AI assistants cite well from ones they ignore or misrepresent" ❌ / ⚠️

**What the record shows (usable):**
1. **The mechanisms came from the Round 3 brief's appendix.** A: a page must be let
   in, read, and have its fact picked out, in that order. B: assistants pick sources
   they can easily reach, read and quote. C: facts assembled after load are
   invisible to simple readers. D: agreement across the web; mistaken identity
   when names are shared. These became the gate model: access → extractability →
   interpretability, then freshness and engagement.
2. **Desk research on how assistant fetchers work** (architecture_v2 §2.2, §3.1):
   - Assistant fetchers pass the raw page through a boilerplate-stripping text
     extractor (Readability/Trafilatura class) that discards `<script>`, `<style>`,
     nav and footer, so data in a hydration payload is in the bytes but not the text.
   - Bot documentation: GPTBot, ClaudeBot, CCBot, Google-Extended, Applebot-Extended
     and Bytespider are training-only. *"Google documents that blocking
     Google-Extended does not affect Search, and AI Overviews are served from the
     Googlebot index."* Only retrieval agents (OAI-SearchBot, ChatGPT-User,
     Claude-User, PerplexityBot, …) gate citation.
3. **An adversarial design review, 2026-09-01.** Architecture v1 went to a
   five-member council (web standards, systems engineering, detection science,
   adversarial grader, engagement measurement), in two rounds. It found five
   fatal flaws, each of which changed the design (see "Why the design is what it
   is" below).
4. **Testing on real sites (the field work that is on record):**
   - Sep 12, live checks on basecamp, djangoproject, ikea.com/de, nps.gov: all
     12/12 in 26–40 s; exposed hidden-control false positives on ikea and nps (fixed)
     and a www/apex crawl collapse (fixed).
   - Sep 12, agent-in-the-loop on in.sennheiser-hearing.com: the tool read
     "Article No. 700403 ₹3,990.00" as the price "700403 ₹" (fixed: currency-first
     and currency-last price tokens read separately). The agent found the About Us
     and Our Company pages naming **two different companies** as the business behind
     the store.
   - Sep 12, The Ritz London: the agent found the first sitemap URL redirects to the
     homepage. Checking candidate claims exposed two bugs: date patterns missed every
     ISO datetime, so correctly dated posts were called undated (**8 false findings on
     cry.org**), and engagement checks counted inert `<template>` content.
   - Sep 12, **100 sites, 100 distinct categories**, none used earlier in development.
     Every high and critical finding was checked against the saved pages:
     **29 of 49 correct (~59%)** before fixes. The false alarms became rules
     (see below). After the fixes, **18 false or overstated severe findings were
     removed**.
5. **The v5 pre-registered experiment**, Sep 13 (details under §6, determinism).
6. **Round 4:** 15 unseen sites screened; four full agent runs; 8 of 8 agent-added
   findings hand-checked true against the live sites.

**The gap (❌):** the brief asks what separates sites assistants *cite* from ones
they ignore. The record has **no observation of what an assistant actually cited**.
`field_research_phase.md` planned it (ask ChatGPT, Perplexity and Claude about 6–8
brands, note who got cited), and architecture_v2 §7 planned a half-day
"counterexample hunt" for Sep 8 ("can an assistant with web access state this
site's price correctly?"). The findings-log template is empty and no result file
exists. **Do not claim this research happened unless a teammate has the notes.**

### Part 1 — "…and how you distilled that into concrete, repeatable checks." ✅
- **43 scripted checks + the agent review**, in `SEVERITY_TABLE` (`model.py:38`).
  Across the 100-site run, 40 of the 43 fired at least once (never:
  `A8_robots_token_unrecognised`, `C6_entity_name_conflict`,
  `D4_internal_contradiction`). Full inventory in the appendix.
- **The distilling rules** (architecture_v2):
  - *Fact-level, not volume-level:* the flagship check grades each expected fact by
    where it sits in the raw response: T0 visible prose (pass), T1 structured data
    (pass), T2 only inside a script payload (medium), T3 absent (high)
    (`extraction-tiers.md`). Payload islands parsed first: `__NEXT_DATA__`, `__NUXT__`,
    `__APOLLO_STATE__`, `window.__INITIAL…`, `self.__next_f`, any
    `<script type="application/json">` (`bundle.py:322`). *"A naive competitor
    shipping 'SPA therefore invisible' will false-positive across the entire Next.js
    and Nuxt web."*
  - *Where expected facts come from, and why it isn't circular:* declared literals
    (what the site asserts in JSON-LD, meta tags, payloads) **plus** role obligations
    (a page titled or linked as "Pricing" commits to a price; "Contact" to a contact
    method).
  - *Thresholds by mechanism, never by percentile:* *"a threshold at the 20th
    percentile flags 20% of sites by construction, regardless of whether any has a
    real problem."*
  - *Every false alarm became a rule* (100-site fixes): price obligations need
    commerce evidence; contact obligations only on the contact page itself;
    bot-challenge pages detected (Incapsula, Cloudflare, Akamai, PerimeterX, DataDome
    markers; a vendor marker counts only on a page under 60 words, found via a false
    hit on glastonburyfestivals.co.uk); noindex is critical only on key pages or most
    of the crawl, otherwise a question for the owner.
  - *Engagement kept to what static HTML can prove:* v1 had ~20 engagement
    heuristics; the council cut them because consent banners are legally required,
    above-fold word count fires on Apple and Stripe, English verb lists fail on other
    languages, and one synthetic load is not a Core Web Vitals measurement. v2 kept
    ~10 statically evidenced checks, capped at medium.

### Part 1 — "How you assigned severities — the logic that decides how much each problem hurts discoverability or engagement." ✅
The complete logic (`model.py`, `severity-rationale.md`):

1. **Base level from where the chain breaks, justified by mechanism** (*"never by how
   common the defect is"*):
   - **critical:** the AI can't get in or the page leaves the index:
     `A1_retrieval_agent_blocked` (*"Retrieval agents gate citation; nothing
     downstream can matter"*), `A3_noindex`, `A7_site_unreadable` (*"must never read
     as 'no findings'"*)
   - **high:** it gets in but can't use the page or fact: `B1_fact_absent`,
     `B4_empty_shell`, `A2_snippet_suppressed` (indexed but unquotable),
     `C1_structured_data_invalid` (*"silently discarded, and nobody notices"*),
     `C2`/`D4` contradictions, `A9_key_page_broken`
   - **medium:** the fact is reachable but hard or ambiguous: `B1_fact_script_only`,
     `C3_entity_unanchored`, `C7_title_problem`, `C1_product_markup_absent`,
     `D1_no_date_signals`, broken non-key pages; engagement risk factors
     (E1, E3, E4, E7, E9, E10, E11)
   - **low:** real but minor: `A6_sitemap_missing` (*"discovery still works through
     links"*), `A4_redirect_chain`, `D3_content_stale` (*"age is a prompt to review,
     not proof the page is wrong"*), `D2_stale_copyright`, E2, E5, E6, E12
2. **× spread (blast radius):** site-wide 1.0, template 0.8, single page 0.5.
   Below 0.7 demotes one level. Not applied when fewer than 3 pages were read
   (`COVERAGE_FLOOR = 3`), *"so a Cloudflare 403 after page three cannot produce '12
   of 12 pages affected'."*
3. **Caps:** rule-of-thumb checks (`static_heuristic`) max medium; heuristic
   confidence can't reach critical; **latent** (behind a total access block) max low;
   **confirm_intent** (looks deliberate) max low; agent claims max low.
4. **Hurts label:** every finding is tagged `ai_discoverability`, `user_retention` or
   `both` (`hurts_for`, `model.py:106`). arduino.cc: 5 / 4 / 1.
5. **Printed arithmetic:** every finding carries `severity_rationale`. Examples from
   arduino.cc:
   - `base=high (extractability/B1_fact_absent); blast=template x0.8 => high`
   - `base=medium (engagement/E1_unlabelled_input); blast=single_page x0.5; -> demoted to low => low`
   - `base=high (…B1_fact_absent); blast=template x0.8; cap(confirm_intent)-> low => low`
   - `base=medium (proposed by agent review…); blast=template x0.8; cap(agent_review)-> low => low`
6. **Why a table and not a formula** (architecture_v2 §5): v1's
   `severity = f(gate, blast, confidence)` *"collapses to table[check_type] ×
   blast_radius"*, because gate and confidence are constants per check. *"A judge can
   read a table."*
7. **Why latent, not suppressed** (§5.1): suppression *"creates a second-audit trap:
   the user fixes robots.txt, re-audits, and meets a wave of findings they were never
   warned about"*; and robots.txt is per-agent, so a page closed to OAI-SearchBot may
   be open to Claude-User.

### Part 1 — "How you derived the suggested actions — why each fix is mechanism-sound…" ✅
- Each check writes its own fix in its own script, so detection and advice can't
  drift apart. Every fix has `summary`, `how[]` steps, `effort`, and a **`verify`**
  step. F-001 on arduino.cc:
  - summary: *"Render the phone/email into server-side HTML text on these pages."*
  - how: emit it as plain text in the server response; if it loads from an API,
    server-render a default and hydrate over it; also express it in structured data
    (`LocalBusiness`/`ContactPoint`)
  - verify: *"curl -s <url> | grep -i '<phone/email value>' returns a match with
    JavaScript disabled."*
- **Site-specific steps from the agent are only merged if they quote text that is
  really on that page** (`verify_claims.py:350`). Both arduino.cc runs grounded the
  F-002 fix on the live homepage line *"Arduino is now a Qualcomm company"* and
  suggested `parentOrganization` naming Qualcomm.
- **Proactive recommendations appear only when the site doesn't already do them**,
  each with its reason; the rest go to `already_in_place[]` with evidence. arduino.cc:
  2 proactive, 5 already in place (e.g. *"/llms.txt is present"*).

### Part 1 — "…and how you prioritized them." ✅
- `rank()` and `priority_score()` in `audit.py:443`: severity level sorts first;
  within a level, **score = severity weight × confidence × status ÷ effort**.
  - severity weights: critical 5, high 4, medium 3, low 2, info 1
  - confidence: 1.0 for a measured fact, 0.7 for a heuristic
  - status: active 1.0, confirm_intent 0.5, latent 0.35
  - effort: low 1.0, medium 1.6, high 2.4
  - an agent claim's effort is forced to medium: *"ranking must not reward a claim
    for calling itself easy"*
- Worked example (arduino.cc): F-001 = 4 × 1.0 × 1.0 ÷ 1.6 = **2.5**; F-002 =
  3 × 1.0 × 1.0 ÷ 1.0 = **3.0**. F-002 scores higher but ranks second, because high
  sorts before medium.
- `prioritized_actions[]` ranks **every** finding (arduino.cc: ranks 1–11).

### Part 1 — "Anchor every claim to your code… Narration that cannot be traced to the submitted code earns no credit" ✅
- Every file and line used in the script was checked against v4:
  `model.py:38` SEVERITY_TABLE, `:95` AGENT_REVIEW_CEILING, `:106` hurts_for,
  `:112` BLAST, `:140` finalise; `audit.py:52–53` weights, `:355` duplicate drop,
  `:392` mark_latent, `:443` priority_score, `:464` checks_skipped; `bundle.py:22` and
  `:634` deterministic frontier, `:60` user agent, `:63` TOTAL_BUDGET_S, `:322/341`
  payload islands, `:332` derive, `:416` bot_challenge; `verify_claims.py:173, 204,
  222, 302, 309, 350`.
- **Not in the submitted code** (so earns nothing on its own): architecture_v2, the
  council review, the 100-site run, the v5 experiment. Use them only as the *why*
  behind something that *is* in the code.

### Part 2 — "…against a site the audit has never seen" ⚠️
- arduino.cc was never used in developing or tuning the engine: the engine was
  frozen on 2026-09-13 and arduino.cc was first crawled on 2026-09-22.
- But it was rehearsed three times. **Say "a site we never used while building it",
  not "never seen".**

### Part 2 — "Enter the URL on camera… Interaction, not a pre-rendered static report." ✅
- The script types the URL by hand; the prompt is identical to the manifest's.

### Part 2 — "…show the agent … invoking your entrypoint skill, fetching, reasoning, and producing findings." ✅
- Observed tool sequence in rehearsal: read `skills/audit-orchestrator/SKILL.md` →
  `audit.py https://www.arduino.cc/ --max-pages 12 --bundle WORK/bundle.json -o
  WORK/report.json` → inspect report and bundle → read the skills' "Interpreting
  results" → `page_profile.py` → write `WORK/claims.json` → `audit.py --replay …
  --agent-claims …` → presentation. The agent chose `--max-pages 12` itself, from
  SKILL.md.

### Part 2 — "Drill into the findings — … real evidence … its severity, and the suggested fix." ✅ / ⚠️
- F-001 (arduino.cc contact page, high): 0 `mailto:`, 0 `tel:`, 0 email-shaped
  tokens in 223,797 bytes; 0 words of extractable text; the server HTML is a Gatsby
  "Loading..." spinner (the agent found this in both runs).
- It matches the brief's own examples: "facts locked" (T3, fact absent from the raw
  response) and "missing JSON-LD" (C3, no Organization/sameAs).
- ⚠️ The brief's first example, "raw-HTML-vs-rendered-DOM diff", is exactly what the
  design **replaced**, on purpose: Chromium is 379 MB against a 50 MB cap
  (architecture_v2 §2.1), and *"the rendered DOM was never the measurement — it was
  only a fact source."* Tiering answers the same question with one HTTP request and
  no nondeterminism. Be ready to say this if asked.
- ⚠️ F-001's printed `Reproduce:` regex matches asset hashes and SVG path numbers, so
  it prints noise even though the finding is right. Show `grep -cE 'mailto:|tel:'` → 0.

### Part 2 — "Show that fixes can be sorted/prioritized by impact." ✅
- `prioritized_actions[]` ranks all 11; the weights are above.

### Part 2 — "State your harness and model on camera" ✅
- Read from all four rehearsal transcripts: **Claude Opus 5.5 (`claude-opus-5-5`),
  effort medium, Claude Code 2.1.280.**
- ⚠️ `/model` now saves effort **high** as the default. Set it back to medium before
  filming, or re-rehearse at high and change the manifest.

### Part 2 — "One line on wiring" ✅
- The script's line: "It's reading our submitted entrypoint and running its script."

### "Everything shown must come from the submitted engine, running live, so that a judge re-running the same steps reaches the same substance." ✅
- Same substance, measured: the scripted layer is identical across runs; the agent
  layer found the same two problems in both arduino.cc runs, in different words.

## §4 Harness and model

### "LLM model — name and version/date" / "Agent harness — name and version" ✅
- `LLM_MODEL: Claude Opus 5.5 (claude-opus-5-5), effort level: medium`
- `AGENT_HARNESS: Claude Code 2.1.280, interactive CLI session (not headless)`

### "Exact invoke command(s) — … from a clean checkout through to the emitted report." ✅
- Tested 2026-09-23 from a clean unzip in a fresh venv, with pinned versions:
  install OK, **398/398 offline tests pass in ~18 s**, fallback command exit 0.
- An unpinned install today resolves **beautifulsoup4 4.15.0**, not the 4.13.5 we
  ran, so the manifest pins the whole dependency set.
- ⚠️ Not yet tested: that `claude` started inside the venv uses the venv's python.
  The manifest has a recovery line. Neel's clean run will confirm.

### "If you use a closed or paid harness … document a fallback run path." ✅
- No-LLM fallback in the manifest:
  `python3 skills/audit-orchestrator/scripts/audit.py https://www.arduino.cc/ --max-pages 12 --bundle WORK/bundle.json -o WORK/report.json`
  → tested: same 9 scripted findings as the rehearsal, `agent_review.status: "not_run"`.
- Provider-neutral by design: the invoke is a plain prompt that names the SKILL.md
  file, not a Claude-Code-only mechanism, so any harness that can read files and
  run Python can follow it.

### "Judge corroboration weighs substance … not exact string-for-string output" ✅
- Direct evidence: the two arduino.cc agent layers, side by side:
  - *"Three section pages reuse the homepage's og:title 'Arduino - Home'…"* ↔
    *"3 section pages reuse the homepage's og:title and meta description"*
  - *"UNO Q and VENTUNO Q product pages mark up only an FAQ, with no Product
    entity"* ↔ *"Both product pages are typed only as FAQPage, with no Product node"*

## §5 The manifest

### Fields, "Mandatory and parseable" ✅
- Exactly six top-level labels, checked by script.

### "Test site URLs must be exact, full URLs… Judges will also run a URL of their own choosing" ✅
- `https://www.arduino.cc/, https://ghost.org/, https://www.blender.org/`, each
  run end to end with the full skill and hand-verified.
- obsidian.md was **rejected**: its only high finding (`A2_snippet_suppressed`)
  was a false positive. Both `data-nosnippet` attributes sit on decorative UI mockups
  marked `aria-hidden="true"`. This is the same class as framer in the 100-site run,
  so it's a known weak check.

### "Test steps must be copy-pasteable, in order, reproducible from a clean checkout" ⚠️
- Every command was taken from a real run. The manifest's full walk-through (Neel,
  on a clean machine, without asking anyone) has **not happened yet**.

### "Consistency with the video… A mismatch is an integrity failure." ✅
- The prompt in the script is identical, character for character, to the
  manifest's; the model, effort and harness match.
- The finding count matches: the manifest explains that the agent's "10 findings"
  is 11 total minus 1 `confirm_intent`.

## §6 Judging

### Reasoning (35): "sound, non-obvious, and traceable to the submitted code" ✅
Non-obvious points on record, each traceable:
- training bots vs answer bots (`bot-taxonomy.md`)
- facts graded by where they live; payload islands parsed first
  (`extraction-tiers.md`, `bundle.py:322`)
- thresholds by mechanism, never by percentile (`severity-rationale.md`)
- latent instead of suppressed (`audit.py:392`, `severity-rationale.md`)
- agent claims can't call themselves easy (`audit.py:443`)
- agent fixes must quote real page text (`verify_claims.py:350`)
- evidence that's "true of every page" is rejected (`verify_claims.py:204`)

### Live behaviour (35): "real, evidence-backed findings — few misses, few false positives" ⚠️
- **Agent layer:** 8 of 8 agent-added findings across three sites checked true by
  hand against the live sites. Two live rejections by the verifier in arduino.cc run
  2: a claim that duplicated `B1_fact_absent`, and a fix quoting `'Loading...'`,
  which exists only in an `aria-label` and was rejected because retrievers don't
  read attributes. **That was not a hallucination; don't call it one.**
- **Scripted layer:** after the Round 3 fixes, a hand check of the 33 non-A1 severe
  findings on 100 sites: 9 true, 9 true only from our machine (IP-level blocks),
  4 uncertain, 11 false or overstated, so **27–55% precision on severe findings**.
  The main failure: network failures and IP blocks reported as site defects.
  **Don't volunteer this figure; answer straight if asked.**
- **Misses:** never measured. No labelled ground truth exists.

### Reproducibility, quality & hygiene (30) ✅
- Deterministic analysis: saved crawl, `--replay`; deterministic crawl order
  (sitemap order, then lexicographic BFS, `bundle.py:22`); stable sorts; severity uses
  banded values only (*"banded, so the ordering is stable across machines"*).
- The honest claim, from architecture_v2 §6.1: *"the analysis layer is
  deterministic given fixed inputs; network observation is not."*
- Evidence: 100/100 double replays identical; two live arduino.cc crawls identical.
- Hard runtime cap: 280 s total, 200 s crawl, 30 s sitemap walk.
- 398 offline tests: RFC 9309 robots conformance, extraction tiers, JSON-LD
  normalisation, severity-table integrity, crawler safety against a fake HTTP
  client, reviewers' adversarial claim files, end-to-end fixture replays.

### Gate: "Integrity floor" ✅ (with rules to keep)
- Engine unchanged; no splicing; manifest matches video.
- Claims to avoid, found during this review: "never tuned on" the 100 sites (false,
  we fixed bugs on them); "never seen" arduino.cc; "caught a hallucination" for the
  `'Loading...'` rejection; any overall accuracy figure.

### Gate: "Unverified floor (ran-blocked)" ⚠️
- The fallback path works without any LLM. The one open item is Neel's clean
  walk-through of the manifest.

### Gate: "Nondeterminism flag" ✅
- The scripted layer can't differ for a fixed crawl. The agent layer varies in
  wording and by ±1 claim, and is capped at low, so it can't move the headline or
  the top of the ranking.
- Live-site drift: if arduino.cc fixes a finding before judges replay, it will
  differ. The manifest says so and dates the observations.

## §7 Scope and guardrails

### "Recommend-only… read-only. Respect robots.txt." ✅
- GET only; robots.txt parsed to RFC 9309 per user agent; truthful user agent
  `AIReadinessAudit/1.0 (+https://github.com/kavyan256/adobe-group)`; at least 1 s
  between requests; Crawl-delay honoured up to 2 s (beyond that the page budget
  shrinks); stops at the first 429, and at a 503 on the start URL or two in a row.
- Why a truthful user agent (architecture_v2 §6.3): v1 tested with `User-Agent:
  GPTBot`, which is impersonation and *"binds you to that agent's robots group"*.

### "Same engine as Round 3." ✅ (see §2)
### "AI assistance allowed" ✅ — the engine and the review were built with Claude Code.
### "No GUI required." ✅ (see §1)

---

## Why the design is what it is: decisions on record (architecture_v2, 2026-09-01)

| v1 | v2 onward | Reason on record |
|---|---|---|
| Playwright headless browser | No browser; HTTP + parse | Chromium 379 MB (headless shell 273 MB) vs a 50 MB cap; runtime download breaks "self-contained" |
| Raw-HTML vs rendered-DOM diff | Extraction tiering T0–T3 | Needed the browser; the rendered DOM was only a fact source |
| Flat list of 8 AI bots → "you are invisible" | Training vs retrieval taxonomy | 6 of the 8 were training-only: a guaranteed false positive on publishers who block training on purpose |
| Severity by formula | An auditable table + printed arithmetic | The formula collapsed to a table; "a judge can read a table" |
| Downstream findings suppressed when blocked | `latent`, capped at low | Second-audit trap; robots.txt is per agent |
| ~20 engagement heuristics | ~10 static, capped at medium | Consent banners legal; Apple/Stripe fire above-fold; English-only verbs; synthetic CWV isn't CWV |
| Determinism asserted absolutely | Qualified and made true | A/B tests, banners, CDN variance, float timings break it; drop the browser, sort everything, band every number, add `--replay` |
| Survey used to set thresholds | Thresholds by mechanism only | Percentile thresholds flag a fixed share by construction |

**Evolution of the agent's role:** v2 said *"Deterministic scripts detect; the agent
narrates and never judges"* (endorsed by all five critics). v3 (Sep 12) added
agent review with verified claims. v4 capped them at low and hardened the verifier.
v5 (Sep 13) let the agent judge scripted findings, and was rejected.

**The v5 pre-registered test** (criteria written before any agent ran; 39 dev
findings, 18 blind held-out, negative controls):
- ✗ Catch ≥ 7 of 10 known false alarms → **6** (failed by one)
- ✓ Remove 0 true findings → 0 removed, 0 reduced
- ✓ Unknowable A7 blocks: ≤ 1 removed → 0
- ✗ Held-out match ≥ 80% → not measurable (most runs produced no output on the
  account's spend limit)
- ✗ Stability ≥ 85% → not measurable, same reason
- ✓ Verifier: 52 of 53 verdicts applied correctly; negative control rejected
- ✗ Runtime: median ≤ 180 s and max ≤ 240 s → median 71–110 s, **max 367 s**
- Later measurements after adding per-item checkpoints: 268 s (mistral) and 302 s
  (msf) for the agent step alone.

**So the accurate Part 1 line is "it failed our own pre-registered test: it caught
6 of 10 known false alarms where we'd required 7, and its slowest run took over six
minutes."** "Its answers changed between runs" is **not** backed by a measurement.

## Numbers cheat-sheet

| Fact | Value | Source |
|---|---|---|
| Scripted checks | 43 (+ agent review) | `SEVERITY_TABLE` |
| Fired at least once on 100 sites | 40 of 43 | 100-site reports |
| 100-site robustness | 0 crashes, 100/100 schema-valid, double replays identical | EVALUATION.md, COMPARISON.md |
| 100-site status after fixes | 69 complete, 13 partial, 14 failed, 4 blocked | COMPARISON.md |
| Runtime on 100 sites | median 31 s, max 139 s | COMPARISON.md |
| Severe precision before fixes | 29 of 49 (~59%) | EVALUATION.md |
| False severe removed by fixes | 18 | COMPARISON.md |
| Severe precision after fixes (hand-checked) | 27–55% | COMPARISON.md |
| Agent claims hand-checked, Round 4 | 8 of 8 true | 2026-09-23 checks |
| Tests | 398 passed, 0 failed | `tests/run_tests.py` |
| Zip | 184 KB; sha256 22aa94…4f14 | `submission/` |
| Crawl cap | 280 s total, 200 s crawl, 30 s sitemaps | `bundle.py:62–66` |
| arduino.cc full run | 11 findings: 1 high, 3 medium, 7 low; 21–31 s crawl | rehearsal reports |
| Session length incl. approvals | 2.7–8.8 min | transcripts |

## Open questions only the team can answer

1. Did anyone run the planned assistant-citation checks (late August, or the Sep 8
   counterexample hunt)? If yes, where are the notes? This is the one ❌ in the brief.
2. `round3-archive/compare_result_v1.0.txt` holds audits of stripe.com, wikipedia,
   react.dev, Hacker News and amazon.in from 2026-09-10, in a different format from
   ours (e.g. "text-to-HTML ratio under 4%"). Whose tool was that? If it was our v1,
   it's a useful before-and-after.

---

## Appendix: check inventory
| check | gate | base | mechanism | sites fired on | fix (from a real report) | verify |
|---|---|---|---|---|---|---|
| A1_retrieval_agent_blocked | access | critical | A | 9 | Allow retrieval agents even if you continue to block training crawlers. | Re-run this audit; A1 should no longer fire for retrieval agents. |
| A2_snippet_suppressed | access | high | B | 2 | Allow snippets on pages you want quoted. | Page source contains no nosnippet and no data-nosnippet around primary content. |
| A3_noindex | access | critical | A | 3 | Remove noindex from pages that should be findable. | curl -sI <url> | grep -i x-robots-tag  returns nothing, and the page source contains no no |
| A3_noindex_utility | access | medium | A | 4 | Confirm these exclusions are deliberate; remove noindex from any page you do want assistants to find. | curl -sI <url> | grep -i x-robots-tag  returns nothing, and the page source contains no no |
| A4_redirect_chain | access | low | A | 2 | Collapse redirect chains to a single hop. | curl -sIL <url> shows at most one 3xx before the 200. |
| A5_canonical_missing | access | low | A | 8 | Give every indexable page a self-referencing canonical URL. | Each page's canonical resolves to itself with HTTP 200. |
| A5_canonical_problem | access | medium | A | 1 | Point each page's canonical at itself unless another URL really should receive its credit. | Each page's canonical resolves to itself with HTTP 200. |
| A6_sitemap_missing | access | low | A | 20 | Publish an XML sitemap and reference it from robots.txt. | curl -s https://<host>/sitemap.xml | grep -c '<loc>' returns > 0. |
| A7_site_unreadable | access | critical | A | 26 | Make the site reachable by non-browser clients before anything else. | curl -sI <url> returns 200 and curl -s <url> returns HTML containing your main heading. |
| A8_robots_token_unrecognised | access | medium | A | 0 | — | — |
| A9_broken_pages | access | medium | A | 7 | Fix or redirect the broken URLs, and drop them from the sitemap if they are gone for good. | curl -sI <url> returns 200 or a single 301 to a 200 page. |
| A9_key_page_broken | access | high | A | 1 | Restore or redirect the broken key page(s) first, then the rest. | curl -sI <url> returns 200 or a single 301 to a 200 page. |
| A10_meta_refresh | access | low | A | 1 | Replace meta refresh with an HTTP 301/302 redirect. | curl -sI <url> shows a 3xx with a Location header, and the page source has no http-equiv=r |
| A11_soft_404 | access | medium | A | 2 | Return a real 404 (or 410) status for pages that do not exist. | curl -sI <url> returns 404 or 410 for a missing page. |
| B1_fact_absent | extractability | high | C | 8 | Render the phone/email into server-side HTML text on these pages. | curl -s <url> | grep -i '<phone/email value>' returns a match with JavaScript disabled. |
| B1_fact_script_only | extractability | medium | C | 3 | Promote these facts from the hydration payload into server-rendered text. | The value appears in the output of a text-extraction tool (e.g. `python -c "import trafila |
| B4_empty_shell | extractability | high | C | 5 | Server-render the primary content of these pages. | curl -s <url> | wc -w shows substantive content with no JS executed. |
| B6_filler_heavy | extractability | low | F | 8 | Raise the share of each page that is unique to that page. | Two different pages, run through a readability extractor, no longer share most of their se |
| C1_product_markup_absent | interpretability | medium | C | 7 | Add Product JSON-LD with an Offer to each product page. | A schema.org validator reports a Product with an Offer and no errors. |
| C1_structured_data_absent | interpretability | low | C | 56 | Add schema.org JSON-LD appropriate to each page type. | A schema.org validator reports a detected item type with no errors. |
| C1_structured_data_invalid | interpretability | high | C | 2 | Fix the JSON syntax in the structured-data blocks. | python -c 'import json,sys;json.load(sys.stdin)' succeeds for each block. |
| C2_markup_text_contradiction | interpretability | high | D | 2 | Make the marked-up price and the displayed price agree. | The price string in JSON-LD appears verbatim in the rendered text. |
| C3_entity_unanchored | interpretability | medium | D | 56 | Publish Organization JSON-LD with sameAs links to authoritative profiles. | Rich Results Test shows Organization with a populated sameAs array. |
| C5_faq_content_unmarked | interpretability | low | B | 14 | Pair each question heading with one self-contained answer, and say so in FAQPage JSON-LD. | Each question heading is followed by an answer that makes sense with the rest of the page  |
| C6_entity_name_conflict | interpretability | medium | D | 0 | — | — |
| C7_title_problem | interpretability | medium | B | 14 | Give every page a unique title that names its subject. | curl -s <url> | grep -o '<title>[^<]*' differs across pages and is never empty. |
| D1_no_date_signals | freshness | medium | D | 3 | Publish explicit datePublished and dateModified. | Rich Results Test shows both date properties populated. |
| D2_stale_copyright | freshness | low | D | 4 | Render the copyright year dynamically. | The footer shows the current year. |
| D3_content_stale | freshness | low | D | 2 | Review whether each page is still accurate; update dateModified if it is, or mark it archived if it is not. | Each listed page carries a dateModified from the review, or an archived notice. |
| D4_internal_contradiction | freshness | high | D | 0 | — | — |
| E1_form_friction | engagement | medium | on-site | 4 | Ask for less up front on contact, demo, signup and checkout forms. | No conversion form asks for more than five required fields, or more than eight fields in t |
| E1_unlabelled_input | engagement | medium | on-site | 19 | Label every form field programmatically. | Every input, select and textarea resolves to a non-empty accessible name without relying o |
| E2_vague_link_text | engagement | low | on-site | 2 | Make link text describe its destination. | Link text read out of context still identifies the destination. |
| E3_unnamed_controls | engagement | medium | on-site | 39 | Give every control a name a machine can read. | Every button/link resolves to a non-empty accessible name. |
| E4_images_missing_alt | engagement | medium | C | 15 | Add alt text to content images; use alt="" for decorative ones. | No content <img> lacks an alt attribute entirely. |
| E5_no_lang | engagement | low | on-site | 12 | Declare the page language. | Every page's <html> element carries a lang attribute. |
| E6_heading_structure | engagement | low | on-site | 40 | Give each page one h1 that states its subject. | Each page has an h1 and its text matches the page's subject. |
| E7_zoom_disabled | engagement | medium | on-site | 7 | Allow users to zoom. | Pinch-zoom works on an Android phone; the viewport tag sets no user-scalable=no and no max |
| E9_promise_payoff_mismatch | engagement | medium | B | 1 | Make the page deliver what its title and description promise. | The first paragraph restates the title's subject in plain words. |
| E10_no_next_step | engagement | medium | on-site | 10 | Give each substantial page at least one relevant next step in the content itself. | Each page over 200 words contains at least one in-content link, form or contact route. |
| E11_no_viewport | engagement | medium | on-site | 7 | Add a viewport meta tag to every page template. | On a phone, the page text is readable without zooming and no horizontal scrollbar appears. |
| E12_no_orientation | engagement | low | on-site | 5 | Give every deep page a title and h1 that name its own subject. | Each deep page's title and h1 differ from the homepage's and name the page. |
| R_agent_review | review | low | review | 3 | Give each section page its own og:title and meta description instead of the homepage defaults. | curl -s https://www.arduino.cc/hardware | grep og:title no longer shows 'Arduino - Home'. |
| X1_low_quotability | interpretability | low | B | 6 | Rewrite key passages so each stands alone as a citable claim. | Read any key paragraph in isolation - the subject is unambiguous. |
