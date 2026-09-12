# Discoverability tests: crawl-access-audit, fact-extractability-audit,
# freshness-corroboration-audit. Run by tests/run_tests.py, which injects the
# helpers (check, _page, _bundle, run_skill, audit_replay, H, X, bundle_mod, ...).
# Owner: discoverability. Add tests below; keep each one small and named for
# the behaviour it pins.
import importlib.util as _ilu

from model import SEVERITY_TABLE  # noqa: E402  (orchestrator scripts are on sys.path)


def _load(name, rel):
    spec = _ilu.spec_from_file_location(name, ROOT / "skills" / rel)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ACC = _load("check_access", "crawl-access-audit/scripts/check_access.py")
FRESH = _load("check_freshness", "freshness-corroboration-audit/scripts/check_freshness.py")
EXTRACT_SRC = (ROOT / "skills/fact-extractability-audit/scripts/check_extractability.py").read_text()


def ids(findings):
    return [f["check_id"] for f in findings]


def by(findings, check_id):
    return next((f for f in findings if f["check_id"] == check_id), {})


def access(pages, robots=""):
    return run_skill("crawl-access-audit", "check_access.py", _bundle(pages, robots))


def extract(pages):
    return run_skill("fact-extractability-audit", "check_extractability.py", _bundle(pages))


def fresh(pages):
    return run_skill("freshness-corroboration-audit", "check_freshness.py", _bundle(pages))


def hdr(page, **headers):
    page["headers"].update(headers)
    return page


LONG = "<h1>Title</h1><p>" + "Twenty five words of body copy that read as a real paragraph " * 3 + "</p>"
FOUR_PAGES = [_page("https://t.test/", "home", H()),
              _page("https://t.test/about", "about", H()),
              _page("https://t.test/team", "generic", H()),
              _page("https://t.test/faq", "generic", H())]

# ---------------------------------------------------------------------------
print("  [A1-D] 'none' is noindex only as a whole directive value")
check("'none, nofollow' is noindex", ACC._has_noindex("none, nofollow"), True)
check("'robots: none' header is noindex",
      any(d in ("none", "noindex") for _, d in ACC._parse_x_robots("robots: none")), True)
check("max-image-preview:none is NOT noindex", ACC._has_noindex("index, follow, max-image-preview:none"), False)
check("max-snippet:-1 is NOT noindex", ACC._has_noindex("max-snippet:-1, noarchive"), False)
check("a page with max-image-preview:none does not fire A3",
      any(i.startswith("A3") for i in ids(access([
          _page("https://t.test/", "home",
                H('<meta name="robots" content="index, follow, max-image-preview:none">'))]))), False)

# ---------------------------------------------------------------------------
print("  [A3-D] robots.txt URL and A7 wording")
wild = access([_page("https://t.test/", "home", H())], "User-agent: *\nDisallow: /\n")
check("robots.txt affected_url has no double slash",
      by(wild, "A1_retrieval_agent_blocked").get("affected_urls"), ["https://t.test/robots.txt"])

unreachable = _bundle([_page("https://t.test/", "home", "", status=0)])
unreachable.update(run_status="blocked", notes=["robots.txt unreachable: ConnectError"])
unreachable["coverage"]["pages_ok"] = 0
unreachable["robots"].update(present=False, status=0, agents={})
a7 = run_skill("crawl-access-audit", "check_access.py", unreachable)
check("an unreachable robots.txt is reported as unfetched",
      "robots.txt could not be fetched" in by(a7, "A7_site_unreadable").get("evidence", ""), True)
check("...and never as a Disallow aimed at us",
      "disallows our auditor" in by(a7, "A7_site_unreadable").get("evidence", ""), False)
really_blocked = _bundle([_page("https://t.test/", "home", "", status=0)],
                         "User-agent: *\nDisallow: /\n")
really_blocked.update(run_status="blocked")
really_blocked["coverage"]["pages_ok"] = 0
a7b = run_skill("crawl-access-audit", "check_access.py", really_blocked)
check("a real Disallow for our UA still says so",
      "disallows our auditor" in by(a7b, "A7_site_unreadable").get("evidence", ""), True)

