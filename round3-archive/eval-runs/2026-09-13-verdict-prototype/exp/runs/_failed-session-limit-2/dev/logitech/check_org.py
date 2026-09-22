import json, re
b = json.load(open('bundle.json'))
pages = {pg['url']: pg for pg in b['pages']}
pg = pages['https://www.logitech.com/']
html = pg.get('html', '')
scripts = re.findall(r'<script[^>]+type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', html, re.S)
for s in scripts:
    try:
        d = json.loads(s)
    except Exception:
        continue
    items = d if isinstance(d, list) else [d]
    for item in items:
        if isinstance(item, dict) and str(item.get('@type', '')).lower() == 'organization':
            print(json.dumps(item, indent=2)[:1500])
