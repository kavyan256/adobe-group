#!/usr/bin/env python3
"""Verify the agent's verdicts on scripted findings.

    python3 verify_verdicts.py bundle.json findings.json claims.json

`findings.json` is the list of finalised findings the orchestrator is about to rank.
A verdict is accepted only when every evidence assertion holds against the crawl and
the evidence meets its reason's rule (references/adjudication.md). The output lists
each accepted verdict with its `finding_index` and `effect`; audit.py applies the
effect and re-derives severity, so the verifier never edits a report itself.
"""
from __future__ import annotations

import json
import re
import sys
from urllib.parse import urlparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from page_profile import is_ok  # noqa: E402
from verify_claims import (FIELD_OPS, Crawl, Rejected, _field_holds, _norm,  # noqa: E402
                           _require_text, check_assertion)

MAX_EVIDENCE = 12
MAX_VERDICTS = 5
REASONS = {
    "measurement_confirmed": "confirm",
    "overstated_impact": "downgrade",
    "access_block_unattributed": "downgrade",
    "access_block_not_bot_specific": "confirm_intent",
    "deliberate_configuration": "confirm_intent",
    "error_or_placeholder_page": "not_a_defect",
    "page_purpose_mismatch": "not_a_defect",
    "measurement_wrong": "not_a_defect",
    "auditor_side_failure": "not_a_defect",
    "duplicate_of_finding": "not_a_defect",
}
# Reasons that only make sense for some checks: a setting can be deliberate only where
# the check reads an indexing or access directive, and a refusal is only an access finding.
REASON_SCOPE = {
    "deliberate_configuration": ("A2_", "A3_", "A5_"),
    "access_block_unattributed": ("A7_",),
    "access_block_not_bot_specific": ("A7_",),
    "auditor_side_failure": ("A7_",),
}
URL_SCOPED = {"error_or_placeholder_page", "page_purpose_mismatch", "measurement_wrong"}
# What a page IS shows on the page itself; a wrong measurement may be proved elsewhere
# (the homepage link the crawler mangled), but every cleared page must still be named.
ON_PAGE_PROOF = {"error_or_placeholder_page", "page_purpose_mismatch"}
SITE_FIELDS = {"run_status", "coverage.pages_ok", "coverage.pages_fetched", "robots.status"}
TRANSPORT_ERRORS = ("connecterror", "connecttimeout", "readtimeout", "ssl", "timed out",
                    "name or service not known", "remoteprotocolerror")
PAGE_TEXT_TYPES = {"html_contains", "html_lacks", "text_contains", "text_lacks"}


def _dig(obj, path: str):
    for part in path.split("."):
        obj = (obj or {}).get(part) if isinstance(obj, dict) else None
    return obj


def site_assertion(a: dict, bundle: dict, report: dict, target: dict):
    kind = a["type"]
    if kind == "site_note_contains":
        value = a.get("value")
        if not isinstance(value, str) or len(value.strip()) < 4:
            raise Rejected("'site_note_contains' needs a 'value' of 4 or more characters")
        notes = _norm(" | ".join(bundle.get("notes") or []))
        return _norm(value) in notes, f"the crawl notes contain {value!r}", True
    if kind == "site_field":
        path, op = a.get("path"), a.get("op")
        if path not in SITE_FIELDS:
            raise Rejected(f"'site_field' path must be one of {sorted(SITE_FIELDS)}")
        if op not in FIELD_OPS:
            raise Rejected(f"'site_field' op must be one of {sorted(FIELD_OPS)}")
        actual, expected = _dig(bundle, path), a.get("value")
        positive = op in ("eq", "contains") and expected not in (None, "")
        return (_field_holds(actual, op, expected),
                f"crawl {path} {op} {expected!r} (actual {json.dumps(actual)[:80]})", positive)
    cid, url = a.get("check_id"), a.get("url")
    other = [f for f in report["findings"] if f is not target and f.get("check_id") == cid
             and url in (f.get("affected_urls") or [])]
    holds = bool(other) and cid != target.get("check_id")
    return holds, f"the report also has {cid} on {url}", True


