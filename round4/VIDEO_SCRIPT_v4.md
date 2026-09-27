# Round 4 video — exact script (v4)

Team 404 Error. Hard cap 5:00: Part 1 ≤ 3:00 (Malhar), Part 2 ≤ 2:00 (Kavyan).
v4 supersedes v3. Topics and their order come from `TOPIC_PLAN.md`.

- **SAY** lines are word for word. Read them exactly.
- **SCREEN** is what must be visible at that moment.
- **YOU'LL SEE** is what the agent actually printed in our two arduino.cc
  rehearsals (2026-09-23). The agent writes in its own words, so its phrasing
  will differ slightly on the day. Anything marked *(fixed)* comes from the
  scripts and appears exactly as written here.

Every file and line reference was checked against the submitted code.

---

# PART 1 — Our reasoning (Malhar) — about 2:55 at a normal speaking pace

Built from `TOPIC_PLAN.md`: every MUST topic, plus the IMPORTANT ones that only
Part 1 can cover. Topic numbers (T1, T2 …) are marked on each section so the plan
and the script stay in step.

**How to record it.** Screen-capture the files, with your voice over them. Nothing
spoken names a file or a function.

**SCREEN lines are instructions for whoever records. Never read them aloud.**
They say which file must be open while each line is spoken. The brief requires
every claim to point to the code, and an open file whose name shows in the
editor tab does that. Keep the tab bar visible.

### 1.1 Opening — T18 (~8 s)

SCREEN: `marketplace.json`

SAY:
> "We're team 404 Error. Our audit follows one rule: scripts measure, the AI
> judges, and a script checks the AI."

### 1.2 How we found the signals — T1, T2, T3, T6, T4 (~53 s)

SCREEN, in order: `crawl-access-audit/SKILL.md`;
`fact-extractability-audit/references/extraction-tiers.md` (tier table);
`crawl-access-audit/references/bot-taxonomy.md` (the two bot tables);
`engagement-audit/references/engagement-checks.md`;
`audit-orchestrator/scripts/bundle.py` line 416 (bot-challenge detection);
`crawl-access-audit/references/deliberate-vs-defect.md`

SAY:
> "What separates a site assistants cite from one they ignore or get wrong?
> Ignored sites fail at the door: the crawler is blocked, or the fact isn't in the
> page it receives. Misrepresented sites have facts that are stale,
> contradictory, or easy to confuse with another brand. So we grade each fact by
> where it lives: visible text passes, hidden script data is medium, missing is
> high. That stops us calling every JavaScript site invisible. Blocking a
> training bot doesn't stop citation, so we only flag bots that fetch answers.
> For visitors, we check what stops them acting. Then we tested on a hundred real
> sites and checked the serious findings by hand. Every false alarm became a
> rule: bot-challenge pages are now detected, and a legal page kept out of search
> is a question, not a critical."

### 1.3 How severity is calculated — T7, T8, T9, T10, T12 (~44 s)

SCREEN, in order: `audit-orchestrator/references/severity-rationale.md` (base
table, then "The arithmetic"); `audit-orchestrator/scripts/model.py` line 38.
Then these three lines from our arduino.cc report:

```
F-001  base=high (extractability/B1_fact_absent); blast=template x0.8 => high
F-005  base=medium (engagement/E1_unlabelled_input); blast=single_page x0.5; -> demoted to low => low
F-009  base=high (extractability/B1_fact_absent); blast=template x0.8; cap(confirm_intent)-> low => low
```

SAY:
> "Severity starts from where the chain breaks. Can't get in: critical, because
> nothing else matters until that's fixed. Gets in, but the fact is missing:
> high. The fact is there but hard to reach or ambiguous: medium. Minor friction:
> low. The level comes from the mechanism, never from how common a problem is,
> because grading on a curve flags the same share of every site. Then we adjust.
> A problem on one page drops a level. Rules of thumb can't go above medium. And
> anything behind a bigger block, anything that looks deliberate, or anything the
> AI proposed is capped at low. Every finding also says whether it hurts
> discovery, visitors, or both."

### 1.4 How fixes are made and ranked — T14, T15, T16 (~23 s)

SCREEN: a finding's fix with its "how" and "verify" steps; arduino.cc's
Qualcomm fix in the report; `audit-orchestrator/scripts/audit.py` line 443

SAY:
> "Every fix targets the cause the check measured, and says how to confirm it
> worked. The AI can add steps for the specific site, but only by quoting text
> really on the page, like 'Arduino is now a Qualcomm company'. For ranking,
> levels sort first, then impact over effort, so a quick cosmetic fix never
> outranks a real blocker."

