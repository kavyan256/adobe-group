import json

WORK = "/tmp/claude-1000/-home-kavyan2-Desktop-adobe/661eb840-02a7-4bfc-9a62-3cd624e22178/scratchpad/exp/runs/pilot/supercell"
r = json.load(open(f"{WORK}/report.json"))
ar = r.get("agent_review", {})
print(json.dumps(ar, indent=2))
