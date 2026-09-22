#!/usr/bin/env python3
"""Entrypoint: fetch once, invoke each sub-skill, compose one audit report.

Usage
-----
    python3 audit.py https://example.com [-o report.json] [--bundle b.json]
    python3 audit.py --replay b.json -o report.json     # deterministic re-run
    python3 audit.py --replay b.json --agent-claims claims.json -o report.json

Composition model
-----------------
1. Build a site bundle (one polite, read-only crawl).
2. Invoke each sub-skill's check script as a separate process, passing the bundle.
   Sub-skills never import from each other or from here -- each skill folder stays
   independently installable and runnable.
3. Merge their findings, mark blocked-but-real findings as `latent`, derive
   severity from the published table, prioritise, and emit a single report.

Given a fixed bundle the analysis is deterministic; `--replay` re-runs it.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

sys.dont_write_bytecode = True  # keep __pycache__ out of the marketplace
sys.path.insert(0, str(Path(__file__).parent))
from model import AGENT_REVIEW_CHECK, SEVERITY_TABLE, Finding, hurts_for  # noqa: E402
import bundle as bundle_mod                    # noqa: E402

SKILLS_DIR = Path(__file__).resolve().parents[2]

SUB_SKILLS = [
    ("crawl-access-audit",            "scripts/check_access.py"),
    ("fact-extractability-audit",     "scripts/check_extractability.py"),
    ("freshness-corroboration-audit", "scripts/check_freshness.py"),
    ("engagement-audit",              "scripts/check_engagement.py"),
]
# Runs only when an agent review supplied claims (--agent-claims): it turns the
# claims that hold against the bundle into findings and rejects the rest.
AGENT_REVIEW = ("agent-review-audit", "scripts/verify_claims.py")
# Runs when the claims file carries verdicts on scripted findings.
AGENT_VERDICTS = ("agent-review-audit", "scripts/verify_verdicts.py")

SEV_WEIGHT = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
EFFORT_WEIGHT = {"low": 1.0, "medium": 1.6, "high": 2.4}

# Which gates a claim's mechanism speaks to. A claim on a page that a scripted
# finding of the same gate already reports is a restatement of that finding,
# whatever the reviewer wrote in nearest_check.
CLAIM_GATES = {
    "A": {"access"},
    "B": {"interpretability", "extractability"},
    "C": {"interpretability", "extractability"},
    "D": {"freshness"},
    "E": {"engagement"},
    "F": {"engagement", "extractability"},
    "on-site": {"engagement"},
}

# Proactive recommendations are conditioned on the site: each carries an
# `applies(bundle, check_ids)` test, and ones the site already satisfies go to
# `already_in_place` instead. They read the same normalised JSON-LD as the
# sub-skills, so a recommendation cannot contradict a finding.


def _ok_pages(b: dict) -> list[dict]:
    return [p for p in b["pages"]
            if 200 <= p["status"] < 300 and p["html"] and isinstance(p.get("derived"), dict)]


def _ok_derived(b: dict):
    return [p["derived"] for p in _ok_pages(b)]


def _has_llms_txt(b, _):
    return bool(b.get("probes", {}).get("llms_txt", {}).get("present"))


def _names_ai_agents(b, _):
    return bool(b.get("probes", {}).get("ai_agents_named_in_robots"))


def _has_faq_markup(b, _):
    return any("faqpage" in d["jsonld"]["types_present"] for d in _ok_derived(b))


# Organisation-like JSON-LD types, the same predicate fact-extractability-audit
# uses for C3 (copied, not imported: skills stay independent), so the citable-
# facts recommendation never contradicts that finding.
_ORG_SUFFIXES = ("organization", "organisation", "business", "store", "corporation",
                 "restaurant", "company", "agency", "shop")
_ORG_LEAF_TYPES = {"dentist", "physician", "attorney", "hotel", "bakery", "cafeorcoffeeshop",
                   "barorpub", "brand", "hospital", "pharmacy", "school", "collegeoruniversity",
                   "library", "museum", "gym", "healthclub", "realestateagent", "autodealer",
                   "autorepair", "medicalclinic", "lodgingbusiness", "foodestablishment",
                   "professionalservice", "financialservice", "bank", "insuranceagency",
                   "travelagency", "hairsalon", "beautysalon", "daycare", "veterinarycare",
                   "hardwarestore", "clothingstore", "electronicsstore", "grocerystore"}


def _is_org_like(types: list[str]) -> bool:
    return any(t.endswith(_ORG_SUFFIXES) or t in _ORG_LEAF_TYPES for t in types)


def _has_sameas(b, _):
    return any(_is_org_like(n["types"]) and n["props"].get("sameAs")
               for d in _ok_derived(b) for n in d["jsonld"]["nodes"])


def _is_hydrated_app(b, _):
    return any(d["payload_islands"] for d in _ok_derived(b))


def _first_screen_answers(b, _):
    """True when the homepage's first 60 extracted words already contain something
    concrete to act on: a number, a price, or the site's own name."""
    site_name = (b.get("site") or "").lower().removeprefix("www.").split(".")[0]
    if len(site_name) < 3:          # "t" or "ab" would match almost any opening
        site_name = ""
    for p in _ok_pages(b):
        if p["role"] == "home":
            head = " ".join(p["derived"]["text"]["extracted"].split()[:60]).lower()
            return any(ch.isdigit() or ch in "$€£¥" for ch in head) \
                or bool(site_name and site_name in head)
    return True   # no readable homepage: nothing to recommend against


