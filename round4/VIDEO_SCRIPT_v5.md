# Round 4 video — exact script (v5)

Team 404 Error. Hard cap 5:00: Part 1 ≤ 3:00 (Malhar), Part 2 ≤ 2:00 (Kavyan).
v5 supersedes v4. Built from `DEEP_DIVE.md`; section numbers in brackets point
there.

- **SAY** lines are word for word.
- **SCREEN** lines are instructions for whoever records. **Never read them aloud.**
  They say which file must be open while the line is spoken. The brief requires
  every claim to point to the code; an open file with its name in the editor tab
  does that. Keep the tab bar visible.
- **YOU'LL SEE** is what the agent printed in our arduino.cc rehearsals. Its wording
  will differ on the day. Items marked *(fixed)* come from the scripts and appear
  exactly as written.

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
3. These lines from our arduino.cc report:
```
F-005  base=medium (engagement/E1_unlabelled_input); blast=single_page x0.5; -> demoted to low => low
F-009  base=high (extractability/B1_fact_absent); blast=template x0.8; cap(confirm_intent)-> low => low
F-010  base=medium (proposed by agent review; ...); blast=template x0.8; cap(agent_review)-> low => low
```
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
2. F-001's `suggested_action` in the arduino.cc report, with its `verify` line:
   *"curl -s <url> | grep -i '<phone/email value>' returns a match with JavaScript
   disabled"*
3. F-002's `site_specific` step quoting *"Arduino is now a Qualcomm company"*
4. `audit-orchestrator/scripts/audit.py` line 443: the ranking, including the
   comment *"ranking must not reward a claim for calling itself easy"*

SAY:
> "Each check writes its own fix, aimed at the mechanism it measured, and every
> fix says how to confirm it worked, using the same test that found the problem.
> The AI can add steps specific to the site, but only by quoting text really on
> the page, like 'Arduino is now a Qualcomm company'. Ranking puts severity
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

# PART 2 — Live run (Kavyan) — hard cap 2:00

