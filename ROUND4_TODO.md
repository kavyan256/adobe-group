# Round 4 — To-do

**Deadline: Sat 27 Sep 2026, 23:59 IST.** Aim to submit Friday; Saturday is buffer.

**Submit exactly two things:** a video (≤5 min) and `REPLAY_<TeamName>.txt`.
The Round 3 package is **not** resubmitted — judges replay their own copy, so
`brand-ai-readiness-audit-v4/` must not change.

## Blocked on a decision

- nothing — all decisions made

## Decided

- [x] **Model:** Claude Opus 5.5 (`claude-opus-5-5`), **effort medium**. Read from all four rehearsal transcripts. `/model` now saves effort **high** as default: set it back to medium before filming
- [x] **Team name:** 404 Error → file is `REPLAY_404Error.txt`
- [x] **Engine:** v4, frozen. Verified byte-identical to `submission/brand-ai-readiness-audit-FINAL.zip` and present on GitHub
- [x] **Harness:** Claude Code 2.1.280, interactive (not headless — shows the agent working, allows follow-up questions)
- [x] **Fallback for judges without Claude Code:** `python3 skills/audit-orchestrator/scripts/audit.py <URL> -o report.json` — no LLM, deterministic, reproduces every scripted finding
- [x] **Environment:** Python 3.13.9, httpx 0.28.1, beautifulsoup4 4.13.5

## 1. Demo site

- [x] Screened 11 unseen candidates (results in `demo-screening/`)
- [x] **groww.in** — 12/12, 49.7 s, **critical** `A3_noindex` on `/p/disclosure` and `/p/policies`, plus 2 medium, 3 low
- [x] **arduino.cc** — 12/12, 38.3 s, high `B1_fact_absent` (contact page has no phone/email in raw HTML), `C7_title_problem` (2 pages with no `<title>`), `C3_entity_unanchored`
- [x] ~~**obsidian.md**~~ — **REJECTED.** Its only high (`A2_snippet_suppressed`) is a false positive: both `data-nosnippet` attributes sit on decorative UI mockup panels marked `aria-hidden="true"`, not on primary content. Same class as the framer case in the 100-site audit → `A2` on element-level `data-nosnippet` is a repeatable weak check
- [x] ~~raspberrypi.com~~ — bot-challenge page, `failed`, 0 pages read
- [x] Confirmed groww.in's `<meta name="robots" content="noindex">` is in the raw HTML of both URLs (HTTP 200, no X-Robots-Tag header)
- [x] **DECIDED: arduino.cc.** Full-skill run twice: complete 12/12, 21–31 s, 11 findings (1 high, 3 medium, 7 low), all 11 ranked
- [x] Verified live: `og:title` is `"Arduino - Home"` on `/qualcomm`, `/hardware`, `/ambassador-program`; contact page has zero `mailto:`/`tel:`/email tokens in 223 KB
- [x] **`TEST_SITE_URLS` = `https://www.arduino.cc/`, `https://ghost.org/`, `https://www.blender.org/`**
      - ghost.org: full skill 12/12, 34.6 s, 8 findings (5 scripted + **3 agent, all verified, none rejected**). All three verified live: `/love` review markup stores author names as `"name":"\"Isaac Saul\""` with literal quotes inside the value; `/pricing` shows three plan prices as text with no `Offer` markup; `/domain-error` is HTTP 200, carries no `noindex` and is listed in `sitemap-pages.xml` (came back `info`, and explains why `E11` fired there). Soft spot: don't drill into `E11_no_viewport` on camera
      - blender.org: full skill 12/12, 35.2 s, 5 findings (2 scripted + **3 agent, all verified, none rejected**). All three verified live: press releases from 2010–2012 all carry `dateModified 2024-08-13T12:10:28–30` (bulk-migration stamp, 2-second spread); the FMX 2011 announcement exists at two URLs dated March 13 and May 1 2011; every press release's meta description is the site tagline. `D3_content_stale` did not fire — the script structurally cannot catch a uniform migration timestamp
      - blender.org scripted-only: 12/12, 38.6 s, **2 findings**; `C3` verified true — zero `ld+json` blocks on the page. Keep it: 2 findings on a clean site vs 11 on a sloppy one is the strongest "few false positives" evidence we have
- [ ] Re-check the findings the day before recording — judges hit the live site later, so it must still be there

## 2. REPLAY_<TeamName>.txt

