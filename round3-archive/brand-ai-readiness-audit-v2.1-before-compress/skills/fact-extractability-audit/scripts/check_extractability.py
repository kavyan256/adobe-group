#!/usr/bin/env python3
"""Gates 2 and 3 - can a machine find, and correctly interpret, the specific fact?

Standalone: reads a site bundle, writes findings. Standard library + BeautifulSoup.

THE MECHANISM THIS ENCODES
--------------------------
Assistant fetchers run a two-stage pipeline: raw bytes, then a boilerplate-
stripping text extractor, and only then does the model see anything. That
extractor discards <script>, <style>, nav and footer BY CONSTRUCTION. So a fact
carried in a hydration payload is present in the BYTES and absent from the TEXT.
Present-in-bytes is not present-to-the-assistant.

We therefore do not need a headless browser, and we do not diff raw against
rendered. We ask an absolute question instead:

    In what FORM does each expected fact exist in the raw response?

    T0  visible prose / heading      -> pass, directly quotable
    T1  JSON-LD / microdata          -> pass, machine-readable by design
    T2  ONLY inside a script payload -> medium; technically present, but no
                                        assistant reliably parses escape-chunked
                                        hydration blobs
    T3  absent from the bytes        -> high; genuinely invisible

Expected facts come from two independent sources so the check is not circular:
  1. DECLARED LITERALS - values the site asserts in JSON-LD / meta / payload.
     Catches "the fact exists in bytes but not in text."
  2. ROLE OBLIGATIONS  - derived from the URL slug and <title>, surfaces that are
     NOT under test. A page asserting "Pricing" is committing to contain a price.
     Catches "the fact does not exist at all."
"""
from __future__ import annotations

import json
import re
import sys

from bs4 import BeautifulSoup

BOILERPLATE = ["script", "style", "noscript", "nav", "header", "footer",
               "aside", "form", "svg", "template"]

