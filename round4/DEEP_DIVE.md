# Deep dive: the six things the brief asks for, and the three things it scores

Scope: only the three Part 1 points, the three Part 2 points, and the three
rubric criteria (the screenshots of 2026-09-24). Every claim below was checked
against the shipped engine (`brand-ai-readiness-audit-v4/`, identical to the
submitted zip) or a measured run. File and line numbers are for the recorder and
the judges; they are not for speaking aloud.

---

## What the scoring words mean in practice

| Word in the brief | What a judge will test |
|---|---|
| **sound** | Is the reasoning correct about how assistants and crawlers actually work? |
| **non-obvious** | Would a competent team have done this by default? If yes, it earns little. |
| **traceable** | Can the judge open a file in the submission and find it? If not, *"earns no credit"*. |
| **real, evidence-backed** | Does each finding name the URL and the exact string or field that proves it? |
| **few misses / few false positives** | On the demo site *and on a URL the judge picks*. |
| **correct, specific, mechanism-sound, prioritized** | Of the findings *and the actions*, on the judge's URL. |
| **deterministic** | Replay gives the same result. |

---

# PART 1

## P1.1 "How you discovered the findings — the field research behind your signals: what separates websites that AI assistants cite well from ones they ignore or misrepresent, and how you distilled that into concrete, repeatable checks."

This bullet asks two different things: **(a)** what separates cited sites from
ignored ones, and **(b)** how that became checks.

### What we can honestly show

The record has three kinds of research, and one kind missing:

| Kind | On record? | What it produced |
|---|---|---|
| Desk research on how assistant fetchers work | ✅ architecture_v2 §2.2, §3.1 | fetchers strip `<script>`, nav and footer before the model reads; training bots ≠ retrieval bots |
| An adversarial design review (5 critics, 2 rounds, 2026-09-01) | ✅ architecture_v2 | five fatal flaws in v1, each changing a check |
| Field testing on real sites, every serious finding checked by hand | ✅ EVALUATION.md, COMPARISON.md, CLAUDE.md | each false alarm became a rule, written into the code |
| **Observing what assistants actually cite** | ❌ planned (field_research_phase.md; architecture_v2 §7 "counterexample hunt"), never recorded | — |

So for (a), the honest answer is the **mechanism**: what the assistant's fetcher
can get in to, read, and pick a fact out of. We learned that from how the fetchers
are built, and it was confirmed on real sites. We can't say "we watched ChatGPT cite
X and ignore Y" unless a teammate has those notes.

### The discoveries, ranked by how non-obvious they are

Each one: the obvious approach → why it's wrong → what we do → how we found out →
where it lives.

**1. Present in the page bytes is not present to the assistant.** *Most
non-obvious; the flagship.*
- Obvious approach: "it's a JavaScript app, so it's invisible", or render it with a
  headless browser and compare.
- Why that's wrong: many JavaScript sites (Next.js, Nuxt) embed their data in the
  HTML as a JSON blob. Calling them invisible is a false positive *"across the
  entire Next.js and Nuxt web"*. And the browser can't ship: Chromium is **379 MB**
  against a 50 MB cap.
- What we do: grade each expected fact by where it sits in the raw response. T0
  visible text: pass. T1 structured data: pass. **T2 only inside a script blob:
  medium** (the bytes are there, but a text extractor throws them away). **T3
  absent: high.** We parse the blobs first (`__NEXT_DATA__`, `__NUXT__`,
  `__APOLLO_STATE__`, `self.__next_f`, `window.__INITIAL…`, JSON scripts).
- Found through: the design review. *"The rendered DOM was never the measurement —
  it was only a fact source."*
- Where: `fact-extractability-audit/references/extraction-tiers.md`;
  `audit-orchestrator/scripts/bundle.py:322` (payload patterns), `:332` `derive()`.

