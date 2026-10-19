#!/usr/bin/env python3
"""Writes one static page per house model (/<maker>-<model>/index.html), the price guide
(/cena-montazne-hise/), the house links in the catalog of index.html, and sitemap.xml, all from the
JSON embedded in index.html. Run after editing that JSON:  python3 generate.py"""
import collections, datetime, glob, html, json, os, re, statistics, unicodedata

SITE = 'https://hisomer.si/'
GUIDE = 'cena-montazne-hise'
PLANS = 'tlorisi-montaznih-his'
CHEAP = 'najcenejse-montazne-hise'
SMALL = 'majhne-montazne-hise'
COMPARE = 'primerjava'
COSTS = 'koliko-stane-gradnja-hise'
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
.mark { color: var(--ink); text-decoration: none; white-space: nowrap; }
@media (max-width: 420px) { .bar nav { gap: 12px; font-size: 13px; } }
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
.plans { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr)); gap: 14px; }
.plans a { display: block; border-radius: var(--r); overflow: hidden; background: #fff; box-shadow: 0 0 0 1px var(--line); }
.plans img { width: 100%; height: auto; display: block; }
.credit-line { font-size: 13px; color: var(--mist); margin: 10px 0 0; }
.sim { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 14px; }
@media (min-width: 700px) { .sim { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
.sim a { display: block; border-radius: var(--r); overflow: hidden; background: var(--dusk); box-shadow: 0 0 0 1px var(--line); color: var(--ink); text-decoration: none; }
.sim a:hover { box-shadow: 0 0 0 1px var(--glow); }
.sim .pic { aspect-ratio: 600 / 340; background: var(--slate); }
.sim img { width: 100%; height: 100%; object-fit: cover; display: block; }
.sim span { display: block; padding: 10px 14px 14px; font-size: 14px; color: var(--mist); }
.sim b { display: block; color: var(--ink); font-size: 15px; margin-bottom: 2px; }
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
BAR = f'''<div class="bar"><div class="wrap">
  <a class="mark" href="../">{MARK}</a>
  <nav><a href="../#kviz">Kviz</a><a href="../#katalog">Katalog</a><a href="../{GUIDE}/">Cene</a><a href="../{PLANS}/">Tlorisi</a></nav>
</div></div>'''
FOOT = (f'<footer><div class="wrap"><p>Podatki so zbrani s spletnih strani in ponudbenih brošur proizvajalcev ({esc(data["collected"])}). '
        'Cene so informativne; pred odločitvijo preverite aktualno ponudbo pri proizvajalcu. Hišni vodič ni povezan s proizvajalci.</p>'
        f'<nav aria-label="Vodiči"><a href="../{GUIDE}/">Cene montažnih hiš</a><a href="../{CHEAP}/">Najcenejše hiše</a><a href="../{SMALL}/">Majhne hiše</a>'
        f'<a href="../{COSTS}/">Stroški gradnje</a><a href="../{PLANS}/">Tlorisi</a><a href="../{COMPARE}/">Primerjava</a></nav></div></footer>\n<script src="../compare.js"></script>')


def head(title, og_title, desc, url, image, ld):
    ld_json = json.dumps(ld, ensure_ascii=False).replace('</', '<\\/')
    return f'''<!doctype html>
<html lang="sl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(og_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="Hišni vodič">
<meta property="og:locale" content="sl_SI">
<meta property="og:image" content="{image}">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{ld_json}</script>
{HEAD_END}</head>'''


def figure(img, alt, maker):
    big = img.replace('img/', 'img/large/') if img else ''
    return (f'<figure class="photo"><img src="../{esc(img)}" srcset="../{esc(img)} 720w, ../{esc(big)} 1400w" '
            f'sizes="(min-width: 1240px) 1208px, 100vw" alt="{esc(alt)}"><figcaption>Foto: {esc(maker)}</figcaption></figure>') if img else ''


def maker_bits(p):
    """The maker's website link and its facts list, shared by house and maker pages."""
    facts = [f for f in [p.get('construction') and 'Konstrukcija: ' + p['construction'], p.get('energy_class') and 'Energija: ' + p['energy_class'],
                         p.get('build_time') and 'Gradnja: ' + p['build_time'],
                         p.get('warranty_years') and f"Garancija na konstrukcijo: {p['warranty_years']} let"] if f]
    site = re.sub(r'^https?://(www\.)?', '', p.get('website', '')).rstrip('/')
    return (f'<p><a href="{esc(p["website"])}" target="_blank" rel="noopener">{esc(site)} ↗</a></p>' if site else '',
            '<ul class="facts">' + ''.join(f'<li>{esc(f)}</li>' for f in facts) + '</ul>' if facts else '')


def house_plans(m):
    """Floor plans img/tloris/<slug>-1.jpg, -2.jpg ... (ground floor first), downloaded from the maker's page."""
    return sorted(glob.glob(f"img/tloris/{m['slug']}-*.jpg"), key=lambda f: int(re.search(r'-(\d+)\.jpg$', f).group(1)))


PLAN_FLOOR = {('rihter-hisa-162', 2): 'kleti'}  # plans that break the ground-floor-then-upper-floor order


def plan_alt(m, name, i, count):
    floor = PLAN_FLOOR.get((m['slug'], i)) or (
        ('pritličja' if m['floors'] == 1 else '') if count == 1 else
        'pritličja' if i == 1 else 'mansarde' if m['floors'] == 1.5 else 'nadstropja')
    return f"Tloris{' ' + floor if floor else ''} – {name}" + (f", {round(m['area_m2'])} m²" if m['area_m2'] else '')


def similar(p, m, count=4):
    """The closest house of each other maker (same floors, nearest size, same roof as a tie-break), best `count` of those."""
    if not m['area_m2']:
        return []
    def gap(o):
        return abs(o['area_m2'] - m['area_m2']) / m['area_m2'] + (0 if o['floors'] == m['floors'] else .25) + (0 if o['roof'] == m['roof'] else .05)
    best = [min(((op, o) for o in op['models'] if o['area_m2']), key=lambda t: gap(t[1]), default=None) for op in data['providers'] if op is not p]
    return sorted((t for t in best if t), key=lambda t: gap(t[1]))[:count]


def page(p, m):
    name = f"{p['name']} {m['name']}"
    url = SITE + m['slug'] + '/'
    img = m.get('image')
    floor_short, floor_long = FLOORS.get(m['floors'], ('—', 'montažna hiša'))
    area = round(m['area_m2']) if m['area_m2'] else None
    roof = ROOF.get(m['roof'])
    price = eur(m['price_eur']) if m['price_eur'] is not None else None
    bed, bath = m['bedrooms'], m['bathrooms']
    plans = house_plans(m)

    s1 = f"{name} je {floor_long}" + (f" s površino {area} m²" if area else '') + f" proizvajalca {p['name']}."
    rooms = [f"{n} {plural(n, w + 'o', w + 'i', w + 'e', w)}" for n, w in ((bed, 'spalnic'), (bath, 'kopalnic')) if n]
    s2 = ('Ima ' + ' in '.join(rooms) + '. ' if rooms else '') + (f"Streha je {roof}. " if roof else '') + \
        (f"Arhitekturni slog: {STYLE[m['style']]}." if m['style'] else '')
    s3 = f"Cena po podatkih proizvajalca: {price} – {m['price_stage']}." if price else \
        'Proizvajalec cene za ta model ne objavlja, ponudbo dobite na povpraševanje.'
    desc_bits = [b for b in [f'{area} m²' if area else '', f"{bed} {plural(bed, 'spalnica', 'spalnici', 'spalnice', 'spalnic')}" if bed else '',
                             f'{roof} streha' if roof else ''] if b]
    desc = f"{name}: montažna hiša" + (', ' + ', '.join(desc_bits) if desc_bits else '') + \
        (f". Cena {price} in kaj vključuje." if price else '. Cena na povpraševanje.') + \
        (' Tloris in primerjava' if plans else ' Primerjava') + ' s tipskimi hišami drugih slovenskih proizvajalcev.'
    image_abs = SITE + (img.replace('img/', 'img/large/') if img else 'img/large/riko-mila.jpg')
    ld = {'@context': 'https://schema.org', '@type': 'Product', 'name': name, 'url': url, 'image': image_abs, 'description': s1,
          'category': 'Montažna hiša', 'brand': {'@type': 'Brand', 'name': p['name']}}
    if price:
        ld['offers'] = {'@type': 'Offer', 'price': m['price_eur'], 'priceCurrency': 'EUR', 'url': url}
    cell = lambda k, v: f'<div><dt>{k}</dt><dd>{v}</dd></div>'
    siblings = [o for o in p['models'] if o is not m]
    photo = figure(img, name, p['name'])
    maker_link, facts_html = maker_bits(p)
    sim = similar(p, m)
    sim_html = (f'<section><h2>Podobne hiše drugih proizvajalcev</h2><div class="sim">' + ''.join(
        f'<a href="../{o["slug"]}/"><div class="pic">' + (f'<img src="../{esc(o["image"])}" alt="" loading="lazy">' if o.get('image') else '') +
        f'</div><span><b>{esc(op["name"])} {esc(o["name"])}</b>{round(o["area_m2"])} m² · {FLOORS.get(o["floors"], ("—",))[0]} · '
        f'{eur(o["price_eur"]) if o["price_eur"] else "cena na povpraševanje"}</span></a>' for op, o in sim) + '</div></section>') if sim else ''
    sib_html = (f'<section><h2>Druge hiše proizvajalca {esc(p["name"])}</h2><ul class="siblings">' +
                ''.join(f'<li><a href="../{o["slug"]}/">{esc(o["name"])}</a></li>' for o in siblings) + '</ul></section>') if siblings else ''
    note = ' Opomba: ' + esc(', '.join(m['flags'])) + '.' if m['flags'] else ''
    stage = esc(m['price_stage']) if price else 'Proizvajalec cene ne objavlja.'
    plans_html = ('<section><h2>Tloris</h2><div class="plans">' + ''.join(
        f'<a href="../{f}"><img src="../{f}" alt="{esc(plan_alt(m, name, i, len(plans)))}" loading="lazy"></a>'
        for i, f in enumerate(plans, 1)) + f'</div><p class="credit-line">Tloris: {esc(p["name"])}, '
        f'<a href="{esc(m["url"])}" target="_blank" rel="noopener">stran hiše pri proizvajalcu ↗</a> · <a href="../{PLANS}/">Vsi tlorisi</a></p></section>') if plans else ''
    title = f"{name} – cena, tloris, m² · Hišni vodič"
    costs_link = f'<a class="btn line" href="../{COSTS}/#h={m["slug"]}">Izračunaj celotne stroške gradnje</a>' if price else ''
    return f'''{head(title, name + ' – cena in lastnosti', desc, url, image_abs, ld)}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / <a href="../#katalog">Katalog</a> / <a href="../{p['id']}/">{esc(p['name'])}</a></div>
    <div class="head">
      <div><h1 class="display">{esc(name)}</h1><div class="prov">Montažna hiša · {esc(p['name'])}</div></div>
      <div class="price"><b>{price or 'Na povpraševanje'}</b><span>{stage}</span></div>
    </div>
  </div>
  {photo}
  <dl class="specs">{cell('Etaže', floor_short)}{cell('Površina', f'{area} m²' if area else '—')}{cell('Spalnice', bed or '—')}{cell('Kopalnice', bath or '—')}{cell('Streha', roof or '—')}</dl>
  <div class="lede"><p>{esc(s1)} {esc(s2)}</p><p>{esc(s3)}{note} {'Opis' if plans else 'Tloris, opis'} in aktualno ponudbo si oglejte pri proizvajalcu. <a href="../{GUIDE}/">Primerjajte cene vseh proizvajalcev</a>.</p></div>
  <div class="actions">
    <a class="btn glow" href="{SITE}#kviz">Ali vam pristaja? Rešite kviz <span class="arrow">→</span></a>
    <a class="btn line" href="{esc(m['url'])}" target="_blank" rel="noopener">{'Podrobnosti' if plans else 'Tloris in podrobnosti'} pri proizvajalcu ↗</a>
    <button type="button" class="btn line cmp" data-slug="{m['slug']}">+ Primerjaj</button>{costs_link}
  </div>
  {plans_html}
  <div class="two">
    <section class="maker-info"><h2>O proizvajalcu {esc(p['name'])}</h2><p>{esc(p.get('description', ''))}</p>{maker_link}</section>
    <div class="edge"><div class="eyebrow">Prednost proizvajalca {esc(p['name'])}</div>{esc(p.get('edge') or '')}{facts_html}</div>
  </div>
  {sim_html}
  {sib_html}
</main>
{FOOT}
</body>
</html>
'''


TABLE_CSS = '''
.page > * { min-width: 0; }
.scroll { position: relative; overflow-x: auto; border-radius: var(--r); box-shadow: 0 0 0 1px var(--line); }
.tbl { width: 100%; border-collapse: collapse; font-size: 15px; }
.tbl th, .tbl td { text-align: left; padding: 11px 14px; border-bottom: 1px solid var(--line); vertical-align: top; }
.tbl tr:last-child > * { border-bottom: 0; }
.tbl thead th { font: 500 10px/1.3 var(--font-data); letter-spacing: .12em; text-transform: uppercase; color: var(--mist); white-space: nowrap; }
.tbl tbody th { font-weight: 600; white-space: nowrap; }
.tbl .n { font-family: var(--font-data); font-size: 14px; white-space: nowrap; }
.tbl .stage { color: var(--mist); font-size: 13px; min-width: 260px; }
.tbl td:first-child { min-width: 170px; }
.tbl a { color: var(--ink); text-decoration-color: var(--line); text-underline-offset: 3px; }
.tbl a:hover { color: var(--glow); }
.points { margin: 0; padding-left: 20px; color: #c9d3e6; display: grid; gap: 10px; max-width: 48em; }
.points b { color: var(--ink); }
'''


def thead(*cols):
    return '<thead><tr>' + ''.join(f'<th scope="col">{c}</th>' for c in cols) + '</tr></thead>'


YEAR = re.search(r'\d{4}', data['collected']).group(0)


def and_join(names):
    return ', '.join(names[:-1]) + ' in ' + names[-1] if len(names) > 1 else names[0]


def guide():
    url = SITE + GUIDE + '/'
    per_m2 = lambda m: m['price_eur'] / m['area_m2']
    priced = [(p, m) for p, m in models if m['price_eur'] and m['area_m2']]
    lo = min(priced, key=lambda pm: pm[1]['price_eur'])
    hi = max(priced, key=lambda pm: pm[1]['price_eur'])
    med_m2 = eur(round(statistics.median(per_m2(m) for _, m in priced))) + '/m²'
    link = lambda p, m: f'<a href="../{m["slug"]}/">{esc(p["name"])} {esc(m["name"])}</a>'
    n = lambda m: f'<td class="n">{m}</td>'

    rows, stages, unpublished = [], {}, []
    for p in data['providers']:
        ms = [m for m in p['models'] if m['price_eur'] and m['area_m2']]
        count = n(f"{len(ms)} / {len(p['models'])}")
        if not ms:
            unpublished.append(p['name'])
            rows.append(f'<tr><th scope="row"><a href="../{p["id"]}/">{esc(p["name"])}</a></th>{count}<td colspan="3">—</td>'
                        '<td class="stage">Cen ne objavlja, ponudba na povpraševanje.</td></tr>')
            continue
        stage = collections.Counter(m['price_stage'] for m in ms).most_common(1)[0][0]
        stages[p['name']] = stage.lower()
        rows.append(f'<tr><th scope="row"><a href="../{p["id"]}/">{esc(p["name"])}</a></th>{count}'
                    f'{n(eur(min(m["price_eur"] for m in ms)))}{n(eur(max(m["price_eur"] for m in ms)))}'
                    f'{n(eur(round(statistics.median(per_m2(m) for m in ms))) + "/m²")}<td class="stage">{esc(stage)}</td></tr>')

    bands = []
    for a, b, label in ((0, 100, 'do 100 m²'), (100, 140, '100–140 m²'), (140, 10 ** 4, '140 m² in več')):
        ms = [m for _, m in priced if a <= m['area_m2'] < b]
        if ms:
            bands.append(f'<tr><th scope="row">{label}</th>{n(len(ms))}{n(eur(min(m["price_eur"] for m in ms)))}'
                         f'{n(eur(round(statistics.median(m["price_eur"] for m in ms))))}{n(eur(round(statistics.median(per_m2(m) for m in ms))) + "/m²")}</tr>')
    cheapest = ''.join(f'<tr><td>{link(p, m)}</td>{n(str(round(m["area_m2"])) + " m²")}{n(eur(m["price_eur"]))}{n(eur(round(per_m2(m))) + "/m²")}</tr>'
                       for p, m in sorted(priced, key=lambda pm: pm[1]['price_eur'])[:10])

    verb = lambda names, one, two, many: one if len(names) == 1 else two if len(names) == 2 else many
    pick = lambda *keys: [k for k, s in stages.items() if any(x in s for x in keys)]
    no_slab, subsidy, from_price = pick('brez temeljne plošče'), pick('subvencij', 'popust'), pick('"od"', 'že od', 'izhodiščn')
    points = ['<li><b>Kaj pomeni »na ključ«.</b> Večina proizvajalcev navaja ceno vseljive hiše, a paketi se razlikujejo po opremi '
              '(tla, kopalnice, ogrevanje, prezračevanje). Primerjajte popis del, ne le končne številke.</li>']
    if no_slab:
        points.append(f'<li><b>Temeljna plošča.</b> Ni vključena v ceno, ki jo {verb(no_slab, "navaja", "navajata", "navajajo")} {and_join(no_slab)}.</li>')
    if subsidy:
        points.append(f'<li><b>Subvencije in popusti.</b> {and_join(subsidy)} {verb(subsidy, "navaja", "navajata", "navajajo")} ceno, '
                      'ki je že zmanjšana za subvencijo Eko sklada oziroma popuste, zato je videti nižja.</li>')
    if from_price:
        points.append(f'<li><b>Cene »od«.</b> {and_join(from_price)} {verb(from_price, "objavlja", "objavljata", "objavljajo")} '
                      'izhodiščne cene za osnovno izvedbo; dejanska ponudba je lahko višja.</li>')
    points.append('<li><b>Kaj običajno ni v ceni.</b> Zemljišče, projektna dokumentacija in gradbeno dovoljenje, komunalni prispevek in priključki, '
                  'zemeljska dela ter zunanja ureditev. Preverite v ponudbi.</li>')
    if unpublished:
        points.append(f'<li><b>Brez objavljenih cen.</b> {and_join(unpublished)} {verb(unpublished, "cen tipskih hiš ne objavlja", "cen tipskih hiš ne objavljata", "cen tipskih hiš ne objavljajo")}; '
                      'ponudbo dobite na povpraševanje.</li>')

    h1 = f'Koliko stane montažna hiša v {YEAR}?'
    desc = (f'Cene {len(priced)} tipskih montažnih hiš slovenskih proizvajalcev: od {eur(lo[1]["price_eur"])} do {eur(hi[1]["price_eur"])}, '
            f'mediana {med_m2}. Primerjava po proizvajalcih in velikosti ter kaj cena vključuje.')
    ld = {'@context': 'https://schema.org', '@type': 'Article', 'headline': h1, 'description': desc, 'inLanguage': 'sl', 'url': url,
          'dateModified': datetime.date.today().isoformat(), 'image': SITE + 'img/large/riko-mila.jpg',
          'author': {'@type': 'Organization', 'name': 'Hišni vodič', 'url': SITE}}
    return f'''{head(f'Cena montažne hiše {YEAR}: primerjava proizvajalcev · Hišni vodič', h1, desc, url, ld['image'], ld).replace('</head>', '<style>' + TABLE_CSS + '</style></head>')}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / Cene</div>
    <div class="head"><div><h1 class="display">{h1}</h1><div class="prov">Primerjava cen tipskih hiš · podatki: {esc(data['collected'])}</div></div></div>
  </div>
  <div class="lede"><p>Med {len(priced)} tipskimi montažnimi hišami slovenskih proizvajalcev z objavljeno ceno je najcenejša {link(*lo)} ({eur(lo[1]['price_eur'])}),
    najdražja pa {link(*hi)} ({eur(hi[1]['price_eur'])}). Srednja cena (mediana) je <b>{med_m2}</b> bivalne površine.</p>
    <p>Cene niso neposredno primerljive, ker jih proizvajalci navajajo za različne pakete. V tabeli je za vsakega navedeno, kaj cena vključuje.</p></div>
  <section><h2>Cene po proizvajalcih</h2><div class="scroll"><table class="tbl">{thead('Proizvajalec', 'Hiš s ceno', 'Od', 'Do', 'Mediana na m²', 'Kaj cena vključuje')}<tbody>{''.join(rows)}</tbody></table></div></section>
  <section><h2>Cena glede na velikost</h2><div class="scroll"><table class="tbl">{thead('Površina', 'Hiš', 'Najcenejša', 'Mediana', 'Mediana na m²')}<tbody>{''.join(bands)}</tbody></table></div></section>
  <section><h2>Najcenejše montažne hiše</h2><div class="scroll"><table class="tbl">{thead('Hiša', 'Površina', 'Cena', 'Na m²')}<tbody>{cheapest}</tbody></table></div></section>
  <section><h2>Na kaj paziti pri primerjavi cen</h2><ul class="points">{''.join(points)}</ul></section>
  <div class="actions">
    <a class="btn glow" href="{SITE}#kviz">Poiščite hišo, ki vam pristaja <span class="arrow">→</span></a>
    <a class="btn line" href="../{CHEAP}/">Najcenejše montažne hiše</a>
    <a class="btn line" href="../{COSTS}/">Kalkulator stroškov gradnje</a>
    <a class="btn line" href="../#katalog">Vse hiše v katalogu</a>
  </div>
</main>
{FOOT}
</body>
</html>
'''


def maker(p):
    name, ms = p['name'], p['models']
    url = SITE + p['id'] + '/'
    priced = [m for m in ms if m['price_eur'] and m['area_m2']]
    stage = collections.Counter(m['price_stage'] for m in priced).most_common(1)[0][0] if priced else None
    lo, hi = (min(m['price_eur'] for m in priced), max(m['price_eur'] for m in priced)) if priced else (None, None)
    count = f"{len(ms)} {plural(len(ms), 'tipska montažna hiša', 'tipski montažni hiši', 'tipske montažne hiše', 'tipskih montažnih hiš')}"
    img = next((m['image'] for m in ms if m.get('image')), None)
    n = lambda v: f'<td class="n">{v}</td>'
    rows = []
    for m in sorted(ms, key=lambda m: (m['area_m2'] or 10 ** 4, m['name'])):
        area = f"{round(m['area_m2'])} m²" if m['area_m2'] else '—'
        price = eur(m['price_eur']) if m['price_eur'] else 'na povpraševanje'
        m2 = eur(round(m['price_eur'] / m['area_m2'])) + '/m²' if m['price_eur'] and m['area_m2'] else '—'
        rows.append(f'<tr><td><a href="../{m["slug"]}/">{esc(m["name"])}</a></td>{n(area)}{n(m["bedrooms"] or "—")}'
                    f'<td>{ROOF.get(m["roof"], "—")}</td>{n(price)}{n(m2)}<td><button type="button" class="cmp sm" data-slug="{m["slug"]}">+ Primerjaj</button></td></tr>')
    others = ''.join(f'<li><a href="../{o["id"]}/">{esc(o["name"])}</a></li>' for o in data['providers'] if o is not p)
    maker_link, facts_html = maker_bits(p)
    desc = (f'{name}: {count}' + (f', cene od {eur(lo)} do {eur(hi)}' if priced else ', cene na povpraševanje') +
            '. Kaj cena vključuje, konstrukcija, energijski razred, čas gradnje in garancija.')
    image_abs = SITE + (img.replace('img/', 'img/large/') if img else 'img/large/riko-mila.jpg')
    ld = {'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': f'{name}: montažne hiše', 'url': url, 'description': desc,
          'inLanguage': 'sl', 'image': image_abs, 'about': {'@type': 'Organization', 'name': name, 'url': p.get('website')}}
    price_box = f'<b>od {eur(lo)}</b><span>{esc(stage)}</span>' if priced else '<b>Na povpraševanje</b><span>Proizvajalec cen ne objavlja.</span>'
    includes = f'Kaj vključuje cena: {esc(stage)}.' if priced else 'Cen tipskih hiš ne objavlja; ponudbo dobite na povpraševanje.'
    return f'''{head(f'{name}: montažne hiše, cene in modeli {YEAR} · Hišni vodič', f'{name}: montažne hiše, cene in modeli', desc, url, image_abs, ld).replace('</head>', '<style>' + TABLE_CSS + '</style></head>')}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / <a href="../#katalog">Katalog</a> / {esc(name)}</div>
    <div class="head">
      <div><h1 class="display">{esc(name)}</h1><div class="prov">Proizvajalec montažnih hiš · {count}</div></div>
      <div class="price">{price_box}</div>
    </div>
  </div>
  {figure(img, 'Montažna hiša ' + name, name)}
  <div class="lede"><p>{esc(p.get('description', ''))}</p><p>{includes} <a href="../{GUIDE}/">Primerjajte cene vseh proizvajalcev</a>.</p></div>
  <section><h2>Vse hiše proizvajalca {esc(name)}</h2><div class="scroll"><table class="tbl">{thead('Hiša', 'Površina', 'Spalnice', 'Streha', 'Cena', 'Na m²', '<span class="sr-only">Primerjava</span>')}<tbody>{''.join(rows)}</tbody></table></div></section>
  <div class="two">
    <div class="edge"><div class="eyebrow">Prednost proizvajalca {esc(name)}</div>{esc(p.get('edge') or '')}{facts_html}</div>
    <section class="maker-info"><h2>Spletna stran</h2>{maker_link}<h2>Drugi proizvajalci</h2><ul class="siblings">{others}</ul></section>
  </div>
  <div class="actions">
    <a class="btn glow" href="{SITE}#kviz">Poiščite hišo, ki vam pristaja <span class="arrow">→</span></a>
    <a class="btn line" href="../#katalog">Vse hiše v katalogu</a>
  </div>
</main>
{FOOT}
</body>
</html>
'''


PLANS_CSS = '''
.page > * { min-width: 0; }
.jump { display: flex; flex-wrap: wrap; gap: 8px; }
.jump a { padding: 8px 14px; border-radius: 999px; box-shadow: inset 0 0 0 1px var(--line); color: var(--ink); text-decoration: none; font-size: 14px; }
.jump a:hover { box-shadow: inset 0 0 0 1px var(--glow); }
.plan-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 260px), 1fr)); gap: 16px; }
.card { display: block; border-radius: var(--r); overflow: hidden; background: var(--dusk); box-shadow: 0 0 0 1px var(--line); color: var(--ink); text-decoration: none; }
.card:hover { box-shadow: 0 0 0 1px var(--glow); }
.card .pic { background: #fff; aspect-ratio: 4 / 3; }
.card img { width: 100%; height: 100%; object-fit: contain; display: block; }
.card span { display: block; padding: 12px 14px 14px; font-size: 14px; color: var(--mist); }
.card b { display: block; color: var(--ink); font-size: 15px; margin-bottom: 2px; }
'''


def plans_page():
    url = SITE + PLANS + '/'
    # shortcut: shows each house's full-size ground-floor plan, lazy-loaded; make thumbnails if the page gets slow.
    houses = sorted(((p, m, house_plans(m)) for p, m in models if house_plans(m)), key=lambda t: (t[1]['area_m2'] or 10 ** 4, t[1]['name']))
    bands = [(0, 80, 'do 80 m²'), (80, 100, '80–100 m²'), (100, 120, '100–120 m²'), (120, 140, '120–140 m²'), (140, 160, '140–160 m²'), (160, 10 ** 4, '160 m² in več')]
    sections, jump = [], []
    for a, b, label in bands + [(None, None, 'brez navedene površine')]:
        group = [t for t in houses if (t[1]['area_m2'] is None if a is None else t[1]['area_m2'] and a <= t[1]['area_m2'] < b)]
        if not group:
            continue
        anchor = slugify(label)
        cards = []
        for p, m, plans in group:
            name = f"{p['name']} {m['name']}"
            bits = [f"{round(m['area_m2'])} m²" if m['area_m2'] else '', FLOORS.get(m['floors'], ('',))[0],
                    f"{m['bedrooms']} {plural(m['bedrooms'], 'spalnica', 'spalnici', 'spalnice', 'spalnic')}" if m['bedrooms'] else '',
                    eur(m['price_eur']) if m['price_eur'] else '']
            cards.append(f'<a class="card" href="../{m["slug"]}/"><div class="pic"><img src="../{plans[0]}" alt="{esc(plan_alt(m, name, 1, len(plans)))}" loading="lazy"></div>'
                         f'<span><b>{esc(name)}</b>{" · ".join(x for x in bits if x)}</span></a>')
        jump.append(f'<a href="#{anchor}">{label}</a>')
        sections.append(f'<section id="{anchor}"><h2>Tlorisi hiš {label} <small class="eyebrow">{len(group)}</small></h2><div class="plan-grid">{"".join(cards)}</div></section>')
    areas = [m['area_m2'] for _, m, _ in houses if m['area_m2']]
    makers = sorted({p['name'] for p, _, _ in houses}, key=[p['name'] for p in data['providers']].index)
    desc = (f'Tlorisi {len(houses)} tipskih montažnih hiš slovenskih proizvajalcev od {round(min(areas))} do {round(max(areas))} m², '
            'razvrščeni po velikosti, s ceno in številom spalnic.')
    image = SITE + houses[0][2][0]
    ld = {'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': 'Tlorisi montažnih hiš', 'url': url, 'description': desc,
          'inLanguage': 'sl', 'image': image}
    return f'''{head(f'Tlorisi montažnih hiš: {len(houses)} tlorisov po velikosti · Hišni vodič', 'Tlorisi montažnih hiš', desc, url, image, ld).replace('</head>', '<style>' + PLANS_CSS + '</style></head>')}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / Tlorisi</div>
    <div class="head"><div><h1 class="display">Tlorisi montažnih hiš</h1><div class="prov">{len(houses)} tipskih hiš · {esc(and_join(makers))}</div></div></div>
  </div>
  <div class="lede"><p>Tlorisi tipskih montažnih hiš slovenskih proizvajalcev, razvrščeni po bivalni površini. Pri hišah z mansardo ali nadstropjem je prikazano pritličje;
    kliknite hišo za vse etaže, ceno in kaj vključuje. Tlorisi so last proizvajalcev.</p></div>
  <nav class="jump" aria-label="Velikost hiše">{''.join(jump)}</nav>
  {''.join(sections)}
  <div class="actions">
    <a class="btn glow" href="{SITE}#kviz">Poiščite hišo, ki vam pristaja <span class="arrow">→</span></a>
    <a class="btn line" href="../{GUIDE}/">Primerjava cen</a>
  </div>
</main>
{FOOT}
</body>
</html>
'''


COMPARE_CSS = '''
.page > * { min-width: 0; }
.cmp-tbl { table-layout: fixed; min-width: 640px; }
.cmp-tbl th:first-child, .cmp-tbl td:first-child { width: 150px; min-width: 0; position: sticky; left: 0; background: var(--night); z-index: 1; }
.cmp-tbl thead th { text-transform: none; letter-spacing: 0; font: inherit; color: var(--ink); white-space: normal; vertical-align: bottom; }
.cmp-tbl .pic { aspect-ratio: 600 / 340; border-radius: 12px; overflow: hidden; background: var(--dusk); margin-bottom: 10px; }
.cmp-tbl .pic img { width: 100%; height: 100%; object-fit: cover; display: block; }
.cmp-tbl thead a { font: 700 18px/1.2 var(--font-display); }
.cmp-tbl thead small { display: block; color: var(--mist); margin: 2px 0 8px; }
.cmp-tbl .rm { font: inherit; font-size: 13px; border: 0; background: none; color: var(--mist); padding: 0; cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
.cmp-tbl tbody th { color: var(--mist); font-weight: 500; font-size: 13px; white-space: normal; }
.cmp-tbl td { font-size: 15px; }
.cmp-tbl td.small { font-size: 13px; color: var(--mist); }
.cmp-tbl .best { color: var(--glow); }
.cmp-tbl .best::after { content: "najnižja"; display: inline-block; margin-left: 8px; padding: 2px 8px; border-radius: 999px; font: 500 10px/1.4 var(--font-data); letter-spacing: .08em; text-transform: uppercase; box-shadow: inset 0 0 0 1px var(--glow); }
.cmp-tbl .plan { display: block; background: #fff; border-radius: 10px; overflow: hidden; }
.cmp-tbl .plan img { width: 100%; height: auto; display: block; }
.tools { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.tools select { font: inherit; color: var(--ink); background: var(--dusk); border: 0; box-shadow: inset 0 0 0 1px var(--line); border-radius: 999px; padding: 12px 18px; max-width: 100%; }
@media (max-width: 640px) {
  .cmp-tbl { min-width: 500px; }
  .cmp-tbl th:first-child, .cmp-tbl td:first-child { width: 92px; }
  .cmp-tbl th, .cmp-tbl td { padding: 10px; }
  .cmp-tbl thead a { font-size: 15px; }
  .cmp-tbl .best::after { display: block; width: max-content; margin: 4px 0 0; }
}
.empty { padding: 28px; border-radius: var(--r); box-shadow: inset 0 0 0 1px var(--line); color: #c9d3e6; }
'''
COMPARE_JS = r'''
(function () {
  const H = JSON.parse(document.getElementById('cmp-data').textContent);
  const bySlug = Object.fromEntries(H.map(h => [h.slug, h]));
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  // by hand: sl-SI number formatting leaves 4-digit numbers ungrouped (1655), the rest of the site writes 1.655
  const eur = n => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '.') + ' €';
  const perM2 = h => h.price && h.area ? Math.round(h.price / h.area) : null;
  const fromHash = decodeURIComponent(location.hash.slice(1)).split(',').filter(s => bySlug[s]).slice(0, 3);
  let picks = fromHash.length ? fromHash : window.HVCompare.get().filter(s => bySlug[s]);
  function lowest(fn) { const v = picks.map(s => fn(bySlug[s])).filter(x => x != null); return v.length > 1 ? Math.min(...v) : null; }
  function render() {
    window.HVCompare.set(picks);
    history.replaceState(null, '', picks.length ? '#' + picks.join(',') : location.pathname);
    for (const o of $('add').options) o.disabled = !!o.value && picks.includes(o.value);
    $('add').hidden = picks.length >= 3;
    $('copy').hidden = picks.length < 2;
    if (picks.length < 2) {
      $('cmp').innerHTML = `<div class="empty">${picks.length ? `Izbrana je <b>${esc(bySlug[picks[0]].name)}</b>. Dodajte še eno ali dve hiši.` : 'Izberite dve ali tri hiše.'}
        Dodate jih z izbirnikom zgoraj ali z gumbom »+ Primerjaj« v <a href="../#katalog">katalogu</a> in na straneh hiš.</div>`;
      return;
    }
    const hs = picks.map(s => bySlug[s]);
    const lowPrice = lowest(h => h.price), lowM2 = lowest(perM2);
    const rows = [
      ['Cena', h => h.price ? `<span class="${h.price === lowPrice ? 'best' : ''}">${eur(h.price)}</span>` : 'na povpraševanje'],
      ['Kaj cena vključuje', h => h.price ? esc(h.stage) : 'Proizvajalec cene ne objavlja.', 'small'],
      ['Površina', h => h.area ? h.area + ' m²' : '—'],
      ['Cena na m²', h => perM2(h) ? `<span class="${perM2(h) === lowM2 ? 'best' : ''}">${eur(perM2(h))}/m²</span>` : '—'],
      ['Etaže', h => esc(h.floors)],
      ['Spalnice', h => h.bed ?? '—'],
      ['Kopalnice', h => h.bath ?? '—'],
      ['Streha', h => esc(h.roof)],
      ['Konstrukcija', h => esc(h.construction), 'small'],
      ['Energija', h => esc(h.energy), 'small'],
      ['Gradnja', h => esc(h.build), 'small'],
      ['Garancija', h => h.warranty ? h.warranty + ' let' : '—'],
      ['Tloris', h => h.plan ? `<a class="plan" href="../${esc(h.plan)}"><img src="../${esc(h.plan)}" alt="Tloris – ${esc(h.name)}" loading="lazy"></a>` : '—'],
    ];
    $('cmp').innerHTML = `<div class="scroll"><table class="tbl cmp-tbl"><thead><tr><th><span class="sr-only">Lastnost</span></th>${hs.map(h => `<th scope="col">
        <div class="pic">${h.image ? `<img src="../${esc(h.image)}" alt="${esc(h.name)}">` : ''}</div>
        <a href="../${h.slug}/">${esc(h.name)}</a><small>${esc(h.maker)}</small><button type="button" class="rm" data-rm="${h.slug}">Odstrani</button></th>`).join('')}</tr></thead>
      <tbody>${rows.map(([label, f, cls]) => `<tr><th scope="row">${label}</th>${hs.map(h => `<td${cls ? ` class="${cls}"` : ''}>${f(h) || '—'}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  $('cmp').addEventListener('click', e => { const b = e.target.closest('[data-rm]'); if (b) { picks = picks.filter(s => s !== b.dataset.rm); render(); } });
  $('add').addEventListener('change', e => { if (e.target.value && picks.length < 3) picks = picks.concat(e.target.value); e.target.value = ''; render(); });
  $('copy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(location.href); $('copy').textContent = 'Povezava kopirana ✓'; setTimeout(() => { $('copy').textContent = 'Kopiraj povezavo'; }, 2500); }
    catch (e) { window.prompt('Kopirajte povezavo:', location.href); }
    try { if (window.umami) window.umami.track('compare-share', { houses: picks.join(',') }); } catch (e) {}
  });
  render();
})();
'''


def compare_page():
    url = SITE + COMPARE + '/'
    rows = []
    for p, m in models:
        plans = house_plans(m)
        rows.append({'slug': m['slug'], 'name': f"{p['name']} {m['name']}", 'maker': p['name'], 'price': m['price_eur'], 'stage': m['price_stage'],
                     'area': round(m['area_m2']) if m['area_m2'] else None, 'floors': FLOORS.get(m['floors'], ('—',))[0],
                     'bed': m['bedrooms'], 'bath': m['bathrooms'], 'roof': ROOF.get(m['roof'], '—'), 'image': m.get('image'),
                     'plan': plans[0] if plans else None, 'construction': p.get('construction'), 'energy': p.get('energy_class'),
                     'build': p.get('build_time'), 'warranty': p.get('warranty_years')})
    options = ''.join(f'<optgroup label="{esc(p["name"])}">' + ''.join(f'<option value="{m["slug"]}">{esc(m["name"])}</option>' for m in p['models']) + '</optgroup>'
                      for p in data['providers'])
    desc = 'Primerjajte do tri tipske montažne hiše slovenskih proizvajalcev: cena, kaj cena vključuje, m², cena na m², sobe, energija, garancija in tloris.'
    ld = {'@context': 'https://schema.org', '@type': 'WebPage', 'name': 'Primerjava montažnih hiš', 'url': url, 'description': desc, 'inLanguage': 'sl'}
    data_json = json.dumps(rows, ensure_ascii=False).replace('</', '<\\/')
    # noindex: the table is built in the browser from the link, so the page has no content of its own for search
    return (head('Primerjava montažnih hiš · Hišni vodič', 'Primerjava montažnih hiš', desc, url, SITE + 'img/large/riko-mila.jpg', ld)
            .replace('</head>', '<meta name="robots" content="noindex, follow"><style>' + TABLE_CSS + COMPARE_CSS + '</style></head>') + f'''
<body data-page="compare">
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / Primerjava</div>
    <div class="head"><div><h1 class="display">Primerjava hiš</h1><div class="prov">Do tri hiše drugo ob drugi</div></div></div>
  </div>
  <div class="tools">
    <select id="add" aria-label="Dodaj hišo v primerjavo"><option value="">+ Dodaj hišo …</option>{options}</select>
    <button type="button" class="btn line" id="copy" hidden>Kopiraj povezavo</button>
  </div>
  <div id="cmp"></div>
  <div class="actions">
    <a class="btn glow" href="{SITE}#kviz">Poiščite hišo, ki vam pristaja <span class="arrow">→</span></a>
    <a class="btn line" href="../#katalog">Vse hiše v katalogu</a>
  </div>
</main>
{FOOT}
<script type="application/json" id="cmp-data">{data_json}</script>
<script>{COMPARE_JS}</script>
</body>
</html>
''')


CMP_TH = '<span class="sr-only">Primerjava</span>'


def cmp_btn(m):
    return f'<button type="button" class="cmp sm" data-slug="{m["slug"]}">+ Primerjaj</button>'


def house_link(p, m):
    return f'<a href="../{m["slug"]}/">{esc(p["name"])} {esc(m["name"])}</a>'


def cheap_page():
    url = SITE + CHEAP + '/'
    per_m2 = lambda m: m['price_eur'] / m['area_m2']
    priced = [(p, m) for p, m in models if m['price_eur']]
    sized = [(p, m) for p, m in priced if m['area_m2']]
    turnkey = [(p, m) for p, m in priced if 'na ključ' in m['price_stage'].lower()]
    n = lambda v: f'<td class="n">{v}</td>'

    def table(rows):
        body = ''.join(f'<tr><td>{house_link(p, m)}</td>{n(str(round(m["area_m2"])) + " m²" if m["area_m2"] else "—")}{n(eur(m["price_eur"]))}'
                       f'{n(eur(round(per_m2(m))) + "/m²" if m["area_m2"] else "—")}<td class="stage">{esc(m["price_stage"])}</td><td>{cmp_btn(m)}</td></tr>'
                       for p, m in rows)
        return f'<div class="scroll"><table class="tbl">{thead("Hiša", "Površina", "Cena", "Na m²", "Kaj cena vključuje", CMP_TH)}<tbody>{body}</tbody></table></div>'

    by_price = lambda rows: sorted(rows, key=lambda pm: pm[1]['price_eur'])[:12]
    lo, lo_key, lo_m2 = by_price(priced)[0], by_price(turnkey)[0], min(sized, key=lambda pm: per_m2(pm[1]))
    key_makers = {p['name'] for p, _ in turnkey}
    other = [p['name'] for p in data['providers'] if p['name'] not in key_makers and any(m['price_eur'] for m in p['models'])]
    unpublished = [p['name'] for p in data['providers'] if not any(m['price_eur'] for m in p['models'])]
    verb = lambda names, one, two, many: one if len(names) == 1 else two if len(names) == 2 else many
    rest = (f'{and_join(other)} {verb(other, "navaja", "navajata", "navajajo")} cene za druge pakete, zato {verb(other, "ni", "nista", "niso")} v tej tabeli' if other else '') + \
        ('; ' if other and unpublished else '') + \
        (f'{and_join(unpublished)} {verb(unpublished, "cen ne objavlja", "cen ne objavljata", "cen ne objavljajo")}' if unpublished else '')
    rest_html = f'<p class="note">{esc(rest)}. <a href="../{GUIDE}/">Kaj vključujejo cene posameznih proizvajalcev</a></p>' if rest else ''

    desc = (f'Najcenejše montažne hiše na ključ od {eur(lo_key[1]["price_eur"])}, najnižja cena na m² {eur(round(per_m2(lo_m2[1])))}. '
            f'Primerjava {len(priced)} tipskih hiš slovenskih proizvajalcev z objavljeno ceno in kaj cena vključuje.')
    image = SITE + (lo_key[1]['image'].replace('img/', 'img/large/') if lo_key[1].get('image') else 'img/large/riko-mila.jpg')
    ld = {'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': 'Najcenejše montažne hiše', 'url': url, 'description': desc,
          'inLanguage': 'sl', 'image': image}
    return f'''{head(f'Najcenejše montažne hiše {YEAR}: na ključ in po m² · Hišni vodič', 'Najcenejše montažne hiše', desc, url, image, ld).replace('</head>', '<style>' + TABLE_CSS + '.note { color: var(--mist); font-size: 14px; margin: 10px 0 0; } .note a { color: var(--ink); text-underline-offset: 3px; }</style></head>')}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / <a href="../{GUIDE}/">Cene</a> / Najcenejše hiše</div>
    <div class="head"><div><h1 class="display">Najcenejše montažne hiše</h1><div class="prov">{len(priced)} tipskih hiš z objavljeno ceno · podatki: {esc(data['collected'])}</div></div></div>
  </div>
  <div class="lede"><p>Najcenejša montažna hiša z objavljeno ceno je {house_link(*lo)} ({eur(lo[1]['price_eur'])}), najcenejša na ključ {house_link(*lo_key)}
    ({eur(lo_key[1]['price_eur'])}). Najnižjo ceno na m² ima {house_link(*lo_m2)} ({eur(round(per_m2(lo_m2[1])))}/m²).</p>
    <p>Proizvajalci navajajo cene za različne pakete, zato pred primerjavo preverite, kaj cena vključuje. <a href="../{GUIDE}/">Primerjava cen po proizvajalcih</a></p></div>
  <section><h2>Najcenejše montažne hiše na ključ</h2>{table(by_price(turnkey))}{rest_html}</section>
  <section><h2>Najcenejše po ceni</h2>{table(by_price(priced))}</section>
  <section><h2>Najnižja cena na m²</h2>{table(sorted(sized, key=lambda pm: per_m2(pm[1]))[:12])}</section>
  <div class="actions">
    <a class="btn glow" href="{SITE}#kviz">Poiščite hišo, ki vam pristaja <span class="arrow">→</span></a>
    <a class="btn line" href="../{GUIDE}/">Primerjava cen</a>
    <a class="btn line" href="../{COMPARE}/">Primerjava hiš</a>
  </div>
</main>
{FOOT}
</body>
</html>
'''


SMALL_CSS = '''
.page > * { min-width: 0; }
.hgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 14px; }
@media (min-width: 700px) { .hgrid { grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); } }
.hc { display: flex; flex-direction: column; border-radius: var(--r); overflow: hidden; background: var(--dusk); box-shadow: 0 0 0 1px var(--line); }
.hc:hover { box-shadow: 0 0 0 1px var(--glow); }
.hc > a { display: block; flex: 1; color: var(--ink); text-decoration: none; }
.hc .pic { aspect-ratio: 600 / 340; background: var(--slate); }
.hc img { width: 100%; height: 100%; object-fit: cover; display: block; }
.hc span { display: block; padding: 10px 14px 8px; font-size: 14px; color: var(--mist); }
.hc b { display: block; color: var(--ink); font-size: 15px; margin-bottom: 2px; }
.hc-act { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; padding: 0 14px 14px; font-size: 13px; }
.hc-act a { color: var(--ink); text-decoration-color: var(--line); text-underline-offset: 3px; }
'''


def small_page():
    url = SITE + SMALL + '/'
    houses = sorted(((p, m) for p, m in models if m['area_m2'] and m['area_m2'] <= 100), key=lambda pm: (pm[1]['area_m2'], pm[1]['name']))
    priced = [(p, m) for p, m in houses if m['price_eur']]
    lo = min(priced, key=lambda pm: pm[1]['price_eur'])
    areas = [round(m['area_m2']) for _, m in houses]
    sections = []
    for a, b, h2 in ((0, 60, 'Majhne montažne hiše do 60 m²'), (60, 80, 'Montažne hiše od 60 do 80 m²'), (80, 100, 'Montažne hiše od 80 do 100 m²')):
        cards = []
        for p, m in (t for t in houses if a < t[1]['area_m2'] <= b):
            plans = house_plans(m)
            bits = [f"{round(m['area_m2'])} m²", FLOORS.get(m['floors'], ('',))[0],
                    f"{m['bedrooms']} {plural(m['bedrooms'], 'spalnica', 'spalnici', 'spalnice', 'spalnic')}" if m['bedrooms'] else '',
                    eur(m['price_eur']) if m['price_eur'] else 'cena na povpraševanje']
            pic = f'<img src="../{esc(m["image"])}" alt="" loading="lazy">' if m.get('image') else ''
            plan = f'<a href="../{plans[0]}">Tloris</a>' if plans else ''
            cards.append(f'<div class="hc"><a href="../{m["slug"]}/"><div class="pic">{pic}</div><span><b>{esc(p["name"])} {esc(m["name"])}</b>'
                         f'{" · ".join(x for x in bits if x)}</span></a><div class="hc-act">{plan}{cmp_btn(m)}</div></div>')
        if cards:
            sections.append(f'<section><h2>{h2} <small class="eyebrow">{len(cards)}</small></h2><div class="hgrid">{"".join(cards)}</div></section>')
    count = f"{len(houses)} {plural(len(houses), 'tipska montažna hiša', 'tipski montažni hiši', 'tipske montažne hiše', 'tipskih montažnih hiš')}"
    desc = (f'Majhne montažne hiše do 100 m²: {count} slovenskih proizvajalcev od {min(areas)} do {max(areas)} m², '
            f'cene od {eur(lo[1]["price_eur"])}, tlorisi in kaj cena vključuje.')
    image = SITE + (lo[1]['image'].replace('img/', 'img/large/') if lo[1].get('image') else 'img/large/riko-mila.jpg')
    ld = {'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': 'Majhne montažne hiše', 'url': url, 'description': desc,
          'inLanguage': 'sl', 'image': image}
    return f'''{head('Majhne montažne hiše do 100 m²: cene in tlorisi · Hišni vodič', 'Majhne montažne hiše do 100 m²', desc, url, image, ld).replace('</head>', '<style>' + SMALL_CSS + '</style></head>')}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / Majhne hiše</div>
    <div class="head"><div><h1 class="display">Majhne montažne hiše</h1><div class="prov">{count} do 100 m² · podatki: {esc(data['collected'])}</div></div></div>
  </div>
  <div class="lede"><p>V vodiču je {count} do 100 m² bivalne površine, od {min(areas)} do {max(areas)} m². Ceno proizvajalec objavlja za {len(priced)} od njih;
    najcenejša je {house_link(*lo)} ({eur(lo[1]['price_eur'])}, {round(lo[1]['area_m2'])} m², {esc(lo[1]['price_stage'])}).</p>
    <p>Za ostale je cena na povpraševanje. Proizvajalci navajajo cene za različne pakete. <a href="../{GUIDE}/">Kaj cena vključuje pri posameznem proizvajalcu</a></p></div>
  {''.join(sections)}
  <div class="actions">
    <a class="btn glow" href="{SITE}#kviz">Poiščite hišo, ki vam pristaja <span class="arrow">→</span></a>
    <a class="btn line" href="../{GUIDE}/">Primerjava cen</a>
    <a class="btn line" href="../{PLANS}/">Tlorisi montažnih hiš</a>
    <a class="btn line" href="../{COMPARE}/">Primerjava hiš</a>
  </div>
</main>
{FOOT}
</body>
</html>
'''


COSTS_CSS = '''
.page > * { min-width: 0; }
.calc { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; }
@media (min-width: 960px) { .calc { grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); align-items: start; } }
.form { display: grid; gap: 16px; background: var(--dusk); border-radius: var(--r); box-shadow: 0 0 0 1px var(--line); padding: 20px; min-width: 0; }
.form label, .form .f { display: grid; gap: 6px; font-size: 14px; color: var(--mist); min-width: 0; }
.form select, .form input[type=number] { font: inherit; font-size: 16px; color: var(--ink); background: var(--slate); border: 0; box-shadow: inset 0 0 0 1px var(--line); border-radius: 12px; padding: 10px 12px; width: 100%; min-width: 0; }
.form label.ck { display: flex; gap: 10px; align-items: flex-start; color: var(--ink); cursor: pointer; }
.form .ck input { margin: 4px 0 0; accent-color: var(--glow); flex: none; }
.form small { font-size: 12.5px; line-height: 1.45; color: var(--mist); }
.sub { display: grid; gap: 12px; padding: 14px; border-radius: 12px; box-shadow: inset 0 0 0 1px var(--line); }
.sub[hidden] { display: none; }
.res { display: grid; gap: 16px; min-width: 0; }
.total { padding: 20px; border-radius: var(--r); background: linear-gradient(160deg, rgba(255,196,119,.14), rgba(255,157,77,.04)); box-shadow: inset 0 0 0 1px var(--glow); }
.total b { display: block; font: 800 clamp(28px, 5vw, 46px)/1.1 var(--font-display); font-stretch: 108%; color: var(--glow); font-variant-numeric: tabular-nums; margin-top: 6px; }
.total p { margin: 8px 0 0; font-size: 13px; color: var(--mist); }
.lines tbody th { white-space: normal; font-weight: 600; }
.lines th small { display: block; font-weight: 400; color: var(--mist); font-size: 12.5px; margin-top: 2px; }
.lines .cmp { margin-left: 6px; }
.lines td { text-align: right; }
.lines td small { display: block; font-size: 12px; color: var(--mist); white-space: nowrap; margin-top: 4px; }
.lines td small a { color: var(--mist); }
.share { display: block; height: 4px; border-radius: 4px; background: var(--line); margin-top: 8px; overflow: hidden; }
.share i { display: block; height: 100%; background: var(--glow); }
.share i.neg { background: #7fd1a8; }
@media (max-width: 640px) { .lines th, .lines td { padding: 10px; } .lines td.n, .lines td small { white-space: normal; } .lines tbody th { width: 52%; } }
.tools { display: flex; flex-wrap: wrap; gap: 12px; }
.prose { max-width: 48em; }
.prose p { color: #c9d3e6; margin: 0 0 10px; }
.prose a, .viri a { color: var(--ink); text-underline-offset: 3px; }
.viri { margin: 0; padding-left: 22px; color: #c9d3e6; display: grid; gap: 8px; font-size: 14px; overflow-wrap: anywhere; }
.viri span { color: var(--mist); }
'''
COSTS_JS = r'''
(function () {
  const D = JSON.parse(document.getElementById('calc-data').textContent);
  const I = D.items, $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  // by hand: sl-SI number formatting leaves 4-digit numbers ungrouped (1655), the rest of the site writes 1.655
  const eur = n => (n < 0 ? '−' : '') + String(Math.round(Math.abs(n))).replace(/\B(?=(\d{3})+(?!\d))/g, '.') + '\u00a0€';
  const span = (lo, hi) => Math.round(lo) === Math.round(hi) ? eur(lo) : eur(lo) + ' – ' + eur(hi);
  const rng = k => { const v = I[k].value; return typeof v === 'object' ? [v.min, v.max] : [v, v]; };
  const RANK = { low: 0, medium: 1, high: 2 }, TAG = { high: 'uradni podatek', medium: 'okvirno', low: 'zelo okvirno' };
  const houses = Object.fromEntries(D.houses.map(h => [h.slug, h]));
  const num = id => Math.max(0, parseFloat($(id).value) || 0);
  const FIELDS = ['h', 'cp', 'ca', 'cf', 'cs', 'plot', 'kp', 'kw', 'san', 'pd', 'zem', 'zu', 'snes', 'tier'];
  const CUSTOM = ['cp', 'ca', 'cf', 'cs'];
  const val = id => $(id).type === 'checkbox' ? ($(id).checked ? '1' : '0') : $(id).value;

  // Several items in one line: sum the ranges, keep the weakest confidence and all sources.
  function sum(label, keys, note) {
    return { label, note, lo: keys.reduce((a, k) => a + rng(k)[0], 0), hi: keys.reduce((a, k) => a + rng(k)[1], 0),
      conf: keys.map(k => I[k].confidence).reduce((a, b) => RANK[a] <= RANK[b] ? a : b),
      src: [...new Set(keys.flatMap(k => I[k].source_ids))] };
  }

  function lines(h) {
    const out = [{ label: 'Hiša', lo: h.price, hi: h.price, tag: h.slug ? 'cena proizvajalca' : 'vaša ponudba', house: h, note: h.stage }];
    if (h.slab) {
      // shortcut: slab ≈ ground floor = net m² / floors, +15 % for walls; use the real footprint if the data ever has it
      const m2 = h.area / h.floors * 1.15, [a, b] = rng('temeljna_plosca_m2');
      out.push({ ...sum('Temeljna plošča', ['temeljna_plosca_m2']), lo: m2 * a, hi: m2 * b, note: `približno ${Math.round(m2)} m² × ${a}–${b} €/m²` });
    }
    const plot = num('plot');
    if (plot) out.push({ label: 'Zemljišče', lo: plot, hi: plot, tag: 'vaš vnos' });
    const k = D.kp.find(x => x.id === $('kp').value);
    out.push({ label: 'Komunalni prispevek', lo: k.lo, hi: k.hi, conf: k.conf, src: k.src, note: `${k.name}: ${k.note}` });
    // projekt_paket already covers PID, so pid_posnetek is not added on top
    out.push($('pd').checked ? sum('Projektna dokumentacija in nadzor', ['gradbeni_nadzor'], 'dokumentacija v ceni hiše, prištet le gradbeni nadzor')
      : sum('Projektna dokumentacija in nadzor', ['projekt_paket', 'geodetski_nacrt', 'geolosko_porocilo', 'mnenja_soglasja', 'gradbeni_nadzor'],
        'IDZ, DGD, PZI, PID, geodetski načrt, geološko poročilo, mnenja, gradbeni nadzor'));
    const mkcn = $('san').value === 'mkcn';
    out.push(sum('Priključki', ['prikljucek_elektrika_' + $('kw').value + 'kw', 'prikljucek_voda', mkcn ? 'mkcn' : 'prikljucek_kanalizacija'],
      `elektrika ${$('kw').value} kW (${eur(rng('prikljucek_elektrika_' + $('kw').value + 'kw')[0])}), voda, ` + (mkcn ? 'MKČN brez vgradnje' : 'kanalizacija')));
    const [zl, zh] = rng('zemeljska_dela'), z = $('zem').value;
    out.push({ ...sum('Zemeljska dela', ['zemeljska_dela']), ...(z === 'l' ? { lo: I.zemeljska_dela.typical, hi: I.zemeljska_dela.typical, note: 'lahek teren' }
      : z === 't' ? { lo: zh, hi: zh, note: 'zahteven teren, skala: ' + eur(zh) + ' ali več' } : { note: 'od lahkega do skalnatega terena' }) });
    if ($('zu').checked) out.push(sum('Zunanja ureditev', ['zunanja_ureditev'], 'dovoz, tlakovanje, zelenice; brez ograje'));
    if ($('snes').checked) {
      const e = I.eko_sklad_snes, rate = D.tiers[+$('tier').value].rate;
      // the call caps the grant at 30 % of eligible costs, and eligible costs at 50 % of a turnkey contract: 15 % of the price
      const byArea = rate * Math.min(h.area, e.max_area_m2), cap = Math.min(e.max_eur, 0.3 * 0.5 * h.price), s = h.sub ? 0 : Math.min(byArea, cap);
      out.push({ ...sum('Subvencija Eko sklada', ['eko_sklad_snes']), lo: -s, hi: -s, note: h.sub ? 'cena te hiše že upošteva subvencijo, zato je ne odštejemo še enkrat'
        : `${rate} €/m² × ${Math.round(Math.min(h.area, e.max_area_m2))} m²` + (cap < byArea ? `, omejeno na ${cap === e.max_eur ? 'najvišji znesek' : '15 % cene hiše'}` : '') });
    }
    return out;
  }

  function render() {
    const custom = $('h').value === 'lastna';
    $('custom').hidden = !custom;
    $('tierbox').hidden = !$('snes').checked;
    const p = new URLSearchParams();
    for (const id of FIELDS) if ((custom || !CUSTOM.includes(id)) && (id !== 'tier' || $('snes').checked) && (id !== 'plot' || num('plot'))) p.set(id, val(id));
    history.replaceState(null, '', '#' + p.toString());
    const h = custom ? { price: num('cp'), area: num('ca'), floors: +$('cf').value, slab: !$('cs').checked, sub: false, name: 'Lastna ponudba' } : houses[$('h').value];
    if (!h.price || !h.area) {
      $('total').innerHTML = '<span class="eyebrow">Skupaj</span><b>—</b><p>Vpišite ceno in neto površino hiše.</p>';
      $('lines').innerHTML = '';
      return;
    }
    const ls = lines(h), lo = ls.reduce((a, l) => a + l.lo, 0), hi = ls.reduce((a, l) => a + l.hi, 0);
    const mids = ls.map(l => (l.lo + l.hi) / 2), mid = mids.reduce((a, b) => a + b, 0);
    $('total').innerHTML = `<span class="eyebrow">Skupaj</span><b>${Math.round(lo) === Math.round(hi) ? 'približno ' + eur(lo) : 'od ' + eur(lo) + ' do ' + eur(hi)}</b>
      <p>${esc(h.name)}, ${Math.round(h.area)} m² neto · na m² od ${eur(lo / h.area)} do ${eur(hi / h.area)}</p>`;
    $('lines').innerHTML = `<table class="tbl lines"><thead><tr><th scope="col">Postavka</th><th scope="col" style="text-align:right">Znesek</th></tr></thead><tbody>${ls.map((l, i) => {
      const name = l.house && l.house.slug ? `<a href="../${l.house.slug}/">${esc(l.house.name)}</a><button type="button" class="cmp sm" data-slug="${l.house.slug}">+ Primerjaj</button>` : '';
      const src = (l.src || []).map(s => `<a href="#vir-${s}">[${D.srcNum[s]}]</a>`).join('');
      const pct = mid > 0 ? Math.min(100, Math.abs(mids[i]) / mid * 100) : 0;
      return `<tr><th scope="row">${l.label}${name ? '<small>' + name + '</small>' : ''}${l.note ? `<small>${esc(l.note)}</small>` : ''}
        <span class="share" title="${Math.round(pct)} % skupaj"><i class="${mids[i] < 0 ? 'neg' : ''}" style="width:${pct.toFixed(1)}%"></i></span></th>
        <td class="n">${span(l.lo, l.hi)}<small>${l.tag || TAG[l.conf]} ${src}</small></td></tr>`;
    }).join('')}</tbody></table>`;
    window.HVCompare.refresh();
  }

  const q = new URLSearchParams(location.hash.slice(1));
  for (const id of FIELDS) {
    if (!q.has(id)) continue;
    const el = $(id), before = el.value;
    if (el.type === 'checkbox') el.checked = q.get(id) === '1';
    else { el.value = q.get(id); if (el.tagName === 'SELECT' && !el.value) el.value = before; }
  }
  $('calc').addEventListener('input', render);
  $('calc').addEventListener('change', render);
  $('copy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(location.href); $('copy').textContent = 'Povezava kopirana ✓'; setTimeout(() => { $('copy').textContent = 'Kopiraj povezavo'; }, 2500); }
    catch (e) { window.prompt('Kopirajte povezavo:', location.href); }
  });
  render();
})();
'''

# English words in the source titles of data/stroski-viri.md, shown in Slovenian on the page.
VIRI_SL = {'forum, May 2021': 'forum, maj 2021', 'modified ': 'spremenjen ', 'updated ': 'posodobljeno '}


def viri():
    """Sources from the table in data/stroski-viri.md: id, title, URL, publisher (without its English remarks in brackets)."""
    out = []
    for line in open('data/stroski-viri.md', encoding='utf-8'):
        cells = [c.strip() for c in line.strip().strip('|').split(' | ')]
        if len(cells) == 5 and cells[2].startswith('http'):
            title = cells[1]
            for a, b in VIRI_SL.items():
                title = title.replace(a, b)
            out.append({'id': cells[0], 'title': title, 'url': cells[2], 'publisher': re.sub(r'\s*\(.*?\)', '', cells[3])})
    return out


def costs_page():
    url = SITE + COSTS + '/'
    cost = json.load(open('data/stroski.json', encoding='utf-8'))
    items = {it['key']: it for it in cost['items']}
    kp = cost['komunalni_prispevek']
    nat = kp['national_range']
    sources = viri()
    src_num = {s['id']: i for i, s in enumerate(sources, 1)}
    used = {s for it in cost['items'] for s in it['source_ids']} | set(kp['source_ids']) | {s for m in kp['municipalities'] for s in m['source_ids']}
    assert used <= set(src_num), used - set(src_num)

    def rng(key):
        v = items[key]['value']
        return (v['min'], v['max']) if isinstance(v, dict) else (v, v)

    def span(key):
        a, b = rng(key)
        return eur(round(a)) if a == b else eur(round(a)) + ' – ' + eur(round(b))

    def cite(*ids):
        return ''.join(f'<a href="#vir-{s}">[{src_num[s]}]</a>' for s in ids)

    conf = {'high': 'uradni podatek', 'medium': 'okvirno', 'low': 'zelo okvirno'}
    nat_min, nat_max = re.search(r'min ([^,]+), max ([^,]+)', nat['basis']).groups()
    covered, of = re.search(r'(\d+) of (\d+) municipalities', nat['basis']).groups()

    # Komunalni prispevek: our odlok calculation (600 m² plot, 180 m² BTP) where we have it, else vsevem.si's figure (600 m², 200 m² BTP).
    kps, kp_rows = [], []
    for m in kp['municipalities']:
        c = m.get('calc_600_180')
        lo, hi = (c['min'], c['max']) if isinstance(c, dict) else (c, c) if c else (m['vsevem_600_200'], m['vsevem_600_200'])
        note = 'parcela 600 m², 180 m² BTP, cene odloka brez indeksacije' if c else 'izračun vsevem.si za parcelo 600 m² in 200 m² BTP'
        kps.append({'id': slugify(m['obcina']), 'name': m['obcina'], 'lo': lo, 'hi': hi, 'conf': m['confidence'], 'src': m['source_ids'], 'note': note})
        calc_txt = (eur(lo) if lo == hi else eur(lo) + ' – ' + eur(hi)) if c else '—'
        kp_rows.append(f'<tr><th scope="row">{esc(m["obcina"])}</th><td class="n">{calc_txt}</td><td class="n">{eur(m["vsevem_600_200"])}</td>'
                       f'<td>{conf[m["confidence"]]} {cite(*m["source_ids"])}</td></tr>')
    kps.append({'id': 'druga', 'name': 'Druga občina (slovensko povprečje)', 'lo': nat['typical'], 'hi': nat['typical'], 'conf': nat['confidence'], 'src': nat['source_ids'],
                'note': f'povprečje {covered} občin, razpon od {eur(nat["min"])} ({nat_min}) do {eur(nat["max"])} ({nat_max})'})
    kp_opts = ''.join(f'<option value="{k["id"]}"{" selected" if k["id"] == "druga" else ""}>{esc(k["name"])} ({eur(k["lo"]) if k["lo"] == k["hi"] else eur(k["lo"]) + " – " + eur(k["hi"])})</option>'
                      for k in sorted(kps[:-1], key=lambda k: k['name']) + kps[-1:])

    # Eko sklad rates per group I/II/III at QH <= 10 / <= 15 kWh/m2a, read from the item's text.
    snes = items['eko_sklad_snes']
    tiers_raw = re.findall(r'(\d+)/(\d+)(?: EUR/m2)? group (I+)\b', snes['applies'])
    assert len(tiers_raw) == 3 and min(int(t[1]) for t in tiers_raw) == snes['value']['min'] and max(int(t[0]) for t in tiers_raw) == snes['value']['max'], tiers_raw
    group = {'I': 'naravna izolacija in lesena okna', 'II': 'mineralna izolacija', 'III': 'sintetična izolacija'}
    tiers = [{'rate': int(t[q]), 'label': f'Skupina {t[2]} ({group[t[2]]}), QH ≤ {10 if q == 0 else 15} kWh/m²a: {t[q]} €/m²'} for q in (0, 1) for t in tiers_raw]
    tier_opts = ''.join(f'<option value="{i}">{esc(t["label"])}</option>' for i, t in enumerate(tiers))

    def stage_has(m, *keys):
        return any(k in m['price_stage'].lower() for k in keys)

    priced = [(p, m) for p, m in models if m['price_eur'] and m['area_m2']]
    houses = [{'slug': m['slug'], 'name': f"{p['name']} {m['name']}", 'price': m['price_eur'], 'area': m['area_m2'], 'floors': m['floors'],
               'stage': m['price_stage'], 'slab': stage_has(m, 'brez temeljne plošče'), 'sub': stage_has(m, 'subvencij')} for p, m in priced]
    plain = sorted((h for h in houses if not h['sub']), key=lambda h: h['price'])
    default = plain[len(plain) // 2]['slug']  # a mid-priced house whose price is not already cut by a subsidy
    house_opts = ''.join(f'<optgroup label="{esc(p["name"])}">' + ''.join(
        f'<option value="{m["slug"]}"{" selected" if m["slug"] == default else ""}>{esc(m["name"])} · {eur(m["price_eur"])}</option>'
        for m in p['models'] if m['price_eur'] and m['area_m2']) + '</optgroup>' for p in data['providers'] if any(m['price_eur'] and m['area_m2'] for m in p['models'])) + \
        '<option value="lastna">Lastna ponudba</option>'

    calc_json = json.dumps({'houses': houses, 'items': items, 'kp': kps, 'tiers': tiers, 'srcNum': src_num}, ensure_ascii=False).replace('</', '<\\/')

    makers_by = lambda *keys: [p['name'] for p in data['providers'] if any(stage_has(m, *keys) for m in p['models'] if m['price_eur'])]
    no_slab, subsidized = makers_by('brez temeljne plošče'), makers_by('subvencij')
    no_slab_n = sum(1 for h in houses if h['slab'])
    verb = lambda names, one, two, many: one if len(names) == 1 else two if len(names) == 2 else many
    eles = items['prikljucek_elektrika_per_kw']['value']
    eles_txt = f'{eles:.2f}'.replace('.', ',')
    el = lambda kw: eur(round(items[f'prikljucek_elektrika_{kw}kw']['value']))
    mn, mx = rng('zemeljska_dela')
    ddv = items['ddv_stopnja']['value']
    pct = lambda r: f'{r * 100:g}'.replace('.', ',') + ' %'
    slab_lo, slab_hi = rng('temeljna_plosca_m2')
    t_rates = sorted({t['rate'] for t in tiers}, reverse=True)

    desc = (f'Kalkulator stroškov gradnje montažne hiše: komunalni prispevek povprečno {eur(nat["typical"])} (od {eur(nat["min"])} do {eur(nat["max"])}), '
            f'projektna dokumentacija {span("projekt_paket")}, priključki, temeljna plošča {slab_lo}–{slab_hi} €/m² in subvencija Eko sklada do {eur(snes["max_eur"])}.')
    h1 = 'Koliko stane gradnja montažne hiše?'
    ld = {'@context': 'https://schema.org', '@type': 'Article', 'headline': h1, 'description': desc, 'inLanguage': 'sl', 'url': url,
          'dateModified': cost['as_of'], 'image': SITE + 'img/large/riko-mila.jpg', 'author': {'@type': 'Organization', 'name': 'Hišni vodič', 'url': SITE}}
    viri_html = ''.join(f'<li id="vir-{s["id"]}"><a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["title"])}</a> <span>· {esc(s["publisher"])}</span></li>' for s in sources)
    sewer = span('prikljucek_kanalizacija')
    y, mo, d = cost['as_of'].split('-')
    checked = f'{int(d)}. {int(mo)}. {y}'
    return f'''{head(f'Koliko stane gradnja montažne hiše {YEAR}? Kalkulator stroškov · Hišni vodič', h1, desc, url, ld['image'], ld).replace('</head>', '<style>' + TABLE_CSS + COSTS_CSS + '</style></head>')}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / <a href="../{GUIDE}/">Cene</a> / Stroški gradnje</div>
    <div class="head"><div><h1 class="display">{h1}</h1><div class="prov">Kalkulator stroškov gradnje · podatki: {esc(data['collected'])}</div></div></div>
  </div>
  <div class="lede"><p>Cena montažne hiše ne pove, koliko boste plačali skupaj. Kalkulator ceni izbrane hiše prišteje, kar je običajno ni v ceni:
    zemljišče, komunalni prispevek, projektno dokumentacijo in nadzor, priključke, temeljno ploščo, zemeljska dela in zunanjo ureditev, ter odšteje subvencijo Eko sklada.
    Pri vsaki postavki je naveden vir in kako zanesljiva je številka.</p></div>
  <div class="calc">
    <form class="form" id="calc" onsubmit="return false">
      <label>Hiša<select id="h">{house_opts}</select></label>
      <div class="sub" id="custom" hidden>
        <label>Cena hiše (€)<input type="number" id="cp" inputmode="numeric" min="0" step="1000"></label>
        <label>Neto površina (m²)<input type="number" id="ca" inputmode="numeric" min="0" step="1"></label>
        <label>Etaže<select id="cf"><option value="1">pritličje</option><option value="1.5">z mansardo</option><option value="2">pritličje in nadstropje</option></select></label>
        <label class="ck"><input type="checkbox" id="cs"> Temeljna plošča je vključena v ceno</label>
      </div>
      <label>Zemljišče (€)<input type="number" id="plot" inputmode="numeric" min="0" step="1000" placeholder="0"><small>Neobvezno; pustite prazno, če parcelo že imate.</small></label>
      <label>Občina (komunalni prispevek)<select id="kp">{kp_opts}</select>
        <small>Ocena za tipičen primer: parcela okoli 600 m² in hiša okoli 150 m² neto. Cene iz odlokov so pred indeksacijo, zato je odmera lahko 8 do 33 % višja.</small></label>
      <label>Priključna moč elektrike<select id="kw"><option value="11">11 kW (3 × 16 A)</option><option value="17" selected>17 kW (3 × 25 A), s toplotno črpalko</option><option value="22">22 kW (3 × 32 A)</option></select></label>
      <label>Odpadne vode<select id="san"><option value="kan">Javna kanalizacija (priključek)</option><option value="mkcn">Mala čistilna naprava (MKČN)</option></select>
        <small>Pri MKČN je upoštevana le cena naprave; izkop in vgradnja sta dodatni strošek.</small></label>
      <label class="ck"><input type="checkbox" id="pd"> Projektna dokumentacija je že vključena v ceno hiše</label>
      <label>Zemeljska dela<select id="zem"><option value="l">Lahek teren</option><option value="n" selected>Ne vem</option><option value="t">Zahteven teren (skala)</option></select></label>
      <label class="ck"><input type="checkbox" id="zu" checked> Zunanja ureditev (dovoz, tlakovanje, zelenice)</label>
      <label class="ck"><input type="checkbox" id="snes"> Gradil bom po standardu sNES+ (Eko sklad)</label>
      <div class="sub" id="tierbox" hidden>
        <label>Izolacija in potreba po toploti<select id="tier">{tier_opts}</select></label>
        <small>Hiša mora biti skoraj pasivna: izračun PHPP, potreba po toploti in hladu največ 15 kWh/m²a, zrakotesnost n50 ≤ 0,6, rekuperacija z izkoristkom vsaj 80 %,
          zbiralnik deževnice vsaj 6 m³ in sončna elektrarna. Mnoge tipske hiše teh pogojev brez nadgradenj ne izpolnjujejo.</small>
      </div>
    </form>
    <div class="res">
      <div class="total" id="total" aria-live="polite"></div>
      <div class="scroll" id="lines"></div>
      <p class="credit-line">Večina tržnih cen ne navaja, ali vključujejo DDV. Za hišo z uporabno površino do 250 m² velja {pct(ddv['reduced'])} DDV, če gradnjo izvajalec obračuna neposredno investitorju kot gradbeno storitev, sicer {pct(ddv['general'])}.</p>
      <div class="tools"><button type="button" class="btn line" id="copy">Kopiraj povezavo</button></div>
    </div>
  </div>
  <section class="prose"><h2>Komunalni prispevek po občinah</h2>
    <p>Komunalni prispevek plačate občini pred izdajo gradbenega dovoljenja. Izračuna se iz površine parcele in bruto tlorisne površine hiše (BTP) ter cen komunalne opreme
      (ceste, vodovod, kanalizacija, javne površine) iz občinskega odloka: KP = Σ (A<sub>parcela</sub> × Cpo × Dpo + A<sub>BTP</sub> × Cto × Dto × Fn) × psz {cite(*kp['source_ids'][:3])}.
      Po izračunu vsevem.si za {covered} od {of} občin (parcela 600 m², 200 m² BTP) je povprečje {eur(nat['typical'])}, najmanj {eur(nat['min'])} ({nat_min}), največ {eur(nat['max'])} ({nat_max}) {cite(*nat['source_ids'])}.
      Cene v odlokih so večinoma iz let 2019–2021 in se ob odmeri lahko indeksirajo, zato je dejanski znesek lahko 8 do 33 % višji. Od 28. 3. 2026 velja nova uredba (Ur. l. RS 53/26) {cite('kp-uredba-2026')}.</p>
    <div class="scroll"><table class="tbl">{thead('Občina', 'Naš izračun (600 m², 180 m² BTP)', 'Vsevem.si (600 m², 200 m² BTP)', 'Zanesljivost')}<tbody>{''.join(kp_rows)}</tbody></table></div>
  </section>
  <section class="prose"><h2>Koliko stane projektna dokumentacija za hišo?</h2>
    <p>Za gradbeno dovoljenje potrebujete projekt DGD ({span('projekt_dgd')}, običajno okoli {eur(items['projekt_dgd']['typical'])}), za gradnjo še projekt za izvedbo PZI ({span('projekt_pzi')}),
      pred tem izhodišča oziroma idejno zasnovo ({span('projekt_izp')}). Celotna dokumentacija (IDZ, DGD, PZI, PID) stane {span('projekt_paket')} {cite(*items['projekt_paket']['source_ids'])}.</p>
    <p>Posebej plačate geodetski načrt ({span('geodetski_nacrt')}), geološko-geomehansko poročilo ({span('geolosko_porocilo')}), mnenja in soglasja (okoli {span('mnenja_soglasja')})
      ter obvezni gradbeni nadzor (okoli {span('gradbeni_nadzor')}) {cite('pd-primerjam', 'pd-glog')}. Nekateri proizvajalci montažnih hiš del dokumentacije vključijo v ceno; preverite ponudbo.</p>
  </section>
  <section class="prose"><h2>Koliko stanejo priključki za hišo?</h2>
    <p>Za nov priključek na elektro omrežje plačate omrežnino za priključno moč: {eles_txt} €/kW brez DDV pri nizki napetosti (cenik ELES 2026) {cite('el-eles-2026')}.
      Z DDV to znese {el(11)} za 11 kW, {el(17)} za 17 kW, kolikor običajno potrebuje hiša s toplotno črpalko, in {el(22)} za 22 kW. Izvedba priključka (kabel, merilna omarica) ni vključena.</p>
    <p>Vodovodni priključek stane {span('prikljucek_voda')}, kanalizacijski {sewer} {cite('pr-mojmojster')}. Kjer javne kanalizacije ni, potrebujete malo komunalno čistilno napravo:
      naprava za 4–6 PE stane okoli {span('mkcn')} brez izkopa in vgradnje {cite('pr-merkur-mkcn')}; številne občine jo sofinancirajo. Vsi priključki skupaj po oceni stanejo {span('prikljucki_skupaj')} {cite('gh-primerjam-2025')}.</p>
  </section>
  <section class="prose"><h2>Koliko stane temeljna plošča?</h2>
    <p>Toplotno izolirana temeljna plošča, kakršno zahtevajo proizvajalci montažnih hiš (podložni beton, dva sloja XPS, hidroizolacija, armatura in beton), stane {slab_lo}–{slab_hi} € na m² bruto površine plošče {cite('tp-mojmojster-2026')}; to je seštevek cen posameznih del (plošča, XPS, hidroizolacija, podložni beton, instalacije pod ploščo).
      Za ploščo s 100 m² to pomeni {span('temeljna_plosca_primer')}. Okvirne cene na portalih so nižje, 125–200 € na m² {cite('tp-primerjam-2026')}, dejanske ponudbe pa so bližje zgornjemu delu razpona {cite('tp-slotech-2024')}. Izkop in tamponsko nasutje stanejo dodatno okoli {span('izkop_tampon_m2')} na m² {cite('tp-mojmojster-2026')}, zato sta v kalkulatorju pri zemeljskih delih.
      Nižje ocene okoli 100–150 € na m², ki jih najdete na spletu, veljajo za neizolirano armiranobetonsko ploščo.
      Ni vključena v ceno, ki jo {verb(no_slab, 'navaja', 'navajata', 'navajajo')} {and_join(no_slab)} ({no_slab_n} {plural(no_slab_n, 'hiša', 'hiši', 'hiše', 'hiš')} v vodiču), zato jo kalkulator tem hišam prišteje.
      Površino plošče oceni kot tloris pritličja (neto površina, deljena s številom etaž) in 15 % za stene.</p>
  </section>
  <section class="prose"><h2>Koliko stanejo zemeljska dela in zunanja ureditev?</h2>
    <p>Izkop in zemeljska dela stanejo okoli {eur(items['zemeljska_dela']['typical'])} na lahkem terenu, na skali pa več kot {eur(mx)} {cite('gh-omisli-2026')}.
      Zunanja ureditev (dovoz, tlakovanje, zelenice) stane {span('zunanja_ureditev')}; asfaltiranje približno 400 m² dovoza okoli 4.000 € {cite('gh-omisli-2026')}. Za ograje zanesljivega slovenskega podatka nismo našli.</p>
  </section>
  <section class="prose"><h2>Subvencija Eko sklada za novogradnjo</h2>
    <p>Eko sklad po javnem pozivu 105SUB-sNESOB23 subvencionira skoraj ničenergijske hiše (sNES+): {', '.join(str(r) for r in t_rates[:-1])} ali {t_rates[-1]} € na m² neto ogrevane površine,
      odvisno od vrste izolacije in potrebe po toploti, za največ {snes['max_area_m2']} m² samostoječe hiše, torej do {eur(snes['max_eur'])} {cite('eko-105')}.
      Subvencija je največ 30 % upravičenih stroškov, ti pa so pri gradnji na ključ največ polovica pogodbene vrednosti, torej največ 15 % cene hiše.
      Projekt, nadzor, zunanja ureditev in sončna elektrarna niso upravičeni stroški.</p>
    <p>Pogoji so strogi: izračun PHPP, potreba po toploti in hladu največ 15 kWh/m²a, zrakotesnost n50 ≤ 0,6, rekuperacija vsaj 80 %, zbiralnik deževnice vsaj 6 m³, sončna elektrarna in vsaj 70 % obnovljivih virov.
      {and_join(subsidized)} {verb(subsidized, 'navaja', 'navajata', 'navajajo')} ceno, ki že upošteva subvencijo, zato je kalkulator pri teh hišah ne odšteje še enkrat.</p>
  </section>
  <section class="prose"><h2>Koliko je DDV pri gradnji hiše?</h2>
    <p>Za stanovanjsko hišo velja znižana stopnja {pct(ddv['reduced'])}, če je njena uporabna površina (vsota bivalnih prostorov) največ 250 m² in izvajalec gradnjo obračuna neposredno investitorju
      kot gradbeno storitev {cite('ddv-pravilnik-54')}. Sicer velja {pct(ddv['general'])}. Za hišo v kompletu brez montaže ter za kuhinjo in vgradne omare je lahko stopnja {pct(ddv['general'])}; preverite pri proizvajalcu ali na FURS.
      Večina tržnih cen v tem kalkulatorju ne navaja, ali vključujejo DDV.</p>
  </section>
  <section class="prose"><h2>Viri</h2><ol class="viri">{viri_html}</ol>
    <p class="credit-line">Vsi viri so bili pregledani {checked}. Komunalni prispevek je najmanj natančna številka: odloki ga računajo od bruto površine, ki jo ocenimo kot 1,2 × neto,
      cone, faktorji za stanovanjske hiše in olajšave pa znesek spremenijo. Tržne cene (dokumentacija, priključki, plošča, zemeljska dela, zunanja ureditev) so z gradbenih portalov z neznanim vzorcem; uporabite jih kot razpon, ne kot ponudbo.
      Noben aktualen vir ne pove, kateri proizvajalci imajo projektno dokumentacijo v ceni. Pri elektriki je upoštevana le omrežnina za priključno moč. Cen priključkov za optiko in plin ter vgradnje MKČN nismo našli.</p>
  </section>
  <div class="actions">
    <a class="btn glow" href="{SITE}#kviz">Poiščite hišo, ki vam pristaja <span class="arrow">→</span></a>
    <a class="btn line" href="../{GUIDE}/">Primerjava cen</a>
    <a class="btn line" href="../{COMPARE}/">Primerjava hiš</a>
  </div>
</main>
{FOOT}
<script type="application/json" id="calc-data">{calc_json}</script>
<script>{COSTS_JS}</script>
</body>
</html>
'''


# Old addresses Google may already know, as instant redirects to the new ones.
MOVED = {f'kager-vita-nova-{k}-family': f'kager-vita-nova-{k}-linija' for k in ('classic', 'edition', 'urbana', 'modern')}


def moved(new):
    return (f'<!doctype html><html lang="sl"><head><meta charset="utf-8"><title>Preusmeritev</title><link rel="canonical" href="{SITE}{new}/">'
            f'<meta http-equiv="refresh" content="0; url=../{new}/"></head><body><a href="../{new}/">{SITE}{new}/</a></body></html>\n')


def write(folder, html_):
    os.makedirs(folder, exist_ok=True)
    open(os.path.join(folder, 'index.html'), 'w', encoding='utf-8').write(html_)


# shortcut: pages of models removed from the JSON are not deleted; delete their folders by hand.
for p, m in models:
    write(m['slug'], page(p, m))
for p in data['providers']:
    write(p['id'], maker(p))
write(GUIDE, guide())
write(PLANS, plans_page())
write(COMPARE, compare_page())
write(CHEAP, cheap_page())
write(SMALL, small_page())
write(COSTS, costs_page())
for old, new in MOVED.items():
    assert new in slugs, new
    write(old, moved(new))

# index.html: slugs into the data (the catalog JS links to them) and a static link list crawlers see without JS.
links = ''.join(f'<div><h3><a href="{p["id"]}/">{esc(p["name"])}</a></h3><ul>' + ''.join(f'<li><a href="{m["slug"]}/">{esc(m["name"])}</a></li>' for m in p['models']) + '</ul></div>'
                for p in data['providers'])
src = DATA_RE.sub(lambda mo: mo.group(1) + json.dumps(data, ensure_ascii=False) + mo.group(3), src)
src = re.sub(r'(<!-- model-links -->).*?(<!-- /model-links -->)', lambda mo: mo.group(1) + links + mo.group(2), src, flags=re.S)


def home_faq():
    """Questions and answers on the home page, as static text with numbers from the data (the rest of the page is built by JS)."""
    provs = data['providers']
    priced = [m for _, m in models if m['price_eur'] and m['area_m2']]
    med_m2 = eur(round(statistics.median(m['price_eur'] / m['area_m2'] for m in priced)))
    areas = sorted(m['area_m2'] for _, m in models if m['area_m2'])
    mid = [a for a in areas if 120 <= a < 160]
    no_slab = [p['name'] for p in provs if any('brez temeljne plošče' in m['price_stage'].lower() for m in p['models'] if m['price_eur'])]
    warranties = sorted({p['warranty_years'] for p in provs if p.get('warranty_years')})
    by = lambda key: ''.join(f'<li><a href="{p["id"]}/">{esc(p["name"])}</a>: {esc(p[key])}</li>' for p in provs if p.get(key))
    qa = [
        ('Koliko stane montažna hiša?',
         f'<p>Med {len(priced)} tipskimi montažnimi hišami slovenskih proizvajalcev z objavljeno ceno je najcenejša {eur(min(m["price_eur"] for m in priced))}, '
         f'najdražja {eur(max(m["price_eur"] for m in priced))}. Srednja cena je {med_m2} na m² bivalne površine.</p>'
         f'<p>Cene niso neposredno primerljive, ker proizvajalci navajajo cene za različne pakete. <a href="{GUIDE}/">Primerjava cen po proizvajalcih</a></p>'),
        ('Kateri so slovenski proizvajalci montažnih hiš?',
         f'<p>V vodiču je {len(models)} tipskih hiš {len(provs)} proizvajalcev:</p><ul>' +
         ''.join(f'<li><a href="{p["id"]}/">{esc(p["name"])}</a>, {len(p["models"])} {plural(len(p["models"]), "hiša", "hiši", "hiše", "hiš")}</li>' for p in provs) + '</ul>'),
        ('Koliko časa traja gradnja montažne hiše?', f'<p>Proizvajalci, ki čas gradnje objavljajo, navajajo:</p><ul>{by("build_time")}</ul>'),
        ('Kako velike so tipske montažne hiše?',
         f'<p>Od {round(areas[0])} do {round(areas[-1])} m². Največ, {len(mid)} od {len(areas)}, jih ima med 120 in 160 m² bivalne površine.</p>'
         f'<p><a href="{PLANS}/">Tlorisi montažnih hiš po velikosti</a></p>'),
        ('Ali so montažne hiše energijsko varčne?', f'<p>Proizvajalci navajajo energijski razred in toplotno prehodnost zunanje stene (U v W/m²K, nižja je boljša):</p><ul>{by("energy_class")}</ul>'),
        ('Kaj običajno ni vključeno v ceno?',
         '<p>Zemljišče, projektna dokumentacija in gradbeno dovoljenje, komunalni prispevek in priključki, zemeljska dela ter zunanja ureditev.' +
         (f' {and_join(no_slab)} v ceno {"ne vključuje" if len(no_slab) == 1 else "ne vključujeta" if len(no_slab) == 2 else "ne vključujejo"} temeljne plošče.' if no_slab else '') + ' Preverite popis del v ponudbi.</p>'),
        ('Kakšno garancijo dajejo proizvajalci?',
         f'<p>Na konstrukcijo od {warranties[0]} do {warranties[-1]} let, odvisno od proizvajalca. Garancijo za instalacije in opremo preverite v ponudbi.</p>'),
    ]
    return ('<div class="eyebrow">Vprašanja</div><h2 class="display">Montažne hiše: pogosta vprašanja</h2><div class="faq-grid">' +
            ''.join(f'<article><h3>{q}</h3>{a}</article>' for q, a in qa) + '</div>')


src = re.sub(r'(<!-- faq -->).*?(<!-- /faq -->)', lambda mo: mo.group(1) + home_faq() + mo.group(2), src, flags=re.S)
open('index.html', 'w', encoding='utf-8').write(src)

locs = [SITE, SITE + GUIDE + '/', SITE + PLANS + '/', SITE + CHEAP + '/', SITE + SMALL + '/', SITE + COSTS + '/'] + [SITE + p['id'] + '/' for p in data['providers']] + [SITE + s + '/' for s in slugs]
open('sitemap.xml', 'w', encoding='utf-8').write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
                                                  ''.join(f'  <url><loc>{l}</loc></url>\n' for l in locs) + '</urlset>\n')

assert len(slugs) == len(models) and all(os.path.isfile(l[len(SITE):] + 'index.html') for l in locs) and src.count('<li><a href="') >= len(models)
print(f'{len(slugs)} pages, {len(locs)} sitemap URLs')