### 1.5 Why it gives the same answer every time — T24, T25, T26, T22, T27, T28 (~41 s)

SCREEN, in order: `audit-orchestrator/scripts/bundle.py` (the saved crawl);
`audit-orchestrator/references/severity-rationale.md` ("banded, so the ordering
is stable across machines"); `audit-orchestrator/scripts/model.py` line 95;
`agent-review-audit/scripts/verify_claims.py`; `bundle.py` line 63

SAY:
> "Why repeatable? An audit you act on has to give the same answer twice, or you
> can't tell if your fix worked. So we crawl once and save it, every check reads
> that copy, and the table sets every scripted severity, never the AI. We tried letting the AI
> re-judge severities, but its answers changed between runs and it was too slow.
> So now it can only add findings, each checked against the saved crawl and
> capped at low. All eight it added held up when we checked by hand. Two live
> crawls of arduino.cc gave identical findings, and every run is capped at 280
> seconds."

### If it runs long when read aloud

Cut in this order, and time it again after each cut:
1. T12: "Every finding also says whether it hurts discovery, visitors, or both."
2. T28: "and every run is capped at 280 seconds"
3. T3: "Blocking a training bot doesn't stop citation, so we only flag bots that fetch answers."
4. T15: the Qualcomm sentence

---

# PART 2 — Live run (Kavyan) — hard cap 2:00

One continuous take. The real session runs about 3 to 6 minutes, including
permission prompts. Cut the waiting to fit. Never cut between two different
runs.

**Before you press record:** do everything in the Pre-flight list at the end.
You start already inside the fresh `brand-ai-readiness-audit/` folder, with
`.venv` active.

### 2.1 Proof it's the submitted package (0:00–0:07)

TYPE:
```
sha256sum ../brand-ai-readiness-audit-FINAL.zip && ls
```
YOU'LL SEE *(fixed)*: `22aa9491490fac0bef88c7f1767ac551a625ea78c081e42313fb1b230dc94f14`,
then `marketplace.json  README.md  requirements.txt  schema  skills  tests  WORK`

SAY:
> "That hash matches our Round 3 zip, and the one in our replay file."

### 2.2 Harness and model (0:07–0:13)

TYPE: `claude`
YOU'LL SEE: the Claude Code welcome box, with the model name visible

SAY:
> "The harness is Claude Code 2.1.280, and the model is Claude Opus 5.5, at medium
> effort."

### 2.3 The prompt, with the URL typed on camera (0:13–0:24)

Paste everything up to "Audit ", then **type the URL by hand**, then paste the rest:
```
Audit https://www.arduino.cc/ for AI-discoverability and on-site-engagement problems. Follow skills/audit-orchestrator/SKILL.md exactly, all six steps, using WORK/ for intermediate files and WORK/report.json for the final report.
```

SAY (while typing the URL):
> "I'm giving it arduino.cc, a site we never used while building this, and
> pointing it at our entrypoint skill."

### 2.4 The wiring (0:24–0:33)

YOU'LL SEE: first a call that reads `skills/audit-orchestrator/SKILL.md`, then
*(fixed command)*:
```
python3 skills/audit-orchestrator/scripts/audit.py https://www.arduino.cc/ --max-pages 12 --bundle WORK/bundle.json -o WORK/report.json
```
Approve each prompt on camera. Choose "Yes", not "don't ask again".

SAY:
> "It's reading our submitted entrypoint and running its script. A real crawl,
> nothing prewritten."

### 2.5 The agent review (0:33–0:41) — CUT most of this segment

YOU'LL SEE: the agent inspecting the report and bundle. It may print
*"/en/contact-us is a 224 KB Gatsby page that yields zero extracted text"*. Then
it runs `page_profile.py`, writes `WORK/claims.json` (approve the write), and
re-runs `audit.py --replay WORK/bundle.json --agent-claims WORK/claims.json`.

Keep about 8 seconds, around the claims.json write. SAY:
> "Now the agent reviews the same crawl and writes its own claims. Our verifier
> checks each one before it gets in."

### 2.6 The result (0:41–1:02)

YOU'LL SEE: the agent's summary. In rehearsal it opened with *"10 findings. The
most severe is 'No phone/email found in the raw HTML of 1 page(s) that should
carry one'"*, with 1 high, 3 medium and 6 low, plus 1 to confirm with the owner.
Under top action 1, it said the contact page's server HTML *"contains nothing
except a Gatsby 'Loading...' spinner"*.

SAY (read the count off the screen. If it isn't ten, say the number you see):
> "Ten findings, plus one to confirm with the owner. The most severe: Arduino's
> contact page has no phone number or email that a machine can read. And the
> agent explains why: the server sends only a loading spinner, so without
> JavaScript the page is empty. It leads with what to fix first, and ends with
> what it couldn't check."

If the agent did not mention the spinner this time, drop the third and fourth sentences.

### 2.7 Proof anyone can run (1:02–1:09)

In a second terminal pane, TYPE:
```
curl -s https://www.arduino.cc/en/contact-us | grep -cE 'mailto:|tel:'
```
YOU'LL SEE: `0`

SAY:
> "Here's the check anyone can run. Zero."

### 2.8 Evidence, severity, fix, ranking (1:09–1:38)

Back in the agent session, TYPE this follow-up:
```
Show me F-001's evidence, severity rationale and suggested fix from the report, then list every finding in priority order.
```
YOU'LL SEE *(fixed, from the report)*:
- evidence: *"…contain no phone/email-shaped token anywhere in the raw response -
  not in visible text, JSON-LD, meta tags, or any hydration payload…"*
- rationale: `base=high (extractability/B1_fact_absent); blast=template x0.8 => high`
- fix: *"Render the phone/email into server-side HTML text on these pages."*
- ranking: F-001 high, then F-002 to F-004 medium, then the lows, ending with
  the agent's own findings

SAY (as each part appears):
> "High, from our severity table, with the arithmetic shown. The fix: put the
> contact details in the server's HTML. And every finding is ranked, not just the
> top three."

### 2.9 What no script caught (1:38–1:52)

YOU'LL SEE: the agent-review findings at the bottom of the list. In both
rehearsals: *"/hardware, /ambassador-program and /qualcomm reuse the homepage's
og:title ('Arduino - Home')"*.

SAY:
> "And one no script caught. Arduino's Qualcomm announcement tells every link
> preview its title is 'Arduino - Home'. The agent found it, the verifier
> checked it, and it's capped at low."

If it isn't in this run's list, say instead:
> "And these last findings came from the agent. Each one was checked against the
> crawl before it got in."

### 2.10 Close (1:52–1:58)

SAY:
> "Same package, running live, and anyone can reproduce it from our replay file."

---

## Before recording Part 1

- [ ] Malhar reads Part 1 aloud once with a timer. Over 2:55, apply the cut
      order at the end of Part 1 until it fits
- [ ] Every file in the SCREEN lines opened in tabs, in order, tab bar visible
- [ ] The three `severity_rationale` lines and the Qualcomm fix ready in the
      arduino.cc report, so they can be shown without searching

## Pre-flight, just before recording Part 2

- [ ] New empty folder. Copy in `brand-ai-readiness-audit-FINAL.zip` and follow
      `ENV_SETUP` in `REPLAY_404Error.txt` exactly, including the 398-test check.
      This is also the final test of the manifest
- [ ] `/model`: Claude Opus 5.5, **effort medium**
- [ ] Check the live site still shows both findings:
      `curl -s https://www.arduino.cc/qualcomm | grep -o 'og:title[^>]*'` should show `Arduino - Home`,
      and the `mailto:|tel:` count should still be `0`
- [ ] Two terminal panes, large font, wide enough for long JSON lines
- [ ] Nothing pre-approved: a judge's cold session will ask, so yours should too

## Things the agent may say that you should not react to

In rehearsal the agent also added caveats such as *"F-003 and F-006 count
/en/about twice"* and *"B4 didn't fire on /en/contact-us"*. That's the agent
being candid about the tool's limits. Leave them on screen and don't comment.

## If something goes differently on the take

- **The crawl comes back `partial` or `failed`.** Stop and start a completely new
  take. Never cut between two runs.
- **The agent's claims differ from rehearsal.** That's expected. Use the
  fallback lines in 2.6 and 2.9. Don't retake just to get a particular claim.
- **Someone asks about F-001's `Reproduce:` line.** Its regex matches asset
  hashes and SVG path numbers, so it prints noise even though the finding is
  right. That's why we show the `mailto:|tel:` count.
- **"Why does rank 1 score 2.5 when rank 2 scores 3.0?"** The severity band sorts
  first; `priority_score` only breaks ties inside a band.

## Do not

- Run the `Reproduce:` command from F-001's evidence
- Say "never seen": we rehearsed on arduino.cc. Say "never used while building it"
- Call the rejected `'Loading...'` fix a hallucination. That text exists in an
  `aria-label`. It was rejected because retrievers don't read attributes
- Claim an overall accuracy figure. The 8 of 8 covers agent claims only
- Splice takes
