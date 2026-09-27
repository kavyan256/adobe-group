# Sites checked for the Round 4 demo

Scripted pass only (`--max-pages 12`) unless the verdict says hand-checked. Verdicts come from checking findings against the live sites.

**147 sites screened** (93 complete, 35 partial, 10 failed, 9 blocked); arduino.cc was also run with the full skill 3 times.


## Round 4 screening 1 (2026-09-22/23): 15 sites

| site | status | pages | findings | verdict |
|---|---|---|---|---|
| archlinux.org | blocked | 0/1 | C1 H0 M0 L0 | blocked or failed |
| arduino.cc | complete | 12/12 | C0 H1 M3 L5 | ❌ REJECTED: F-001 high overstated; contact page is form-only and contacts exist elsewhere. Other findings true |
| blender.org | complete | 12/12 | C0 H0 M1 L1 | ✅ CLEAN: all 5 true (3 agent, e.g. 2010 press releases dated 2024); no engagement findings |
| cred.club | partial | 11/12 | C0 H0 M3 L6 | screened only |
| ghost.org | complete | 12/12 | C0 H0 M4 L1 | ✅ CLEAN: all 8 true (5 scripted + 3 agent, e.g. "\"Isaac Saul\"" JSON-LD); headline C3 medium |
| groww.in | complete | 12/12 | C1 H0 M2 L3 | ❌ REJECTED: critical noindex on legal pages (arguably deliberate) |
| gutenberg.org | blocked | 0/1 | C1 H0 M0 L0 | blocked or failed |
| instructables.com | blocked | 0/1 | C1 H0 M0 L0 | blocked or failed |
| meesho.com | failed | 0/1 | C1 H0 M0 L0 | blocked or failed |
| obsidian | complete | 12/12 | C0 H1 M3 L5 | screened only |
| obsidian.md | complete | 12/12 | C0 H1 M3 L5 | ❌ REJECTED: A2 false positive (data-nosnippet on aria-hidden UI mockups) |
| openlibrary.org | blocked | 0/1 | C1 H0 M0 L0 | blocked or failed |
| raspberrypi.com | failed | 0/1 | C0 H1 M0 L0 | blocked or failed |
| swiggy.com | failed | 0/1 | C0 H1 M0 L0 | blocked or failed |
| zomato.com | blocked | 0/1 | C1 H0 M0 L0 | blocked or failed |

## Screening 2 (2026-09-25): 20 sites

| site | status | pages | findings | verdict |
|---|---|---|---|---|
| digikey.in | failed | 0/1 | C0 H1 M0 L0 | blocked or failed |
| espressif.com | complete | 20/20 | C0 H0 M5 L6 | ⚠️ WEAK: 4 search-box E1; Crawl-delay pushed the crawl to 20 pages |
| fairphone.com | partial | 8/13 | C1 H0 M6 L4 | screened only |
| frame.work | failed | 0/1 | C0 H1 M0 L0 | blocked or failed |
| freecodecamp.org | complete | 12/12 | C0 H0 M3 L2 | ⚠️ MIXED: homepage has no <title> (true); D1 fires on donation/wallpaper pages, not articles |
| gimp.org | complete | 12/20 | C0 H0 M3 L2 | ❌ REJECTED: search box flagged on every page |
| inkscape.org | complete | 5/5 | C0 H0 M3 L5 | ⚠️ WEAK: only 5 pages; relies on E12 |
| kicad.org | complete | 12/12 | C0 H1 M2 L2 | ❌ REJECTED: contact page has no phone/email by design (links to issue tracker) |
| libreoffice.org | complete | 12/12 | C0 H0 M3 L4 | ❌ REJECTED: E10 false (/for-business has content links) |
| mozilla.org | complete | 12/12 | C0 H1 M2 L3 | ❌ REJECTED: A2 false positive (data-nosnippet on the cookie banner) |
| openstreetmap.org | partial | 9/15 | C0 H0 M4 L5 | screened only |
| pimoroni.com | blocked | 0/1 | C1 H0 M0 L0 | blocked or failed |
| postgresql.org | complete | 12/12 | C0 H0 M4 L4 | ❌ REJECTED: findings on /include/topbar, an HTML fragment |
| practo.com | complete | 12/12 | C0 H1 M4 L7 | ❌ REJECTED: B1 reads "0.931307" as a phone number |
| prusa3d.com | complete | 12/16 | C0 H0 M2 L2 | ⚠️ WEAK: only 4 findings |
| raspberrypi.org | partial | 5/6 | C0 H0 M3 L2 | screened only |
| seeedstudio.com | partial | 3/12 | C0 H0 M4 L4 | screened only |
| sparkfun.com | partial | 15/15 | C0 H0 M0 L1 | screened only |
| sqlite.org | complete | 12/13 | C0 H0 M4 L6 | ⚠️ WEAK: same search box reported as 3 findings |
| zerodha.com | complete | 12/12 | C0 H0 M4 L2 | ❌ REJECTED: headline E10 on a legal consent page |