# ---------------------------------------------------------------------------
print("  [B1] per-bot directives")
news_only = access([hdr(_page("https://t.test/", "home", H()), **{"x-robots-tag": "googlebot-news: noindex"})])
check("X-Robots-Tag scoped to googlebot-news does not fire A3", any(i.startswith("A3") for i in ids(news_only)), False)
bing = access([_page("https://t.test/", "home", H('<meta name="bingbot" content="noindex">'))])
check("meta bingbot noindex fires A3 (Bing feeds ChatGPT search and Copilot)", "A3_noindex" in ids(bing), True)
scoped_hdr = access([hdr(_page("https://t.test/", "home", H()), **{"x-robots-tag": "googlebot: noindex, nofollow"})])
check("X-Robots-Tag scoped to googlebot fires A3", "A3_noindex" in ids(scoped_hdr), True)
mixed = access([_page("https://t.test/", "home", H('<meta name="robots" content="noindex">')),
                hdr(_page("https://t.test/x", "generic", H()), **{"x-robots-tag": "gptbot: noindex"})])
check("a training-only scope is recorded in detail, not fired",
      (by(mixed, "A3_noindex").get("affected_urls"),
       [d["bots"] for d in by(mixed, "A3_noindex").get("detail", {}).get("scoped_to_other_bots", [])]),
      (["https://t.test/"], [["gptbot"]]))

print("  [B1] A2 snippet suppression")
check("noarchive alone is not snippet suppression",
      "A2_snippet_suppressed" in ids(access([_page("https://t.test/", "home", H('<meta name="robots" content="noarchive">'))])), False)
check("bingbot: noarchive header (theguardian.com) is not snippet suppression",
      "A2_snippet_suppressed" in ids(access([hdr(_page("https://t.test/", "home", H()), **{"x-robots-tag": "bingbot: noarchive"})])), False)
check("nosnippet still is",
      "A2_snippet_suppressed" in ids(access([_page("https://t.test/", "home", H('<meta name="robots" content="nosnippet">'))])), True)
check("max-snippet: 0 with a space still is", ACC._suppresses_snippets("max-snippet: 0"), True)
check("data-nosnippet on a cookie banner does not fire A2",
      "A2_snippet_suppressed" in ids(access([_page("https://t.test/", "home",
                                                    H(body='<div data-nosnippet>We use cookies. Accept?</div>' + LONG))])), False)
check("data-nosnippet around the h1 fires A2",
      "A2_snippet_suppressed" in ids(access([_page("https://t.test/", "home",
                                                    H(body=f'<div data-nosnippet>{LONG}</div>'))])), True)
check("data-nosnippet on <main> fires A2",
      "A2_snippet_suppressed" in ids(access([_page("https://t.test/", "home",
                                                    f'<html><head><title>t</title></head><body><main data-nosnippet><p>x</p></main></body></html>')])), True)

print("  [B1] A1 intent: named blocks vs wildcard vs index-critical")
GUARDIAN_LIKE = ("User-agent: Claude-SearchBot\nDisallow: /\n\nUser-agent: Claude-User\nDisallow: /\n\n"
                 "User-agent: PerplexityBot\nDisallow: /\n\nUser-agent: OAI-SearchBot\nAllow: /\n\n"
                 "User-agent: Googlebot\nAllow: /\n")
a1 = by(access([_page("https://t.test/", "home", H())], GUARDIAN_LIKE), "A1_retrieval_agent_blocked")
check("Guardian-style named blocks with OAI-SearchBot and Googlebot open -> confirm_intent", a1.get("status"), "confirm_intent")
check("...naming the agents that stay open", any("fully allowed" in s for s in a1.get("intent_signals", [])), True)
a1_rep = by(audit_replay(_bundle(FOUR_PAGES, GUARDIAN_LIKE))["findings"], "A1_retrieval_agent_blocked")
check("...and the report caps it at low", a1_rep.get("severity"), "low")
a1w = by(audit_replay(_bundle(FOUR_PAGES, "User-agent: *\nDisallow: /\n"))["findings"], "A1_retrieval_agent_blocked")
check("wildcard Disallow: / stays active", a1w.get("status"), "active")
check("...at critical", a1w.get("severity"), "critical")
a1g = by(access([_page("https://t.test/", "home", H())],
                "User-agent: Googlebot\nDisallow: /\nUser-agent: OAI-SearchBot\nAllow: /\n"), "A1_retrieval_agent_blocked")
check("blocking Googlebot by name is never confirm_intent", a1g.get("status"), "active")
a1b = by(access([_page("https://t.test/", "home", H())],
                "User-agent: Bingbot\nDisallow: /\nUser-agent: Claude-User\nAllow: /\n"), "A1_retrieval_agent_blocked")
