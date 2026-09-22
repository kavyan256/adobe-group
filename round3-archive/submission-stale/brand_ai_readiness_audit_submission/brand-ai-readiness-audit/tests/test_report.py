# Report, orchestrator, crawler and agent-review tests: audit.py, model.py,
# bundle.py, verify_claims.py, page_profile.py. Run by tests/run_tests.py, which
# injects the helpers (check, _page, _bundle, _write, run_skill, audit_replay,
# H, Finding, sev, replay, RETRIEVAL_AGENTS, ...).
# Owner: skills & report. Add tests below; keep each one small and named for
# the behaviour it pins.
import audit as audit_mod  # noqa: E402  (orchestrator scripts are on sys.path)

FIX = ROOT / "tests" / "fixtures"
JUDGES = FIX / "rep_judges.bundle.json"          # the n.example site the reviewers used
JUDGES_B = json.loads(JUDGES.read_text(encoding="utf-8"))
HOME, BLOG = "https://n.example/", "https://n.example/blog/x"


def replay_claims(bundle_path, claims_path):
    proc = subprocess.run([sys.executable, str(AUDIT), "--replay", str(bundle_path),
                           "--agent-claims", str(claims_path)],
                          capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        FAIL.append(f"audit.py --agent-claims exited {proc.returncode}")
        print(f"  FAIL audit.py --agent-claims exited {proc.returncode}: {proc.stderr[-300:]}")
        return {"findings": [], "agent_review": {}}
    return json.loads(proc.stdout)


def rejections(report):
    return " | ".join(r["reason"] for r in report.get("agent_review", {}).get("rejected", []))


def agent_findings(report):
    return [f for f in report["findings"] if f.get("source") == "agent_review"]


def rclaim(title, evidence, affected, mechanism="A", hurts="ai_discoverability", severity="high",
           why="A mechanism explanation that is long enough to pass the length rule.",
           how=("Do the fix.",), verify="Re-run the audit and check.", summary="Fix the thing on the page."):
    return {"title": title, "why": why, "mechanism": mechanism, "hurts": hurts, "severity": severity,
            "nearest_check": None, "affected_urls": affected, "evidence": evidence,
            "suggested_action": {"summary": summary, "how": list(how), "verify": verify,
                                 "effort": "low"}}


# ---------------------------------------------------------------------------
print("\n[A1-S] a crashing skill is a failed test, not an empty result")
got = run_skill("audit-orchestrator", "does-not-exist.py",
                _bundle([_page("https://t.test/", "home", H())]), expect_crash=True)
check("run_skill returns [] when a script exits non-zero (and records a FAIL unless expected)",
      got, [])

# ---------------------------------------------------------------------------
print("\n[A1-S] the reviewers' claim files, replayed as regression tests")
crash = replay_claims(JUDGES, FIX / "rep_crash.claims.json")
check("a claim with a list-valued url does not crash the review",
      crash.get("agent_review", {}).get("status"), "run")
check("...it is rejected as malformed", "malformed claim: " in rejections(crash), True)
check("...and the other claims are still evaluated",
      crash.get("agent_review", {}).get("claims_submitted"), 5)

adv = replay_claims(JUDGES, FIX / "rep_redteam.claims.json")
adv_reasons = rejections(adv)
check("red team: nothing in the adversarial claims file is merged", agent_findings(adv), [])
check("red team: 'status eq 200' + an absence is not positive evidence",
      "identity field" in adv_reasons, True)
check("red team: canonical eq \"None\" does not match a null canonical",
      "does not hold" in adv_reasons and "canonical eq \"None\"" in adv_reasons, True)
check("red team: '</html>' on every page is not evidence", "true of every page" in adv_reasons, True)

arch = replay_claims(JUDGES, FIX / "rep_architect.claims.json")
arch_reasons = rejections(arch)
check("architect: a claim whose fix step carries a <script> tag is rejected",
      "markup or external links" in arch_reasons, True)
check("architect: a restated finding under nearest_check null is not merged",
      agent_findings(arch), [])

grader = replay_claims(JUDGES, FIX / "rep_grader.claims.json")
check("grader: 'value proposition unclear' backed only by status 200 is rejected",
      "identity field" in rejections(grader), True)
check("grader: 'no press page' backed by status + html_lacks is rejected",
      agent_findings(grader), [])

# ---------------------------------------------------------------------------
print("\n[A2] verifier rules")
quote = "what does feature 1 actually do?"      # a real heading on the n.example homepage
good = rclaim("Feature question is answered only in repeated filler",
              [{"url": HOME, "type": "text_contains", "value": quote}], [HOME])
one = replay_claims(JUDGES, _write("one.claims.json", {"claims": [good]}))
merged_one = agent_findings(one)
check("a specific, true, non-duplicate claim is merged", len(merged_one), 1)
ev = merged_one[0]["evidence"] if merged_one else ""
check("the reviewer's explanation is labelled unverified",
      ev.startswith("Reviewer's explanation (not verified): "), True)
check("the assertions are labelled as checked against the crawl",
      "Checked against the crawl: " in ev, True)
check("the merged claim is capped at low", merged_one[0]["severity"] if merged_one else None, "low")
check("the report's agent_review carries no determinism prose",
      "determinism" in one.get("agent_review", {}), False)

null_eq = rclaim("Canonical is null, stated as JSON null",
                 [{"url": HOME, "type": "field", "path": "canonical", "op": "eq", "value": None}], [HOME])
check("'eq null' holds but counts as an absence",
      "identity field" in rejections(replay_claims(JUDGES, _write("n.claims.json", {"claims": [null_eq]}))),
      True)

offsite = rclaim("Explanation links off-site", [{"url": HOME, "type": "text_contains", "value": quote}],
                 [HOME], why="See https://evil.example/proof for why this matters to the site here.")
onsite = rclaim("Explanation links on-site", [{"url": HOME, "type": "text_contains", "value": quote}],
                [HOME], why="See https://n.example/blog/x for the page this contrasts with here.")
js = rclaim("Verify step uses javascript:", [{"url": HOME, "type": "text_contains", "value": quote}],
            [HOME], verify="javascript:alert(1) then reload the page")
mixed = replay_claims(JUDGES, _write("links.claims.json", {"claims": [offsite, onsite, js]}))
check("an off-site URL in the explanation is rejected, an on-site one is not",
      ([f["title"] for f in agent_findings(mixed)],
       rejections(mixed).count("markup or external links")),
      (["Explanation links on-site"], 2))

five = [rclaim(f"Claim number {i} about the same heading",
               [{"url": HOME, "type": "text_contains", "value": quote}], [HOME]) for i in range(5)]
over = replay_claims(JUDGES, _write("five.claims.json", {"claims": five}))
check("at most 4 claims are verified", "over the limit of 4 claims" in rejections(over), True)
check("...and the verifier reports the limit", over.get("agent_review", {}).get("claim_limit"), 4)

dup = rclaim("Question headings on the homepage have no FAQ markup",
             [{"url": HOME, "type": "text_contains", "value": quote}], [HOME], mechanism="B")
dup["nearest_check"] = "C5_faq_content_unmarked"
names_conflict = rclaim("The homepage calls the company by several names",
                        [{"url": HOME, "type": "field", "path": "meta.og:site_name", "op": "eq",
                          "value": "Zeta Holdings"}], [HOME], mechanism="D")
access_claim = rclaim("The article page carries a stray canonical hint in its body",
                      [{"url": BLOG, "type": "text_contains", "value": "substantive article content"}],
                      [BLOG], mechanism="A")
dup_rep = replay_claims(JUDGES, _write("dup.claims.json", {"claims": [dup, names_conflict, access_claim]}))
dup_reasons = rejections(dup_rep)
check("a claim naming C5 in nearest_check on C5's page is dropped as a duplicate",
      "duplicates scripted check C5_faq_content_unmarked" in dup_reasons, True)
check("a mechanism-D claim on the page where C6 (medium, same audience) fired is dropped",
      "duplicates scripted check C6_entity_name_conflict" in dup_reasons, True)
check("a mechanism-A claim is not swallowed by the low-base A5_canonical_missing on its page",
      [f["title"] for f in agent_findings(dup_rep)],
      ["The article page carries a stray canonical hint in its body"])

low_effort = Finding(check_id="R_agent_review", title="t", evidence="e",
                     suggested_action={"summary": "s", "priority": "low", "effort": "low"},
                     detail={"proposed_severity": "high"}).finalise(1, 10)
med_effort = Finding(check_id="R_agent_review", title="t", evidence="e",
                     suggested_action={"summary": "s", "priority": "low", "effort": "medium"},
                     detail={"proposed_severity": "high"}).finalise(1, 10)
check("ranking ignores the effort a reviewer chose for their own claim",
      audit_mod.priority_score(low_effort), audit_mod.priority_score(med_effort))

plain = subprocess.run([sys.executable, str(AUDIT), "--replay", str(JUDGES)],
                       capture_output=True, text=True, cwd=str(ROOT))
check("a plain run prints a one-line hint that the agent review did not run",
      "agent review not run" in plain.stderr and "agent-review-audit/SKILL.md" in plain.stderr, True)

# ---------------------------------------------------------------------------
print("\n[A1-S/A3] agent findings are never latent; counts and order are consistent")
blocked_pages = [
    _page("https://t.test/", "home", H()),
    _page("https://t.test/pricing", "pricing",
          H(body="<h1>Pricing</h1><p>Plans for teams of every size and shape.</p>")),
    _page("https://t.test/about", "about", H(body="<h1>About</h1><p>We make things for people.</p>")),
]
all_blocked = _bundle(blocked_pages, "".join(f"User-agent: {a}\nDisallow: /\n\n" for a in RETRIEVAL_AGENTS))
blocked_claim = rclaim("Pricing page names no plan tiers",
                       [{"url": "https://t.test/pricing", "type": "text_contains",
                         "value": "teams of every size"}], ["https://t.test/pricing"], mechanism="D")
latent_rep = audit_replay(all_blocked, "--agent-claims",
                          str(_write("latent.claims.json", {"claims": [blocked_claim]})))
lat_agent = agent_findings(latent_rep)
check("an agent-review finding behind a total retrieval block stays active",
      lat_agent[0]["status"] if lat_agent else None, "active")
check("...while a scripted extractability finding there is latent",
      next((f["status"] for f in latent_rep["findings"] if f["check_id"] == "B1_fact_absent"), None),
      "latent")
s = latent_rep["summary"]
check("severity counts cover every finding and add up to total_findings",
      s["critical"] + s["high"] + s["medium"] + s["low"] + s["info"], s["total_findings"])
check("active_by_severity is present and adds up to active_findings",
      sum(s["active_by_severity"].values()) + sum(1 for f in latent_rep["findings"]
                                                  if f["status"] == "active" and f["severity"] == "info"),
      s["active_findings"])
check("latent findings are counted in the severity totals",
      s["latent_findings"] > 0 and s["low"] >= s["latent_findings"], True)
ids = [f["id"] for f in latent_rep["findings"]]
check("ids are assigned in report order", ids, [f"F-{i:03d}" for i in range(1, len(ids) + 1)])
order = [audit_mod.SEV_WEIGHT[f["severity"]] for f in latent_rep["findings"]]
check("findings are ordered by severity band first", order, sorted(order, reverse=True))
check("prioritized_actions follows the same order",
      [a["finding_id"] for a in latent_rep["prioritized_actions"]], ids[:15])

unreadable = _bundle([_page("https://t.test/", "home", "", status=429)])
unreadable["run_status"], unreadable["coverage"]["pages_ok"] = "failed", 0
zero = audit_replay(unreadable)
check("with no readable page, engagement appears in checks_skipped",
      any(sk["check"].startswith("engagement") for sk in zero.get("checks_skipped", [])), True)

# ---------------------------------------------------------------------------
print("\n[B7] site-specific fixes grounded on the page's own words")
fixes_doc = {"claims": [], "fixes": [
    {"check_id": "C5_faq_content_unmarked", "url": HOME, "quote": quote,
     "site_specific": ["Wrap the heading and its answer in FAQPage JSON-LD.",
                       "Keep the answer copy self-contained."]},
    {"check_id": "C5_faq_content_unmarked", "url": HOME, "quote": "an invented sentence nobody wrote",
     "site_specific": ["Do something."]},
    {"check_id": "D1_no_date_signals", "url": HOME, "quote": quote,
     "site_specific": ["Add a dateModified to the homepage."]},
]}
fixed = replay_claims(JUDGES, _write("fixes.claims.json", fixes_doc))
c5 = next((f for f in fixed["findings"] if f["check_id"] == "C5_faq_content_unmarked"), {})
fr = fixed.get("agent_review", {})
fix_reasons = " | ".join(r["reason"] for r in fr.get("rejected_fixes", []))
check("a fix whose quote is on the page is merged into the finding's suggested_action",
      c5.get("suggested_action", {}).get("site_specific"),
      ["Wrap the heading and its answer in FAQPage JSON-LD.", "Keep the answer copy self-contained."])
check("...and records what it was grounded on",
      c5.get("suggested_action", {}).get("grounded_on"), {"url": HOME, "quote": quote})
check("an invented quote is rejected", "quote is not on the page" in fix_reasons, True)
check("a fix for a check that does not report that page is rejected",
      "no finding D1_no_date_signals reports" in fix_reasons, True)
check("the review counts fixes submitted and merged",
      (fr.get("fixes_submitted"), fr.get("fixes_merged")), (3, 1))

script_fix = {"claims": [], "fixes": [
    {"check_id": "C5_faq_content_unmarked", "url": HOME, "quote": quote,
     "site_specific": ["Add <script src=//evil.example/x.js> to the page."]},
]}
scripted = replay_claims(JUDGES, _write("script-fix.claims.json", script_fix))
check("a step carrying a script tag is rejected",
      "markup or external links" in " | ".join(
          r["reason"] for r in scripted.get("agent_review", {}).get("rejected_fixes", [])), True)

four_fixes = [{"check_id": "Z1_no_such_check", "url": HOME, "quote": quote,
              "site_specific": [f"Step {i}."]} for i in range(4)]
over_fixes = replay_claims(JUDGES, _write("four-fixes.claims.json", {"claims": [], "fixes": four_fixes}))
check("at most 3 fixes are verified", "over the limit of 3 fixes" in " | ".join(
      r["reason"] for r in over_fixes.get("agent_review", {}).get("rejected_fixes", [])), True)

# ---------------------------------------------------------------------------
print("\n[B8-S] orientation items are conditioned on the crawl; limits are actionable")
titles = lambda rep, key: [p["title"] for p in rep.get(key, [])]  # noqa: E731
FIRST = "Answer the question visitors arrive with on the first screen"
DEEP = "Every deep page links to its parent section and a contact route"
LONG = " ".join(f"Sentence number {i} of a guide that goes on at some length." for i in range(12))
vague_home = _bundle([
    _page("https://t.test/", "home",
          H('<meta property="og:site_name" content="Acme Widgets">',
            "<h1>Welcome</h1><p>We believe in better outcomes for everyone, everywhere, always.</p>")),
    _page("https://t.test/guide", "generic", H(body=f"<h1>Guide</h1><p>{LONG}</p>")),
])
vague = audit_replay(vague_home)
check("a homepage opening that names neither the brand nor a fact gets the first-screen item",
      FIRST in titles(vague, "proactive_recommendations"), True)
check("a deep page whose main content has no internal link gets the deep-page item",
      DEEP in titles(vague, "proactive_recommendations"), True)
clear_home = _bundle([
    _page("https://t.test/", "home",
          H('<meta property="og:site_name" content="Acme Widgets">',
            "<h1>Acme Widgets</h1><p>Acme Widgets makes industrial widgets for 400 factories.</p>")),
    _page("https://t.test/guide", "generic",
          H(body=f'<h1>Guide</h1><p>{LONG} Back to <a href="/">the catalogue</a> or '
                 '<a href="/contact">contact us</a>.</p>')),
])
clear = audit_replay(clear_home)
check("a homepage that names itself moves the first-screen item to already_in_place",
      FIRST in titles(clear, "already_in_place"), True)
check("a deep page that links onward moves the deep-page item to already_in_place",
      DEEP in titles(clear, "already_in_place"), True)
check("limits are written as Not assessed / Reason / How to check it yourself",
      all(l.startswith("Not assessed: ") and "Reason: " in l and "How to check it yourself: " in l
          for l in clear.get("limits", [])) and len(clear.get("limits", [])) >= 6, True)
check("markup contradiction, broken pages and title problems hurt both audiences",
      [Finding(check_id=c, title="t", evidence="e", suggested_action={}).finalise(1, 10).hurts
       for c in ("C2_markup_text_contradiction", "A9_broken_pages", "C7_title_problem")],
      ["both"] * 3)

# ---------------------------------------------------------------------------
print("\n[A4] crawler safety edges (fake HTTP client, no network)")
from datetime import timedelta  # noqa: E402
from urllib.parse import urlparse as _urlparse  # noqa: E402


class _Resp:
    def __init__(self, url, status, text, ctype):
        self.url, self.status_code, self.text = url, status, text
        self.headers, self.history, self.elapsed = {"content-type": ctype}, [], timedelta(0)


class _FakeHttpx:
    """Just enough of httpx for bundle.build: Client(...).get(url) and HTTPError."""
    HTTPError = Exception

    def __init__(self, routes, log):
        self.routes, self.log = routes, log

    def Client(self, **_):
        return self

    def get(self, url, timeout=None):
        self.log.append(_urlparse(url).path or "/")
        status, body = self.routes.get(self.log[-1], (404, ""))
        ctype = "text/plain" if url.endswith(".txt") else ("application/xml" if url.endswith(".xml") else "text/html")
        return _Resp(url, status, body, ctype)

    def close(self):
        pass


def crawl(routes, **kw):
    log, sleeps = [], []
    fake = _FakeHttpx(routes, log)
    saved = bundle_mod._httpx, bundle_mod._sleep
    bundle_mod._httpx, bundle_mod._sleep = (lambda: fake), sleeps.append
    try:
        b = bundle_mod.build("https://t.test/", max_pages=10, **kw)
    finally:
        bundle_mod._httpx, bundle_mod._sleep = saved
    return b, log, sleeps


HOME_HTML = H(body='<h1>Home</h1><a href="/a">A</a> <a href="/b">B</a> <a href="/c">C</a>')
PAGE_HTML = H(body="<h1>Inner</h1><p>Some inner page copy.</p>")

one_503, log1, _ = crawl({"/": (200, HOME_HTML), "/a": (503, ""), "/b": (200, PAGE_HTML), "/c": (200, PAGE_HTML)})
check("a single 503 on an inner page does not stop the crawl", one_503.coverage["pages_fetched"], 4)
two_503, log2, _ = crawl({"/": (200, HOME_HTML), "/a": (503, ""), "/b": (503, ""), "/c": (200, PAGE_HTML)})
check("a second consecutive 503 stops it", (two_503.coverage["pages_fetched"], "/c" in log2), (3, False))
check("...and the note says why", any("crawl stopped" in n for n in two_503.notes), True)
start_503, _, _ = crawl({"/": (503, ""), "/a": (200, PAGE_HTML)})
check("a 503 on the start URL stops at once", start_503.coverage["pages_fetched"], 1)
r429, log3, _ = crawl({"/": (200, HOME_HTML), "/a": (429, ""), "/b": (200, PAGE_HTML)})
check("a 429 always stops the crawl", (r429.coverage["pages_fetched"], "/b" in log3), (2, False))

polite, log4, sleeps4 = crawl({"/": (200, HOME_HTML), "/a": (200, PAGE_HTML), "/b": (200, PAGE_HTML),
                               "/c": (200, PAGE_HTML), "/robots.txt": (200, "User-agent: *\nAllow: /\n"),
                               "/sitemap.xml": (200, "<urlset><url><loc>https://t.test/b</loc></url></urlset>")})
check("robots, sitemap, llms.txt and pages are all fetched through one paced client",
      log4[:4], ["/robots.txt", "/sitemap.xml", "/llms.txt", "/"])
check("every request after the first waits for the polite delay",
      len(sleeps4) == len(log4) - 1 and all(0 < s <= bundle_mod.MAX_HONOURED_CRAWL_DELAY for s in sleeps4), True)

saved_budget = bundle_mod.SITEMAP_BUDGET_S
bundle_mod.SITEMAP_BUDGET_S = 0
try:
    no_budget, log5, _ = crawl({"/": (200, HOME_HTML),
                                "/sitemap.xml": (200, "<urlset><url><loc>https://t.test/b</loc></url></urlset>")})
finally:
    bundle_mod.SITEMAP_BUDGET_S = saved_budget
check("the sitemap walk stops when its own budget is spent",
      (no_budget.robots["sitemaps_fetched"], any("sitemap walk stopped" in n for n in no_budget.notes)),
      (0, True))


# ---------------------------------------------------------------------------
print("\n[final gate] verifier: weak ops, every-page fields, link scrub, step length, template twins")
weak = [rclaim("Title is non-empty and page has words",
               [{"url": HOME, "type": "field", "path": "title", "op": "nonempty"},
                {"url": HOME, "type": "field", "path": "words_extracted", "op": "gt", "value": 1},
                {"url": HOME, "type": "text_lacks", "value": "testimonial"}], [HOME]),
        rclaim("Language is English on this page",
               [{"url": HOME, "type": "field", "path": "lang", "op": "eq", "value": "en"}], [HOME])]
weak_rep = replay_claims(JUDGES, _write("weak.claims.json", {"claims": weak}))
check("nonempty/gt carry no claim on their own", agent_findings(weak_rep), [])
check("...rejected as absence-only", "every assertion is an absence" in rejections(weak_rep)
      or "identity field" in rejections(weak_rep), True)
check("a field value true of every page is rejected", "true of every page" in rejections(weak_rep), True)

evil = [rclaim("Protocol-relative link", [{"url": HOME, "type": "text_contains", "value": quote}], [HOME],
               how=("Install the fix from //evil.example/pay",)),
        rclaim("Bare www link", [{"url": HOME, "type": "text_contains", "value": quote}], [HOME],
               summary="See www.evil.example for the fix"),
        rclaim("Overlong step", [{"url": HOME, "type": "text_contains", "value": quote}], [HOME],
               how=("x" * 400,))]
evil_rep = replay_claims(JUDGES, _write("evil.claims.json", {"claims": evil}))
check("//host and bare www. links are rejected", rejections(evil_rep).count("markup or external links"), 2)
check("a 400-character step is rejected", "longer than 300" in rejections(evil_rep), True)
check("none of them merged", agent_findings(evil_rep), [])

onsite_claim = rclaim("Homepage offers no route for a visitor who came to check one fact",
                      [{"url": HOME, "type": "text_contains", "value": quote}], [HOME],
                      mechanism="on-site", hurts="user_retention")
twin_rep = replay_claims(JUDGES, _write("twin.claims.json", {"claims": [onsite_claim]}))
check("a site-wide E11_no_viewport does not swallow an unrelated retention claim",
      [f["title"] for f in agent_findings(twin_rep)], [onsite_claim["title"]])
