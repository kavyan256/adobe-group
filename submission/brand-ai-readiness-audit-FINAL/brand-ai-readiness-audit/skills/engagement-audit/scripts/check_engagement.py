#!/usr/bin/env python3
"""On-site engagement risk factors, measured statically.

Standalone: reads a site bundle, writes {findings, checks_skipped}.

Every finding but E11 is static_heuristic, so capped at medium: these are
structural risk factors inferred from markup, never observed behaviour. E11
(no viewport meta at all) is a plain fact about the markup and is the one
deterministic check here. What is deliberately not checked (bounce rate,
consent banners, Core Web Vitals, contrast, action verbs), and why:
references/engagement-checks.md.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse
import sys

from bs4 import BeautifulSoup

VAGUE_LINKS = {"click here", "here", "read more", "more", "learn more", "this",
               "link", "continue", "details", "find out more"}
STOPWORDS = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with",
             "your", "our", "we", "you", "is", "are", "be", "by", "at", "from",
             "that", "this", "it", "as", "home", "welcome"}
# A control carrying any of these attribute prefixes has its name bound by a
# JS framework (Vue, Alpine, Angular, Knockout) and is assumed named at runtime.
FRAMEWORK_ATTR_PREFIXES = (":", "v-", "x-", "ng-", "@", "[", "data-bind")
# Form actions or field names/ids that mark a conversion form (E1_form_friction).
CONVERSION_WORDS = ("contact", "demo", "quote", "signup", "sign-up", "register",
                    "checkout", "order", "apply")
NON_FIELD_TYPES = ("hidden", "submit", "button", "image", "reset")

SKIPPED = [{
    "check": "E_colour_contrast",
    "reason": "Not assessed: colour contrast (WCAG 1.4.3). Reason: contrast ratios need "
              "computed styles, which need a browser; this marketplace runs without one to "
              "stay portable and deterministic.",
    "impact": "How to check it yourself: run axe DevTools or Lighthouse on the top 3 "
              "page templates and read the contrast section.",
}, {
    "check": "E_core_web_vitals",
    "reason": "Not assessed: Core Web Vitals (LCP, CLS, INP). Reason: these are field "
              "metrics at the 75th percentile; a single synthetic fetch is not a measurement "
              "and INP cannot be measured synthetically at all.",
    "impact": "How to check it yourself: open Google Search Console's Core Web Vitals "
              "report, which uses real-user data, or run Lighthouse for lab LCP/CLS.",
}, {
    "check": "E_behaviour_metrics",
    "reason": "Not assessed: behaviour metrics (bounce rate, dwell time, scroll depth, "
              "conversion rate). Reason: they are observed, not inferred from markup, and a "
              "short visit from an AI answer is often a success - the visitor came to verify "
              "one fact and did.",
    "impact": "How to check it yourself: in your analytics, segment sessions by referrer "
              "(chatgpt.com, perplexity.ai, claude.ai) and compare their conversion rate, "
              "not their bounce rate, with search traffic.",
}, {
    "check": "E_rendered_experience",
    "reason": "Not assessed: the rendered experience (overlay and cookie-banner timing, tap "
              "target size, focus visibility, layout at phone width). Reason: all of it "
              "depends on CSS and JavaScript executing, which needs a browser.",
    "impact": "How to check it yourself: run Lighthouse and axe on the top 3 templates at "
              "phone width, then tab through each page once to confirm focus is visible.",
}, {
    "check": "E_copy_quality",
    "reason": "Not assessed: copy quality, persuasion and jargon. Reason: subjective; no "
              "static threshold separates plain language from marketing copy across "
              "industries and languages without a high false-positive rate.",
    "impact": "How to check it yourself: read the first paragraph of the homepage and one "
              "product page aloud to someone outside the company and ask what the site "
              "offers and for whom.",
}, {
    "check": "E_authenticated_flows",
    "reason": "Not assessed: anything behind a login, checkout step or account area. "
              "Reason: the audit is read-only and never authenticates, submits a form or "
              "creates an account.",
    "impact": "How to check it yourself: walk the signup, checkout or booking flow on a "
              "phone with a test account and count the required steps and fields.",
}]


def load_bundle() -> dict:
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        return json.loads(open(sys.argv[1], encoding="utf-8").read())
    return json.loads(sys.stdin.read())


def framework_bound(el) -> bool:
    return any(k.startswith(FRAMEWORK_ATTR_PREFIXES) for k in el.attrs)


def labelledby_text(el, soup) -> str:
    ids = (el.get("aria-labelledby") or "").split()
    parts = []
    for ref in ids:
        target = soup.find(id=ref)
        if target is not None:
            parts.append(target.get_text(" ", strip=True))
    return " ".join(p for p in parts if p).strip()


def accessible_name(el, soup) -> str:
    for attr in ("aria-label", "title"):
        if (el.get(attr) or "").strip():
            return el[attr].strip()
    if el.get("aria-labelledby"):
        text = labelledby_text(el, soup)
        if text:
            return text
    if el.name == "input" and (el.get("value") or "").strip():
        return el["value"].strip()
    img = el.find("img")
    if img is not None and (img.get("alt") or "").strip():
        return img["alt"].strip()
    svg_title = el.find("title")
    if svg_title is not None and svg_title.get_text(" ", strip=True):
        return svg_title.get_text(" ", strip=True)
    # An icon child labelled for assistive tech names its parent link too:
    # <a href=...><svg aria-label="Facebook"></svg></a> (USWDS, most icon sets).
    labelled_child = el.find(attrs={"aria-label": True})
    if labelled_child is not None and (labelled_child.get("aria-label") or "").strip():
        return labelled_child["aria-label"].strip()
    return el.get_text(" ", strip=True)


def is_tracking_pixel(img) -> bool:
    for attr in ("width", "height"):
        try:
            if float(str(img.get(attr, "")).rstrip("px") or "9") <= 2:
                return True
        except ValueError:
            pass
    src = (img.get("src") or "").lower()
    return any(w in src for w in ("pixel", "beacon", "track"))


def routes_onward(a, page_url: str) -> bool:
    """A link is a route onward only if it resolves to a different page on the same host."""
    href = (a.get("href") or "").strip()
    if not href or href.startswith("#") or href.lower().startswith("javascript:"):
        return False
    target = urljoin(page_url, href)
    if urlparse(target).netloc != urlparse(page_url).netloc:
        return False
    return target.split("#")[0].rstrip("/") != page_url.split("#")[0].rstrip("/")


def form_fields(form) -> list:
    return [f for f in form.find_all(["input", "select", "textarea"])
            if (f.get("type") or "text").lower() not in NON_FIELD_TYPES]


def is_conversion_form(form, fields) -> bool:
    hay = " ".join([form.get("action") or "", form.get("id") or "", form.get("name") or ""]
                   + [f.get("name") or "" for f in fields] + [f.get("id") or "" for f in fields]).lower()
    return any(w in hay for w in CONVERSION_WORDS)


def label_state(f, soup) -> str:
    """'labelled', 'placeholder-only' or 'unlabelled'."""
    fid = f.get("id")
    if (f.get("aria-label") or "").strip() or (f.get("title") or "").strip() \
            or labelledby_text(f, soup) \
            or (fid and soup.find("label", attrs={"for": fid})) \
            or f.find_parent("label"):
        return "labelled"
    return "placeholder-only" if (f.get("placeholder") or "").strip() else "unlabelled"


def _zoom_suppressed(content: str) -> str:
    """Return why this viewport blocks zoom, or "" if it does not.

    Parse the directives rather than substring-matching them: "maximum-scale=10"
    contains the text "maximum-scale=1" but permits 10x zoom, and "user-scalable=0"
    disables zoom without containing the word "no". WCAG 1.4.4 asks for 200%,
    so a maximum-scale below 2 is the real threshold.
    """
    directives = {}
    for part in content.split(","):
        k, _, v = part.partition("=")
        if k.strip():
            directives[k.strip().lower()] = v.strip().lower()

    if directives.get("user-scalable") in ("no", "0"):
        return "user-scalable=" + directives["user-scalable"]

    raw = directives.get("maximum-scale")
    if raw:
        try:
            if float(raw) < 2.0:
                return f"maximum-scale={raw} (below the 200% WCAG 1.4.4 requires)"
        except ValueError:
            pass
    return ""


def _is_home(p: dict, b: dict) -> bool:
    return p["role"] == "home" or p["url"].rstrip("/") == (b.get("start_url") or "").rstrip("/")


def run(b: dict) -> tuple[list[dict], list[dict]]:
    findings: list[dict] = []
    skipped: list[dict] = [dict(s) for s in SKIPPED]

    pages = [p for p in b["pages"] if 200 <= p["status"] < 300 and p["html"]]
    if not pages:
        skipped.append({
            "check": "engagement-audit",
            "reason": "no page returned readable HTML, so no engagement check ran",
            "impact": "On-site engagement was not assessed at all. Fix the access problem "
                      "reported by crawl-access-audit, then re-run.",
        })
        return findings, skipped
    total = len(pages)

    heavy_forms, vague, unnamed, no_alt = [], [], [], []
    no_lang, no_h1, zoom_blocked, no_viewport, mismatch, dead_ends = [], [], [], [], [], []
    templates: dict[tuple, dict] = {}          # E1_unlabelled_input, keyed per form template
    orientation: dict[str, dict] = {}          # E12, url -> {title, h1, words, home}

    for p in pages:
        soup = BeautifulSoup(p["html"], "html.parser")
        # <template> content is inert until a script clones it: a control, form
        # or image inside one is not on the page a visitor sees.
        for tmpl in soup.find_all("template"):
            tmpl.decompose()
        d = p["derived"]

        # -- E5 language -----------------------------------------------------
        html_tag = soup.find("html")
        lang = (html_tag.get("lang") if html_tag else None) or ""
        if not lang.strip():
            no_lang.append(p["url"])

        # -- E1 forms ---------------------------------------------------------
        # E1_unlabelled_input is deduplicated per form TEMPLATE (same action and
        # field names), so a footer newsletter box repeated on every page is one
        # finding. A placeholder-only field counts only when required: the
        # accessible-name algorithm falls back to the placeholder, but it vanishes
        # exactly when the user must get the value right.
        for form in soup.find_all("form"):
            fields = form_fields(form)
            if not fields:
                continue
            required = [f for f in fields if f.has_attr("required")]
            unlabelled = []
            for f in fields:
                state = label_state(f, soup)
                if state == "unlabelled" or (state == "placeholder-only" and f.has_attr("required")):
                    unlabelled.append((f.get("name") or f.get("id") or f.get("type") or "?",
                                       state, f.has_attr("required")))
            if unlabelled:
                key = ((form.get("action") or "").strip(),
                       tuple(sorted(f.get("name") or f.get("id") or "?" for f in fields)))
                t = templates.setdefault(key, {"urls": [], "fields": len(fields), "unlabelled": unlabelled})
                if p["url"] not in t["urls"]:
                    t["urls"].append(p["url"])
            if is_conversion_form(form, fields) and (len(required) > 5 or len(fields) > 8):
                heavy_forms.append((p["url"], form.get("action") or "(no action)",
                                    len(fields), len(required)))

        # -- E2 link purpose --------------------------------------------------
        anchors = [a for a in soup.find_all("a") if a.get("href")]
        vague_here = [a for a in anchors
                      if a.get_text(" ", strip=True).lower() in VAGUE_LINKS
                      and ((a.get("aria-label") or a.get("title") or "").strip().lower()
                           in ("", *VAGUE_LINKS))]
        if anchors and len(vague_here) >= max(3, len(anchors) * 0.15):
            vague.append((p["url"], len(vague_here), len(anchors)))

        # -- E3 unnamed interactive controls ----------------------------------
        controls = soup.find_all(["button"]) + \
            [a for a in anchors] + \
            [i for i in soup.find_all("input")
             if (i.get("type") or "").lower() in ("submit", "button", "image")]
        # A control hidden from assistive technology (aria-hidden) or taken out
        # of the tab order (tabindex=-1) is decorative by declaration: a card's
        # duplicate icon button, a carousel arrow mirrored for layout.
        controls = [c for c in controls if not framework_bound(c)
                    and (c.get("aria-hidden") or "").lower() != "true"
                    and (c.get("tabindex") or "").strip() != "-1"]
        nameless = [c for c in controls if not accessible_name(c, soup)]
        if len(nameless) >= 3:
            unnamed.append((p["url"], len(nameless), len(controls)))

        # -- E4 image alt coverage ---------------------------------------------
        imgs = [i for i in soup.find_all("img")
                if not i.get("aria-hidden")
                and (i.get("role") or "").lower() not in ("presentation", "none")
                and i.find_parent("noscript") is None
                and not is_tracking_pixel(i)]
        missing = [i for i in imgs if i.get("alt") is None]
        if imgs and len(missing) >= max(3, len(imgs) * 0.3):
            no_alt.append((p["url"], len(missing), len(imgs)))

        # -- E6 heading structure ----------------------------------------------
        # Zero h1 only: several h1s are legal HTML5 with sectioning, not a defect.
        h1 = soup.find("h1")
        if not h1:
            no_h1.append(p["url"])

        # -- E7 zoom disabled / E11 no viewport at all ---------------------------
        vp = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
        if vp is None:
            no_viewport.append(p["url"])
        else:
            reason = _zoom_suppressed(vp.get("content") or "")
            if reason:
                zoom_blocked.append((p["url"], reason))

        # -- E10 no machine-readable next step ---------------------------------
        # A visitor arriving from an AI answer lands mid-site to check one fact.
        # If the CONTENT offers no route onward, the only available action is
        # "back". Judged on the content subtree only, so a site-wide nav or
        # footer cannot rescue a dead-end body -- and skipped on legal pages,
        # which are legitimately terminal. "#top", "javascript:", empty and
        # self-referencing hrefs are not routes onward.
        if p["role"] != "legal" and len(d["text"]["extracted"].split()) >= 200:
            body = BeautifulSoup(str(soup), "html.parser")
            for t in body.find_all(["nav", "header", "footer", "aside", "script", "style"]):
                t.decompose()
            onward = [a for a in body.find_all("a", href=True) if routes_onward(a, p["url"])]
            contact = body.find("a", href=re.compile(r"^(tel:|mailto:)", re.I))
            if not onward and not body.find("form") and not contact:
                dead_ends.append((p["url"], len(d["text"]["extracted"].split())))

        # -- E9 promise/payoff (fires only on ZERO overlap) ----------------------
        title = (soup.title.get_text(" ", strip=True) if soup.title else "")
        desc_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
        promise = f"{title} {desc_tag.get('content') if desc_tag else ''}".lower()
        promise_terms = {w for w in re.findall(r"[a-z]{4,}", promise)} - STOPWORDS
        body_text = d["text"]["extracted"].lower()
        if promise_terms and len(body_text.split()) > 50:
            if not any(t in body_text for t in promise_terms):
                mismatch.append((p["url"], title[:60]))

        # -- E12 orientation (collected here, judged across pages below) ---------
        orientation[p["url"]] = {
            "title": title, "h1": h1.get_text(" ", strip=True) if h1 else "",
            "words": len(d["text"]["extracted"].split()), "home": _is_home(p, b)}

    # -- E12: can the visitor tell where they are? ---------------------------
    # A non-home page of 100+ words with neither title nor h1, or whose h1 is
    # the homepage's h1 on 3+ pages (one heading for the whole site).
    home_h1 = next((o["h1"] for o in orientation.values() if o["home"] and o["h1"]), "")
    deep = [(u, o) for u, o in orientation.items() if not o["home"] and o["words"] >= 100]
    unnamed_pages = [(u, "no title and no h1") for u, o in deep if not o["title"] and not o["h1"]]
    same_h1 = [(u, f"h1 '{home_h1[:50]}' is the homepage's h1") for u, o in deep
               if home_h1 and o["h1"] == home_h1]
    lost = unnamed_pages + (same_h1 if len(same_h1) >= 3 else [])

    # ============ emit =====================================================
    def add(check_id, title, evidence, urls, action, blast="template",
            confidence="heuristic", basis="static_heuristic"):
        findings.append({
            "check_id": check_id, "title": title, "evidence": evidence,
            "affected_urls": urls, "blast_radius": blast,
            "confidence": confidence, "measurement_basis": basis,
            "suggested_action": action,
        })

    for (action, names), t in sorted(templates.items(), key=lambda kv: (-len(kv[1]["urls"]), kv[0])):
        ul = t["unlabelled"]
        add("E1_unlabelled_input",
            f"Form field(s) without a label in a template used on {len(t['urls'])} page(s)",
            f"Form action='{action or '(none)'}' (fields: {', '.join(names)[:120]}) appears on "
            f"{len(t['urls'])} page(s); {len(ul)} of {t['fields']} field(s) have no associated "
            f"label: " + ", ".join(f"{n} ({s}{', required' if r else ''})" for n, s, r in ul[:6])
            + ". Placeholder text disappears once typing starts, so a required field with "
              "nothing else naming it is easy to get wrong.",
            t["urls"],
            {"summary": "Label every form field programmatically.",
             "priority": "medium", "effort": "low",
             "how": ['Associate every input with a <label for="id">, or an aria-label where '
                     "there is no room for visible text.",
                     "Keep the placeholder as an example value, not as the only name.",
                     "Add autocomplete tokens and the right type/inputmode so mobile keyboards match."],
             "verify": "Every input, select and textarea resolves to a non-empty accessible "
                       "name without relying on its placeholder."},
            blast="template" if len(t["urls"]) > 1 else "single_page")

    if heavy_forms:
        add("E1_form_friction",
            f"Long conversion form on {len(heavy_forms)} page(s)",
            "; ".join(f"{u}: form '{a}' has {n} visible fields, {r} required"
                      for u, a, n, r in heavy_forms[:4]),
            [u for u, _, _, _ in heavy_forms],
            {"summary": "Ask for less up front on contact, demo, signup and checkout forms.",
             "priority": "medium", "effort": "low",
             "how": ["Completion drops sharply beyond about five required fields - ask only for "
                     "what you need now and collect the rest later.",
                     "Split a long form into steps with a visible progress indicator, and "
                     "never make the first step the long one.",
                     "Add autocomplete tokens and correct type/inputmode so mobile keyboards match."],
             "verify": "No conversion form asks for more than five required fields, or more "
                       "than eight fields in total, on its first step."},
            blast="single_page" if len(heavy_forms) == 1 else "template")

    if vague:
        add("E2_vague_link_text",
            f"Non-descriptive link text on {len(vague)} page(s)",
            "; ".join(f"{u}: {n}/{tot} links read 'click here', 'read more' or similar"
                      for u, n, tot in vague[:4]),
            [u for u, _, _ in vague],
            {"summary": "Make link text describe its destination.",
             "priority": "low", "effort": "low",
             "how": ["Replace 'read more' with the destination, e.g. 'read the 2026 pricing guide'.",
                     "Descriptive links help visitors scan, and give assistants a signal about "
                     "what the linked page contains."],
             "verify": "Link text read out of context still identifies the destination."})

    if unnamed:
        add("E3_unnamed_controls",
            f"Interactive controls without an accessible name on {len(unnamed)} page(s)",
            "; ".join(f"{u}: {n}/{tot} controls expose no text, aria-label, aria-labelledby, "
                      f"title, SVG title or image alt" for u, n, tot in unnamed[:4])
            + ". Controls whose name is bound by a JS framework (v-, x-, ng-, :, @, [) were "
              "assumed named at runtime and not counted.",
            [u for u, _, _ in unnamed],
            {"summary": "Give every control a name a machine can read.",
             "priority": "medium", "effort": "low",
             "how": ["Add visible text, or aria-label where the control is icon-only.",
                     "An unnamed control is unusable with a screen reader and invisible to any "
                     "agent trying to understand what actions the page offers."],
             "verify": "Every button/link resolves to a non-empty accessible name."})

    if no_alt:
        add("E4_images_missing_alt",
            f"Images missing alt attributes on {len(no_alt)} page(s)",
            "; ".join(f"{u}: {n}/{tot} images have no alt attribute" for u, n, tot in no_alt[:4])
            + ". Tracking pixels, images inside <noscript> and images marked presentational "
              "or aria-hidden are not counted.",
            [u for u, _, _ in no_alt],
            {"summary": "Add alt text to content images; use alt=\"\" for decorative ones.",
             "priority": "medium", "effort": "low",
             "how": ["Describe what the image conveys, not that it is an image.",
                     "If a price, specification table or contact detail exists only inside an "
                     "image, restate it as text: retrieval agents do not read images.",
                     'Decorative images should carry an explicit empty alt="" so assistive tech '
                     "skips them."],
             "verify": "No content <img> lacks an alt attribute entirely."})

    if dead_ends:
        add("E10_no_next_step",
            f"No route onward from the content on {len(dead_ends)} page(s)",
            "; ".join(f"{u}: {w} words of content, no in-content link, form, tel: or mailto:"
                      for u, w in dead_ends[:4])
            + ". A visitor who arrives here from an AI answer, checks the one fact they came "
              "for and wants to go further has nothing in the content to act on. Anchors to "
              "'#', 'javascript:' or the page itself were not counted as routes.",
            [u for u, _ in dead_ends],
            {"summary": "Give each substantial page at least one relevant next step in the content itself.",
             "priority": "medium", "effort": "low",
             "how": ["Link to the obvious follow-on page from within the body copy -- pricing "
                     "from a product page, the product from a blog post.",
                     "A site-wide nav bar does not count here: it is the same on every page, so "
                     "it says nothing about where THIS page should lead."],
             "verify": "Each page over 200 words contains at least one in-content link, form or "
                       "contact route."})

    if lost:
        add("E12_no_orientation",
            f"Visitors cannot tell where they are on {len(lost)} page(s)",
            "; ".join(f"{u}: {why}" for u, why in lost[:4])
            + ". A visitor arriving mid-site from an AI answer reads the title and h1 first to "
              "confirm they landed in the right place; a page that names nothing, or repeats "
              "the homepage heading, gives them no such confirmation.",
            [u for u, _ in lost],
            {"summary": "Give every deep page a title and h1 that name its own subject.",
             "priority": "low", "effort": "low",
             "how": ["Set the <title> to 'Page subject | Site name' and make the h1 the page "
                     "subject, not the brand slogan.",
                     "Add a breadcrumb (with BreadcrumbList JSON-LD) so the page also says which "
                     "section it belongs to."],
             "verify": "Each deep page's title and h1 differ from the homepage's and name the page."},
            blast="template" if len(lost) > 1 else "single_page")

    if no_lang:
        add("E5_no_lang", f"No lang attribute on {len(no_lang)} page(s)",
            f"{len(no_lang)}/{total} pages omit <html lang>. Examples: {no_lang[:3]}. "
            f"Language declaration affects pronunciation in screen readers and helps any "
            f"consumer pick the right processing rules.",
            no_lang,
            {"summary": "Declare the page language.",
             "priority": "low", "effort": "low",
             "how": ['Set <html lang="en"> (or the correct BCP-47 tag) on every page.'],
             "verify": "Every page's <html> element carries a lang attribute."},
            blast="site_wide" if len(no_lang) == total else "template")

    if no_h1:
        add("E6_heading_structure",
            f"No h1 heading on {len(no_h1)} page(s)",
            f"{len(no_h1)}/{total} pages contain no h1 element at all. Examples: {no_h1[:4]}. "
            f"Extractors and assistants use the top heading to decide what a page is about.",
            no_h1,
            {"summary": "Give each page one h1 that states its subject.",
             "priority": "low", "effort": "low",
             "how": ["Add a single h1 naming the page subject, then h2/h3 for sections in order.",
                     "If the visual title is styled as a div or span, change the element, not the CSS."],
             "verify": "Each page has an h1 and its text matches the page's subject."},
            blast="site_wide" if len(no_h1) == total else "template")

    if no_viewport:
        # The one deterministic check here: the tag is present or it is not.
        add("E11_no_viewport", f"No viewport meta tag on {len(no_viewport)} page(s)",
            f"{len(no_viewport)}/{total} crawled page(s) have no <meta name=\"viewport\"> at all. "
            f"Examples: {no_viewport[:3]}. Without it, mobile browsers lay the page out at a "
            f"desktop width (about 980px) and shrink it to fit, so text is unreadable until "
            f"the visitor pinch-zooms.",
            no_viewport,
            {"summary": "Add a viewport meta tag to every page template.",
             "priority": "medium", "effort": "low",
             "how": ['Add <meta name="viewport" content="width=device-width, initial-scale=1"> '
                     "inside <head> in the base template.",
                     "Do not add user-scalable=no or a maximum-scale below 2 while you are there "
                     "(see E7)."],
             "verify": "On a phone, the page text is readable without zooming and no horizontal "
                       "scrollbar appears."},
            blast="site_wide" if len(no_viewport) == total else "template",
            confidence="deterministic", basis="static_fact")

    if zoom_blocked:
        add("E7_zoom_disabled", f"Pinch-zoom suppressed on {len(zoom_blocked)} page(s)",
            f"{len(zoom_blocked)}/{total} crawled page(s) restrict zoom in the viewport meta tag, "
            f"failing WCAG 1.4.4 (Resize Text). Examples: "
            + "; ".join(f"{u} sets {why}" for u, why in zoom_blocked[:3])
            + ". iOS Safari has ignored these directives since iOS 10, so the impact falls on "
              "Android Chrome and other browsers that still honour them.",
            [u for u, _ in zoom_blocked],
            {"summary": "Allow users to zoom.",
             "priority": "medium", "effort": "low",
             "how": ['Use <meta name="viewport" content="width=device-width, initial-scale=1"> '
                     "with no user-scalable or maximum-scale restriction.",
                     "If a pinch gesture is needed by a map or canvas, scope the suppression to "
                     "that element with CSS touch-action instead of disabling it page-wide."],
             "verify": "Pinch-zoom works on an Android phone; the viewport tag sets no "
                       "user-scalable=no and no maximum-scale below 2."},
            blast="site_wide" if len(zoom_blocked) == total else "template")

    if mismatch:
        add("E9_promise_payoff_mismatch",
            f"Page content shares no vocabulary with its own title on {len(mismatch)} page(s)",
            "; ".join(f"{u}: title '{t}' - none of its distinctive terms appear in the body text"
                      for u, t in mismatch[:4]),
            [u for u, _ in mismatch],
            {"summary": "Make the page deliver what its title and description promise.",
             "priority": "medium", "effort": "medium",
             "how": ["A visitor arriving from an AI answer came to verify something specific. If "
                     "the page does not visibly address the title's subject, they leave.",
                     "State the page's subject in the first paragraph using the same words as the "
                     "title.",
                     "If the title is aspirational marketing copy, add a plain-language sentence "
                     "underneath saying concretely what this page covers."],
             "verify": "The first paragraph restates the title's subject in plain words."})

    return findings, skipped


if __name__ == "__main__":
    f, s = run(load_bundle())
    print(json.dumps({"findings": f, "checks_skipped": s}, indent=2, ensure_ascii=False))