check("blocking Bingbot by name is never confirm_intent", a1b.get("status"), "active")
a1o = by(access([_page("https://t.test/", "home", H())],
                "User-agent: OAI-SearchBot\nDisallow: /\nUser-agent: Claude-User\nAllow: /\n"), "A1_retrieval_agent_blocked")
check("blocking OAI-SearchBot by name is never confirm_intent", a1o.get("status"), "active")

# ---------------------------------------------------------------------------
print("  [B2] one price parser in both skills")
for raw, want in (("1,29,999", 129999.0), ("49,00", 49.0), ("1.299,00", 1299.0),
                  ("1,299.00", 1299.0), ("1,299", 1299.0), ("12.50", 12.5)):
    check(f"extractability reads {raw!r} as {want}", X._as_number(raw), want)
    check(f"freshness reads {raw!r} as {want}", FRESH._as_number(raw), want)
check("₹1,29,999 in prose is a price token", 129999.0 in X._price_tokens("Price ₹1,29,999 today"), True)
check("D4 reads an Indian-grouped Offer.price", FRESH._offer_prices({"@type": "Offer", "price": "1,29,999"}), {129999.0})
check("D4 reads a decimal-comma Offer.price", FRESH._offer_prices({"@type": "Offer", "price": "49,00"}), {49.0})
lakh = extract([_page("https://t.test/products/phone", "product",
                      H('<script type="application/ld+json">{"@type":"Product","name":"Phone",'
                        '"offers":{"@type":"Offer","price":"129999","priceCurrency":"INR"}}</script>',
                        "<h1>Phone</h1><p>Price ₹1,29,999 with EMI from ₹6,000 a month.</p>"))])
check("an Indian-grouped visible price matches its JSON-LD price (no C2)",
      "C2_markup_text_contradiction" in ids(lakh), False)
check("...and is a T0 price, not B1", any(i.startswith("B1") for i in ids(lakh)), False)

print("  [B2] D1: Last-Modified header and section index pages")
check("an RFC 1123 Last-Modified parses to a date", FRESH._http_date("Wed, 01 Jul 2026 07:28:00 GMT"), "2026-07-01")
check("garbage in the header is ignored", FRESH._http_date("yesterday"), None)
only_header = fresh([hdr(_page("https://t.test/blog/post", "blog", H()), **{"last-modified": "Wed, 01 Jul 2026 07:28:00 GMT"})])
check("a blog post dated only by Last-Modified does not fire D1", "D1_no_date_signals" in ids(only_header), False)
check("a blog post with no date at all does fire D1",
      "D1_no_date_signals" in ids(fresh([_page("https://t.test/blog/post", "blog", H())])), True)
check("the /blog index page is a listing, not an undated article",
      "D1_no_date_signals" in ids(fresh([_page("https://t.test/blog", "blog", H())])), False)
check("...likewise /news/", "D1_no_date_signals" in ids(fresh([_page("https://t.test/news/", "blog", H())])), False)
old_index = fresh([_page("https://t.test/blog", "blog", H('<meta property="article:published_time" content="2020-01-01">'))])
check("an old date on the index page is not D3", "D3_content_stale" in ids(old_index), False)

print("  [B2] C3 across pages and organisation subtypes")
def _org(url, role, typ, same=True):
    same_as = ',"sameAs":["https://instagram.com/x"]' if same else ""
    return _page(url, role, H(f'<script type="application/ld+json">{{"@type":"{typ}","name":"X"{same_as}}}</script>'))
check("Restaurant + sameAs on the homepage anchors the brand",
      "C3_entity_unanchored" in ids(extract([_org("https://t.test/", "home", "Restaurant")])), False)
check("NewsMediaOrganization + sameAs anchors it",
      "C3_entity_unanchored" in ids(extract([_org("https://t.test/", "home", "NewsMediaOrganization")])), False)
check("Dentist + sameAs anchors it",
      "C3_entity_unanchored" in ids(extract([_org("https://t.test/", "home", "Dentist")])), False)
check("sameAs on /about (not the homepage) still anchors it",
      "C3_entity_unanchored" in ids(extract([_page("https://t.test/", "home", H()),
                                              _org("https://t.test/about", "about", "Organization")])), False)
c3 = by(extract([_org("https://t.test/", "home", "Organization", same=False),
                 _page("https://t.test/about", "about", H())]), "C3_entity_unanchored")
