#!/usr/bin/env python3
"""Verify agent-review claims against the crawl, deterministically.

    python3 verify_claims.py bundle.json claims.json

The reviewing agent may propose any finding; this script decides whether it is
true. Each claim carries evidence assertions ("this page's HTML contains X",
"this profile field equals Y", "this page's text lacks Z"). A claim becomes a
finding only if it is well-formed, names only crawled pages, and EVERY assertion
holds against the bundle. Nothing is taken on the agent's word.

Writes {"findings": [...], "checks_skipped": [], "review": {...}} to stdout.
Findings use the sub-skill raw format; the orchestrator assigns severity.
Format of a claim: references/claim-format.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent))
from page_profile import get_field, is_ok, profile_page  # noqa: E402  (same skill)

CHECK_ID = "R_agent_review"
MAX_CLAIMS = 12
MAX_ASSERTIONS = 8
MIN_CONTAINS_CHARS = 6      # shorter literals match almost any page
MIN_LACKS_CHARS = 3
MECHANISMS = {"A", "B", "C", "D", "E", "F", "on-site"}
HURTS = {"ai_discoverability", "user_retention", "both"}
SEVERITIES = ("high", "medium", "low")
EFFORTS = ("low", "medium", "high")
TEXT_TYPES = {"html_contains", "html_lacks", "text_contains", "text_lacks", "header_contains"}
FIELD_OPS = {"eq", "ne", "contains", "lacks", "gt", "lt", "empty", "nonempty"}
POSITIVE_FIELD_OPS = {"eq", "contains", "gt", "lt", "nonempty"}


class Rejected(Exception):
    pass


def _norm(value) -> str:
    return " ".join(str(value).split()).lower()


def _is_empty(value) -> bool:
    return value in (None, "", 0) or (isinstance(value, (list, dict)) and not value)


def _field_holds(actual, op: str, expected) -> bool:
    if op in ("empty", "nonempty"):
        return _is_empty(actual) == (op == "empty")
    if op in ("gt", "lt"):
        try:
            a, e = float(actual), float(expected)
        except (TypeError, ValueError):
            raise Rejected(f"'{op}' needs numbers, got {actual!r} and {expected!r}")
        return a > e if op == "gt" else a < e
    if op in ("eq", "ne"):
        same = (actual == expected) or (_norm(actual) == _norm(expected)
                                        and not isinstance(actual, (list, dict)))
        return same if op == "eq" else not same
    # contains / lacks
    if expected in (None, ""):
        raise Rejected(f"'{op}' needs a non-empty value")
    needle = _norm(expected)
    if isinstance(actual, list):
        present = any(needle in _norm(item) for item in actual)
    else:
        present = needle in _norm(actual)
    return present if op == "contains" else not present


def check_assertion(a, pages: dict, profiles: dict) -> tuple[bool, str, bool]:
    """(holds, human-readable description, is_positive)."""
    if not isinstance(a, dict):
        raise Rejected("an evidence entry is not an object")
    url, kind = a.get("url"), a.get("type")
    page = pages.get(url)
    if page is None:
        raise Rejected(f"evidence names a URL that was not crawled: {url!r}")

    if kind in TEXT_TYPES:
        value = a.get("value")
        if not isinstance(value, str):
            raise Rejected(f"'{kind}' needs a string 'value'")
        positive = kind.endswith("contains")
        needle = _norm(value)
        if len(needle) < (MIN_CONTAINS_CHARS if positive else MIN_LACKS_CHARS):
            raise Rejected(f"'{kind}' value is too short to be evidence: {value!r}")
        if kind == "header_contains":
            header = str(a.get("header", "")).lower()
            if not header:
                raise Rejected("'header_contains' needs a 'header' name")
            haystack = _norm((page.get("headers") or {}).get(header, ""))
            where = f"the {header} header"
        else:
            if not is_ok(page):
                raise Rejected(f"{url} returned no readable HTML, so its content cannot be evidence")
            if kind.startswith("html"):
                haystack, where = _norm(page["html"]), "the raw HTML"
            else:
                scope = a.get("scope", "extracted")
                if scope not in ("extracted", "full"):
                    raise Rejected("text 'scope' must be 'extracted' or 'full'")
                text = ((page.get("derived") or {}).get("text") or {}).get(scope, "")
                haystack, where = _norm(text), f"the {scope} text"
        found = needle in haystack
        holds = found if positive else not found
        verb = "contains" if positive else "does not contain"
        return holds, f"{url}: {where} {verb} {value!r}", positive

    if kind == "field":
        path, op = a.get("path"), a.get("op")
        if not isinstance(path, str) or op not in FIELD_OPS:
            raise Rejected(f"'field' needs a 'path' and an 'op' in {sorted(FIELD_OPS)}")
        try:
            actual = get_field(profiles[url], path)
        except KeyError:
            raise Rejected(f"{url} has no profile field {path!r}")
        expected = a.get("value")
        holds = _field_holds(actual, op, expected)
        shown = json.dumps(actual, ensure_ascii=False)
        if len(shown) > 120:
            shown = shown[:117] + "..."
        target = "" if op in ("empty", "nonempty") else f" {json.dumps(expected, ensure_ascii=False)}"
        return holds, f"{url}: {path} {op}{target} (actual {shown})", op in POSITIVE_FIELD_OPS

    raise Rejected(f"unknown evidence type {kind!r}")


def _require_text(claim: dict, key: str, min_len: int = 1, max_len: int = 600) -> str:
    value = claim.get(key)
    if not isinstance(value, str) or not (min_len <= len(value.strip()) <= max_len):
        raise Rejected(f"'{key}' must be a string of {min_len}-{max_len} characters")
    return " ".join(value.split())


def verify_claim(claim, pages: dict, profiles: dict, ok_urls: set) -> dict:
    if not isinstance(claim, dict):
        raise Rejected("claim is not an object")
    title = _require_text(claim, "title", 8, 160)
    why = _require_text(claim, "why", 20, 600)
    for key, allowed in (("mechanism", MECHANISMS), ("hurts", HURTS), ("severity", SEVERITIES)):
        if claim.get(key) not in allowed:
            raise Rejected(f"'{key}' must be one of {sorted(allowed)}")
    nearest = claim.get("nearest_check")
    if nearest is not None and not isinstance(nearest, str):
        raise Rejected("'nearest_check' must be a check_id string or null")

    affected = claim.get("affected_urls")
    if not isinstance(affected, list) or not affected:
        raise Rejected("'affected_urls' must list at least one crawled page")
    stray = [u for u in affected if u not in ok_urls]
    if stray:
        raise Rejected(f"affected_urls include pages that were not crawled successfully: {stray[:3]}")

    evidence = claim.get("evidence")
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= MAX_ASSERTIONS:
        raise Rejected(f"'evidence' must hold 1-{MAX_ASSERTIONS} assertions")
    uncovered = sorted(set(affected) - {a.get("url") for a in evidence if isinstance(a, dict)})
    if uncovered:
        raise Rejected(f"no evidence is given for affected URL(s) {uncovered[:3]}")

    action = claim.get("suggested_action")
    if not isinstance(action, dict):
        raise Rejected("'suggested_action' must be an object")
    summary = _require_text(action, "summary", 8, 200)
    verify = _require_text(action, "verify", 8, 300)
    how = action.get("how")
    if not isinstance(how, list) or not how or not all(isinstance(h, str) and h.strip() for h in how):
        raise Rejected("'suggested_action.how' must list at least one step")
    effort = action.get("effort", "medium")
    if effort not in EFFORTS:
        raise Rejected(f"'suggested_action.effort' must be one of {list(EFFORTS)}")

    results, positive_seen = [], False
    for a in evidence:
        holds, described, positive = check_assertion(a, pages, profiles)
        if not holds:
            raise Rejected(f"evidence does not hold: {described}")
        positive_seen = positive_seen or positive
        results.append(described)
    if not positive_seen:
        # "The page lacks X" is true of every page that is not about X. An absence
        # claim must also show, positively, what the page is.
        raise Rejected("every assertion is an absence; add one that shows what the page is")

    n, total = len(set(affected)), len(ok_urls)
    blast = "site_wide" if n == total and n >= 2 else ("template" if n > 1 else "single_page")
    return {
        "check_id": CHECK_ID,
        "title": title,
        "evidence": f"{why} Verified against the crawl: " + "; ".join(results) + ".",
        "affected_urls": sorted(set(affected)),
        "blast_radius": blast,
        "confidence": "heuristic",
        "measurement_basis": "static_heuristic",
        "suggested_action": {"summary": summary, "priority": claim["severity"], "effort": effort,
                             "how": [" ".join(h.split()) for h in how], "verify": verify},
        "detail": {"source": "agent_review", "mechanism": claim["mechanism"],
                   "hurts": claim["hurts"], "proposed_severity": claim["severity"],
                   "nearest_check": nearest, "verified_assertions": results},
    }


def run(bundle: dict, claims_doc) -> dict:
    claims = claims_doc.get("claims") if isinstance(claims_doc, dict) else claims_doc
    review = {"claims_submitted": 0, "verified": 0, "rejected": [], "claim_limit": MAX_CLAIMS}
    if not isinstance(claims, list):
        review["error"] = "claims file must be a list of claims or {\"claims\": [...]}"
        return {"findings": [], "checks_skipped": [], "review": review}

    pages = {p["url"]: p for p in bundle.get("pages", [])}
    profiles = {url: profile_page(p) for url, p in pages.items()}
    ok_urls = {url for url, p in pages.items() if is_ok(p)}
    review["claims_submitted"] = len(claims)

    findings, seen = [], set()
    for i, claim in enumerate(claims):
        title = claim.get("title", "") if isinstance(claim, dict) else ""
        try:
            if i >= MAX_CLAIMS:
                raise Rejected(f"over the limit of {MAX_CLAIMS} claims per audit")
            finding = verify_claim(claim, pages, profiles, ok_urls)
            key = (_norm(finding["title"]), tuple(finding["affected_urls"]))
            if key in seen:
                raise Rejected("repeats an earlier claim")
            seen.add(key)
            findings.append(finding)
        except Rejected as exc:
            review["rejected"].append({"index": i, "title": str(title)[:160], "reason": str(exc)})
    review["verified"] = len(findings)
    return {"findings": findings, "checks_skipped": [], "review": review}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: verify_claims.py bundle.json claims.json", file=sys.stderr)
        raise SystemExit(2)
    bundle_doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        claims_input = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        claims_input = None
        print(json.dumps({"findings": [], "checks_skipped": [],
                          "review": {"claims_submitted": 0, "verified": 0, "rejected": [],
                                     "claim_limit": MAX_CLAIMS,
                                     "error": f"claims file unreadable: {type(exc).__name__}"}}))
        raise SystemExit(0)
    print(json.dumps(run(bundle_doc, claims_input), indent=2, ensure_ascii=False))
