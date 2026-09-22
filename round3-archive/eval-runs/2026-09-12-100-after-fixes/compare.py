#!/usr/bin/env python3
"""Compare the baseline 100-site run with the after-fixes run: status and severe findings."""
import json
from collections import Counter, defaultdict
from pathlib import Path
HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "2026-09-12-100"
def load(d, slug):
    p = d / "results" / slug / f"{slug}.report.json"
    return json.loads(p.read_text()) if p.exists() else None
def severe(r):
    return Counter(f["check_id"] for f in (r or {}).get("findings", [])
                   if f["severity"] in ("critical", "high") and f.get("status", "active") == "active")
def all_checks(r):
    return Counter((f["check_id"], f["severity"], f.get("status")) for f in (r or {}).get("findings", []))
spot = defaultdict(list)
for s in json.loads((BASE / "spot_checks.json").read_text()):
    spot[(s["site"], s["check_id"])].append(s["verdict"])
sites = json.loads((HERE / "sites.json").read_text())
out = {"status_changes": [], "severe_removed": [], "severe_added": [], "other_changes": {}}
tally = {"before": Counter(), "after": Counter()}
for s in sites:
    slug = s["slug"]; b, a = load(BASE, slug), load(HERE, slug)
    sb, sa = b["summary"]["run_status"], a["summary"]["run_status"]
    if sb != sa:
        out["status_changes"].append([slug, sb, sa])
    vb, va = severe(b), severe(a)
    for cid in vb: tally["before"][tuple(spot.get((slug, cid)) or ["unchecked"])[0]] += vb[cid]
    for cid in va: tally["after"][tuple(spot.get((slug, cid)) or ["unchecked"])[0]] += va[cid]
    for cid in vb - va: out["severe_removed"].append([slug, cid, (spot.get((slug, cid)) or ["unchecked"])[0]])
    for cid in va - vb: out["severe_added"].append([slug, cid, (spot.get((slug, cid)) or ["unchecked"])[0]])
    cb, ca = all_checks(b), all_checks(a)
    if cb != ca:
        out["other_changes"][slug] = {"gone": [list(k) for k in cb - ca], "new": [list(k) for k in ca - cb]}
out["severe_verdict_tally"] = {k: dict(v) for k, v in tally.items()}
out["severe_totals"] = {"before": sum(sum(severe(load(BASE, s["slug"])).values()) for s in sites),
                        "after": sum(sum(severe(load(HERE, s["slug"])).values()) for s in sites)}
(HERE / "compare.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "other_changes"}, indent=1))
print("sites with any finding change:", len(out["other_changes"]))