PAYLOAD_ISLANDS = [
    ("__NEXT_DATA__",     re.compile(r'id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', re.S)),
    ("self.__next_f",     re.compile(r'self\.__next_f\.push\((.*?)\)</script>', re.S)),
    ("__NUXT__",          re.compile(r'window\.__NUXT__\s*=\s*(.*?)</script>', re.S)),
    ("__APOLLO_STATE__",  re.compile(r'__APOLLO_STATE__\s*=\s*(.*?)</script>', re.S)),
    ("__INITIAL_STATE__", re.compile(r'__INITIAL_STATE__\s*=\s*(.*?)</script>', re.S)),
    ("application/json",  re.compile(r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>', re.S)),
]

FACT_PATTERNS = {
    "price": re.compile(r'(?:[$£€¥₹]\s?\d[\d,.]*|\d[\d,.]*\s?(?:USD|EUR|GBP|INR|CAD|AUD))', re.I),
    "phone": re.compile(r'(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?\d{3}[\s.-]?\d{3,4}[\s.-]?\d{0,4}'),
    "email": re.compile(r'[\w.+-]+@[\w-]+\.[\w.]{2,}'),
}

# Page role -> the obligations that role implies.
#
# Each obligation is a GROUP of alternatives, satisfied if ANY member is present.
# A contact page that lists an email but no phone number has met its obligation;
# requiring both would fire on the large number of businesses that deliberately
# offer only one channel.
ROLE_OBLIGATIONS = {
    "pricing": [["price"]],
    "product": [["price"]],
    "contact": [["phone", "email"]],
}

ANAPHORA = re.compile(r'\b(this|these|those|it|they|our platform|our product|the above|'
                      r'as mentioned|as noted|as described above|the former|the latter)\b', re.I)


def load_bundle() -> dict:
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        return json.loads(open(sys.argv[1], encoding="utf-8").read())
    return json.loads(sys.stdin.read())


def payload_text(html: str) -> tuple[str, list[str]]:
    found, names = [], []
    for name, pattern in PAYLOAD_ISLANDS:
        for m in pattern.findall(html):
            found.append(m if isinstance(m, str) else " ".join(m))
            if name not in names:
                names.append(name)
    return " ".join(found), names


def derived_of(page: dict) -> dict | None:
    """Normalised JSON-LD + text, computed once by the crawl layer.

    v2.0 parsed JSON-LD independently inside each skill and the skills disagreed
    with one another inside a single report. There is now exactly one parse, in
    bundle.py::derive, and every skill reads its result. A bundle predating that
    schema is reported as a skipped check, never silently re-parsed here -- that
    would recreate the divergence this replaced.
    """
    d = page.get("derived")
    return d if isinstance(d, dict) and "jsonld" in d else None


def nodes_of_type(derived: dict, *types: str) -> list[dict]:
    wanted = set(types)
    return [n for n in derived["jsonld"]["nodes"] if wanted & set(n["types"])]


_PRICE_TOKEN = re.compile(r"[$\u00a3\u20ac\u00a5\u20b9]\s?(\d[\d,]*(?:\.\d{1,2})?)"
                          r"|\b(?:USD|EUR|GBP|INR|CAD|AUD)\s?(\d[\d,]*(?:\.\d{1,2})?)")


def _as_number(text: str) -> float | None:
    try:
        return round(float(str(text).replace(",", "").strip()), 2)
    except (TypeError, ValueError):
        return None


def _price_tokens(prose: str) -> set:
    """Every price-SHAPED number in the visible text, as numbers.

    Only currency-marked numbers count. A bare "99" in prose is not a price and
    must not be able to satisfy a declared price of 99.
    """
    out = set()
    for m in _PRICE_TOKEN.finditer(prose):
        value = _as_number(m.group(1) or m.group(2))
        if value is not None:
            out.add(value)
    return out


def _types_of_offer(offers: dict) -> list[str]:
    raw = offers.get("@type")
    items = raw if isinstance(raw, list) else [raw]
    return [str(t).rsplit("/", 1)[-1].lower() for t in items if isinstance(t, str)]


def _brand_tokens(name: str) -> set:
    """A comparable form of a brand name: case, punctuation and legal suffix removed."""
    cleaned = LEGAL_SUFFIX.sub(" ", (name or "").lower())
    return {t for t in re.findall(r"[a-z0-9]{2,}", cleaned)}


def _name_surfaces(soup, ld_nodes: list) -> dict:
    """The places a page EXPLICITLY declares who it is.

    Only `Organization.name` and `og:site_name` count. The <title> is
    deliberately excluded: "Acme Robotics | Pricing" and "Pricing | Acme
    Robotics" are both normal, so there is no reliable way to tell the brand
    segment from the page segment, and guessing produced a false positive on
    every well-formed site we tested. The title is used below only to say which
    of two conflicting names the page itself corroborates.
    """
    out = {}
    org = [n for n in ld_nodes if {"organization", "corporation", "localbusiness",
                                   "onlinestore"} & set(n["types"])]
    for n in org:
        if isinstance(n["props"].get("name"), str) and n["props"]["name"].strip():
            out["Organization.name"] = n["props"]["name"].strip()
            break
    og = soup.find("meta", attrs={"property": re.compile("^og:site_name$", re.I)})
    if og and (og.get("content") or "").strip():
        out["og:site_name"] = og["content"].strip()
    return out


def _content_image(img) -> bool:
    """Is this an image a reader would expect to carry a fact?

    Two rules, both learned from false positives:

    * ``alt=""`` is a deliberate, correct declaration that an image is
      decorative. It is never a defect. Only a MISSING alt attribute is.
      (v2.0 counted ``alt=""`` here while the engagement skill recommended it.)
    * "No width attribute" is not evidence of size. Modern sites size images in
      CSS and almost never set the attribute, so treating absence as "large"
      made this check fire on every icon on the page. An image counts as
      substantial only if it declares a large width, or sits in a <figure>.
    """
    if img.get("alt") is not None:
        return False
    if img.get("aria-hidden") or img.get("role") == "presentation":
        return False
    width = str(img.get("width") or "").rstrip("px")
    if width.isdigit():
        return int(width) > 150
    return img.find_parent(["figure", "picture"]) is not None


def tier_of(fact_type: str, prose: str, ld_text: str, meta_text: str,
            payload: str) -> str:
    pat = FACT_PATTERNS[fact_type]
    if pat.search(prose):
        return "T0"
    if pat.search(ld_text):
        return "T1"
    if pat.search(meta_text) or pat.search(payload):
        return "T2"
    return "T3"


INTERROGATIVE = re.compile(r"^\s*(what|who|why|how|when|where|which|can|do|does|is|are|will|should)\b"
                           r".*\?\s*$", re.I)
LEGAL_SUFFIX = re.compile(r"\b(inc|ltd|llc|l\.l\.c|gmbh|s\.a|sa|plc|co|corp|corporation|limited)\b\.?",
                          re.I)
TITLE_SPLIT = re.compile(r"\s[|\u2013\u2014\u00b7-]\s")

SENTENCE = re.compile(r"[^.!?]{25,}?[.!?]")
FILLER_MIN_PAGES = 4          # below this, "appears on most pages" means nothing
FILLER_MIN_WORDS = 300        # short pages are legitimately mostly chrome
FILLER_SHARE = 0.60           # a sentence on >=60% of pages is site-common
FILLER_TRIGGER = 0.45         # >45% of this page's extracted words are site-common


def _sentences(text: str) -> list[str]:
    return [" ".join(m.group(0).split()).lower() for m in SENTENCE.finditer(text)]


def site_common_sentences(pages: list) -> set:
    """Sentences that survive extraction on most pages, so say nothing about any.

    Language-agnostic on purpose: no stopword list, no lexicon. A sentence is
    filler here because it is repeated site-wide, not because of the words in it.
    """
    if len(pages) < FILLER_MIN_PAGES:
        return set()
    counts: dict[str, int] = {}
    for p in pages:
        for sent in set(_sentences(derived_of(p)["text"]["extracted"])):
            counts[sent] = counts.get(sent, 0) + 1
    threshold = max(2, int(len(pages) * FILLER_SHARE))
    return {s for s, n in counts.items() if n >= threshold}


def run(b: dict) -> tuple[list[dict], list[dict]]:
    out: list[dict] = []
    skipped: list[dict] = []
    pages = [p for p in b["pages"] if 200 <= p["status"] < 300 and p["html"]]
    if not pages:
        return out, skipped

    t3_hits, t2_hits, shells, malformed = [], [], [], []
    no_structured, unanchored_entity, no_anchor_ids = [], [], []
    low_quotability, contradictions, image_locked = [], [], []
    filler_heavy, faq_unmarked, name_conflict = [], [], []

    if any(derived_of(p) is None for p in pages):
        skipped.append({
            "check": "fact-extractability-audit_structured_data",
            "reason": "this bundle predates bundle_schema_version 2, so it carries no "
                      "normalised JSON-LD or text. Re-crawl with this version: "
                      "python3 skills/audit-orchestrator/scripts/bundle.py <url> out.json",
            "impact": "Structured-data and text-extraction checks (B1/B5/C1/C2/C3/X1/X2) "
                      "did not run. Nothing was inferred in their place.",
        })
        return out, skipped

    common = site_common_sentences(pages)

    for p in pages:
        html = p["html"]
        soup = BeautifulSoup(html, "html.parser")
        d = derived_of(p)
        prose = d["text"]["extracted"]
        payload, island_names = payload_text(html)
        ld_nodes = d["jsonld"]["nodes"]
        ld_text = d["jsonld"]["text"]
        meta_text = " ".join(
            (m.get("content") or "") for m in soup.find_all("meta"))

        # ---- B1: extraction tiering over obligated facts -----------------
        # An obligation group is satisfied by its BEST tier across alternatives:
        # an email at T0 discharges a contact page's duty even with no phone.
        for group in ROLE_OBLIGATIONS.get(p["role"], []):
            tiers = {ft: tier_of(ft, prose, ld_text, meta_text, payload)
                     for ft in group}
            best = min(tiers.values(), key=lambda t: ("T0", "T1", "T2", "T3").index(t))
            if best in ("T0", "T1"):
                continue                       # obligation met, nothing to report
            label = "/".join(group)
            if best == "T3":
                t3_hits.append((p["url"], label, p["role"], group[0]))
            else:                              # T2: present, but only in a script blob
                ft = next(f for f, t in tiers.items() if t == "T2")
                sample = (FACT_PATTERNS[ft].search(payload)
                          or FACT_PATTERNS[ft].search(meta_text))
                t2_hits.append((p["url"], ft,
                                sample.group(0) if sample else "?",
                                ", ".join(island_names) or "meta tags"))

        # ---- B4: empty shell (only where role gave us nothing) -----------
        body = soup.find("body")
        if body is not None and len(prose.split()) < 30:
            mounts = body.find_all(id=re.compile(r"^(root|app|__next|__nuxt)$"))
            if mounts:
                shells.append((p["url"], len(prose.split()), mounts[0].get("id")))

        # ---- C1: structured data ----------------------------------------
        # "Malformed" means one thing only: the block failed to parse as JSON.
        # An unknown @type or a missing property is not malformed.
        if d["jsonld"]["malformed_blocks"]:
            malformed.append(p["url"])
        elif not ld_nodes and p["role"] in ("home", "product", "pricing", "about", "blog"):
            no_structured.append((p["url"], p["role"]))

        # ---- C2: markup vs visible text contradiction --------------------
        prose_prices = _price_tokens(prose)
        for node in ld_nodes:
            offers = node["props"].get("offers")
            if not isinstance(offers, dict) or "price" not in offers:
                continue
            declared = str(offers["price"]).strip()
            currency = str(offers.get("priceCurrency", "")).strip()
            # Conservative: only fire on a single unambiguous declared price that
            # matches NO price shown on the page. Compared as numbers against
            # price-shaped tokens, not as a substring of a digit blob -- v2.0
            # compared "99" against every digit in the page, so a year or a
            # phone number silently satisfied it.
            value = _as_number(declared)
            if value is None or "aggregateoffer" in " ".join(_types_of_offer(offers)):
                continue
            # If the page shows no price at all, that is B1's finding, not this one.
            if prose_prices and value not in prose_prices:
                contradictions.append((p["url"], declared, currency))

        # ---- C3: entity anchoring (homepage only) ------------------------
        if p["role"] == "home":
            org = nodes_of_type(d, "organization", "corporation",
                                "localbusiness", "onlinestore")
            if not org or not any(o["props"].get("sameAs") for o in org):
                unanchored_entity.append(p["url"])

        # ---- B5: facts locked in images ----------------------------------
        # ---- C5: question content with no Q&A markup -----------------------
        # An assistant lifting an answer wants a question paired with a
        # self-contained answer. A page that already asks the questions in its
        # headings is one markup block away from being quotable that way.
        questions = [h.get_text(" ", strip=True) for h in soup.find_all(["h2", "h3"])
                     if INTERROGATIVE.match(h.get_text(" ", strip=True) or "")]
        if len(questions) >= 3 and not ({"faqpage", "question"}
                                        & set(d["jsonld"]["types_present"])):
            faq_unmarked.append((p["url"], questions))

        # ---- C6: the site states more than one name for itself -------------
        if p["role"] == "home":
            surfaces = _name_surfaces(soup, ld_nodes)
            if len(surfaces) == 2:
                (k1, v1), (k2, v2) = sorted(surfaces.items())
                t1, t2 = _brand_tokens(v1), _brand_tokens(v2)
                if t1 and t2 and not (t1 & t2):
                    # Which one does the page's own title back up? Useful
                    # evidence, and never itself the reason the check fires.
                    title_tokens = _brand_tokens(
                        soup.title.get_text(" ", strip=True) if soup.title else "")
                    corroborated = [k for k, t in ((k1, t1), (k2, t2))
                                    if t & title_tokens]
                    name_conflict.append((p["url"], surfaces, corroborated))

        # ---- B6: filler-heavy ---------------------------------------------
        if common and p["role"] != "home":
            words = len(prose.split())
            if words >= FILLER_MIN_WORDS:
                shared = sum(len(sent.split()) for sent in _sentences(prose)
                             if sent in common)
                if shared / words > FILLER_TRIGGER:
                    filler_heavy.append((p["url"], round(shared / words * 100)))

        imgs = [i for i in soup.find_all("img") if _content_image(i)]
        if len(imgs) >= 3:
            image_locked.append((p["url"], len(imgs)))

        # ---- X2: citation surface ----------------------------------------
        heads = soup.find_all(["h2", "h3"])
        if len(heads) >= 3 and sum(1 for h in heads if h.get("id")) == 0:
            no_anchor_ids.append((p["url"], len(heads)))

        # ---- X1: quotability ---------------------------------------------
        paras = [t.get_text(" ", strip=True) for t in soup.find_all("p")]
        candidates = [t for t in paras if 25 <= len(t.split()) <= 90]
        if candidates:
            weak = [t for t in candidates if ANAPHORA.match(t.strip())]
            if len(weak) >= max(2, len(candidates) // 3):
                low_quotability.append((p["url"], len(weak), len(candidates)))

    total = len(pages)

    # ================= emit =================================================
    if t3_hits:
        by_type: dict[str, list] = {}
        pattern_key: dict[str, str] = {}
        for url, label, role, pkey in t3_hits:
            by_type.setdefault(label, []).append((url, role))
            pattern_key[label] = pkey
        for ft, items in sorted(by_type.items()):
            urls = [u for u, _ in items]
            pkey = pattern_key[ft]
            out.append({
                "check_id": "B1_fact_absent",
                "title": f"No {ft} found in the raw HTML of {len(items)} page(s) that should carry one",
                "evidence": (
                    f"{len(items)} page(s) whose URL/role commits them to state a {ft} contain no "
                    f"{ft}-shaped token anywhere in the raw response - not in visible text, "
                    f"JSON-LD, meta tags, or any hydration payload. Examples: "
                    f"{[f'{u} (role={r})' for u, r in items[:3]]}. "
                    f"Reproduce: curl -s '{urls[0]}' | grep -Ec "
                    f"'{FACT_PATTERNS[pkey].pattern[:40]}'"),
                "affected_urls": urls,
                "blast_radius": "template" if len(items) < total else "site_wide",
                "confidence": "deterministic",
                "suggested_action": {
                    "summary": f"Render the {ft} into server-side HTML text on these pages.",
                    "priority": "high", "effort": "medium",
                    "how": [
                        f"Emit the {ft} as plain text in the server response, not only after "
                        f"client-side JavaScript runs.",
                        "If the value is loaded from an API at runtime, server-render a default "
                        "and hydrate over it, so the HTML is never empty of the fact.",
                        f"Additionally express it in structured data (Product/Offer for price, "
                        f"LocalBusiness/ContactPoint for phone).",
                    ],
                    "verify": f"curl -s <url> | grep -i '<{ft} value>' returns a match with "
                              f"JavaScript disabled.",
                },
                "detail": {
                    "fact_type": ft, "tier": "T3",
                    "measured_on": "raw HTTP response, no JavaScript executed",
                    "limit": ("If this value is fetched by client-side XHR after load, a human in a "
                              "browser sees it and a non-rendering retrieval agent does not. The "
                              "finding stands for the agent; verify with JavaScript disabled, not "
                              "by viewing the page in a browser."),
                },
            })

    if t2_hits:
        out.append({
            "check_id": "B1_fact_script_only",
            "title": f"Key facts exist only inside script payloads on {len(t2_hits)} page(s)",
            "evidence": "; ".join(
                f"{u}: {ft} '{val}' found only in {src}, absent from extracted text"
                for u, ft, val, src in t2_hits[:4]),
            "affected_urls": [u for u, _, _, _ in t2_hits],
            "blast_radius": "template" if len(t2_hits) < total else "site_wide",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Promote these facts from the hydration payload into server-rendered text.",
                "priority": "medium", "effort": "medium",
                "how": [
                    "The value is in the bytes, so a determined parser could reach it - but "
                    "boilerplate extractors strip <script> before the model sees the page, so in "
                    "practice it is invisible.",
                    "Server-render the same value into visible prose, or mirror it into JSON-LD, "
                    "which extractors do retain.",
                ],
                "verify": "The value appears in the output of a text-extraction tool "
                          "(e.g. `python -c \"import trafilatura,sys;print(trafilatura.extract(sys.stdin.read()))\"`).",
            },
            "detail": {"tier": "T2"},
        })

    if shells:
        out.append({
            "check_id": "B4_empty_shell",
            "title": f"{len(shells)} page(s) serve an essentially empty HTML shell",
            "evidence": "; ".join(f"{u}: {n} words of extractable text, mount element #{mid}"
                                  for u, n, mid in shells[:4]),
            "affected_urls": [u for u, _, _ in shells],
            "blast_radius": "site_wide" if len(shells) == total else "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Server-render the primary content of these pages.",
                "priority": "high", "effort": "high",
                "how": ["Adopt SSR/SSG for these routes so the first response contains the "
                        "main heading and body copy.",
                        "At minimum, server-render the title, the primary heading, and a "
                        "one-sentence description."],
                "verify": "curl -s <url> | wc -w shows substantive content with no JS executed.",
            },
            "detail": {
                "measured_on": "raw HTTP response, no JavaScript executed",
                "limit": ("The page may look complete in a browser once its script runs. That is "
                          "not what a non-rendering retrieval agent receives; the finding describes "
                          "the agent's view."),
            },
        })

    if malformed:
        out.append({
            "check_id": "C1_structured_data_invalid",
            "title": f"Malformed JSON-LD on {len(malformed)} page(s)",
            "evidence": f"application/ld+json blocks failed to parse as JSON on: {malformed[:4]}. "
                        f"Invalid markup is discarded entirely, so it provides no benefit.",
            "affected_urls": malformed,
            "blast_radius": "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Fix the JSON syntax in the structured-data blocks.",
                "priority": "high", "effort": "low",
                "how": ["Validate each block with a JSON parser and with Google's Rich Results Test.",
                        "Watch for unescaped quotes in templated values and trailing commas."],
                "verify": "python -c 'import json,sys;json.load(sys.stdin)' succeeds for each block.",
            },
        })

    if no_structured:
        out.append({
            "check_id": "C1_structured_data_absent",
            "title": f"No structured data on {len(no_structured)} significant page(s)",
            "evidence": (f"{len(no_structured)}/{total} crawled pages of type "
                         f"{sorted({r for _, r in no_structured})} contain no JSON-LD. Structured "
                         f"data survives text extraction, so it is the most reliable way to state "
                         f"a fact machine-readably. Examples: {[u for u, _ in no_structured[:3]]}"),
            "affected_urls": [u for u, _ in no_structured],
            "blast_radius": "site_wide" if len(no_structured) == total else "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Add schema.org JSON-LD appropriate to each page type.",
                "priority": "medium", "effort": "medium",
                "how": ["Homepage/About -> Organization with name, url, logo, description, sameAs.",
                        "Product -> Product with name, description, offers{price, priceCurrency, availability}.",
                        "Pricing -> Product or Service per tier, or an Offer list.",
                        "Article/blog -> Article with headline, datePublished, dateModified, author."],
                "verify": "Google Rich Results Test reports a detected item type with no errors.",
            },
        })

    if contradictions:
        out.append({
            "check_id": "C2_markup_text_contradiction",
            "title": f"Structured-data price not present in the visible text on {len(contradictions)} page(s)",
            "evidence": "; ".join(f"{u}: JSON-LD declares {c} {v} but those digits do not appear "
                                  f"in the page's extractable text"
                                  for u, v, c in contradictions[:3]),
            "affected_urls": [u for u, _, _ in contradictions],
            "blast_radius": "template",
            "confidence": "heuristic",
            "measurement_basis": "static_heuristic",
            "suggested_action": {
                "summary": "Make the marked-up price and the displayed price agree.",
                "priority": "high", "effort": "low",
                "how": ["Render the price from a single source of truth so markup and copy cannot drift.",
                        "If the page legitimately shows a sale price, express both with "
                        "priceSpecification rather than a bare price."],
                "verify": "The price string in JSON-LD appears verbatim in the rendered text.",
            },
        })

    if faq_unmarked:
        sample_url, sample_qs = faq_unmarked[0]
        out.append({
            "check_id": "C5_faq_content_unmarked",
            "title": f"Question-and-answer content is not marked up on {len(faq_unmarked)} page(s)",
            "evidence": (f"{sample_url} asks {len(sample_qs)} questions in its own headings, "
                         f"e.g. {sample_qs[:3]}, but the page carries no FAQPage or Question "
                         f"structured data. The content is already in the shape an assistant "
                         f"wants to quote; nothing tells it so."),
            "affected_urls": [u for u, _ in faq_unmarked],
            "blast_radius": "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Add FAQPage JSON-LD pairing each existing heading with its answer.",
                "priority": "medium", "effort": "low",
                "how": ["Emit one Question node per heading you already have, with the answer "
                        "text in acceptedAnswer -- do not write new content for this.",
                        "Keep each answer self-contained: an answer that depends on the "
                        "paragraph above it cannot be lifted on its own."],
                "verify": "Rich Results Test reports FAQPage with one Question per heading.",
            },
        })

    if name_conflict:
        url, surfaces, corroborated = name_conflict[0]
        rendered = "; ".join(f"{k} = {v!r}" for k, v in sorted(surfaces.items()))
        backing = (f" The page title corroborates {corroborated[0]}."
                   if len(corroborated) == 1 else "")
        out.append({
            "check_id": "C6_entity_name_conflict",
            "title": "The homepage states more than one name for the brand",
            "evidence": (f"{url} declares: {rendered}. These share no words in common after "
                         f"normalising case, punctuation and legal suffixes. A machine "
                         f"reconciling several names for one entity has no anchor, which is the "
                         f"standard route to mistaken identity where names collide."
                         + backing),
            "affected_urls": [u for u, _, _ in name_conflict],
            "blast_radius": "site_wide",
            "confidence": "heuristic",
            "measurement_basis": "static_heuristic",
            "suggested_action": {
                "summary": "Use one brand name, identically, across markup and metadata.",
                "priority": "medium", "effort": "low",
                "how": ["Pick the name you want assistants to use and set Organization.name, "
                        "og:site_name and the title suffix to that exact string.",
                        "If the legal entity name differs from the trading name, keep the "
                        "trading name in `name` and put the legal one in `legalName`, which is "
                        "what that property is for."],
                "verify": "Organization.name, og:site_name and the title suffix are the same "
                          "string on the homepage.",
            },
        })

    if filler_heavy:
        out.append({
            "check_id": "B6_filler_heavy",
            "title": f"Page content is mostly site-wide filler on {len(filler_heavy)} page(s)",
            "evidence": ("; ".join(f"{u}: {pct}% of the extractable text also appears on most "
                                   f"other pages" for u, pct in filler_heavy[:4])
                         + ". A summariser given this page has little that is actually about "
                           "this page to work with, so the specific claim gets dropped in "
                           "favour of the boilerplate."),
            "affected_urls": [u for u, _ in filler_heavy],
            "blast_radius": "template",
            "confidence": "deterministic",
            "measurement_basis": "static_heuristic",
            "suggested_action": {
                "summary": "Raise the share of each page that is unique to that page.",
                "priority": "low", "effort": "medium",
                "how": ["Move repeated legal, promotional or navigational copy out of the main "
                        "content area and into <footer>/<aside>, so extractors treat it as "
                        "chrome instead of substance.",
                        "Lead each page with two or three sentences that are true only of that "
                        "page -- that is what a summariser will lift."],
                "verify": "Two different pages, run through a readability extractor, no longer "
                          "share most of their sentences.",
            },
        })

    if unanchored_entity:
        out.append({
            "check_id": "C3_entity_unanchored",
            "title": "Brand identity is not anchored to any external profile",
            "evidence": ("The homepage declares no Organization structured data with sameAs links. "
                         "Without sameAs, an assistant has nothing distinguishing this brand from "
                         "others sharing the name, which is the standard cause of mistaken identity."),
            "affected_urls": unanchored_entity,
            "blast_radius": "site_wide",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Publish Organization JSON-LD with sameAs links to authoritative profiles.",
                "priority": "medium", "effort": "low",
                "how": ['Add Organization markup with "sameAs": [Wikidata, LinkedIn, Crunchbase, '
                        'and your primary social profiles].',
                        "Use the identical legal/brand name across title tags, markup and body copy."],
                "verify": "Rich Results Test shows Organization with a populated sameAs array.",
            },
        })

    if image_locked:
        out.append({
            "check_id": "B5_fact_locked_in_image",
            "title": f"Substantial imagery without alt text on {len(image_locked)} page(s)",
            "evidence": "; ".join(f"{u}: {n} sizeable images with empty alt"
                                  for u, n in image_locked[:4]),
            "affected_urls": [u for u, _ in image_locked],
            "blast_radius": "template",
            "confidence": "heuristic",
            "measurement_basis": "static_heuristic",
            "suggested_action": {
                "summary": "Describe content images in alt text, and never leave a fact image-only.",
                "priority": "medium", "effort": "low",
                "how": ["Write descriptive alt text for every content image.",
                        "If a specification table, price or contact detail exists only inside an "
                        "image, restate it as text."],
                "verify": "Every content <img> has a non-empty alt attribute.",
            },
        })

    if low_quotability:
        out.append({
            "check_id": "X1_low_quotability",
            "title": f"Passages are hard to quote standalone on {len(low_quotability)} page(s)",
            "evidence": "; ".join(
                f"{u}: {w}/{c} candidate passages open with an unresolved reference"
                for u, w, c in low_quotability[:4]),
            "affected_urls": [u for u, _, _ in low_quotability],
            "blast_radius": "template",
            "confidence": "heuristic",
            "measurement_basis": "static_heuristic",
            "suggested_action": {
                "summary": "Rewrite key passages so each stands alone as a citable claim.",
                "priority": "medium", "effort": "medium",
                "how": ["Assistants quote passages, not whole pages. A paragraph opening with "
                        "'This means...' or 'Our platform...' loses its subject when lifted out.",
                        "Name the subject explicitly in the first sentence of each key paragraph.",
                        "State the single most important fact as one self-contained sentence "
                        "directly under its heading."],
                "verify": "Read any key paragraph in isolation - the subject is unambiguous.",
            },
        })

    if no_anchor_ids:
        out.append({
            "check_id": "X2_no_citation_anchor",
            "title": f"Headings lack stable anchors on {len(no_anchor_ids)} page(s)",
            "evidence": "; ".join(f"{u}: {n} section headings, none with an id attribute"
                                  for u, n in no_anchor_ids[:4]),
            "affected_urls": [u for u, _ in no_anchor_ids],
            "blast_radius": "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Give every section heading a stable id so answers can deep-link to it.",
                "priority": "low", "effort": "low",
                "how": ['Emit <h2 id="slug"> for each section and keep the slugs stable across '
                        "releases.",
                        "This lets an assistant cite a specific section rather than the page as a "
                        "whole, which raises the chance your page is the one linked."],
                "verify": "Each h2/h3 has an id, and <url>#<id> scrolls to that section.",
            },
        })

    return out, skipped


if __name__ == "__main__":
    _findings, _skipped = run(load_bundle())
    print(json.dumps({"findings": _findings, "checks_skipped": _skipped},
                     indent=2, ensure_ascii=False))
