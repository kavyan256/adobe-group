#!/usr/bin/env python3
"""Test suite. No network access required.

  python3 tests/run_tests.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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
print("\nManifest & schema")
mf = json.loads((ROOT / "marketplace.json").read_text())
entry = [s for s in mf["skills"] if s.get("entrypoint")]
check("exactly one entrypoint", len(entry), 1)
check("every listed skill folder exists",
      all((ROOT / s["path"]).is_dir() for s in mf["skills"]), True)
check("every skill folder has a SKILL.md",
      all((ROOT / s["path"] / "SKILL.md").is_file() for s in mf["skills"]), True)

for s in mf["skills"]:
    text = (ROOT / s["path"] / "SKILL.md").read_text()
    ok = text.startswith("---") and "\nname:" in text and "description:" in text \
        and "license:" in text
    check(f"{s['id']}: valid frontmatter", ok, True)

json.loads((ROOT / "schema" / "audit-report.schema.json").read_text())
check("report schema is valid JSON", True, True)

# ---------------------------------------------------------------------------
print(f"\n{'=' * 58}")
print(f"  {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for name in FAIL:
        print(f"    FAILED: {name}")
print(f"{'=' * 58}\n")
raise SystemExit(1 if FAIL else 0)