- [x] v2 at `round4/REPLAY_404Error.txt`: six fields, zip sha256, exact pins for the whole dependency set, offline self-check, fresh session per site, fallback
- [x] Pins needed: an unpinned install today resolves beautifulsoup4 **4.15.0**, not the 4.13.5 we ran
- [x] Tested from a clean unzip: pinned venv install works, 398/398 offline tests pass in ~18 s, fallback command gives the same 9 scripted findings on arduino.cc
- [ ] Not yet tested: that `claude` started inside the venv sees the venv's python (the manifest has a recovery line if not). Neel's clean run covers it
- [ ] **Neel replays it on a clean clone without asking anyone anything** — every stumble is a bug in the file
- [ ] Fix and repeat until clean

## 3. Variation — MEASURED, passes

- [x] Scripted-only, two separate live crawls: **identical** — same 9 findings, severities, order; 12/12 pages; 22.1 s vs 22.3 s
- [x] Full skill, two fresh sessions: **identical** scripted findings, coverage (12/12, 76 URLs), headline, `total_findings`, severity split, and ranks 1–5
- [x] Agent layer varied only in wording — both runs surfaced the same two problems (og:title reuse; FAQPage-without-Product). Textbook "model-phrasing variance", which the brief exempts from the nondeterminism flag
- [x] Guardrails caught working live in run 2: 1 claim rejected as duplicating `B1_fact_absent`; 1 fix rejected because its quote `'Loading...'` was not on the page

## 3b. Two things to have answers ready for on camera

- [ ] **F-001's printed reproduce command over-matches.** The regex hits asset hashes and SVG path data, so it prints output even though the finding is correct. Demonstrate with `curl -s https://www.arduino.cc/en/contact-us | grep -cE 'mailto:|tel:'` → `0` instead. If a judge runs the printed line, answer straight
- [ ] **Rank 1 scores 2.5 while ranks 2–3 score 3.0.** Severity band sorts first; `priority_score` only breaks ties inside a band. One sentence, ready

## 4. Part 1 — methodology, ≤3 min (Malhar) — script: `round4/VIDEO_SCRIPT_v3.md` (exact wording), 391 words ≈ 2:36–2:48

Every claim must point at a file, or it scores nothing.

- [ ] **Signal discovery** → `agent-review-audit/references/mechanism-checklist.md`, each skill's `SKILL.md`
- [ ] **Agent precision across the three sites** → 8 claims submitted, 8 verified by the script, **8 confirmed true by hand against the live sites**, 0 false. Say the sample size out loud; contrast with the scripted layer's 27–55% severe precision from the 100-site audit
- [ ] **One sentence on extracted text vs raw source** → checks run on extracted text because that is what a retriever sees. Pre-empts a judge who greps raw HTML for ghost's `18 USD / mo` or arduino's contact token and finds nothing
- [ ] **Agent-layer value, use the blender.org example** → scripts found 2, agent found 3 more, all verified, none rejected; the dateModified-2024 catch is the illustration. Keeps Part 2 free for arduino.cc
- [ ] **Severity logic** → `SEVERITY_TABLE` and `finalise()` in `audit-orchestrator/scripts/model.py`, `references/severity-rationale.md`, `AGENT_REVIEW_CEILING = "low"`
- [ ] **Fix derivation and ranking** → fix templates in the check scripts, `priority_score()` in `audit.py`, `verify_claims.py`
- [ ] Time it aloud — target 2:45, not 3:00
- [ ] Cut anything that can't be pointed at in code

## 5. Part 2 — live run, ≤2 min (Kavyan)

- [ ] Verify engine matches the submitted zip immediately before recording
- [ ] One continuous take; keep the raw file
- [ ] Say the harness and model aloud
- [ ] Type the URL on camera
- [ ] Show the agent invoking the entrypoint (tool calls visible)
- [ ] Say the one line confirming this is the Round 3 entrypoint, not a hardcoded demo
- [ ] Drill into F-001 (high, `B1_fact_absent`): evidence → severity → fix
- [ ] Then the money shot: F-010, the agent-found `og:title "Arduino - Home"` on the Qualcomm announcement page — no script found it
- [ ] Show `prioritized_actions[]` ranking all findings, not just the top 3
- [ ] Ask 1–2 follow-up questions to show it's navigable ("which do I fix first?", "show me the evidence")

## 6. Edit and final check (Neel)

- [ ] Trim idle waiting only — **never splice takes**
- [ ] Total ≤5:00, Part 1 ≤3:00, Part 2 ≤2:00
- [ ] Harness, model and URL in the video match REPLAY.txt word for word
- [ ] Fresh replay of REPLAY.txt still produces a report
- [ ] Raw Part 2 recording kept

## Rules

- Nobody edits `brand-ai-readiness-audit-v4/`
- Only the video and REPLAY.txt are submitted, so anything a judge's replay needs must be in the package or typed into REPLAY.txt
- Trimming idle time is allowed; splicing a run that did not happen is an integrity failure
