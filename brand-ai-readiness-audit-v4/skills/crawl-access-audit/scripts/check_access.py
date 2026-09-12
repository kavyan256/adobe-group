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
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# noarchive is deliberately absent: it controls cached copies, not quoting.
SNIPPET_SUPPRESSORS = ("nosnippet", "max-snippet:0")

# Bots whose page-level directives decide whether assistants can index or quote
# the page: the unscoped tokens, the two search indexes assistants query (Bing
# feeds ChatGPT search and Copilot), and the retrieval agents. Mirrors
# RETRIEVAL_AGENTS in audit-orchestrator/scripts/robots.py -- repeated here on
# purpose, since each skill must run without importing another.
DIRECTIVE_BOTS = {"robots", "googlebot", "bingbot", "oai-searchbot", "chatgpt-user",
                  "claude-searchbot", "claude-user", "perplexitybot", "perplexity-user",
                  "applebot"}
# Directives that carry a value after a colon, so "max-snippet: 0" is not read
# as a bot named max-snippet.
_VALUED_DIRECTIVES = ("max-snippet", "max-image-preview", "max-video-preview",
                      "unavailable_after")

# Blocking any of these is never read as a per-assistant licensing choice:
# Googlebot and Bingbot feed the indexes most assistants query, and
# OAI-SearchBot is ChatGPT's own.
INDEX_CRITICAL_AGENTS = {"googlebot", "bingbot", "oai-searchbot"}

KEY_ROLES = {"pricing", "product", "contact"}
GENERIC_TITLES = {"home", "index", "untitled", "welcome", "new page", "document"}
SOFT_404_PHRASES = ("not found", "404", "page doesn't exist", "page does not exist",
                    "no longer available", "seite nicht gefunden", "page introuvable",
                    "página no encontrada")
META_REFRESH = re.compile(r"^\s*(\d+)\s*[;,]\s*url\s*=\s*['\"]?([^'\"]+)", re.I)


def load_bundle() -> dict:
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        return json.loads(open(sys.argv[1], encoding="utf-8").read())
    return json.loads(sys.stdin.read())


def ok_pages(b: dict) -> list[dict]:
    return [p for p in b["pages"] if 200 <= p["status"] < 300 and p["html"]]


def _split_directives(value: str) -> list[str]:
    return [v.strip().lower() for v in (value or "").split(",") if v.strip()]


def _parse_x_robots(header: str) -> list[tuple[str, str]]:
    """(bot, directive) pairs from an X-Robots-Tag value.

    A value may be scoped to one crawler ("googlebot-news: noindex, nofollow"),
    in which case the scope carries to the directives after it. Unscoped
    directives bind every crawler and are recorded under "robots".
    """
    pairs, bot = [], "robots"
    for token in _split_directives(header):
        if ":" in token and not token.startswith(_VALUED_DIRECTIVES):
            bot, _, token = (s.strip() for s in token.partition(":"))
        if token:
            pairs.append((bot, token))
    return pairs


def _robots_directives(page: dict, soup: BeautifulSoup) -> list[tuple[str, str]]:
    """Every (bot, directive) the page declares, from the header and every
    <meta name="robots|<bot>">."""
    pairs = _parse_x_robots(page["headers"].get("x-robots-tag", ""))
    for m in soup.find_all("meta"):
        name = (m.get("name") or "").strip().lower()
        if name == "robots" or name in DIRECTIVE_BOTS or name.endswith("bot"):
            pairs.extend((name, d) for d in _split_directives(m.get("content") or ""))
    return pairs


def _gating(pairs: list[tuple[str, str]]) -> list[str]:
    """Directives aimed at a bot that gates indexing or quoting for assistants.

    A directive scoped to a news-only or training-only crawler
    ("googlebot-news: noindex") does not remove the page for anyone else.
    """
    return [d for bot, d in pairs if bot in DIRECTIVE_BOTS]


def _has_noindex(directives) -> bool:
    """noindex, or "none" as a WHOLE directive value (its shorthand).

    "none" inside max-image-preview:none or max-snippet:… is a different
    setting and must not count.
    """
    values = _split_directives(directives) if isinstance(directives, str) else directives
    return any(v in ("noindex", "none") for v in values)


