"""Site-bundle builder: the single fetch pass shared by every sub-skill.

Design contract
---------------
The orchestrator fetches ONCE and writes a normalised, self-describing bundle.
Every sub-skill then reads that bundle and emits its own findings. This is what
lets the sub-skills stay code-independent of each other (no shared library, so
each skill folder remains portable and standalone-installable) while still
producing real outputs for the entrypoint to compose.

Guarantees
----------
* read-only; GET only; never touches authenticated areas
* truthful, identifying User-Agent -- we never impersonate GPTBot or any other
  agent (claiming a UA would bind us to that agent's robots group, and would be
  impersonation besides)
* respects robots.txt for OUR OWN user-agent
* deterministic crawl frontier: sitemap order first, then lexicographic BFS
* global deadline with graceful partial results; coverage is always recorded so
  a truncated crawl can never masquerade as a complete one
"""
from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from robots import Robots  # noqa: E402  (same-folder module, not a shared lib)

USER_AGENT = "AIReadinessAudit/1.0 (+https://github.com/example/brand-ai-readiness-audit)"
DEFAULT_MAX_PAGES = 20
DEFAULT_DEADLINE_S = 240        # leaves headroom inside the 5-minute budget
MAX_HONOURED_CRAWL_DELAY = 2.0  # cap; we reduce page count rather than stall
PER_REQUEST_TIMEOUT = 12.0
MAX_BYTES = 3_000_000

# Page roles inferred from the URL slug. These come from a surface that is NOT
# under test (the URL we crawled), which is what keeps the extractability check
# non-circular -- see fact-extractability-audit/references/extraction-tiers.md
ROLE_PATTERNS = [
    ("pricing", re.compile(r"/(pricing|plans?|subscribe|buy)(/|$|\?)", re.I)),
    # Deliberately narrow: /help and /support are usually documentation hubs, not
    # contact pages, and obligating them to carry a phone number is a false positive.
    ("contact", re.compile(r"/(contact|contact-us|get-in-touch)(/|$|\?)", re.I)),
    ("product", re.compile(r"/(product|item|shop|store|p)/", re.I)),
    ("about",   re.compile(r"/(about|company|who-we-are|our-story)(/|$|\?)", re.I)),
    ("blog",    re.compile(r"/(blog|news|articles?|insights|press)(/|$)", re.I)),
    ("legal",   re.compile(r"/(privacy|terms|legal|cookie)", re.I)),
]


def infer_role(url: str, path_is_root: bool) -> str:
    if path_is_root:
        return "home"
    for role, pattern in ROLE_PATTERNS:
        if pattern.search(url):
            return role
    return "generic"


def normalise(url: str) -> str:
    p = urlparse(url)
    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return urlunparse((p.scheme, p.netloc.lower(), path, "", p.query, ""))


@dataclass
class Page:
    url: str
    final_url: str
    status: int
    role: str
    headers: dict
    html: str
    elapsed_ms: int
    redirect_chain: list = field(default_factory=list)
    error: str | None = None


@dataclass
class Bundle:
    site: str
    start_url: str
    audited_at: str
    user_agent: str
    run_status: str                      # complete | partial | blocked | failed
    coverage: dict
    robots: dict
    sitemap_urls: list
    pages: list
    notes: list = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True, ensure_ascii=False)


def _discover_sitemap_urls(client: httpx.Client, base: str, robots_obj: Robots,
                           notes: list) -> list[str]:
    candidates = list(robots_obj.sitemaps) or [urljoin(base, "/sitemap.xml")]
    found: list[str] = []
    for sm in candidates[:3]:
        try:
            r = client.get(sm, timeout=PER_REQUEST_TIMEOUT)
            if r.status_code != 200:
                continue
            locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)
            # A sitemap index points at more sitemaps; follow one level only.
            if "<sitemapindex" in r.text[:2000].lower() and locs:
                for child in locs[:2]:
                    try:
                        rc = client.get(child, timeout=PER_REQUEST_TIMEOUT)
                        if rc.status_code == 200:
                            found += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", rc.text)
                    except httpx.HTTPError:
                        continue
            else:
                found += locs
        except httpx.HTTPError as exc:
            notes.append(f"sitemap fetch failed for {sm}: {type(exc).__name__}")
    # Deterministic: preserve sitemap order, dedupe, cap.
    seen, ordered = set(), []
    for u in found:
        n = normalise(u)
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered[:200]


