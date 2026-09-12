#!/usr/bin/env python3
"""Run the scripted audit over every site in sites.json, resumably.

    python3 runner.py [--workers 6] [--max-pages 12]

Each site gets results/<slug>/ with <slug>.report.json, <slug>.bundle.json and
run.json (exit code, wall time, stderr tail). Sites whose report already exists
are skipped, so the run can be interrupted and resumed. Workers never share a
host, and each audit keeps its own polite pacing and robots.txt handling.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parents[1] / "brand-ai-readiness-audit-v4" / "skills" / "audit-orchestrator" / "scripts" / "audit.py"
TIMEOUT_S = 330


def run_one(site: dict, max_pages: int) -> dict:
    out = HERE / "results" / site["slug"]
    out.mkdir(parents=True, exist_ok=True)
    report = out / f"{site['slug']}.report.json"
    if report.exists():
        return {"slug": site["slug"], "skipped": True}
    started = time.monotonic()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run(
            [sys.executable, str(AUDIT), site["url"], "--max-pages", str(max_pages),
             "--bundle", str(out / f"{site['slug']}.bundle.json"), "-o", str(report)],
            capture_output=True, text=True, timeout=TIMEOUT_S, env=env)
        rc, stderr = proc.returncode, proc.stderr
    except subprocess.TimeoutExpired as exc:
        rc, stderr = "timeout", (exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    run = {**site, "rc": rc, "wall_s": round(time.monotonic() - started, 1),
           "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "stderr_tail": stderr.strip().splitlines()[-5:], "report_written": report.exists()}
    (out / "run.json").write_text(json.dumps(run, indent=1, ensure_ascii=False), encoding="utf-8")
    return run


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-pages", type=int, default=12)
    args = ap.parse_args()
    sites = json.loads((HERE / "sites.json").read_text(encoding="utf-8"))
    print(f"{len(sites)} sites, {args.workers} workers, max {args.max_pages} pages, audit={AUDIT}", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, s, args.max_pages): s for s in sites}
        for fut in as_completed(futures):
            done += 1
            r = fut.result()
            if r.get("skipped"):
                print(f"[{done:3}/{len(sites)}] {r['slug']}: already done", flush=True)
            else:
                print(f"[{done:3}/{len(sites)}] {r['slug']}: rc={r['rc']} {r['wall_s']}s report={r['report_written']}", flush=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
