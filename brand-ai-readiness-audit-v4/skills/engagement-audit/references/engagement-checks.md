# Engagement checks: thresholds, mechanisms, and what was cut

Every check must yield **a number and a selector** that a non-expert can verify in
thirty seconds: "14 required fields, 6 with no label" qualifies; "above-fold text
is 12 words" does not (Apple and Stripe would both fail it). All findings but `E11`
are `static_heuristic` and therefore capped at medium — risk factors inferred from
markup, never observed behaviour. `E11` is the one `static_fact` here: the viewport
tag is present or it is not, so it is `deterministic` and not capped.

## Checks that ship

| Check | Threshold | Mechanism |
|---|---|---|
| `E1_unlabelled_input` | any input/select/textarea with no `<label for>`, wrapping `<label>`, `aria-label`, `aria-labelledby` or `title`; deduplicated per form **template** (same `action` + same field names), every page carrying it listed in `affected_urls` | An unlabelled input is ambiguous to a screen reader and to any agent. **Placeholder-only** fields count only when `required`: the accessible-name algorithm falls back to the placeholder, but it vanishes exactly when the user must get the value right. An optional placeholder-only search box is not reported. A footer newsletter box on every page is therefore one finding, not "friction on N pages". |
| `E1_form_friction` | a **conversion form** (action, id, or a field name/id containing contact, demo, quote, signup, sign-up, register, checkout, order, apply) with >5 required fields or >8 visible fields (hidden/submit/button/image/reset excluded) | Completion drops sharply past about five required fields. Restricted to conversion forms so a faceted filter or a settings panel with many controls does not fire. |
| `E2_vague_link_text` | ≥3 links, or ≥15% of links, from a fixed vague-phrase set, and no descriptive `aria-label` or `title` on the link | Non-descriptive links defeat scanning and tell assistants nothing about the destination. A "Read more" whose `aria-label` names the article is fine: that is the accessible name. |
| `E3_unnamed_controls` | ≥3 controls with an empty accessible name | The accessible name — from text, `aria-label`, `aria-labelledby` (resolved to the referenced elements' text), `title`, an SVG `<title>` child or child `img alt` — is spec-defined and **language-neutral**, unlike action-verb matching. Controls carrying framework binding attributes (any attribute starting with `:`, `v-`, `x-`, `ng-`, `@`, `[` or `data-bind`) are **assumed named at runtime** and skipped: Vue's `v-text`/`:aria-label`, Alpine's `x-text`, Angular's `[attr.aria-label]` and Knockout's `data-bind` all inject the name after hydration, which this audit does not run. The evidence says so. |
| `E4_images_missing_alt` | ≥3 content images, or ≥30%, with no `alt` attribute at all | `alt=""` correctly marks decoration; a missing attribute does not. Not counted: images inside `<noscript>` (analytics fallbacks), `role="presentation"`/`"none"`, `aria-hidden`, and tracking pixels (`width` or `height` ≤ 2, or `src` containing `pixel`, `beacon` or `track`). A fact carried only in an image is also invisible to retrieval agents, so this hurts discoverability too. |
| `E5_no_lang` | `<html>` has no `lang` | Affects screen-reader pronunciation and how any consumer processes the text. |
| `E6_heading_structure` | no `h1` on the page | Extractors use the top heading to decide what a page is about. Several `h1`s are legal HTML5 and are not reported. |
| `E7_zoom_disabled` | `user-scalable` is `no`/`0`, or `maximum-scale` below `2` | WCAG 1.4.4 asks for 200% zoom, so the threshold is `< 2`. Directives are parsed, not substring-matched: `maximum-scale=10` contains `maximum-scale=1`. Medium, not high: iOS Safari ignores these directives, and a map may suppress pinch deliberately. |
| `E11_no_viewport` | no `<meta name="viewport">` element at all | **A fact, not a heuristic.** Without the tag, mobile browsers lay the page out at about 980px and shrink it, so text is unreadable until the visitor pinch-zooms. Does not fire when the tag exists; a restrictive one is `E7`'s job. `static_fact`, `deterministic`, base medium: the page is still usable after a zoom, so not high. |
| `E9_promise_payoff_mismatch` | **zero** distinctive title/description terms in the body | Deliberately extreme: any softer overlap threshold has an undefined false-positive rate on brand-only titles. |
| `E10_no_next_step` | a non-legal page of 200+ words whose content (nav, header, footer, aside removed) has no internal link **to another page**, form, `tel:` or `mailto:` | A visitor from an AI answer lands mid-site. A site-wide nav is identical on every page, so it says nothing about where this page should lead. Anchors whose `href` is `#…` ("Back to top"), `javascript:`, empty, or the page's own URL are not routes onward. Legal pages are legitimately terminal. |
| `E12_no_orientation` | a non-home page of 100+ words with neither `<title>` nor `h1`, **or** whose `h1` is identical to the homepage's `h1` on 3+ pages | The visitor reads title and top heading first to confirm they landed in the right place. One brand slogan as the h1 of every page gives no such confirmation. Base low: a visible breadcrumb or nav highlight the audit cannot see may already orient them. |

## Deliberately not checked

Each of these is listed in `checks_skipped[]` in the form *Not assessed: X. Reason: Y.
How to check it yourself: Z.* so a reader knows the gap and how to close it.

| Excluded (`check` id) | Reason |
|---|---|
| Consent-banner presence | Legally mandated under ePrivacy/GDPR; flagging it would fire on nearly every EU-facing site. |
| Core Web Vitals (`E_core_web_vitals`) | Field metrics at the 75th percentile. One synthetic fetch is not a measurement, and INP cannot be measured synthetically at all. |
| Colour contrast (`E_colour_contrast`) | Needs computed styles, therefore a browser. axe DevTools / Lighthouse cover it. |
| Behaviour metrics (`E_behaviour_metrics`) | Bounce, dwell, scroll depth and conversion are observed, not inferred from markup — and for AI-sourced traffic the click is often verification, so a short visit is frequently the desired outcome. Segment analytics by AI referrer and compare conversion, not bounce. |
| Rendered experience (`E_rendered_experience`) | Overlay and cookie-banner timing, tap-target size, focus visibility and layout at phone width all depend on CSS and JS executing. Run Lighthouse/axe on the top 3 templates. |
| Copy quality, persuasion, jargon (`E_copy_quality`) | Subjective; no static threshold separates plain language from marketing copy across industries and languages. |
| Authenticated flows (`E_authenticated_flows`) | The audit is read-only and never logs in, submits a form or creates an account. |
| "Above the fold" | Most users scroll, and viewport diversity makes any fixed threshold arbitrary. |
| Action-verb CTA detection | An English verb list fails on other languages, noun CTAs and icon buttons; `E3` tests affordance structurally instead. |
| "CTA is an image" | `<a><img alt="…"></a>` is valid and accessible; there is no reliable detector. |

When zero pages return readable HTML the skill emits no findings and adds an
`engagement-audit` entry to `checks_skipped[]`, so a blocked site never reads as
"no engagement problems".
