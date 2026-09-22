---
name: engagement-audit
description: >-
  Detect on-site engagement risk factors from static markup — form friction,
  unnamed interactive controls, non-descriptive link text, missing image alt
  text, absent lang declaration, broken heading structure, disabled pinch-zoom,
  and pages whose content shares no vocabulary with their own title. Deliberately
  excludes lab performance metrics, consent-banner presence and colour contrast,
  which cannot be measured honestly without a browser or field data. Use
  standalone to answer "why don't visitors who arrive actually act?", or as the
  engagement half of a full AI-readiness audit.
license: Apache-2.0
allowed-tools: Bash, Read
---

# Engagement Audit

## When to use

Standalone, when traffic arrives but does not convert, or as the on-site half of
`audit-orchestrator`. Discoverability and engagement are weighted equally: being
found is worthless if the visitor cannot act once they arrive.

## The reasoning this skill encodes

### Why this skill does not report bounce rate

Bounce conflates satisfied and dissatisfied exits, which is why GA4 deprecated it
in favour of engagement rate. A single-page visit that answered the visitor's
question is a **success**.

This matters more for AI-sourced traffic, not less. An assistant has already
summarised the answer before the visitor clicks, so the residual click is usually
**verification** — the visitor arrives to confirm one specific fact and leaves in
fifteen seconds. That is the desired outcome, and an audit that scored it as
failure would be measuring the wrong thing.

So this skill reports **engagement risk factors** — structural properties that
make acting harder — and never claims to observe behaviour.

### What that implies: fact locatability

If the visitor came to verify one fact, the question is whether they can *find*
it. That is why `X2_no_citation_anchor` (stable heading `id`s, deep-linkable
sections) lives in the extractability skill but serves engagement too: a section
an assistant can link to directly is a section the verifying visitor lands on
without scrolling or searching.

### The evidentiary bar

Every check must yield **a number and a selector**. `"Above-fold text is 12
words"` is not a defect — Apple and Stripe would both fail it. `"14 required
fields, 6 with no associated label"` is a defect a non-expert can verify in
thirty seconds. Checks that could not meet this bar were cut rather than shipped
as heuristics.

## What this skill deliberately does NOT check, and why

| Not checked | Reason |
|---|---|
| **Presence of a consent banner** | Consent notices are legally mandated in many jurisdictions. Flagging their presence would be a false positive on essentially every EU-facing site. |
| **Core Web Vitals (LCP/CLS/INP)** | These are *field* metrics at the 75th percentile. A single synthetic fetch is not a measurement, and **INP cannot be measured synthetically at all**. Reporting a lab number as a finding would be indefensible. |
| **Colour contrast** | Requires computed styles, therefore a browser. Reported in `checks_skipped[]` with the remedy, rather than approximated from inline styles. |
| **"Above the fold" content** | ~85% of users scroll past the first viewport, and viewport sizes vary too widely for a fixed threshold to mean anything. |
| **Action-verb CTA detection** | An English verb list fails on every non-English site. We test for *interactive affordance* structurally instead — an element with a computed accessible name. |
| **"CTA is an image"** | `<a><img alt="…"></a>` is valid and accessible. There is no reliable detector. |

Every finding this skill emits is `measurement_basis: static_heuristic` and is
therefore **capped at medium severity** by the shared severity table. These are
inferred risk factors, not observed behaviour, and the report says so.

## Added in 2.1

`E10_no_next_step`: a page over 200 extracted words whose *content subtree* --
nav, header, footer and aside removed -- offers no in-content link, form or
contact route. A site-wide nav is identical on every page, so it says nothing
about where this page should lead; a visitor who arrives from an AI answer,
checks their one fact and wants to go further has nothing to act on. Legal pages
are exempt, being legitimately terminal.

`E4_images_missing_alt` now agrees with `B5_fact_locked_in_image` on what counts:
a missing `alt` attribute is the defect, and `alt=""` is a correct declaration
that an image is decorative. Previously this skill recommended `alt=""` while the
extractability skill counted it as a defect.

## Inputs

A site bundle, as a path argument or on stdin.

## Procedure

1. Read `<html lang>` first — it gates every language-dependent check (`E5`).
2. Per form, count fields, required fields, and inputs with no programmatic label
   (`E1`). Completion drops sharply beyond about five required fields.
3. Compute the accessible name of every interactive control from text,
   `aria-label`, `title` or child image `alt`; flag controls with none (`E3`).
   This is spec-defined and language-neutral.
4. Measure the ratio of non-descriptive link text — "click here", "read more"
   (`E2`).
5. Check image `alt` coverage (`E4`), heading structure (`E6`), and viewport
   zoom suppression (`E7`, WCAG 1.4.4).
6. Compare the page's own title and meta description against its body text
   (`E9`) — fire **only** when *zero* distinctive title terms appear in the body,
   which is a near-unambiguous promise/payoff failure rather than a stylistic
   judgement.

```bash
python3 scripts/check_engagement.py bundle.json
```

## Output

A JSON object with `findings` and `checks_skipped`. The skipped list always
carries contrast and Core Web Vitals with an explanation and a pointer to the
right tool for each — so a reader knows what was *not* covered and how to cover it.

## References

- `references/engagement-checks.md` — each check, its threshold, and the
  mechanism justifying it
