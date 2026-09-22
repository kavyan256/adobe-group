import subprocess, sys

WORK = "/tmp/claude-1000/-home-kavyan2-Desktop-adobe/661eb840-02a7-4bfc-9a62-3cd624e22178/scratchpad/exp/runs/pilot/supercell"

out = subprocess.run(
    ["python3", "skills/agent-review-audit/scripts/page_profile.py", f"{WORK}/bundle.json", f"{WORK}/report.json"],
    capture_output=True, text=True,
)
with open(f"{WORK}/profile.json", "w") as f:
    f.write(out.stdout)
print("returncode", out.returncode)
print("stdout_len", len(out.stdout))
print("stderr", out.stderr[:3000])
