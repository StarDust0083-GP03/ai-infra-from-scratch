#!/usr/bin/env python3
from html.parser import HTMLParser
from pathlib import Path
import json, re, sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.ids=[]; self.labels=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if 'id' in a: self.ids.append(a['id'])
        if 'aria-labelledby' in a: self.labels.extend(a['aria-labelledby'].split())
        if tag == 'a' and 'href' in a: self.links.append(a['href'])

pages = list(ROOT.glob('*.html')) + list((ROOT/'chapters').glob('*.html'))
assert len(list((ROOT/'chapters').glob('*.html'))) == 22, 'expected 22 chapter pages'
errors=[]
for page in pages:
    p=Links(); p.feed(page.read_text())
    assert len(p.ids) == len(set(p.ids)), f'duplicate IDs: {page}'
    assert set(p.labels) <= set(p.ids), f'unresolved aria-labelledby: {page}'
    for figure in re.findall(r'<figure[^>]*data-review-figure="[^"]+"[^>]*>(.*?)</figure>', page.read_text(), re.S):
        svg = ET.fromstring(re.search(r'<svg\b.*?</svg>', figure, re.S)[0])
        assert svg.get('role') == 'img' and svg.get('viewBox'), page
        for tag in ('title', 'desc'):
            element = svg.find('{http://www.w3.org/2000/svg}' + tag)
            assert element is not None and element.text, (page, tag)
    for href in p.links:
        if href.startswith(('http:', 'https:', 'mailto:')): continue
        target=(page.parent/href.split('#')[0]).resolve() if href.split('#')[0] else page.resolve()
        if '#' in href and target.exists() and target.suffix == '.html':
            linked = Links(); linked.feed(target.read_text())
            from urllib.parse import unquote
            assert unquote(href.split('#', 1)[1]) in linked.ids, (page, href)
        if href and not target.exists(): errors.append(f'{page.relative_to(ROOT)} -> {href}')
assert not errors, 'broken links:\n'+'\n'.join(errors)
idx=json.loads((ROOT/'assets/search-index.json').read_text())
assert len(idx) == 22 and all(x['text'] for x in idx)
for required in ('index.html','search.html','assets/reader.css','assets/reader.js'):
    assert (ROOT/required).exists(), required
assert len(list((ROOT/'assets/diagrams').glob('*.svg'))) == 15
inline_count = sum(p.read_text().count('data-review-figure=') for p in (ROOT / 'chapters').glob('*.html'))
assert inline_count == 4, f'missing new illustrations: {inline_count}'
print(f'Inline illustrations: {inline_count}, accessible labels and SVG markup checked')
print(f'OK: {len(pages)} pages, 22 chapters, 15 diagrams, {len(idx)} search records')
