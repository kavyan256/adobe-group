# Engagement checks: thresholds, mechanisms, and what was cut

Every check must yield **a number and a selector** that a non-expert can verify in
thirty seconds: "14 required fields, 6 with no label" qualifies; "above-fold text
is 12 words" does not (Apple and Stripe would both fail it). All findings are
`static_heuristic` and therefore capped at medium — risk factors inferred from
markup, never observed behaviour.

## Checks that ship

| Check | Threshold | Mechanism |
|---|---|---|
| `E1_form_friction` | >5 required fields, or any input with no programmatic label | Completion drops sharply past about five required fields. An unlabelled input is unusable with a screen reader and ambiguous to any agent. |
| `E2_vague_link_text` | ≥3 links, or ≥15% of links, from a fixed vague-phrase set | Non-descriptive links defeat scanning and tell assistants nothing about the destination. |
| `E3_unnamed_controls` | ≥3 controls with an empty accessible name | The accessible name — from text, `aria-label`, `title` or child `img alt` — is spec-defined and **language-neutral**, unlike action-verb matching. |
| `E4_images_missing_alt` | ≥3 images, or ≥30%, with no `alt` attribute at all | `alt=""` correctly marks decoration; a missing attribute does not. A fact carried only in an image is also invisible to retrieval agents, so this hurts discoverability too. |
| `E5_no_lang` | `<html>` has no `lang` | Affects screen-reader pronunciation and how any consumer processes the text. |
| `E6_heading_structure` | no `h1` on the page | Extractors use the top heading to decide what a page is about. Several `h1`s are legal HTML5 and are not reported. |
| `E7_zoom_disabled` | `user-scalable` is `no`/`0`, or `maximum-scale` below `2` | WCAG 1.4.4 asks for 200% zoom, so the threshold is `< 2`. Directives are parsed, not substring-matched: `maximum-scale=10` contains `maximum-scale=1`. Medium, not high: iOS Safari ignores these directives, and a map may suppress pinch deliberately. |
| `E9_promise_payoff_mismatch` | **zero** distinctive title/description terms in the body | Deliberately extreme: any softer overlap threshold has an undefined false-positive rate on brand-only titles. |
| `E10_no_next_step` | a non-legal page of 200+ words whose content (nav, header, footer, aside removed) has no internal link, form, `tel:` or `mailto:` | A visitor from an AI answer lands mid-site. A site-wide nav is identical on every page, so it says nothing about where this page should lead. Legal pages are legitimately terminal. |

## Deliberately not checked

| Excluded | Reason |
|---|---|
| Consent-banner presence | Legally mandated under ePrivacy/GDPR; flagging it would fire on nearly every EU-facing site. |
| Core Web Vitals (LCP / CLS / INP) | Field metrics at the 75th percentile. One synthetic fetch is not a measurement, and INP cannot be measured synthetically at all. Listed in `checks_skipped[]`. |
| Colour contrast | Needs computed styles, therefore a browser. Listed in `checks_skipped[]` with axe DevTools / Lighthouse as the remedy. |
| "Above the fold" | Most users scroll, and viewport diversity makes any fixed threshold arbitrary. |
| Action-verb CTA detection | An English verb list fails on other languages, noun CTAs and icon buttons; `E3` tests affordance structurally instead. |
| "CTA is an image" | `<a><img alt="…"></a>` is valid and accessible; there is no reliable detector. |
| Bounce rate | Conflates satisfied and dissatisfied exits. For AI-sourced traffic the click is often verification, so a short visit is frequently the desired outcome. |