def _suppresses_snippets(directives) -> bool:
    values = _split_directives(directives) if isinstance(directives, str) else directives
    return any(re.sub(r"\s", "", v) in SNIPPET_SUPPRESSORS for v in values)


def _nosnippet_on_content(soup: BeautifulSoup) -> bool:
    """data-nosnippet only counts on or around the primary content.

    A cookie banner wrapped in data-nosnippet leaves the page fully quotable;
    the h1, <main>/<article>, or the first substantial paragraph inside such a
    wrapper does not.
    """
    wrapped = soup.find_all(attrs={"data-nosnippet": True})
    if not wrapped:
        return False
    first_p = next((p for p in soup.find_all("p")
                    if len(p.get_text(" ", strip=True).split()) >= 20), None)
    for el in wrapped:
        if el.name in ("main", "article") or el.find(["main", "article", "h1"]):
            return True
        if first_p is not None and (el is first_p or any(a is el for a in first_p.parents)):
            return True
    return False


def _page_title(soup: BeautifulSoup) -> str:
    return " ".join(soup.title.get_text(" ", strip=True).split()) if soup.title else ""


def _looks_soft_404(soup: BeautifulSoup) -> str | None:
    """The title or h1 phrase that reads as a not-found page, if any."""
    h1 = soup.find("h1")
    for text in (_page_title(soup), h1.get_text(" ", strip=True) if h1 else ""):
        low = text.lower()
        for phrase in SOFT_404_PHRASES:
            if phrase in low:
                return text[:80]
    return None


def _canonical_href(soup: BeautifulSoup) -> str | None:
    """The first <link rel="canonical"> href, or None.

    bs4 exposes rel as a list of tokens on some parsers and a string on others,
    so both shapes are normalised here rather than trusted to a find() filter.
    """
    for link in soup.find_all("link", href=True):
        rel = link.get("rel") or []
        tokens = rel.split() if isinstance(rel, str) else rel
        if "canonical" in {t.lower() for t in tokens}:
            return link["href"].strip() or None
    return None


# Deliberate configuration vs. breakage: findings that look chosen are reported
# as confirm_intent (a question, capped at low). Rules in
# references/deliberate-vs-defect.md.

# Templates whose exclusion is never routine: these ARE the brand's answer surface.
CONTENT_ROLES = {"home", "product", "pricing", "about", "blog", "contact"}
MAX_DELIBERATE_NOINDEX_SHARE = 0.5


def _classify_noindex(noindex_pages: list, total: int) -> tuple[str, list]:
    """Is this noindex on pages a site routinely keeps out of an index?

    Critical when it reaches a key page (home, pricing, product, about, blog,
    contact) or most of the crawl. Elsewhere -- profiles, archives, pagination,
    legal and utility pages -- it is usually deliberate, so it is asked about,
    not asserted (5 such cases were reported as critical in the 100-site
    evaluation: user profiles, tribunal decisions, reward pages, teasers,
    pagination).
    """
    roles = {p["role"] for p in noindex_pages}
    share = len(noindex_pages) / total if total else 1.0
    if roles & CONTENT_ROLES or share > MAX_DELIBERATE_NOINDEX_SHARE or len(noindex_pages) == total:
        return "active", []
    return "confirm_intent", [
        f"{len(noindex_pages)} of {total} crawled pages ({share:.0%}) carry noindex",
        f"none of them is a home, pricing, product, about, blog or contact page: "
        f"{sorted(p['url'] for p in noindex_pages)[:3]}",
        "sites routinely keep profiles, archives, pagination, legal and utility pages out of "
        "an index on purpose",
    ]