## Screening 3 (2026-09-25): 24 sites

| site | status | pages | findings | verdict |
|---|---|---|---|---|
| allbirds.com | partial | 11/12 | C0 H0 M2 L1 | screened only |
| astro.build | complete | 12/12 | C0 H0 M2 L1 | screened only |
| bose.com | partial | 11/12 | C0 H0 M5 L2 | screened only |
| chargebee.com | complete | 12/12 | C0 H0 M3 L2 | ⚠️ PARTLY CHECKED: E10 true, zoom disabled site-wide; discoverability side thin |
| decathlon.in | complete | 12/18 | C0 H0 M1 L1 | screened only |
| elastic.co | partial | 11/12 | C0 H1 M3 L2 | screened only |
| freshworks.com | complete | 12/12 | C1 H0 M2 L1 | ✅ STRONG: critical = /contact is noindex,nofollow (verified); E10 true on 3 event pages. Only 4 findings; HEAD returns 403 |
| go.dev | complete | 12/12 | C0 H0 M3 L2 | ✅ CLEAN: C3, no sitemap (404), social icons without alt/names; all true |
| hashicorp.com | failed | 0/1 | C0 H1 M0 L0 | blocked or failed |
| kotlinlang.org | complete | 12/12 | C0 H0 M1 L2 | screened only |
| mongodb.com | complete | 12/12 | C0 H0 M3 L1 | screened only |
| netlify.com | complete | 12/12 | C0 H0 M2 L1 | screened only |
| nodejs.org | partial | 11/12 | C0 H0 M2 L2 | screened only |
| patagonia.com | complete | 1/1 | C0 H0 M1 L3 | screened only |
| postman.com | complete | 12/12 | C1 H0 M3 L1 | ❌ REJECTED: E10 false on the noindexed page (it has 3 links) |
| python.org | complete | 12/12 | C0 H0 M2 L1 | screened only |
| razorpay.com | complete | 12/12 | C0 H2 M3 L3 | ❌ REJECTED: pricing page empty only to our UA (3,522 words with curl); C2 "INR 0" |
| redis.io | complete | 12/15 | C0 H0 M1 L4 | screened only |
| ruby-lang.org | complete | 12/12 | C0 H0 M3 L3 | ❌ REJECTED: findings on a meta-refresh redirect stub |
| rust-lang.org | complete | 12/12 | C0 H0 M2 L3 | screened only |
| svelte.dev | complete | 11/11 | C0 H0 M1 L5 | screened only |
| tailwindcss.com | complete | 8/8 | C0 H1 M2 L5 | screened only |
| typescriptlang.org | complete | 10/10 | C0 H0 M3 L4 | ❌ REJECTED: E10 false (page has a link) |
| vuejs.org | complete | 12/12 | C0 H0 M1 L1 | screened only |

## Indian sites (2026-09-25): 40 sites

