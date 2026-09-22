# 100-site evaluation — brand-ai-readiness-audit-v4 (commit 5caafe2)

Run: 2026-09-12, scripted audit only (`--max-pages 12`, 6 parallel workers, one host each).
Sites: `sites.json` — 100 sites, 100 distinct categories, none used earlier in development.
Per-site output: `results/<slug>/` (`<slug>.report.json`, `<slug>.bundle.json`, `run.json`).
Mechanical summary: `evaluation.json`. Hand verdicts: `spot_checks.json`.

## 1. Robustness and report integrity — passed

| Check | Result |
|---|---|
| Crashes / non-zero exits | 0 of 100 |
| Reports written | 100 of 100 |
| Runtime | median 35 s, max 166 s (hdfcbank) — all under 300 s |
| Schema validation | all 100 valid |
| Severity counts add up to `total_findings` | all 100 |
| IDs in ranked order, no duplicate URLs | all 100 |
| Determinism (each saved crawl replayed twice) | all identical |
| Run status | 70 complete, 15 partial, 10 failed, 5 blocked |
| Findings per readable site | median 4, max 14 (glossier) |

## 2. Accuracy of the most severe findings — needs work

Every high and critical finding family was checked against the saved pages
(49 findings). About **29 were correct and 20 were false or overstated (~59% precision)**.

| Check (severity) | Correct | False / overstated | What went wrong |
|---|---|---|---|
| B1 fact absent (high, 21 sites) | 10 | **11** | URL-based page roles obligate facts that the page never owes: `/products/…` on SaaS and pharma (notion, mistral, pfizer), `/plan` feature page (linear), `/buy` category hub (carvana), `/subscribe` newsletter pages (cliffordchance, smittenkitchen), `/shop/` sections (rhs), a contact *directory* (gov.uk) and an office-directions sub-page (metoffice). bfi's email sits in a script payload the island list does not cover, so "absent" should be "script only". |
| A3 noindex (critical, 9 sites) | 2 | **7** | Deliberate noindex on generic pages reported as critical: user profiles (webflow), tribunal decisions (gov.uk), reward pages (msf), teaser fragments (ethz), pagination (gymshark). boots and nypl returned **bot-challenge pages with HTTP 200** ("Pardon Our Interruption", an empty Incapsula page) that carry noindex, and were analysed as the real homepage. |
| A1 AI crawlers blocked (critical, 6 sites) | 6 (facts) | posture | bbc, npr, thehindu, wikihow, bhaskar, spiegel block OpenAI/Perplexity/Claude agents **by name** — a deliberate publisher policy. Reported as critical defects because blocking OAI-SearchBot is never treated as deliberate. Decision needed, not a code bug. |
| A7 site unreadable (critical, 5) | 4 | **1** | curl.se: one robots.txt timeout was treated as "disallow everything"; it answers 200 in 0.5 s on retry. lobste.rs is really blocked, but the report never says that every AI crawler except Googlebot is blocked (A1 is skipped). |
| B4 empty shell (high, 5) | 5 | 0 | — |
| C1 invalid JSON-LD (high, 2) | 2 | 0 | HTML-escaped JSON (aspendental), raw control characters (weworkremotely). |
| A2 snippet suppressed (high, 1) | 0 | **1** (likely) | framer: `data-nosnippet` on a "Links: Brand" block. |
| A7 403 bot protection (high, 10) | 10 | 0 | Correct and clearly explained. |

Medium and low checks sampled:

| Check | Verdict |
|---|---|
| C3 no sameAs (62% of sites) | Correct on the 3 checked (bbc, nature, britannica). Common because it is common. |
| C2 price contradiction (2) | **Both false**: price shown outside the extracted text area (glossier), price "0" for a free offer (bhaskar). |
| A11 soft 404 (2) | supercell `/404` correct; **wikihow "0404 Angel Number" false** ("404" matched inside a word). |
| E1 unlabelled input | Correct fields, but **one finding per form template**: glossier lists it 9 times, thehoxton 5 — report flooding. |

## 3. Crawler bugs found

1. A single robots.txt timeout marks the whole site blocked (curl.se).
2. A long `Crawl-delay` *raises* the page budget above `--max-pages` (thisamericanlife, visitportugal: 20 instead of 12).
3. Relative `Sitemap: /sitemap.xml` lines fail with UnsupportedProtocol (tfl, thehoxton).
4. Bot-challenge pages returned with HTTP 200 are analysed as real pages (boots, nypl).
5. After some successes, a run of HTTP 403 does not stop the crawl (strava: 8 more requests).
6. Tracking parameters create duplicate pages (webflow `?utm_source=` copy of contact-sales).

## 4. Ranked fixes

| # | Fix | Removes |
|---|---|---|
| 1 | B1: obligate price only with commerce evidence (Product/Offer markup, add-to-cart form, `og:type product`, or pricing words in title/h1); drop URL-only `subscribe`/`buy`/`plan`/`shop`/`store`; contact obligation only on the contact page itself, not directories or sub-pages; search all `<script>` JSON before declaring a fact absent | ~11 false high findings |
| 2 | Detect bot-challenge pages (Incapsula, Cloudflare, Akamai, PerimeterX, DataDome markers, empty 200) → report as refusal, skip analysis | false critical A3 on homepages |
| 3 | A3: critical only for home/pricing/product/about/contact pages or noindex on most pages; otherwise confirm_intent | ~7 false critical findings |
| 4 | Crawler: retry robots.txt once; cap page budget at `--max-pages`; resolve relative sitemap URLs; stop on 3 consecutive 403s; strip tracking parameters; emit A1 when our own UA is robots-blocked | crawler bugs 1–3, 5, 6 |
| 5 | C2: compare against full text, skip price 0 · A11: "404" as a standalone token · A2: data-nosnippet only on h1/main/article · E1: one finding per site listing templates | smaller false positives, flooding |
| 6 | Decide A1 posture for named publisher blocks of OpenAI/Perplexity | 6 critical findings that read as accusations |

Checks that never fired in 100 sites: A3_noindex_utility, A8_robots_token_unrecognised,
C6_entity_name_conflict, D4_internal_contradiction (and R_agent_review, as no agent review ran).
