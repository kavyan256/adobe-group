---
name: engagement-audit
description: >-
  Detect on-site engagement risk factors from static markup — form friction,
  unnamed interactive controls, non-descriptive link text, missing image alt
  text, absent lang declaration, missing h1, disabled pinch-zoom, pages whose
  content shares no vocabulary with their own title, and content that offers no
  next step. Deliberately excludes bounce rate, lab performance metrics,
  consent-banner presence and colour contrast, which cannot be measured honestly
  without a browser or field data. Use standalone to answer "why don't visitors
  who arrive actually act?", or as the engagement half of a full AI-readiness
  audit.
license: Apache-2.0
allowed-tools: Bash, Read
---

# Engagement Audit

## When to use

When traffic arrives but doesn't act, or as the on-site half of `audit-orchestrator`.
A visitor from an AI answer often comes to verify one fact, so a short visit can be
a success. This skill therefore reports structural **risk factors** in the markup,
never inferred behaviour, and caps every finding at medium.

## Inputs

A site bundle, as a path argument or on stdin.

## Procedure

1. `<html>` without `lang` → `E5_no_lang`.
2. A form with more than five required fields, or any input without a programmatic
   label → `E1_form_friction`.
3. Three or more links, or 15% of links, reading "click here", "read more" and the
   like → `E2_vague_link_text`.
4. Three or more buttons or links with no accessible name from text, `aria-label`,
   `title` or image `alt` (language-neutral) → `E3_unnamed_controls`.
5. Three or more images, or 30%, with no `alt` attribute → `E4_images_missing_alt`.
   `alt=""` is a correct decorative declaration, not a defect.
6. No `h1` → `E6_heading_structure`. `user-scalable=no`, or `maximum-scale` below 2
   (WCAG 1.4.4) → `E7_zoom_disabled`.
7. None of the distinctive words in the title and meta description appear in the
   body → `E9_promise_payoff_mismatch`.
8. A non-legal page of 200+ words whose content (nav, header, footer and aside
   removed) has no internal link, form, `tel:` or `mailto:` → `E10_no_next_step`.
9. Record colour contrast and Core Web Vitals in `checks_skipped[]`, naming the tool
   that can measure each.

```bash
python3 scripts/check_engagement.py bundle.json
```

## Output

`{"findings": [...], "checks_skipped": [...]}`

## References

- `references/engagement-checks.md` — each threshold and its mechanism, and what is
  deliberately not checked
