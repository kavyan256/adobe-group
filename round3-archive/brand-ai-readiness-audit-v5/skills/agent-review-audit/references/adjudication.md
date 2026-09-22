# Adjudicating scripted findings

The scripts measure reproducibly, but they cannot tell what a page is for, whether a
failure was the site's or the auditor's, or whether a setting is deliberate. You can,
by reading the crawl. A verdict changes the report only when `verify_verdicts.py`
confirms every piece of evidence it cites; a verdict that does not hold changes nothing.

## Order

Take every finding in `scripted_findings` at `medium` or above, most severe first.
For each one, read its `evidence`, then open its affected pages in `profile.json`
(`status`, `title`, `h1`, `headings`, `text_excerpt`, `robots_directives`, `canonical`,
`links`, `forms`) and `site.notes` / `site.coverage`. Ask the questions below in order;
the first one that applies decides the verdict. Judge each finding on its own.

## Questions

1. **Did the audit fail rather than the site?** `site.notes` names a transport error
   (`ConnectError`, `ConnectTimeout`, `ReadTimeout`, an SSL error) and no page was read.
   A transport error is not an answer from the site, so it proves nothing about the site.
   → `not_a_defect`, `auditor_side_failure`. Evidence: `site_note_contains` the error name.
   An HTTP status (403, 429, 503) *is* an answer: go on to question 2.
2. **Is a refusal something other than a wall aimed at bots?** The refused page's own
   body says the site is under maintenance, or that it is unavailable where the request
   came from. → `confirm_intent`, `access_block_not_bot_specific`. Evidence:
   `html_contains` that phrase on the refused URL.
   A refusal the crawl cannot attribute (a named challenge vendor with no body left, or
   a bare 403) may target bots or only the auditor's network. → `downgrade`,
   `access_block_unattributed`. Evidence: `site_field` or the page's `status`/`title`.
3. **Is the page an error, test or placeholder page?** Its title, H1 or text says the
   page was not found, is a test or staging page, or is a placeholder. A defect on such a
   page costs nothing. → `not_a_defect` for those URLs, `error_or_placeholder_page`.
   Evidence: `text_contains` or `field title contains` on each URL you clear.
4. **Does the page's real purpose carry the obligation the check assumed?** A check
   that expects a price, a phone number or product markup inferred the page's role
   from its URL or title. A listing hub, a newsletter sign-up, a support page for one
   sub-product, or an article *about* a subject owes what that kind of page owes, not
   what a shop or head-office contact page owes. → `not_a_defect` for those URLs,
   `page_purpose_mismatch`. Evidence: the title, H1 or text that shows the purpose.
5. **Is the measurement itself wrong?** Before trusting an "absent" or "missing"
   finding, actively search for the thing it says is missing: `text_contains` or
   `html_contains` the price, phone number, link text or fact on the pages it names,
   not just a skim of the excerpt. A finding is proven wrong by finding the very thing
   it says is not there — a price the crawl's own pricing parser missed, an onward link
   that exists but was not the one the check counted, a fact stated in different words
   than the check searched for. A matched "phone number" that is really a map
   coordinate or a number from an SVG path is the same failure the other way. →
   `not_a_defect`, `measurement_wrong`. Evidence: `html_contains` or `text_contains`
   the context around the value, or the fact itself, on the page the finding names.
6. **Is an indexing directive deliberate?** Only for findings that read an indexing or
   access directive (`A2` snippet suppression, `A3` noindex, `A5` canonical): the
   directive is confined to duplicate, translated, archived, member-only or utility
   pages while the key pages stay open. A usability or markup defect (zoom disabled,
   missing labels, missing markup) is never "deliberate", however few pages it is on.
   → `confirm_intent`, `deliberate_configuration`. Evidence: a positive assertion that
   shows what the affected pages are (their titles or text), plus, where it helps, a key
   page whose `robots_directives` lacks the directive.
   Do not use this for robots.txt rules that name AI agents: that posture is judged by
   the scripted check and left as reported.
7. **Is it the same problem as another finding on the same page?** A missing fact on a
   page that another finding already reports as empty. → `not_a_defect`,
   `duplicate_of_finding`. Evidence: `finding_exists` naming the other finding.
