#!/usr/bin/env python3
"""Score agent adjudication runs against the pre-registered criteria.

    python3 score.py DEV_TAG HELDOUT_TAG [REPEAT_TAG]
"""
import json, statistics, sys
from pathlib import Path
import jsonschema

EXP = Path(__file__).resolve().parent
SCHEMA = json.load(open("/home/kavyan2/Desktop/adobe/brand-ai-readiness-audit-v4/schema/audit-report.schema.json"))
ORDER = ["info", "low", "medium", "high", "critical"]


def outcome(tag, slug, cid):
    w = EXP / "runs" / tag / slug
    if not (w / "adjudicated.json").exists():
        return "no_output"
    before = [f for f in json.load(open(w / "report.scripted.json"))["findings"] if f["check_id"] == cid]
    adj = json.load(open(w / "adjudicated.json"))
    after = [f for f in adj["findings"] if f["check_id"] == cid]
    if not before:
        return "absent_in_scripted"
    if not after:
        return "removed"
    b, a = before[0], after[0]
    if (a.get("status") != b.get("status") or ORDER.index(a["severity"]) < ORDER.index(b["severity"])
            or len(a.get("affected_urls") or []) < len(b.get("affected_urls") or [])):
        return "reduced"
    return "kept"


def all_outcomes(tag, slug):
    w = EXP / "runs" / tag / slug
    if not (w / "report.scripted.json").exists():
        return {}
    cids = {f["check_id"] for f in json.load(open(w / "report.scripted.json"))["findings"]
            if ORDER.index(f["severity"]) >= ORDER.index("medium") and f.get("source") != "agent_review"}
    return {c: outcome(tag, slug, c) for c in sorted(cids)}


def main():
    dev, held = sys.argv[1], sys.argv[2]
    rep = sys.argv[3] if len(sys.argv) > 3 else None
    gs, gh = json.load(open(EXP / "ground_truth_severe.json")), json.load(open(EXP / "ground_truth_heldout.json"))
    out, verdict = {}, {}

    o = {k: [(s, c, outcome(dev, s, c)) for s, c, *_ in gs[k]] for k in gs}
    out["dev"] = o
    caught = sum(1 for *_, r in o["knowable_false"] if r in ("reduced", "removed"))
    true_removed = sum(1 for *_, r in o["strict_true"] if r == "removed")
    true_reduced = sum(1 for *_, r in o["strict_true"] if r == "reduced")
    a7_removed = sum(1 for *_, r in o["unknowable_a7"] if r == "removed")
    verdict["1 catch >=7/10"] = (caught, caught >= 7)
    verdict["2 keep: 0 removed, <=1 reduced"] = ((true_removed, true_reduced), true_removed == 0 and true_reduced <= 1)
    verdict["3 unknowable A7 <=1 removed"] = (a7_removed, a7_removed <= 1)

    h = {k: [(s, c, outcome(held, s, c)) for s, c, *_ in gh[k]] for k in ("keep", "either", "reduce")}
    out["heldout"] = h
    match = sum(1 for *_, r in h["keep"] if r == "kept") + sum(1 for *_, r in h["reduce"] if r in ("reduced", "removed")) \
        + sum(1 for *_, r in h["either"] if r in ("kept", "reduced"))
    n = len(h["keep"]) + len(h["reduce"]) + len(h["either"])
    held_true_removed = sum(1 for *_, r in h["keep"] + h["either"] if r == "removed")
    verdict["4 held-out >=80% match, 0 true removed"] = ((match, n, held_true_removed), match / n >= 0.8 and held_true_removed == 0)

    if rep:
        same = total = 0
        diffs = []
        for slug in gh["repeat_sites"]:
            a, b = all_outcomes(dev if (EXP / "runs" / dev / slug).exists() else held, slug), all_outcomes(rep, slug)
            for c in a:
                total += 1
                if a[c] == b.get(c):
                    same += 1
                else:
                    diffs.append((slug, c, a[c], b.get(c)))
        out["stability_diffs"] = diffs
        verdict["5 stability >=85%"] = ((same, total), total and same / total >= 0.85)

    walls, costs, submitted, applied, schema_bad, rejected = [], [], 0, 0, [], []
    for tag in filter(None, (dev, held, rep)):
        for w in sorted((EXP / "runs" / tag).glob("*/result.json")):
            r = json.load(open(w)); walls.append(r["wall_s"]); costs.append(r.get("total_cost_usd") or 0)
            adj = w.parent / "adjudicated.json"
            if adj.exists():
                d = json.load(open(adj)); ar = d.get("agent_review", {})
                submitted += ar.get("verdicts_submitted", 0); applied += ar.get("verdicts_applied", 0)
                rejected += [(w.parent.name, x.get("reason")) for x in ar.get("verdicts_rejected", [])]
                try:
                    jsonschema.validate(d, SCHEMA)
                except jsonschema.ValidationError as e:
                    schema_bad.append((tag, w.parent.name, str(e).splitlines()[0][:120]))
            else:
                schema_bad.append((tag, w.parent.name, "no adjudicated.json"))
    out["rejected_verdicts"] = rejected
    verdict["6 verifier acceptance (applied/submitted)"] = ((applied, submitted), submitted and applied / submitted >= 0.9)
    verdict["7 runtime median<=180 max<=240"] = ((statistics.median(walls) if walls else None, max(walls) if walls else None),
                                                 bool(walls) and statistics.median(walls) <= 180 and max(walls) <= 240)
    verdict["8 schema-valid and produced"] = (schema_bad, not schema_bad)
    out["cost_usd"] = round(sum(costs), 2)
    out["criteria"] = verdict
    (EXP / f"score-{dev}-{held}{'-' + rep if rep else ''}.json").write_text(json.dumps(out, indent=1))
    for k, (val, ok) in verdict.items():
        print(("PASS " if ok else "FAIL ") + k + ": " + json.dumps(val)[:400])
    print("total cost USD:", out["cost_usd"])


if __name__ == "__main__":
    main()