**2. Blocking training is not blocking citation.**
- Obvious: "you block GPTBot, so ChatGPT can't see you."
- Wrong because: GPTBot, ClaudeBot, CCBot, Google-Extended, Applebot-Extended and
  Bytespider only gate training. v1's list had 6 of 8 like that, which would have
  flagged every publisher who blocks training on purpose.
- What we do: only blocks on retrieval agents (OAI-SearchBot, ChatGPT-User,
  Claude-User, PerplexityBot, Googlebot, Bingbot, …) produce a finding, and robots.txt
  is read per agent (RFC 9309).
- Found through: vendor documentation, plus the design review.
- Where: `crawl-access-audit/references/bot-taxonomy.md`;
  `audit-orchestrator/scripts/robots.py`.

**3. A page owes a fact because of what it's *for*, not its URL.**
- Obvious: `/products/...` must show a price; `/contact` must show a phone number.
- Wrong because: in the 100-site run this produced **11 false high findings**:
  `/products/` on SaaS and pharma sites, a `/plan` feature page, a `/buy` hub,
  `/subscribe` newsletter pages, a contact *directory*.
- What we do: a price is owed only with commerce evidence on the page itself
  (Product/Offer markup, an add-to-cart form, `og:type product`, pricing words in
  the title or h1). Contact details are owed only on the contact page itself, and
  **phone *or* email is enough**, because *"requiring both would fire on the large
  number of businesses that deliberately offer only one channel."* Role words are
  matched in eight languages (pricing/preise/tarifs/precios/prezzi/prijzen,
  contact/kontakt/contatto/contacto…).
- Found through: field testing. **The code comment cites the evaluation itself.**
- Where: `fact-extractability-audit/scripts/check_extractability.py:126–149`
  (`ROLE_OBLIGATIONS`, `_commerce_evidence`).

**4. An HTTP 200 page can be a bot wall.**
- Obvious: status 200 means you got the page.
- Wrong because: boots.com and nypl.org returned "Pardon Our Interruption"
  Incapsula pages *with HTTP 200 and a noindex tag*. v4 read them as the real
  homepage and reported a **critical noindex**. Then the first fix overreached:
  glastonburyfestivals.co.uk's real homepage loads the Incapsula script and was
  misread as a challenge.
- What we do: detect challenge pages by vendor marker (Incapsula, Cloudflare,
  Akamai, PerimeterX, DataDome), but a marker counts only on a page with under 60
  words. Report *"Site serves a bot-challenge page to automated clients"* instead of
  auditing the challenge page.
- Found through: field testing, in two rounds.
- Where: `audit-orchestrator/scripts/bundle.py:416` `bot_challenge()`.

**5. Deliberate is not defective.**
- Obvious: noindex on any page is a critical problem.
- Wrong because: in the 100-site run, 7 of 9 critical noindex findings were
  deliberate: user profiles, tribunal decisions, reward pages, pagination.
- What we do: noindex is critical only on key pages (home, pricing, product,
  about, contact) or most of the crawl. Otherwise it's `confirm_intent`: a question
  for the owner, capped at low.
- Where: `crawl-access-audit/references/deliberate-vs-defect.md`.

**6. Where expected facts come from, without circular logic.**
- Obvious: check the facts the site declares in structured data.
- Wrong because: that makes the check *"strongest on the sites that need it
  least"*. A site with no structured data would never be expected to show anything.
- What we do: two independent sources. Declared literals (what the site asserts
  anywhere: JSON-LD, meta tags, payloads) **plus** role obligations (what the page
  commits to by being a pricing or contact page).
- Where: `extraction-tiers.md` ("Where expectations come from").

**7. A short visit from an AI answer can be a success.**
- Obvious: measure bounce rate or dwell time.
- Wrong because: the assistant already summarised the answer, so the click is
  usually verification, and *"a 15-second exit is a win"*. Bounce is also not
  observable from a crawl.
- What we do: engagement checks measure only what the markup can prove (unlabelled
  forms, nameless buttons, zoom disabled, no viewport, no next step), capped at
  medium. Behaviour metrics are declared as not assessed.
