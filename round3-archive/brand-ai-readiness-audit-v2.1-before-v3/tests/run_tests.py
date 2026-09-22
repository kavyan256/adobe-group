#!/usr/bin/env python3
"""Test suite. No network access required.

  python3 tests/run_tests.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# No __pycache__ in the marketplace: the env var covers child processes, the
# flag covers our own imports.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "audit-orchestrator" / "scripts"))

PASS, FAIL = [], []


def check(name: str, got, want) -> None:
    (PASS if got == want else FAIL).append(name)
    flag = "ok  " if got == want else "FAIL"
    extra = "" if got == want else f"   got={got!r} want={want!r}"
    print(f"  {flag} {name}{extra}")


# ---------------------------------------------------------------------------
print("\nRFC 9309 robots.txt conformance")
from robots import Robots, classify_agent  # noqa: E402

R = Robots("""
User-agent: *
Disallow: /private/
Allow: /private/public/

User-agent: GPTBot
Disallow: /

User-agent: OAI-SearchBot
Allow: /
Disallow: /internal/

Crawl-delay: 5
Sitemap: https://x.test/sitemap.xml
""")
check("'*' group disallow applies",          R.allowed("Anon", "/private/x"), False)
check("longest-match Allow beats Disallow",  R.allowed("Anon", "/private/public/y"), True)
check("unmatched path is allowed",           R.allowed("Anon", "/other"), True)
check("specific group blocks everything",    R.allowed("GPTBot", "/anything"), False)
check("'*' never applies additively",        R.allowed("GPTBot", "/private/public/y"), False)
check("longer Disallow beats shorter Allow", R.allowed("OAI-SearchBot", "/internal/a"), False)
check("Allow: / permits other paths",        R.allowed("OAI-SearchBot", "/public"), True)
check("sitemap captured",                    R.sitemaps, ["https://x.test/sitemap.xml"])

check("4xx robots => allow all",  Robots("User-agent: *\nDisallow: /", status=404).allowed("X", "/a"), True)
check("5xx robots => disallow",   Robots("", status=503).allowed("X", "/a"), False)
check("empty Disallow => allow",  Robots("User-agent: *\nDisallow:").allowed("X", "/a"), True)

print("\nAgent taxonomy — retrieval vs training")
check("OAI-SearchBot is retrieval",     classify_agent("OAI-SearchBot"), "retrieval")
check("Claude-User is retrieval",       classify_agent("Claude-User"), "retrieval")
check("GPTBot is training-only",        classify_agent("GPTBot"), "training")
check("Google-Extended is training",    classify_agent("Google-Extended"), "training")
check("CCBot is training",              classify_agent("CCBot"), "training")
check("Applebot is retrieval",          classify_agent("Applebot"), "retrieval")
check("Applebot-Extended is training",  classify_agent("Applebot-Extended"), "training")
check("agent match is case-insensitive", classify_agent("gptbot"), "training")

# ---------------------------------------------------------------------------
print("\nSeverity table")
from model import Finding  # noqa: E402


def sev(check_id, **kw):
    f = Finding(check_id=check_id, title="t", evidence="e",
                suggested_action={"summary": "s", "priority": "high"}, **kw)
    return f.finalise(1, kw.pop("_cov", 10)).severity


check("site-wide critical stays critical",
      sev("A1_retrieval_agent_blocked", blast_radius="site_wide"), "critical")
check("single-page demotes one band",
      sev("A1_retrieval_agent_blocked", blast_radius="single_page"), "high")
check("static_heuristic caps at medium",
      sev("B1_fact_absent", blast_radius="site_wide",
          measurement_basis="static_heuristic"), "medium")
check("latent caps at low",
      sev("B1_fact_absent", blast_radius="site_wide", status="latent"), "low")
check("T2 (script-only) is medium, not high",
      sev("B1_fact_script_only", blast_radius="site_wide"), "medium")

f = Finding(check_id="A2_snippet_suppressed", title="t", evidence="e",
            suggested_action={"summary": "s", "priority": "high"},
            blast_radius="template").finalise(1, 10)
check("severity_rationale shows the arithmetic",
      "base=high" in f.severity_rationale and "blast=template" in f.severity_rationale, True)

low_cov = Finding(check_id="A1_retrieval_agent_blocked", title="t", evidence="e",
                  suggested_action={"summary": "s", "priority": "high"},
                  blast_radius="single_page").finalise(1, 1)
check("coverage floor suppresses blast demotion", low_cov.severity, "critical")
check("engagement findings are tagged user_retention",
      Finding(check_id="E1_form_friction", title="t", evidence="e", suggested_action={}
              ).finalise(1, 10).hurts, "user_retention")
check("access findings are tagged ai_discoverability",
      Finding(check_id="A3_noindex", title="t", evidence="e", suggested_action={}
              ).finalise(1, 10).hurts, "ai_discoverability")

# ---------------------------------------------------------------------------
print("\nExtraction tiering (end-to-end, fixture)")
fixture = ROOT / "tests" / "fixtures" / "extraction_tiers.bundle.json"
script = ROOT / "skills" / "fact-extractability-audit" / "scripts" / "check_extractability.py"
proc = subprocess.run([sys.executable, str(script), str(fixture)],
                      capture_output=True, text=True)
check("skill exits cleanly", proc.returncode, 0)
findings = json.loads(proc.stdout) if proc.returncode == 0 else []
by_id = {f["check_id"]: f for f in findings}

check("T3 page fires fact_absent", "B1_fact_absent" in by_id, True)
check("T3 finding names only the absent page",
      by_id.get("B1_fact_absent", {}).get("affected_urls"),
      ["https://synthetic.test/pricing-absent"])
check("T2 page fires fact_script_only", "B1_fact_script_only" in by_id, True)
check("T2 finding names only the payload page",
      by_id.get("B1_fact_script_only", {}).get("affected_urls"),
      ["https://synthetic.test/pricing-payload"])
check("T0 page (price in prose) produces no B1 finding",
      any("pricing-visible" in u
          for f in findings if f["check_id"].startswith("B1")
          for u in f["affected_urls"]), False)
check("T2 evidence names the payload island",
      "__NEXT_DATA__" in by_id.get("B1_fact_script_only", {}).get("evidence", ""), True)


# ---------------------------------------------------------------------------
print("\nJSON-LD normalisation")
import bundle as bundle_mod
from bs4 import BeautifulSoup


def _ld(payload: str) -> dict:
    html = f'<html><head><script type="application/ld+json">{payload}</script></head><body></body></html>'
    return bundle_mod.normalise_jsonld(BeautifulSoup(html, "html.parser"))


graph = _ld('{"@context":"https://schema.org","@graph":['
            '{"@type":"WebSite","name":"S"},'
            '{"@type":["Organization","Corporation"],"name":"S","sameAs":["https://wikidata.org/Q1"]}]}')
check("@graph members are hoisted into the node stream", len(graph["nodes"]), 2)
check("list-valued @type is normalised", "organization" in graph["types_present"], True)
check("@graph-nested sameAs is found", graph["sameas"], ["https://wikidata.org/Q1"])
check("bare @graph wrapper is not itself a node",
      any(n["types"] == [] for n in graph["nodes"]), False)

nested = _ld('{"@type":"ItemList","itemListElement":['
             '{"@type":"Product","offers":{"@type":"Offer","price":"12.00"}}]}')
check("nested entities are collected", "product" in nested["types_present"], True)
check("nested offer stays reachable inside its parent",
      any(n["props"].get("offers", {}).get("price") == "12.00"
          for n in nested["nodes"] if "product" in n["types"]), True)

check("IRI @type is reduced to a bare name",
      _ld('{"@type":"http://schema.org/Organization","name":"x"}')["types_present"],
      ["organization"])
check("prefixed @type is reduced to a bare name",
      _ld('{"@type":"schema:Organization","name":"x"}')["types_present"],
      ["organization"])

comment_wrapped = bundle_mod.normalise_jsonld(BeautifulSoup(
    '<script type="application/ld+json"><!--{"@type":"Organization","name":"x"}--></script>',
    "html.parser"))
check("a comment-wrapped block still parses (tag.string is None)",
      comment_wrapped["types_present"], ["organization"])

check("unparseable JSON counts as malformed", _ld("{not json")["malformed_blocks"], 1)
check("an empty block is inert, not malformed", _ld("   ")["malformed_blocks"], 0)
check("an empty block is counted separately", _ld("   ")["empty_blocks"], 1)

two = bundle_mod.normalise_jsonld(BeautifulSoup(
    '<script type="application/ld+json">{"@type":"Organization","name":"a"}</script>'
    '<script type="application/ld+json">{"@type":"Product","name":"b"}</script>', "html.parser"))
check("multiple ld+json tags merge into one stream", two["types_present"],
      ["organization", "product"])

# ---------------------------------------------------------------------------
print("\nText normalisation (one definition per notion)")
txt = bundle_mod.normalise_text(BeautifulSoup(
    "<html><body><nav>Nav junk</nav><main><p>Real body copy.</p></main>"
    "<script>var c = '(c) 2019 stale'; var p = '$1999';</script>"
    "<footer>(c) 2019 Acme</footer></body></html>", "html.parser"))
check("chrome is excluded from extracted", "Nav junk" in txt["extracted"], False)
check("body copy survives extraction", "Real body copy." in txt["extracted"], True)
check("footer is kept in full", "2019 Acme" in txt["full"], True)
check("script bodies appear in neither",
      "stale" in txt["full"] or "stale" in txt["extracted"], False)

# ---------------------------------------------------------------------------
print("\nRobots: exact product-token matching (RFC 9309 2.2.1)")
partial = Robots("User-agent: Claude\nDisallow: /\n", status=200)
check("a partial token matches no crawler", partial.allowed("ClaudeBot", "/"), True)
check("a partial token matches no crawler (retrieval too)",
      partial.allowed("Claude-User", "/"), True)
check("the useless rule is surfaced, not silently dropped",
      [u["token"] for u in partial.unrecognised_agent_tokens()], ["Claude"])
exact = Robots("User-agent: ClaudeBot\nDisallow: /\n", status=200)
check("an exact token still blocks its own crawler", exact.allowed("ClaudeBot", "/"), False)
check("an exact token does not block a different crawler",
      exact.allowed("Claude-User", "/"), True)
check("a real token is not reported as unrecognised",
      exact.unrecognised_agent_tokens(), [])
check("a full crawler token we do not list is not reported (no A8 false positive)",
      Robots("User-agent: Google-CloudVertexBot\nDisallow: /\n"
             "User-agent: Meta-ExternalFetcher\nDisallow: /\n").unrecognised_agent_tokens(), [])

named = Robots("User-agent: OAI-SearchBot\nDisallow: /internal/\n", status=200)
check("explain quotes the deciding rule",
      named.explain("OAI-SearchBot", "/internal/x")["rule"], "Disallow: /internal/")
check("a named group is not via_wildcard",
      named.explain("OAI-SearchBot", "/internal/x")["via_wildcard"], False)
wild = Robots("User-agent: *\nDisallow: /\n", status=200)
check("a wildcard block is marked via_wildcard",
      wild.explain("OAI-SearchBot", "/")["via_wildcard"], True)

# ---------------------------------------------------------------------------
print("\nIntent-aware severity")
check("confirm_intent caps at low",
      sev("A3_noindex_utility", status="confirm_intent", blast_radius="site_wide"), "low")
check("confirm_intent records its reasoning",
      "cap(confirm_intent)" in Finding(
          check_id="A3_noindex_utility", title="t", evidence="e", suggested_action={},
          blast_radius="site_wide", status="confirm_intent"
      ).finalise(1, 10).severity_rationale, True)
check("latent takes precedence over confirm_intent",
      "cap(latent)" in Finding(
          check_id="A3_noindex_utility", title="t", evidence="e", suggested_action={},
          blast_radius="site_wide", status="latent"
      ).finalise(1, 10).severity_rationale, True)
check("intent_signals survive to the report",
      Finding(check_id="A3_noindex_utility", title="t", evidence="e", suggested_action={},
              status="confirm_intent", intent_signals=["because"]
              ).finalise(1, 10).to_report()["intent_signals"], ["because"])

# ---------------------------------------------------------------------------
print("\nPrice comparison is numeric, not substring")
sys.path.insert(0, str(ROOT / "skills" / "fact-extractability-audit" / "scripts"))
import check_extractability as X
check("a year does not satisfy a declared price",
      99.0 in X._price_tokens("Founded in 1999, trusted since then."), False)
check("a currency-marked price does",
      99.0 in X._price_tokens("Plans from $99 per month."), True)
check("a bare number is not a price",
      X._price_tokens("You get 99 credits."), set())

# ---------------------------------------------------------------------------
print("\nSeverity table integrity")
emitted, declared_skipped = set(), set()
for script in sorted((ROOT / "skills").glob("*/scripts/check_*.py")):
    # checks_skipped[] entries name a check we deliberately did NOT run; those
    # have no severity by definition.
    declared_skipped |= set(re.findall(r'"check":\s*"([A-Za-z0-9_\-]+)"', script.read_text()))
    # Any check-id-shaped string literal: ids are also written inline in
    # conditionals ("A3_noindex_utility" if deliberate else "A3_noindex").
    emitted |= set(re.findall(r'"([A-Z]\d*_[a-z][A-Za-z0-9_]+)"', script.read_text()))
from model import SEVERITY_TABLE
emitted -= declared_skipped
check("every emitted check has a published severity", sorted(emitted - set(SEVERITY_TABLE)), [])
check("the table promises no check that is never emitted",
      sorted(set(SEVERITY_TABLE) - emitted), [])

# ---------------------------------------------------------------------------
print("\nRegression fixtures (end-to-end through the entrypoint)")
AUDIT = ROOT / "skills" / "audit-orchestrator" / "scripts" / "audit.py"


def replay(name):
    proc = subprocess.run(
        [sys.executable, str(AUDIT), "--replay",
         str(ROOT / "tests" / "fixtures" / name)],
        capture_output=True, text=True, cwd=str(ROOT))
    return json.loads(proc.stdout) if proc.returncode == 0 else {"findings": [], "_err": proc.stderr}


rep = replay("graph_jsonld.bundle.json")
ids = [f["check_id"] for f in rep["findings"]]
check("an @graph-wrapped Organization does NOT fire C3 (the confirmed FP)",
      "C3_entity_unanchored" in ids, False)
check("a page with @graph is not reported as having no structured data",
      "C1_structured_data_absent" in ids, False)
d5 = next((f for f in rep["findings"] if f["check_id"] == "D5_no_corroboration_hooks"), None)
check("D5 does not claim sameAs is missing when it is published",
      "sameAs" in (d5 or {}).get("evidence", ""), False)
check("...and already_in_place agrees sameAs is published",
      any("sameAs" in a["because"] for a in rep.get("already_in_place", [])), True)

deliberate = replay("intent_noindex.bundle.json")
a3 = next((f for f in deliberate["findings"] if f["check_id"].startswith("A3")), {})
check("noindex confined to legal/utility reads as deliberate",
      a3.get("status"), "confirm_intent")
check("...and is capped at low", a3.get("severity"), "low")
check("...and carries its reasoning", bool(a3.get("intent_signals")), True)
check("...and never becomes the headline",
      "noindex" in deliberate["summary"]["headline"], False)

real = replay("content_noindex.bundle.json")
a3r = next((f for f in real["findings"] if f["check_id"].startswith("A3")), {})
check("noindex on home/pricing stays a defect", a3r.get("status"), "active")
check("...and stays critical", a3r.get("severity"), "critical")

fresh = replay("new_checks.bundle.json")
fresh_ids = [f["check_id"] for f in fresh["findings"]]
check("question headings without FAQ markup are detected",
      "C5_faq_content_unmarked" in fresh_ids, True)
check("a site stating three different names for itself is detected",
      "C6_entity_name_conflict" in fresh_ids, True)
check("a content dead end is detected despite a site-wide nav",
      "E10_no_next_step" in fresh_ids, True)
check("C5 quotes the actual headings as evidence",
      "?" in next(f["evidence"] for f in fresh["findings"]
                  if f["check_id"] == "C5_faq_content_unmarked"), True)

# The graph fixture is well-formed on all three: none of them may fire there.
check("the new checks do not fire on a well-formed site",
      sorted({"C5_faq_content_unmarked", "C6_entity_name_conflict",
              "E10_no_next_step"} & set(ids)), [])

filler = replay("filler_heavy.bundle.json")
check("site-wide filler is detected",
      "B6_filler_heavy" in [f["check_id"] for f in filler["findings"]], True)

check("every replayed fixture ran all four skills",
      [s["check"] for r in (rep, deliberate, real, fresh, filler)
       for s in r.get("checks_skipped", []) if s["check"].endswith("-audit")], [])

# ---------------------------------------------------------------------------
print(f"\n{'=' * 58}")
print(f"  {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for name in FAIL:
        print(f"    FAILED: {name}")
print(f"{'=' * 58}\n")
raise SystemExit(1 if FAIL else 0)
