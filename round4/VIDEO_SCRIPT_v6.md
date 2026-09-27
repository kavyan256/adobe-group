# Round 4 video — exact script (v6: vyaparapp.in)

Team 404 Error. Hard cap 5:00: Part 1 ≤ 3:00 (Malhar), Part 2 ≤ 2:00 (Kavyan).
v6 supersedes v5: Part 2 now runs on vyaparapp.in; Part 1's examples come from it.
Built from `DEEP_DIVE.md`.

- **SAY** lines are word for word.
- **SCREEN** lines are instructions for whoever records. **Never read them aloud.**
- **YOU'LL SEE** marked *(fixed)* comes from the scripted checks and appears exactly
  as written. Agent output on vyaparapp.in is not yet rehearsed.

---

# PART 1 — Our reasoning (Malhar)

Plain English only: nothing spoken names a file or a function.

### 1.1 Opening

SCREEN: `marketplace.json`

SAY:
> "We're team 404 Error. Our audit follows one rule: scripts measure, the AI
> judges, and a script checks the AI."

### 1.2 How we found the signals [DEEP_DIVE P1.1]

SCREEN, in order:
1. `fact-extractability-audit/references/extraction-tiers.md`: the T0–T3 table
2. `audit-orchestrator/scripts/bundle.py` line 322: the list of hidden data blocks it parses
3. `fact-extractability-audit/scripts/check_extractability.py` lines 136–139: the
   comment that reads *"11 false high findings in the 100-site evaluation"*.
   **Hold this one on screen:** it is our field research, written into the code
4. `audit-orchestrator/scripts/bundle.py` line 416: bot-challenge detection
5. `crawl-access-audit/references/bot-taxonomy.md`: the two bot tables

SAY:
> "What separates a site assistants cite from one they ignore or misquote?
> Whether their fetcher can get in, read the page, and find a fact that's current
> and unambiguous. So we grade each fact by where it sits in what the fetcher
> receives. Visible text passes. Only in script data is medium: the bytes are
> there, but the text reader drops them. Missing is high. That stops us calling
> every JavaScript site invisible. Then we ran every check on a hundred real
> sites, checked the serious findings by hand, and turned each false alarm into a
> rule. Newsletter pages were told they owed a price; now a price is owed only
> where there's real commerce. Bot walls looked like normal pages; now we detect
> them. And blocking a training bot doesn't stop citation, so we only flag bots
> that fetch answers."

### 1.3 How we assign severity [DEEP_DIVE P1.2]

SCREEN, in order:
1. `audit-orchestrator/references/severity-rationale.md`: the line *"justified by
   mechanism, never by how common the defect is"*, then the base-severity table
2. `audit-orchestrator/scripts/model.py` line 38 (the table), line 112 (the spread
   bands), line 140 (the caps)
3. These lines from our vyaparapp.in report:
```
F-001  base=critical (access/A3_noindex); blast=template x0.8 => critical
F-009  base=medium (engagement/E1_unlabelled_input); blast=single_page x0.5; -> demoted to low => low
```
   plus one `cap(agent_review)-> low` line from the vyaparapp.in full run
4. `model.py` line 106: the discovery / visitors / both label
5. `model.py` line 95: AI findings capped at low

SAY:
> "Severity answers two questions: how much it hurts, and what it hurts. How much
> depends on where the chain breaks, never on how common the problem is, because
> grading on a curve flags the same share of every site. Can't get in: critical.
> Gets in, but the fact is missing: high. There, but hard to reach or ambiguous:
> medium. Minor: low. Then a problem on one page drops a level, and certainty
> caps it: a rule of thumb stops at medium, and anything hidden behind a bigger
> block, deliberate-looking, or proposed by the AI stops at low. What it hurts is
> a label on every finding: discovery, visitors, or both. And every finding prints
> its own arithmetic. We tested letting the AI set severity instead, against rules
> we wrote in advance: it caught six of ten known false alarms where we'd required
> seven, and its slowest run took over six minutes. So the table decides, and the
> same crawl always gives the same answer."

### 1.4 How we derive and rank the fixes [DEEP_DIVE P1.3]

SCREEN, in order:
1. The fix text for `B1_fact_absent` inside
   `fact-extractability-audit/scripts/check_extractability.py`
2. F-003's `suggested_action` in the vyaparapp.in report, with its `verify` line:
   *"curl -s <url> | wc -w shows substantive content with no JS executed."*
3. Any `site_specific` step from the vyaparapp.in full run, with the quote it rests on
4. `audit-orchestrator/scripts/audit.py` line 443: the ranking, including the
   comment *"ranking must not reward a claim for calling itself easy"*

