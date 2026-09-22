# Before vs after fixes 1-3 (same 100 sites, live re-crawl, 2026-09-12)

Baseline: `../2026-09-12-100` on commit 5caafe2. After: uncommitted v4 with
(1) B1 obligations need commerce evidence, contact obligation only on the contact page itself;
(2) bot-challenge detection in the crawler; (3) noindex critical only on key pages or most of the crawl.
Per-site detail: `compare.json` (produced by `compare.py`).

## Severe (active critical/high) findings

| | before | after |
|---|---|---|
| total | 59 | 39 |
| confirmed true or true-as-measured | 31 | 31 |
| false or overstated | 22 | 2 |
| A1 publisher-block posture (decision pending) | 6 | 6 |
| precision excluding A1 posture | ~58% (unchecked rows assumed true) | SUPERSEDED, see Verification |

"True-as-measured" covers the A7 rows: a named challenge vendor or a 403 was actually served to our crawler.
The spot-check join keys on site+check, so notion's remaining B1 (on /contact-sales, verified true)
shows as "false" in `compare.json`; it is counted as true here.

## What each fix removed
- **Fix 1 (B1 evidence):** carvana, cliffordchance, smittenkitchen, pfizer, mistral, rhs, metoffice, linear, notion feature page, govuk contact directory. bfi and webflow moved to script-only (medium).
- **Fix 2 (bot challenge):** boots and nypl no longer report a critical noindex read off an Incapsula interstitial; they get "Site serves a bot-challenge page". curl.se is no longer reported blocked (the robots.txt timeout did not recur on this run; the crawler bug itself is not fixed).
- **Fix 3 (noindex):** ethz, govuk, gymshark, webflow now "confirm intent". msf stays critical (9 of 12 pages).

## What got worse
- **True findings lost (5):** bbc and glastonbury contact hubs, compass contact page, webflow B1 (now medium script-only), wework noindex (wework's homepage was challenged by Cloudflare this run, so nothing was readable).
- **Coverage:** stopping at the first challenge cut britannica and puregym from 12 to 9 pages.
- **Run status:** failed went 10 to 14 (final: 69 complete, 13 partial, 14 failed, 4 blocked) because challenged sites are now reported as failed instead of fake "complete" (boots, nypl) or partial crawls of challenge assets (easyjet).
- **Found during the re-run and fixed:** glastonbury's real homepage loads the Incapsula script and was misread as a challenge. A vendor marker now counts only on a page with under 60 words of text; a challenge title still counts alone. Re-crawled: complete, 4 ordinary findings.

## Still open
- framer A2 (data-nosnippet on a brand-links block) and msf A3 critical, both not in scope of these fixes.
- A1 posture for named publisher blocks (bbc, thehindu, spiegel, bhaskar, wikihow, npr): awaiting a decision.
- Crawler bugs from the baseline evaluation: robots.txt retry, Crawl-delay page budget, relative sitemap URLs, 403 bursts, tracking-param duplicates, A1 when our own UA is blocked; C2/A11/E1 flooding.

## Robustness (evaluate.py, final)
100/100 reports schema-valid, counts consistent, IDs ordered, double replays deterministic.
Median 31 s, max 139 s. Only problem flagged: E1 repeated per template (glossier 9, thehoxton 5), unchanged from baseline.

## Verification against raw evidence (added after review)
The ~94% figure assumed every unchecked severe finding was true. Checked one by one, the 33 non-A1 severe findings after the fixes are:

| verdict | n | findings |
|---|---|---|
| true | 9 | duolingo, bluebottle, notion shells; aspendental entity-escaped JSON-LD; logitech, thehindu, msf missing facts; nyc.gov and nba block non-browser user-agents |
| true only from this machine | 9 | boots, nypl, easyjet, britishmuseum, mayoclinic, lemonade, tesla, powells, festool block a Chrome user-agent too, so the block may be on this IP, not on AI agents |
| uncertain | 4 | weworkremotely JSON-LD has raw newlines (strict JSON rejects, lenient parsers accept); lobste.rs robots allows only named search engines; jio times out for our UA only; notion B1 repeats its own empty-shell finding |
| false or overstated | 11 | wework (transient Cloudflare block, loads now); fnac (maintenance page); magalu (geo block); kraken, muji (network failure reported as robots block); supercell and websummit shells (404, gift and test pages); mcmaster noindex (duplicate alias URLs); zoho (sub-product contact page); framer nosnippet; msf noindex |

Precision is therefore 9 to 18 of 33 (27% to 55%), not 94%. The fixes still removed 18 false or overstated severe findings; the remaining errors come from checks the fixes did not touch.

Code-only replay (new code over the baseline bundles) changes 24 sites and confirms the fix effects above. One regression: bluebottle's two product pages are empty shells whose $45 price lives only in __NEXT_DATA__; the commerce-evidence rule reads visible text only, so B1_fact_script_only and C1_product_markup_absent are lost. Across all 27 pricing/product pages whose obligation was cleared, this is the only real price in a payload (article "4kr" and raycast "$1" are false).
