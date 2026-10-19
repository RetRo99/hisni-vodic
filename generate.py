#!/usr/bin/env python3
"""Writes one static page per house model (/<maker>-<model>/index.html), the price guide
(/cena-montazne-hise/), the house links in the catalog of index.html, and sitemap.xml, all from the
JSON embedded in index.html. Run after editing that JSON:  python3 generate.py"""
import collections, datetime, glob, html, json, os, re, statistics, unicodedata

SITE = 'https://hisomer.si/'
GUIDE = 'cena-montazne-hise'
PLANS = 'tlorisi-montaznih-his'
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
        'Cene so informativne; pred odločitvijo preverite aktualno ponudbo pri proizvajalcu. Hišni vodič ni povezan s proizvajalci.</p></div></footer>')


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
    sib_html = (f'<section><h2>Druge hiše proizvajalca {esc(p["name"])}</h2><ul class="siblings">' +
                ''.join(f'<li><a href="../{o["slug"]}/">{esc(o["name"])}</a></li>' for o in siblings) + '</ul></section>') if siblings else ''
    note = ' Opomba: ' + esc(', '.join(m['flags'])) + '.' if m['flags'] else ''
    stage = esc(m['price_stage']) if price else 'Proizvajalec cene ne objavlja.'
    plans_html = ('<section><h2>Tloris</h2><div class="plans">' + ''.join(
        f'<a href="../{f}"><img src="../{f}" alt="{esc(plan_alt(m, name, i, len(plans)))}" loading="lazy"></a>'
        for i, f in enumerate(plans, 1)) + f'</div><p class="credit-line">Tloris: {esc(p["name"])}, '
        f'<a href="{esc(m["url"])}" target="_blank" rel="noopener">stran hiše pri proizvajalcu ↗</a> · <a href="../{PLANS}/">Vsi tlorisi</a></p></section>') if plans else ''
    title = f"{name} – cena, tloris, m² · Hišni vodič"
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
  </div>
  {plans_html}
  <div class="two">
    <section class="maker-info"><h2>O proizvajalcu {esc(p['name'])}</h2><p>{esc(p.get('description', ''))}</p>{maker_link}</section>
    <div class="edge"><div class="eyebrow">Prednost proizvajalca {esc(p['name'])}</div>{esc(p.get('edge') or '')}{facts_html}</div>
  </div>
  {sib_html}
</main>
{FOOT}
</body>
</html>
'''


TABLE_CSS = '''
.page > * { min-width: 0; }
.scroll { overflow-x: auto; border-radius: var(--r); box-shadow: 0 0 0 1px var(--line); }
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
                    f'<td>{ROOF.get(m["roof"], "—")}</td>{n(price)}{n(m2)}</tr>')
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
  <section><h2>Vse hiše proizvajalca {esc(name)}</h2><div class="scroll"><table class="tbl">{thead('Hiša', 'Površina', 'Spalnice', 'Streha', 'Cena', 'Na m²')}<tbody>{''.join(rows)}</tbody></table></div></section>
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
for old, new in MOVED.items():
    assert new in slugs, new
    write(old, moved(new))

# index.html: slugs into the data (the catalog JS links to them) and a static link list crawlers see without JS.
links = ''.join(f'<div><h3><a href="{p["id"]}/">{esc(p["name"])}</a></h3><ul>' + ''.join(f'<li><a href="{m["slug"]}/">{esc(m["name"])}</a></li>' for m in p['models']) + '</ul></div>'
                for p in data['providers'])
src = DATA_RE.sub(lambda mo: mo.group(1) + json.dumps(data, ensure_ascii=False) + mo.group(3), src)
src = re.sub(r'(<!-- model-links -->).*?(<!-- /model-links -->)', lambda mo: mo.group(1) + links + mo.group(2), src, flags=re.S)
open('index.html', 'w', encoding='utf-8').write(src)

locs = [SITE, SITE + GUIDE + '/', SITE + PLANS + '/'] + [SITE + p['id'] + '/' for p in data['providers']] + [SITE + s + '/' for s in slugs]
open('sitemap.xml', 'w', encoding='utf-8').write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
                                                  ''.join(f'  <url><loc>{l}</loc></url>\n' for l in locs) + '</urlset>\n')

assert len(slugs) == len(models) and all(os.path.isfile(l[len(SITE):] + 'index.html') for l in locs) and src.count('<li><a href="') >= len(models)
print(f'{len(slugs)} pages, {len(locs)} sitemap URLs')