def _deep_pages_route_onward(b, c):
    """True when every non-home, non-legal page of 100+ words has at least one
    in-content link to another page on the same host (nav/header/footer/aside
    removed), and E10 did not fire."""
    if "E10_no_next_step" in c:
        return False
    for p in _ok_pages(b):
        if p["role"] in ("home", "legal") or len(p["derived"]["text"]["extracted"].split()) < 100:
            continue
        body = BeautifulSoup(p["html"], "html.parser")
        for t in body.find_all(["nav", "header", "footer", "aside", "script", "style"]):
            t.decompose()
        host, own = urlparse(p["url"]).netloc, p["url"].split("#")[0].rstrip("/")
        if not any(urlparse(a["href"]).netloc in ("", host)
                   and not a["href"].startswith(("#", "javascript:"))
                   and a["href"].split("#")[0].rstrip("/") not in ("", own)
                   for a in body.find_all("a", href=True)):
            return False
    return True


PROACTIVE = [
    {"title": "Publish an llms.txt describing your site for AI clients",
     "rationale": "An emerging convention: a short, stable, plain-text map of what your site "
                  "covers and where the authoritative pages are. Cheap to add, and it gives "
                  "retrieval agents an unambiguous starting point.",
     "effort": "low",
     "applies": lambda b, c: not _has_llms_txt(b, c),
     "applies_because": "GET /llms.txt did not return a plain-text document",
     "in_place_because": "/llms.txt is present"},
    {"title": "Decide your AI-crawler policy deliberately, and write it down",
     "rationale": "Training access and retrieval access are separate decisions. Blocking training "
                  "crawlers while explicitly allowing retrieval agents is a coherent, defensible "
                  "position - but it has to be configured on purpose, per user-agent.",
     "effort": "low",
     "applies": lambda b, c: not _names_ai_agents(b, c),
     "applies_because": "robots.txt names no AI retrieval or training agent, so the current "
                        "policy is whatever the wildcard group happens to say",
     "in_place_because": "robots.txt already addresses AI agents by name"},
    {"title": "Add a machine-readable FAQ layer shaped for quotation",
     "rationale": "FAQPage structured data pairs a question with a self-contained answer. That is "
                  "exactly the shape an assistant wants to lift, and it survives text extraction.",
     "effort": "medium",
     "applies": lambda b, c: not _has_faq_markup(b, c),
     "applies_because": "no crawled page carries FAQPage JSON-LD",
     "in_place_because": "FAQPage JSON-LD found on at least one crawled page"},
    {"title": "Publish a stable, citable facts page",
     "rationale": "Founding date, leadership, HQ, product line, pricing - in one durable URL that "
                  "third parties can cite verbatim. Corroboration across independent sources is "
                  "what makes a claim credible to a machine, and you can seed it.",
     "effort": "medium",
     "applies": lambda b, c: not _has_sameas(b, c),
     "applies_because": "no crawled page declares Organization sameAs links, so there is no "
                        "anchor for third parties to corroborate against",
     "in_place_because": "Organization sameAs links are already published"},
    {"title": "Server-render your most-quoted facts even inside a SPA",
     "rationale": "You do not have to abandon client-side rendering. Server-render the handful of "
                  "facts you most want cited - price, what you do, how to contact you - and let "
                  "the rest hydrate.",
     "effort": "high",
     # Only relevant to a hydrated app; and if B1/B4 already fired, the finding
     # carries this exact fix and repeating it here would be padding.
     "applies": lambda b, c: _is_hydrated_app(b, c)
                             and not ({"B1_fact_script_only", "B4_empty_shell", "B1_fact_absent"} & c),
     "applies_because": "the site ships a client-side hydration payload; its key facts currently "
                        "extract fine, so this is about keeping it that way as the app grows",
     "in_place_because": "not a client-rendered app, or a specific finding already covers it"},
    # -- orientation: a visitor from an AI answer lands mid-site, with a question --
    {"title": "Answer the question visitors arrive with on the first screen",
     "rationale": "A visitor sent by an AI answer arrives with one question already in mind - "
                  "how much, how fast, is this the company I was told about. If the first "
                  "screen of the homepage is a slogan with no number, price or even the "
                  "company name in it, they have to hunt for the confirmation they came for, "
                  "and many leave instead. State who you are and one concrete fact in the "
                  "first sixty words.",
     "effort": "low",
     "applies": lambda b, c: not _first_screen_answers(b, c),
     "applies_because": "the first 60 words of the homepage's extracted text contain no digit, "
                        "price or the site's own name, so a visitor checking an AI answer finds "
                        "nothing concrete to confirm on the first screen",
     "in_place_because": "the homepage's first 60 words already name the site or state a "
                         "concrete figure"},
    {"title": "Every deep page links to its parent section and a contact route",
     "rationale": "AI answers send visitors to deep pages, not the homepage. From there the two "
                  "moves they most often want are 'show me the rest of this section' and "
                  "'let me ask someone'. A breadcrumb (with BreadcrumbList JSON-LD) and one "
                  "contact link inside the content give both without relying on the site-wide "
                  "nav, and the breadcrumb doubles as an orientation and citation signal.",
     "effort": "low",
     "applies": lambda b, c: not _deep_pages_route_onward(b, c),
     "applies_because": "E10_no_next_step fired, or at least one non-home page of 100+ words has "
                        "no in-content link to another page on the site",
     "in_place_because": "every substantial deep page already links onward from its content"},
]