- Where: `engagement-audit/references/engagement-checks.md`; the
  `E_behaviour_metrics` entry in every report's `checks_skipped[]`.

### How it was distilled into concrete, repeatable checks

The loop, which is the real answer to the second half of the bullet:

> mechanism → a check with a threshold named by its mechanism → run on real sites →
> every serious finding checked by hand against the raw page → each false alarm
> becomes a rule in the code → run again

- **Thresholds by mechanism, never by percentile.** *"A threshold at the 20th
  percentile flags 20% of sites by construction, regardless of whether any has a
  real problem."* (architecture_v2 §2.4)
- **The measured loop:** 100 sites in 100 categories. Before the fixes, 29 of 49
  serious findings were correct. The fixes removed 18 false or overstated serious
  findings. Earlier rounds on Sennheiser (an article number read as a price), cry.org
  (8 dated posts wrongly flagged as undated) and ikea/nps (hidden controls) did the
  same.
- **Result:** 43 scripted checks in `SEVERITY_TABLE` (`model.py:38`); 40 of the 43
  fired at least once across the 100 sites.

---

## P1.2 "How you assigned severities — the logic that decides how much each problem hurts discoverability or engagement."

The bullet has two parts: **how much** (the level) and **which**, discoverability
or engagement. We answer both, separately.

### The logic, complete

**Step 1. Base level: where in the chain it breaks** (`model.py:38`,
`severity-rationale.md`). The principle: *"justified by mechanism, never by how
common the defect is."*

| Level | Meaning | Examples (with the reason on record) |
|---|---|---|
| critical | the AI can't get in, or the page leaves the index | `A1` retrieval agents blocked: *"nothing downstream can matter"*; `A3` noindex; `A7` unreadable: *"must never read as 'no findings'"* |
| high | it gets in, but can't use the page or the fact | `B1_fact_absent` (T3), `B4` empty shell, `A2` snippet suppressed (*"indexed, but its text cannot be quoted"*), `C1` invalid structured data (*"silently discarded, and nobody notices"*), `C2`/`D4` contradictions, `A9` key page broken |
| medium | reachable but hard or ambiguous | `B1_fact_script_only` (T2), `C3` brand unanchored, `C7` title problem, `D1` no dates; engagement risk factors E1, E3, E4, E7, E9, E10, E11 |
| low | real but minor | `A6` no sitemap (*"discovery still works through links"*), `A4` redirect chain, `D3` stale content (*"a prompt to review, not proof the page is wrong"*), E2, E5, E6, E12 |

**Step 2. × how far it spreads:** site-wide 1.0, a template 0.8, one page 0.5.
Under 0.7 drops one level. Skipped when fewer than 3 pages were read, *"so a
Cloudflare 403 after page three cannot produce '12 of 12 pages affected'."*
(`model.py:112` `BLAST`, `:24` `COVERAGE_FLOOR = 3`)

**Step 3. Caps, by how sure we can be** (`model.py:140` `finalise()`):
- a check that is a rule of thumb (`static_heuristic`) → max **medium**. This is
  why most engagement findings can't exceed medium: markup shows *risk*, not harm.
- heuristic confidence → can't reach critical
- **latent**, hidden behind a total access block → max low
- **confirm_intent**, looks deliberate → max low
- anything the agent proposed → max low (`model.py:95`)

**Step 4. Which it hurts:** every finding is labelled `ai_discoverability`,
`user_retention` or `both` (`model.py:106` `hurts_for`). Engagement-gate checks →
user retention, a named few → both, everything else → discoverability. arduino.cc:
5 / 4 / 1.

**Step 5. Show the arithmetic:** every finding prints `severity_rationale`.

### Worked examples, from the arduino.cc report

```
F-001  base=high (extractability/B1_fact_absent); blast=template x0.8 => high
F-005  base=medium (engagement/E1_unlabelled_input); blast=single_page x0.5; -> demoted to low => low
F-009  base=high (extractability/B1_fact_absent); blast=template x0.8; cap(confirm_intent)-> low => low
F-010  base=medium (proposed by agent review; ...); blast=template x0.8; cap(agent_review)-> low => low
```

