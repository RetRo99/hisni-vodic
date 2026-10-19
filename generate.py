#!/usr/bin/env python3
"""Writes one static page per house model (/<maker>-<model>/index.html), the house links in the
catalog of index.html, and sitemap.xml, all from the JSON embedded in index.html. Run after
editing that JSON:  python3 generate.py"""
import datetime, html, json, os, re, unicodedata

SITE = 'https://hisomer.si/'
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

src = open('index.html', encoding='utf-8').read()
DATA_RE = re.compile(r'(<script id="data" type="application/json">)(.*?)(</script>)')
data = json.loads(DATA_RE.search(src).group(2))

ROOF = {'gable': 'dvokapna', 'flat': 'ravna', 'mono': 'enokapna', 'hip': 'štirikapna', 'multi': 'večkapna'}
STYLE = {
    'classic': 'klasična', 'classic timber-glass': 'klasična, les in steklo', 'classic/contemporary': 'klasično-sodobna',
    'classic/modern': 'klasično-moderna', 'contemporary timber-glass': 'sodobna, les in steklo', 'minimalist': 'minimalistična',
    'modern': 'moderna', 'modern (minimalist gable, extended roof)': 'moderna, minimalistična dvokapnica s podaljšano streho',
    'modern / solid wood': 'moderna, masivni les', 'modern alpine/scandinavian': 'moderna alpska oz. skandinavska',
    'modern atrium': 'moderna z atrijem', 'modern cubic': 'moderna kubična', 'modern minimalist glass house': 'moderna minimalistična, veliko stekla',
    'modern timber-glass hybrid': 'moderna, les in steklo', 'modern urban timber-glass': 'moderna urbana, les in steklo',
    'modern villa': 'moderna vila', 'modern-classic': 'moderno-klasična', 'modern/scandinavian': 'moderna skandinavska',
}
FLOORS = {1: ('pritličje', 'pritlična montažna hiša'), 1.5: ('z mansardo', 'montažna hiša z mansardo'),
          2: ('P + 1', 'dvoetažna montažna hiša (pritličje in nadstropje)')}
esc = html.escape


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()).strip('-')


def plural(n, one, two, few, many):
    return one if n == 1 else two if n == 2 else few if n in (3, 4) else many


def eur(n):
    return f'{n:,}'.replace(',', '.') + ' €'


models = [(p, m) for p in data['providers'] for m in p['models']]
for p, m in models:
    m['slug'] = slugify(p['id'] + '-' + m['name'])
slugs = [m['slug'] for _, m in models]
assert len(set(slugs)) == len(slugs), 'duplicate slug'

# Shared look: tokens, base, top bar and the result-card pieces, lifted straight from index.html's <style>.
css = re.search(r'<style>(.*?)</style>', src, re.S).group(1)
CSS = css[css.index(':root {'):css.index('/* ---------- hero')] + '\n'.join(
    l for l in css.splitlines() if l.startswith(('.btn', '.price', '.specs', '.edge', '.facts', '.two', 'footer'))) + '''
.bar { position: static; }
.mark { color: var(--ink); text-decoration: none; }
.page { display: grid; gap: 28px; padding-block: 8px 64px; }
.crumbs a { color: var(--mist); text-decoration: none; }
.crumbs a:hover { color: var(--ink); }
.head { display: flex; justify-content: space-between; align-items: end; flex-wrap: wrap; gap: 18px 30px; }
.head h1 { font-size: clamp(36px, 6vw, 72px); margin-top: 12px; }
.head .prov { color: var(--mist); margin-top: 10px; }
.photo { position: relative; margin: 0; border-radius: var(--r); overflow: hidden; background: var(--dusk); box-shadow: 0 0 0 1px var(--line); aspect-ratio: 600 / 315; }
.photo img { width: 100%; height: 100%; object-fit: cover; display: block; }
.photo figcaption { position: absolute; left: 12px; top: 12px; padding: 6px 10px; border-radius: 999px; background: rgba(10,18,32,.78); font: 500 10px/1 var(--font-data); letter-spacing: .12em; text-transform: uppercase; }
.lede { color: #c9d3e6; font-size: 18px; max-width: 44em; margin: 0; }
.lede p { margin: 0 0 10px; }
h2 { font: 700 22px/1.2 var(--font-display); font-stretch: 105%; margin: 0 0 12px; }
.maker-info p { margin: 0 0 10px; color: #c9d3e6; }
.actions { display: flex; flex-wrap: wrap; gap: 12px; }
.siblings { list-style: none; padding: 0; margin: 0; columns: 3 200px; column-gap: 24px; }
.siblings li { padding: 4px 0; break-inside: avoid; }
.siblings a { color: var(--ink); text-decoration-color: var(--line); text-underline-offset: 3px; }
.siblings a:hover { color: var(--glow); }
@media (max-width: 899px) { .two { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 640px) {
  .specs { grid-template-columns: repeat(6, minmax(0, 1fr)); }
  .specs div { grid-column: span 2; }
  .specs div:nth-child(n+4) { grid-column: span 3; }
  .price { text-align: left; }
  .price span { margin-left: 0; }
  .photo { aspect-ratio: 600 / 380; }
}'''
HEAD_END = re.search(r'<meta name="theme-color".*?</head>', src, re.S).group(0).replace(
    'href="fonts/', 'href="../fonts/').replace('<style>' + css + '</style>', '<style>' + CSS + '</style>').replace('</head>', '')