def proactive_for(b: dict, findings: list) -> tuple[list[dict], list[dict]]:
    check_ids = {f.check_id for f in findings}
    applies, in_place = [], []
    for rec in PROACTIVE:
        public = {k: v for k, v in rec.items() if k not in ("applies", "applies_because", "in_place_because")}
        if rec["applies"](b, check_ids):
            applies.append({**public, "applies_because": rec["applies_because"]})
        else:
            in_place.append({"title": rec["title"], "because": rec["in_place_because"]})
    return applies, in_place


def run_sub_skill(folder: str, script: str, bundle_path: Path,
                  timeout_s: float) -> tuple[list, list]:
    path = SKILLS_DIR / folder / script
    if not path.exists():
        return [], [{"check": folder, "reason": f"skill script not found at {path}",
                     "impact": "this concern was not audited"}]
    if timeout_s <= 0:
        return [], [{"check": folder, "reason": "runtime budget exhausted before this skill ran",
                     "impact": "this concern was not audited"}]
    try:
        proc = subprocess.run([sys.executable, str(path), str(bundle_path)],
                              capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return [], [{"check": folder, "reason": f"sub-skill timed out after {timeout_s:.0f}s",
                     "impact": "this concern was not audited"}]
    if proc.returncode != 0:
        return [], [{"check": folder,
                     "reason": f"sub-skill exited {proc.returncode}: {proc.stderr.strip()[:200]}",
                     "impact": "this concern was not audited"}]
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return [], [{"check": folder, "reason": "sub-skill emitted invalid JSON",
                     "impact": "this concern was not audited"}]
    if isinstance(data, dict):
        return data.get("findings", []), data.get("checks_skipped", [])
    return data, []


def run_agent_review(bundle_path: Path, claims_path: Path | None, scripted: list[dict],
                     timeout_s: float) -> tuple[list, list, dict, list]:
    """Verify an agent review's claims. Returns (findings, checks_skipped, review, fixes)."""
    if claims_path is None:
        print("agent review not run - problems outside the scripted checks are not reported; "
              "see agent-review-audit/SKILL.md", file=sys.stderr)
        return [], [], {"status": "not_run"}, []
    not_run = {"check": "agent_review",
               "impact": "Problems outside the scripted checks are not reported. Follow "
                         "agent-review-audit/SKILL.md, then re-run with --agent-claims."}
    folder, script = AGENT_REVIEW
    path = SKILLS_DIR / folder / script
    failure = None
    if not path.exists():
        failure = f"verifier not found at {path}"
    elif timeout_s <= 0:
        failure = "runtime budget exhausted before the agent review was verified"
    else:
        # The verifier needs the scripted findings to know which review candidates
        # a scripted check already covers.
        fd, name = tempfile.mkstemp(prefix="audit-scripted-", suffix=".json")
        os.close(fd)
        scripted_path = Path(name)
        scripted_path.write_text(json.dumps([{"check_id": f.get("check_id"),
                                              "affected_urls": f.get("affected_urls", [])}
                                             for f in scripted]), encoding="utf-8")
        try:
            proc = subprocess.run([sys.executable, str(path), str(bundle_path), str(claims_path),
                                   str(scripted_path)],
                                  capture_output=True, text=True, timeout=timeout_s)
            data = json.loads(proc.stdout) if proc.returncode == 0 else None
            if data is None:
                failure = f"verifier exited {proc.returncode}: {proc.stderr.strip()[:200]}"
        except subprocess.TimeoutExpired:
            failure = f"verifier timed out after {timeout_s:.0f}s"
        except json.JSONDecodeError:
            failure = "verifier emitted invalid JSON"
        finally:
            scripted_path.unlink(missing_ok=True)
    if failure:
        return [], [{**not_run, "reason": failure}], {"status": "failed", "error": failure}, []
    review = {"status": "run", **data.get("review", {})}
    skipped = [{**not_run, "reason": review["error"]}] if review.get("error") else []
    return data.get("findings", []), skipped, review, data.get("fixes", [])


# Template-level checks say something about every page of a site, nothing about
# the topic of a claim: a missing viewport tag must not silence a review claim
# about a dead-end page that happens to share the URL.
TEMPLATE_CHECKS = {"E11_no_viewport", "C7_title_problem", "E5_no_lang", "E6_heading_structure",
                   "E12_no_orientation", "C1_structured_data_absent", "A5_canonical_missing",
                   "E4_images_missing_alt", "E1_unlabelled_input"}


def _restates(claim_detail: dict, scripted: dict) -> bool:
    """Is this scripted finding the same problem the claim describes?

    Yes when the reviewer says so (nearest_check), or when the finding reports
    the same gate for the same audience and is substantial enough to have
    covered it -- a low-base check such as a missing canonical must not swallow
    a claim that happens to share its page.
    """
    spec = SEVERITY_TABLE.get(scripted["check_id"], {})
    if claim_detail.get("nearest_check") == scripted["check_id"]:
        return True
    if spec.get("base", "low") == "low" or scripted["check_id"] in TEMPLATE_CHECKS:
        return False
    hurts = hurts_for(scripted["check_id"], spec.get("gate", ""))
    same_audience = hurts == claim_detail.get("hurts") or "both" in (hurts, claim_detail.get("hurts"))
    mechanism = claim_detail.get("mechanism")
    same_concern = (spec.get("gate") in CLAIM_GATES.get(mechanism, set())
                    or spec.get("mechanism") == mechanism)
    return same_concern and same_audience


def drop_duplicate_claims(scripted: list[dict], agent: list[dict], review: dict) -> list[dict]:
    """A verified claim that restates a scripted finding on the same pages is dropped.

    The scripted finding wins: it has a published severity and a tested check.
    "Same" is decided here, not by the reviewer alone: naming the check in
    nearest_check counts, and so does a medium-or-higher scripted finding of the
    same gate and audience on any of the same pages -- so setting nearest_check
    to null does not get a restatement through.
    """
    kept = []
    for f in agent:
        detail = f.get("detail") or {}
        urls = set(f.get("affected_urls", []))
        twins = sorted({s["check_id"] for s in scripted
                        if urls & set(s.get("affected_urls", [])) and _restates(detail, s)})
        if twins:
            review.setdefault("rejected", []).append({
                "title": f["title"],
                "reason": f"duplicates scripted check {', '.join(twins)}, which already reports "
                          f"these pages for the same gate"})
            continue
        kept.append(f)
    if review.get("status") == "run":
        review["merged"] = len(kept)
    return kept


def merge_fixes(findings: list[Finding], fixes: list[dict], review: dict) -> None:
    """Attach each verified site-specific fix to the finding it was written for.

    The verifier proved the quote is on the page; here we prove the page is one
    the named finding actually reports. One fix per finding.
    """
    merged = 0
    for fix in fixes:
        url = (fix.get("grounded_on") or {}).get("url")
        target = next((f for f in findings
                       if f.check_id == fix.get("check_id") and url in f.affected_urls), None)
        if target is None:
            review.setdefault("rejected_fixes", []).append({
                "check_id": fix.get("check_id"),
                "reason": f"no finding {fix.get('check_id')} reports {url}"})
            continue
        if "grounded_on" in target.suggested_action:
            review.setdefault("rejected_fixes", []).append({
                "check_id": fix.get("check_id"),
                "reason": "a site-specific fix was already merged into this finding"})
            continue
        target.suggested_action["site_specific"] = list(fix.get("site_specific", []))
        target.suggested_action["grounded_on"] = fix["grounded_on"]
        merged += 1
    if review.get("status") == "run":
        review["fixes_merged"] = merged


def mark_latent(raw: list[dict], b: dict) -> list[dict]:
    """Downstream findings on unreachable URLs are demoted, never suppressed.

    Suppressing them would mean the operator fixes the blocker, re-audits, and
    meets a wave of findings nobody warned them about.

    A page is "unreachable" only when EVERY retrieval agent is refused it. robots
    is per-agent: a site that blocks one assistant is still read by the others,
    so its findings stay live at full severity. Engagement findings are never
    latent -- robots.txt and noindex do not stop a human visitor.
    """
    blockers = [f for f in raw if f["check_id"] in ("A1_retrieval_agent_blocked", "A3_noindex")]
    if not blockers:
        return raw
    blocked_urls, agents, blocked_paths = set(), set(), set()
    for blocker in blockers:
        if blocker["check_id"] == "A3_noindex":
            blocked_urls |= set(blocker.get("affected_urls", []))
            agents |= {"all indexing agents"}
            continue
        retrieval = {t: d for t, d in (b.get("robots", {}).get("agents") or {}).items()
                     if d.get("class") == "retrieval"}
        if not retrieval:
            continue
        refused_to_all = set.intersection(*(set(d.get("blocked_paths", []))
                                            for d in retrieval.values()))
        if refused_to_all:
            blocked_paths |= refused_to_all
            agents |= set(retrieval)
    for f in raw:
        # Access findings ARE the blockers (load-bearing: without this a blocker
        # would mark itself unobservable); engagement findings concern humans;
        # an agent-review claim is already capped at low and may be about the
        # blocker itself.
        if f["check_id"].startswith(("A", "E")) or f["check_id"] == AGENT_REVIEW_CHECK:
            continue
        urls = set(f.get("affected_urls", []))
        if urls and blocked_paths and not (urls <= blocked_urls):
            # agent_report paths are exact crawled page paths, not prefixes.
            if all((urlparse(u).path or "/") in blocked_paths for u in urls):
                blocked_urls |= urls
        if urls and urls <= blocked_urls:
            f["status"] = "latent"
            f["blocked_by"] = {
                "finding_check": blockers[0]["check_id"],
                "agents_affected": sorted(agents),
                "note": "Real, but unobservable by the blocked agents until the blocker is fixed.",
            }
    return raw


def apply_verdicts(findings: list[Finding], bundle_path: Path, claims_path: Path, review: dict,
                   pages_ok: int, timeout_s: float) -> list[Finding]:
    """Apply the agent's verified verdicts on scripted findings, before ranking.

    verify_verdicts.py decides which verdicts hold and what each may do; this applies
    the effect and lets the model re-derive severity, so ranking, ids, headline and
    prioritized actions all describe the judged findings.
    """
    snapshot = [f.to_report() for f in findings]
    fd, name = tempfile.mkstemp(prefix="audit-findings-", suffix=".json")
    os.close(fd)
    snapshot_path = Path(name)
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    folder, script = AGENT_VERDICTS
    try:
        proc = subprocess.run([sys.executable, str(SKILLS_DIR / folder / script), str(bundle_path),
                               str(snapshot_path), str(claims_path)],
                              capture_output=True, text=True, timeout=max(1.0, timeout_s))
        data = json.loads(proc.stdout) if proc.returncode == 0 else None
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        data = None
    finally:
        snapshot_path.unlink(missing_ok=True)
    if data is None:
        review["verdicts_error"] = "the verdict verifier failed or timed out; no verdict was applied"
        return findings

    judged = {rec["finding_index"] for rec in data["accepted"]}
    removed = set()
    for rec in data["accepted"]:
        f = findings[rec.pop("finding_index")]
        rec["before"] = {"severity": f.severity, "status": f.status,
                         "affected_url_count": len(set(f.affected_urls))}
        if rec["effect"] == "remove":
            removed.add(id(f))
            review.setdefault("adjudicated_out", []).append(
                {"check_id": f.check_id, "title": f.title, "severity": f.severity,
                 "reason": rec["reason"], "verified_evidence": rec["verified_evidence"]})
            rec["after"] = "removed"
            continue
        if rec["effect"] == "clear_urls":
            f.affected_urls = [u for u in f.affected_urls if u not in rec["urls"]]
        if rec["effect"] == "confirm_intent":
            f.status = "confirm_intent"
        f.detail["agent_verdict"] = {"verdict": rec["verdict"], "reason": rec["reason"]}
        f.finalise(0, pages_ok)
        rec["after"] = {"severity": f.severity, "status": f.status,
                        "affected_url_count": len(set(f.affected_urls))}
    review.update(verdicts_submitted=data["submitted"], verdicts_applied=len(data["accepted"]),
                  verdicts_rejected=data["rejected"], adjudications=data["accepted"],
                  unjudged_medium_or_above=[
                      {"check_id": s["check_id"], "severity": s["severity"]}
                      for i, s in enumerate(snapshot)
                      if i not in judged and s["source"] == "scripted"
                      and s["severity"] in ("medium", "high", "critical")])
    return [f for f in findings if id(f) not in removed]


def priority_score(f: Finding) -> float:
    sev = SEV_WEIGHT.get(f.severity, 1)
    conf = 1.0 if f.confidence == "deterministic" else 0.7
    # The reviewer chose the effort on an agent-review claim; ranking must not
    # reward a claim for calling itself easy, so those count as medium.
    effort_key = "medium" if f.check_id == AGENT_REVIEW_CHECK \
        else f.suggested_action.get("effort", "medium")
    effort = EFFORT_WEIGHT.get(effort_key, 1.6)
    # A finding the owner may have configured on purpose ranks below an equally
    # severe real defect, and above one that is not yet observable.
    status_weight = {"latent": 0.35, "confirm_intent": 0.5}.get(f.status, 1.0)
    return round(sev * conf * status_weight / effort, 3)


def rank(findings: list[Finding]) -> list[Finding]:
    """Severity band first, then priority within the band, then a stable tie-break."""
    return sorted(findings, key=lambda f: (-SEV_WEIGHT.get(f.severity, 0), -priority_score(f),
                                           f.check_id, f.title, sorted(f.affected_urls)[:1]))


# What a static crawl structurally cannot see. Same shape as the sub-skills'
# checks_skipped entries ("Not assessed / Reason / How to check it yourself"),
# so the two lists say the same thing where they overlap.
LIMITS = [
    "Not assessed: behaviour metrics (bounce rate, dwell time, scroll depth, conversion). "
    "Reason: a crawl sees markup, never visitors; engagement findings are structural risk "
    "factors, capped at medium for that reason. How to check it yourself: in your analytics, "
    "segment sessions by referrer (chatgpt.com, perplexity.ai, claude.ai) and compare their "
    "conversion rate with search traffic.",
    "Not assessed: the rendered experience (layout, overlays and cookie banners, colour "
    "contrast, Core Web Vitals) and facts loaded by client-side requests after page load. "
    "Reason: no JavaScript is executed and no browser is used - which is also what "
    "non-rendering AI retrieval agents see; a fact fetched only by XHR can be a false "
    "negative here. How to check it yourself: run Lighthouse and axe on the top three "
    "templates, and open a key page with JavaScript disabled to see what a bot gets.",
    "Not assessed: copy quality - whether the words persuade, or answer the visitor's "
    "question well. Reason: subjective, with no static threshold that holds across "
    "industries and languages; the scripted checks measure only structure and vocabulary "
    "overlap. How to check it yourself: read the first paragraph of the homepage and one "
    "product page to someone outside the company and ask what the site offers and for whom.",
    "Not assessed: anything behind a login, checkout step or account area. Reason: the "
    "audit is read-only and never authenticates, submits a form or creates an account. "
    "How to check it yourself: walk the signup, checkout or booking flow with a test "
    "account and count the required steps and fields.",
    "Not assessed: personalization of AI answers (appendix E). Reason: it happens inside "
    "the assistant, from the user's own context, and no site-side measurement exists; the "
    "site-side lever - self-contained, quotable facts - is what the extraction and "
    "quotability checks cover. How to check it yourself: ask an assistant the same "
    "question about your brand in a fresh session and in a long-running one, and compare.",
    "Not assessed: cross-web corroboration - whether independent sources agree with the "
    "site's facts. Reason: it needs a search backend and off-site fetches, which this "
    "audit does not make; only on-site corroboration hooks (sameAs, press links) are "
    "checked. How to check it yourself: search Wikipedia, Wikidata, Crunchbase and the "
    "press for your founding date, HQ, leadership and pricing, and reconcile differences.",
    "Not assessed: problems outside the scripted checks, unless an agent review ran (see "
    "agent_review). Reason: a fixed list of checks misses what it does not list. How to "
    "check it yourself: follow agent-review-audit/SKILL.md; every claim it admits was "
    "checked against the crawl and is capped at low severity.",
]


def build_report(b: dict, findings: list[Finding], skipped: list[dict],
                 review: dict | None = None) -> dict:
    """`findings` arrives ranked, with ids assigned in that order."""
    active = [f for f in findings if f.status == "active"]
    latent = [f for f in findings if f.status == "latent"]
    confirm = [f for f in findings if f.status == "confirm_intent"]
    proactive, in_place = proactive_for(b, findings)
    bands = ("critical", "high", "medium", "low", "info")
    counts = {s: sum(1 for f in findings if f.severity == s) for s in bands}
    active_counts = {s: sum(1 for f in active if f.severity == s) for s in bands}

    return {
        # ---- required by the specification ----
        "site": b["site"],
        "audited_at": b["audited_at"],
        "summary": {
            # total_findings == len(findings[]) and the severity counts add up
            # to it, so an external validator agrees with the array. The
            # active-only split follows, since latent and confirm-intent
            # findings are capped at low and not what to act on today.
            "total_findings": len(findings),
            **{k: v for k, v in counts.items() if k != "info"},
            # ---- superset ----
            "active_findings": len(active),
            "latent_findings": len(latent),
            "confirm_intent_findings": len(confirm),
            "info": counts["info"],
            "active_by_severity": {k: v for k, v in active_counts.items() if k != "info"},
            "by_hurts": {h: sum(1 for f in active if f.hurts == h)
                         for h in ("ai_discoverability", "user_retention", "both")},
            "run_status": b["run_status"],
            "headline": _headline(active, b, review),
        },
        "findings": [f.to_report() for f in findings],
        # ---- superset ----
        "site_profile": {
            "start_url": b["start_url"],
            "pages_crawled": b["coverage"]["pages_ok"],
            "roles_seen": sorted({p["role"] for p in b["pages"]}),
            "robots_present": b["robots"]["present"],
            "ai_policy": _ai_policy(b),
            "user_agent_used": b["user_agent"],
        },
        "coverage": b["coverage"],
        "checks_skipped": sorted(skipped, key=lambda s: s["check"]),
        "agent_review": review or {"status": "not_run"},
        "prioritized_actions": [
            {"rank": i + 1, "finding_id": f.id, "title": f.title,
             "priority_score": priority_score(f),
             "severity": f.severity, "status": f.status, "hurts": f.hurts,
             "effort": f.suggested_action.get("effort", "medium"),
             "action": f.suggested_action["summary"]}
            for i, f in enumerate(findings[:15])
        ],
        "proactive_recommendations": proactive,
        "already_in_place": in_place,
        "limits": list(LIMITS),
        "notes": b.get("notes", []),
    }


def _ai_policy(b: dict) -> dict:
    agents = b["robots"]["agents"]
    return {
        "retrieval_agents_blocked": sorted(t for t, d in agents.items()
                                           if d["class"] == "retrieval" and d["fully_blocked"]),
        "training_agents_blocked": sorted(t for t, d in agents.items()
                                          if d["class"] == "training" and d["fully_blocked"]),
        "interpretation": "Blocking training agents is a licensing choice and does not affect "
                          "whether assistants can cite you. Only retrieval agents gate citation.",
    }


def _headline(active: list[Finding], b: dict, review: dict | None = None) -> str:
    if any(x.get("reason") == "auditor_side_failure" for x in (review or {}).get("adjudicated_out", [])):
        return ("The audit could not reach the site from this network, so nothing about the site "
                "was measured - re-run from another network.")
    if b["run_status"] in ("blocked", "failed"):
        return "The site could not be read by an automated client - fix access before anything else."
    if not active:
        return "No blocking problems detected in the checks that ran; see proactive recommendations."
    worst = min(active, key=lambda f: -SEV_WEIGHT.get(f.severity, 0))
    return f"{len(active)} finding(s); most severe: {worst.title}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit a site for AI discoverability and engagement.")
    ap.add_argument("url", nargs="?", help="site URL to audit")
    ap.add_argument("--replay", metavar="BUNDLE", help="re-run analysis over a saved bundle")
    ap.add_argument("-o", "--out", help="write report JSON here (default: stdout)")
    ap.add_argument("--bundle", help="also save the fetched bundle here")
    ap.add_argument("--max-pages", type=int, default=bundle_mod.DEFAULT_MAX_PAGES)
    ap.add_argument("--crawl-budget-s", type=float, default=bundle_mod.DEFAULT_DEADLINE_S,
                    help="crawl deadline in seconds; use 100 when an agent review follows")
    ap.add_argument("--agent-claims", metavar="CLAIMS",
                    help="verify an agent review's claims (agent-review-audit) and merge those "
                         "that hold; use with --replay on the bundle the review read")
    args = ap.parse_args()
    t_start = time.monotonic()

    tmp = None
    if args.replay:
        b = json.loads(Path(args.replay).read_text(encoding="utf-8"))
        bundle_path = Path(args.replay)
    elif args.url:
        b = json.loads(bundle_mod.build(args.url, max_pages=args.max_pages, deadline_s=args.crawl_budget_s).to_json())
        if args.bundle:
            bundle_path = Path(args.bundle)
        else:
            # Sub-skills read the bundle from disk; keep it out of the marketplace.
            fd, name = tempfile.mkstemp(prefix="audit-bundle-", suffix=".json")
            os.close(fd)
            bundle_path = tmp = Path(name)
        bundle_path.write_text(json.dumps(b, indent=2, sort_keys=True, ensure_ascii=False),
                               encoding="utf-8")
    else:
        ap.error("provide a URL or --replay BUNDLE")
        return 2

    # Analysis shares whatever the crawl left of the total budget, so the whole
    # audit is bounded inside the 5-minute limit rather than per-stage.
    raw, skipped = [], []
    try:
        for folder, script in SUB_SKILLS:
            remaining = bundle_mod.TOTAL_BUDGET_S - (time.monotonic() - t_start)
            f, s = run_sub_skill(folder, script, bundle_path, min(30.0, remaining))
            raw += f
            skipped += s
        remaining = bundle_mod.TOTAL_BUDGET_S - (time.monotonic() - t_start)
        agent_raw, s, review, fixes = run_agent_review(
            bundle_path, Path(args.agent_claims) if args.agent_claims else None, raw,
            min(30.0, remaining))
        skipped += s
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)

    # With nothing readable the engagement skill has nothing to assess; say so
    # even if its script did not.
    if b["coverage"]["pages_ok"] == 0 and not any(s["check"].startswith("engagement")
                                                  for s in skipped):
        skipped.append({"check": "engagement-audit",
                        "reason": "no page returned readable HTML, so no engagement check ran",
                        "impact": "On-site engagement was not assessed at all. Fix the access "
                                  "problem reported by crawl-access-audit, then re-run."})

    raw += drop_duplicate_claims(raw, agent_raw, review)
    raw = mark_latent(raw, b)
    raw.sort(key=lambda f: (f["check_id"], sorted(f.get("affected_urls", []))[:1]))

    findings: list[Finding] = []
    for r in raw:
        findings.append(Finding(
            check_id=r["check_id"], title=r["title"], evidence=r["evidence"],
            suggested_action=r["suggested_action"],
            affected_urls=r.get("affected_urls", []),
            blast_radius=r.get("blast_radius", "single_page"),
            confidence=r.get("confidence", "deterministic"),
            measurement_basis=r.get("measurement_basis", "static_fact"),
            status=r.get("status", "active"),
            intent_signals=r.get("intent_signals", []),
            blocked_by=r.get("blocked_by"),
            detail=r.get("detail", {}),
        ).finalise(0, b["coverage"]["pages_ok"]))
    merge_fixes(findings, fixes, review)
    if args.agent_claims and review.get("status") == "run" and bundle_path.exists():
        remaining = bundle_mod.TOTAL_BUDGET_S - (time.monotonic() - t_start)
        findings = apply_verdicts(findings, bundle_path, Path(args.agent_claims), review,
                                  b["coverage"]["pages_ok"], min(30.0, remaining))

    # Ids follow the ranking, so the report reads F-001, F-002... top down.
    findings = rank(findings)
    for i, f in enumerate(findings, start=1):
        f.id = f"F-{i:03d}"

    report = build_report(b, findings, skipped, review)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}  ({report['summary']['active_findings']} active, "
              f"{report['summary']['latent_findings']} latent, "
              f"run_status={report['summary']['run_status']})")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