These show a finding that keeps its level, one demoted for spread, one capped
because it looks deliberate, and one capped because the agent proposed it.

### What's non-obvious here, ranked

1. **Never by prevalence.** Most tools grade on how common a problem is. That's
   circular.
2. **A table, not a formula.** v1's `f(gate, blast, confidence)` collapsed to a
   table, because gate and confidence are fixed per check. *"A judge can read a
   table."* (architecture_v2 §5)
3. **Latent, not suppressed.** Hiding findings behind a block creates a
   *"second-audit trap"*: the owner fixes robots.txt, re-runs, and meets a wave of
   new problems. And robots.txt is per agent, so a page blocked to one assistant may
   be open to another. (`audit.py:392`, `severity-rationale.md`)
4. **Certainty caps severity.** A rule of thumb can't become critical, however bad
   it looks. E11 (no viewport) is the one engagement check that's a plain fact, so
   it isn't capped. That shows the cap is about certainty, not category.
5. **Banded numbers only.** Spread is one of three bands, never a raw ratio, *"so
   the ordering is stable across machines."*

### Soft spots a judge could probe

- **F-001 says `blast=template` for one page.** In code, `B1` is `template` unless
  every page is affected (`check_extractability.py:539`), so it never drops for
  being on one page. The code does it, but no reason is written down. Plausible
  reading: an obligation only exists on key-role pages, so one missing contact page
  is the whole contact function. Don't use F-001 as the spread example; use F-005.
- **"Why is an engagement problem only medium?"** Because static markup shows a
  risk factor, not what visitors did, and certainty caps severity. It's on record in
  `severity-rationale.md`.

---

## P1.3 "How you derived the suggested actions — why each fix is mechanism-sound and how you prioritized them."

### Why each fix is mechanism-sound

1. **Each check writes its own fix, in the same script**, so the advice can't
   drift from what was measured. For example, `B1` in `check_extractability.py`.
2. **The fix targets the measured mechanism.** F-001 (fact absent from the raw
   response): *"Render the phone/email into server-side HTML text"*; if it comes
   from an API, *"server-render a default and hydrate over it"*; also add it as
   structured data (`ContactPoint`). It fixes the thing a non-rendering fetcher
   can't see, not something adjacent.
3. **Every fix has a `verify` step that restates the check's own pass
   condition.** Across all 41 checks seen in 119 real reports, 41 of 41 have one,
   and 14 are commands you can run:
   - B1: *"curl -s <url> | grep -i '<phone/email value>' returns a match with
     JavaScript disabled"*
   - A3: *"curl -sI <url> | grep -i x-robots-tag returns nothing…"*
   - A4: *"curl -sIL <url> shows at most one 3xx before the 200"*
   - C7: *"curl -s <url> | grep -o '<title>…' differs across pages and is never
     empty"*

   The owner can confirm the fix with the same measurement that found the problem,
   without us. This is non-obvious, and it's visible in every report.
4. **Agent fixes are grounded in the page.** A site-specific step is merged only if
   it quotes text that's really on that page (`verify_claims.py:350`). Both
   arduino.cc runs quoted the homepage's *"Arduino is now a Qualcomm company"* and
   suggested `parentOrganization` naming Qualcomm. A quote that isn't in the
   readable text is rejected: in arduino.cc run 2, `'Loading...'` existed only in an
   `aria-label`.
