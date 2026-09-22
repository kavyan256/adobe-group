#!/usr/bin/env python3
"""On-site engagement risk factors, measured statically.

Standalone: reads a site bundle, writes findings. Standard library + BeautifulSoup.

WHAT THIS SKILL DELIBERATELY DOES NOT DO
----------------------------------------
* It does not report bounce rate. A single-page visit that answered the visitor's
  question is a success, not a failure - and a visitor arriving from an AI answer
  is usually there to VERIFY one fact, so a short visit is often the desired
  outcome. We report engagement RISK FACTORS, not inferred behaviour.
* It does not flag the presence of a consent banner. Consent notices are legally
  required in many jurisdictions; flagging them would be a false positive on
  essentially every EU-facing site.
* It does not report Core Web Vitals. Field data at the 75th percentile is what
  matters, a single synthetic fetch cannot measure it, and INP cannot be measured
  synthetically at all. Reporting a lab number as a finding would be indefensible.
* It does not check colour contrast. That needs computed styles, which needs a
  browser. It is reported in checks_skipped[] rather than approximated.
* It does not match action verbs. An English verb list fails on every non-English
  site; we test for interactive affordance structurally instead.

Every finding here is measurement_basis=static_heuristic and therefore capped at
medium severity by the severity table: these are structural risk factors inferred
from markup, never observed user behaviour.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse
import sys

from bs4 import BeautifulSoup

VAGUE_LINKS = {"click here", "here", "read more", "more", "learn more", "this",
               "link", "continue", "details", "find out more"}
STOPWORDS = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with",
             "your", "our", "we", "you", "is", "are", "be", "by", "at", "from",
             "that", "this", "it", "as", "home", "welcome"}


def load_bundle() -> dict:
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        return json.loads(open(sys.argv[1], encoding="utf-8").read())
    return json.loads(sys.stdin.read())


def derived_of(page: dict) -> dict | None:
    """Normalised JSON-LD + text from the crawl layer. See bundle.py::derive."""
    d = page.get("derived")
    return d if isinstance(d, dict) and "jsonld" in d else None


def accessible_name(el) -> str:
    for attr in ("aria-label", "title"):
        if (el.get(attr) or "").strip():
            return el[attr].strip()
    if el.name == "input" and (el.get("value") or "").strip():
        return el["value"].strip()
    img = el.find("img")
    if img is not None and (img.get("alt") or "").strip():
        return img["alt"].strip()
    return el.get_text(" ", strip=True)


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


def run(b: dict) -> tuple[list[dict], list[dict]]:
    findings: list[dict] = []
    skipped: list[dict] = [{
        "check": "E_colour_contrast",
        "reason": "WCAG contrast ratios require computed styles, which require a browser; "
                  "this marketplace runs without one to stay portable and deterministic",
        "impact": "Text that is hard to read for low-vision users is not detected. Run an "
                  "in-browser tool (axe DevTools, Lighthouse) to cover this.",
    }, {
        "check": "E_core_web_vitals",
        "reason": "LCP/CLS/INP are field metrics; a single synthetic fetch is not a valid "
                  "measurement and INP cannot be measured synthetically at all",
        "impact": "Real-user performance is not assessed. Check Google Search Console's Core "
                  "Web Vitals report, which uses field data.",
    }]

    pages = [p for p in b["pages"] if 200 <= p["status"] < 300 and p["html"]]
    if not pages:
        return findings, skipped
    total = len(pages)

    heavy_forms, vague, unnamed, no_alt = [], [], [], []
    no_lang, no_h1, multi_h1, zoom_blocked, mismatch = [], [], [], [], []
    dead_ends = []

    if any(derived_of(p) is None for p in pages):
        skipped.append({
            "check": "engagement-audit_text_dependent",
            "reason": "this bundle predates bundle_schema_version 2, so it carries no "
                      "normalised text. Re-crawl with this version: "
                      "python3 skills/audit-orchestrator/scripts/bundle.py <url> out.json",
            "impact": "The promise/payoff check (E9) did not run. DOM-only engagement "
                      "checks were unaffected.",
        })

    for p in pages:
        soup = BeautifulSoup(p["html"], "html.parser")
        d = derived_of(p)

        # -- E5 language -----------------------------------------------------
        html_tag = soup.find("html")
        lang = (html_tag.get("lang") if html_tag else None) or ""
        if not lang.strip():
            no_lang.append(p["url"])

        # -- E1 form friction ------------------------------------------------
        for form in soup.find_all("form"):
            fields = [f for f in form.find_all(["input", "select", "textarea"])
                      if (f.get("type") or "text").lower()
                      not in ("hidden", "submit", "button", "image")]
            required = [f for f in fields if f.has_attr("required")]
            unlabelled = []
            for f in fields:
                fid = f.get("id")
                labelled = bool(f.get("aria-label") or f.get("aria-labelledby")
                                or (fid and soup.find("label", attrs={"for": fid}))
                                or f.find_parent("label"))
                if not labelled:
                    unlabelled.append(f.get("name") or f.get("type") or "?")
            if len(required) > 5 or unlabelled:
                heavy_forms.append((p["url"], len(fields), len(required), len(unlabelled)))

        # -- E2 link purpose --------------------------------------------------
        anchors = [a for a in soup.find_all("a") if a.get("href")]
        vague_here = [a.get_text(" ", strip=True).lower() for a in anchors
                      if a.get_text(" ", strip=True).lower() in VAGUE_LINKS]
        if anchors and len(vague_here) >= max(3, len(anchors) * 0.15):
            vague.append((p["url"], len(vague_here), len(anchors)))

        # -- E3 unnamed interactive controls ----------------------------------
        controls = soup.find_all(["button"]) + \
            [a for a in anchors] + \
            [i for i in soup.find_all("input")
             if (i.get("type") or "").lower() in ("submit", "button", "image")]
        nameless = [c for c in controls if not accessible_name(c)]
        if len(nameless) >= 3:
            unnamed.append((p["url"], len(nameless), len(controls)))

        # -- E4 image alt coverage ---------------------------------------------
        imgs = [i for i in soup.find_all("img") if not i.get("aria-hidden")]
        missing = [i for i in imgs if i.get("alt") is None]
        if imgs and len(missing) >= max(3, len(imgs) * 0.3):
            no_alt.append((p["url"], len(missing), len(imgs)))

        # -- E6 heading structure ----------------------------------------------
        # Zero h1 is a defect: nothing tells an extractor what the page is about.
        # Several h1s are legal HTML5 with sectioning and common in practice --
        # reported as info only, never as a problem to fix.
        h1s = soup.find_all("h1")
        if not h1s:
            no_h1.append(p["url"])
        elif len(h1s) > 1:
            multi_h1.append((p["url"], len(h1s)))

        # -- E7 zoom disabled ---------------------------------------------------
        vp = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
        reason = _zoom_suppressed((vp.get("content") if vp else "") or "")
        if reason:
            zoom_blocked.append((p["url"], reason))

        # -- E10 no machine-readable next step ---------------------------------
        # A visitor arriving from an AI answer lands mid-site to check one fact.
        # If the CONTENT offers no route onward, the only available action is
        # "back". Judged on the content subtree only, so a site-wide nav or
        # footer cannot rescue a dead-end body -- and skipped on legal pages,
        # which are legitimately terminal.
        if d and p["role"] != "legal" and len(d["text"]["extracted"].split()) >= 200:
            body = BeautifulSoup(str(soup), "html.parser")
            for t in body.find_all(["nav", "header", "footer", "aside", "script", "style"]):
                t.decompose()
            host = urlparse(p["url"]).netloc
            onward = [a for a in body.find_all("a", href=True)
                      if not urlparse(a["href"]).netloc
                      or urlparse(a["href"]).netloc == host]
            contact = body.find("a", href=re.compile(r"^(tel:|mailto:)", re.I))
            if not onward and not body.find("form") and not contact:
                dead_ends.append((p["url"], len(d["text"]["extracted"].split())))

        # -- E9 promise/payoff (fires only on ZERO overlap) ----------------------
        title = (soup.title.get_text(" ", strip=True) if soup.title else "")
        desc_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
        promise = f"{title} {desc_tag.get('content') if desc_tag else ''}".lower()
        promise_terms = ({w for w in re.findall(r"[a-z]{4,}", promise)} - STOPWORDS
                         if d else set())
        # The canonical extraction from the crawl layer, so "the body text" means
        # the same thing in every skill (v2.0 stripped 10 tags in one skill, 5
        # here and none in a third).
        body_text = d["text"]["extracted"].lower() if d else ""
        if promise_terms and len(body_text.split()) > 50:
            if not any(t in body_text for t in promise_terms):
                mismatch.append((p["url"], title[:60]))

    # ============ emit =====================================================
    def add(check_id, title, evidence, urls, action, blast="template", see_also=None):
        f = {
            "check_id": check_id, "title": title, "evidence": evidence,
            "affected_urls": urls, "blast_radius": blast,
            "confidence": "heuristic", "measurement_basis": "static_heuristic",
            "suggested_action": action,
        }
        if see_also:
            f["see_also"] = see_also
        findings.append(f)

    if heavy_forms:
        add("E1_form_friction",
            f"Form friction on {len(heavy_forms)} page(s)",
            "; ".join(f"{u}: {n} fields, {r} required, {ul} without an associated label"
                      for u, n, r, ul in heavy_forms[:4]),
            [u for u, _, _, _ in heavy_forms],
            {"summary": "Reduce required fields and label every input.",
             "priority": "medium", "effort": "low",
             "how": ["Completion drops sharply beyond about five required fields - ask only for "
                     "what you need now and collect the rest later.",
                     'Associate every input with a <label for="id"> or an aria-label.',
                     "Add autocomplete tokens and correct type/inputmode so mobile keyboards match."],
             "verify": "Every input has a programmatic label; required fields are minimal."})

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
            "; ".join(f"{u}: {n}/{tot} controls expose no text, aria-label, title or image alt"
                      for u, n, tot in unnamed[:4]),
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
            "; ".join(f"{u}: {n}/{tot} images have no alt attribute" for u, n, tot in no_alt[:4]),
            [u for u, _, _ in no_alt],
            {"summary": "Add alt text to content images; use alt=\"\" for decorative ones.",
             "priority": "medium", "effort": "low",
             "how": ["Describe what the image conveys, not that it is an image.",
                     'Decorative images should carry an explicit empty alt="" so assistive tech '
                     "skips them."],
             "verify": "No <img> lacks an alt attribute entirely."},
            see_also=["B5_fact_locked_in_image"])

    if dead_ends:
        add("E10_no_next_step",
            f"No route onward from the content on {len(dead_ends)} page(s)",
            "; ".join(f"{u}: {w} words of content, no in-content link, form, tel: or mailto:"
                      for u, w in dead_ends[:4])
            + ". A visitor who arrives here from an AI answer, checks the one fact they came "
              "for and wants to go further has nothing in the content to act on.",
            [u for u, _ in dead_ends],
            {"summary": "Give each substantial page at least one relevant next step in the content itself.",
             "priority": "medium", "effort": "low",
             "how": ["Link to the obvious follow-on page from within the body copy -- pricing "
                     "from a product page, the product from a blog post.",
                     "A site-wide nav bar does not count here: it is the same on every page, so "
                     "it says nothing about where THIS page should lead."],
             "verify": "Each page over 200 words contains at least one in-content link, form or "
                       "contact route."})

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

    if multi_h1:
        add("E6_multiple_h1",
            f"More than one h1 on {len(multi_h1)} page(s)",
            "; ".join(f"{u}: {n} h1 elements" for u, n in multi_h1[:4])
            + ". Legal HTML5 with sectioning; noted because some extractors take only the first h1 as the page subject.",
            [u for u, _ in multi_h1],
            {"summary": "Optional: keep one h1 per page if the extra ones are not sectioning roots.",
             "priority": "low", "effort": "low",
             "how": ["No action required if each h1 heads its own <section>/<article>.",
                     "Otherwise demote the secondary headings to h2."],
             "verify": "The first h1 on the page names the page's subject."})

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
