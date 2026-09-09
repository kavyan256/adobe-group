# Engagement checks: thresholds, mechanisms, and what was deliberately cut

The evidentiary bar: **every check must yield a number and a selector.**
`"Above-fold text is 12 words"` is not a defect — Apple and Stripe would both
fail it. `"14 required fields, 6 with no associated label"` is a defect a
non-expert can verify in thirty seconds. Checks that could not meet this bar were
cut rather than shipped as heuristics.

All findings here are `measurement_basis: static_heuristic` and therefore capped
at **medium** severity. They are structural risk factors inferred from markup,
never observed behaviour, and the report states this in its `limits` block.

## Checks that ship

| Check | Threshold | Mechanism |
|---|---|---|
| `E1_form_friction` | >5 required fields, or any input with no programmatic label | Completion drops sharply past ~5 required fields. An unlabelled input is unusable with a screen reader and ambiguous to any agent. |
| `E2_vague_link_text` | ≥3 links, or ≥15% of links, matching a fixed vague-phrase set | Non-descriptive links defeat scanning and give assistants no signal about the destination. |
| `E3_unnamed_controls` | ≥3 controls with an empty computed accessible name | Accessible name is spec-defined and **language-neutral** — computed from text, `aria-label`, `title`, or child `img alt`. This replaces action-verb matching, which fails on every non-English site. |
| `E4_images_missing_alt` | ≥3 images, or ≥30%, with no `alt` attribute at all | A missing attribute is distinct from `alt=""`, which correctly marks decoration. |
| `E5_no_lang` | `<html>` has no `lang` | Gates every language-dependent check; also affects screen-reader pronunciation. |
| `E6_heading_structure` | `h1` count ≠ 1 | Extractors use heading hierarchy to decide what a passage is about. |
| `E7_zoom_disabled` | `user-scalable` is `no`/`0`, or `maximum-scale` parses below `2` | Direct WCAG 1.4.4 (Resize Text) failure: the criterion asks for 200%, so the threshold is `< 2`, not `== 1`. Parse the directives — `maximum-scale=10` *contains* the string `maximum-scale=1` but permits 10x zoom, and `user-scalable=0` disables zoom without containing `no`. Kept at medium, not high: iOS Safari has ignored these directives since iOS 10, so the harm is real but not universal, and a map or drawing canvas may suppress pinch deliberately. |
| `E9_promise_payoff_mismatch` | **zero** distinctive title terms appear in body text | Deliberately extreme. Any softer threshold (semantic overlap, embedding distance) has an undefined false-positive rate on legitimate pages with brand-only titles. Zero overlap is near-unambiguous. |

## Deliberately NOT checked

| Excluded | Reason |
|---|---|
| Presence of a consent banner | Legally mandated under ePrivacy/GDPR. Flagging presence is a false positive on essentially every EU-facing site. Only a banner that *blocks content extraction* matters, and that surfaces as a Gate-2 readability finding instead. |
| Core Web Vitals (LCP / CLS / INP) | Field metrics at the 75th percentile. A single synthetic fetch is not a measurement; headless CLS without scrolling misses most real shifts; **INP cannot be measured synthetically at all**. |
| Colour contrast | Requires computed styles, therefore a browser. Reported in `checks_skipped[]` with the remedy (axe DevTools / Lighthouse) rather than faked from inline styles. This is the single most unarguable number we lose by not shipping a browser, and we say so. |
| "Above the fold" | ~85% of users scroll past the first viewport, and viewport diversity makes any fixed threshold arbitrary. |
| Action-verb CTA detection | An English verb list fails on non-English sites, on noun CTAs ("Pricing", "Free trial") and on icon buttons. Replaced by structural affordance detection (`E3`). |
| "CTA is an image" | `<a><img alt="…"></a>` is valid and accessible. No reliable detector exists. |
| Bounce rate | Conflates satisfied and dissatisfied exits. GA4 deprecated it for that reason. For AI-sourced traffic the residual click is usually *verification*, so a short visit is often the desired outcome. |
| Dead-end pages (no outbound internal links) | Fires on intentional landing pages, one-pagers and contact pages. Would need archetype gating we do not yet trust. |
