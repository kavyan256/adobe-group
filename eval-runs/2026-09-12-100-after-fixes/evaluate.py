#!/usr/bin/env python3
"""Evaluate the 100-site run: robustness, report integrity, determinism, check behaviour.

    python3 evaluate.py            -> prints a summary and writes evaluation.json

Everything here is mechanical. Whether a finding is TRUE is judged separately by
spot-checking findings against the saved bundles.
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKET = HERE.parents[1] / "brand-ai-readiness-audit-v4"
AUDIT = MARKET / "skills" / "audit-orchestrator" / "scripts" / "audit.py"
SCHEMA = MARKET / "schema" / "audit-report.schema.json"
sys.path.insert(0, str(MARKET / "skills" / "audit-orchestrator" / "scripts"))
sys.dont_write_bytecode = True
from model import SEVERITY_TABLE  # noqa: E402

try:
    import jsonschema
except ImportError:
    jsonschema = None


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def replay(bundle: Path) -> str | None:
    p = subprocess.run([sys.executable, str(AUDIT), "--replay", str(bundle)], capture_output=True,
                       text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    if p.returncode != 0:
        return None
    d = json.loads(p.stdout)
    return json.dumps(d, sort_keys=True)


def main() -> None:
    sites = load(HERE / "sites.json")
    schema = load(SCHEMA)
    ev = {"sites": len(sites), "per_site": {}, "problems": defaultdict(list)}
    status, walls, fired, fired_sev = Counter(), [], Counter(), defaultdict(Counter)
    findings_per_site, category_of = {}, {}
    for s in sites:
        d = HERE / "results" / s["slug"]
        run, rep, bundle = load(d / "run.json"), load(d / f"{s['slug']}.report.json"), d / f"{s['slug']}.bundle.json"
        category_of[s["slug"]] = s["category"]
        row = {"url": s["url"], "category": s["category"]}
        if not run:
            ev["problems"]["not_run"].append(s["slug"]); ev["per_site"][s["slug"]] = row; continue
        row.update(rc=run["rc"], wall_s=run["wall_s"])
        walls.append(run["wall_s"])
        if run["wall_s"] >= 300: ev["problems"]["over_5_minutes"].append((s["slug"], run["wall_s"]))
        if run["rc"] != 0 or not rep:
            ev["problems"]["crash_or_no_report"].append((s["slug"], run["rc"], run["stderr_tail"][-2:]))
            ev["per_site"][s["slug"]] = row; continue
        sm = rep["summary"]
        row.update(run_status=sm["run_status"], pages_ok=rep["coverage"]["pages_ok"], total=sm["total_findings"],
                   checks=sorted({f["check_id"] for f in rep["findings"]}))
        status[sm["run_status"]] += 1
        findings_per_site[s["slug"]] = sm["total_findings"]
        # integrity
        if schema and jsonschema:
            try:
                jsonschema.validate(rep, schema)
            except jsonschema.ValidationError as exc:
                ev["problems"]["schema_invalid"].append((s["slug"], str(exc).splitlines()[0][:160]))
        counts = sum(sm.get(k, 0) for k in ("critical", "high", "medium", "low", "info"))
        if counts != sm["total_findings"]:
            ev["problems"]["counts_do_not_add_up"].append((s["slug"], counts, sm["total_findings"]))
        ids = [f["id"] for f in rep["findings"]]
        if ids != [f"F-{i:03d}" for i in range(1, len(ids) + 1)]:
            ev["problems"]["ids_out_of_order"].append(s["slug"])
        for f in rep["findings"]:
            fired[f["check_id"]] += 1
            fired_sev[f["check_id"]][f["severity"]] += 1
            if len(set(f["affected_urls"])) != len(f["affected_urls"]):
                ev["problems"]["duplicate_affected_urls"].append((s["slug"], f["check_id"]))
            if f["check_id"] not in SEVERITY_TABLE:
                ev["problems"]["unknown_check_id"].append((s["slug"], f["check_id"]))
        same_check = Counter(f["check_id"] for f in rep["findings"])
        for cid, n in same_check.items():
            if n > 3:
                ev["problems"]["same_check_repeated_over_3_times"].append((s["slug"], cid, n))
        # determinism: two replays of the saved bundle must be identical
        if bundle.exists():
            a, b = replay(bundle), replay(bundle)
            if a is None or a != b:
                ev["problems"]["replay_not_deterministic"].append(s["slug"])
        ev["per_site"][s["slug"]] = row
    readable = [sl for sl, r in ev["per_site"].items() if r.get("run_status") in ("complete", "partial")]
    ev["run_status"] = dict(status)
    ev["wall_s"] = {"median": statistics.median(walls) if walls else None, "max": max(walls) if walls else None}
    ev["check_fire_rate_over_readable_sites"] = {
        cid: {"sites": n, "rate": round(n / max(1, len(readable)), 2), "severities": dict(fired_sev[cid])}
        for cid, n in fired.most_common()}
    ev["checks_never_fired"] = sorted(set(SEVERITY_TABLE) - set(fired))
    ev["findings_per_site"] = {"median": statistics.median(findings_per_site.values()) if findings_per_site else None,
                               "max": max(findings_per_site.items(), key=lambda kv: kv[1]) if findings_per_site else None}
    ev["problems"] = {k: v for k, v in ev["problems"].items()}
    (HERE / "evaluation.json").write_text(json.dumps(ev, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: ev[k] for k in ("sites", "run_status", "wall_s", "findings_per_site", "checks_never_fired")}, indent=1))
    print("\nproblems:")
    for k, v in ev["problems"].items():
        print(f"  {k}: {len(v)} -> {v[:6]}")
    print("\ncheck fire rate (readable sites):")
    for cid, v in ev["check_fire_rate_over_readable_sites"].items():
        print(f"  {cid:32} {v['sites']:3} sites ({v['rate']:.0%})  {v['severities']}")


if __name__ == "__main__":
    main()
