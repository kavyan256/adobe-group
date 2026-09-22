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
* polite: every request (robots.txt, sitemaps, llms.txt, pages) at least
  MIN_POLITE_DELAY after the previous one; the crawl stops at the first HTTP 429,
  and at a 503 on the start URL or a second consecutive 503, instead of pushing
  on through rate limiting
* deterministic crawl frontier: sitemap order first, then lexicographic BFS
* global deadline with graceful partial results, and a separate budget for the
  sitemap walk; coverage is always recorded so a truncated crawl can never
  masquerade as a complete one
"""
from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

# httpx is imported lazily, inside build(), on purpose: `audit.py --replay` and the
# test suite import this module only for its normalisers and never fetch anything.
# A module-scope import would make the deterministic, network-free path depend on a
# network library being installed.


def _httpx():
    try:
        import httpx
    except ImportError:  # pragma: no cover
        sys.exit("bundle.py: missing dependency 'httpx'. Install with:  "
                 "pip install -r requirements.txt  (from the marketplace root)")
    return httpx


sys.dont_write_bytecode = True  # keep __pycache__ out of the marketplace
sys.path.insert(0, str(Path(__file__).parent))
from robots import Robots, classify_agent  # noqa: E402  (same-folder module, not a shared lib)

USER_AGENT = "AIReadinessAudit/1.0 (+https://github.com/kavyan256/adobe-group)"
DEFAULT_MAX_PAGES = 20
DEFAULT_DEADLINE_S = 200        # crawl budget; analysis shares the remainder of TOTAL_BUDGET_S
TOTAL_BUDGET_S = 280            # whole audit, inside the 5-minute limit with margin
MAX_HONOURED_CRAWL_DELAY = 2.0  # cap; we reduce page count rather than stall
MIN_POLITE_DELAY = 1.0          # between ANY two requests, even when robots.txt asks for none
SITEMAP_BUDGET_S = 30           # the sitemap walk's own slice of the crawl deadline
PER_REQUEST_TIMEOUT = 12.0
_sleep = time.sleep             # indirection so tests can observe pacing without waiting
MAX_BYTES = 3_000_000
BUNDLE_SCHEMA_VERSION = 2       # v2 adds page["derived"]: normalised JSON-LD + text

# Bound to httpx.HTTPError by build(); only the fetching path ever raises it, and
# that path has already called _httpx().
_HTTP_ERROR: type[BaseException] = Exception

# Page roles inferred from the URL slug. These come from a surface that is NOT
# under test (the URL we crawled), which is what keeps the extractability check
# non-circular -- see fact-extractability-audit/references/extraction-tiers.md
ROLE_PATTERNS = [
    ("pricing", re.compile(r"/(pricing|plans?|subscribe|buy)(/|$|\?)", re.I)),
    # Deliberately narrow: /help and /support are usually documentation hubs, not
    # contact pages, and obligating them to carry a phone number is a false positive.
    ("contact", re.compile(r"/(contact|contact-us|get-in-touch)(/|$|\?)", re.I)),
    ("product", re.compile(r"/(products?|items?|shop|store|p)/", re.I)),
    ("about",   re.compile(r"/(about|company|who-we-are|our-story)(/|$|\?)", re.I)),
    ("blog",    re.compile(r"/(blog|news|articles?|insights|press)(/|$)", re.I)),
    # Whole slugs only: "/privacy-policy" is legal, "/cookieless-web-analytics" is not.
    ("legal",   re.compile(r"/(privacy|terms|legal|cookies?|imprint|impressum|datenschutz|agb|gdpr)"
                           r"(-(policy|notice|statement|of-service|of-use|and-conditions|conditions|"
                           r"settings|preferences|information))?(/|$|\?)", re.I)),
    # Templates a site routinely and legitimately keeps out of an index. Kept
    # AFTER the content roles above so a real page never falls in here, and used
    # by crawl-access-audit to tell deliberate exclusion from breakage.
    ("search",  re.compile(r"/(search|results?|recherche)(/|$|\?)|[?&](q|s|query)=", re.I)),
    ("utility", re.compile(r"/(log-?in|sign-?in|sign-?up|register|account|cart|basket|"
                           r"checkout|preview|thank-?you|thanks|unsubscribe|print|amp|"
                           r"404|error|sitemap)(/|$|\?)", re.I)),
]


# Second pass, for URLs the patterns above do not recognise ("/plans-and-pricing",
# "/preise", "/contact-sales"). A label names a role only if EVERY word in it is a
# role word or a connector and at least one is a role word -- so "Plans & Pricing"
# is a pricing page, while "how-to-buy-a-house" is not.
_ROLE_WORDS = {
    "pricing": {"pricing", "prices", "price", "plans", "plan", "subscribe", "subscriptions",
                "buy", "preise", "tarifs", "tarifas", "precios", "prezzi", "prijzen",
                "priser", "cennik", "precos"},
    "contact": {"contact", "kontakt", "contacto", "contatti", "contato", "contactez", "touch"},
    "about":   {"about", "company", "story", "who", "über", "ueber", "nosotros", "somos",
                "siamo", "sommes"},
}
_ROLE_CONNECTORS = {"and", "our", "us", "the", "we", "are", "get", "in", "sales", "team",
                    "nous", "uns", "quienes", "chi", "qui", "de", "la", "le", "page"}
_TITLE_SPLIT = re.compile(r"\s[|–—·:-]\s")


def _role_from_words(label: str) -> str | None:
    tokens = set(re.findall(r"[^\W\d_]+", label.lower()))
    for role, core in _ROLE_WORDS.items():
        if tokens & core and tokens <= core | _ROLE_CONNECTORS:
            return role
    return None


def infer_role(url: str, path_is_root: bool, title: str = "", anchor: str = "") -> str:
    """Role from surfaces that are not under test: the URL, then the page's own
    title segments, then the homepage anchor text that links to it."""
    if path_is_root:
        return "home"
    for role, pattern in ROLE_PATTERNS:
        if pattern.search(url):
            return role
    leaf = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")
    for label in [leaf, *_TITLE_SPLIT.split(title or ""), anchor]:
        role = _role_from_words(label) if label else None
        if role:
            return role
    return "generic"


# ---------------------------------------------------------------------------
# Normalisation. Runs ONCE here, in the crawl layer, and every sub-skill reads
# the result, so no two skills can disagree about what a page says -- see
# references/jsonld-normalisation.md.
# ---------------------------------------------------------------------------

# The strict extraction model: what a Readability/Trafilatura-grade extractor
# keeps. Anything only visible outside this is, by definition, chrome.
BOILERPLATE_TAGS = ("script", "style", "noscript", "template", "nav", "header",
                    "footer", "aside", "form", "svg")
# The permissive model: everything a human sees, chrome included. Used only where
# a fact legitimately lives in chrome (copyright lines, press links).
INERT_TAGS = ("script", "style", "noscript", "template")

MAX_JSONLD_NODES = 300
MAX_JSONLD_TEXT = 20_000
MAX_JSONLD_DEPTH = 6

_CDATA = re.compile(r"^\s*(?://\s*)?<!\[CDATA\[(.*?)\]\]>\s*$", re.S)
_HTML_COMMENT = re.compile(r"^\s*<!--(.*?)-->\s*$", re.S)
_DATE_KEYS = ("datepublished", "datemodified", "datecreated", "uploaddate")


def _types_of(node: dict) -> list[str]:
    """@type normalised to a list of lowercase bare type names.

    Handles: plain string, list of strings, namespaced IRIs
    ("http://schema.org/Organization" and "schema:Organization"), and absence.
    Never mutates the node -- a check reading props["@type"] still sees the
    original.
    """
    raw = node.get("@type")
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else [raw]
    out = []
    for t in items:
        if not isinstance(t, str):
            continue
        bare = t.rsplit("/", 1)[-1].rsplit(":", 1)[-1].strip().lower()
        if bare:
            out.append(bare)
    return sorted(set(out))


def _walk_nodes(obj, nodes: list, depth: int = 0) -> None:
    """Collect every dict carrying @type into a flat stream.

    @graph members are spliced in; nested entities are collected while remaining
    in place inside their parent's props, so a check can still read
    product["offers"]["price"] structurally.
    """
    if depth > MAX_JSONLD_DEPTH or len(nodes) >= MAX_JSONLD_NODES:
        return
    if isinstance(obj, list):
        for item in obj:
            _walk_nodes(item, nodes, depth)
        return
    if not isinstance(obj, dict):
        return

    graph = obj.get("@graph")
    if graph is not None:
        # Keep the wrapper only if it carries meaning of its own. Yoast and
        # RankMath emit a bare {"@context":..., "@graph":[...]} wrapper.
        if set(obj) - {"@context", "@graph"}:
            _record(obj, nodes)
        _walk_nodes(graph, nodes, depth + 1)
        return

    if _types_of(obj):
        _record(obj, nodes)
    for value in obj.values():
        if isinstance(value, (dict, list)):
            _walk_nodes(value, nodes, depth + 1)


def _record(node: dict, nodes: list) -> None:
    if len(nodes) >= MAX_JSONLD_NODES:
        return
    nodes.append({"types": _types_of(node),
                  "id": node.get("@id") if isinstance(node.get("@id"), str) else None,
                  "props": node})


def _flatten_scalars(obj, acc: list) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _flatten_scalars(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _flatten_scalars(v, acc)
    else:
        acc.append(str(obj))


def normalise_jsonld(soup: BeautifulSoup) -> dict:
    """Parse every ld+json block on a page into one normalised node stream.

    "Malformed" means one thing only: json.loads raised. An unknown @type, a
    missing required property or a non-schema.org vocabulary is NOT malformed --
    that distinction matters because malformed drives a `high` severity.
    """
    blocks = soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)})
    nodes: list = []
    malformed_detail: list = []
    empty_blocks = 0

    for i, tag in enumerate(blocks):
        # tag.string is None whenever the element has more than one child node
        # (a comment or a CDATA wrapper). get_text() is the only reliable read.
        raw = (tag.get_text() or "").strip()
        for pattern in (_HTML_COMMENT, _CDATA):
            m = pattern.match(raw)
            if m:
                raw = m.group(1).strip()
        if not raw:
            empty_blocks += 1        # inert, not broken
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            malformed_detail.append({"index": i, "error": str(exc)[:120],
                                     "excerpt": raw[:120]})
            continue
        _walk_nodes(data, nodes)

    types_present, sameas, dates = set(), set(), set()
    for n in nodes:
        types_present.update(n["types"])
        raw_same = n["props"].get("sameAs")
        for v in (raw_same if isinstance(raw_same, list) else [raw_same]):
            if isinstance(v, str) and v.strip():
                sameas.add(v.strip())
        for key, value in n["props"].items():
            if key.lower() in _DATE_KEYS and isinstance(value, str):
                # Digit guards, not \b: in "2023-12-11T14:15:55+00:00" there is no
                # word boundary between "11" and "T", so \b missed every datetime.
                found = re.search(r"(?<!\d)(20\d{2}-\d{2}-\d{2})(?!\d)", value)
                if found:
                    dates.add(found.group(1))

    scalars: list = []
    _flatten_scalars([n["props"] for n in nodes], scalars)
    text = " ".join(scalars)

    return {
        "block_count": len(blocks),
        "malformed_blocks": len(malformed_detail),
        "malformed_detail": malformed_detail[:4],
        "empty_blocks": empty_blocks,
        "truncated": len(nodes) >= MAX_JSONLD_NODES,
        "nodes": nodes,
        "types_present": sorted(types_present),
        "sameas": sorted(sameas)[:50],
        "dates": sorted(dates)[:20],
        "text": text[:MAX_JSONLD_TEXT],
    }


def normalise_text(soup: BeautifulSoup) -> dict:
    """Exactly two notions of page text, defined once for every skill.

    If a fact is in `full` but not in `extracted`, that gap is itself the
    finding -- never silently mix the two.
    """
    strict = BeautifulSoup(str(soup), "html.parser")
    for tag in strict.find_all(BOILERPLATE_TAGS):
        tag.decompose()
    extracted = " ".join(strict.get_text(" ", strip=True).split())

    loose = BeautifulSoup(str(soup), "html.parser")
    for tag in loose.find_all(INERT_TAGS):
        tag.decompose()
    full = " ".join(loose.get_text(" ", strip=True).split())

    return {"extracted": extracted, "full": full,
            "words_extracted": len(extracted.split())}


PAYLOAD_ISLAND_PATTERNS = [
    ("__NEXT_DATA__",      re.compile(r"id=[\"']__NEXT_DATA__[\"']")),
    ("__NUXT__",           re.compile(r"window\.__NUXT__")),
    ("__APOLLO_STATE__",   re.compile(r"__APOLLO_STATE__")),
    ("window.__INITIAL",   re.compile(r"window\.__INITIAL[_A-Z]*")),
    ("self.__next_f",      re.compile(r"self\.__next_f")),
    ("application/json",   re.compile(r"type=[\"']application/json[\"']")),
]


def derive(html: str) -> dict:
    """Everything a sub-skill needs that would otherwise be re-parsed per skill."""
    soup = BeautifulSoup(html, "html.parser")
    return {
        "jsonld": normalise_jsonld(soup),
        "text": normalise_text(soup),
        # Names only. The payload text itself can be megabytes and stays out of
        # the bundle; check_extractability re-reads it locally when it needs the
        # actual bytes.
        "payload_islands": [name for name, pat in PAYLOAD_ISLAND_PATTERNS
                            if pat.search(html)],
    }


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
    # Normalised JSON-LD + text, computed once here so no two skills can
    # disagree about what this page says. See derive().
    derived: dict = field(default_factory=dict)


@dataclass
class Bundle:
    bundle_schema_version: int
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
    # Cheap single-fetch probes used to condition proactive recommendations on
    # what the site already does, so we never recommend something it has.
    probes: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True, ensure_ascii=False)


_TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
# Bot-management layers answer automated clients with a small interstitial, often
# with HTTP 200. Analysed as the real page, its noindex, empty body and missing
# markup become false findings about the site (boots.com and nypl.org in the
# 100-site evaluation). Vendor markers are trusted only on a small document, so a
# real page that merely loads a vendor script is left alone.
_CHALLENGE_TITLE = re.compile(r"<title[^>]*>\s*(pardon our interruption|just a moment\.{0,3}|"
                              r"attention required! \| cloudflare|access denied|are you a (human|robot)\??|"
                              r"security check(point)?|verifying you are human|one more step)\s*</title>", re.I)
_CHALLENGE_VENDORS = (
    ("Incapsula", re.compile(r"_Incapsula_Resource|Incapsula incident ID", re.I)),
    ("Cloudflare", re.compile(r"cf_chl_opt|cf-browser-verification", re.I)),
    ("PerimeterX", re.compile(r"px-captcha|captcha\.px-cdn\.net", re.I)),
    ("DataDome", re.compile(r"captcha-delivery\.com", re.I)),
    ("Akamai", re.compile(r"Reference&#32;&#35;|Reference #\d+\.[0-9a-f]+", re.I)),
)
CHALLENGE_MAX_BYTES = 60_000
# Vendors inject their script into REAL pages too (glastonburyfestivals.co.uk loads
# _Incapsula_Resource on its homepage), so a vendor marker alone proves nothing.
# A challenge title does; otherwise the page must also carry almost no text.
CHALLENGE_MAX_WORDS = 60
_SCRIPT_OR_STYLE = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.I | re.S)
_ANY_TAG = re.compile(r"<[^>]+>")


def bot_challenge(html: str) -> str | None:
    """The vendor of a bot-challenge interstitial, or None for a real page."""
    if not html or len(html) > CHALLENGE_MAX_BYTES:
        return None
    vendor = next((name for name, pat in _CHALLENGE_VENDORS if pat.search(html)), None)
    if _CHALLENGE_TITLE.search(html[:4000]):
        return vendor or "unrecognised vendor"
    words = len(_ANY_TAG.sub(" ", _SCRIPT_OR_STYLE.sub(" ", html)).split())
    return vendor if vendor and words < CHALLENGE_MAX_WORDS else None
# URLs that are never HTML pages. Following them spends the page budget on
# stylesheets and images, and turns a healthy crawl into "partial".
_ASSET_URL = re.compile(r"\.(css|m?js|json|xml|rss|atom|txt|ico|png|jpe?g|gif|svg|webp|avif|bmp|"
                        r"woff2?|ttf|otf|eot|mp4|webm|mov|mp3|wav|zip|gz|pdf)$", re.I)


def _same_host(a: str, b: str) -> bool:
    """example.com and www.example.com are one site: the typed host and the
    host the site redirects to must not split the crawl."""
    return a.lower().removeprefix("www.") == b.lower().removeprefix("www.")


def homepage_links(html: str, base: str) -> tuple[list[str], dict[str, str]]:
    """Same-host page links from <a href> only, sorted, plus each link's label.

    <link href="...css"> and other asset references are not pages. The label a
    homepage gives a page ("Pricing", "Contact us") is kept as a role signal from
    a surface that is not the page under test.
    """
    host = urlparse(base).netloc
    targets, labels = set(), {}
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        href = a["href"].split("#")[0].strip()
        if not href or href.lower().startswith(("mailto:", "tel:", "javascript:", "data:")):
            continue
        target = normalise(urljoin(base, href))
        if not _same_host(urlparse(target).netloc, host) or _ASSET_URL.search(urlparse(target).path):
            continue
        targets.add(target)
        label = " ".join(a.get_text(" ", strip=True).split())
        if label and target not in labels:
            labels[target] = label[:80]
    return sorted(targets), labels


PRIORITY_ROLES = ("pricing", "contact", "about", "product")
MAX_PRIORITY_PER_ROLE = 2


def prioritise(frontier: list[str], links: list[str], labels: dict[str, str]) -> list[str]:
    """Move up to two homepage-linked pages per fact-bearing role to the front.

    Sitemap and alphabetical order are deterministic but arbitrary: a sitemap that
    opens with blog posts, or a homepage whose links sort /about ... /community
    before /pricing, spends the page budget before reaching the pages the
    extractability checks need. Still deterministic: roles in a fixed order, links
    in sorted order.
    """
    per_role: dict[str, list[str]] = {}
    for link in links:
        role = infer_role(link, urlparse(link).path in ("", "/"), anchor=labels.get(link, ""))
        if role in PRIORITY_ROLES and len(per_role.setdefault(role, [])) < MAX_PRIORITY_PER_ROLE:
            per_role[role].append(link)
    first = [link for role in PRIORITY_ROLES for link in per_role.get(role, [])]
    return first + [u for u in frontier if u not in first]

_SITEMAP_URL = re.compile(r"\.xml(\.gz)?$|sitemap[^/]*\.xml", re.I)


def _is_sitemap_url(url: str) -> bool:
    return bool(_SITEMAP_URL.search(urlparse(url).path))


MAX_SITEMAP_DEPTH = 3       # index -> index -> sitemap -> pages, seen in the wild
MAX_SITEMAPS_FETCHED = 8    # total XML fetches, whatever the shape of the tree


class _Polite:
    """One GET at a time, never sooner than `delay` after the previous request.

    Every fetch in the crawl goes through here -- robots.txt, sitemaps, the
    llms.txt probe and the pages -- so the spacing holds across stages, not
    just between pages.
    """

    def __init__(self, client, delay: float = MIN_POLITE_DELAY):
        self.client, self.delay, self.last = client, delay, None

    def get(self, url: str):
        if self.last is not None:
            wait = self.delay - (time.monotonic() - self.last)
            if wait > 0:
                _sleep(wait)
        try:
            return self.client.get(url, timeout=PER_REQUEST_TIMEOUT)
        finally:
            self.last = time.monotonic()


def _discover_sitemap_urls(client: _Polite, base: str, robots_obj: Robots,
                           notes: list) -> tuple[list[str], int]:
    """Page URLs from the sitemap tree, plus how many sitemaps we actually read.

    Sitemap indexes nest, so the tree is walked to a bounded depth and inside
    its own time budget, and a sitemap is never treated as a page (that would
    spend the crawl budget on XML).
    """
    queue = [(sm, 0) for sm in (list(robots_obj.sitemaps) or [urljoin(base, "/sitemap.xml")])[:3]]
    pages: list[str] = []
    visited: set[str] = set()
    fetched = 0
    budget_end = time.monotonic() + SITEMAP_BUDGET_S

    while queue and fetched < MAX_SITEMAPS_FETCHED:
        if time.monotonic() >= budget_end:
            notes.append(f"sitemap walk stopped after its {SITEMAP_BUDGET_S}s budget with "
                         f"{len(queue)} sitemap(s) unread; page discovery continues from links")
            break
        sm, depth = queue.pop(0)
        if sm in visited or depth >= MAX_SITEMAP_DEPTH:
            continue
        visited.add(sm)
        # "Respect robots.txt" covers sitemap fetches too.
        if not robots_obj.allowed(USER_AGENT, sm):
            notes.append(f"sitemap not fetched (robots.txt disallows it for our UA): {sm}")
            continue
        try:
            r = client.get(sm)
            if r.status_code != 200:
                continue
            # Count only sitemaps we actually read: a 404 on /sitemap.xml is
            # evidence there is NO sitemap, which is exactly what A6 reports.
            fetched += 1
            locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)
            # Scan the whole document for the index marker, not just the head:
            # some generators emit a long XSL stylesheet declaration first, which
            # pushed <sitemapindex> past a head-only window and let child sitemap
            # URLs through as though they were pages.
            is_index = "<sitemapindex" in r.text.lower()
            for loc in locs:
                if is_index or _is_sitemap_url(loc):
                    queue.append((loc, depth + 1))
                else:
                    pages.append(loc)
        except _HTTP_ERROR as exc:
            notes.append(f"sitemap fetch failed for {sm}: {type(exc).__name__}")

    # Deterministic: preserve sitemap order, dedupe, cap. A sitemap is never a
    # page candidate, whatever level it was reached from.
    seen, ordered = set(), []
    for u in pages:
        n = normalise(u)
        if n in seen or _is_sitemap_url(n):
            continue
        seen.add(n)
        ordered.append(n)
    return ordered[:200], fetched


def build(start_url: str, max_pages: int = DEFAULT_MAX_PAGES,
          deadline_s: float = DEFAULT_DEADLINE_S) -> Bundle:
    t0 = time.monotonic()
    if not start_url.startswith(("http://", "https://")):
        start_url = "https://" + start_url
    base = normalise(start_url)
    host = urlparse(base).netloc
    notes: list[str] = []

    global _HTTP_ERROR
    httpx = _httpx()
    _HTTP_ERROR = httpx.HTTPError

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    raw_client = httpx.Client(headers=headers, follow_redirects=True,
                              timeout=PER_REQUEST_TIMEOUT, verify=True)
    client = _Polite(raw_client)

    # ---- robots.txt ---------------------------------------------------
    robots_url = urljoin(base, "/robots.txt")
    try:
        rr = client.get(robots_url)
        robots_obj = Robots(rr.text if rr.status_code == 200 else "",
                            status=rr.status_code, reachable=True)
        robots_present = rr.status_code == 200
    except _HTTP_ERROR as exc:
        robots_obj = Robots("", status=0, reachable=False)
        robots_present = False
        notes.append(f"robots.txt unreachable: {type(exc).__name__}")

    sitemap_urls, sitemaps_fetched = _discover_sitemap_urls(client, base, robots_obj, notes)

    # ---- llms.txt probe (one GET, robots-checked like any other URL) ----
    llms_url = urljoin(base, "/llms.txt")
    llms = {"url": llms_url, "present": False, "status": None}
    if robots_obj.allowed(USER_AGENT, llms_url):
        try:
            lr = client.get(llms_url)
            ctype = lr.headers.get("content-type", "")
            llms["status"] = lr.status_code
            # Many hosts answer 200 with an HTML 404 page; require text/plain-ish.
            llms["present"] = lr.status_code == 200 and "html" not in ctype and bool(lr.text.strip())
        except _HTTP_ERROR as exc:
            notes.append(f"llms.txt probe failed: {type(exc).__name__}")
    ai_agents_named = sorted({
        a for g in robots_obj.groups for a in g.agents
        if classify_agent(a) in ("retrieval", "training", "ambiguous")
    }, key=str.lower)

    # ---- crawl-delay policy -------------------------------------------
    declared_delay = robots_obj.crawl_delay(USER_AGENT) or 0.0
    delay = min(max(declared_delay, MIN_POLITE_DELAY), MAX_HONOURED_CRAWL_DELAY)
    client.delay = delay
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
        if _same_host(urlparse(u).netloc, host) and u not in seen and not _ASSET_URL.search(urlparse(u).path):
            seen.add(u)
            frontier.append(u)

    pages: list[Page] = []
    anchor_text: dict[str, str] = {}
    attempted = 0
    blocked_by_robots = 0
    consecutive_503 = 0

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
            r = client.get(url)
            body = r.text[:MAX_BYTES] if "html" in r.headers.get("content-type", "") else ""
            challenge = bot_challenge(body)
            if challenge:
                body = ""                      # the interstitial is not the site
            title_m = _TITLE_TAG.search(body) if body else None
            page = Page(
                url=url,
                final_url=str(r.url),
                status=r.status_code,
                role=infer_role(url, urlparse(url).path in ("", "/"),
                                title=unescape(title_m.group(1)) if title_m else "",
                                anchor=anchor_text.get(url, "")),
                headers={k.lower(): v for k, v in r.headers.items()},
                html=body,
                elapsed_ms=int(r.elapsed.total_seconds() * 1000),
                redirect_chain=[str(h.url) for h in r.history],
                derived=derive(body) if body else derive(""),
                error=f"bot_challenge:{challenge}" if challenge else None,
            )
        except _HTTP_ERROR as exc:
            page = Page(url=url, final_url=url, status=0,
                        role=infer_role(url, urlparse(url).path in ("", "/")),
                        headers={}, html="", elapsed_ms=0, error=type(exc).__name__,
                        derived=derive(""))
        pages.append(page)

        if page.error and page.error.startswith("bot_challenge:"):
            notes.append(f"server returned a bot-challenge page ({page.error.split(':', 1)[1]}) at "
                         f"{url}; crawl stopped, as further requests would meet the same wall")
            break

        # 429 is explicit: stop at once. A single 503 on an inner page may be one
        # bad backend, so the crawl continues; on the start URL or twice in a
        # row it is the site shedding load, and we add none.
        consecutive_503 = consecutive_503 + 1 if page.status == 503 else 0
        if page.status == 429 or (page.status == 503 and (url == base or consecutive_503 >= 2)):
            notes.append(f"server answered HTTP {page.status} at {url} after {len(pages)} page "
                         f"request(s); crawl stopped so the audit adds no load to a site that is "
                         f"shedding it")
            break
        if page.status == 503:
            notes.append(f"HTTP 503 at {url}; continuing, a second consecutive 503 stops the crawl")

        # Expand frontier from the homepage only, lexicographically (deterministic).
        if len(pages) == 1 and page.html:
            same_host, labels = homepage_links(page.html, base)
            anchor_text.update(labels)
            frontier = prioritise(frontier, same_host, labels)
            seen.update(frontier)
            for l in same_host:
                if l not in seen:
                    seen.add(l)
                    frontier.append(l)

    raw_client.close()

    # ---- run status ----------------------------------------------------
    ok = [p for p in pages if 200 <= p.status < 300 and p.html]
    if not pages and blocked_by_robots:
        run_status = "blocked"
    elif not ok:
        run_status = "failed"
    elif len(pages) < min(max_pages, len(seen)) or any(p.error for p in pages):
        run_status = "partial"
    elif len(ok) < len(pages):
        # Fetched fine, but most of it was not readable HTML. Reporting that as
        # "complete" would let a one-page sample masquerade as a full crawl.
        run_status = "partial"
    else:
        run_status = "complete"

    sample_paths = sorted({urlparse(p.url).path or "/" for p in pages}) or ["/"]

    return Bundle(
        bundle_schema_version=BUNDLE_SCHEMA_VERSION,
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
            # Groups naming a token no real crawler answers to. Matching is exact
            # per RFC 9309, so these rules bind nothing at all.
            "unrecognised_agent_tokens": robots_obj.unrecognised_agent_tokens(),
            # How many sitemap documents we actually read. A6 asks whether a
            # sitemap EXISTS, which is not the same question as whether it
            # yielded page URLs we had budget to crawl.
            "sitemaps_fetched": sitemaps_fetched,
        },
        sitemap_urls=sitemap_urls[:50],
        pages=[asdict(p) for p in pages],
        notes=notes,
        probes={"llms_txt": llms, "ai_agents_named_in_robots": ai_agents_named},
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