def _classify_ai_block(b: dict, agents: dict, blocked_retrieval: dict) -> tuple[str, list]:
    """Deliberate AI policy, or wildcard collateral damage?

    A site that blocks some retrieval agents BY NAME while another retrieval
    agent stays fully allowed wrote a per-agent policy. A block inherited from
    the wildcard group, or one that catches Googlebot, Bingbot or OAI-SearchBot,
    stays a defect whatever else the file says.
    """
    named_only = all(not d.get("blocked_via_wildcard", False)
                     for d in blocked_retrieval.values())
    index_critical = sorted(t for t in blocked_retrieval if t.lower() in INDEX_CRITICAL_AGENTS)
    ai_tokens_named = len(b.get("probes", {}).get("ai_agents_named_in_robots", []) or [])
    other_retrieval_allowed = [t for t, d in agents.items()
                               if d["class"] == "retrieval"
                               and not d["fully_blocked"] and not d["partially_blocked"]]
    all_fully_blocked = all(d["fully_blocked"] for d in blocked_retrieval.values())

    if named_only and not index_critical and (other_retrieval_allowed or not all_fully_blocked):
        return "confirm_intent", [
            "every blocking rule comes from a group naming that agent explicitly, "
            "not from the wildcard group",
            f"robots.txt names {ai_tokens_named} AI agent(s) by token, which indicates a "
            "per-agent policy rather than an inherited rule",
            (f"other retrieval agents remain fully allowed: {sorted(other_retrieval_allowed)[:4]}"
             if other_retrieval_allowed else
             "blocks are path-scoped rather than whole-site"),
            "Googlebot, Bingbot and OAI-SearchBot, which feed the indexes most assistants "
            "query, are not blocked",
            "blocking retrieval agents is a coherent licensing position; the cost is that "
            "assistants cannot cite you, which is a business decision, not a bug",
        ]
    return "active", []


def _robots_unfetched_reason(b: dict) -> str | None:
    """Why run_status is "blocked" when robots.txt itself was the problem.

    bundle.py treats an unreachable robots.txt, or a 5xx on it, as disallow-all
    (RFC 9309's conservative reading), so every URL is skipped and the run is
    reported as blocked without robots.txt ever naming our user-agent.
    """
    robots = b.get("robots") or {}
    status = robots.get("status") or 0
    if (not status or robots.get("reachable") is False
            or any("robots.txt unreachable" in n for n in b.get("notes", []))):
        return ("robots.txt could not be fetched, and an unreachable robots.txt is treated "
                "as disallow-all, so no page was requested")
    if 500 <= status < 600:
        return (f"robots.txt answered HTTP {status}, which is treated as disallow-all, "
                f"so no page was requested")
    return None