check("Organization without sameAs anywhere fires C3", bool(c3), True)
check("...pointing at the homepage", c3.get("affected_urls"), ["https://t.test/"])
person_only = _bundle([_page("https://t.test/", "home", H()), _org("https://t.test/blog/a", "blog", "Person")])
rep = audit_replay(person_only)
check("sameAs only on a Person node does not anchor the brand: C3 fires and the "
      "citable-facts recommendation applies (the two never contradict)",
      ("C3_entity_unanchored" in ids(rep["findings"]),
       any("sameAs" in a["because"] for a in rep.get("already_in_place", [])),
       any("sameAs" in r.get("applies_because", "") for r in rep.get("proactive_recommendations", []))),
      (True, False, True))

print("  [B2] A5: same site and the missing/problem split")
www = access([_page("https://t.test/", "home", H()),
              _page("https://t.test/pricing", "pricing", H('<link rel="canonical" href="https://www.t.test/pricing">'))])
check("www.host and host are the same site", any(i.startswith("A5") for i in ids(www)), False)
split = access([_page("https://t.test/", "home", H()),
                _page("https://t.test/pricing", "pricing", H()),
                _page("https://t.test/blog/a", "blog", H('<link rel="canonical" href="https://other.test/a">'))])
check("a missing canonical is A5_canonical_missing", by(split, "A5_canonical_missing").get("affected_urls"), ["https://t.test/pricing"])
check("...with a detail note", "note" in by(split, "A5_canonical_missing").get("detail", {}), True)
check("an off-domain canonical stays A5_canonical_problem", by(split, "A5_canonical_problem").get("affected_urls"), ["https://t.test/blog/a"])
check("A5_canonical_missing is low in the table", SEVERITY_TABLE["A5_canonical_missing"]["base"], "low")
check("A5_canonical_problem stays medium", SEVERITY_TABLE["A5_canonical_problem"]["base"], "medium")

# ---------------------------------------------------------------------------
print("  [B3] noise removed")
three_h2 = H(body="<h1>T</h1><h2>One</h2><p>a</p><h2>Two</h2><p>b</p><h2>Three</h2><p>c</p>")
check("X2_no_citation_anchor is gone from the code",
      "X2_no_citation_anchor" in ids(extract([_page("https://t.test/", "home", three_h2)])), False)
check("...and from the table", "X2_no_citation_anchor" in SEVERITY_TABLE, False)
check("D5_no_corroboration_hooks is gone from the code",
      "D5_no_corroboration_hooks" in ids(fresh([_page("https://t.test/", "home", H("<h1>Joe Plumbing</h1>"))])), False)
check("...and from the table", "D5_no_corroboration_hooks" in SEVERITY_TABLE, False)
check("the false 'structured data survives text extraction' claim is gone",
      ("survives text extraction" in EXTRACT_SRC, "which extractors do retain" in EXTRACT_SRC), (False, False))

questions = H(body="<h1>T</h1><h2>What is it?</h2><p>a</p><h2>How does it work?</h2><p>b</p><h2>Why use it?</h2><p>c</p>")
check("C5 does not fire on an article (interview questions are narrative)",
      "C5_faq_content_unmarked" in ids(extract([_page("https://t.test/blog/interview", "blog", questions)])), False)
c5 = by(extract([_page("https://t.test/help", "generic", questions)]), "C5_faq_content_unmarked")
check("C5 fires on a non-article page", bool(c5), True)
check("C5 is framed around self-contained answers, not rich results",
      ("self-contained answer" in c5.get("title", "") + c5.get("evidence", ""),
       "rich results" in (c5.get("title", "") + c5.get("evidence", "") + " ".join(c5.get("suggested_action", {}).get("how", []))).lower()),
      (True, False))
check("C5 is low in the table", SEVERITY_TABLE["C5_faq_content_unmarked"]["base"], "low")
check("X1 is low in the table", SEVERITY_TABLE["X1_low_quotability"]["base"], "low")
check("D3 is low in the table", SEVERITY_TABLE["D3_content_stale"]["base"], "low")
check("C1_structured_data_absent is low in the table", SEVERITY_TABLE["C1_structured_data_absent"]["base"], "low")
check("C1_product_markup_absent is medium in the table", SEVERITY_TABLE["C1_product_markup_absent"]["base"], "medium")
c1 = extract([_page("https://t.test/", "home", H()),
              _page("https://t.test/products/mug", "product", H(body="<h1>Mug</h1><p>Only $12 each.</p>")),
              _page("https://t.test/products/cup", "product",
                    H('<script type="application/ld+json">{"@type":"Product","name":"Cup","offers":{"@type":"Offer","price":"9"}}</script>',
                      "<h1>Cup</h1><p>Only $9 each.</p>"))])
