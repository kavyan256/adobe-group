import json, re
WORK = "/home/kavyan2/Desktop/adobe/eval-runs/2026-09-13-verdict-prototype/exp/runs/held/pentagram"
b = json.load(open(WORK + "/bundle.json"))
pages = {p['url']: p for p in b['pages']}
html = pages['https://www.pentagram.com/'].get('html', '')
print(len(html))
count = 0
for m in re.finditer(r'<button[^>]*>', html):
    tag = m.group(0)
    if 'aria-label' not in tag and 'aria-labelledby' not in tag:
        after = html[m.end():m.end()+200]
        if not re.search(r'[A-Za-z]{2,}', after.split('<')[0]):
            print('CANDIDATE:', tag[:250])
            print('AFTER:', after[:200])
            count += 1
            if count > 3:
                break
print('total candidates found (capped):', count)
