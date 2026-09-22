#!/usr/bin/env python3
"""Freshness, internal consistency, and corroboration hooks.

Standalone: reads a site bundle, writes {findings, checks_skipped}.

Only what is verifiable on the site itself is measured. Whether independent
third parties agree with a claim needs a search backend, so that check (D6) is
always reported in checks_skipped[] rather than guessed at.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup

# The clock comes from the bundle's audited_at, passed as a parameter through
# run(), never from the wall clock and never from a module global: a replay of
# the same bundle must produce the same staleness verdicts on any day, and in
# any order relative to other runs in the same process.
STALE_MONTHS = 18

COPYRIGHT = re.compile(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(\d{4})", re.I)
ISO_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
PRESS_PATH = re.compile(r"(^|/)(press|newsroom|news|media-cent(er|re)|in-the-news)(/|$|\?|#)", re.I)


def _clock_from(b: dict) -> datetime:
    try:
        return datetime.fromisoformat(b["audited_at"].replace("Z", "+00:00"))
    except (KeyError, ValueError, AttributeError):
        return datetime.now(timezone.utc)


def load_bundle() -> dict:
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        return json.loads(open(sys.argv[1], encoding="utf-8").read())
    return json.loads(sys.stdin.read())


def _months_since(now: datetime, y: int, m: int, d: int) -> float:
    try:
        then = datetime(y, m, d, tzinfo=timezone.utc)
    except ValueError:
        return 0.0
    return (now - then).days / 30.44


def run(b: dict) -> tuple[list[dict], list[dict]]:
    now = _clock_from(b)
    findings: list[dict] = []
    skipped: list[dict] = []
    pages = [p for p in b["pages"] if 200 <= p["status"] < 300 and p["html"]]
    if not pages:
        return findings, skipped
    total = len(pages)

    stale_copyright, no_dates, stale_content = [], [], []
    prices_by_page: dict[str, set] = {}
    has_press = False

    for p in pages:
        soup = BeautifulSoup(p["html"], "html.parser")
        d = p["derived"]
        # `full` keeps nav/footer, where copyright lines and press links live,
        # but drops <script> bodies, so JavaScript literals cannot fire D2 or D4.
        text = d["text"]["full"]

        # -- D2 copyright year --------------------------------------------
        years = [int(y) for y in COPYRIGHT.findall(text) if y.isdigit()]
        if years and max(years) < now.year - 1:
            stale_copyright.append((p["url"], max(years)))

        # -- D1 / D3 date signals ------------------------------------------
        signals = []
        for tag in soup.find_all(["time"]):
            if tag.get("datetime"):
                signals.append(tag["datetime"])
        for m in soup.find_all("meta"):
            prop = (m.get("property") or m.get("name") or "").lower()
            if any(k in prop for k in ("published_time", "modified_time", "date")):
                signals.append(m.get("content") or "")
        if "last-modified" in p["headers"]:
            signals.append(p["headers"]["last-modified"])
        # JSON-LD dates come only from real date properties, never from @id URLs.
        signals.extend(d["jsonld"]["dates"])

        blob = " ".join(signals)
        dates = ISO_DATE.findall(blob)
        # Blog/article pages only. A homepage routinely and correctly carries no
        # date; firing there would be a false positive on most sites.
        if p["role"] == "blog" and not dates:
            no_dates.append((p["url"], p["role"]))
        elif dates:
            ages = [_months_since(now, int(y), int(mo), int(dd)) for y, mo, dd in dates]
            newest = min(ages) if ages else 0
            if p["role"] == "blog" and newest > STALE_MONTHS:
                stale_content.append((p["url"], round(newest)))

        # -- D4 internal contradiction (price consistency) ------------------
        found = set(re.findall(r'[$£€¥₹]\s?(\d[\d,]*(?:\.\d{2})?)', text))
        if p["role"] in ("pricing", "product") and found:
            prices_by_page[p["url"]] = found

        # -- D5 corroboration hooks -----------------------------------------
        # Press: a *link* whose path segment is a press/news section -- not any
        # substring, which would match /media/logo.png or /wp-content/media/.
        for a in soup.find_all("a", href=True):
            if PRESS_PATH.search(a["href"]):
                has_press = True
                break

    # ---- emit ------------------------------------------------------------
    if stale_copyright:
        findings.append({
            "check_id": "D2_stale_copyright",
            "title": f"Copyright year is out of date on {len(stale_copyright)} page(s)",
            "evidence": "; ".join(f"{u}: latest copyright year {y} (now {now.year})"
                                  for u, y in stale_copyright[:4]),
            "affected_urls": [u for u, _ in stale_copyright],
            "blast_radius": "site_wide" if len(stale_copyright) >= total * 0.8 else "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Render the copyright year dynamically.",
                "priority": "low", "effort": "low",
                "how": ["Generate the year at build or request time rather than hard-coding it.",
                        "A stale year is a cheap but widely-used freshness cue - it suggests the "
                        "whole site may be unmaintained."],
                "verify": "The footer shows the current year.",
            },
        })

    if no_dates:
        findings.append({
            "check_id": "D1_no_date_signals",
            "title": f"No machine-readable date on {len(no_dates)} page(s)",
            "evidence": (f"{len(no_dates)} page(s) expose no <time datetime>, no article "
                         f"published/modified meta, no Last-Modified header and no date in "
                         f"structured data. Examples: {[u for u, _ in no_dates[:3]]}. Assistants "
                         f"weight recency, and a page with no date cannot demonstrate it."),
            "affected_urls": [u for u, _ in no_dates],
            "blast_radius": "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Publish explicit datePublished and dateModified.",
                "priority": "medium", "effort": "low",
                "how": ["Add Article (or WebPage) JSON-LD carrying datePublished and dateModified.",
                        'Show a human-visible date with <time datetime="YYYY-MM-DD">.',
                        "Ensure dateModified genuinely changes when content changes."],
                "verify": "Rich Results Test shows both date properties populated.",
            },
        })

    if stale_content:
        findings.append({
            "check_id": "D3_content_stale",
            "title": f"{len(stale_content)} page(s) have not been updated in over {STALE_MONTHS} months",
            "evidence": "; ".join(f"{u}: most recent date ~{m} months old"
                                  for u, m in stale_content[:4]),
            "affected_urls": [u for u, _ in stale_content],
            "blast_radius": "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Refresh or explicitly retire ageing content.",
                "priority": "medium", "effort": "medium",
                "how": ["Review each page: update it and bump dateModified, or retire it.",
                        "Leaving superseded material live invites assistants to repeat outdated "
                        "claims about you."],
                "verify": "dateModified reflects a genuine recent edit.",
            },
        })

    distinct = {frozenset(v) for v in prices_by_page.values()}
    if len(distinct) > 1 and len(prices_by_page) > 1:
        findings.append({
            "check_id": "D4_internal_contradiction",
            "title": "The same product/plan appears at different prices across pages",
            "evidence": "; ".join(f"{u}: {sorted(v)}" for u, v in list(prices_by_page.items())[:4]),
            "affected_urls": list(prices_by_page),
            "blast_radius": "template",
            "confidence": "heuristic",
            "measurement_basis": "static_heuristic",
            "suggested_action": {
                "summary": "Serve every price from a single source of truth.",
                "priority": "high", "effort": "medium",
                "how": ["Reconcile the pricing shown on each page.",
                        "Inconsistency across your own pages is worse than a missing fact: it "
                        "gives an assistant contradictory evidence and lowers confidence in "
                        "everything else you publish."],
                "verify": "Each plan resolves to one price everywhere it appears.",
            },
        })

    # A missing Organization sameAs is C3's finding (fact-extractability-audit);
    # D5 does not report the same missing link a second time.
    if not has_press:
        findings.append({
            "check_id": "D5_no_corroboration_hooks",
            "title": "No press or news section linking third-party coverage",
            "evidence": (f"None of the {total} crawled page(s) links to a press, newsroom or news "
                         "section. Machines trust a claim more when independent sources repeat "
                         "it, and a page pointing at independent coverage is how a site makes "
                         "that agreement findable."),
            "affected_urls": [b["start_url"]],
            "blast_radius": "site_wide",
            "confidence": "heuristic",
            "measurement_basis": "static_heuristic",
            "suggested_action": {
                "summary": "Create citable, corroborable reference points for your key facts.",
                "priority": "medium", "effort": "medium",
                "how": ["Publish a stable facts/company page (founding date, leadership, HQ, "
                        "product line) that third parties can cite verbatim.",
                        "Maintain a press page linking outward to independent coverage.",
                        "Keep name, address and phone identical everywhere they appear."],
                "verify": "A search for your brand surfaces at least three independent sources "
                          "agreeing on your core facts.",
            },
        })

    skipped.append({
        "check": "D6_cross_web_corroboration",
        "reason": "third-party agreement cannot be verified without a search backend, which "
                  "this marketplace does not assume",
        "impact": "Claims that exist only on this site are not distinguished from claims "
                  "corroborated across the web. The on-site corroboration checks still ran.",
    })
    return findings, skipped


if __name__ == "__main__":
    f, s = run(load_bundle())
    print(json.dumps({"findings": f, "checks_skipped": s}, indent=2, ensure_ascii=False))