5. **Proactive advice only when it applies.** Each proactive recommendation carries
   `applies_because`; anything the site already does goes to `already_in_place[]`
   with the evidence. arduino.cc: 2 proactive, 5 already in place (*"/llms.txt is
   present"*). (`audit.py:232` `proactive_for`)

### How they're prioritised

`audit.py:443` `priority_score()` and `rank()`:
- **Severity level sorts first.** Within a level: **severity × confidence ×
  status ÷ effort.**
- Weights (`audit.py:52–53`): critical 5, high 4, medium 3, low 2 · confidence 1.0
  for a measured fact, 0.7 for a heuristic · status active 1.0, confirm_intent 0.5,
  latent 0.35 · effort low 1.0, medium 1.6, high 2.4.
- **An agent claim can't call itself easy.** Its effort is forced to medium:
  *"ranking must not reward a claim for calling itself easy."* Non-obvious, and
  in the code.
- Worked example: F-001 = 4 × 1.0 × 1.0 ÷ 1.6 = **2.5**; F-002 = 3 × 1.0 × 1.0 ÷
  1.0 = **3.0**. F-002 scores higher but ranks second, because high sorts before
  medium.

### Soft spots

- **A2's verify contradicts A2's check.** The verify says "no data-nosnippet
  *around primary content*", but the check fires on any `data-nosnippet`. That's the
  obsidian.md false positive. Don't feature A2.
- **Without the agent, fixes are templates.** They're specific to the check, not the
  site. The agent's grounded steps are what make them site-specific, so show one.

---

## "Anchor every claim to your code."

Everything in P1.1–P1.3 above names its file and line. Three rules for recording:
- Keep the file open, with the editor's tab bar visible, while the claim is spoken.
- For a claim whose evidence isn't in the submission (the design review, the
  100-site run), anchor the *decision* it produced, which is in the code: e.g. the
  `ROLE_OBLIGATIONS` comment that cites the 11 false findings.
- **Best anchor available:** `check_extractability.py:136–139`. The code comment
  itself says *"11 false high findings in the 100-site evaluation"*. It ties field
  research to code in one frame.

---

# PART 2

## P2.1 "Enter the URL on camera — the run must be real and continuous… Interaction, not a pre-rendered static report."

- Type `https://www.arduino.cc/` by hand, inside the manifest's exact prompt.
- One continuous take; cut only waiting time. A real session lasts 2.7–8.8 minutes
  with permission prompts (from transcripts), so heavy trimming is expected.
- "Interaction": at least one follow-up question answered from the report.

## P2.2 "Let the agent work in the CLI — show the agent … invoking your entrypoint skill, fetching, reasoning, and producing findings."

Observed in both rehearsals, in order. Each maps to a word in the bullet:
1. **invoking the entrypoint:** reads `skills/audit-orchestrator/SKILL.md`
2. **fetching:** `audit.py https://www.arduino.cc/ --max-pages 12 --bundle
   WORK/bundle.json -o WORK/report.json` (it chose 12 pages itself, from SKILL.md)
3. **reasoning:** inspects the report and the saved pages, reads each skill's
   "Interpreting results", and says what it found, e.g. *"/en/contact-us is a 224 KB
   Gatsby page that yields zero extracted text"*
4. **producing findings:** writes `WORK/claims.json`, re-runs with
   `--agent-claims`, the verifier accepts or rejects each claim, then it presents
   the result in SKILL.md step 6's order

The "reasoning" moment worth keeping in the edit is the agent explaining *why* the
contact page is empty. That's the agent judging, on camera.

## P2.3 "Drill into the findings — walk through real evidence for at least one finding (e.g. raw-HTML-vs-rendered-DOM diff, missing/invalid JSON-LD, stale or contradictory dates, facts locked in an image/PDF), its severity, and the suggested fix. Show that fixes can be sorted/prioritized by impact."

### The brief's four example evidence types, and what we can show

