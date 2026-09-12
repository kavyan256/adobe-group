#!/usr/bin/env python3
"""Gates 2 and 3 - can a machine find, and correctly interpret, the specific fact?

Standalone: reads a site bundle, writes a findings array.

Each fact a page's role obligates it to carry is graded by the form it takes in
the raw response -- T0 prose, T1 JSON-LD, T2 only inside a script payload, T3
absent -- because assistant fetchers strip <script> before the model sees the
page. The tier model: references/extraction-tiers.md.
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

# ---- fact recognisers -------------------------------------------------------
# A price is a number with a currency marker on EITHER side: "$49", "49,00 €",
# "CHF 49", "Rs. 499", "49 kr". Case-sensitive on purpose: "20 ft" is a length,
# not forints. Thousands may be separated by a (narrow) no-break space.
_CUR_SYMBOL = r"(?:US\$|A\$|C\$|NZ\$|S\$|HK\$|R\$|[$£€¥₹₩₽₺₪฿₫₱₦])"
_CUR_CODE = (r"(?:USD|EUR|GBP|INR|CAD|AUD|NZD|SGD|HKD|JPY|CNY|CHF|SEK|NOK|DKK|PLN|CZK|"
             r"HUF|BRL|MXN|ZAR|AED|SAR|KRW|RUB|TRY|ILS|THB|IDR|MYR|PHP|VND|NGN|"
             r"Rs\.?|kr\.?|zł|Kč)")
_AMOUNT = r"\d(?:[\d.,\u00a0\u202f]*\d)?"
PRICE = re.compile(
    rf"(?:{_CUR_SYMBOL}|(?<![A-Za-z]){_CUR_CODE})\s?(?P<a>{_AMOUNT})"
    rf"|(?P<b>{_AMOUNT})\s?(?:{_CUR_SYMBOL}|{_CUR_CODE}(?![A-Za-z]))")

_PHONE_CANDIDATE = re.compile(r"(?<![\w/.-])\+?\(?\d[\d\s().\-\u00a0]{5,20}\d(?![\w/-])")
_DATE_LIKE = re.compile(r"^\s*(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s*$")
# The lookbehind rejects fediverse handles: "@django@fosstodon.org" is a Mastodon
# account, not an address anyone can email.
EMAIL = re.compile(r"(?<![\w@.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?!png\b|jpe?g\b|svg\b|webp\b|gif\b)"
                   r"[A-Za-z]{2,}\b")


def _as_number(text: str) -> float | None:
    """A displayed amount as a number, whichever grouping convention it uses.

    "1,299.00" and "1.299,00" are both 1299.0; "49,00" is 49.0; "1.299" and
    "1,299" (one thousands group) are 1299.0; "1,29,999" (Indian lakh grouping)
    is 129999.0. Kept byte-identical with the copy in
    freshness-corroboration-audit/scripts/check_freshness.py, so a JSON-LD
    price and a visible price are read the same way by both skills.
    """
    s = re.sub(r"[\s\u00a0\u202f]", "", str(text))
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


def _is_phone(candidate: str) -> bool:
    """A phone number, not a year pair, a date, a price or a bare digit run."""
    c = candidate.strip()
    digits = re.sub(r"\D", "", c)
    if not 7 <= len(digits) <= 15 or "," in c or _DATE_LIKE.match(c):
        return False
    groups = re.findall(r"\d+", c)
    if all(len(g) == 4 and g[:2] in ("19", "20") for g in groups):
        return False                      # "© 2025 2026", "2019-2024"
    if c.startswith("+") or "(" in c:
        return True
    if len(groups) == 2 and not re.search(r"\d[-.]\d", c):
        return False                      # "1200 546": two numbers side by side
    return len(groups) >= 2 and not all(len(g) == 4 for g in groups)


def _find_price(text: str) -> str | None:
    m = PRICE.search(text)
    return m.group(0) if m else None


def _find_phone(text: str) -> str | None:
    for m in _PHONE_CANDIDATE.finditer(text):
        if _is_phone(m.group(0)):
            return m.group(0).strip()
    return None


def _find_email(text: str) -> str | None:
    m = EMAIL.search(text)
    return m.group(0) if m else None


FACT_FINDERS = {"price": _find_price, "phone": _find_phone, "email": _find_email}
# A grep a non-expert can paste to confirm a T3 verdict.
GREP_HINT = {
    "price": r"grep -Eo '[$£€¥₹][ ]?[0-9]|[0-9][ ]?(€|EUR|USD|GBP|CHF|kr)'",
    "phone": r"grep -Eo 'tel:|\+?[0-9][0-9 ().-]{6,}[0-9]'",
    "email": r"grep -Eo 'mailto:|[[:alnum:]._%+-]+@[[:alnum:].-]+\.[a-z]{2,}'",
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
    return " | ".join(found), names


# The brand can declare itself as Organization or any of its subtypes
# (NewsMediaOrganization, Corporation), as LocalBusiness or one of ITS many
# subtypes (Restaurant, Dentist, Store ...), so a suffix test plus the common
# leaf types stands in for the whole schema.org tree.
_ORG_SUFFIXES = ("organization", "organisation", "business", "store", "corporation",
                 "restaurant", "company", "agency", "shop")
_ORG_LEAF_TYPES = {"dentist", "physician", "attorney", "hotel", "bakery", "cafeorcoffeeshop",
                   "barorpub", "brand", "hospital", "pharmacy", "school", "collegeoruniversity",
                   "library", "museum", "gym", "healthclub", "realestateagent", "autodealer",
                   "autorepair", "medicalclinic", "lodgingbusiness", "foodestablishment",
                   "professionalservice", "financialservice", "bank", "insuranceagency",
                   "travelagency", "hairsalon", "beautysalon", "daycare", "veterinarycare",
                   "hardwarestore", "clothingstore", "electronicsstore", "grocerystore",
                   "newsmediaorganization", "educationalorganization", "governmentorganization",
                   "sportsorganization", "medicalorganization", "ngo", "airline"}


def _is_org_like(types: list[str]) -> bool:
    return any(t.endswith(_ORG_SUFFIXES) or t in _ORG_LEAF_TYPES for t in types)


def _org_anchor(derived: dict) -> bool:
    """Does this page declare an organisation-like node WITH sameAs?"""
    return any(_is_org_like(n["types"]) and n["props"].get("sameAs")
               for n in derived["jsonld"]["nodes"])


def _price_tokens(prose: str) -> set:
    """Every price-SHAPED number in the visible text, as numbers.

    Only currency-marked numbers count. A bare "99" in prose is not a price and
    must not be able to satisfy a declared price of 99.
    """
    out = set()
    for m in PRICE.finditer(prose):
        value = _as_number(m.group("a") or m.group("b"))
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
    org = [n for n in ld_nodes if _is_org_like(n["types"])]
    for n in org:
        if isinstance(n["props"].get("name"), str) and n["props"]["name"].strip():
            out["Organization.name"] = n["props"]["name"].strip()
            break
    og = soup.find("meta", attrs={"property": re.compile("^og:site_name$", re.I)})
    if og and (og.get("content") or "").strip():
        out["og:site_name"] = og["content"].strip()
    return out


def tier_of(fact_type: str, prose: str, ld_text: str, meta_text: str,
            payload: str) -> str:
    find = FACT_FINDERS[fact_type]
    if find(prose):
        return "T0"
    if find(ld_text):
        return "T1"
    if find(meta_text) or find(payload):
        return "T2"
    return "T3"


INTERROGATIVE = re.compile(r"^\s*(what|who|why|how|when|where|which|can|do|does|is|are|will|should)\b"
                           r".*\?\s*$", re.I)
LEGAL_SUFFIX = re.compile(r"\b(inc|ltd|llc|l\.l\.c|gmbh|s\.a|sa|plc|co|corp|corporation|limited)\b\.?",
                          re.I)
TITLE_SPLIT = re.compile(r"\s[|\u2013\u2014\u00b7-]\s")

GENERIC_TITLES = {"home", "index", "untitled", "welcome", "new page", "document", "home page"}
SHARED_TITLE_MIN_PAGES = 3    # one title on this many pages is a template default

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
        for sent in set(_sentences(p["derived"]["text"]["extracted"])):
            counts[sent] = counts.get(sent, 0) + 1
    threshold = max(2, int(len(pages) * FILLER_SHARE))
    return {s for s, n in counts.items() if n >= threshold}


def run(b: dict) -> list[dict]:
    out: list[dict] = []
    pages = [p for p in b["pages"] if 200 <= p["status"] < 300 and p["html"]]
    if not pages:
        return out

    t3_hits, t2_hits, shells, malformed = [], [], [], []
    no_structured, no_product_markup = [], []
    low_quotability, contradictions = [], []
    filler_heavy, faq_unmarked, name_conflict = [], [], []
    titles: dict[str, list[str]] = {}
    title_problems: list[tuple[str, str]] = []

    common = site_common_sentences(pages)
    # C3 looks at every crawled page: the Organization block often lives on
    # /about or in a site-wide footer graph rather than on the homepage.
    anchored = any(_org_anchor(p["derived"]) for p in pages)
    home = next((p["url"] for p in pages if p["role"] == "home"), pages[0]["url"])

    for p in pages:
        html = p["html"]
        soup = BeautifulSoup(html, "html.parser")
        d = p["derived"]
        prose = d["text"]["extracted"]
        payload, island_names = payload_text(html)
        ld_nodes = d["jsonld"]["nodes"]
        ld_text = d["jsonld"]["text"]
        # " | " keeps separate tags separate: joined with a space, og:image:width
        # 1200 and og:image:height 546 read as the phone number "1200 546".
        meta_text = " | ".join(
            (m.get("content") or "") for m in soup.find_all("meta"))

        # ---- B1: extraction tiering over obligated facts -----------------
        # An obligation group is satisfied by its BEST tier across alternatives:
        # an email at T0 discharges a contact page's duty even with no phone.
        for group in ROLE_OBLIGATIONS.get(p["role"], []):
            tiers = {ft: tier_of(ft, prose, ld_text, meta_text, payload)
                     for ft in group}
            # A visible tel:/mailto: link is a quotable contact route even when
            # its label reads "Call us" rather than the number itself.
            if "phone" in tiers and soup.find("a", href=re.compile(r"^\s*tel:", re.I)):
                tiers["phone"] = "T0"
            if "email" in tiers and soup.find("a", href=re.compile(r"^\s*mailto:", re.I)):
                tiers["email"] = "T0"
            best = min(tiers.values(), key=lambda t: ("T0", "T1", "T2", "T3").index(t))
            if best in ("T0", "T1"):
                continue                       # obligation met, nothing to report
            label = "/".join(group)
            if best == "T3":
                # A contact page built around a form is a deliberate choice, not a
                # missing fact: the visitor can act, but an assistant has nothing
                # to quote. Reported as a question, capped at low downstream.
                form_only = (p["role"] == "contact" and soup.find("form") is not None
                             and (soup.find("textarea") is not None
                                  or soup.find("input", attrs={"type": re.compile("^email$", re.I)})
                                  is not None))
                t3_hits.append((p["url"], label, p["role"], group[0], form_only))
            else:                              # T2: present, but only in a script blob
                ft = next(f for f, t in tiers.items() if t == "T2")
                sample = FACT_FINDERS[ft](payload) or FACT_FINDERS[ft](meta_text)
                t2_hits.append((p["url"], ft, sample or "?",
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
        elif p["role"] == "product" and "product" not in d["jsonld"]["types_present"]:
            # A product page is the one place structured data carries the fact
            # itself (Offer.price), so its absence is graded above the rest.
            no_product_markup.append(p["url"])
        elif not ld_nodes and p["role"] in ("home", "pricing", "about", "blog"):
            no_structured.append((p["url"], p["role"]))

        # ---- C7: <title> missing, generic, or shared across pages ---------
        title = " ".join(soup.title.get_text(" ", strip=True).split()) if soup.title else ""
        if not title:
            title_problems.append((p["url"], "no <title>" if soup.title is None else "empty <title>"))
        elif title.lower() in GENERIC_TITLES:
            title_problems.append((p["url"], f"generic title '{title}'"))
        else:
            titles.setdefault(title, []).append(p["url"])

        # ---- C2: markup vs visible text contradiction --------------------
        prose_prices = _price_tokens(prose)
        for node in ld_nodes:
            offers = node["props"].get("offers")
            if not isinstance(offers, dict) or "price" not in offers:
                continue
            declared = str(offers["price"]).strip()
            currency = str(offers.get("priceCurrency", "")).strip()
            # Conservative: only fire on a single unambiguous declared price that
            # matches NO currency-marked price on the page, compared as numbers
            # so a year or a phone number cannot satisfy it.
            value = _as_number(declared)
            if value is None or "aggregateoffer" in " ".join(_types_of_offer(offers)):
                continue
            # If the page shows no price at all, that is B1's finding, not this one.
            if prose_prices and value not in prose_prices:
                contradictions.append((p["url"], declared, currency))

        # ---- C5: question content with no Q&A markup -----------------------
        # An assistant lifting an answer wants a question paired with a
        # self-contained answer. A page that already asks the questions in its
        # headings is one markup block away from being quotable that way.
        # Articles are skipped: an interview's question headings are narrative,
        # not an FAQ.
        questions = [h.get_text(" ", strip=True) for h in soup.find_all(["h2", "h3"])
                     if INTERROGATIVE.match(h.get_text(" ", strip=True) or "")]
        if (p["role"] != "blog" and len(questions) >= 3
                and not ({"faqpage", "question"} & set(d["jsonld"]["types_present"]))):
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

        # ---- X1: quotability ---------------------------------------------
        paras = [t.get_text(" ", strip=True) for t in soup.find_all("p")]
        candidates = [t for t in paras if 25 <= len(t.split()) <= 90]
        if candidates:
            weak = [t for t in candidates if ANAPHORA.match(t.strip())]
            if len(weak) >= max(2, len(candidates) // 3):
                low_quotability.append((p["url"], len(weak), len(candidates)))

    total = len(pages)
    for title, urls in titles.items():
        if len(urls) >= SHARED_TITLE_MIN_PAGES:
            title_problems.extend((u, f"title '{title}' shared by {len(urls)} pages") for u in urls)

    # ================= emit =================================================
    if t3_hits:
        by_type: dict[str, list] = {}
        pattern_key: dict[str, str] = {}
        for url, label, role, pkey, form_only in t3_hits:
            by_type.setdefault((label, form_only), []).append((url, role))
            pattern_key[label] = pkey
        for (ft, form_only), items in sorted(by_type.items()):
            urls = [u for u, _ in items]
            pkey = pattern_key[ft]
            finding = {
                "check_id": "B1_fact_absent",
                "title": f"No {ft} found in the raw HTML of {len(items)} page(s) that should carry one",
                "evidence": (
                    f"{len(items)} page(s) whose URL/role commits them to state a {ft} contain no "
                    f"{ft}-shaped token anywhere in the raw response - not in visible text, "
                    f"JSON-LD, meta tags, or any hydration payload. Examples: "
                    f"{[f'{u} (role={r})' for u, r in items[:3]]}. "
                    f"Reproduce: curl -s '{urls[0]}' | {GREP_HINT[pkey]}"),
                "affected_urls": urls,
                "blast_radius": "template" if len(items) < total else "site_wide",
                "confidence": "deterministic",
            }
            if form_only:
                finding.update({
                    "status": "confirm_intent",
                    "intent_signals": [
                        "the page carries a contact form (a textarea or email field), so a "
                        "visitor can still get in touch",
                        "offering a form instead of a published phone number or address is a "
                        "common deliberate choice",
                        "the cost is that an assistant asked 'how do I contact them?' has "
                        "nothing to quote",
                    ],
                    "title": (f"Confirm intent: {len(items)} contact page(s) offer a form but no "
                              f"quotable {ft}"),
                    "suggested_action": {
                        "summary": "If you want assistants to answer 'how do I contact them', "
                                   "publish a phone number or email next to the form.",
                        "priority": "low", "effort": "low",
                        "how": ["Add the address as visible text, plus a mailto: or tel: link.",
                                "Mirror it in Organization/ContactPoint structured data.",
                                "If a form-only route is deliberate (spam, routing), no action "
                                "is needed."],
                        "verify": f"curl -s <url> | {GREP_HINT[pkey]} returns a match.",
                    },
                    "detail": {"fact_type": ft, "tier": "T3", "contact_form_present": True},
                })
                out.append(finding)
                continue
            finding.update({
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
            out.append(finding)

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
                    "Server-render the same value into visible prose, and also state it in "
                    "JSON-LD, which the indexing crawlers that build the search index "
                    "assistants query do read.",
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

    if no_product_markup:
        out.append({
            "check_id": "C1_product_markup_absent",
            "title": f"No Product structured data on {len(no_product_markup)} product page(s)",
            "evidence": (f"{len(no_product_markup)}/{total} crawled product pages carry no "
                         f"Product JSON-LD, so the price, availability and identity of the item "
                         f"are stated only in prose, if at all. Examples: {no_product_markup[:3]}. "
                         f"Structured data is read by the indexing crawlers that build the "
                         f"search index assistants query."),
            "affected_urls": no_product_markup,
            "blast_radius": "site_wide" if len(no_product_markup) == total else "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Add Product JSON-LD with an Offer to each product page.",
                "priority": "medium", "effort": "medium",
                "how": ["Product -> name, description, sku, image, offers{price, priceCurrency, "
                        "availability}.",
                        "Render the same price in the visible text, from the same source of truth."],
                "verify": "A schema.org validator reports a Product with an Offer and no errors.",
            },
        })

    if no_structured:
        out.append({
            "check_id": "C1_structured_data_absent",
            "title": f"No structured data on {len(no_structured)} significant page(s)",
            "evidence": (f"{len(no_structured)}/{total} crawled pages of type "
                         f"{sorted({r for _, r in no_structured})} contain no JSON-LD. Structured "
                         f"data is read by the indexing crawlers that build the search index "
                         f"assistants query, and it states a fact with a type attached. "
                         f"Examples: {[u for u, _ in no_structured[:3]]}"),
            "affected_urls": [u for u, _ in no_structured],
            "blast_radius": "site_wide" if len(no_structured) == total else "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Add schema.org JSON-LD appropriate to each page type.",
                "priority": "low", "effort": "medium",
                "how": ["Homepage/About -> Organization with name, url, logo, description, sameAs.",
                        "Pricing -> Product or Service per tier, or an Offer list.",
                        "Article/blog -> Article with headline, datePublished, dateModified, author."],
                "verify": "A schema.org validator reports a detected item type with no errors.",
            },
        })

    if title_problems:
        out.append({
            "check_id": "C7_title_problem",
            "title": f"Missing, generic or duplicated <title> on {len(title_problems)} page(s)",
            "evidence": ("; ".join(f"{u}: {why}" for u, why in title_problems[:4])
                         + ". The title is the first thing an index stores and the label an "
                           "assistant shows next to a citation; a blank or shared one gives "
                           "the page no identity of its own."),
            "affected_urls": [u for u, _ in title_problems],
            "blast_radius": "site_wide" if len(title_problems) >= total else "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Give every page a unique title that names its subject.",
                "priority": "medium", "effort": "low",
                "how": ["Template the title as '<page subject> | <brand>' so no two pages share one.",
                        "Never ship the CMS default ('Home', 'Untitled', 'Document')."],
                "verify": "curl -s <url> | grep -o '<title>[^<]*' differs across pages and is "
                          "never empty.",
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
            "title": f"Questions are not paired with self-contained answers on {len(faq_unmarked)} page(s)",
            "evidence": (f"{sample_url} asks {len(sample_qs)} questions in its own headings, "
                         f"e.g. {sample_qs[:3]}, but nothing on the page pairs each question "
                         f"with a self-contained answer: no FAQPage or Question structured data. "
                         f"An assistant lifting an answer takes the question plus the answer "
                         f"as one unit, and here it has to guess where each answer ends."),
            "affected_urls": [u for u, _ in faq_unmarked],
            "blast_radius": "template",
            "confidence": "deterministic",
            "suggested_action": {
                "summary": "Pair each question heading with one self-contained answer, and say "
                           "so in FAQPage JSON-LD.",
                "priority": "low", "effort": "low",
                "how": ["Under each question heading, open with a one- or two-sentence answer "
                        "that stands on its own before any elaboration.",
                        "Emit one Question node per heading you already have, with that answer "
                        "in acceptedAnswer -- do not write new content for this."],
                "verify": "Each question heading is followed by an answer that makes sense with "
                          "the rest of the page hidden, and the FAQPage block lists it.",
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

    # Fires only when NO crawled page anchors the brand with an organisation-like
    # node. A sameAs on an author's Person node does not anchor the brand; the
    # orchestrator's already_in_place entry applies the same organisation-only
    # rule, so the two can never contradict each other.
    if not anchored:
        out.append({
            "check_id": "C3_entity_unanchored",
            "title": "Brand identity is not anchored to any external profile",
            "evidence": (f"None of the {total} crawled page(s) declares Organization, LocalBusiness "
                         f"or similar structured data with sameAs links. Without sameAs, an "
                         f"assistant has nothing distinguishing this brand from others sharing the "
                         f"name, which is the standard cause of mistaken identity."),
            "affected_urls": [home],
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
                "priority": "low", "effort": "medium",
                "how": ["Assistants quote passages, not whole pages. A paragraph opening with "
                        "'This means...' or 'Our platform...' loses its subject when lifted out.",
                        "Name the subject explicitly in the first sentence of each key paragraph.",
                        "State the single most important fact as one self-contained sentence "
                        "directly under its heading."],
                "verify": "Read any key paragraph in isolation - the subject is unambiguous.",
            },
        })

    return out


if __name__ == "__main__":
    print(json.dumps(run(load_bundle()), indent=2, ensure_ascii=False))