8. **Is the impact overstated?** Before confirming, compute the actual proportion the
   finding's own evidence implies: 3 of 195 controls, or 1 of 40 images, is a handful
   out of many, whatever the raw count says. A brand-entity or corroboration finding on
   a personal, single-author or non-commercial site carries little weight — nobody is
   deciding whether to trust "the brand" of somebody's blog. A stale-looking page that
   is explicitly an archive, a past event or a superseded version is expected to look
   old. Any of these → `downgrade`, `overstated_impact`. Not allowed on a critical
   finding. Evidence: a positive assertion showing the actual scope (the ratio, or the
   site's own words for what kind of page or site this is).
9. **Otherwise it stands.** Confirming is not the default: it is what is left after 5
   and 8 were actively checked and did not apply, not what happens when nothing
   contrary was noticed. → `confirm`, `measurement_confirmed`, with one positive
   assertion that shows the defect on an affected page.

## Never

- Clear a finding because the fix looks hard, or because the site is well known.
- Use knowledge from outside the crawl about what a site is usually like.
- Clear a page you have not opened in `profile.json`.
- Resubmit a rejected verdict with weaker evidence.

## Verdict format

Verdicts go in `WORK/claims.json` next to `claims` and `fixes`:

```json
{
  "verdicts": [
    {
      "finding": {"check_id": "B4_empty_shell", "url": "https://example.com/404"},
      "verdict": "not_a_defect",
      "reason": "error_or_placeholder_page",
      "urls": ["https://example.com/404"],
      "explanation": "The page is the site's not-found page, so its lack of content costs nothing.",
      "evidence": [
        {"url": "https://example.com/404", "type": "field", "path": "title", "op": "contains", "value": "Page not found"}
      ]
    }
  ]
}
```

| Field | Rule |
|---|---|
| `finding` | `check_id` of a scripted finding, and `url`, one of its affected URLs (required when two findings share a `check_id`). |
| `verdict` / `reason` | One of the pairs below. |
| `urls` | For `not_a_defect` with a page reason: the affected URLs you clear (default: all). A finding with no URLs left is removed. |
| `explanation` | 20–600 characters, plain text. |
| `evidence` | 1–12 assertions; all must hold. |

| `reason` | `verdict` | Allowed on | Effect | Evidence rule |
|---|---|---|---|---|
| `measurement_confirmed` | `confirm` | any | none; marked confirmed | one positive assertion |
| `overstated_impact` | `downgrade` | any but critical | one band lower, never below low | one positive assertion showing the limited scope |
| `access_block_unattributed` | `downgrade` | A7 | one band lower | one positive assertion |
| `access_block_not_bot_specific` | `confirm_intent` | A7 | status confirm_intent, severity low | one positive assertion |
| `deliberate_configuration` | `confirm_intent` | A2, A3, A5 | status confirm_intent, severity low | one positive assertion |
| `error_or_placeholder_page` | `not_a_defect` | any | cleared URLs removed | a positive assertion on every cleared URL |
| `page_purpose_mismatch` | `not_a_defect` | any | cleared URLs removed | a positive assertion on every cleared URL |
| `measurement_wrong` | `not_a_defect` | any | cleared URLs removed | every cleared URL named, plus one positive assertion; a site-wide one counts only if its value names a cleared page's path or the value the finding quoted |
| `auditor_side_failure` | `not_a_defect` | A7 | finding removed | `site_note_contains` a transport error, and no page was read |
| `duplicate_of_finding` | `not_a_defect` | any | finding removed | `finding_exists` naming the other finding |

The verifier rejects a reason used outside its "Allowed on" checks.

## Evidence types

All the page assertions of `claim-format.md` (`html_contains`, `text_contains`,
`field`, …). `html_contains` / `html_lacks` also work on a refused page whose body was
kept (a 403 maintenance page). Three more:

| `type` | Fields | Holds when |
|---|---|---|
| `site_note_contains` | `value` | the crawl notes contain `value` |
| `site_field` | `path` (`run_status`, `coverage.pages_ok`, `coverage.pages_fetched`, `robots.status`), `op`, `value` | the crawl-level field satisfies `op` |
| `finding_exists` | `check_id`, `url` | another finding with that `check_id` lists `url` |