SAY:
> "Each check writes its own fix, aimed at the mechanism it measured, and every
> fix says how to confirm it worked, using the same test that found the problem.
> The AI can add steps specific to the site, but only by quoting text that's
> really on that page, and our verifier checks the quote. Ranking puts severity
> first, then impact over effort, and the AI can't push its own suggestions up
> by calling them easy."

### If it runs long when read aloud

Time one read-through. Cut in this order, re-timing after each:
1. "And every finding prints its own arithmetic." (the screen still shows it)
2. "Bot walls looked like normal pages; now we detect them."
3. "And blocking a training bot doesn't stop citation, so we only flag bots that
   fetch answers."

Never cut: the tier grading, the "11 false findings" comment, the two halves of
severity, the verify step, or the pre-registered test.

---

# PART 2 — Live run on vyaparapp.in (Kavyan) — hard cap 2:00

One continuous take. A real session runs 3–9 minutes including permission
prompts, so cut the waiting to fit. **Never cut between two different runs.**
Start inside a fresh `brand-ai-readiness-audit/` folder with `.venv` active (see
Pre-flight).

**Not yet rehearsed on vyaparapp.in:** the agent's own reasoning and claims. Lines
marked *(fixed)* come from the scripted checks and were verified on 2026-09-25;
lines about the agent get filled in after the two full rehearsal runs.

### 2.1 Proof it's the submitted package (0:00–0:07)

TYPE: `sha256sum ../brand-ai-readiness-audit-FINAL.zip && ls`
YOU'LL SEE *(fixed)*: `22aa9491490fac0bef88c7f1767ac551a625ea78c081e42313fb1b230dc94f14`,
then `marketplace.json  README.md  requirements.txt  schema  skills  tests  WORK`

SAY:
> "That hash matches our Round 3 zip, and the one in our replay file."

### 2.2 Harness and model (0:07–0:13)

TYPE: `claude`

SAY:
> "The harness is Claude Code 2.1.280, and the model is Claude Opus 5.5, at medium
> effort."

### 2.3 The URL, typed on camera (0:13–0:24)

Paste the prompt up to "Audit ", **type the URL by hand**, paste the rest:
```
Audit https://vyaparapp.in/ for AI-discoverability and on-site-engagement problems. Follow skills/audit-orchestrator/SKILL.md exactly, all six steps, using WORK/ for intermediate files and WORK/report.json for the final report.
```

SAY (while typing the URL):
> "I'm giving it Vyapar, a billing app used by small businesses across India. We
> never used this site while building the tool."

### 2.4 Invoking the entrypoint and fetching (0:24–0:33)

YOU'LL SEE: the agent reading `skills/audit-orchestrator/SKILL.md`, then
*(fixed)*:
```
python3 skills/audit-orchestrator/scripts/audit.py https://vyaparapp.in/ --max-pages 12 --bundle WORK/bundle.json -o WORK/report.json
```
Approve each prompt on camera with "Yes", not "don't ask again".

SAY:
> "It's reading our submitted entrypoint and running its script. A real crawl,
> nothing prewritten."

### 2.5 Reasoning (0:33–0:41) — keep the agent's reasoning, cut the rest

YOU'LL SEE: the agent inspecting the report and the saved pages, writing
`WORK/claims.json` (approve the write), and re-running with `--agent-claims`.
**Keep one line where the agent explains something in its own words** (fill in
after rehearsal).

SAY:
> "Now it reviews the same crawl and writes its own claims. Our verifier checks
> each one before it gets in."

### 2.6 The findings (0:41–0:52)

YOU'LL SEE *(fixed part)*: headline *"…most severe: 1 page(s) carry a noindex
directive"*; scripted findings 1 critical, 2 high, 3 medium, 9 low. The agent's
claims add to the count.

SAY (read the count off the screen):
> "[Count] findings. The most severe is critical: Vyapar's About page has been
> removed from search."

### 2.7 The evidence, live (0:52–1:08)

Second terminal pane, TYPE:
```
curl -s https://vyaparapp.in/about-us | grep -io "<meta name=.robots[^>]*>"
```
YOU'LL SEE *(fixed, verified 2026-09-25)*:
```
<meta name='robots' content='index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1' />
<meta name="robots" content="noindex, nofollow">
```

SAY:
> "Here's why. The page says 'index me', and then 'don't index me'. When a page
> contradicts itself, search engines obey the stricter rule, so the About page
> disappears. Nobody writes both on purpose."

### 2.8 Severity, fix, ranking (1:08–1:34)

