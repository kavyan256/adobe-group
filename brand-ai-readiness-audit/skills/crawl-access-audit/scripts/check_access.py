#!/usr/bin/env python3
"""Gate 1 - can a retrieval agent reach the page at all?

Standalone: reads a site bundle (JSON on stdin or a path argv[1]) and writes a
findings array to stdout. Depends only on the standard library + BeautifulSoup.

Central rule enforced here
--------------------------
Blocking a TRAINING crawler is a licensing posture, not a discoverability
defect. Only agents that gate live retrieval / indexing produce a finding.
Getting this wrong fires "you are invisible to AI" at publishers who correctly
allow retrieval while refusing training -- the most likely false positive in
the entire audit.
"""
from __future__ import annotations

import json
import re
import sys
from urllib.parse import urlparse

from bs4 import BeautifulSoup

SNIPPET_SUPPRESSORS = ("nosnippet", "noarchive", "max-snippet:0", "max-snippet: 0")


def load_bundle() -> dict:
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        return json.loads(open(sys.argv[1], encoding="utf-8").read())
    return json.loads(sys.stdin.read())


def ok_pages(b: dict) -> list[dict]:
    return [p for p in b["pages"] if 200 <= p["status"] < 300 and p["html"]]


def _robots_directives(page: dict, soup: BeautifulSoup) -> str:
    parts = [page["headers"].get("x-robots-tag", "")]
    for m in soup.find_all("meta"):
        if (m.get("name") or "").lower() in ("robots", "googlebot"):
            parts.append(m.get("content") or "")
    return " ".join(parts).lower()


