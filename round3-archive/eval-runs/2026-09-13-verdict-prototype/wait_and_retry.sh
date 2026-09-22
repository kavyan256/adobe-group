#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/exp"
echo "WAITING: sleeping until 16:00 Asia/Kolkata (session limit reset)"
while true; do
  now=$(TZ=Asia/Kolkata date +%H:%M)
  now_min=$((10#$(TZ=Asia/Kolkata date +%H)*60 + 10#$(TZ=Asia/Kolkata date +%M)))
  if [ "$now_min" -ge $((16*60)) ]; then break; fi
  sleep 300
done
echo "TIME REACHED: $(TZ=Asia/Kolkata date), probing session availability"

# Probe: wait for a real reply, retrying every 2 min for up to 30 min past reset
probe_ok=0
for i in $(seq 1 15); do
  out=$(timeout 60 claude -p "Reply with only: ok" --model sonnet --output-format json 2>&1)
  if echo "$out" | grep -q '"result": *"ok"'; then
    probe_ok=1; echo "PROBE OK on attempt $i"; break
  fi
  echo "PROBE FAILED attempt $i: $(echo "$out" | head -c 200)"
  sleep 120
done
if [ "$probe_ok" != "1" ]; then
  echo "GIVING UP: session still limited after retries"
  exit 1
fi

DEV=$(python3 -c "import json;g=json.load(open('ground_truth_severe.json'));print(' '.join(sorted({s for v in g.values() for s,*_ in v})))")
HELD=$(python3 -c "import json;g=json.load(open('ground_truth_heldout.json'));print(' '.join(sorted({s for k in ('keep','either','reduce') for s,*_ in g[k]})))")
REP=$(python3 -c "import json;print(' '.join(json.load(open('ground_truth_heldout.json'))['repeat_sites']))")

echo "RUNNING: dev set (resumable, skips completed)"
python3 run_agent.py dev sonnet $DEV --workers 5
echo "RUNNING: held-out set"
python3 run_agent.py held sonnet $HELD --workers 5
echo "RUNNING: repeat set"
python3 run_agent.py repeat sonnet $REP --workers 5
echo "SCORING"
python3 score.py dev held repeat
echo "EXPERIMENT COMPLETE"