MARK = re.search(r'<div class="mark">(.*?)</div>', src).group(1)


def page(p, m):
    name = f"{p['name']} {m['name']}"
    url = SITE + m['slug'] + '/'
    img = m.get('image')
    floor_short, floor_long = FLOORS.get(m['floors'], ('—', 'montažna hiša'))
    area = round(m['area_m2']) if m['area_m2'] else None
    roof = ROOF.get(m['roof'])
    price = eur(m['price_eur']) if m['price_eur'] is not None else None
    bed, bath = m['bedrooms'], m['bathrooms']

    s1 = f"{name} je {floor_long}" + (f" s površino {area} m²" if area else '') + f" proizvajalca {p['name']}."
    rooms = [f"{n} {plural(n, w + 'o', w + 'i', w + 'e', w)}" for n, w in ((bed, 'spalnic'), (bath, 'kopalnic')) if n]
    s2 = ('Ima ' + ' in '.join(rooms) + '. ' if rooms else '') + (f"Streha je {roof}. " if roof else '') + \
        (f"Arhitekturni slog: {STYLE[m['style']]}." if m['style'] else '')
    s3 = f"Cena po podatkih proizvajalca: {price} – {m['price_stage']}." if price else \
        'Proizvajalec cene za ta model ne objavlja, ponudbo dobite na povpraševanje.'
    desc_bits = [b for b in [f'{area} m²' if area else '', f"{bed} {plural(bed, 'spalnica', 'spalnici', 'spalnice', 'spalnic')}" if bed else '',
                             f'{roof} streha' if roof else ''] if b]
    desc = f"{name}: montažna hiša" + (', ' + ', '.join(desc_bits) if desc_bits else '') + \
        (f". Cena {price} in kaj vključuje." if price else '. Cena na povpraševanje.') + ' Primerjava s tipskimi hišami drugih slovenskih proizvajalcev.'
    image_abs = SITE + (img.replace('img/', 'img/large/') if img else 'img/large/riko-mila.jpg')
    ld = {'@context': 'https://schema.org', '@type': 'Product', 'name': name, 'url': url, 'image': image_abs, 'description': s1,
          'category': 'Montažna hiša', 'brand': {'@type': 'Brand', 'name': p['name']}}
    if price:
        ld['offers'] = {'@type': 'Offer', 'price': m['price_eur'], 'priceCurrency': 'EUR', 'url': url}
    cell = lambda k, v: f'<div><dt>{k}</dt><dd>{v}</dd></div>'
    facts = [f for f in [p.get('construction') and 'Konstrukcija: ' + p['construction'], p.get('energy_class') and 'Energija: ' + p['energy_class'],
                         p.get('build_time') and 'Gradnja: ' + p['build_time'],
                         p.get('warranty_years') and f"Garancija na konstrukcijo: {p['warranty_years']} let"] if f]
    siblings = [o for o in p['models'] if o is not m]
    site = re.sub(r'^https?://(www\.)?', '', p.get('website', '')).rstrip('/')
    ld_json = json.dumps(ld, ensure_ascii=False).replace('</', '<\\/')
    big = img.replace('img/', 'img/large/') if img else ''
    photo = (f'<figure class="photo"><img src="../{esc(img)}" srcset="../{esc(img)} 720w, ../{esc(big)} 1400w" '
             f'sizes="(min-width: 1240px) 1208px, 100vw" alt="{esc(name)}"><figcaption>Foto: {esc(p["name"])}</figcaption></figure>') if img else ''
    maker_link = f'<p><a href="{esc(p["website"])}" target="_blank" rel="noopener">{esc(site)} ↗</a></p>' if site else ''
    facts_html = '<ul class="facts">' + ''.join(f'<li>{esc(f)}</li>' for f in facts) + '</ul>' if facts else ''
    sib_html = (f'<section><h2>Druge hiše proizvajalca {esc(p["name"])}</h2><ul class="siblings">' +
                ''.join(f'<li><a href="../{o["slug"]}/">{esc(o["name"])}</a></li>' for o in siblings) + '</ul></section>') if siblings else ''
    note = ' Opomba: ' + esc(', '.join(m['flags'])) + '.' if m['flags'] else ''
    stage = esc(m['price_stage']) if price else 'Proizvajalec cene ne objavlja.'
    title = f"{name} – cena, tloris, m² · Hišni vodič"
    return f'''<!doctype html>
<html lang="sl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(name)} – cena in lastnosti">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="Hišni vodič">
<meta property="og:locale" content="sl_SI">
<meta property="og:image" content="{image_abs}">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{ld_json}</script>
{HEAD_END}</head>
<body>
<div class="bar"><div class="wrap">
  <a class="mark" href="../">{MARK}</a>
  <nav><a href="../#kviz">Kviz</a><a href="../#katalog">Katalog</a></nav>
</div></div>
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / <a href="../#katalog">Katalog</a> / {esc(p['name'])}</div>
    <div class="head">
      <div><h1 class="display">{esc(name)}</h1><div class="prov">Montažna hiša · {esc(p['name'])}</div></div>
      <div class="price"><b>{price or 'Na povpraševanje'}</b><span>{stage}</span></div>
    </div>
  </div>
  {photo}
  <dl class="specs">{cell('Etaže', floor_short)}{cell('Površina', f'{area} m²' if area else '—')}{cell('Spalnice', bed or '—')}{cell('Kopalnice', bath or '—')}{cell('Streha', roof or '—')}</dl>
  <div class="lede"><p>{esc(s1)} {esc(s2)}</p><p>{esc(s3)}{note} Tloris, opis in aktualno ponudbo si oglejte pri proizvajalcu.</p></div>
  <div class="actions">
    <a class="btn glow" href="{SITE}#kviz">Ali vam pristaja? Rešite kviz <span class="arrow">→</span></a>
    <a class="btn line" href="{esc(m['url'])}" target="_blank" rel="noopener">Tloris in podrobnosti pri proizvajalcu ↗</a>
  </div>
  <div class="two">
    <section class="maker-info"><h2>O proizvajalcu {esc(p['name'])}</h2><p>{esc(p.get('description', ''))}</p>{maker_link}</section>
    <div class="edge"><div class="eyebrow">Prednost proizvajalca {esc(p['name'])}</div>{esc(p.get('edge') or '')}{facts_html}</div>
  </div>
  {sib_html}
</main>
<footer><div class="wrap"><p>Podatki so zbrani s spletnih strani in ponudbenih brošur proizvajalcev ({esc(data['collected'])}). Cene so informativne; pred odločitvijo preverite aktualno ponudbo pri proizvajalcu. Hišni vodič ni povezan s proizvajalci.</p></div></footer>
</body>
</html>
'''