def page_assertion(a: dict, crawl: Crawl):
    url, kind = a.get("url"), a.get("type")
    page = crawl.pages.get(url) if isinstance(url, str) else None
    if page is None:
        raise Rejected(f"evidence names a URL that was not crawled: {url!r}")
    if kind in PAGE_TEXT_TYPES and not is_ok(page):
        body = page.get("html") or ""
        if not body:
            raise Rejected(f"{url} kept no response body, so its content cannot be evidence")
        value = a.get("value")
        if not isinstance(value, str) or len(_norm(value)) < 4:
            raise Rejected(f"'{kind}' needs a 'value' of 4 or more characters")
        positive = kind.endswith("contains")
        found = _norm(value) in _norm(body)
        verb = "contains" if positive else "does not contain"
        return (found if positive else not found,
                f"{url} (HTTP {page.get('status')}): the response body {verb} {value!r}", positive)
    return check_assertion(a, crawl)


def _names_target(a: dict, urls: list, target: dict) -> bool:
    """Does this assertion's value name a cleared page's path or a value the finding quoted?"""
    value = _norm(str(a.get("value") or ""))
    if len(value) < 6:
        return False
    paths = [_norm(urlparse(u).path.rstrip("/")) for u in urls]
    quoted = [_norm(q) for q in re.findall(r"'([^']{6,})'", target.get("evidence") or "")]
    return any(p and len(p) > 1 and p in value for p in paths) or any(q in value for q in quoted)


def resolve(v: dict, report: dict) -> dict:
    ref = v.get("finding")
    if not isinstance(ref, dict) or not isinstance(ref.get("check_id"), str):
        raise Rejected("'finding' must name a scripted finding's check_id")
    cid, url = ref["check_id"], ref.get("url")
    pool = [f for f in report["findings"] if f.get("check_id") == cid
            and f.get("source") != "agent_review"
            and (f.get("detail") or {}).get("source") != "agent_review"]
    if url is not None:
        pool = [f for f in pool if url in (f.get("affected_urls") or [])]
    if len(pool) != 1:
        raise Rejected(f"'finding' matches {len(pool)} scripted findings; give a 'url' that one of them lists")
    return pool[0]