One continuous take. A real session runs 3–9 minutes including permission
prompts, so cut the waiting to fit. **Never cut between two different runs.**
Start inside a fresh `brand-ai-readiness-audit/` folder with `.venv` active (see
Pre-flight).

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
Audit https://www.arduino.cc/ for AI-discoverability and on-site-engagement problems. Follow skills/audit-orchestrator/SKILL.md exactly, all six steps, using WORK/ for intermediate files and WORK/report.json for the final report.
```

SAY (while typing the URL):
> "I'm giving it arduino.cc, a site we never used while building this, and
> pointing it at our entrypoint skill."

### 2.4 Invoking the entrypoint and fetching (0:24–0:33)

YOU'LL SEE: the agent reading `skills/audit-orchestrator/SKILL.md`, then
*(fixed)*:
```
python3 skills/audit-orchestrator/scripts/audit.py https://www.arduino.cc/ --max-pages 12 --bundle WORK/bundle.json -o WORK/report.json
```
Approve each prompt on camera with "Yes", not "don't ask again".

SAY:
> "It's reading our submitted entrypoint and running its script. A real crawl,
> nothing prewritten."

### 2.5 Reasoning (0:33–0:43) — keep the agent's reasoning, cut the rest

YOU'LL SEE: the agent inspecting the report and the saved pages. **Keep the line
where it explains the contact page**; in rehearsal: *"/en/contact-us is a 224 KB
Gatsby page that yields zero extracted text"*. Then it writes `WORK/claims.json`
(approve the write) and re-runs with `--agent-claims`.

SAY:
> "Now it's reasoning over the same crawl: it's noticed the contact page is empty
> to a fetcher. Its own claims go through our verifier before they get in."

If the agent doesn't print the contact-page observation, drop the first sentence
after the colon.

### 2.6 The findings (0:43–1:00)

YOU'LL SEE: the agent's summary. In rehearsal: *"10 findings. The most severe is
'No phone/email found in the raw HTML of 1 page(s) that should carry one'"*,
1 high, 3 medium, 6 low, plus 1 to confirm with the owner.

SAY (read the count off the screen):
> "Ten findings, plus one to confirm with the owner. The most severe: Arduino's
> contact page. A person with a browser sees a working page. A fetcher that
> doesn't run JavaScript gets a loading spinner, with no phone or email anywhere."

### 2.7 The evidence, checked live (1:00–1:08)

Second terminal pane, TYPE:
```
curl -s https://www.arduino.cc/en/contact-us | grep -cE 'mailto:|tel:'
```
YOU'LL SEE: `0`

SAY:
> "That's what the fetcher gets. Zero."

### 2.8 Severity, fix, ranking (1:08–1:38)

Back in the agent session, TYPE:
```
Show me F-001's evidence, severity rationale and suggested fix from the report, then list every finding in priority order.
```
YOU'LL SEE *(fixed, from the report)*:
- evidence: *"…no phone/email-shaped token anywhere in the raw response - not in
  visible text, JSON-LD, meta tags, or any hydration payload…"*
- rationale: `base=high (extractability/B1_fact_absent); blast=template x0.8 => high`
- fix: *"Render the phone/email into server-side HTML text on these pages."*,
  verify: *"…returns a match with JavaScript disabled."*
- ranking: F-001 high, F-002 to F-004 medium, then the lows, ending with the
  agent's own findings

SAY (as each part appears):
> "High, because the fact isn't anywhere in what the fetcher receives. The fix is
> to put it in the server's HTML, and the report says how to confirm that with
> JavaScript off. And every finding is ranked by impact, not just the top three."

### 2.9 What no script caught (1:38–1:52)

YOU'LL SEE: the agent's findings at the end of the list. In both rehearsals:
*"/hardware, /ambassador-program and /qualcomm reuse the homepage's og:title
('Arduino - Home')"*.

SAY:
> "And one no script caught. Arduino's Qualcomm announcement tells every link
> preview its title is 'Arduino - Home'. The agent found it, the verifier checked
> it, and it's capped at low."

If it isn't in this run's list, say instead:
> "And these last findings came from the agent. Each one was checked against the
> crawl before it got in."

---

## Prepared answers (for questions, or if the agent raises them on screen)

- **"Why no raw-HTML-versus-rendered-page comparison?"** A browser can't ship: Chromium
  is 379 MB against a 50 MB cap. And assistant fetchers don't render pages either,
  so the raw response *is* what the assistant sees. F-001 is that test.
- **"F-003 says 3 pages, but I count 2."** `arduino.cc/en/about` redirects to
  `www.arduino.cc/en/about`, and both are counted. The finding is true; the count is
  one too high. The agent flagged this in both rehearsals.
- **"Why didn't the empty-shell check fire on the contact page?"** It looks for
  React, Next and Nuxt mount points, and Gatsby's isn't on the list. The page is
  still caught at high by the missing-fact check.
- **"F-001 is on one page; why does it say template?"** The missing-fact check is
  written never to drop a level for being on one page. The code doesn't state why;
  our reading is that the obligation only exists on key pages like contact and
  pricing, so one empty contact page is the whole contact function. Say it as our
  reading, not as documented design.
- **"Why does rank 1 score 2.5 and rank 2 score 3.0?"** Severity sorts first. Within
  a level: severity × confidence × status ÷ effort. F-001 is 4 ÷ 1.6 = 2.5; F-002 is
  3 ÷ 1.0 = 3.0.
- **"Do you check facts locked in images or PDFs?"** No. That check was planned and
  not shipped. Don't imply otherwise.
- **"The Reproduce line in F-001 prints numbers."** Its regex matches asset hashes
  and SVG path data. The `mailto:|tel:` count is the clean check.

## Before recording Part 1

- [ ] Malhar times one read-aloud; apply the cut order until it fits under 3:00
- [ ] Every SCREEN file open in tabs, in order, tab bar visible
- [ ] The three `severity_rationale` lines, F-001's `suggested_action` and F-002's
      Qualcomm step ready to show from the arduino.cc report
- [ ] `check_extractability.py` scrolled to lines 136–139 in its own tab

## Pre-flight, just before recording Part 2

- [ ] New empty folder; copy in `brand-ai-readiness-audit-FINAL.zip`; follow
      `ENV_SETUP` in `REPLAY_404Error.txt` exactly, including the 398-test check
- [ ] `/model`: Claude Opus 5.5, **effort medium**
- [ ] Open `https://www.arduino.cc/en/contact-us` in a normal browser and confirm it
      shows a real page to a person. 2.6 says it does. If it doesn't, change 2.6's
      third sentence
- [ ] `curl -s https://www.arduino.cc/qualcomm | grep -o 'og:title[^>]*'` still shows
      `Arduino - Home`, and the `mailto:|tel:` count is still `0`
- [ ] Two terminal panes, large font, wide enough for long JSON lines
- [ ] Nothing pre-approved: a judge's cold session will ask, so yours should too

## If something goes differently on the take

- **The crawl comes back `partial` or `failed`:** start a completely new take.
- **The agent's claims differ from rehearsal:** expected. Use the fallback lines in
  2.5 and 2.9. Don't retake just to get a particular claim.

## Do not

- Run the `Reproduce:` command from F-001's evidence
- Say "never seen" (we rehearsed on arduino.cc); say "never used while building it"
- Call the rejected `'Loading...'` fix a hallucination: that text is in an `aria-label`
- Say "its answers changed between runs" about the v5 test: that wasn't measured.
  Use the pre-registered result
- Claim observing what assistants cite, an image/PDF check, or an overall accuracy
  figure
- Feature `A2` (snippet suppression): its fix text and its check disagree
- Splice takes
