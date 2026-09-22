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


def extracted_text(html: str) -> str:
    """Approximate what a bot-grade readability extractor keeps."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(BOILERPLATE):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def payload_text(html: str) -> tuple[str, list[str]]:
    found, names = [], []
    for name, pattern in PAYLOAD_ISLANDS:
        for m in pattern.findall(html):
            found.append(m if isinstance(m, str) else " ".join(m))
            if name not in names:
                names.append(name)
    return " ".join(found), names


def jsonld_blocks(soup: BeautifulSoup) -> list:
    out = []
    for tag in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        try:
            data = json.loads(tag.string or "{}")
        except (json.JSONDecodeError, TypeError):
            out.append({"__malformed__": True})
            continue
        out.extend(data if isinstance(data, list) else [data])
    return out


def flatten(obj, acc=None):
    acc = acc if acc is not None else []
    if isinstance(obj, dict):
        for v in obj.values():
            flatten(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            flatten(v, acc)
    else:
        acc.append(str(obj))
    return acc


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


def run(b: dict) -> list[dict]:
    out: list[dict] = []
    pages = [p for p in b["pages"] if 200 <= p["status"] < 300 and p["html"]]
    if not pages:
        return out

    t3_hits, t2_hits, shells, malformed = [], [], [], []
    no_structured, unanchored_entity, no_anchor_ids = [], [], []
    low_quotability, contradictions, image_locked = [], [], []

    for p in pages:
        html = p["html"]
        soup = BeautifulSoup(html, "html.parser")
        prose = extracted_text(html)
        payload, island_names = payload_text(html)
        ld = jsonld_blocks(soup)
        ld_text = " ".join(flatten(ld))
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
        if any(d.get("__malformed__") for d in ld):
            malformed.append(p["url"])
        elif not ld and p["role"] in ("home", "product", "pricing", "about", "blog"):
            no_structured.append((p["url"], p["role"]))

        # ---- C2: markup vs visible text contradiction --------------------
        for block in ld:
            if block.get("__malformed__"):
                continue
            offers = block.get("offers")
            if isinstance(offers, dict) and "price" in offers:
                declared = str(offers["price"]).strip()
                currency = str(offers.get("priceCurrency", "")).strip()
                # Conservative: only fire on a single unambiguous declared price
                # whose digits appear nowhere in the visible prose. Sale-vs-list,
                # AggregateOffer, variants and locale formats are skipped.
                digits = re.sub(r"[^\d]", "", declared)
                if digits and len(digits) <= 7 and "AggregateOffer" not in str(block):
                    if not re.search(re.escape(digits[:len(digits)]), re.sub(r"[^\d]", "", prose)):
                        contradictions.append((p["url"], declared, currency))

        # ---- C3: entity anchoring (homepage only) ------------------------
        if p["role"] == "home":
            org = [d for d in ld if str(d.get("@type", "")).lower() in
                   ("organization", "corporation", "localbusiness", "onlinestore")]
            if not org or not any(o.get("sameAs") for o in org):
                unanchored_entity.append(p["url"])

        # ---- B5: facts locked in images ----------------------------------
        imgs = [i for i in soup.find_all("img")
                if not (i.get("alt") or "").strip()
                and not i.get("aria-hidden")
                and (i.get("width") is None or str(i.get("width")).rstrip("px").isdigit()
                     and int(str(i.get("width")).rstrip("px") or 0) > 150)]
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

    return out


if __name__ == "__main__":
    print(json.dumps(run(load_bundle()), indent=2, ensure_ascii=False))