check("a product page without Product markup is C1_product_markup_absent",
      by(c1, "C1_product_markup_absent").get("affected_urls"), ["https://t.test/products/mug"])
check("a home page without JSON-LD is C1_structured_data_absent",
      by(c1, "C1_structured_data_absent").get("affected_urls"), ["https://t.test/"])
stale = by(fresh([_page("https://t.test/blog/guide", "blog", H('<meta property="article:published_time" content="2021-01-01">'))]),
           "D3_content_stale")
check("D3 asks for a review, not a refresh-or-retire",
      ("still accurate" in stale.get("suggested_action", {}).get("summary", ""),
       "retire" in stale.get("suggested_action", {}).get("summary", "")), (True, False))

# ---------------------------------------------------------------------------
print("  [B5-D] A9 broken pages")
broken = access([_page("https://t.test/", "home", H()),
                 _page("https://t.test/pricing", "pricing", "", status=404),
                 _page("https://t.test/old", "generic", "", status=410),
                 _page("https://t.test/private", "generic", "", status=403),
                 _page("https://t.test/down", "generic", "", status=0)])
a9 = by(broken, "A9_key_page_broken")
check("a 404 pricing page is A9_key_page_broken", sorted(a9.get("affected_urls", [])), ["https://t.test/old", "https://t.test/pricing"])
check("403 and status 0 are not broken pages",
      any(u in a9.get("affected_urls", []) for u in ("https://t.test/private", "https://t.test/down")), False)
check("evidence lists URL and status", "https://t.test/pricing: HTTP 404" in a9.get("evidence", ""), True)
check("A9 carries hurts_both in detail", a9.get("detail", {}).get("hurts_both"), True)
plain = access([_page("https://t.test/", "home", H()), _page("https://t.test/x", "generic", "", status=500)])
check("a 5xx on a generic page is A9_broken_pages", by(plain, "A9_broken_pages").get("affected_urls"), ["https://t.test/x"])
check("A9 does not fire on a healthy crawl", any(i.startswith("A9") for i in ids(access(FOUR_PAGES))), False)
check("A9_key_page_broken is high, A9_broken_pages medium",
      (SEVERITY_TABLE["A9_key_page_broken"]["base"], SEVERITY_TABLE["A9_broken_pages"]["base"]), ("high", "medium"))

print("  [B5-D] A10 meta refresh")
a10 = by(access([_page("https://t.test/old", "generic", H('<meta http-equiv="refresh" content="0;url=https://t.test/new">'))]), "A10_meta_refresh")
check("a zero-delay meta refresh to another URL fires A10", bool(a10), True)
check("...and says it acts as a redirect fetchers do not follow", "redirect" in a10.get("evidence", ""), True)
check("a timed reload of the same page is not A10",
      "A10_meta_refresh" in ids(access([_page("https://t.test/", "home", H('<meta http-equiv="refresh" content="30">'))])), False)
check("A10 does not fire without a refresh", "A10_meta_refresh" in ids(access(FOUR_PAGES)), False)
check("A10 is low in the table", SEVERITY_TABLE["A10_meta_refresh"]["base"], "low")

print("  [B5-D] C7 title problems")
def _titled(url, title):
    return _page(url, "generic", H().replace("<title>t</title>", f"<title>{title}</title>" if title is not None else ""))
c7 = by(extract([_titled("https://t.test/a", "Home"), _titled("https://t.test/b", None),
                 _titled("https://t.test/c", ""), _titled("https://t.test/d", "Real page | Acme")]), "C7_title_problem")
check("generic, missing and empty titles fire C7",
      sorted(c7.get("affected_urls", [])), ["https://t.test/a", "https://t.test/b", "https://t.test/c"])
dup = by(extract([_titled(f"https://t.test/{i}", "Acme") for i in range(3)]), "C7_title_problem")
check("one title on three pages fires C7", len(dup.get("affected_urls", [])), 3)
check("unique titles do not fire C7",
      "C7_title_problem" in ids(extract([_titled(f"https://t.test/{i}", f"Page {i} | Acme") for i in range(3)])), False)
