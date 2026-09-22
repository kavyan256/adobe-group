#!/usr/bin/env python3
"""Gate 1 - can a retrieval agent reach the page at all?

Standalone: reads a site bundle (path argv[1], or stdin) and writes a findings
array to stdout. Only agents that gate retrieval produce a finding; blocking a
training crawler is policy, not a defect (references/bot-taxonomy.md).
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


# Deliberate configuration vs. breakage: findings that look chosen are reported
# as confirm_intent (a question, capped at low). Rules in
# references/deliberate-vs-defect.md.

# Templates a site routinely and legitimately keeps out of a search index.
EXCLUDABLE_ROLES = {"legal", "utility", "search"}
# Templates whose exclusion is never routine: these ARE the brand's answer surface.
CONTENT_ROLES = {"home", "product", "pricing", "about", "blog", "contact"}
MAX_DELIBERATE_NOINDEX_SHARE = 0.34


def _classify_noindex(noindex_pages: list, total: int) -> tuple[str, list]:
    """Is this noindex confined to templates a site routinely excludes?"""
    roles = {p["role"] for p in noindex_pages}
    share = len(noindex_pages) / total if total else 1.0
    if (len(noindex_pages) < total
            and share <= MAX_DELIBERATE_NOINDEX_SHARE
            and roles <= EXCLUDABLE_ROLES
            and not (roles & CONTENT_ROLES)):
        return "confirm_intent", [
            f"{len(noindex_pages)} of {total} crawled pages ({share:.0%}) carry noindex",
            f"all of them are on {'/'.join(sorted(roles))} templates: "
            f"{sorted(p['url'] for p in noindex_pages)[:3]}",
            "no noindex was found on home, pricing, product, about, blog or contact templates",
            "confining noindex to legal and utility templates is a common deliberate "
            "configuration, not a defect",
        ]
    return "active", []


def _classify_ai_block(b: dict, agents: dict, blocked_retrieval: dict) -> tuple[str, list]:
    """Deliberate AI policy, or wildcard collateral damage?"""
    named_only = all(not d.get("blocked_via_wildcard", False)
                     for d in blocked_retrieval.values())
    ai_tokens_named = len(b.get("probes", {}).get("ai_agents_named_in_robots", []) or [])
    other_retrieval_allowed = [t for t, d in agents.items()
                               if d["class"] == "retrieval"
                               and not d["fully_blocked"] and not d["partially_blocked"]]
    all_fully_blocked = all(d["fully_blocked"] for d in blocked_retrieval.values())

    if named_only and (ai_tokens_named >= 2 or other_retrieval_allowed) and not all_fully_blocked:
        return "confirm_intent", [
            "every blocking rule comes from a group naming that agent explicitly, "
            "not from the wildcard group",
            f"robots.txt names {ai_tokens_named} AI agent(s) by token, which indicates a "
            "per-agent policy rather than an inherited rule",
            (f"other retrieval agents remain allowed: {sorted(other_retrieval_allowed)[:4]}"
             if other_retrieval_allowed else
             "blocks are path-scoped rather than whole-site"),
            "blocking retrieval agents is a coherent licensing position; the cost is that "
            "assistants cannot cite you, which is a business decision, not a bug",
        ]
    return "active", []


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
        status, signals = _classify_ai_block(b, agents, blocked_retrieval)
        rules = sorted({r for d in blocked_retrieval.values()
                        for r in d.get("deciding_rules", [])})[:4]
        if rules:
            note += f" Deciding robots.txt rule(s): {rules}."
        out.append({
            "check_id": "A1_retrieval_agent_blocked",
            "status": status,
            "intent_signals": signals,
            "title": (f"Confirm intent: robots.txt deliberately blocks "
                      f"{len(blocked_retrieval)} AI retrieval agent(s)"
                      if status == "confirm_intent" else
                      f"robots.txt blocks {len(blocked_retrieval)} AI retrieval agent(s)"),
            "evidence": (f"robots.txt disallows these retrieval/indexing agents: {names}. "
                         f"Blocked paths sampled: {sample}. These agents fetch pages in order to "
                         f"answer user questions, so pages they cannot reach cannot be cited.{note}"),
            "affected_urls": [b["start_url"] + "/robots.txt"],
            "blast_radius": "site_wide",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": ("Confirm you intend to be uncitable in AI assistants; if not, allow "
                            "the retrieval agents you want citing you."
                            if status == "confirm_intent" else
                            "Allow retrieval agents even if you continue to block training crawlers."),
                "priority": "low" if status == "confirm_intent" else "critical",
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
                       "blocked_training_agents": sorted(blocked_training),
                       # Path prefixes downstream findings can sit behind, so the
                       # orchestrator can mark them latent.
                       "blocked_paths": sorted({p for d in blocked_retrieval.values()
                                                for p in d["blocked_paths"]})},
        })

    # -- A2/A3: per-page directives ---------------------------------------
    noindex, nosnippet, canonical_problems, chains = [], [], [], []
    for p in pages:
        soup = BeautifulSoup(p["html"], "html.parser")
        directives = _robots_directives(p, soup)

        if "noindex" in directives:
            noindex.append({"url": p["url"], "role": p["role"]})
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
        status, signals = _classify_noindex(noindex, total)
        urls = [n["url"] for n in noindex]
        roles = sorted({n["role"] for n in noindex})
        deliberate = status == "confirm_intent"
        out.append({
            "check_id": "A3_noindex_utility" if deliberate else "A3_noindex",
            "status": status,
            "intent_signals": signals,
            "title": (f"Confirm intent: {len(noindex)} {'/'.join(roles)} page(s) carry noindex"
                      if deliberate else
                      f"{len(noindex)} page(s) carry a noindex directive"),
            "evidence": (f"{len(noindex)}/{total} crawled pages emit noindex via meta robots or "
                         f"X-Robots-Tag. Examples: {urls[:3]}. A noindex page is removed from "
                         f"the indexes that assistants draw on."
                         + (f" All of them are on {'/'.join(roles)} templates, which sites "
                            f"routinely exclude on purpose." if deliberate else "")),
            "affected_urls": urls,
            "blast_radius": "site_wide" if len(noindex) == total else "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": ("Confirm these exclusions are deliberate; remove noindex from any "
                            "page you do want assistants to find."
                            if deliberate else
                            "Remove noindex from pages that should be findable."),
                "priority": "low" if deliberate else "critical",
                "effort": "low",
                "how": (["Check this list against the pages you intend to keep out of search. "
                         "If every one is intentional, no action is needed.",
                         "If any page here should be citable, delete the noindex value from its "
                         "meta robots tag or X-Robots-Tag response header."]
                        if deliberate else
                        ["Delete the noindex value from the meta robots tag or the X-Robots-Tag "
                         "response header on these URLs.",
                         "Check for a staging-environment header leaking into production."]),
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

    # -- A8: robots.txt names a truncated agent token -----------------------
    unrecognised = b["robots"].get("unrecognised_agent_tokens") or []
    if unrecognised:
        lines = "; ".join(f"'User-agent: {u['token']}' (probably meant "
                          f"{', '.join(u['probably_meant'][:3])})" for u in unrecognised[:4])
        out.append({
            "check_id": "A8_robots_token_unrecognised",
            "title": (f"robots.txt names {len(unrecognised)} truncated user-agent token(s) "
                      f"that match no crawler"),
            "evidence": (f"These groups bind nothing: {lines}. RFC 9309 compares the full "
                         f"product token exactly, so a group written 'User-agent: Claude' is "
                         f"matched by neither ClaudeBot nor Claude-User: the rule looks active "
                         f"in the file and affects no crawler."),
            "affected_urls": [b["start_url"] + "/robots.txt"],
            "blast_radius": "site_wide",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Write each crawler's exact product token as its own group.",
                "priority": "medium", "effort": "low",
                "how": ["Replace the partial token with the full ones you meant, one group each.",
                        "Decide retrieval and training separately -- e.g. 'User-agent: ClaudeBot' "
                        "(training) and 'User-agent: Claude-User' (retrieval) are different "
                        "decisions with different consequences for whether you get cited."],
                "verify": "Every User-agent line in robots.txt is either '*' or an exact "
                          "published crawler token.",
            },
            "detail": {"unrecognised": unrecognised[:10]},
        })

    # -- A6: sitemap -------------------------------------------------------
    # A6 asks whether a sitemap exists at all -- not whether it happened to
    # yield page URLs within our crawl budget. A site with a deep sitemap index
    # has a sitemap; saying otherwise is a false positive.
    if not b["sitemap_urls"] and not b["robots"].get("sitemaps_fetched"):
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
