#!/usr/bin/env bash
# Finish the pre-registered verdict-layer test (needs Claude usage headroom: ~63 runs, ~$35-45, ~35 min).
set -euo pipefail
cd "$(dirname "$0")/exp"
python3 controls/run_controls.py
DEV=$(python3 -c "import json;g=json.load(open('ground_truth_severe.json'));print(' '.join(sorted({s for v in g.values() for s,*_ in v})))")
HELD=$(python3 -c "import json;g=json.load(open('ground_truth_heldout.json'));print(' '.join(sorted({s for k in ('keep','either','reduce') for s,*_ in g[k]})))")
REP=$(python3 -c "import json;print(' '.join(json.load(open('ground_truth_heldout.json'))['repeat_sites']))")
python3 run_agent.py dev sonnet $DEV --workers 5
python3 run_agent.py held sonnet $HELD --workers 5
python3 run_agent.py repeat sonnet $REP --workers 5
python3 score.py dev held repeat
