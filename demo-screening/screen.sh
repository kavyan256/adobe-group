#!/bin/bash
cd /home/kavyan2/Desktop/adobe/brand-ai-readiness-audit-v4
BASE=/home/kavyan2/Desktop/adobe/demo-screening
for site in "$@"; do
  slug=$(echo "$site" | sed 's|https\?://||; s|www\.||; s|/.*||; s|\.|_|g')
  mkdir -p "$BASE/$slug"
  timeout 180 python3 skills/audit-orchestrator/scripts/audit.py "$site" --max-pages 12 \
      --bundle "$BASE/$slug/bundle.json" -o "$BASE/$slug/report.json" >/dev/null 2>&1
  python3 - "$BASE/$slug/report.json" "$slug" <<'PY'
import json, sys
try:
    r = json.load(open(sys.argv[1])); s = r['summary']
    crit = [f['title'] for f in r['findings'] if f['severity'] == 'critical']
    high = [f['title'] for f in r['findings'] if f['severity'] == 'high']
    print(f"{sys.argv[2]:16} {s['run_status']:9} ok={r['coverage']['pages_ok']:2} "
          f"C{s['critical']} H{s['high']} M{s['medium']} L{s['low']}  {r['coverage']['elapsed_s']}s")
    for t in crit: print(f"     CRITICAL: {t[:70]}")
    for t in high: print(f"     high    : {t[:70]}")
except Exception as e:
    print(f"{sys.argv[2]:16} FAILED ({type(e).__name__})")
PY
done