def run(b: dict) -> list[dict]:
    out: list[dict] = []
    pages = ok_pages(b)
    total = len(pages)

    # -- A7: nothing readable at all -------------------------------------
    if total == 0:
        statuses = sorted({p["status"] for p in b["pages"] if p.get("status")})
        refused = [s for s in statuses if s in (401, 403, 429, 503)]
        errors = sorted({p["error"] for p in b["pages"] if p.get("error")})
        challenges = sorted({p["error"].split(":", 1)[1] for p in b["pages"]
                             if (p.get("error") or "").startswith("bot_challenge:")})
        title = "Site could not be read by an automated client"
        confidence = "deterministic"
        if b["run_status"] == "blocked":
            reason = (_robots_unfetched_reason(b)
                      or "robots.txt disallows our auditor's user-agent")
        elif challenges:
            title = "Site serves a bot-challenge page to automated clients"
            reason = (f"instead of the page, the server returned a bot-challenge page "
                      f"({', '.join(challenges)}), which a client that does not run a browser "
                      f"cannot pass. AI retrieval agents are commonly stopped by the same wall")
            confidence = "heuristic"
        elif refused:
            codes = "/".join(map(str, refused))
            title = f"Site refuses automated clients (HTTP {codes})"
            reason = (f"the server answered HTTP {codes} instead of the page. On a first, single "
                      f"request that usually means bot protection or rate limiting rather than an "
                      f"outage, and AI retrieval agents are commonly refused by the same rule")
            # We observe our own client being refused, not the AI agents.
            confidence = "heuristic"
        elif errors:
            reason = f"requests failed ({', '.join(errors)})"
        else:
            reason = (f"no page returned readable HTML (HTTP status seen: "
                      f"{', '.join(map(str, statuses)) or 'none'})")
        return [{
            "check_id": "A7_site_unreadable",
            "title": title,
            "evidence": (f"{reason}. Attempted {b['coverage']['pages_attempted']} URL(s); "
                         f"{b['coverage']['pages_ok']} returned usable HTML. "
                         f"run_status={b['run_status']}."),
            "affected_urls": [b["start_url"]],
            "blast_radius": "site_wide",
            "confidence": confidence,
            "suggested_action": {
                "summary": "Make the site reachable by non-browser clients before anything else.",
                "priority": "critical",
                "effort": "medium",
                "how": ["Confirm the site returns HTTP 200 to a plain GET with a non-browser "
                        "User-Agent (test: curl -A 'AIReadinessAudit/1.0' -I <url>).",
                        "If a WAF or bot-management rule is challenging non-browser clients, "
                        "add an allow rule for documented assistant retrieval agents.",
                        "If robots.txt is blocking broadly, narrow the Disallow rules.",
                        "If robots.txt itself could not be fetched, make sure /robots.txt "
                        "answers HTTP 200 (or 404): crawlers treat an unreachable one as "
                        "disallow-all."],
                "verify": "curl -sI <url> returns 200 and curl -s <url> returns HTML containing "
                          "your main heading.",
            },
        }]

    robots_url = urljoin(b["start_url"], "/robots.txt")

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
            "affected_urls": [robots_url],
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
    noindex, nosnippet, canonical_problems, canonical_missing, chains = [], [], [], [], []
    scoped_only, refreshes, soft_404s = [], [], []
    for p in pages:
        soup = BeautifulSoup(p["html"], "html.parser")
        pairs = _robots_directives(p, soup)
        directives = _gating(pairs)

        if _has_noindex(directives):
            noindex.append({"url": p["url"], "role": p["role"]})
        elif _has_noindex([d for _, d in pairs]):
            # noindex aimed at a news-only or training-only crawler: the page
            # stays indexed for everyone that matters here. Recorded, not fired.
            scoped_only.append((p["url"], sorted({bot for bot, d in pairs
                                                  if d in ("noindex", "none")})))
        if _suppresses_snippets(directives) or _nosnippet_on_content(soup):
            nosnippet.append(p["url"])

        href = _canonical_href(soup)
        if href:
            target = urlparse(urljoin(p["final_url"], href))
            here = urlparse(p["final_url"])
            # www.example.com and example.com are the same site.
            same_site = (re.sub(r"^www\.", "", target.netloc.lower())
                         == re.sub(r"^www\.", "", here.netloc.lower()))
            if target.netloc and not same_site:
                canonical_problems.append((p["url"], f"points off-domain to {href}"))
            elif (p["role"] != "home" and (target.path or "/") == "/"
                  and (here.path or "/") != "/"):
                # A content page declaring the homepage as its canonical asks to be
                # treated as a duplicate of it, so its own content is dropped.
                canonical_problems.append((p["url"], f"points to the homepage ({href}), "
                                                     f"marking this page a duplicate of it"))
        elif p["role"] in ("product", "pricing", "blog"):
            canonical_missing.append(p["url"])

        if len(p["redirect_chain"]) > 2:
            chains.append((p["url"], len(p["redirect_chain"])))

        # A10: <meta http-equiv="refresh"> pointing somewhere else.
        for m in soup.find_all("meta", attrs={"http-equiv": re.compile(r"^refresh$", re.I)}):
            hit = META_REFRESH.match(m.get("content") or "")
            if hit and urljoin(p["final_url"], hit.group(2).strip()) != p["final_url"]:
                refreshes.append((p["url"], int(hit.group(1)), hit.group(2).strip()))

        # A11: HTTP 200 wrapped around a not-found page.
        phrase = _looks_soft_404(soup)
        if phrase:
            soft_404s.append((p["url"], phrase))

    if noindex:
        status, signals = _classify_noindex(noindex, total)
        urls = [n["url"] for n in noindex]
        roles = sorted({n["role"] for n in noindex})
        deliberate = status == "confirm_intent"
        out.append({
            "check_id": "A3_noindex_utility" if deliberate else "A3_noindex",
            "status": status,
            "intent_signals": signals,
            "title": (f"Confirm intent: {len(noindex)} page(s) outside the key templates carry noindex"
                      if deliberate else
                      f"{len(noindex)} page(s) carry a noindex directive"),
            "evidence": (f"{len(noindex)}/{total} crawled pages emit noindex via meta robots or "
                         f"X-Robots-Tag. Examples: {urls[:3]}. A noindex page is removed from "
                         f"the indexes that assistants draw on."
                         + (" None of them is a home, pricing, product, about, blog or contact "
                            f"page ({'/'.join(roles)} templates); pages like these are often "
                            f"excluded on purpose." if deliberate else "")),
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
            **({"detail": {"scoped_to_other_bots": [
                {"url": u, "bots": bots} for u, bots in scoped_only[:10]]}}
               if scoped_only else {}),
        })

    if nosnippet:
        out.append({
            "check_id": "A2_snippet_suppressed",
            "title": f"{len(nosnippet)} page(s) suppress text snippets",
            "evidence": (f"{len(nosnippet)}/{total} pages carry nosnippet or max-snippet:0, or "
                         f"wrap their primary content in data-nosnippet. Examples: "
                         f"{nosnippet[:3]}. These pages stay indexed but their text may not be "
                         f"quoted in an AI answer -- the page can pass every other check and "
                         f"still be unquotable."),
            "affected_urls": nosnippet,
            "blast_radius": "site_wide" if len(nosnippet) == total else "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Allow snippets on pages you want quoted.",
                "priority": "high", "effort": "low",
                "how": ["Remove nosnippet / max-snippet:0 from meta robots and X-Robots-Tag on "
                        "pages meant to be cited.",
                        "If you use max-snippet to limit length, set a positive character budget "
                        "(e.g. max-snippet:160) rather than 0.",
                        "Remove data-nosnippet wrappers from blocks containing your key facts; "
                        "keeping it on a cookie banner is fine."],
                "verify": "Page source contains no nosnippet and no data-nosnippet around "
                          "primary content.",
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
                "summary": "Point each page's canonical at itself unless another URL really "
                           "should receive its credit.",
                "priority": "medium", "effort": "low",
                "how": ['Set <link rel="canonical" href="<absolute self URL>"> on each page.',
                        "Only point canonical off-domain when you genuinely intend the other "
                        "domain to receive all credit."],
                "verify": "Each page's canonical resolves to itself with HTTP 200.",
            },
        })

    if canonical_missing:
        out.append({
            "check_id": "A5_canonical_missing",
            "title": f"No canonical link on {len(canonical_missing)} duplicate-prone page(s)",
            "evidence": (f"{len(canonical_missing)}/{total} product, pricing or blog pages declare "
                         f"no <link rel=\"canonical\">. Examples: {canonical_missing[:3]}. Without "
                         f"one, tracking parameters and trailing-slash variants of the same page "
                         f"compete as separate URLs."),
            "affected_urls": canonical_missing,
            "blast_radius": "template" if len(canonical_missing) < total else "site_wide",
            "confidence": "heuristic",
            "suggested_action": {
                "summary": "Give every indexable page a self-referencing canonical URL.",
                "priority": "low", "effort": "low",
                "how": ['Add <link rel="canonical" href="<absolute self URL>"> to each page.'],
                "verify": "Each page's canonical resolves to itself with HTTP 200.",
            },
            "detail": {"note": "A missing canonical is a hygiene gap, not a blocker: an indexer "
                               "picks a URL on its own, usually the one it crawled."},
        })

    if refreshes:
        instant = [(u, t) for u, n, t in refreshes if n == 0]
        out.append({
            "check_id": "A10_meta_refresh",
            "title": f"{len(refreshes)} page(s) redirect with a meta refresh",
            "evidence": ("; ".join(f"{u}: refresh after {n}s to {t}" for u, n, t in refreshes[:4])
                         + (". A zero-delay meta refresh acts as a redirect that many fetchers "
                            "do not follow: they index the empty page they were served."
                            if instant else
                            ". A timed refresh moves the reader on but leaves the fetched page "
                            "as the one an indexer keeps.")),
            "affected_urls": [u for u, _, _ in refreshes],
            "blast_radius": "single_page" if len(refreshes) == 1 else "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Replace meta refresh with an HTTP 301/302 redirect.",
                "priority": "low", "effort": "low",
                "how": ["Serve the redirect from the server (301 for permanent moves), so every "
                        "client lands on the destination.",
                        "If the page must stay, put the real content on it instead of a "
                        "refresh stub."],
                "verify": "curl -sI <url> shows a 3xx with a Location header, and the page "
                          "source has no http-equiv=refresh.",
            },
        })

    if soft_404s:
        out.append({
            "check_id": "A11_soft_404",
            "title": f"{len(soft_404s)} page(s) answer HTTP 200 with a not-found page",
            "evidence": ("; ".join(f"{u}: '{t}'" for u, t in soft_404s[:4])
                         + ". A 200 tells crawlers the page exists, so the error text is indexed "
                           "as the page's content and the real page, if any, is never looked for."),
            "affected_urls": [u for u, _ in soft_404s],
            "blast_radius": "single_page" if len(soft_404s) == 1 else "template",
            "confidence": "heuristic",
            "suggested_action": {
                "summary": "Return a real 404 (or 410) status for pages that do not exist.",
                "priority": "medium", "effort": "low",
                "how": ["Make the error handler set the HTTP status, not just render an error "
                        "template.",
                        "If the URL was linked from your own site or sitemap, fix or remove the "
                        "link."],
                "verify": "curl -sI <url> returns 404 or 410 for a missing page.",
            },
            "detail": {"limit": "Matched on the title or h1 wording only; an article ABOUT "
                                "404 pages would match too. Check the page before acting."},
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

    # -- A9: pages we fetched that answered 404/410/5xx ----------------------
    # 401/403/429 are refusals of our client, not broken pages (A7 covers the
    # site-wide case); status 0 is a transport error with nothing to cite.
    broken = [p for p in b["pages"]
              if p.get("status") in (404, 410) or 500 <= (p.get("status") or 0) < 600]
    if broken:
        listed = set(b.get("sitemap_urls") or [])
        key = [p for p in broken if p["role"] in KEY_ROLES]
        lines = "; ".join(
            f"{p['url']}: HTTP {p['status']}"
            + (" (listed in the sitemap)" if p["url"] in listed else "")
            + (f" ({p['role']} page)" if p["role"] in KEY_ROLES else "")
            for p in broken[:6])
        out.append({
            "check_id": "A9_key_page_broken" if key else "A9_broken_pages",
            "title": (f"{len(broken)} linked page(s) are broken, including a "
                      f"{'/'.join(sorted({p['role'] for p in key}))} page"
                      if key else f"{len(broken)} linked page(s) are broken"),
            "evidence": (f"{lines}. These URLs were reached from the homepage or the sitemap, so "
                         f"a crawler and a visitor both arrive at an error instead of the page."),
            "affected_urls": [p["url"] for p in broken],
            "blast_radius": "single_page" if len(broken) == 1 else "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": ("Restore or redirect the broken key page(s) first, then the rest."
                            if key else "Fix or redirect the broken URLs, and drop them from the "
                                        "sitemap if they are gone for good."),
                "priority": "high" if key else "medium", "effort": "low",
                "how": ["For a moved page, add a 301 to its new URL.",
                        "For a page that is gone, return 410 and remove it from the sitemap and "
                        "internal links.",
                        "For a 5xx, check the server log for that route."],
                "verify": "curl -sI <url> returns 200 or a single 301 to a 200 page.",
            },
            # Hurts both audiences: the orchestrator's HURTS_BOTH set is not ours
            # to edit, so the tag is carried here.
            "detail": {"hurts_both": True,
                       "statuses": sorted({p["status"] for p in broken}),
                       "sitemap_listed": sorted(p["url"] for p in broken if p["url"] in listed)},
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
            "affected_urls": [robots_url],
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
