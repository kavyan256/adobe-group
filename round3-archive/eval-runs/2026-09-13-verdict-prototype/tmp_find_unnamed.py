import json, re
b = json.load(open('/home/kavyan2/Desktop/adobe/eval-runs/2026-09-13-verdict-prototype/exp/runs/newclaim-test/injected/bundle.json'))
for pg in b['pages']:
    if pg['url'] == 'https://www.msf.org/':
        html = pg['html']
        # find all <button ...>...</button> and <a ...>...</a> (non-greedy, single-line-ish)
        tags = re.findall(r'<button\b[^>]*>.*?</button>', html, re.S)
        tags += re.findall(r'<a\b[^>]*>.*?</a>', html, re.S)
        count = 0
        for tag in tags:
            if 'aria-label' in tag or 'aria-labelledby' in tag or 'title=' in tag:
                continue
            # strip tags to see visible text
            inner = re.sub(r'<[^>]+>', '', tag).strip()
            if inner:
                continue
            if 'alt="' in tag and not re.search(r'alt=""', tag):
                continue
            count += 1
            if count <= 5:
                print(tag[:300])
                print('---')
        print('total candidates', count)