| Brief's example | What our engine does | On arduino.cc | Elsewhere |
|---|---|---|---|
| raw-HTML-vs-rendered-DOM diff | **Deliberately replaced** by tiering: no browser (379 MB vs 50 MB cap), and *"the rendered DOM was never the measurement"*. We test the raw side: is the fact in what a non-rendering fetcher gets? | **F-001:** the raw HTML of `/en/contact-us` is a "Loading..." spinner: 0 words, 0 `mailto:`, 0 `tel:` in 223,797 bytes | — |
| missing/invalid JSON-LD | `C1`, `C3`, `C2` | **F-002:** no Organization or `sameAs` on any page (hand-checked); **F-011** (agent): product pages carry only `FAQPage`, no `Product` | ghost.org: review author stored as `"\"Isaac Saul\""` |
| stale or contradictory dates | `D1`–`D4` | none | blender.org (agent): 2010–2012 press releases all `dateModified 2024-08-13`, within 2 seconds |
| facts locked in an image/PDF | **no check in v4** (v2 planned `B5`, not shipped); `E4` covers missing alt text as an engagement issue | — | — |

**Recommended drill: F-001.** It's the closest match to the brief's first example,
done the way the design intends. It covers evidence (the raw response has no
contact token), severity (high, T3, with the arithmetic printed) and fix
(server-render it; verify with curl with JavaScript off). Running the report's own
verify step on camera (`curl … | grep -cE 'mailto:|tel:'` → `0`) is the finding
corroborating itself.

**If a judge asks "why no rendered-DOM diff?"**, the answer is on record: the
browser can't ship inside 50 MB, a browser adds nondeterminism, and assistant
fetchers don't render either. So the raw response *is* what the assistant sees.

### "Show that fixes can be sorted/prioritized by impact."
- `prioritized_actions[]` ranks all 11. Ask the agent to list them in order.

---

# THE RUBRIC

## Reasoning (35): "sound, non-obvious, and traceable to the submitted code"

Scorecard of every candidate Part 1 claim:

| Claim | Sound | Non-obvious | Traceable | Use? |
|---|---|---|---|---|
| Present in bytes ≠ present to the assistant (T2 vs T3) | ✅ | ✅✅ | ✅ `extraction-tiers.md`, `bundle.py:322` | **yes, lead** |
| A page owes a fact because of what it's for; the code cites the 11 false findings | ✅ | ✅✅ | ✅ `check_extractability.py:126–149` | **yes** |
| HTTP 200 can be a bot wall (two rounds of fixes) | ✅ | ✅ | ✅ `bundle.py:416` | **yes** |
| Training ≠ retrieval bots | ✅ | ✅ | ✅ `bot-taxonomy.md` | **yes** |
| Never by prevalence (no percentile thresholds) | ✅ | ✅✅ | ✅ `severity-rationale.md` | **yes** |
| Latent, not suppressed (second-audit trap) | ✅ | ✅ | ✅ `audit.py:392` | yes |
| Certainty caps severity (rule of thumb → max medium; E11 exception) | ✅ | ✅ | ✅ `model.py:140` | yes |
| Verify step re-states the check's pass condition (41/41) | ✅ | ✅ | ✅ every report | **yes** |
| Agent fixes must quote the page | ✅ | ✅ | ✅ `verify_claims.py:350` | yes |
| Agent claims can't call themselves easy | ✅ | ✅ | ✅ `audit.py:443` | yes |
| Deliberate ≠ defective | ✅ | medium | ✅ `deliberate-vs-defect.md` | yes, briefly |
| Short AI visits can be success (no bounce metrics) | ✅ | ✅ | ✅ `checks_skipped` | optional |
| The three-gate model (let in / read / pick out) | ✅ | ❌ it's the brief's own appendix | ✅ | one line only |
| "43 checks, 40 fired on 100 sites" | ✅ | ❌ | partly | optional |
| "We watched assistants cite X, ignore Y" | — | — | ❌ no record | **no** |

## Live behaviour (35): "real, evidence-backed findings — few misses, few false positives"

**Real and evidence-backed:** every finding names its URLs and the exact string or
field. The agent's claims were each checked against the saved crawl before being
admitted.