| site | status | pages | findings | verdict |
|---|---|---|---|---|
| amul.com | blocked | 0/1 | C1 H0 M0 L0 | blocked or failed |
| bankbazaar.com | complete | 12/12 | C0 H0 M1 L1 | screened only |
| bewakoof.com | partial | 10/12 | C0 H1 M7 L2 | screened only |
| boat-lifestyle.com | partial | 11/12 | C0 H1 M2 L1 | screened only |
| browserstack.com | complete | 12/12 | C0 H0 M4 L2 | screened only |
| cashfree.com | complete | 12/12 | C0 H1 M2 L4 | ❌ REJECTED: E10 false (4 links); C1 is control-character class |
| cleartax.in | complete | 12/12 | C1 H0 M4 L2 | ✅ STRONG: critical = only pricing page is noindex + self-canonical (verified). ChatGPT still answered prices citing ClearTax; engine missed that the pricing HTML has no plan prices |
| clevertap.com | complete | 20/20 | C0 H0 M3 L5 | screened only |
| cult.fit | complete | 12/12 | C0 H2 M3 L1 | screened only |
| darwinbox.com | partial | 9/12 | C1 H0 M1 L3 | screened only |
| exotel.com | blocked | 0/1 | C1 H0 M0 L0 | blocked or failed |
| gupshup.io | complete | 12/12 | C0 H0 M1 L3 | screened only |
| hasura.io | complete | 12/12 | C0 H1 M2 L1 | screened only |
| infosys.com | failed | 0/1 | C0 H1 M0 L0 | blocked or failed |
| instamojo.com | complete | 12/12 | C0 H0 M4 L3 | screened only |
| isro.gov.in | complete | 12/12 | C0 H0 M1 L4 | screened only |
| ixigo.com | complete | 12/12 | C0 H0 M3 L5 | screened only |
| jupiter.money | partial | 10/12 | C0 H0 M3 L3 | screened only |
| kissflow.com | complete | 12/12 | C0 H1 M2 L2 | screened only |
| leadsquared.com | complete | 12/12 | C0 H0 M3 L1 | screened only |
| lenskart.com | partial | 10/12 | C0 H0 M3 L0 | screened only |
| licious.in | partial | 10/12 | C0 H1 M1 L2 | screened only |
| mamaearth.in | partial | 11/12 | C0 H1 M1 L1 | screened only |
| npci.org.in | failed | 0/1 | C0 H1 M0 L0 | blocked or failed |
| paytm.com | complete | 12/12 | C0 H1 M4 L1 | ❌ REJECTED: C2 "INR 0" and a search-box E1 |
| phonepe.com | complete | 12/12 | C0 H0 M0 L2 | screened only |
| policybazaar.com | failed | 0/1 | C0 H1 M0 L0 | blocked or failed |
| redbus.in | complete | 12/12 | C0 H0 M0 L2 | screened only |
| smallcase.com | complete | 12/12 | C0 H0 M2 L0 | screened only |
| sugarcosmetics.com | partial | 11/12 | C0 H1 M1 L1 | screened only |
| tata1mg.com | complete | 11/11 | C0 H0 M2 L2 | screened only |
| tatamotors.com | complete | 12/18 | C0 H0 M4 L2 | screened only |
| unacademy.com | complete | 12/12 | C0 H0 M1 L0 | screened only |
| upgrad.com | complete | 12/12 | C0 H0 M2 L0 | screened only |
| upstox.com | complete | 12/12 | C0 H0 M2 L2 | screened only |
| urbancompany.com | complete | 12/12 | C0 H0 M3 L4 | screened only |
| vedantu.com | complete | 12/12 | C0 H1 M4 L7 | ⚠️ MIXED: soft 404 on /vote, "© 2011", E10 true; headline C1 is the uncertain control-character class |
| vwo.com | complete | 1/1 | C0 H0 M3 L0 | screened only |
| wakefit.co | failed | 0/1 | C0 H1 M0 L0 | blocked or failed |
| whatfix.com | complete | 12/12 | C0 H1 M8 L5 | screened only |

## Indian startups (2026-09-25): 48 sites

