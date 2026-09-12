# Engagement tests: engagement-audit. Run by tests/run_tests.py, which injects
# the helpers (check, _page, _bundle, run_skill, audit_replay, H, ...).
# Owner: retention. Add tests below; keep each one small and named for the
# behaviour it pins.

ENG = ("engagement-audit", "check_engagement.py")
VP = '<meta name="viewport" content="width=device-width, initial-scale=1">'
WORDS = " ".join(f"word{i}" for i in range(220))   # 220 words of body copy


def eng(pages):
    return run_skill(*ENG, _bundle(pages))


def ids(findings):
    return [f["check_id"] for f in findings]


def one(findings, check_id):
    return next((f for f in findings if f["check_id"] == check_id), {})


def eng_raw(pages):
    """Full {findings, checks_skipped} output, not just the findings list."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "skills" / ENG[0] / "scripts" / ENG[1]),
         str(_write("eng_raw.json", _bundle(pages)))], capture_output=True, text=True)
    return json.loads(proc.stdout) if proc.returncode == 0 else {"_err": proc.stderr}


# Three pages so blast radius is trusted; the home page always has a real link
# so E10 only ever concerns the page under test.
HOME = _page("https://t.test/", "home",
             H(VP, f"<h1>Acme</h1><p>{WORDS}</p><a href='/guide'>The guide</a>"))
ABOUT = _page("https://t.test/about", "about",
              H(VP, f"<h1>About Acme</h1><p>{WORDS}</p><a href='/guide'>The guide</a>"))


def site(*extra):
    return [HOME, ABOUT, *extra]


print("\nE10: only a real route onward counts")
back_to_top = site(_page("https://t.test/guide", "generic",
                         H(VP, f"<h1>Guide</h1><p>{WORDS}</p><a href='#top'>Back to top</a>"
                               "<a href='javascript:void(0)'>Print</a><a href=''>x</a>"
                               "<a href='https://t.test/guide'>Permalink</a>")))
check("a dead-end body whose links are #top, javascript:, empty and self still fires E10",
      one(eng(back_to_top), "E10_no_next_step").get("affected_urls"), ["https://t.test/guide"])
real_link = site(_page("https://t.test/guide", "generic",
                       H(VP, f"<h1>Guide</h1><p>{WORDS}</p><a href='#top'>Back to top</a>"
                             "<a href='/pricing'>See pricing</a>")))
check("a body with one real internal link does not fire E10",
      "E10_no_next_step" in ids(eng(real_link)), False)

print("\nE4: pixels, noscript and presentational images are not content")
pixels = site(_page("https://t.test/p", "generic", H(VP, (
    "<h1>P</h1><p>copy</p>"
    '<noscript><img src="https://x.test/a.gif" height="1" width="1">'
    '<img src="https://x.test/b.gif" height="1" width="1">'
    '<img src="https://x.test/c.gif" height="1" width="1"></noscript>'))))
check("three 1x1 pixels inside noscript do not fire E4",
      "E4_images_missing_alt" in ids(eng(pixels)), False)
decor = site(_page("https://t.test/p", "generic", H(VP, (
    "<h1>P</h1><p>copy</p>"
    '<img src="/a.png" role="presentation"><img src="/b.png" aria-hidden="true">'
    '<img src="/c.png" role="none"><img src="https://cdn.test/beacon.gif">'
    '<img src="https://cdn.test/track/x.png"><img src="/pixel.gif">'))))
check("role=presentation/none, aria-hidden and beacon/track/pixel images do not fire E4",
      "E4_images_missing_alt" in ids(eng(decor)), False)
real_imgs = site(_page("https://t.test/p", "generic", H(VP, (
    '<h1>P</h1><p>copy</p><img src="/hero.jpg"><img src="/team.jpg"><img src="/office.jpg"><img src="/ok.jpg" alt="ok">'))))
check("three content images without alt still fire E4",
      one(eng(real_imgs), "E4_images_missing_alt").get("affected_urls"), ["https://t.test/p"])

print("\nE3: accessible names from aria-labelledby, SVG title and framework bindings")
labelledby = site(_page("https://t.test/p", "generic", H(VP, (
    "<h1>P</h1><span id='l1'>Open</span><span id='l2'>menu</span>"
    "<button aria-labelledby='l1 l2'></button><button aria-labelledby='l1'></button>"
    "<button aria-labelledby='l2'></button>"))))
check("aria-labelledby resolving to text is an accessible name",
      "E3_unnamed_controls" in ids(eng(labelledby)), False)
svg_title = site(_page("https://t.test/p", "generic", H(VP, (
    "<h1>P</h1><button><svg><title>Close</title></svg></button>"
    "<button><svg><title>Search</title></svg></button>"
    "<a href='/x'><svg><title>Cart</title></svg></a>"))))
check("an SVG title child is an accessible name", "E3_unnamed_controls" in ids(eng(svg_title)), False)
framework = site(_page("https://t.test/p", "generic", H(VP, (
    "<h1>P</h1><button v-text='label'></button><button :aria-label='x'></button>"
    "<button @click='go'></button><button x-text='t'></button><button ng-bind='n'></button>"
    "<button [attr.aria-label]='l'></button><button data-bind='text: t'></button>"))))
check("controls carrying framework binding attributes are assumed named at runtime",
      "E3_unnamed_controls" in ids(eng(framework)), False)
nameless = site(_page("https://t.test/p", "generic", H(VP, (
    "<h1>P</h1><button></button><button><svg></svg></button><a href='/x'></a>"
    "<button aria-labelledby='missing'></button>"))))
check("genuinely nameless controls (including a dangling aria-labelledby) still fire E3",
      one(eng(nameless), "E3_unnamed_controls").get("evidence", "").startswith("https://t.test/p: 4/"), True)

print("\nE2: a vague link with a descriptive aria-label or title is not vague")
labelled_vague = site(_page("https://t.test/p", "generic", H(VP, (
    "<h1>P</h1><a href='/a' aria-label='Read the 2026 pricing guide'>Read more</a>"
    "<a href='/b' title='Open the returns policy'>click here</a>"
    "<a href='/c' aria-label='Learn more about shipping'>Learn more</a>"))))
check("aria-label or title rescues vague link text", "E2_vague_link_text" in ids(eng(labelled_vague)), False)
plain_vague = site(_page("https://t.test/p", "generic", H(VP, (
    "<h1>P</h1><a href='/a'>Read more</a><a href='/b'>click here</a><a href='/c'>Learn more</a>"))))
check("plain vague links still fire E2", "E2_vague_link_text" in ids(eng(plain_vague)), True)

print("\nE1 split: unlabelled inputs per template, friction only on conversion forms")
NEWSLETTER = ('<form action="/contact#newsletter" method="post">'
              '<input type="email" name="contact[email]" placeholder="Email Address" required>'
              '<button type="submit">Sign up</button></form>')
five = [_page(f"https://t.test/{i}", "generic",
              H(VP, f"<h1>Page {i}</h1><p>{WORDS}</p><a href='/guide'>The guide</a>{NEWSLETTER}"))
        for i in range(5)]
nl = eng([HOME, *five])
check("a one-field newsletter box is not form friction", "E1_form_friction" in ids(nl), False)
check("the same unlabelled newsletter template on five pages is one finding listing every page",
      (ids(nl).count("E1_unlabelled_input"), len(one(nl, "E1_unlabelled_input").get("affected_urls", []))),
      (1, 5))
check("the evidence says the field is placeholder-only and required",
      "placeholder" in one(nl, "E1_unlabelled_input").get("evidence", ""), True)
optional_ph = site(_page("https://t.test/p", "generic", H(VP, (
    '<h1>P</h1><form action="/search"><input name="q" placeholder="Search"></form>'))))
check("an optional placeholder-only input (a search box) is not reported",
      "E1_unlabelled_input" in ids(eng(optional_ph)), False)
labelled = site(_page("https://t.test/p", "generic", H(VP, (
    '<h1>P</h1><form action="/contact"><label for="e">Email</label><input id="e" name="email" required>'
    '<input name="n" aria-label="Name" required><span id="t">Phone</span><input name="p" aria-labelledby="t">'
    '<input name="c" title="Company"></form>'))))
check("label, aria-label, aria-labelledby and title all count as labels",
      "E1_unlabelled_input" in ids(eng(labelled)), False)
big_contact = site(_page("https://t.test/contact", "contact", H(VP, "<h1>Contact</h1><form action='/contact'>" + "".join(
    f"<label for='f{i}'>F{i}</label><input id='f{i}' name='f{i}' required>" for i in range(6)) + "</form>")))
check("a contact form with six required fields fires E1_form_friction",
      one(eng(big_contact), "E1_form_friction").get("affected_urls"), ["https://t.test/contact"])
big_signup = site(_page("https://t.test/join", "generic", H(VP, "<h1>Join</h1><form action='/x'>" + "".join(
    f"<label for='f{i}'>F{i}</label><input id='f{i}' name='signup_f{i}'>" for i in range(9)) + "</form>")))
check("a signup form with nine visible fields fires E1_form_friction",
      "E1_form_friction" in ids(eng(big_signup)), True)
big_filter = site(_page("https://t.test/shop", "generic", H(VP, "<h1>Shop</h1><form action='/shop'>" + "".join(
    f"<label for='f{i}'>F{i}</label><select id='f{i}' name='facet{i}'></select>" for i in range(9)) + "</form>")))
check("a nine-field form that is not a conversion form (facet filters) does not fire E1_form_friction",
      "E1_form_friction" in ids(eng(big_filter)), False)
check("unlabelled inputs alone never fire E1_form_friction", "E1_form_friction" in ids(nl), False)

print("\nE11: no viewport meta at all is a plain fact")
no_vp = [_page("https://t.test/", "home", H("", "<h1>Acme</h1><p>copy</p><a href='/a'>a</a>")),
         _page("https://t.test/a", "about", H("", "<h1>About</h1><p>copy</p>")),
         _page("https://t.test/b", "generic", H("", "<h1>B</h1><p>copy</p>"))]
e11 = one(eng(no_vp), "E11_no_viewport")
check("E11 fires when no page declares a viewport", len(e11.get("affected_urls", [])), 3)
check("E11 is a deterministic static fact, not a heuristic",
      (e11.get("confidence"), e11.get("measurement_basis")), ("deterministic", "static_fact"))
check("E11 does not fire when the tag exists, even a restrictive one (E7's job)",
      "E11_no_viewport" in ids(eng(site(_page("https://t.test/p", "generic",
          H('<meta name="viewport" content="width=device-width, user-scalable=no">', "<h1>P</h1>"))))), False)
rep = audit_replay(_bundle(no_vp))
e11r = next((f for f in rep["findings"] if f["check_id"] == "E11_no_viewport"), {})
check("E11 keeps medium through the orchestrator (no heuristic cap applies)",
      (e11r.get("severity"), e11r.get("blast_radius")), ("medium", "site_wide"))

print("\nE12: a visitor should be able to tell where they are")
untitled = site(_page("https://t.test/p", "generic",
                      f"<html lang='en'><head>{VP}</head><body><main><p>{WORDS}</p></main></body></html>"))
check("a 100+ word non-home page with neither title nor h1 fires E12",
      one(eng(untitled), "E12_no_orientation").get("affected_urls"), ["https://t.test/p"])
short_untitled = site(_page("https://t.test/p", "generic",
                            f"<html lang='en'><head>{VP}</head><body><main><p>short page</p></main></body></html>"))
check("a short page without title or h1 does not fire E12", "E12_no_orientation" in ids(eng(short_untitled)), False)
same_h1 = [HOME] + [_page(f"https://t.test/{i}", "generic",
                          H(VP, f"<h1>Acme</h1><p>{WORDS}</p><a href='/guide'>The guide</a>")) for i in range(3)]
e12 = one(eng(same_h1), "E12_no_orientation")
check("the homepage h1 repeated on three pages fires E12 on those pages, not the homepage",
      sorted(e12.get("affected_urls", [])), [f"https://t.test/{i}" for i in range(3)])
check("the homepage h1 repeated on only two pages does not fire E12",
      "E12_no_orientation" in ids(eng(same_h1[:3])), False)
check("distinct h1s never fire E12", "E12_no_orientation" in ids(eng(site())), False)
check("E12 is a heuristic", e12.get("confidence"), "heuristic")

print("\nHonest limits: what engagement-audit does not assess")
raw = eng_raw(site())
skipped = {s["check"]: s for s in raw.get("checks_skipped", [])}
check("behaviour metrics, rendered experience, copy quality and authenticated flows are declared skipped",
      sorted({"E_behaviour_metrics", "E_rendered_experience", "E_copy_quality",
              "E_authenticated_flows", "E_colour_contrast", "E_core_web_vitals"} - set(skipped)), [])
check("every skipped entry says what, why and how to check it yourself",
      all(s["reason"].startswith("Not assessed: ") and "Reason: " in s["reason"]
          and s.get("impact", "").startswith("How to check it yourself: ") for s in skipped.values()), True)
check("a short visit from an AI answer is called out as often a success",
      "success" in skipped.get("E_behaviour_metrics", {}).get("reason", ""), True)
check("the engagement skill does not declare itself skipped when pages were readable",
      "engagement-audit" in skipped, False)
blocked = [_page("https://t.test/", "home", "", status=403), _page("https://t.test/a", "about", "", status=403)]
raw_blocked = eng_raw(blocked)
blocked_skipped = {s["check"]: s for s in raw_blocked.get("checks_skipped", [])}
check("with zero readable pages the skill reports itself as not run, with the fixed skips",
      ("engagement-audit" in blocked_skipped, "E_colour_contrast" in blocked_skipped,
       raw_blocked.get("findings")), (True, True, []))
check("...and says why", "no page returned readable HTML" in blocked_skipped.get("engagement-audit", {}).get("reason", ""), True)


print("\nE3: controls hidden from assistive tech are not unnamed controls (ikea.com)")
hidden_ctl = site(_page("https://t.test/p", "generic", H(VP, (
    "<h1>P</h1><button aria-hidden='true' tabindex='-1'><span class='icon'></span></button>"
    "<button aria-hidden='true'><span></span></button><a href='/x' tabindex='-1'></a>"
    "<button tabindex='-1'></button>"))))
check("aria-hidden or tabindex=-1 controls do not fire E3", "E3_unnamed_controls" in ids(eng(hidden_ctl)), False)

child_label = site(_page("https://t.test/p", "generic", H(VP, (
    "<h1>P</h1><a href='https://f.test/x'><svg aria-label='Facebook'></svg></a>"
    "<a href='https://y.test/x'><svg aria-label='YouTube'></svg></a>"
    "<a href='https://i.test/x'><span aria-label='Instagram'></span></a>"))))
check("an aria-label on an icon child names the link (nps.gov)", "E3_unnamed_controls" in ids(eng(child_label)), False)