check("C7 is medium in the table", SEVERITY_TABLE["C7_title_problem"]["base"], "medium")

print("  [B5-D] A11 soft 404")
soft = access([_page("https://t.test/", "home", H()),
               _page("https://t.test/gone", "generic", H().replace("<title>t</title>", "<title>Page not found | Acme</title>")),
               _page("https://t.test/de", "generic", H(body="<h1>Seite nicht gefunden</h1><p>x</p>"))])
check("a 200 titled 'Page not found' fires A11", sorted(by(soft, "A11_soft_404").get("affected_urls", [])),
      ["https://t.test/de", "https://t.test/gone"])
check("A11 is heuristic", by(soft, "A11_soft_404").get("confidence"), "heuristic")
check("A11 does not fire on ordinary pages", "A11_soft_404" in ids(access(FOUR_PAGES)), False)
check("A11 is medium in the table", SEVERITY_TABLE["A11_soft_404"]["base"], "medium")

# ---------------------------------------------------------------------------
print("  [hygiene] docs")
for skill in ("crawl-access-audit", "fact-extractability-audit", "freshness-corroboration-audit"):
    text = (ROOT / "skills" / skill / "SKILL.md").read_text()
    check(f"{skill}/SKILL.md has an Interpreting results section", "## Interpreting results" in text, True)
    check(f"{skill}/SKILL.md stays under 200 lines", len(text.splitlines()) < 200, True)
rationale = (ROOT / "skills/audit-orchestrator/references/severity-rationale.md").read_text()
for cid in ("A5_canonical_missing", "A9_broken_pages", "A9_key_page_broken", "A10_meta_refresh",
            "A11_soft_404", "C1_product_markup_absent", "C7_title_problem"):
    check(f"severity-rationale.md defends {cid}", f"`{cid}`" in rationale, True)
check("severity-rationale.md no longer lists removed checks",
      ("X2_no_citation_anchor" in rationale, "D5_no_corroboration_hooks" in rationale), (False, False))

print("\nB1: a contact page built around a form is a question, not a high defect (djangoproject.com)")
_form = ('<h1>Contact us</h1><p>Use this form to reach the foundation team with any question you have.</p>'
         '<form action="/contact"><label for="m">Message</label><textarea id="m" name="m"></textarea>'
         '<button>Send</button></form>')
form_site = _bundle([_page("https://t.test/", "home", H()),
                     _page("https://t.test/about", "about", H()),
                     _page("https://t.test/contact", "contact", H(body=_form))])
form_rep = audit_replay(form_site)
b1_form = next((f for f in form_rep["findings"] if f["check_id"] == "B1_fact_absent"), {})
check("a form-only contact page is reported as confirm_intent", b1_form.get("status"), "confirm_intent")
check("...capped at low", b1_form.get("severity"), "low")
check("...and says why", any("contact form" in s for s in b1_form.get("intent_signals", [])), True)
bare_site = _bundle([_page("https://t.test/", "home", H()),
                     _page("https://t.test/about", "about", H()),
                     _page("https://t.test/contact", "contact",
                           H(body="<h1>Contact us</h1><p>We would love to hear from you sometime soon.</p>"))])
b1_bare = next((f for f in audit_replay(bare_site)["findings"] if f["check_id"] == "B1_fact_absent"), {})
check("a contact page with neither a form nor a phone/email stays an active defect",
      (b1_bare.get("status"), b1_bare.get("severity")), ("active", "high"))


print("\n[final gate] apex and www are one site")
check("_same_host treats www. and apex as one host",
      (bundle_mod._same_host("www.example.com", "example.com"), bundle_mod._same_host("example.com", "WWW.example.com"),
       bundle_mod._same_host("shop.example.com", "example.com")), (True, True, False))
links, _ = bundle_mod.homepage_links(
    "<body><a href='https://www.example.com/pricing'>Pricing</a><a href='https://example.com/about'>About</a>"
    "<a href='https://other.example/x'>x</a></body>", "https://example.com/")
check("absolute www links are kept when the typed host is the apex",
      links, ["https://example.com/about", "https://www.example.com/pricing"])


print("\n[C2] prices after an article number, variant prices, distinct page counts (sennheiser)")
check("a number before a currency-first price does not hide the price",
      3990.0 in X._price_tokens("4.4MM CABLE Article No. 700403 ₹3,990.00 Why buy directly"), True)