Back in the agent session, TYPE:
```
Show me F-001's severity rationale and suggested fix from the report, then list every finding in priority order.
```
YOU'LL SEE *(fixed, from the report)*:
- rationale: `base=critical (access/A3_noindex); blast=template x0.8 => critical`
- fix: *"Remove noindex from pages that should be findable."*, including
  *"Check for a staging-environment header leaking into production."*
- verify: *"…the page source contains no noindex."*
- ranking: F-001 critical, F-002 and F-003 high (the pricing page), then the
  mediums and lows

SAY (as each part appears):
> "Critical, because a key page is out of the index. The fix is to delete the
> stray tag, and the report says how to confirm it's gone. And every finding is
> ranked by impact."

### 2.9 The second finding: pricing (1:34–1:52)

Second pane, TYPE:
```
curl -s https://vyaparapp.in/pricing | grep -c '₹'
```
YOU'LL SEE: `0`

SAY:
> "And the pricing page, the two highs. To an AI fetcher, the whole page is four
> words: 'Vyapar Plans and Pricing'. Not one rupee sign. The prices only appear
> after JavaScript runs."

The last sentence depends on the Pre-flight browser check. If a browser doesn't
show prices either, drop it.

If the agent added a claim worth showing and there's time, one sentence on it
(fill in after rehearsal).

---

## Prepared answers (for questions, or if the agent raises them on screen)

- **"Maybe the noindex is deliberate?"** The same page also says `index, follow`.
  Two contradictory tags usually mean two tools each writing one, e.g. an SEO
  plugin plus a leftover staging setting. The report's fix says to check exactly
  that.
- **"Why is an About page critical?"** Home, pricing, product, about and contact
  are key pages in our rules: they're where assistants look up who a company is.
  noindex there is critical; on a utility page it would only be a question for the
  owner.
- **"F-002 and F-003 are both the pricing page. Double counting?"** Two mechanisms
  with one cause. F-003: the whole page is empty without JavaScript. F-002: the one
  fact a pricing page owes, a price, isn't anywhere in the response. One fix,
  server-rendering the page, clears both.
- **"Why seven 'unlabelled field' findings?"** The engine reports each form
  separately. The ones on a single page were demoted to low. They're true: phone,
  OTP and email fields with only placeholders.
- **"Why is rank 3 (score 1.667) above rank 4 (score 2.1)?"** Severity level sorts
  first. Within a level: severity × confidence × status ÷ effort. F-003 is high
  (4) ÷ server-rendering effort (2.4) = 1.667; F-004 is medium (3) × heuristic
  confidence (0.7) ÷ low effort (1.0) = 2.1.
- **"Why no raw-HTML-versus-rendered-page comparison?"** A browser can't ship:
  Chromium is 379 MB against a 50 MB cap. Assistant fetchers don't render pages
  either, so the raw response *is* what they see. The pricing check is that test.
- **"Do you check facts locked in images or PDFs?"** No. That check was planned and
  not shipped.
- **"Can ChatGPT still find Vyapar's prices?"** Possibly, from other pages or third
  parties. We say the pricing page is blank to AI fetchers, not that the price
  can't be found anywhere.

## Before recording Part 1

- [ ] Malhar times one read-aloud; apply the cut order until it fits under 3:00
- [ ] Every SCREEN file open in tabs, in order, tab bar visible
- [ ] The vyaparapp.in `severity_rationale` lines and F-003's `suggested_action`
      ready to show
- [ ] `check_extractability.py` scrolled to lines 136–139 in its own tab

## Pre-flight, just before recording Part 2

- [ ] New empty folder; copy in `brand-ai-readiness-audit-FINAL.zip`; follow
      `ENV_SETUP` in `REPLAY_404Error.txt` exactly, including the 398-test check
- [ ] `/model`: Claude Opus 5.5, **effort medium**
- [ ] **Open https://vyaparapp.in/pricing in a normal browser and confirm prices
      appear.** 2.9's last sentence depends on it
- [ ] Both commands still give the same output: two robots tags on `/about-us`, and
      `0` for the `₹` count on `/pricing`
- [ ] Two terminal panes, large font, wide enough for long lines
- [ ] Nothing pre-approved: a judge's cold session will ask, so yours should too

## If something goes differently on the take

- **The crawl comes back `partial` or `failed`:** start a completely new take.
- **The agent's claims differ from rehearsal:** expected. Don't retake just to get
  a particular claim.

## Do not

- Say "never seen": we rehearsed on vyaparapp.in. Say "never used while building it"
- Drill into the seven E1 findings; scroll past them
- Say "AI can't find Vyapar's price"; say "the pricing page is blank to AI fetchers"
- Say "its answers changed between runs" about the v5 test; use the pre-registered result
- Claim observing what assistants cite, an image/PDF check, or an overall accuracy figure
- Splice takes