def build(start_url: str, max_pages: int = DEFAULT_MAX_PAGES,
          deadline_s: float = DEFAULT_DEADLINE_S) -> Bundle:
    t0 = time.monotonic()
    if not start_url.startswith(("http://", "https://")):
        start_url = "https://" + start_url
    base = normalise(start_url)
    host = urlparse(base).netloc
    notes: list[str] = []

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    client = httpx.Client(headers=headers, follow_redirects=True,
                          timeout=PER_REQUEST_TIMEOUT, verify=True)

    # ---- robots.txt ---------------------------------------------------
    robots_url = urljoin(base, "/robots.txt")
    try:
        rr = client.get(robots_url, timeout=PER_REQUEST_TIMEOUT)
        robots_obj = Robots(rr.text if rr.status_code == 200 else "",
                            status=rr.status_code, reachable=True)
        robots_present = rr.status_code == 200
    except httpx.HTTPError as exc:
        robots_obj = Robots("", status=0, reachable=False)
        robots_present = False
        notes.append(f"robots.txt unreachable: {type(exc).__name__}")

    sitemap_urls = _discover_sitemap_urls(client, base, robots_obj, notes)

    # ---- crawl-delay policy -------------------------------------------
    declared_delay = robots_obj.crawl_delay(USER_AGENT) or 0.0
    delay = min(declared_delay, MAX_HONOURED_CRAWL_DELAY)
    if declared_delay > MAX_HONOURED_CRAWL_DELAY:
        # Reduce breadth rather than blow the runtime budget.
        max_pages = max(5, int(deadline_s / max(declared_delay, 1)))
        notes.append(
            f"robots declares Crawl-delay: {declared_delay}s; honouring {delay}s and "
            f"reducing page budget to {max_pages} to stay inside the runtime limit")

    # ---- deterministic frontier ---------------------------------------
    frontier: list[str] = [base]
    seen = {base}
    for u in sitemap_urls:                       # sitemap order first
        if urlparse(u).netloc == host and u not in seen:
            seen.add(u)
            frontier.append(u)

    pages: list[Page] = []
    attempted = 0
    blocked_by_robots = 0

    while frontier and len(pages) < max_pages:
        if time.monotonic() - t0 > deadline_s:
            notes.append("global deadline reached; crawl truncated")
            break
        url = frontier.pop(0)
        attempted += 1

        if not robots_obj.allowed(USER_AGENT, url):
            blocked_by_robots += 1
            continue

        try:
            r = client.get(url, timeout=PER_REQUEST_TIMEOUT)
            body = r.text[:MAX_BYTES] if "html" in r.headers.get("content-type", "") else ""
            page = Page(
                url=url,
                final_url=str(r.url),
                status=r.status_code,
                role=infer_role(url, urlparse(url).path in ("", "/")),
                headers={k.lower(): v for k, v in r.headers.items()},
                html=body,
                elapsed_ms=int(r.elapsed.total_seconds() * 1000),
                redirect_chain=[str(h.url) for h in r.history],
            )
        except httpx.HTTPError as exc:
            page = Page(url=url, final_url=url, status=0,
                        role=infer_role(url, urlparse(url).path in ("", "/")),
                        headers={}, html="", elapsed_ms=0, error=type(exc).__name__)
        pages.append(page)

        # Expand frontier from the homepage only, lexicographically (deterministic).
        if len(pages) == 1 and page.html:
            links = re.findall(r'href=["\']([^"\'#]+)', page.html)
            same_host = sorted({
                normalise(urljoin(base, l)) for l in links
                if urlparse(urljoin(base, l)).netloc == host
            })
            for l in same_host:
                if l not in seen:
                    seen.add(l)
                    frontier.append(l)

        if delay:
            time.sleep(delay)

    client.close()

    # ---- run status ----------------------------------------------------
    ok = [p for p in pages if 200 <= p.status < 300 and p.html]
    if not pages and blocked_by_robots:
        run_status = "blocked"
    elif not ok:
        run_status = "failed"
    elif len(pages) < min(max_pages, len(seen)) or any(p.error for p in pages):
        run_status = "partial"
    else:
        run_status = "complete"

    sample_paths = sorted({urlparse(p.url).path or "/" for p in pages}) or ["/"]

    return Bundle(
        site=host,
        start_url=base,
        audited_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        user_agent=USER_AGENT,
        run_status=run_status,
        coverage={
            "pages_attempted": attempted,
            "pages_fetched": len(pages),
            "pages_ok": len(ok),
            "pages_blocked_by_robots_for_our_ua": blocked_by_robots,
            "urls_discovered": len(seen),
            "elapsed_s": round(time.monotonic() - t0, 1),
        },
        robots={
            "present": robots_present,
            "status": robots_obj.status,
            "sitemaps_declared": robots_obj.sitemaps,
            "crawl_delay_declared": declared_delay or None,
            "agents": robots_obj.agent_report(sample_paths),
        },
        sitemap_urls=sitemap_urls[:50],
        pages=[asdict(p) for p in pages],
        notes=notes,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: bundle.py <url> [out.json]", file=sys.stderr)
        raise SystemExit(2)
    b = build(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if out:
        out.write_text(b.to_json(), encoding="utf-8")
        print(f"{out}  ({b.run_status}, {b.coverage['pages_ok']} pages)")
    else:
        print(b.to_json())
