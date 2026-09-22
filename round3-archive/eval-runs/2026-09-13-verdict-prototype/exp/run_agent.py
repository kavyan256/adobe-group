#!/usr/bin/env python3
"""Run a headless general agent on the prototype skill over saved bundles.

    python3 run_agent.py TAG MODEL slug [slug ...] [--workers N]

Each run gets runs/TAG/<slug>/ with bundle.json, report.json (scripted), the agent's
claims.json, adjudicated.json and result.json (wall time, cost, turns, denials).
Resumable: a slug with result.json is skipped. No web access is allowed.
"""
import hashlib, json, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EXP = Path(__file__).resolve().parent
PROTO = EXP.parent / "v5-proto"
RESULTS = Path("/home/kavyan2/Desktop/adobe/eval-runs/2026-09-12-100-after-fixes/results")
PROMPT = """You are a general AI agent auditing the website {site} with the Agent Skill Marketplace in the current directory (its root holds marketplace.json).
The crawl and the scripted audit have already run. WORK is {work}; it holds bundle.json and report.json. Do not fetch anything from the web.
Carry out skills/agent-review-audit/SKILL.md, writing WORK as {work}. Run its scripts as written there, from the current directory.
You are done when step 5 has rewritten {work}/report.json. Then reply with one line: how many verdicts, claims and fixes were applied, and how many were rejected."""
# A realistic agent shell: python3 and read-only text tools, file edits accepted inside
# the working directories. No web tools and no network commands.
TOOLS = ["Read", "Write", "Edit", "Glob", "Grep",
         "Bash(python3:*)", "Bash(cat:*)", "Bash(ls:*)", "Bash(wc:*)", "Bash(head:*)",
         "Bash(tail:*)", "Bash(grep:*)", "Bash(jq:*)", "Bash(echo:*)", "Bash(cd:*)", "Bash(pwd)"]
DISALLOWED = ["WebFetch", "WebSearch", "Bash(curl:*)", "Bash(wget:*)"]


def tree_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(PROTO.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(str(p.relative_to(PROTO)).encode()); h.update(p.read_bytes())
    return h.hexdigest()[:16]


def run(tag: str, model: str, slug: str):
    work = EXP / "runs" / tag / slug
    if (work / "result.json").exists():
        return slug, "skipped"
    work.mkdir(parents=True, exist_ok=True)
    shutil.copy(RESULTS / slug / f"{slug}.bundle.json", work / "bundle.json")
    shutil.copy(RESULTS / slug / f"{slug}.report.json", work / "report.json")
    shutil.copy(work / "report.json", work / "report.scripted.json")
    site = json.loads((work / "report.json").read_text())["site"]
    cmd = ["claude", "-p", PROMPT.format(site=site, work=work), "--model", model,
           "--output-format", "json", "--add-dir", str(work), "--max-budget-usd", "2",
           "--permission-mode", "acceptEdits", "--disallowedTools", *DISALLOWED,
           "--allowedTools", *TOOLS]
    t = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=PROTO, capture_output=True, text=True, timeout=900,
                           env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
        stdout, stderr, rc = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, rc = "", "timeout", "timeout"
    wall = round(time.monotonic() - t, 1)
    # The final report is report.json once the agent's claims file was applied to it.
    try:
        final = json.loads((work / "report.json").read_text())
        if "verdicts_submitted" in (final.get("agent_review") or {}):
            shutil.copy(work / "report.json", work / "adjudicated.json")
    except Exception:
        pass
    try:
        out = json.loads(stdout)
    except Exception:
        out = {"raw_stdout": stdout[-2000:]}
    res = {"slug": slug, "tag": tag, "model": model, "wall_s": wall, "rc": rc, "stderr": stderr[-1500:],
           "adjudicated": (work / "adjudicated.json").exists(),
           **{k: out.get(k) for k in ("is_error", "subtype", "num_turns", "duration_ms",
                                      "total_cost_usd", "result", "permission_denials", "raw_stdout")}}
    (work / "result.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    return slug, f"{wall}s ${res.get('total_cost_usd')} adjudicated={res['adjudicated']} denials={len(res.get('permission_denials') or [])}"


def main():
    args = sys.argv[1:]
    workers = 5
    if "--workers" in args:
        i = args.index("--workers"); workers = int(args[i + 1]); del args[i:i + 2]
    tag, model, slugs = args[0], args[1], args[2:]
    before = tree_hash()
    with ThreadPoolExecutor(workers) as ex:
        for slug, msg in ex.map(lambda s: run(tag, model, s), slugs):
            print(f"[{tag}] {slug}: {msg}", flush=True)
    after = tree_hash()
    print(f"prototype tree unchanged: {before == after} ({before} -> {after})", flush=True)


if __name__ == "__main__":
    main()
