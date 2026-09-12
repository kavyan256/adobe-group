#!/usr/bin/env python3
"""Freshness and internal consistency.

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
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup

# The clock comes from the bundle's audited_at, passed as a parameter through
# run(), never from the wall clock and never from a module global: a replay of
# the same bundle must produce the same staleness verdicts on any day, and in
# any order relative to other runs in the same process.
STALE_MONTHS = 18

COPYRIGHT = re.compile(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(\d{4})", re.I)
# Digit guards, not \b: the standard datetime "2023-12-11T14:15:55+00:00" has no
# word boundary between the day and "T", so \b ignored every dated page.
ISO_DATE = re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)")
# The listing page of a blog or news section is not an article: it has no date
# of its own and is never stale.
SECTION_INDEX = re.compile(r"^/(blog|news|articles?|insights|press)/?$", re.I)


def _as_number(text: str) -> float | None:
    """A displayed amount as a number, whichever grouping convention it uses.

    "1,299.00" and "1.299,00" are both 1299.0; "49,00" is 49.0; "1.299" and
    "1,299" (one thousands group) are 1299.0; "1,29,999" (Indian lakh grouping)
    is 129999.0. Kept byte-identical with the copy in
    fact-extractability-audit/scripts/check_extractability.py, so a JSON-LD
    price and a visible price are read the same way by both skills.
    """
    s = re.sub(r"[\s  ]", "", str(text))
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        s = s.replace("." if dec == "," else ",", "").replace(dec, ".")
    elif s.count(",") > 1 or re.fullmatch(r"\d{1,3}(,\d{3})+", s):
        s = s.replace(",", "")                  # thousands groups, any locale
    elif "," in s:
        s = s.replace(",", ".")                 # "49,00": a decimal comma
    elif s.count(".") > 1 or re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")                  # "1.299": a thousands dot
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def _http_date(value: str) -> str | None:
    """An RFC 1123 header date ("Wed, 09 Sep 2026 11:04:24 GMT") as YYYY-MM-DD."""
    try:
        return parsedate_to_datetime(value).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return None


def _clock_from(b: dict) -> datetime:
    try:
        return datetime.fromisoformat(b["audited_at"].replace("Z", "+00:00"))
    except (KeyError, ValueError, AttributeError):
        return datetime.now(timezone.utc)


def load_bundle() -> dict:
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        return json.loads(open(sys.argv[1], encoding="utf-8").read())
    return json.loads(sys.stdin.read())


def _item_identity(props: dict) -> str | None:
    for key in ("sku", "gtin", "gtin13", "mpn", "name"):
        value = props.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return f"{key}:{' '.join(str(value).lower().split())}"
    return None


def _offer_prices(offers) -> set:
    """Declared prices as numbers; AggregateOffer ranges are not single prices."""
    out = set()
    for offer in (offers if isinstance(offers, list) else [offers]):
        if not isinstance(offer, dict):
            continue
        types = offer.get("@type")
        if "aggregateoffer" in str(types).lower():
            continue
        value = _as_number(offer.get("price", ""))
        if value is not None:
            out.add(value)
    return out


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
    prices_by_item: dict[str, dict[str, set]] = {}

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
        # The header is RFC 1123, not ISO: parsed, then fed in as YYYY-MM-DD.
        header_date = _http_date(p["headers"].get("last-modified", ""))
        if header_date:
            signals.append(header_date)
        # JSON-LD dates come only from real date properties, never from @id URLs.
        signals.extend(d["jsonld"]["dates"])

        blob = " ".join(signals)
        dates = ISO_DATE.findall(blob)
        # Blog/article pages only. A homepage routinely and correctly carries no
        # date; firing there would be a false positive on most sites. The
        # section's own index page (/blog, /news) is a listing, not an article.
        is_article = (p["role"] == "blog"
                      and not SECTION_INDEX.match(urlparse(p["url"]).path or "/"))
        if is_article and not dates:
            no_dates.append((p["url"], p["role"]))
        elif dates:
            ages = [_months_since(now, int(y), int(mo), int(dd)) for y, mo, dd in dates]
            newest = min(ages) if ages else 0
            if is_article and newest > STALE_MONTHS:
                stale_content.append((p["url"], round(newest)))

        # -- D4 internal contradiction (price consistency) ------------------
        # Only the SAME item can contradict itself. Items are identified by the
        # sku or name the site declares in Product markup; two different
        # products at two different prices is a catalogue, not a contradiction.
        for node in d["jsonld"]["nodes"]:
            if "product" not in node["types"]:
                continue
            props = node["props"]
            ident = _item_identity(props)
            prices = _offer_prices(props.get("offers"))
            if ident and prices:
                prices_by_item.setdefault(ident, {}).setdefault(p["url"], set()).update(prices)

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
                "summary": "Review whether each page is still accurate; update dateModified if "
                           "it is, or mark it archived if it is not.",
                "priority": "low", "effort": "low",
                "how": ["Read each page against what is true today. If nothing has changed, "
                        "say so: a reviewed date in dateModified is an honest freshness signal.",
                        "If it has been superseded, label it archived (a visible note plus a "
                        "link to the current page) rather than leaving it to be quoted as "
                        "current.",
                        "Reference material can be years old and still right; the age is the "
                        "prompt to check, not the verdict."],
                "verify": "Each listed page carries a dateModified from the review, or an "
                          "archived notice.",
            },
        })

    conflicts = []
    for ident, per_page in sorted(prices_by_item.items()):
        if len(per_page) > 1 and len({frozenset(v) for v in per_page.values()}) > 1:
            conflicts.append((ident, per_page))
    if conflicts:
        findings.append({
            "check_id": "D4_internal_contradiction",
            "title": f"{len(conflicts)} product(s) are declared at different prices on different pages",
            "evidence": " | ".join(
                f"'{ident}': " + "; ".join(f"{u} declares {sorted(v)}"
                                           for u, v in sorted(per_page.items())[:3])
                for ident, per_page in conflicts[:3])
                + ". Each item is matched by the sku or name in its Product markup, so these "
                  "are the same item priced differently by the site itself.",
            "affected_urls": sorted({u for _, per_page in conflicts for u in per_page}),
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

    # Corroboration hooks (a citable facts page, sameAs anchors) are not a
    # finding here: a missing Organization sameAs is C3's, and the orchestrator's
    # proactive "citable facts page" recommendation covers the rest.
    skipped.append({
        "check": "D6_cross_web_corroboration",
        "reason": "Not assessed: whether independent third parties agree with this site's "
                  "claims. Reason: that needs a search backend, which this marketplace does "
                  "not assume. How to check it yourself: search your brand plus a key fact "
                  "(price, founding year, HQ) and count independent sources that agree.",
        "impact": "Claims that exist only on this site are not distinguished from claims "
                  "corroborated across the web. The on-site corroboration checks still ran.",
    })
    return findings, skipped


if __name__ == "__main__":
    f, s = run(load_bundle())
    print(json.dumps({"findings": f, "checks_skipped": s}, indent=2, ensure_ascii=False))