def run(b: dict) -> list[dict]:
    out: list[dict] = []
    pages = ok_pages(b)
    total = len(pages)

    # -- A7: nothing readable at all -------------------------------------
    if total == 0:
        reason = {"blocked": "robots.txt disallows our auditor's user-agent",
                  "failed": "no page returned readable HTML"}.get(
                      b["run_status"], "site could not be read")
        return [{
            "check_id": "A7_site_unreadable",
            "title": "Site could not be read by an automated client",
            "evidence": (f"{reason}. Attempted {b['coverage']['pages_attempted']} URL(s); "
                         f"{b['coverage']['pages_ok']} returned usable HTML. "
                         f"run_status={b['run_status']}."),
            "affected_urls": [b["start_url"]],
            "blast_radius": "site_wide",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Make the site reachable by non-browser clients before anything else.",
                "priority": "critical",
                "effort": "medium",
                "how": ["Confirm the site returns HTTP 200 to a plain GET with a non-browser "
                        "User-Agent (test: curl -A 'AIReadinessAudit/1.0' -I <url>).",
                        "If a WAF or bot-management rule is challenging non-browser clients, "
                        "add an allow rule for documented assistant retrieval agents.",
                        "If robots.txt is blocking broadly, narrow the Disallow rules."],
                "verify": "curl -sI <url> returns 200 and curl -s <url> returns HTML containing "
                          "your main heading.",
            },
        }]

    # -- A1: retrieval agents blocked -------------------------------------
    agents = b["robots"]["agents"]
    blocked_retrieval = {t: d for t, d in agents.items()
                         if d["class"] == "retrieval" and (d["fully_blocked"] or d["partially_blocked"])}
    blocked_training = [t for t, d in agents.items()
                        if d["class"] == "training" and d["fully_blocked"]]

    if blocked_retrieval:
        names = ", ".join(sorted(blocked_retrieval))
        sample = sorted({p for d in blocked_retrieval.values() for p in d["blocked_paths"]})[:6]
        note = ""
        if blocked_training:
            note = (f" (Note: {', '.join(sorted(blocked_training))} are also blocked, but those "
                    f"are training-only agents and do not affect citation -- reported separately "
                    f"as policy, not as a defect.)")
        out.append({
            "check_id": "A1_retrieval_agent_blocked",
            "title": f"robots.txt blocks {len(blocked_retrieval)} AI retrieval agent(s)",
            "evidence": (f"robots.txt disallows these retrieval/indexing agents: {names}. "
                         f"Blocked paths sampled: {sample}. These agents fetch pages in order to "
                         f"answer user questions, so pages they cannot reach cannot be cited.{note}"),
            "affected_urls": [b["start_url"] + "/robots.txt"],
            "blast_radius": "site_wide",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Allow retrieval agents even if you continue to block training crawlers.",
                "priority": "critical",
                "effort": "low",
                "how": [
                    "In robots.txt, add explicit Allow groups for the retrieval agents you want "
                    "citing you: OAI-SearchBot, ChatGPT-User, Claude-SearchBot, Claude-User, "
                    "PerplexityBot, Perplexity-User, Applebot.",
                    "Keep any GPTBot / ClaudeBot / Google-Extended / CCBot blocks if refusing "
                    "training is a deliberate policy -- those are independent of citation.",
                    "Example:\n  User-agent: OAI-SearchBot\n  Allow: /\n\n"
                    "  User-agent: GPTBot\n  Disallow: /",
                ],
                "verify": "Re-run this audit; A1 should no longer fire for retrieval agents.",
            },
            "detail": {"blocked_retrieval_agents": sorted(blocked_retrieval),
                       "blocked_training_agents": sorted(blocked_training)},
        })

    # -- A2/A3: per-page directives ---------------------------------------
    noindex, nosnippet, canonical_problems, chains = [], [], [], []
    for p in pages:
        soup = BeautifulSoup(p["html"], "html.parser")
        directives = _robots_directives(p, soup)

        if "noindex" in directives:
            noindex.append(p["url"])
        if any(s in directives for s in SNIPPET_SUPPRESSORS) or 'data-nosnippet' in p["html"]:
            nosnippet.append(p["url"])

        link = soup.find("link", rel=lambda v: v and "canonical" in [x.lower() for x in v])
        if link and link.get("href"):
            href = link["href"]
            if urlparse(href).netloc and urlparse(href).netloc != urlparse(p["final_url"]).netloc:
                canonical_problems.append((p["url"], f"points off-domain to {href}"))
        elif p["role"] in ("product", "pricing", "blog"):
            canonical_problems.append((p["url"], "no canonical link on a duplicate-prone page type"))

        if len(p["redirect_chain"]) > 2:
            chains.append((p["url"], len(p["redirect_chain"])))

    if noindex:
        out.append({
            "check_id": "A3_noindex",
            "title": f"{len(noindex)} page(s) carry a noindex directive",
            "evidence": (f"{len(noindex)}/{total} crawled pages emit noindex via meta robots or "
                         f"X-Robots-Tag. Examples: {noindex[:3]}. A noindex page is removed from "
                         f"the indexes that assistants draw on."),
            "affected_urls": noindex,
            "blast_radius": "site_wide" if len(noindex) == total else "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Remove noindex from pages that should be findable.",
                "priority": "critical", "effort": "low",
                "how": ["Delete the noindex value from the meta robots tag or the X-Robots-Tag "
                        "response header on these URLs.",
                        "Check for a staging-environment header leaking into production."],
                "verify": "curl -sI <url> | grep -i x-robots-tag  returns nothing, and the page "
                          "source contains no noindex.",
            },
        })

    if nosnippet:
        out.append({
            "check_id": "A2_snippet_suppressed",
            "title": f"{len(nosnippet)} page(s) suppress text snippets",
            "evidence": (f"{len(nosnippet)}/{total} pages carry nosnippet, noarchive, "
                         f"max-snippet:0 or data-nosnippet. Examples: {nosnippet[:3]}. These pages "
                         f"stay indexed but their text may not be quoted in an AI answer -- the page "
                         f"can pass every other check and still be unquotable."),
            "affected_urls": nosnippet,
            "blast_radius": "site_wide" if len(nosnippet) == total else "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Allow snippets on pages you want quoted.",
                "priority": "high", "effort": "low",
                "how": ["Remove nosnippet / noarchive / max-snippet:0 from meta robots and "
                        "X-Robots-Tag on pages meant to be cited.",
                        "If you use max-snippet to limit length, set a positive character budget "
                        "(e.g. max-snippet:160) rather than 0.",
                        "Remove data-nosnippet wrappers from blocks containing your key facts."],
                "verify": "Page source contains no nosnippet/noarchive and no data-nosnippet "
                          "around primary content.",
            },
        })

    if canonical_problems:
        out.append({
            "check_id": "A5_canonical_problem",
            "title": f"Canonical link problems on {len(canonical_problems)} page(s)",
            "evidence": "; ".join(f"{u}: {why}" for u, why in canonical_problems[:4]),
            "affected_urls": [u for u, _ in canonical_problems],
            "blast_radius": "template" if len(canonical_problems) < total else "site_wide",
            "confidence": "heuristic",
            "suggested_action": {
                "summary": "Give every indexable page a self-referencing canonical URL.",
                "priority": "medium", "effort": "low",
                "how": ['Add <link rel="canonical" href="<absolute self URL>"> to each page.',
                        "Only point canonical off-domain when you genuinely intend the other "
                        "domain to receive all credit."],
                "verify": "Each page's canonical resolves to itself with HTTP 200.",
            },
        })

    if chains:
        out.append({
            "check_id": "A4_redirect_chain",
            "title": f"Long redirect chains on {len(chains)} URL(s)",
            "evidence": "; ".join(f"{u}: {n} hops" for u, n in chains[:4]),
            "affected_urls": [u for u, _ in chains],
            "blast_radius": "single_page",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Collapse redirect chains to a single hop.",
                "priority": "low", "effort": "low",
                "how": ["Rewrite the redirect rules so the first URL points straight at the final "
                        "destination.", "Prefer 301 for permanent moves."],
                "verify": "curl -sIL <url> shows at most one 3xx before the 200.",
            },
        })

    # -- A6: sitemap -------------------------------------------------------
    if not b["sitemap_urls"]:
        out.append({
            "check_id": "A6_sitemap_missing",
            "title": "No usable XML sitemap discovered",
            "evidence": (f"robots.txt declared {len(b['robots']['sitemaps_declared'])} sitemap(s) "
                         f"and /sitemap.xml yielded no parsable <loc> entries. Crawlers then rely "
                         f"entirely on link discovery."),
            "affected_urls": [b["start_url"]],
            "blast_radius": "site_wide",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Publish an XML sitemap and reference it from robots.txt.",
                "priority": "low", "effort": "low",
                "how": ["Generate /sitemap.xml listing every canonical URL with an accurate "
                        "<lastmod>.", "Add 'Sitemap: https://<host>/sitemap.xml' to robots.txt."],
                "verify": "curl -s https://<host>/sitemap.xml | grep -c '<loc>' returns > 0.",
            },
        })
    return out


if __name__ == "__main__":
    print(json.dumps(run(load_bundle()), indent=2, ensure_ascii=False))
