#!/usr/bin/env python3
"""Verify agent-review claims against the crawl, deterministically.

    python3 verify_claims.py bundle.json claims.json

The reviewing agent may propose any finding; this script decides whether it is
true. Each claim carries evidence assertions ("this page's HTML contains X",
"this profile field equals Y", "this page's text lacks Z"). A claim becomes a
finding only if it is well-formed, names only crawled pages, and EVERY assertion
holds against the bundle. Nothing is taken on the agent's word: the reviewer's
explanation is carried into the report labelled as unverified, and the
orchestrator caps every claim at low severity.

Writes {"findings": [...], "fixes": [...], "checks_skipped": [], "review": {...}}
to stdout. Findings use the sub-skill raw format; the orchestrator assigns
severity. Format of a claim and of a fix: references/claim-format.md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent))
from page_profile import get_field, is_ok, profile_page  # noqa: E402  (same skill)

CHECK_ID = "R_agent_review"
MAX_CLAIMS = 6
MAX_FIXES = 5
MAX_ASSERTIONS = 8
MAX_STEPS = 8
MIN_CONTAINS_CHARS = 6      # shorter literals match almost any page
MIN_LACKS_CHARS = 3
MECHANISMS = {"A", "B", "C", "D", "E", "F", "on-site"}
HURTS = {"ai_discoverability", "user_retention", "both"}
SEVERITIES = ("high", "medium", "low")
EFFORTS = ("low", "medium", "high")
TEXT_TYPES = {"html_contains", "html_lacks", "text_contains", "text_lacks", "header_contains"}
FIELD_OPS = {"eq", "ne", "contains", "lacks", "gt", "lt", "empty", "nonempty"}
POSITIVE_FIELD_OPS = {"eq", "contains", "gt", "lt", "nonempty"}
# Fields that say WHICH page this is, not what is wrong with it. They may
# support a claim ("the pricing page ...") but never carry it on their own:
# "status eq 200" is true of every page the crawl kept.
IDENTITY_FIELDS = {"url", "final_url", "status", "role", "content_type", "redirect_hops"}
# Claim text reaches a human reader as-is, so it may not smuggle markup or
# point off the audited site.
_MARKUP = re.compile(r"<\s*/?\s*[a-zA-Z!?]|javascript\s*:", re.I)
_URL_HOST = re.compile(r"https?://([^\s/\"'<>]+)", re.I)


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
        if actual in (None, "") or expected in (None, ""):
            # null is null: it never normalises to the string "none".
            same = actual == expected
        else:
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


class Crawl:
    """The bundle, with page profiles and normalised text built on first use.

    A bundle can hold twenty pages of several hundred KB each; profiling them
    all up front costs seconds the review does not have. Only pages a claim
    actually names are ever profiled.
    """

    def __init__(self, bundle: dict):
        self.site = (bundle.get("site") or "").lower()
        self.pages = {p["url"]: p for p in bundle.get("pages", [])}
        self.ok_urls = {url for url, p in self.pages.items() if is_ok(p)}
        self._profiles: dict = {}
        self._html: dict = {}
        self._text: dict = {}

    def profile(self, url: str) -> dict:
        if url not in self._profiles:
            self._profiles[url] = profile_page(self.pages[url])
        return self._profiles[url]

    def html(self, url: str) -> str:
        if url not in self._html:
            self._html[url] = _norm(self.pages[url]["html"])
        return self._html[url]

    def text(self, url: str, scope: str) -> str:
        key = (url, scope)
        if key not in self._text:
            derived = (self.pages[url].get("derived") or {}).get("text") or {}
            self._text[key] = _norm(derived.get(scope, ""))
        return self._text[key]

    def header(self, url: str, name: str) -> str:
        return _norm((self.pages[url].get("headers") or {}).get(name, ""))

    def field_has(self, url: str, path: str, needle: str) -> bool:
        try:
            actual = get_field(self.profile(url), path)
        except KeyError:
            return False
        if isinstance(actual, list):
            return any(needle in _norm(item) for item in actual)
        return needle in _norm(actual)

    def everywhere(self, present) -> bool:
        """True when `present(url)` holds on every readable page.

        Evidence that is true of the whole crawl ("</html>", the site name)
        distinguishes nothing, so it cannot be positive evidence. With a single
        readable page there is nothing to distinguish it from, so the test is
        skipped rather than rejecting every claim.
        """
        return len(self.ok_urls) >= 2 and all(present(u) for u in sorted(self.ok_urls))


def check_assertion(a, crawl: Crawl) -> tuple[bool, str, bool]:
    """(holds, human-readable description, is_positive)."""
    if not isinstance(a, dict):
        raise Rejected("an evidence entry is not an object")
    url, kind = a.get("url"), a.get("type")
    page = crawl.pages.get(url) if isinstance(url, str) else None
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
            haystack, where = crawl.header(url, header), f"the {header} header"
            on_page = lambda u: needle in crawl.header(u, header)  # noqa: E731
        else:
            if not is_ok(page):
                raise Rejected(f"{url} returned no readable HTML, so its content cannot be evidence")
            if kind.startswith("html"):
                haystack, where = crawl.html(url), "the raw HTML"
                on_page = lambda u: needle in crawl.html(u)  # noqa: E731
            else:
                scope = a.get("scope", "extracted")
                if scope not in ("extracted", "full"):
                    raise Rejected("text 'scope' must be 'extracted' or 'full'")
                haystack, where = crawl.text(url, scope), f"the {scope} text"
                on_page = lambda u: needle in crawl.text(u, scope)  # noqa: E731
        found = needle in haystack
        holds = found if positive else not found
        if holds and positive and crawl.everywhere(on_page):
            raise Rejected(f"evidence is true of every page: {value!r}")
        verb = "contains" if positive else "does not contain"
        return holds, f"{url}: {where} {verb} {value!r}", positive

    if kind == "field":
        path, op = a.get("path"), a.get("op")
        if not isinstance(path, str) or op not in FIELD_OPS:
            raise Rejected(f"'field' needs a 'path' and an 'op' in {sorted(FIELD_OPS)}")
        try:
            actual = get_field(crawl.profile(url), path)
        except KeyError:
            raise Rejected(f"{url} has no profile field {path!r}")
        expected = a.get("value")
        holds = _field_holds(actual, op, expected)
        positive = (op in POSITIVE_FIELD_OPS
                    and path.split(".")[0] not in IDENTITY_FIELDS
                    and not (op == "eq" and expected in (None, "")))   # eq null is an absence
        if holds and positive and op == "contains" \
                and crawl.everywhere(lambda u: crawl.field_has(u, path, _norm(expected))):
            raise Rejected(f"evidence is true of every page: {path} contains {expected!r}")
        shown = json.dumps(actual, ensure_ascii=False)
        if len(shown) > 120:
            shown = shown[:117] + "..."
        target = "" if op in ("empty", "nonempty") else f" {json.dumps(expected, ensure_ascii=False)}"
        return holds, f"{url}: {path} {op}{target} (actual {shown})", positive

    raise Rejected(f"unknown evidence type {kind!r}")


def _same_site(host: str, site: str) -> bool:
    host = host.lower().split("@")[-1].split(":")[0]
    return bool(site) and (host == site or host.endswith("." + site) or site.endswith("." + host))


def _scrub(text: str, site: str) -> str:
    """Reject markup, javascript: and links off the audited site in reader-facing text."""
    if _MARKUP.search(text) or any(not _same_site(h, site) for h in _URL_HOST.findall(text)):
        raise Rejected("claim text contains markup or external links")
    return text


def _require_text(obj: dict, key: str, site: str, min_len: int = 1, max_len: int = 600) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not (min_len <= len(value.strip()) <= max_len):
        raise Rejected(f"'{key}' must be a string of {min_len}-{max_len} characters")
    return _scrub(" ".join(value.split()), site)


def _require_steps(obj: dict, key: str, site: str) -> list[str]:
    steps = obj.get(key)
    if not isinstance(steps, list) or not steps or len(steps) > MAX_STEPS \
            or not all(isinstance(s, str) and s.strip() for s in steps):
        raise Rejected(f"'{key}' must list 1-{MAX_STEPS} non-empty steps")
    return [_scrub(" ".join(s.split()), site) for s in steps]


def verify_claim(claim, crawl: Crawl) -> dict:
    if not isinstance(claim, dict):
        raise Rejected("claim is not an object")
    site = crawl.site
    title = _require_text(claim, "title", site, 8, 160)
    why = _require_text(claim, "why", site, 20, 600)
    for key, allowed in (("mechanism", MECHANISMS), ("hurts", HURTS), ("severity", SEVERITIES)):
        if claim.get(key) not in allowed:
            raise Rejected(f"'{key}' must be one of {sorted(allowed)}")
    nearest = claim.get("nearest_check")
    if nearest is not None and not isinstance(nearest, str):
        raise Rejected("'nearest_check' must be a check_id string or null")

    affected = claim.get("affected_urls")
    if not isinstance(affected, list) or not affected:
        raise Rejected("'affected_urls' must list at least one crawled page")
    stray = [u for u in affected if u not in crawl.ok_urls]
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
    summary = _require_text(action, "summary", site, 8, 200)
    verify = _require_text(action, "verify", site, 8, 300)
    how = _require_steps(action, "how", site)
    effort = action.get("effort", "medium")
    if effort not in EFFORTS:
        raise Rejected(f"'suggested_action.effort' must be one of {list(EFFORTS)}")

    results, positive_seen = [], False
    for a in evidence:
        holds, described, positive = check_assertion(a, crawl)
        if not holds:
            raise Rejected(f"evidence does not hold: {described}")
        positive_seen = positive_seen or positive
        results.append(described)
    if not positive_seen:
        # "The page lacks X" is true of every page that is not about X, and
        # "status eq 200" is true of every page that was crawled. A claim must
        # show, positively and specifically, what is wrong with the page.
        raise Rejected("every assertion is an absence or an identity field; add one that "
                       "shows what is wrong with the page")

    n, total = len(set(affected)), len(crawl.ok_urls)
    blast = "site_wide" if n == total and n >= 2 else ("template" if n > 1 else "single_page")
    return {
        "check_id": CHECK_ID,
        "title": title,
        # The reviewer's reasoning is opinion until a reader checks it; only the
        # assertions after the second label were tested against the bundle.
        "evidence": (f"Reviewer's explanation (not verified): {why} "
                     "Checked against the crawl: " + "; ".join(results) + "."),
        "affected_urls": sorted(set(affected)),
        "blast_radius": blast,
        "confidence": "heuristic",
        "measurement_basis": "static_heuristic",
        "suggested_action": {"summary": summary, "priority": "low", "effort": effort,
                             "how": how, "verify": verify},
        "detail": {"source": "agent_review", "mechanism": claim["mechanism"],
                   "hurts": claim["hurts"], "proposed_severity": claim["severity"],
                   "nearest_check": nearest, "verified_assertions": results},
    }


def verify_fix(fix, crawl: Crawl) -> dict:
    """A site-specific fix is admitted only when its quote really is on the page.

    Whether the page belongs to the named check's affected_urls is decided by
    the orchestrator, which holds the scripted findings.
    """
    if not isinstance(fix, dict):
        raise Rejected("fix is not an object")
    check_id = fix.get("check_id")
    if not isinstance(check_id, str) or not check_id.strip():
        raise Rejected("'check_id' must name the finding this fix belongs to")
    url = fix.get("url")
    if url not in crawl.ok_urls:
        raise Rejected(f"'url' must be a page that was crawled successfully, got {url!r}")
    quote = _require_text(fix, "quote", crawl.site, MIN_CONTAINS_CHARS, 300)
    needle = _norm(quote)
    if needle not in crawl.text(url, "extracted") and needle not in crawl.text(url, "full"):
        raise Rejected(f"quote is not on the page: {quote!r}")
    steps = _require_steps(fix, "site_specific", crawl.site)
    return {"check_id": check_id.strip(), "site_specific": steps,
            "grounded_on": {"url": url, "quote": quote}}


def run(bundle: dict, claims_doc) -> dict:
    claims = claims_doc.get("claims") if isinstance(claims_doc, dict) else claims_doc
    fixes = claims_doc.get("fixes", []) if isinstance(claims_doc, dict) else []
    review = {"claims_submitted": 0, "verified": 0, "rejected": [], "claim_limit": MAX_CLAIMS,
              "fixes_submitted": 0, "fixes_verified": 0, "rejected_fixes": []}
    if not isinstance(claims, list):
        review["error"] = "claims file must be a list of claims or {\"claims\": [...]}"
        return {"findings": [], "fixes": [], "checks_skipped": [], "review": review}
    if not isinstance(fixes, list):
        fixes = []
        review["rejected_fixes"].append({"check_id": None, "reason": "'fixes' must be a list"})

    crawl = Crawl(bundle)
    review["claims_submitted"] = len(claims)
    review["fixes_submitted"] = len(fixes)

    findings, seen = [], set()
    for i, claim in enumerate(claims):
        title = claim.get("title", "") if isinstance(claim, dict) else ""
        try:
            if i >= MAX_CLAIMS:
                raise Rejected(f"over the limit of {MAX_CLAIMS} claims per audit")
            finding = verify_claim(claim, crawl)
            key = (_norm(finding["title"]), tuple(finding["affected_urls"]))
            if key in seen:
                raise Rejected("repeats an earlier claim")
            seen.add(key)
            findings.append(finding)
        except Rejected as exc:
            review["rejected"].append({"index": i, "title": str(title)[:160], "reason": str(exc)})
        except Exception as exc:  # a malformed claim fails alone, never the review
            review["rejected"].append({"index": i, "title": str(title)[:160],
                                       "reason": f"malformed claim: {type(exc).__name__}: {exc}"[:200]})
    review["verified"] = len(findings)

    verified_fixes = []
    for i, fix in enumerate(fixes):
        check_id = fix.get("check_id") if isinstance(fix, dict) else None
        try:
            if i >= MAX_FIXES:
                raise Rejected(f"over the limit of {MAX_FIXES} fixes per audit")
            verified_fixes.append(verify_fix(fix, crawl))
        except Rejected as exc:
            review["rejected_fixes"].append({"index": i, "check_id": str(check_id)[:60],
                                             "reason": str(exc)})
        except Exception as exc:
            review["rejected_fixes"].append({"index": i, "check_id": str(check_id)[:60],
                                             "reason": f"malformed fix: {type(exc).__name__}: {exc}"[:200]})
    review["fixes_verified"] = len(verified_fixes)
    return {"findings": findings, "fixes": verified_fixes, "checks_skipped": [], "review": review}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: verify_claims.py bundle.json claims.json", file=sys.stderr)
        raise SystemExit(2)
    bundle_doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        claims_input = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"findings": [], "fixes": [], "checks_skipped": [],
                          "review": {"claims_submitted": 0, "verified": 0, "rejected": [],
                                     "claim_limit": MAX_CLAIMS, "fixes_submitted": 0,
                                     "fixes_verified": 0, "rejected_fixes": [],
                                     "error": f"claims file unreadable: {type(exc).__name__}"}}))
        raise SystemExit(0)
    print(json.dumps(run(bundle_doc, claims_input), indent=2, ensure_ascii=False))
