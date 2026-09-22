# Pre-registered test: agent adjudication of scripted findings (written before any agent run)

Inputs: saved bundles and v4 reports from eval-runs/2026-09-12-100-after-fixes (no live fetching).
Agent: headless `claude -p --model sonnet` (a mid-tier general agent, so a pass is conservative),
tools limited to Read, Write and the skill's own scripts. Instructions: prototype v5 SKILL.md and
references only; no site names or answers in them.

## Sets
- DEV (graded before prototype written): 39 severe findings on 36 sites, verdicts in ground_truth_severe.json.
- HELD-OUT (graded blind before any agent run): 18 medium findings on 17 sites not in DEV, verdicts in ground_truth_heldout.json.
- NEGATIVE CONTROL: hand-written verdicts with fabricated evidence (no agent), must be rejected by the verifier.

## Pass criteria (all must hold)
1. Catch: >= 7 of the 10 knowable-false DEV findings end downgraded, confirm_intent or removed.
2. Keep: 0 of the 7 strict-true DEV findings removed; at most 1 downgraded.
3. Unknowable A7 blocks (12): at most 1 removed (downgrade to a verify-question is acceptable).
4. Held-out: agent verdict matches my blind grade (keep vs downgrade/remove) on >= 80% of findings,
   and removes 0 findings I graded true.
5. Stability: on a repeat run of 10 sites, >= 85% of verdicts identical (keep / downgrade / remove).
6. Verifier: accepts >= 90% of verdicts whose reasoning matches ground truth; rejects 100% of the negative control.
7. Runtime: median agent step <= 180 s per site, max <= 240 s (scripted part adds ~30-140 s; budget 5 min).
8. Every merged report stays schema-valid.
A failure on any criterion is reported as a failure, not re-scored.

## Amendments after the 2-site pilot (supercell, fnac), before any scored run
Pilot runs are tagged `pilot` and are not scored.
- Harness: the pilot allowlist blocked the skill's own `page_profile.py ... > profile.json`
  step (12-13 denied commands per run), inflating runtime to 400 s. Scored runs use
  acceptEdits, python3 and read-only shell tools, with web tools, curl and wget denied.
- Rule: the pilot agent called disabled zoom "deliberate_configuration". That reason now
  applies only to A2/A3/A5 findings, and the A7 reasons only to A7, enforced by the
  verifier and stated in references/adjudication.md. A control verdict for this case was
  added and must be rejected.
- Criteria unchanged.

## Amendment 2 (2026-09-13), before the held-out and repeat runs
The skill changed after the development runs: review candidates with checked dispositions,
duplicates resolved by an explicit scripted-check list, verdicts applied inside audit.py
before ranking, engagement candidates, and a review time budget. Development results
(criteria 1-3) were measured on the earlier version.
- Held-out (criterion 4) and repeat (criterion 5) run on the new version only.
- Repeat sites changed from ['supercell', 'fnac', 'kraken', 'mcmaster', 'zoho', 'msf', 'notion', 'duolingo', 'nhs', 'theverge'] to the first 10 held-out sites, ['bosch', 'curl', 'deliveroo', 'glossier', 'khanacademy', 'lego', 'linear', 'mistral', 'mit', 'nhs'], so
  stability compares two runs of the same version.
- Criteria unchanged.