**False positives on arduino.cc, hand-checked 2026-09-24 against the live site:**
- ✅ True: F-001 (no contact token), F-002 (no JSON-LD or `sameAs` on home, about,
  hardware or maker), F-003 (no `<title>` on `/en/about` and `/en/contact-us`),
  F-004 (unnamed controls on every page checked), F-006 (no `lang` on those two
  pages), F-007 (no `<h1>` on home, contact, hardware, maker), F-008 (no structured
  data), F-010 and F-011 (agent claims).
- ⚠️ **Counts overstated:** `arduino.cc/en/about` redirects to
  `www.arduino.cc/en/about` and both are counted, and `/from-blink-to-think`
  redirects to `/qualcomm`. So F-003 and F-006 say "3 pages" (really 2), and F-004
  says "11 pages". The agent flagged this itself in both rehearsals. That's the
  honest answer if asked.
- ⚠️ F-001's printed `Reproduce:` regex matches asset hashes and SVG numbers, so it
  prints noise although the finding is right.

**Misses on arduino.cc:**
- `B4` (empty shell) didn't fire on the contact page. It looks for React, Next and
  Nuxt mount points (`root|app|__next|__nuxt`, `check_extractability.py:417`), and
  Gatsby's isn't in the list. The page is still caught by `B1` at high, and the
  agent noticed the miss.
- No check for facts locked in images or PDFs.
- Facts fetched by the browser after load are invisible to the method. This is
  declared in every report's Not-assessed list.

**On a URL the judge picks:** the agent's triage (SKILL.md step 3, each skill's
"Interpreting results") tells it how to spot the known weak cases, e.g. *"A2 from
data-nosnippet is decided by where the attribute sits"*, and to say so. In v4 that
changes **what the agent tells the user**, not `report.json`. The measured risk
from 100 sites: serious-finding precision 27–55%, mainly network or IP blocks read
as site defects. About 1 site in 5 is blocked or fails, and is reported as such.

## Reproducibility, quality & hygiene (30)

| Sub-point in the brief | Status | Evidence |
|---|---|---|
| "replay the run via the disclosed harness + model + REPLAY.txt and reach the same substance" | ✅ | two fresh arduino.cc sessions: same scripted findings, counts, headline, ranks 1–5; agent found the same two problems in different words |
| "findings and actions hold up under a judge-chosen URL (correct, specific, mechanism-sound, prioritized)" | ⚠️ | correct: the risk above; specific: every finding names URLs and strings; mechanism-sound: fix beside check, verify restates the check; prioritized: all findings ranked |
| "harness/model fully disclosed" | ✅ | Claude Opus 5.5 (`claude-opus-5-5`), effort medium; Claude Code 2.1.280. **Set effort back to medium before filming.** |
| "REPLAY.txt well-formed" | ✅ | six labels; pinned versions (bs4 4.15.0 would install otherwise); clean-install tested; ⚠️ Neel's full walk-through pending |
| "engine self-consistent with the video" | ✅ | zip sha256 `22aa94…4f14`; fresh unzip for filming |
| "deterministic" | ✅ | saved crawl + `--replay`; deterministic crawl order (`bundle.py:22`); stable sorts; banded severity; 100/100 double replays identical; two live arduino.cc crawls identical. Honest wording: *"deterministic given fixed inputs; network observation is not."* |

---

## What this changes, in one list

1. **P1.1:** lead with "present in the bytes ≠ present to the assistant". Anchor
   field research on the `ROLE_OBLIGATIONS` comment that cites the evaluation. Don't
   claim assistant observation unless someone has notes.
2. **P1.2:** answer both halves, *how much* and *which*. Use F-005 for spread,
   F-009 and F-010 for caps; don't use F-001 for spread.
3. **P1.3:** the strongest new point is "every fix ships a verify step that restates
   the check's own pass condition", plus "an agent claim can't call itself easy".
4. **P2.3:** drill into F-001 as our version of the brief's raw-vs-rendered example,
   and have the "why no rendered diff" answer ready. Don't claim an image/PDF check.
5. **Live behaviour:** be ready for "3 pages" really being 2; the agent will likely
   say it first.
