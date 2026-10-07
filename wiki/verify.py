#!/usr/bin/env python3
from html.parser import HTMLParser
from pathlib import Path
import json, re, sys

ROOT = Path(__file__).resolve().parent

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.ids=set()
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if 'id' in a: self.ids.add(a['id'])
        if tag == 'a' and 'href' in a: self.links.append(a['href'])

pages = list(ROOT.glob('*.html')) + list((ROOT/'chapters').glob('*.html'))
assert len(list((ROOT/'chapters').glob('*.html'))) == 22, 'expected 22 chapter pages'
errors=[]
for page in pages:
    p=Links(); p.feed(page.read_text())
    for href in p.links:
        if href.startswith(('http:', 'https:', 'mailto:', '#')): continue
        target=(page.parent/href.split('#')[0]).resolve()
        if href and not target.exists(): errors.append(f'{page.relative_to(ROOT)} -> {href}')
assert not errors, 'broken links:\n'+'\n'.join(errors)
idx=json.loads((ROOT/'assets/search-index.json').read_text())
assert len(idx) == 22 and all(x['text'] for x in idx)
for required in ('index.html','search.html','assets/reader.css','assets/reader.js'):
    assert (ROOT/required).exists(), required
assert len(list((ROOT/'assets/diagrams').glob('*.svg'))) == 15
print(f'OK: {len(pages)} pages, 22 chapters, 15 diagrams, {len(idx)} search records')
