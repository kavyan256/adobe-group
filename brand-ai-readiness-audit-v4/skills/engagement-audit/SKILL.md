---
name: engagement-audit
description: >-
  Detect on-site engagement risk factors from static markup — unlabelled form
  fields, long conversion forms, unnamed interactive controls, non-descriptive
  link text, missing image alt text, absent lang declaration, missing h1, no
  viewport meta tag, disabled pinch-zoom, pages whose content shares no
  vocabulary with their own title, content that offers no next step, and deep
  pages that give the visitor no orientation (no title/h1, or the homepage's
  h1 repeated). Deliberately excludes bounce rate, dwell time, Core Web Vitals,
  colour contrast, overlay timing, copy quality and anything behind a login,
  which cannot be measured honestly without a browser, field data or a human.
  Runs on its own against a bundle from audit-orchestrator to answer "why don't
  visitors who arrive actually act?", or as the engagement half of a full
  AI-readiness audit.
license: Apache-2.0
allowed-tools: Bash Read
compatibility: Python 3.10+, httpx, beautifulsoup4
---

# Engagement Audit

## When to use

When traffic arrives but doesn't act, or as the on-site half of `audit-orchestrator`.
A visitor from an AI answer often comes to verify one fact, so a short visit can be
a success. This skill therefore reports structural **risk factors** in the markup,
never inferred behaviour. Every check but `E11` is a heuristic capped at medium;
`E11` is a plain fact about the markup.

## Inputs

A site bundle, as a path argument or on stdin.

## Procedure

1. `<html>` without `lang` → `E5_no_lang`.
2. A form field with no `<label for>`, wrapping label, `aria-label`, `aria-labelledby`
   or `title` → `E1_unlabelled_input`, once per form **template** (same action and
   field names), with every page that carries it in `affected_urls`. A
   placeholder-only field counts only when it is `required`.
3. A conversion form (action or a field name/id containing contact, demo, quote,
   signup, register, checkout, order or apply) with more than five required fields
   or more than eight visible fields → `E1_form_friction`.
4. Three or more links, and at least 15% of links, reading "click here", "read more" and the
   like, with no descriptive `aria-label` or `title` → `E2_vague_link_text`.
5. Three or more buttons or links with no accessible name from text, `aria-label`,
   `aria-labelledby`, `title`, SVG `<title>` or image `alt` → `E3_unnamed_controls`.
   Controls carrying framework binding attributes (`v-`, `x-`, `ng-`, `:`, `@`, `[`,
   `data-bind`) are assumed named at runtime and skipped.
6. Three or more content images, and at least 30%, with no `alt` attribute →
   `E4_images_missing_alt`. `alt=""` is a correct decorative declaration; tracking
   pixels, images inside `<noscript>`, `role="presentation"` and `aria-hidden` do not count.
7. No `h1` → `E6_heading_structure`.
8. No `<meta name="viewport">` at all → `E11_no_viewport` (deterministic, static
   fact). One that sets `user-scalable=no` or `maximum-scale` below 2 (WCAG 1.4.4)
   → `E7_zoom_disabled`.
9. None of the distinctive words in the title and meta description appear in the
   body → `E9_promise_payoff_mismatch`.
10. A non-legal page of 200+ words whose content (nav, header, footer and aside
    removed) has no internal link to another page, form, `tel:` or `mailto:` →
    `E10_no_next_step`. Anchors to `#…`, `javascript:` or the page itself do not count.
11. A non-home page of 100+ words with neither title nor h1, or whose h1 equals the
    homepage's h1 on three or more pages → `E12_no_orientation`.
12. Record everything not assessed in `checks_skipped[]`, each entry saying what,
    why, and how to check it yourself.
13. If no page returned readable HTML, emit no findings and add an
    `engagement-audit` entry to `checks_skipped[]` saying so.

```bash
python3 scripts/check_engagement.py bundle.json
```

## Output

`{"findings": [...], "checks_skipped": [...]}`

## Interpreting results

Every E finding except `E11` is a markup heuristic; downgrade or drop one when the page's purpose explains it:

- `E1_unlabelled_input`: drop if the only field is a search box beside a visible button; keep for a required email or payment field.
- `E3_unnamed_controls`: drop if names are injected by a JS framework the check did not recognise (the evidence says which prefixes were skipped); keep for plain icon `<button>`s.
- `E4_images_missing_alt`: downgrade to low when the images are gallery thumbnails with the product name in adjacent text.
- `E9_promise_payoff_mismatch`: drop when the title is a brand slogan and the body addresses the subject in other words.
- `E10_no_next_step`: drop for a legitimately terminal page — a thank-you or confirmation page, or a contact page whose route is the phone number in the header.
- `E12_no_orientation`: downgrade when a visible breadcrumb or highlighted nav item orients the visitor although title and h1 do not.

Thresholds and mechanisms for each: `references/engagement-checks.md`.

## References

- `references/engagement-checks.md` — each threshold and its mechanism, and what is
  deliberately not checked