# shortcut: pages of models removed from the JSON are not deleted; delete their folders by hand.
for p, m in models:
    os.makedirs(m['slug'], exist_ok=True)
    open(os.path.join(m['slug'], 'index.html'), 'w', encoding='utf-8').write(page(p, m))

# index.html: slugs into the data (the catalog JS links to them) and a static link list crawlers see without JS.
links = ''.join(f'<div><h3>{esc(p["name"])}</h3><ul>' + ''.join(f'<li><a href="{m["slug"]}/">{esc(m["name"])}</a></li>' for m in p['models']) + '</ul></div>'
                for p in data['providers'])
src = DATA_RE.sub(lambda mo: mo.group(1) + json.dumps(data, ensure_ascii=False) + mo.group(3), src)
src = re.sub(r'(<!-- model-links -->).*?(<!-- /model-links -->)', lambda mo: mo.group(1) + links + mo.group(2), src, flags=re.S)
open('index.html', 'w', encoding='utf-8').write(src)

today = datetime.date.today().isoformat()
locs = [SITE] + [SITE + s + '/' for s in slugs]
open('sitemap.xml', 'w', encoding='utf-8').write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
                                                  ''.join(f'  <url><loc>{l}</loc><lastmod>{today}</lastmod></url>\n' for l in locs) + '</urlset>\n')

assert len(slugs) == len(models) and all(os.path.isfile(l[len(SITE):] + 'index.html') for l in locs) and src.count('<li><a href="') >= len(models)
print(f'{len(slugs)} pages, {len(locs)} sitemap URLs')