def verify_verdict(v, crawl: Crawl, bundle: dict, report: dict, used: set):
    if not isinstance(v, dict):
        raise Rejected("verdict is not an object")
    target = resolve(v, report)
    if id(target) in used:
        raise Rejected("that finding already has a verdict")
    reason, verdict = v.get("reason"), v.get("verdict")
    if reason not in REASONS:
        raise Rejected(f"'reason' must be one of {sorted(REASONS)}")
    if REASONS[reason] != verdict:
        raise Rejected(f"reason {reason!r} goes with verdict {REASONS[reason]!r}")
    scope = REASON_SCOPE.get(reason)
    if scope and not target["check_id"].startswith(scope):
        raise Rejected(f"reason {reason!r} applies only to {', '.join(p.rstrip('_') for p in scope)} findings")
    explanation = _require_text(v, "explanation", crawl.site, 20, 600)
    affected = list(target.get("affected_urls") or [])
    urls = v.get("urls") or affected
    if not isinstance(urls, list) or not set(urls) <= set(affected):
        raise Rejected("'urls' must be affected URLs of that finding")
    if target["severity"] == "critical" and reason == "overstated_impact":
        raise Rejected("a critical finding is not downgraded for scope")

    evidence = v.get("evidence")
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= MAX_EVIDENCE:
        raise Rejected(f"'evidence' must hold 1-{MAX_EVIDENCE} assertions")
    results, positive_urls, named_urls, site_positive = [], set(), set(), False
    for a in evidence:
        if not isinstance(a, dict):
            raise Rejected("an evidence entry is not an object")
        if a.get("type") in ("site_note_contains", "site_field", "finding_exists"):
            holds, described, positive = site_assertion(a, bundle, report, target)
            site_positive = site_positive or (holds and positive)
        else:
            try:
                holds, described, positive = page_assertion(a, crawl)
            except Rejected as exc:
                # A site-wide defect is true of every page; confirming it is fine. A wrong
                # measurement may also be proved by site-wide markup (a menu link), but only
                # by a value that names a cleared page or the value the finding quoted.
                if not str(exc).startswith("evidence is true of every page"):
                    raise
                if not (verdict == "confirm" or (reason == "measurement_wrong" and _names_target(a, urls, target))):
                    raise
                holds, described, positive = True, f"{a.get('url')}: holds on every crawled page ({a.get('value') or a.get('path')!r})", True
            if holds:
                named_urls.add(a.get("url"))
            if holds and positive:
                positive_urls.add(a.get("url"))
        if not holds:
            raise Rejected(f"evidence does not hold: {described}")
        results.append(described)

    if reason in ON_PAGE_PROOF:
        missing = [u for u in urls if u not in positive_urls]
        if missing:
            raise Rejected(f"every page a verdict clears needs its own positive evidence; none for {missing[:3]}")
    elif reason == "measurement_wrong":
        missing = [u for u in urls if u not in named_urls]
        if missing or not positive_urls:
            raise Rejected(f"name every cleared page and give one positive assertion; not named: {missing[:3]}")
    elif reason == "auditor_side_failure":
        notes = [_norm(a.get("value", "")) for a in evidence if a.get("type") == "site_note_contains"]
        if not any(any(t in n for t in TRANSPORT_ERRORS) for n in notes):
            raise Rejected("an auditor-side failure needs a crawl note naming the transport error")
        if ((bundle.get("coverage") or {}).get("pages_ok") or 0) > 0:
            raise Rejected("pages were read, so the audit did not fail as a whole")
    elif reason == "duplicate_of_finding":
        if not any(a.get("type") == "finding_exists" for a in evidence):
            raise Rejected("a duplicate needs 'finding_exists' naming the other finding")
    elif not (positive_urls or site_positive):
        raise Rejected("add one positive assertion that shows why")
    used.add(id(target))
    return target, {"check_id": target["check_id"], "verdict": verdict, "reason": reason,
                    "urls": sorted(urls), "explanation": explanation, "verified_evidence": results}


def verify_all(bundle: dict, findings: list[dict], doc) -> dict:
    verdicts = doc.get("verdicts") if isinstance(doc, dict) else None
    verdicts = verdicts if isinstance(verdicts, list) else []
    crawl, used, accepted, rejected = Crawl(bundle), set(), [], []
    report = {"findings": findings}
    for i, v in enumerate(verdicts):
        try:
            if i >= MAX_VERDICTS:
                raise Rejected(f"over the limit of {MAX_VERDICTS} verdicts per audit")
            target, rec = verify_verdict(v, crawl, bundle, report, used)
        except Rejected as exc:
            rejected.append({"index": i, "finding": v.get("finding") if isinstance(v, dict) else None,
                             "reason": str(exc)})
            continue
        except Exception as exc:  # a malformed verdict rejects that verdict only
            rejected.append({"index": i, "reason": f"malformed verdict: {type(exc).__name__}: {exc}"})
            continue
        left = set(target.get("affected_urls") or []) - set(rec["urls"])
        rec["effect"] = (rec["verdict"] if rec["verdict"] != "not_a_defect"
                         else "clear_urls" if rec["reason"] in URL_SCOPED and left else "remove")
        rec["finding_index"] = next(n for n, f in enumerate(findings) if f is target)
        accepted.append(rec)
    return {"submitted": len(verdicts), "accepted": accepted, "rejected": rejected,
            "verdict_limit": MAX_VERDICTS}


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: verify_verdicts.py bundle.json findings.json claims.json", file=sys.stderr)
        return 2
    bundle, findings, doc = (json.loads(Path(p).read_text(encoding="utf-8")) for p in sys.argv[1:4])
    print(json.dumps(verify_all(bundle, findings, doc), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
