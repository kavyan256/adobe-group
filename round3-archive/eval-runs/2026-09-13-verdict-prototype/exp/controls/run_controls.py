#!/usr/bin/env python3
"""Deterministic verdict controls through the entrypoint: fabricated verdicts must be
rejected, genuine ones applied, and every report must stay schema-valid."""
import json, subprocess, sys
from pathlib import Path
import jsonschema
HERE = Path(__file__).resolve().parent
R = "/home/kavyan2/Desktop/adobe/eval-runs/2026-09-12-100-after-fixes/results"
MARKET = Path("/home/kavyan2/Desktop/adobe/brand-ai-readiness-audit-v5")
AUDIT = MARKET / "skills/audit-orchestrator/scripts/audit.py"
SCHEMA = json.loads((MARKET / "schema/audit-report.schema.json").read_text())
E = "The crawl shows this finding does not hold for the reason given here."


def run(name, slug, verdict):
    claims, out = HERE / f"{name}.claims.json", HERE / f"{name}.report.json"
    claims.write_text(json.dumps({"verdicts": [verdict]}))
    subprocess.run([sys.executable, str(AUDIT), "--replay", f"{R}/{slug}/{slug}.bundle.json",
                    "--agent-claims", str(claims), "-o", str(out)], capture_output=True, text=True, check=True)
    report = json.loads(out.read_text())
    jsonschema.validate(report, SCHEMA)
    ar = report["agent_review"]
    return ar.get("verdicts_applied", 0), (ar.get("verdicts_rejected") or [{}])[0].get("reason"), report


NEG = {
 "duolingo": ("duolingo", {"finding":{"check_id":"B4_empty_shell"},"verdict":"not_a_defect","reason":"error_or_placeholder_page","urls":["https://www.duolingo.com/"],"explanation":E,"evidence":[{"url":"https://www.duolingo.com/","type":"field","path":"title","op":"contains","value":"Page not found"}]}),
 "kraken": ("kraken", {"finding":{"check_id":"A7_site_unreadable"},"verdict":"not_a_defect","reason":"auditor_side_failure","explanation":E,"evidence":[{"type":"site_note_contains","value":"ReadTimeout"}]}),
 "aspendental": ("aspendental", {"finding":{"check_id":"C1_structured_data_invalid"},"verdict":"not_a_defect","reason":"measurement_wrong","explanation":E,"evidence":[{"url":"https://www.aspendental.com/mottoaligners/pricing","type":"html_contains","value":"this JSON-LD parses cleanly"},{"url":"https://www.aspendental.com/mottoaligners/results","type":"field","path":"status","op":"eq","value":200}]}),
 "mit": ("mit", {"finding":{"check_id":"A5_canonical_problem"},"verdict":"not_a_defect","reason":"duplicate_of_finding","explanation":E,"evidence":[{"type":"finding_exists","check_id":"A9_broken_pages","url":"https://www.mit.edu/"}]}),
 "thehindu": ("thehindu", {"finding":{"check_id":"B1_fact_absent"},"verdict":"not_a_defect","reason":"page_purpose_mismatch","urls":["https://www.thehindu.com/subscription"],"explanation":E,"evidence":[{"url":"https://www.thehindu.com/","type":"field","path":"title","op":"contains","value":"The Hindu"}]}),
 "msf": ("msf", {"finding":{"check_id":"A3_noindex"},"verdict":"downgrade","reason":"overstated_impact","explanation":E,"evidence":[{"url":"https://www.msf.org/rewards/msf-staff-rewards","type":"field","path":"title","op":"contains","value":"Rewards"}]}),
 "logitech": ("logitech", {"finding":{"check_id":"B1_fact_absent"},"verdict":"confirm_intent","reason":"page_purpose_mismatch","explanation":E,"evidence":[{"url":"https://www.logitech.com/en-in/products/combos/pop-icon-combo","type":"field","path":"title","op":"contains","value":"POP Icon"}]}),
 "supercell-zoom-intent": ("supercell", {"finding":{"check_id":"E7_zoom_disabled","url":"https://supercell.com/clashofclans-gift/ar"},"verdict":"confirm_intent","reason":"deliberate_configuration","explanation":E,"evidence":[{"url":"https://supercell.com/clashofclans-gift/ar","type":"field","path":"lang","op":"eq","value":"ar"}]}),
 "bluebottle-trivial": ("bluebottle", {"finding":{"check_id":"B4_empty_shell"},"verdict":"not_a_defect","reason":"measurement_wrong","explanation":E,"evidence":[{"url":"https://bluebottlecoffee.com/us/eng","type":"html_contains","value":"bluebottlecoffee.com"}] + [{"url":u,"type":"field","path":"status","op":"eq","value":200} for u in ["https://bluebottlecoffee.com/us/eng/FAQ","https://bluebottlecoffee.com/us/eng/accessibility","https://bluebottlecoffee.com/us/eng/blue-bottle-studio","https://bluebottlecoffee.com/us/eng/blue-bottle-sustainability","https://bluebottlecoffee.com/us/eng/product/beyond-arabica","https://bluebottlecoffee.com/us/eng/product/bella-donovan?a_oID=bella-donovan"]]}),
}
POS = {
 "supercell": {"finding":{"check_id":"B4_empty_shell"},"verdict":"not_a_defect","reason":"error_or_placeholder_page","urls":["https://supercell.com/404"],"explanation":"This is the site's not-found page, so an empty body costs nothing.","evidence":[{"url":"https://supercell.com/404","type":"field","path":"title","op":"contains","value":"Page not found"}]},
 "muji": {"finding":{"check_id":"A7_site_unreadable"},"verdict":"not_a_defect","reason":"auditor_side_failure","explanation":"robots.txt timed out at the transport level, which says nothing about the site.","evidence":[{"type":"site_note_contains","value":"ReadTimeout"}]},
 "fnac": {"finding":{"check_id":"A7_site_unreadable"},"verdict":"confirm_intent","reason":"access_block_not_bot_specific","explanation":"The refused page is a maintenance page, not a wall aimed at bots.","evidence":[{"url":"https://www.fnac.com/","type":"html_contains","value":"FNAC DARTY - Maintenance"}]},
 "tfl": {"finding":{"check_id":"A9_broken_pages"},"verdict":"not_a_defect","reason":"measurement_wrong","urls":["https://tfl.gov.uk/corporate/about-tfl"],"explanation":"The homepage links to the URL with a trailing slash; the crawl requested it without one.","evidence":[{"url":"https://tfl.gov.uk/","type":"html_contains","value":"href=\"/corporate/about-tfl/\""},{"url":"https://tfl.gov.uk/corporate/about-tfl","type":"field","path":"status","op":"eq","value":404}]},
}
bad = 0
for name, (slug, v) in NEG.items():
    applied, reason, _ = run(name, slug, v)
    bad += applied != 0
    print("NEG", name, "rejected" if applied == 0 else "APPLIED (BAD)", "|", reason)
for name, v in POS.items():
    applied, reason, report = run(name, name, v)
    ok = applied == 1
    # The ranking must agree with the judged findings: no action for a removed finding,
    # and every action's severity equals its finding's.
    by_id = {f["id"]: f for f in report["findings"]}
    ok = ok and all(a["finding_id"] in by_id and a["severity"] == by_id[a["finding_id"]]["severity"]
                    for a in report["prioritized_actions"])
    bad += not ok
    print("POS", name, "applied, ranking consistent" if ok else "FAILED", "|", reason, "| headline:", report["summary"]["headline"][:70])
print("control failures:", bad)
sys.exit(1 if bad else 0)