| site | status | pages | findings | verdict |
|---|---|---|---|---|
| 100ms.live | complete | 12/12 | C0 H1 M4 L3 | screened only |
| appsmith.com | complete | 12/12 | C0 H0 M3 L3 | screened only |
| atlan.com | complete | 12/12 | C0 H0 M1 L0 | screened only |
| beardo.in | partial | 11/12 | C0 H1 M1 L1 | ✅ C1 certain: control character + missing comma. Partial crawl 11/12 |
| bebodywise.com | partial | 8/12 | C0 H1 M2 L1 | ⚠️ A9 facts true (4 products 410 but still in sitemap); discontinued products, so the real defect is a stale sitemap, not "high". Partial 8/12 |
| bluetokaicoffee.com | partial | 11/12 | C0 H1 M5 L3 | ✅ C1 certain: control character + missing comma. Partial crawl 11/12 |
| bombayshavingcompany.com | partial | 11/12 | C0 H0 M2 L3 | screened only |
| bummer.in | partial | 11/12 | C0 H0 M2 L2 | screened only |
| damensch.com | complete | 12/12 | C0 H0 M1 L2 | screened only |
| decentro.tech | complete | 12/12 | C0 H1 M1 L3 | ✅ C1 certain: JSON-LD HTML-escaped (&quot;); weak on engagement |
| dyte.io | complete | 12/12 | C0 H0 M2 L2 | screened only |
| eka.care | partial | 11/12 | C0 H0 M3 L3 | screened only |
| epigamia.com | complete | 12/12 | C0 H0 M3 L4 | screened only |
| fampay.in | partial | 5/6 | C0 H0 M4 L4 | screened only |
| hevodata.com | complete | 12/12 | C0 H1 M3 L1 | screened only |
| kapture.cx | complete | 12/12 | C0 H1 M5 L4 | screened only |
| khatabook.com | complete | 12/12 | C0 H1 M5 L5 | screened only |
| masaischool.com | complete | 12/12 | C0 H0 M4 L3 | screened only |
| mcaffeine.com | partial | 11/12 | C0 H0 M0 L2 | screened only |
| newtonschool.co | complete | 12/12 | C0 H1 M3 L3 | screened only |
| okcredit.in | complete | 12/12 | C0 H0 M0 L3 | screened only |
| plumgoodness.com | partial | 11/12 | C0 H0 M2 L1 | screened only |
| rarerabbit.in | partial | 1/12 | C0 H0 M4 L2 | screened only |
| rocketlane.com | complete | 12/12 | C0 H0 M2 L1 | screened only |
| scrut.io | complete | 12/12 | C0 H0 M2 L2 | screened only |
| setu.co | complete | 12/12 | C0 H0 M0 L0 | screened only |
| signeasy.com | complete | 12/12 | C0 H1 M0 L2 | ⚠️ C1 uncertain: control character only |
| sleepycat.in | partial | 11/12 | C0 H0 M2 L1 | screened only |
| slurrpfarm.com | partial | 11/12 | C0 H0 M6 L0 | screened only |
| snitch.co.in | blocked | 0/1 | C1 H0 M0 L0 | blocked or failed |
| sprinto.com | complete | 12/12 | C0 H2 M1 L3 | ❌ not reproducible: that page has no JSON-LD today |
| spyne.ai | complete | 12/12 | C0 H0 M4 L1 | screened only |
| superops.com | complete | 12/12 | C0 H0 M1 L6 | screened only |
| themancompany.com | partial | 11/12 | C0 H0 M1 L1 | screened only |
| thesleepcompany.in | partial | 11/12 | C0 H1 M3 L1 | ⚠️ C1 uncertain: control character only |
| thesouledstore.com | complete | 12/12 | C0 H1 M2 L1 | screened only |
| thewholetruthfoods.com | complete | 12/12 | C0 H0 M2 L2 | screened only |
| tooljet.com | complete | 12/12 | C0 H0 M2 L2 | screened only |
| traya.health | partial | 11/12 | C0 H1 M4 L3 | ✅ C1 certain: two JSON objects run together on the homepage ("Extra data"). Partial crawl 11/12 |
| ultrahuman.com | complete | 12/12 | C1 H0 M1 L2 | ❌ noindex on a /buy page (arguably deliberate) |
| vahdamteas.com | complete | 12/13 | C0 H0 M4 L1 | screened only |
| vyaparapp.in | complete | 12/12 | C1 H2 M3 L9 | ✅ STRONG: About page has BOTH index and noindex tags; pricing page empty shell for every UA incl. OAI-SearchBot; zoom disabled. Noise: 7 separate E1 findings |
| xyxxcrew.com | partial | 11/12 | C0 H0 M2 L1 | screened only |
| yogabars.in | partial | 11/12 | C0 H0 M4 L1 | screened only |
| zenduty.com | complete | 12/12 | C0 H1 M3 L1 | ✅ STRONG: pricing JSON-LD HTML-escaped (certain); case studies canonical → homepage (verified). Weak: search-box E1. Risk: migrating to xurrent.com |
| zipy.ai | complete | 12/12 | C0 H1 M2 L8 | ⚠️ C1 uncertain: control character; www/apex counted twice |
| zluri.com | complete | 12/12 | C0 H0 M2 L4 | screened only |
| zolve.com | complete | 12/12 | C0 H0 M2 L1 | screened only |