check("currency-last price lists keep every price", X._price_tokens("10 € 20 € 30 €"), {10.0, 20.0, 30.0})
check("pack counts and model numbers do not replace the real price",
      (19.99 in X._price_tokens("Pack of 2 €19.99"), 1299.0 in X._price_tokens("Model 700 €1.299,00")), (True, True))

def _offer_ld(*offers):
    nodes = ",".join('{"@type":"Product","name":"%s","offers":{"@type":"Offer","price":"%s","priceCurrency":"INR"}}'
                     % (n, v) for n, v in offers)
    return '<script type="application/ld+json">{"@type":"ProductGroup","hasVariant":[%s]}</script>' % nodes

article = _page("https://t.test/products/cable", "product",
                H(_offer_ld(("Cable", "3990.00")), "<p>4.4MM CABLE Article No. 700403 ₹3,990.00 Inclusive of all taxes</p>"))
check("the Sennheiser accessory page (article number then price) raises no C2",
      "C2_markup_text_contradiction" in ids(extract([article])), False)
variants = _page("https://t.test/products/earpad", "product",
                 H(_offer_ld(("Earpad - Black", "1462.00"), ("Earpad - Beige", "1500.00")),
                   "<p>Accentum Earpad Article No. 700551 ₹1,462.00</p>"))
check("variant prices with the selected one shown raise no C2",
      "C2_markup_text_contradiction" in ids(extract([variants])), False)
wrong = _page("https://t.test/products/amp", "product",
              H(_offer_ld(("Amp", "999.00")), "<p>Amplifier Article No. 555001 ₹1,299.00</p>"))
check("a real markup/text price disagreement still raises C2",
      "C2_markup_text_contradiction" in ids(extract([wrong])), True)
two_wrong = _page("https://t.test/products/amp2", "product",
                  H(_offer_ld(("Amp S", "999.00"), ("Amp L", "1099.00")), "<p>Amplifier ₹1,299.00</p>"))
c2_two = by(extract([two_wrong]), "C2_markup_text_contradiction")
check("two contradicting offers on one page count as one page",
      (c2_two.get("affected_urls"), "on 1 page(s)" in c2_two.get("title", "")), (["https://t.test/products/amp2"], True))
dup = Finding(check_id="C2_markup_text_contradiction", title="t", evidence="e", suggested_action={},
              affected_urls=["https://t.test/a", "https://t.test/a", "https://t.test/b"]).finalise(1, 10).to_report()
check("the report never lists or counts a page twice", (dup["affected_urls"], dup["affected_url_count"]),
      (["https://t.test/a", "https://t.test/b"], 2))


print("\n[dates] ISO datetimes are dates (theritzlondon.com, dishoom.com)")
from bs4 import BeautifulSoup as _BS
_dt_ld = _BS('<script type="application/ld+json">{"@type":"BlogPosting","headline":"H",'
             '"datePublished":"2023-12-11T14:15:55+00:00","dateModified":"2025-04-04T16:03:08Z"}</script>', "html.parser")
check("JSON-LD datetimes are read as dates", bundle_mod.normalise_jsonld(_dt_ld)["dates"], ["2023-12-11", "2025-04-04"])
check("the freshness date pattern reads a datetime", FRESH.ISO_DATE.findall("2023-12-11T14:15:55+00:00"), [("2023", "12", "11")])
check("...and still ignores a longer digit run", FRESH.ISO_DATE.findall("12023-12-110"), [])
_post = '<h1>Post</h1><p>Body copy for a post.</p>'
ld_dated = _page("https://t.test/blog/a", "blog", H('<script type="application/ld+json">{"@type":"BlogPosting",'
                 f'"headline":"H","datePublished":"2026-05-01T09:00:00+00:00"}}</script>', _post))
meta_dated = _page("https://t.test/blog/b", "blog", H('<meta property="article:published_time" content="2026-05-01T09:00:00+00:00">', _post))
undated = _page("https://t.test/blog/c", "blog", H("", _post))
d1 = by(fresh([ld_dated, meta_dated, undated]), "D1_no_date_signals")
check("D1 fires only on the post with no date at all", d1.get("affected_urls"), ["https://t.test/blog/c"])
old_post = _page("https://t.test/blog/old", "blog", H('<meta property="article:modified_time" content="2021-01-01T00:00:00Z">', _post))
check("D3 now sees an old datetime", "D3_content_stale" in ids(fresh([old_post])), True)
