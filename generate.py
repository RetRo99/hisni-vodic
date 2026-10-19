#!/usr/bin/env python3
"""Writes one static page per house model (/<maker>-<model>/index.html), the price guide
(/cena-montazne-hise/), the house links in the catalog of index.html, and sitemap.xml, all from the
JSON embedded in index.html. Run after editing that JSON:  python3 generate.py"""
import collections, datetime, glob, html, json, os, re, shutil, statistics, struct, subprocess, unicodedata

SITE = 'https://hisomer.si/'
GUIDE = 'cena-montazne-hise'
PLANS = 'tlorisi-montaznih-his'
CHEAP = 'najcenejse-montazne-hise'
SMALL = 'majhne-montazne-hise'
COMPARE = 'primerjava'
COSTS = 'koliko-stane-gradnja-hise'
KP = 'komunalni-prispevek'
EKO = 'eko-sklad-subvencija-novogradnja'
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

src = open('index.html', encoding='utf-8').read()
DATA_RE = re.compile(r'(<script id="data" type="application/json">)(.*?)(</script>)')
data = json.loads(DATA_RE.search(src).group(2))

ROOF = {'gable': 'dvokapna', 'flat': 'ravna', 'mono': 'enokapna', 'hip': 'štirikapna', 'multi': 'večkapna'}
STYLE = {  # agrees with "slog" (masculine): "Arhitekturni slog: klasičen."
    'classic': 'klasičen', 'classic timber-glass': 'klasičen, les in steklo', 'classic/contemporary': 'klasično-sodoben',
    'classic/modern': 'klasično-moderen', 'contemporary timber-glass': 'sodoben, les in steklo', 'minimalist': 'minimalističen',
    'modern': 'moderen', 'modern (minimalist gable, extended roof)': 'moderen, minimalistična dvokapnica s podaljšano streho',
    'modern / solid wood': 'moderen, masivni les', 'modern alpine/scandinavian': 'moderen alpski oz. skandinavski',
    'modern atrium': 'moderen, z atrijem', 'modern cubic': 'moderen kubičen', 'modern minimalist glass house': 'moderen minimalističen, veliko stekla',
    'modern timber-glass hybrid': 'moderen, les in steklo', 'modern urban timber-glass': 'moderen urban, les in steklo',
    'modern villa': 'moderen, vila', 'modern-classic': 'moderno-klasičen', 'modern/scandinavian': 'moderen skandinavski',
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

COST = json.load(open('data/stroski.json', encoding='utf-8'))
FIN = json.load(open('data/financiranje.json', encoding='utf-8'))
SLAB = next(i for i in COST['items'] if i['key'] == 'temeljna_plosca_m2')['value']
SLAB_MID = (SLAB['min'] + SLAB['max']) / 2
INFO = {i['id']: i for i in json.load(open('data/proizvajalci-info.json', encoding='utf-8'))}
ROOMS_FLAG = 'spalnice = število sob'  # a data note: the maker gives rooms, not bedrooms
# data flags as visitor text on the house page; a flag missing here stays internal (the rooms flag shows as the "Sobe" spec label instead)
FLAG_SL = {'spletna cena se razlikuje od cenika': 'Cena je s strani hiše pri proizvajalcu; cenik 2026 navaja nekoliko drugačno ceno.',
           'brez fasadne obloge in terase': 'Cena ne vključuje fasadne obloge in terase.'}
# a maker description that states a model count uses the count in the data ("okoli 34 tipskih hiš" while 33 are listed)
for p in data['providers']:
    n_m = len(p['models'])
    p['description'] = re.sub(r'(?:okoli |približno )?\d+ tipskih hiš', lambda mo: f"{n_m} {plural(n_m, 'tipska hiša', 'tipski hiši', 'tipske hiše', 'tipskih hiš')}",
                              p['description'])


def num_sl(v):
    return f'{v:g}'.replace('.', ',')


# Comparable price: the maker's price plus the slab estimate where the price leaves the slab out, with the calculator's
# footprint rule (net m² / floors × 1,15) at the middle of temeljna_plosca_m2. cmp_ok is false for prices that stay
# unlike the rest even so: after a subsidy or discount, or a basic package that isn't turnkey. Rankings use only cmp_ok.
for p, m in models:
    for k in ('price_cmp', 'cmp_note', 'cmp_ok', 'thumb'):  # popped and set again in this order, so the JSON is the same on every run
        m.pop(k, None)
    if m['price_eur'] is None:
        continue
    st = (m['price_stage'] or '').lower()
    no_slab = 'brez temeljne plošče' in st
    reduced, basic = 'subvencij' in st or 'popust' in st, 'osnovni' in st
    add = int(round(m['area_m2'] / m['floors'] * 1.15 * SLAB_MID, -2)) if no_slab and m['area_m2'] else 0
    notes = ([f'vključena ocena temeljne plošče ~{eur(add)}'] if add else ['brez temeljne plošče, površina ni znana'] if no_slab else []) + \
        (['cena že po odbitku subvencije Eko sklada' + (' in popusta' if 'popust' in st else '') if 'eko sklad' in st else
          'cena že po odbitku subvencij in popustov'] if reduced else []) + \
        (['osnovni paket, ne na ključ'] if basic else [])
    m['price_cmp'] = m['price_eur'] + add
    if notes:
        m['cmp_note'] = ', '.join(notes)
    m['cmp_ok'] = not (reduced or basic)
CMP_EXPLAIN = (f'<b>Primerljiva cena</b> je cena proizvajalca, ki ji pri hišah brez temeljne plošče prištejemo oceno plošče: tloris pritličja '
               f'(neto površina, deljena s številom etaž, in 15 % za stene) × {num_sl(SLAB_MID)} €/m², sredina razpona {SLAB["min"]}–{SLAB["max"]} €/m² iz '
               f'<a href="../{COSTS}/">kalkulatorja stroškov</a>. Cen, ki so že zmanjšane za subvencijo Eko sklada ali popuste, in osnovnih paketov, ki niso na ključ, '
               'ne razvrščamo med druge: navedemo jih posebej, z opombo, in jih nikoli ne imenujemo najcenejše.')
ABOUT = 'o-vodicu'
SHOW = 'kje-si-ogledati-montazne-hise'
# one line in place of the method paragraph on every page that ranks prices
CMP_LINE = (f'Razvrščeno po primerljivi ceni (s temeljno ploščo); cene po subvenciji ali s popustom in osnovni paketi so navedeni posebej. '
            f'<a href="../{ABOUT}/#cene">Kako primerjamo cene</a>')


def ok(m):
    return bool(m.get('cmp_ok'))


def price_tag(m):
    """A short tag for a price that isn't comparable, for lists that show only the maker's price."""
    if m['price_eur'] is None or ok(m):
        return ''
    st = m['price_stage'].lower()
    return 'osnovni paket' if 'osnovni' in st else 'po odbitku subvencije' if 'subvencij' in st else 'po popustu'


def cmp_sub(m):
    """The secondary price line: the comparable price where it differs from the maker's, and the note."""
    if m['price_eur'] is None:
        return ''
    if m['price_cmp'] != m['price_eur']:
        return f'Primerljiva cena ~{eur(m["price_cmp"])}' + (f' · {m["cmp_note"]}' if m.get('cmp_note') else '')
    return m.get('cmp_note') or ''


# N-7: an estimate for unpriced houses from the maker's median comparable €/m² (the basis of every €/m² on the site, cmp_ok houses only),
# only where the maker has at least 5 such houses
EST_MIN = 5
EST_M2 = {}
for p in data['providers']:
    ms = [m for m in p['models'] if m['price_eur'] and m['area_m2'] and ok(m)]
    if len(ms) >= EST_MIN:
        EST_M2[p['id']] = (round(statistics.median(m['price_cmp'] / m['area_m2'] for m in ms)), len(ms),
                           collections.Counter(m['price_stage'] for m in ms).most_common(1)[0][0])


def estimate(p, m):
    """(rounded estimate, median €/m², priced count, the stage those prices are for), or None."""
    if m['price_eur'] is not None or not m['area_m2'] or p['id'] not in EST_M2:
        return None
    med, n, stage = EST_M2[p['id']]
    return int(round(med * m['area_m2'], -3)), med, n, stage


def jpeg_size(path):
    """(width, height) from a JPEG's SOF header."""
    b = open(path, 'rb').read()
    i = 2
    while i + 9 < len(b):
        if b[i] != 0xFF:
            i += 1
            continue
        mk = b[i + 1]
        if 0xC0 <= mk <= 0xCF and mk not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack('>HH', b[i + 5:i + 9])
            return w, h
        i += 1 if mk == 0xFF else 2 if mk in (0xD8, 0x01) or 0xD0 <= mk <= 0xD7 else 2 + struct.unpack('>H', b[i + 2:i + 4])[0]
    raise ValueError(path)


SIPS = shutil.which('sips')


def thumb(src, width):
    """A `width` px wide copy of img/.../x.jpg at img/.../thumb/x.jpg, made once with macOS sips; the original if it can't be made."""
    out = os.path.join(os.path.dirname(src), 'thumb', os.path.basename(src))
    if not os.path.isfile(out) and SIPS and os.path.isfile(src) and jpeg_size(src)[0] > width:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        subprocess.run([SIPS, '--resampleWidth', str(width), '-s', 'formatOptions', '72', src, '--out', out], capture_output=True)
    return out if os.path.isfile(out) else src


def img_tag(src, width, alt=''):
    """A lazy <img> of the thumbnail with its real width and height."""
    t = thumb(src, width)
    w, h = jpeg_size(t)
    return f'<img src="../{esc(t)}" width="{w}" height="{h}" alt="{esc(alt)}" loading="lazy">'


for p, m in models:
    if m.get('image'):
        m['thumb'] = thumb(m['image'], 320)

# Jargon: the first match on each page gets an <abbr title>, and the page ends with a short list of what they mean.
GLOSS = [
    (r'\bBTP\b', 'BTP', 'bruto tlorisna površina: površina vseh etaž, merjena po zunanjih merah sten'),
    (r'\bpsz\b', 'psz', 'prispevna stopnja zavezanca: delež stroškov komunalne opreme, ki ga plača investitor'),
    (r'\bCpo\b', 'Cpo', 'cena komunalne opreme na m² parcele, določi jo občinski odlok'),
    (r'\bCto\b', 'Cto', 'cena komunalne opreme na m² bruto tlorisne površine, določi jo občinski odlok'),
    (r'\bDpo\b', 'Dpo', 'delež parcele v izračunu komunalnega prispevka'),
    (r'\bDto\b', 'Dto', 'delež površine objekta v izračunu komunalnega prispevka'),
    (r'\bFn\b', 'Fn', 'faktor namembnosti: utež za vrsto stavbe, za stanovanjske hiše jo določi odlok'),
    (r'\bQH\b', 'QH', 'letna potreba po toploti za ogrevanje na m² ogrevane površine (kWh/m²a)'),
    (r'\bQK\b', 'QK', 'letna potreba po hladu za hlajenje na m² (kWh/m²a)'),
    (r'\bn50\b', 'n50', 'zrakotesnost: kolikokrat se zrak v hiši izmenja v eni uri pri tlačni razliki 50 Pa; manjša številka je boljša'),
    (r'\bPHPP\b', 'PHPP', 'program za izračun energijske bilance pasivne hiše (Passivhaus Projektierungspaket)'),
    (r'\bIDZ\b', 'IDZ', 'idejna zasnova, prvi korak projekta'),
    (r'\bDGD\b', 'DGD', 'dokumentacija za pridobitev gradbenega dovoljenja'),
    (r'\bPZI\b', 'PZI', 'projekt za izvedbo, po katerem se hiša gradi'),
    (r'\bPID\b', 'PID', 'projekt izvedenih del, ki opiše hišo, kot je bila zgrajena'),
    (r'\bIII\. faza\b', 'III. faza', 'stopnja gradnje: zunaj dokončana hiša; kaj točno vključuje, določi proizvajalec v popisu del'),
    (r'\bIV\. (?:gradbena )?faza\b', 'IV. faza', 'stopnja gradnje: zunaj dokončana hiša z delom notranjih del; natančen obseg je v popisu del proizvajalca'),
    (r'sNES[+⁺]', 'sNES+', 'skoraj ničenergijska stavba po pogojih Eko sklada, pogoj za subvencijo za novo hišo'),
    (r'(?i:\bdelni ključ\b)', 'delni ključ', 'hiša z instalacijami in delom notranjih del, brez dela končne opreme; obseg določi proizvajalec'),
    (r'\bDSTI\b', 'DSTI', 'razmerje med obroki vseh kreditov in neto dohodkom; Banka Slovenije ga omejuje na največ 50 %'),
    (r'\bLTV\b', 'LTV', 'razmerje med zneskom kredita in vrednostjo nepremičnine, zastavljene za kredit'),
    (r'\bEURIBOR\b', 'EURIBOR', 'medbančna obrestna mera v evroobmočju; spremenljiva obrestna mera je EURIBOR in pribitek banke'),
    (r'(?i:\banuitet\w*)', 'anuiteta', 'enak mesečni obrok, ki vsebuje obresti in del glavnice'),
    (r'(?i:\bna ključ\b)', 'na ključ', 'vseljiva hiša z instalacijami, tlaki, kopalnicami in ogrevanjem; obseg opreme se med proizvajalci razlikuje'),
]
GLOSS_SKIP = {'script', 'style', 'title', 'select', 'option', 'textarea', 'abbr', 'button', 'summary', 'dialog'}


def gloss(page_html):
    a, b = page_html.find('<main'), page_html.rfind('</main>')
    if a < 0 or b < 0:
        return page_html
    parts, seen, skip, keep = re.split(r'(<[^>]+>)', page_html[a:b]), [], 0, []
    for i, part in enumerate(parts):
        if part.startswith('<'):
            t = re.match(r'</?([a-zA-Z0-9]+)', part)
            if t and t.group(1).lower() in GLOSS_SKIP and not part.endswith('/>'):
                skip += -1 if part.startswith('</') else 1
            continue
        if skip:
            continue
        for pat, term, tip in GLOSS:
            if term in seen:
                continue
            mo = re.search(pat, part)
            if mo:
                seen.append(term)
                # focusable, so the meaning shows on tap and keyboard focus too (CSS tooltip), and screen readers get it from the box
                keep.append(f'<abbr tabindex="0" data-tip="{esc(tip)}" aria-describedby="gl-{slugify(term)}">{mo.group(0)}</abbr>')
                part = part[:mo.start()] + f'\x00{len(keep) - 1}\x00' + part[mo.end():]  # placeholder, so later terms can't match inside the title
        parts[i] = re.sub('\x00(\\d+)\x00', lambda mo: keep[int(mo.group(1))], part)
    box = ('<details class="gloss"><summary>Kaj pomenijo izrazi na tej strani?</summary><dl>' +
           ''.join(f'<div><dt>{esc(t)}</dt><dd id="gl-{slugify(t)}">{esc(tip)}</dd></div>' for _, t, tip in GLOSS if t in seen) + '</dl></details>\n') if seen else ''
    return page_html[:a] + ''.join(parts) + box + page_html[b:]

# Shared look: tokens, base, top bar and the result-card pieces, lifted straight from index.html's <style>.
css = re.search(r'<style>(.*?)</style>', src, re.S).group(1)
CSS = css[css.index(':root {'):css.index('/* ---------- hero')] + '\n'.join(
    l for l in css.splitlines() if l.startswith(('.btn', '.price', '.specs', '.edge', '.facts', '.two', 'footer'))) + '''
.bar { position: static; }
.mark { color: var(--ink); text-decoration: none; white-space: nowrap; }
@media (max-width: 420px) {  /* five nav links and the wordmark in 343 px */
  .bar .wrap { gap: 10px; }
  .bar .mark { font-size: 13px; font-stretch: 100%; letter-spacing: 0; gap: 8px; }
  .bar .mark svg { width: 22px; height: 22px; }
  .bar nav { gap: 8px; font-size: 13px; }
}
@media (max-width: 370px) { .bar nav { gap: 6px; font-size: 12px; } }
.page { display: grid; gap: 28px; padding-block: 8px 64px; }
.crumbs a { color: var(--mist); text-decoration: none; }
.crumbs a:hover { color: var(--ink); }
.head { display: flex; justify-content: space-between; align-items: end; flex-wrap: wrap; gap: 18px 30px; }
.head h1 { font-size: clamp(36px, 6vw, 72px); margin-top: 12px; }
.head .prov { color: var(--mist); margin-top: 10px; }
.photo { position: relative; margin: 0; border-radius: var(--r); overflow: hidden; background: var(--dusk); box-shadow: 0 0 0 1px var(--line); aspect-ratio: 600 / 315; }
.photo picture { display: contents; }
.photo img { width: 100%; height: 100%; object-fit: cover; display: block; }
.photo figcaption { position: absolute; left: 12px; top: 12px; padding: 6px 10px; border-radius: 999px; background: rgba(10,18,32,.78); font: 500 11px/1 var(--font-data); letter-spacing: .12em; text-transform: uppercase; }
@media (min-width: 900px) { .photo { aspect-ratio: auto; height: min(56vh, 634px); } }
.specs dt { font-size: 11px; }
@media (max-width: 640px) {
  /* M-1: the primary action full width, the others two to a row, the maker link as plain text, so the photo stays near the fold */
  .actions.hact { display: grid; grid-template-columns: 1fr 1fr; grid-auto-flow: dense; gap: 8px; }
  .actions.hact .btn { justify-content: center; text-align: center; padding: 12px 14px; font-size: 14px; min-height: 48px; }
  .actions.hact .btn.glow { order: -1; grid-column: 1 / -1; font-size: 16px; }
  .actions.hact .ask { grid-column: 1 / -1; }
  .actions.hact .btn.mk { grid-column: 1 / -1; min-height: 44px; padding: 8px 4px; background: none; box-shadow: none; backdrop-filter: none; color: var(--mist); font-weight: 500; text-decoration: underline; text-underline-offset: 3px; }
}
.na { color: var(--mist); font: 400 14px/1.2 var(--font-body); }
.price .est { display: block; font: 500 12px/1.3 var(--font-data); letter-spacing: .12em; text-transform: uppercase; color: var(--mist); margin-bottom: 6px; }
abbr[data-tip] { position: relative; text-decoration: underline dotted; text-underline-offset: 3px; cursor: help; border-radius: 3px; }
abbr[data-tip]:hover::after, abbr[data-tip]:focus::after { content: attr(data-tip); position: absolute; left: 0; top: calc(100% + 6px); z-index: 40;
  width: max-content; max-width: 300px; padding: 8px 12px; border-radius: 10px; background: var(--slate); box-shadow: 0 0 0 1px var(--line), 0 10px 30px rgba(0,0,0,.55);
  color: var(--ink); font: 400 13px/1.45 var(--font-body); letter-spacing: 0; text-transform: none; white-space: normal; text-align: left; pointer-events: none; }
@media (max-width: 640px) { abbr[data-tip]:hover::after, abbr[data-tip]:focus::after { position: fixed; left: 16px; right: 16px; top: auto; bottom: calc(16px + env(safe-area-inset-bottom, 0px)); width: auto; max-width: none; z-index: 60; } }
sub { font-size: max(12px, .75em); }
.gloss { border-radius: var(--r); box-shadow: inset 0 0 0 1px var(--line); padding: 14px 18px; color: #c9d3e6; font-size: 14px; max-width: 60em; }
.gloss summary { cursor: pointer; color: var(--ink); font-weight: 600; }
.gloss dl { display: grid; gap: 8px; margin: 12px 0 0; }
.gloss dt { display: inline; font-weight: 600; color: var(--ink); }
.gloss dt::after { content: ": "; }
.gloss dd { display: inline; margin: 0; }
.basis { color: var(--mist); font-size: 14px; margin: 10px 0 0; max-width: 60em; }
.basis a, .basis b { color: var(--ink); }
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
  <nav><a href="../#kviz">Kviz</a><a href="../#katalog">Katalog</a><a href="../{GUIDE}/">Cene</a><a href="../{COSTS}/">Stroški</a><a href="../{PLANS}/">Tlorisi</a></nav>
</div></div>'''
FOOT = (f'<footer><div class="wrap"><p>Podatki so zbrani s spletnih strani in ponudbenih brošur proizvajalcev ({esc(data["collected"])}). '
        'Cene so informativne; pred odločitvijo preverite aktualno ponudbo pri proizvajalcu. Hišni vodič ni povezan s proizvajalci.</p>'
        f'<nav aria-label="Vodiči"><a href="../{GUIDE}/">Cene montažnih hiš</a><a href="../{CHEAP}/">Najcenejše hiše</a><a href="../{SMALL}/">Majhne hiše</a>'
        f'<a href="../{COSTS}/">Stroški gradnje</a><a href="../{KP}/">Komunalni prispevek</a><a href="../{EKO}/">Subvencija Eko sklada</a><a href="../{PLANS}/">Tlorisi</a><a href="../{COMPARE}/">Primerjava</a><a href="../{SHOW}/">Kje si ogledati hiše</a><a href="../{ABOUT}/">O vodiču</a></nav></div></footer>\n<script src="../compare.js"></script>')


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


NA = '<span class="na">ni podatka</span>'


def cmp_btn(p, m, cls='cmp sm'):
    name = esc(f"{p['name']} {m['name']}")
    return f'<button type="button" class="{cls}" data-slug="{m["slug"]}" data-name="{name}" aria-label="Dodaj {name} v primerjavo">+ Primerjaj</button>'


def figure(img, alt, maker):
    """The hero: phones (<= 640 px) always get the 720 px image, wider screens choose by width; never a larger file that isn't sharper."""
    if not img:
        return ''
    big = img.replace('img/', 'img/large/')
    w, h = jpeg_size(img)
    bw = jpeg_size(big)[0] if os.path.isfile(big) else 0
    wide = f'<source media="(min-width: 641px)" srcset="../{esc(img)} {w}w, ../{esc(big)} {bw}w" sizes="(min-width: 1240px) 1208px, 100vw">' if bw > w else ''
    return (f'<figure class="photo"><picture>{wide}<img src="../{esc(img)}" width="{w}" height="{h}" alt="{esc(alt)}"></picture>'
            f'<figcaption>Foto: {esc(maker)}</figcaption></figure>')


def maker_bits(p):
    """The maker's website link and its facts list, shared by house and maker pages."""
    facts = [f for f in [p.get('construction') and 'Konstrukcija: ' + p['construction'], p.get('energy_class') and 'Energija: ' + p['energy_class'],
                         p.get('build_time') and 'Gradnja: ' + p['build_time'],
                         p.get('warranty_years') and f"Garancija na konstrukcijo: {p['warranty_years']} let"] if f]
    site = re.sub(r'^https?://(www\.)?', '', p.get('website', '')).rstrip('/')
    return (f'<p><a href="{esc(p["website"])}" target="_blank" rel="noopener">{esc(site)} ↗</a></p>' if site else '',
            '<ul class="facts">' + ''.join(f'<li>{esc(f)}</li>' for f in facts) + '</ul>' if facts else '')


NOT_SAID = 'ni navedeno'


def src_link(url):
    return f' <a class="src" href="{esc(url)}" target="_blank" rel="noopener">vir ↗</a>' if url else ''


def maker_facts(p, info):
    """The facts box of a maker page from data/proizvajalci-info.json, each fact with its source; "ni navedeno" where the maker says nothing."""
    if not info:
        return ''
    said = lambda f: f and f.get('text') and f['text'] != NOT_SAID
    fact = lambda f: (esc(f['text']) if said(f) else f'<span class="na">{NOT_SAID}</span>') + src_link((f or {}).get('url'))
    fo = info.get('founded') or {}
    founded = (str(fo['year']) if fo.get('year') else f'<span class="na">{NOT_SAID}</span>' + (f' ({esc(fo["note"])})' if fo.get('note') else '')) + src_link(fo.get('url'))
    q = info.get('quote') or {}
    phone = q.get('phone') if q.get('phone') and q['phone'] != NOT_SAID else None
    quote = ((f'<a href="{esc(q["form_url"])}" target="_blank" rel="noopener">obrazec za povpraševanje ↗</a>' if q.get('form_url') else
              f'<span class="na">obrazec ni naveden</span>') + (f' · tel. {esc(phone)}' if phone else ' · <span class="na">telefon ni naveden</span>'))
    rows = [('Ustanovljen', founded), ('Garancija', fact(info.get('warranty'))), ('Čas gradnje', fact(info.get('build_time'))),
            ('Kaj vključuje »na ključ«', fact(info.get('turnkey_scope'))), ('Kje gradi', fact(info.get('delivery_area'))), ('Povpraševanje', quote)]
    return (f'<section class="mfacts" id="dejstva"><h2>{esc(p["name"])} na kratko</h2><dl>' +
            ''.join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in rows) +
            f'</dl><p class="credit-line">Povzeto po straneh proizvajalca, preverjeno {ddate(info["checked"])}. '
            f'<a href="../{SHOW}/#{p["id"]}">Vzorčne hiše in dnevi odprtih vrat</a></p></section>')


MFACTS_CSS = """
.mfacts dl { display: grid; gap: 0; margin: 0; border-radius: var(--r); box-shadow: inset 0 0 0 1px var(--line); }
.mfacts dl > div { display: grid; grid-template-columns: minmax(0, 13em) minmax(0, 1fr); gap: 4px 20px; padding: 12px 16px; border-bottom: 1px solid var(--line); }
.mfacts dl > div:last-child { border-bottom: 0; }
.mfacts dt { font: 500 12px/1.5 var(--font-data); letter-spacing: .1em; text-transform: uppercase; color: var(--mist); }
.mfacts dd { margin: 0; color: #c9d3e6; font-size: 15px; max-width: 60em; }
.mfacts a, .shows a { color: var(--ink); text-underline-offset: 3px; }
.mfacts a.src, .shows a.src { color: var(--mist); font-size: 13px; white-space: nowrap; }
@media (max-width: 640px) { .mfacts dl > div { grid-template-columns: minmax(0, 1fr); } }
"""


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
    rooms_only = ROOMS_FLAG in m['flags']
    rooms = ([f"{bed} {plural(bed, 'soba', 'sobi', 'sobe', 'sob')}"] if rooms_only and bed else []) + \
        [f"{n} {plural(n, w + 'o', w + 'i', w + 'e', w)}" for n, w in (((bed, 'spalnic'),) if not rooms_only else ()) + ((bath, 'kopalnic'),) if n]
    s2 = ('Ima ' + ' in '.join(rooms) + '. ' if rooms else '') + (f"Streha je {roof}. " if roof else '') + \
        (f"Arhitekturni slog: {STYLE[m['style']]}." if m['style'] else '')
    est = estimate(p, m)
    s3 = f"Cena po podatkih proizvajalca: {price} – {m['price_stage']}." if price else \
        'Proizvajalec cene za ta model ne objavlja, ponudbo dobite na povpraševanje.' + \
        (f' Okvirna ocena ~{eur(est[0])} je izračunana iz mediane primerljivih cen {p["name"]} na m² in ni cena proizvajalca.' if est else '')
    desc_bits = [b for b in [f'{area} m²' if area else '', (f"{bed} {plural(bed, 'soba', 'sobi', 'sobe', 'sob')}" if rooms_only else f"{bed} {plural(bed, 'spalnica', 'spalnici', 'spalnice', 'spalnic')}") if bed else '',
                             f'{roof} streha' if roof else ''] if b]
    desc = f"{name}: montažna hiša" + (', ' + ', '.join(desc_bits) if desc_bits else '') + \
        (f". Cena {price} in kaj vključuje." if price else '. Cena na povpraševanje.') + \
        (' Tloris in primerjava' if plans else ' Primerjava') + ' s tipskimi hišami drugih slovenskih proizvajalcev.'
    image_abs = SITE + (img.replace('img/', 'img/large/') if img else 'img/og/site.jpg')
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
        f'<a href="../{o["slug"]}/"><div class="pic">' + (img_tag(o['image'], 320) if o.get('image') else '') +
        f'</div><span><b>{esc(op["name"])} {esc(o["name"])}</b>{round(o["area_m2"])} m² · {FLOORS.get(o["floors"], ("—",))[0]} · '
        f'{eur(o["price_eur"]) + (" · " + price_tag(o) if price_tag(o) else "") if o["price_eur"] else "cena na povpraševanje"}</span></a>' for op, o in sim) + '</div></section>') if sim else ''
    sib_html = (f'<section><h2>Druge hiše proizvajalca {esc(p["name"])}</h2><ul class="siblings">' +
                ''.join(f'<li><a href="../{o["slug"]}/">{esc(o["name"])}</a></li>' for o in siblings) + '</ul></section>') if siblings else ''
    note = ''.join(' ' + esc(FLAG_SL[f]) for f in m['flags'] if f in FLAG_SL)
    if price:
        big, stage = price, esc(m['price_stage']) + (f'<br>{esc(cmp_sub(m))}' if cmp_sub(m) else '')
    elif est:
        big = f'<small class="est">Okvirna ocena</small>~{eur(est[0])}'
        no_slab = 'brez temeljne plošče' in est[3].lower()
        stage = (f'Ocena, ne cena proizvajalca: mediana primerljivih cen {est[2]} hiš {esc(p["name"])} na m² ({eur(est[1])}/m²) × {area} m². '
                 f'Te cene so: {esc(est[3])}{", s prišteto oceno temeljne plošče" if no_slab else ""}. Proizvajalec cene za ta model ne objavlja.')
    else:
        big, stage = 'Na povpraševanje', 'Proizvajalec cene ne objavlja.'
    quote = (INFO.get(p['id']) or {}).get('quote') or {}
    ask = (f'<a class="btn line ask" href="{esc(quote["form_url"])}" target="_blank" rel="noopener">Povpraševanje pri proizvajalcu ↗</a>'
           if not price and quote.get('form_url') else '')
    plans_html = ('<section><h2>Tloris</h2><div class="plans">' + ''.join(
        f'<a href="../{f}">{img_tag(f, 600, plan_alt(m, name, i, len(plans)))}</a>'
        for i, f in enumerate(plans, 1)) + f'</div><p class="credit-line">Tloris: {esc(p["name"])}, '
        f'<a href="{esc(m["url"])}" target="_blank" rel="noopener">stran hiše pri proizvajalcu ↗</a> · <a href="../{PLANS}/">Vsi tlorisi</a></p></section>') if plans else ''
    title = f"{name} – cena, tloris, m² · Hišni vodič"
    calc = bool(price and area)  # the calculator lists only houses with a price and an area
    # unpriced: the calculator's own-offer mode, prefilled with the estimate; the slab is added when the maker's prices leave it out
    calc_href = f'#h={m["slug"]}' if calc else \
        f'#h=lastna&cp={est[0]}&ca={area}&cf={m["floors"]:g}&cs=1' if est else ''
    quiz = f'<a class="btn {"line" if calc_href else "glow"}" href="{SITE}#kviz">Ali vam pristaja? Rešite kviz{"" if calc_href else " <span class=arrow>→</span>"}</a>'
    costs_link = (f'<a class="btn glow" href="../{COSTS}/{calc_href}">Izračunaj celotne stroške gradnje{"" if calc else " z oceno"} <span class="arrow">→</span></a>'
                  if calc_href else '')
    return f'''{head(title, name + ' – cena in lastnosti', desc, url, image_abs, ld)}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / <a href="../#katalog">Katalog</a> / <a href="../{p['id']}/">{esc(p['name'])}</a></div>
    <div class="head">
      <div><h1 class="display">{esc(name)}</h1><div class="prov">Montažna hiša · {esc(p['name'])}</div></div>
      <div class="price"><b>{big}</b><span>{stage}</span></div>
    </div>
  </div>
  <dl class="specs">{cell('Etaže', floor_short)}{cell('Površina', f'{area} m²' if area else NA)}{cell('Sobe' if rooms_only else 'Spalnice', bed or NA)}{cell('Kopalnice', bath or NA)}{cell('Streha', roof or NA)}</dl>
  <div class="actions hact">
    {costs_link}{cmp_btn(p, m, 'btn line cmp')}{ask}{quiz}
    <a class="btn line mk" href="{esc(m['url'])}" target="_blank" rel="noopener">{'Podrobnosti' if plans else 'Tloris in podrobnosti'} pri proizvajalcu ↗</a>
  </div>
  {photo}
  <div class="lede"><p>{esc(s1)} {esc(s2)}</p><p>{esc(s3)}{note} {'Opis' if plans else 'Tloris, opis'} in aktualno ponudbo si oglejte pri proizvajalcu. <a href="../{GUIDE}/">Primerjajte cene vseh proizvajalcev</a>.</p></div>
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
.tbl thead th { font: 500 11px/1.3 var(--font-data); letter-spacing: .12em; text-transform: uppercase; color: var(--mist); white-space: nowrap; }
.tbl tbody th { font-weight: 600; white-space: nowrap; }
.tbl .n { font-family: var(--font-data); font-size: 14px; white-space: nowrap; }
.tbl .stage { color: var(--mist); font-size: 13px; min-width: 260px; }
.tbl td:first-child { min-width: 170px; }
.tbl a { color: var(--ink); text-decoration-color: var(--line); text-underline-offset: 3px; }
.tbl a:hover { color: var(--glow); }
.tbl .n small { display: block; min-width: 13em; max-width: 18em; white-space: normal; font: 400 12.5px/1.4 var(--font-body); color: var(--mist); margin-top: 3px; }
.tbl .hth { display: flex; align-items: center; gap: 12px; }
.tbl .hth img { width: 72px; height: auto; border-radius: 8px; flex: none; background: var(--slate); }
.points { margin: 0; padding-left: 20px; color: #c9d3e6; display: grid; gap: 10px; max-width: 48em; }
.points b { color: var(--ink); }
.tbl .grp th { font: 500 12px/1.3 var(--font-data); letter-spacing: .1em; text-transform: uppercase; color: var(--glow); white-space: normal; padding-top: 18px; }
/* N-5: on phones every static table becomes a stack of cards; each cell's data-label (from its column head) is shown above the value */
@media (max-width: 640px) {
  .tbl.cards, .tbl.cards tbody, .tbl.cards tfoot { display: block; }
  .tbl.cards thead { display: none; }
  .tbl.cards tr { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px 16px; padding: 14px 16px; border-bottom: 1px solid var(--line); }
  .tbl.cards tbody:last-child tr:last-child, .tbl.cards tfoot tr { border-bottom: 0; }
  .tbl.cards tr > * { display: block; padding: 0; border: 0; min-width: 0; max-width: none; white-space: normal; text-align: left; }
  .tbl.cards tr > :first-child, .tbl.cards .stage, .tbl.cards [colspan], .tbl.cards td:not([data-label]) { grid-column: 1 / -1; }
  .tbl.cards td:first-child, .tbl.cards .stage, .tbl.cards .n small { min-width: 0; max-width: none; }
  .tbl.cards tbody th { white-space: normal; font-size: 16px; }
  .tbl.cards [data-label]::before { content: attr(data-label); display: block; margin-bottom: 3px; font: 500 11px/1.3 var(--font-data); letter-spacing: .1em; text-transform: uppercase; color: var(--mist); }
  .tbl.cards .grp th { padding-top: 4px; }
}
'''


def card_labels(page_html):
    """Gives every static <table class="tbl"> the class "cards" and each body cell a data-label from its column head (N-5)."""
    def table(mo):
        t = mo.group(0)
        head = re.search(r'<thead>(.*?)</thead>', t, re.S)
        labels = [] if not head else ['' if 'sr-only' in h else html.unescape(re.sub(r'<[^>]+>', '', h)).strip()
                                      for h in re.findall(r'<th\b[^>]*>(.*?)</th>', head.group(1), re.S)]

        def row(rm):
            col = 0

            def cell(cm):
                nonlocal col
                tag, attrs = cm.group(1), cm.group(2)
                label = labels[col] if col < len(labels) else ''
                span = re.search(r'colspan="(\d+)"', attrs)
                col += int(span.group(1)) if span else 1
                return f'<{tag}{attrs} data-label="{esc(label)}">' if label and not span and col > 1 else cm.group(0)
            return re.sub(r'<(td|th)\b([^>]*)>', cell, rm.group(0))
        body = re.sub(r'<tr\b.*?</tr>', row, t[head.end():] if head else t, flags=re.S)
        return ((t[:head.end()] if head else '') + body).replace('<table class="tbl">', '<table class="tbl cards">', 1)
    return re.sub(r'<table class="tbl">.*?</table>', table, page_html, flags=re.S)


def thead(*cols):
    return '<thead><tr>' + ''.join(f'<th scope="col">{c}</th>' for c in cols) + '</tr></thead>'


def cmp_cell(m):
    """The comparable price with its note, for tables ranked by it."""
    return f'<td class="n">{eur(m["price_cmp"])}' + (f'<small>{esc(m["cmp_note"])}</small>' if m.get('cmp_note') else '') + '</td>'


def cmp_text(m):
    """The comparable price for running text: with the maker's price when they differ, else with the note."""
    return eur(m['price_cmp']) + (f'; cena proizvajalca {eur(m["price_eur"])}' if m['price_cmp'] != m['price_eur'] else
                                  f'; {esc(m["cmp_note"])}' if m.get('cmp_note') else '')


def thumb_link(p, m):
    """The house name with a small photo, for tables."""
    return (f'<div class="hth">{img_tag(m["image"], 320) if m.get("image") else ""}'
            f'<a href="../{m["slug"]}/">{esc(p["name"])} {esc(m["name"])}</a></div>')


YEAR = re.search(r'\d{4}', data['collected']).group(0)


def and_join(names):
    return ', '.join(names[:-1]) + ' in ' + names[-1] if len(names) > 1 else names[0]


def guide():
    url = SITE + GUIDE + '/'
    per_m2 = lambda m: m['price_cmp'] / m['area_m2']  # one €/m² basis on every page: the comparable price
    priced = [(p, m) for p, m in models if m['price_eur'] and m['area_m2']]
    comparable = [(p, m) for p, m in priced if ok(m)]
    apart = sorted(((p, m) for p, m in priced if not ok(m)), key=lambda pm: pm[1]['price_eur'])
    lo = min(comparable, key=lambda pm: pm[1]['price_cmp'])
    hi = max(comparable, key=lambda pm: pm[1]['price_cmp'])
    med_m2 = eur(round(statistics.median(per_m2(m) for _, m in comparable))) + '/m²'
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
                    f'{n(eur(round(statistics.median(per_m2(m) for m in ms if ok(m)))) + "/m²" if any(ok(m) for m in ms) else "ni primerljivo")}<td class="stage">{esc(stage)}'
                    f'{"" if all(ok(m) for m in ms) else "<br>Ni v razvrstitvah: " + esc(ms[0].get("cmp_note", ""))}</td></tr>')

    bands = []
    for a, b, label in ((0, 100, 'do 100 m²'), (100, 140, '100–140 m²'), (140, 10 ** 4, '140 m² in več')):
        ms = [m for _, m in comparable if a <= m['area_m2'] < b]
        if ms:
            bands.append(f'<tr><th scope="row">{label}</th>{n(len(ms))}{n(eur(min(m["price_cmp"] for m in ms)))}'
                         f'{n(eur(round(statistics.median(m["price_cmp"] for m in ms))))}{n(eur(round(statistics.median(per_m2(m) for m in ms))) + "/m²")}</tr>')
    by_cmp = sorted(comparable, key=lambda pm: pm[1]['price_cmp'])
    row = lambda p, m: (f'<tr><td>{thumb_link(p, m)}</td>{n(str(round(m["area_m2"])) + " m²")}{n(eur(m["price_eur"]))}{cmp_cell(m)}'
                        f'{n(eur(round(per_m2(m))) + "/m²")}</tr>')
    cheapest = ''.join(row(p, m) for p, m in by_cmp[:10])
    apart_rows = ''.join(row(p, m) for p, m in apart[:10])

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
    points.append(f'<li><b>Kaj običajno ni v ceni.</b> Zemljišče, projektna dokumentacija in gradbeno dovoljenje, <a href="../{KP}/">komunalni prispevek</a> in priključki, '
                  'zemeljska dela ter zunanja ureditev. Preverite v ponudbi.</li>')
    if unpublished:
        points.append(f'<li><b>Brez objavljenih cen.</b> {and_join(unpublished)} {verb(unpublished, "cen tipskih hiš ne objavlja", "cen tipskih hiš ne objavljata", "cen tipskih hiš ne objavljajo")}; '
                      'ponudbo dobite na povpraševanje.</li>')

    h1 = f'Koliko stane montažna hiša v {YEAR}?'
    desc = (f'Cene {len(priced)} tipskih montažnih hiš slovenskih proizvajalcev, primerljivo (na ključ, s temeljno ploščo) od {eur(lo[1]["price_cmp"])} '
            f'do {eur(hi[1]["price_cmp"])}, mediana {med_m2}. Primerjava po proizvajalcih in velikosti ter kaj cena vključuje.')
    ld = {'@context': 'https://schema.org', '@type': 'Article', 'headline': h1, 'description': desc, 'inLanguage': 'sl', 'url': url,
          'dateModified': datetime.date.today().isoformat(), 'image': SITE + 'img/og/cene.jpg',
          'author': {'@type': 'Organization', 'name': 'Hišni vodič', 'url': SITE}}
    return f'''{head(f'Cena montažne hiše {YEAR}: primerjava proizvajalcev · Hišni vodič', h1, desc, url, ld['image'], ld).replace('</head>', '<style>' + TABLE_CSS + '</style></head>')}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / Cene</div>
    <div class="head"><div><h1 class="display">{h1}</h1><div class="prov">Primerjava cen tipskih hiš · podatki: {esc(data['collected'])}</div></div></div>
  </div>
  <div class="lede"><p>Cena objavljena za {len(priced)} tipskih montažnih hiš slovenskih proizvajalcev; {len(comparable)} od njih je primerljivih (na ključ, brez odbitih subvencij in popustov).
    Med njimi je po primerljivi ceni (s temeljno ploščo) najcenejša {link(*lo)} ({cmp_text(lo[1])}), najdražja {link(*hi)} ({cmp_text(hi[1])}).
    Mediana primerljive cene je <b>{med_m2}</b> bivalne površine.</p>
    <p>Proizvajalci navajajo cene za različne pakete, zato je v tabeli za vsakega navedeno, kaj cena vključuje. {len(apart)} cen je že zmanjšanih za subvencijo ali popust
    ali velja za osnovni paket; teh ne razvrščamo med druge, navedene so posebej.</p></div>
  <section><h2>Cene po proizvajalcih</h2><div class="scroll"><table class="tbl">{thead('Proizvajalec', 'Hiš s ceno', 'Cena od', 'Cena do', 'Primerljiva na m² (mediana)', 'Kaj cena vključuje')}<tbody>{''.join(rows)}</tbody></table></div></section>
  <section><h2>Cena glede na velikost</h2><div class="scroll"><table class="tbl">{thead('Površina', 'Primerljivih hiš', 'Najnižja primerljiva', 'Mediana primerljive', 'Mediana na m²')}<tbody>{''.join(bands)}</tbody></table></div>
    <p class="basis">Samo primerljive cene ({len(comparable)} hiš).</p></section>
  <section><h2>Najcenejše montažne hiše</h2><div class="scroll"><table class="tbl">{thead('Hiša', 'Površina', 'Cena proizvajalca', 'Primerljiva cena', 'Primerljiva na m²')}<tbody>{cheapest}</tbody></table></div>
    <p class="basis">{CMP_LINE}</p></section>
  <section><h2>Cene po subvenciji, s popustom ali za osnovni paket</h2><div class="scroll"><table class="tbl">{thead('Hiša', 'Površina', 'Cena proizvajalca', 'Primerljiva cena', 'Na m²')}<tbody>{apart_rows}</tbody></table></div>
    <p class="basis">Te cene niso primerljive z drugimi, zato niso v razvrstitvi najcenejših. Razvrščeno po ceni proizvajalca{f", prikazanih {min(10, len(apart))} od {len(apart)}" if len(apart) > 10 else ""}.</p></section>
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
    info = INFO.get(p['id'])
    count = f"{len(ms)} {plural(len(ms), 'tipska montažna hiša', 'tipski montažni hiši', 'tipske montažne hiše', 'tipskih montažnih hiš')}"
    img = next((m['image'] for m in ms if m.get('image')), None)
    n = lambda v: f'<td class="n">{v}</td>'
    rows = []
    for m in sorted(ms, key=lambda m: (m['area_m2'] or 10 ** 4, m['name'])):
        area = f"{round(m['area_m2'])} m²" if m['area_m2'] else '—'
        est = estimate(p, m)
        price = eur(m['price_eur']) + (f'<small>{esc(cmp_sub(m))}</small>' if cmp_sub(m) else '') if m['price_eur'] else \
            f'na povpraševanje<small>okvirna ocena ~{eur(est[0])}, ni cena proizvajalca</small>' if est else 'na povpraševanje'
        m2 = eur(round(m['price_cmp'] / m['area_m2'])) + '/m²' if m['price_eur'] and m['area_m2'] else '—'
        rows.append(f'<tr><td><a href="../{m["slug"]}/">{esc(m["name"])}</a></td>{n(area)}{n(m["bedrooms"] or "—")}'
                    f'<td>{ROOF.get(m["roof"], "—")}</td>{n(price)}{n(m2)}<td>{cmp_btn(p, m)}</td></tr>')
    others = ''.join(f'<li><a href="../{o["id"]}/">{esc(o["name"])}</a></li>' for o in data['providers'] if o is not p)
    maker_link, facts_html = maker_bits(p)
    desc = (f'{name}: {count}' + (f', cene od {eur(lo)} do {eur(hi)}' if priced else ', cene na povpraševanje') +
            '. Kaj cena vključuje, konstrukcija, energijski razred, čas gradnje in garancija.')
    image_abs = SITE + (img.replace('img/', 'img/large/') if img else 'img/og/site.jpg')
    ld = {'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': f'{name}: montažne hiše', 'url': url, 'description': desc,
          'inLanguage': 'sl', 'image': image_abs, 'about': {'@type': 'Organization', 'name': name, 'url': p.get('website')}}
    price_box = f'<b>od {eur(lo)}</b><span>{esc(stage)}</span>' if priced else '<b>Na povpraševanje</b><span>Proizvajalec cen ne objavlja.</span>'
    includes = f'Kaj vključuje cena: {esc(stage)}.' if priced else 'Cen tipskih hiš ne objavlja; ponudbo dobite na povpraševanje.'
    return f'''{head(f'{name}: montažne hiše, cene in modeli {YEAR} · Hišni vodič', f'{name}: montažne hiše, cene in modeli', desc, url, image_abs, ld).replace('</head>', '<style>' + TABLE_CSS + MFACTS_CSS + '</style></head>')}
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
  <section><h2>Vse hiše proizvajalca {esc(name)}</h2><div class="scroll"><table class="tbl">{thead('Hiša', 'Površina', 'Spalnice', 'Streha', 'Cena proizvajalca', 'Primerljiva na m²', '<span class="sr-only">Primerjava</span>')}<tbody>{''.join(rows)}</tbody></table></div></section>
  {maker_facts(p, info)}
  <div class="two">
    <div class="edge"><div class="eyebrow">Prednost proizvajalca {esc(name)}</div>{esc(p.get('edge') or '')}{facts_html}</div>
    <section class="maker-info"><h2>Spletna stran</h2>{maker_link}<p><a href="../{SHOW}/#{p['id']}">Kje si ogledati hiše {esc(name)}</a></p><h2>Drugi proizvajalci</h2><ul class="siblings">{others}</ul></section>
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
.more { display: none; }
@media (max-width: 640px) {
  /* R-1: two small cards to a row, and each size group shows its first 6 until "Pokaži vse" */
  .plan-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .card span { padding: 8px 10px 10px; font-size: 12.5px; line-height: 1.4; }
  .card b { font-size: 14px; }
  .plan-grid:not(.all) > .card:nth-child(n+7) { display: none; }
  .more { display: flex; justify-content: center; width: 100%; margin-top: 12px; }
}
'''


def plans_page():
    url = SITE + PLANS + '/'
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
                    eur(m['price_eur']) + (f' ({price_tag(m)})' if price_tag(m) else '') if m['price_eur'] else '']
            cards.append(f'<a class="card" href="../{m["slug"]}/"><div class="pic">{img_tag(plans[0], 600, plan_alt(m, name, 1, len(plans)))}</div>'
                         f'<span><b>{esc(name)}</b>{" · ".join(x for x in bits if x)}</span></a>')
        jump.append(f'<a href="#{anchor}">{label}</a>')
        more = f'<button type="button" class="btn line more" aria-expanded="false">Pokaži vse ({len(group)})</button>' if len(group) > 6 else ''
        sections.append(f'<section id="{anchor}"><h2>Tlorisi hiš {label} <small class="eyebrow">{len(group)}</small></h2><div class="plan-grid">{"".join(cards)}</div>{more}</section>')
    areas = [m['area_m2'] for _, m, _ in houses if m['area_m2']]
    makers = sorted({p['name'] for p, _, _ in houses}, key=[p['name'] for p in data['providers']].index)
    desc = (f'Tlorisi {len(houses)} tipskih montažnih hiš slovenskih proizvajalcev od {round(min(areas))} do {round(max(areas))} m², '
            'razvrščeni po velikosti, s ceno in številom spalnic.')
    image = SITE + 'img/og/tlorisi.jpg'
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
<script>document.addEventListener('click', e => {{ const b = e.target.closest('.more'); if (!b) return; b.previousElementSibling.classList.add('all'); b.setAttribute('aria-expanded', 'true'); b.hidden = true; }});</script>
{FOOT}
</body>
</html>
'''


COMPARE_CSS = '''
.page > * { min-width: 0; }
#cmp { position: relative; }
.cmp-tbl { table-layout: fixed; min-width: 640px; }
.cmp-tbl col.lab { width: 150px; }
.cmp-tbl th:first-child, .cmp-tbl td:first-child { min-width: 0; position: sticky; left: 0; background: var(--night); z-index: 1; }
.cmp-tbl thead th { text-transform: none; letter-spacing: 0; font: inherit; color: var(--ink); white-space: normal; vertical-align: bottom; }
.cmp-tbl .pic { aspect-ratio: 600 / 340; border-radius: 12px; overflow: hidden; background: var(--dusk); margin-bottom: 10px; }
.cmp-tbl .pic img { width: 100%; height: 100%; object-fit: cover; display: block; }
.cmp-tbl thead a { font: 700 18px/1.2 var(--font-display); }
.cmp-tbl thead small { display: block; color: var(--mist); margin: 2px 0 8px; }
.cmp-tbl .rm { font: inherit; font-size: 13px; border: 0; background: none; color: var(--mist); padding: 0; cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
.cmp-tbl tbody th { color: var(--mist); font-weight: 500; font-size: 13px; white-space: normal; }
.cmp-tbl td { font-size: 15px; overflow-wrap: anywhere; }
.cmp-tbl td.small { font-size: 13px; color: var(--mist); }
.cmp-tbl td small { display: block; font-size: 12.5px; color: var(--mist); margin-top: 4px; }
.cmp-tbl .best { color: var(--glow); }
.cmp-tbl .best::after { content: "najnižja"; display: inline-block; margin-left: 8px; padding: 2px 8px; border-radius: 999px; font: 500 11px/1.4 var(--font-data); letter-spacing: .08em; text-transform: uppercase; box-shadow: inset 0 0 0 1px var(--glow); }
.cmp-tbl .plan { display: block; background: #fff; border-radius: 10px; overflow: hidden; cursor: zoom-in; }
.cmp-tbl .plan img { width: 100%; height: auto; display: block; }
#cmp.diff tr.same { display: none; }
.sn { position: sticky; top: 0; z-index: 5; height: 0; }
.sn-in { overflow: hidden; background: var(--night); box-shadow: 0 1px 0 var(--line), 0 10px 24px -12px rgba(0,0,0,.6); border-radius: 0 0 12px 12px; visibility: hidden; }
.sn.on .sn-in { visibility: visible; }
.sn .cmp-tbl thead th { padding-block: 10px; vertical-align: middle; }
.sn .cmp-tbl thead a { font-size: 15px; text-decoration: none; color: var(--ink); }
.tools { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.tools select { font: inherit; color: var(--ink); background: var(--dusk); border: 0; box-shadow: inset 0 0 0 1px var(--line); border-radius: 999px; padding: 12px 18px; max-width: 100%; }
.tools .ck { display: inline-flex; gap: 10px; align-items: center; cursor: pointer; color: var(--ink); font-size: 15px; padding: 10px 4px; }
.tools .ck input { width: 18px; height: 18px; margin: 0; accent-color: var(--glow); }
.tools .ck[hidden] { display: none; }
#zoom { width: min(1100px, 96vw); max-height: 94vh; padding: 12px; border: 0; border-radius: var(--r); background: #fff; color: #0a1220; }
#zoom::backdrop { background: rgba(5,9,16,.82); }
#zoom img { display: block; max-width: 100%; max-height: calc(94vh - 90px); margin: 10px auto 0; height: auto; }
#zoom button { font: 600 15px/1 var(--font-body); color: #0a1220; background: #eef2f9; border: 0; border-radius: 999px; padding: 12px 18px; cursor: pointer; }
#zoom p { margin: 0 0 0 4px; display: inline; font-size: 14px; }
@media (max-width: 640px) {
  #sc, .sn-in { container-type: inline-size; }
  .cmp-tbl { min-width: 0; width: calc(92px + var(--n) * (100vw - 32px - 92px) / 2); width: calc(92px + var(--n) * (100cqw - 92px) / 2); }
  .cmp-tbl col.lab { width: 92px; }
  .cmp-tbl th, .cmp-tbl td { padding: 10px; }
  .cmp-tbl thead a { font-size: 15px; }
  .sn .cmp-tbl thead a { font-size: 13px; }
  .cmp-tbl .best::after { display: block; width: max-content; margin: 4px 0 0; }
}
.colnav { display: none; }
@media (max-width: 640px) {
  .colnav { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; color: var(--mist); font-size: 14px; }
  .colnav span { margin-right: auto; }
  .colnav button { font: inherit; font-size: 14px; color: var(--ink); background: var(--dusk); border: 0; box-shadow: inset 0 0 0 1px var(--line); border-radius: 999px; padding: 10px 14px; min-height: 44px; cursor: pointer; }
  .colnav button[aria-pressed="true"] { box-shadow: inset 0 0 0 1px var(--glow); color: var(--glow); }
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
  const NA = '<span class="na">ni podatka</span>';
  const perM2 = h => h.cmp && h.area ? Math.round(h.cmp / h.area) : null;
  const fromHash = decodeURIComponent(location.hash.slice(1)).split(',').filter(s => bySlug[s]).slice(0, 3);
  let picks = fromHash.length ? fromHash : window.HVCompare.get().filter(s => bySlug[s]);
  let io = null;
  // the badge compares only comparable prices (cmp_ok): not after a subsidy or discount, not a basic package
  function lowest(fn) { const v = picks.map(s => bySlug[s]).filter(h => h.ok).map(fn).filter(x => x != null); return v.length > 1 ? Math.min(...v) : null; }
  function render() {
    window.HVCompare.set(picks);
    history.replaceState(null, '', picks.length ? '#' + picks.join(',') : location.pathname);
    for (const o of $('add').options) o.disabled = !!o.value && picks.includes(o.value);
    $('add').hidden = picks.length >= 3;
    $('copy').hidden = $('difflab').hidden = picks.length < 2;
    if (io) io.disconnect();
    if (picks.length < 2) {
      $('cmp').innerHTML = `<div class="empty">${picks.length ? `Izbrana je <b>${esc(bySlug[picks[0]].name)}</b>. Dodajte še eno ali dve hiši.` : 'Izberite dve ali tri hiše.'}
        Dodate jih z izbirnikom zgoraj ali z gumbom »+ Primerjaj« v <a href="../#katalog">katalogu</a> in na straneh hiš.</div>`;
      return;
    }
    const hs = picks.map(s => bySlug[s]);
    const lowCmp = lowest(h => h.cmp), lowM2 = lowest(perM2);
    const rows = [
      ['Cena proizvajalca', h => h.price ? eur(h.price) : 'na povpraševanje'],
      ['Primerljiva cena', h => !h.cmp ? NA : h.ok ? `<span class="${h.cmp === lowCmp ? 'best' : ''}">${eur(h.cmp)}</span>${h.note ? `<small>${esc(h.note)}</small>` : ''}`
        : `<span class="na">ni primerljivo</span><small>${esc(h.note)}</small>`],
      ['Kaj cena vključuje', h => h.price ? esc(h.stage) : 'Proizvajalec cene ne objavlja.', 'small'],
      ['Celotni stroški', h => h.calc ? `<a href="../koliko-stane-gradnja-hise/#h=${h.slug}">Izračunaj v kalkulatorju →</a>` : NA],
      ['Površina', h => h.area ? h.area + ' m²' : NA],
      ['Primerljiva cena na m²', h => !perM2(h) ? NA : h.ok ? `<span class="${perM2(h) === lowM2 ? 'best' : ''}">${eur(perM2(h))}/m²</span>` : '<span class="na">ni primerljivo</span>'],
      ['Etaže', h => esc(h.floors)],
      ['Spalnice', h => h.bed ?? NA],
      ['Kopalnice', h => h.bath ?? NA],
      ['Streha', h => h.roof ? esc(h.roof) : NA],
      ['Konstrukcija', h => esc(h.construction), 'small'],
      ['Energija', h => esc(h.energy), 'small'],
      ['Gradnja', h => esc(h.build), 'small'],
      ['Garancija', h => h.warranty ? h.warranty + ' let' : NA],
      ['Tloris', h => h.plan ? `<a class="plan" href="../${esc(h.planFull)}"><img src="../${esc(h.plan)}" width="${h.planWH[0]}" height="${h.planWH[1]}" alt="Tloris – ${esc(h.name)}" loading="lazy"></a>` : NA],
    ];
    const cols = `<colgroup><col class="lab">${hs.map(() => '<col>').join('')}</colgroup>`;
    const tbl = `class="tbl cmp-tbl" style="--n:${hs.length}"`;
    const nav = hs.length > 2 ? `<div class="colnav" role="group" aria-label="Prikazani hiši"><span>Prikazani hiši</span>
      <button type="button" data-col="0" aria-pressed="true">1 in 2</button><button type="button" data-col="1" aria-pressed="false">2 in 3 →</button></div>` : '';
    $('cmp').innerHTML = nav + `<div class="sn" aria-hidden="true"><div class="sn-in" id="sn"><table ${tbl}>${cols}<thead><tr><th></th>${hs.map(h =>
        `<th><a tabindex="-1" href="../${h.slug}/">${esc(h.name)}</a></th>`).join('')}</tr></thead></table></div></div>
      <div class="scroll" id="sc"><table ${tbl}>${cols}<thead><tr><th><span class="sr-only">Lastnost</span></th>${hs.map(h => `<th scope="col">
        <div class="pic">${h.image ? `<img src="../${esc(h.image)}" width="${h.imageWH[0]}" height="${h.imageWH[1]}" alt="${esc(h.name)}">` : ''}</div>
        <a href="../${h.slug}/">${esc(h.name)}</a><small>${esc(h.maker)}</small><button type="button" class="rm" data-rm="${h.slug}">Odstrani</button></th>`).join('')}</tr></thead>
      <tbody>${rows.map(([label, f, cls]) => {
        const cells = hs.map(h => f(h) || NA);
        return `<tr${cells.every(c => c === cells[0]) ? ' class="same"' : ''}><th scope="row">${label}</th>${cells.map(c => `<td${cls ? ` class="${cls}"` : ''}>${c}</td>`).join('')}</tr>`;
      }).join('')}</tbody></table></div>`;
    const sc = $('sc'), sn = $('sn'), head = sc.querySelector('thead');
    sc.addEventListener('scroll', () => {
      sn.scrollLeft = sc.scrollLeft;
      const end = sc.scrollLeft > (sc.scrollWidth - sc.clientWidth) / 2;
      $('cmp').querySelectorAll('[data-col]').forEach(b => b.setAttribute('aria-pressed', String((b.dataset.col === '1') === end)));
    });
    io = new IntersectionObserver(([e]) => sn.parentNode.classList.toggle('on', !e.isIntersecting && e.boundingClientRect.top < 0));
    io.observe(head);
  }
  $('cmp').addEventListener('click', e => {
    const b = e.target.closest('[data-rm]');
    if (b) { picks = picks.filter(s => s !== b.dataset.rm); render(); return; }
    const c = e.target.closest('[data-col]');
    if (c) { const sc = $('sc'); sc.scrollTo({ left: c.dataset.col === '1' ? sc.scrollWidth : 0, behavior: 'smooth' }); return; }
    const a = e.target.closest('a.plan');
    if (a && $('zoom').showModal) {
      e.preventDefault();
      $('zimg').src = a.href; $('zimg').alt = a.querySelector('img').alt; $('zcap').textContent = a.querySelector('img').alt;
      $('zoom').showModal();
    }
  });
  $('zoom').addEventListener('click', e => { if (e.target === $('zoom') || e.target.closest('#zclose')) $('zoom').close(); });
  $('diff').addEventListener('change', e => $('cmp').classList.toggle('diff', e.target.checked));
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
        plan = thumb(plans[0], 600) if plans else None
        rows.append({'slug': m['slug'], 'name': f"{p['name']} {m['name']}", 'maker': p['name'], 'price': m['price_eur'], 'stage': m['price_stage'],
                     'cmp': m.get('price_cmp'), 'note': m.get('cmp_note'), 'ok': ok(m), 'calc': bool(m['price_eur'] and m['area_m2']),
                     'area': round(m['area_m2']) if m['area_m2'] else None, 'floors': FLOORS.get(m['floors'], ('—',))[0],
                     'bed': m['bedrooms'], 'bath': m['bathrooms'], 'roof': ROOF.get(m['roof']), 'image': m.get('thumb'),
                     'imageWH': jpeg_size(m['thumb']) if m.get('thumb') else None,
                     'plan': plan, 'planFull': plans[0] if plans else None, 'planWH': jpeg_size(plan) if plan else None,
                     'construction': p.get('construction'), 'energy': p.get('energy_class'),
                     'build': p.get('build_time'), 'warranty': p.get('warranty_years')})
    options = ''.join(f'<optgroup label="{esc(p["name"])}">' + ''.join(f'<option value="{m["slug"]}">{esc(m["name"])}</option>' for m in p['models']) + '</optgroup>'
                      for p in data['providers'])
    desc = 'Primerjajte do tri tipske montažne hiše slovenskih proizvajalcev: cena, kaj cena vključuje, m², cena na m², sobe, energija, garancija in tloris.'
    ld = {'@context': 'https://schema.org', '@type': 'WebPage', 'name': 'Primerjava montažnih hiš', 'url': url, 'description': desc, 'inLanguage': 'sl'}
    data_json = json.dumps(rows, ensure_ascii=False).replace('</', '<\\/')
    # noindex: the table is built in the browser from the link, so the page has no content of its own for search
    return (head('Primerjava montažnih hiš · Hišni vodič', 'Primerjava montažnih hiš', desc, url, SITE + 'img/og/site.jpg', ld)
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
    <label class="ck" id="difflab" hidden><input type="checkbox" id="diff"> Pokaži samo razlike</label>
    <button type="button" class="btn line" id="copy" hidden>Kopiraj povezavo</button>
  </div>
  <div id="cmp"></div>
  <p class="basis">Oznaka »najnižja« velja za primerljivo ceno in za primerljivo ceno na m², le med primerljivimi cenami. <a href="../{ABOUT}/#cene">Kako primerjamo cene</a></p>
  <div class="actions">
    <a class="btn glow" href="{SITE}#kviz">Poiščite hišo, ki vam pristaja <span class="arrow">→</span></a>
    <a class="btn line" href="../#katalog">Vse hiše v katalogu</a>
  </div>
</main>
<dialog id="zoom" aria-labelledby="zcap"><button type="button" id="zclose">Zapri</button><p id="zcap"></p><img id="zimg" alt=""></dialog>
{FOOT}
<script type="application/json" id="cmp-data">{data_json}</script>
<script>{COMPARE_JS}</script>
</body>
</html>
''')


CMP_TH = '<span class="sr-only">Primerjava</span>'


def house_link(p, m):
    return f'<a href="../{m["slug"]}/">{esc(p["name"])} {esc(m["name"])}</a>'


def cheap_page():
    url = SITE + CHEAP + '/'
    per_m2 = lambda m: m['price_cmp'] / m['area_m2']
    all_priced = [(p, m) for p, m in models if m['price_eur']]
    priced = [(p, m) for p, m in all_priced if ok(m)]  # only comparable prices are ranked
    apart = sorted(((p, m) for p, m in all_priced if not ok(m)), key=lambda pm: pm[1]['price_eur'])
    sized = [(p, m) for p, m in priced if m['area_m2']]
    n = lambda v: f'<td class="n">{v}</td>'

    def table(rows):
        body = ''.join(f'<tr><td>{thumb_link(p, m)}</td>{n(str(round(m["area_m2"])) + " m²" if m["area_m2"] else "—")}{n(eur(m["price_eur"]))}{cmp_cell(m)}'
                       f'{n(eur(round(per_m2(m))) + "/m²" if m["area_m2"] else "—")}<td class="stage">{esc(m["price_stage"])}</td><td>{cmp_btn(p, m)}</td></tr>'
                       for p, m in rows)
        return f'<div class="scroll"><table class="tbl">{thead("Hiša", "Površina", "Cena proizvajalca", "Primerljiva cena", "Primerljiva na m²", "Kaj cena vključuje", CMP_TH)}<tbody>{body}</tbody></table></div>'

    by_price = lambda rows: sorted(rows, key=lambda pm: pm[1]['price_cmp'])[:12]
    lo, lo_m2 = by_price(priced)[0], min(sized, key=lambda pm: per_m2(pm[1]))
    other = sorted({p['name'] for p, _ in apart}, key=[p['name'] for p in data['providers']].index)
    unpublished = [p['name'] for p in data['providers'] if not any(m['price_eur'] for m in p['models'])]
    verb = verb3
    rest = (f'{and_join(other)} {verb(other, "navaja", "navajata", "navajajo")} cene po odbitku subvencij ali popustov oziroma za osnovni paket, '
            f'zato {verb(other, "ni", "nista", "niso")} v razvrstitvi; te cene so v zadnji tabeli' if other else '') + \
        ('; ' if other and unpublished else '') + \
        (f'{and_join(unpublished)} {verb(unpublished, "cen ne objavlja", "cen ne objavljata", "cen ne objavljajo")}' if unpublished else '')
    rest_html = f'<p class="note">{esc(rest)}. <a href="../{GUIDE}/">Kaj vključujejo cene posameznih proizvajalcev</a></p>' if rest else ''

    desc = (f'Najcenejše montažne hiše na ključ od {eur(lo[1]["price_cmp"])} s temeljno ploščo, najnižja primerljiva cena na m² {eur(round(per_m2(lo_m2[1])))}. '
            f'Primerjava {len(priced)} primerljivih cen tipskih hiš slovenskih proizvajalcev in kaj cena vključuje.')
    image = SITE + (lo[1]['image'].replace('img/', 'img/large/') if lo[1].get('image') else 'img/og/cene.jpg')
    ld = {'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': 'Najcenejše montažne hiše', 'url': url, 'description': desc,
          'inLanguage': 'sl', 'image': image}
    return f'''{head(f'Najcenejše montažne hiše {YEAR}: na ključ in po m² · Hišni vodič', 'Najcenejše montažne hiše', desc, url, image, ld).replace('</head>', '<style>' + TABLE_CSS + '.note { color: var(--mist); font-size: 14px; margin: 10px 0 0; } .note a { color: var(--ink); text-underline-offset: 3px; }</style></head>')}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / <a href="../{GUIDE}/">Cene</a> / Najcenejše hiše</div>
    <div class="head"><div><h1 class="display">Najcenejše montažne hiše</h1><div class="prov">{len(priced)} primerljivih cen od {len(all_priced)} objavljenih · podatki: {esc(data['collected'])}</div></div></div>
  </div>
  <div class="lede"><p>Po primerljivi ceni (na ključ, s temeljno ploščo) je najcenejša montažna hiša {house_link(*lo)} ({cmp_text(lo[1])}). Najnižjo primerljivo ceno na m² ima {house_link(*lo_m2)} ({round(lo_m2[1]['area_m2'])} m², {eur(round(per_m2(lo_m2[1])))}/m²);
    večje hiše imajo praviloma nižjo ceno na m², zato je ta podatek uporaben predvsem za primerjavo hiš podobne velikosti.</p>
    <p>Proizvajalci navajajo cene za različne pakete, zato pred primerjavo preverite, kaj cena vključuje. <a href="../{GUIDE}/">Primerjava cen po proizvajalcih</a></p></div>
  <p class="basis">{CMP_LINE}</p>
  <section><h2>Najcenejše montažne hiše na ključ</h2>{table(by_price(priced))}{rest_html}</section>
  <section><h2>Najnižja primerljiva cena na m²</h2>{table(sorted(sized, key=lambda pm: per_m2(pm[1]))[:12])}</section>
  <section><h2>Cene po subvenciji, s popustom ali za osnovni paket</h2>{table(apart[:12])}
    <p class="note">Te cene niso primerljive z drugimi, zato niso razvrščene med najcenejše. Razvrščeno po ceni proizvajalca{f", prikazanih 12 od {len(apart)}" if len(apart) > 12 else ""}.</p></section>
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
.hc span small { display: block; font-size: 12.5px; line-height: 1.4; margin-top: 4px; }
.hc-act { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; padding: 0 14px 14px; font-size: 13px; }
.hc-act a { color: var(--ink); text-decoration-color: var(--line); text-underline-offset: 3px; }
'''


def small_page():
    url = SITE + SMALL + '/'
    houses = sorted(((p, m) for p, m in models if m['area_m2'] and m['area_m2'] <= 100), key=lambda pm: (pm[1]['area_m2'], pm[1]['name']))
    priced = [(p, m) for p, m in houses if m['price_eur']]
    lo = min((pm for pm in priced if ok(pm[1])), key=lambda pm: pm[1]['price_cmp'])
    areas = [round(m['area_m2']) for _, m in houses]
    sections = []
    for a, b, h2 in ((0, 60, 'Majhne montažne hiše do 60 m²'), (60, 80, 'Montažne hiše od 60 do 80 m²'), (80, 100, 'Montažne hiše od 80 do 100 m²')):
        cards = []
        for p, m in (t for t in houses if a < t[1]['area_m2'] <= b):
            plans = house_plans(m)
            bits = [f"{round(m['area_m2'])} m²", FLOORS.get(m['floors'], ('',))[0],
                    f"{m['bedrooms']} {plural(m['bedrooms'], 'spalnica', 'spalnici', 'spalnice', 'spalnic')}" if m['bedrooms'] else '',
                    eur(m['price_eur']) if m['price_eur'] else 'cena na povpraševanje']
            sub = f'<small>{esc(cmp_sub(m))}</small>' if cmp_sub(m) else ''
            pic = img_tag(m['image'], 320) if m.get('image') else ''
            plan = f'<a href="../{plans[0]}">Tloris</a>' if plans else ''
            cards.append(f'<div class="hc"><a href="../{m["slug"]}/"><div class="pic">{pic}</div><span><b>{esc(p["name"])} {esc(m["name"])}</b>'
                         f'{" · ".join(x for x in bits if x)}{sub}</span></a><div class="hc-act">{plan}{cmp_btn(p, m)}</div></div>')
        if cards:
            sections.append(f'<section><h2>{h2} <small class="eyebrow">{len(cards)}</small></h2><div class="hgrid">{"".join(cards)}</div></section>')
    count = f"{len(houses)} {plural(len(houses), 'tipska montažna hiša', 'tipski montažni hiši', 'tipske montažne hiše', 'tipskih montažnih hiš')}"
    desc = (f'Majhne montažne hiše do 100 m²: {count} slovenskih proizvajalcev od {min(areas)} do {max(areas)} m², '
            f'primerljive cene od {eur(lo[1]["price_cmp"])}, tlorisi in kaj cena vključuje.')
    image = SITE + (lo[1]['image'].replace('img/', 'img/large/') if lo[1].get('image') else 'img/og/cene.jpg')
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
    med primerljivimi cenami (na ključ, s temeljno ploščo) je najcenejša {house_link(*lo)} ({eur(lo[1]['price_cmp'])}{'; cena proizvajalca ' + eur(lo[1]['price_eur']) if lo[1]['price_cmp'] != lo[1]['price_eur'] else ''}, {round(lo[1]['area_m2'])} m², {esc(lo[1]['price_stage'])}).</p>
    <p>Za ostale je cena na povpraševanje. Proizvajalci navajajo cene za različne pakete; cene po subvenciji ali za osnovni paket so na karticah označene in niso v razvrstitvi.
    <a href="../{GUIDE}/">Kaj cena vključuje pri posameznem proizvajalcu</a></p></div>
  <p class="basis">Primerljiva cena vključuje oceno temeljne plošče, kjer je proizvajalec ne vključi. <a href="../{ABOUT}/#cene">Kako primerjamo cene</a></p>
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
.form select, .form input[type=text] { font: inherit; font-size: 16px; color: var(--ink); background: var(--slate); border: 0; box-shadow: inset 0 0 0 1px var(--line); border-radius: 12px; padding: 10px 12px; width: 100%; min-width: 0; }
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
@media (min-width: 641px) { .lines td { width: 1%; white-space: nowrap; } }
.lines th small.src { font-size: 12px; overflow-wrap: anywhere; }
.lines th small.src a { color: var(--mist); text-decoration: none; }
.lines th small.src a:hover { color: var(--ink); }
.total .likely { font-size: 15px; color: var(--ink); }
.total .likely strong { color: var(--glow); font-variant-numeric: tabular-nums; }
.stack { display: flex; height: 10px; border-radius: 5px; overflow: hidden; margin-top: 14px; background: var(--line); }
.stack i { display: block; height: 100%; }
.legend { list-style: none; margin: 10px 0 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 13px; color: var(--mist); }
.legend li { display: inline-flex; align-items: center; gap: 6px; }
.legend i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
.legend i.neg { background: #7fd1a8; }
.legend span { color: var(--ink); font-variant-numeric: tabular-nums; }
.stotal { display: none; }
@media (max-width: 959px) {
  .stotal { display: flex; position: fixed; z-index: 29; left: 16px; right: 16px; bottom: calc(16px + env(safe-area-inset-bottom, 0px)); justify-content: space-between; align-items: center; gap: 12px;
    padding: 12px 18px; border-radius: 18px; background: var(--dusk); box-shadow: inset 0 0 0 1px var(--glow), 0 12px 40px rgba(0,0,0,.5); color: var(--ink); text-decoration: none; font-variant-numeric: tabular-nums; font-weight: 600; }
  .stotal[hidden] { display: none; }
  .stotal small { display: block; font: 500 11px/1.2 var(--font-data); letter-spacing: .14em; text-transform: uppercase; color: var(--mist); }
  .stotal .go { color: var(--glow); font-size: 14px; white-space: nowrap; }
  .calc { padding-bottom: 72px; }
}
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
#kredit .tbl th small { display: block; font-weight: 400; font-size: 12.5px; color: var(--mist); margin-top: 2px; }
#kredit .tbl td:last-child { font-size: 13.5px; color: #c9d3e6; }
@media (min-width: 641px) { #kredit .tbl td:last-child { min-width: 16em; } }
.fin { display: grid; gap: 14px; min-width: 0; margin-top: 12px; }
.fin h2 { margin: 0; }
.fin .form { grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr)); align-items: start; }
.fstats { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 160px), 1fr)); gap: 12px; }
.fstats > div { padding: 14px 16px; border-radius: 12px; box-shadow: inset 0 0 0 1px var(--line); min-width: 0; }
.fstats .fmain { background: linear-gradient(160deg, rgba(255,196,119,.14), rgba(255,157,77,.04)); box-shadow: inset 0 0 0 1px var(--glow); }
.fstats span { display: block; font: 500 11px/1.3 var(--font-data); letter-spacing: .12em; text-transform: uppercase; color: var(--mist); }
.fstats b { display: block; font: 700 22px/1.2 var(--font-display); font-variant-numeric: tabular-nums; margin-top: 6px; color: var(--ink); }
.fstats .fmain b { font-size: 30px; color: var(--glow); }
.fstats small { display: block; font-size: 12.5px; color: var(--mist); margin-top: 4px; }
.fnote { margin: 12px 0 0; font-size: 14px; line-height: 1.5; color: #c9d3e6; }
.fnote b { color: var(--ink); font-variant-numeric: tabular-nums; }
.fnote a, .fin .credit-line a { color: var(--ink); text-underline-offset: 3px; }
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
  // amounts are typed as 185000 or 185.000 (thousands with dots, decimals with a comma) and shown grouped after editing
  const num = id => Math.max(0, parseFloat($(id).value.replace(/[\s.€]/g, '').replace(',', '.')) || 0);
  const group = n => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  const NUMS = ['cp', 'ca', 'plot', 'pa', 'lf', 'lk'];
  const fmt = id => { const n = num(id); if (n && Number.isInteger(n)) $(id).value = group(n); };
  const FIELDS = ['h', 'cp', 'ca', 'cf', 'cs', 'plot', 'kp', 'pa', 'kw', 'san', 'pd', 'zem', 'zu', 'snes', 'tier', 'lf', 'lk', 'it', 'ir', 'lt'];
  const F = D.fin, pc = v => String(Math.round(v * 100) / 100).replace('.', ',') + ' %';
  const rate = () => Math.max(0, parseFloat($('ir').value.replace(',', '.')) || 0);
  // the loan follows the total until it is typed in; an empty field goes back to the total
  let lkSet = false;
  const CUSTOM = ['cp', 'ca', 'cf', 'cs'];
  const COLORS = ['#ffc477', '#ff9d4d', '#9fe0b5', '#8fb8ff', '#c9a7ff', '#ff9d8a', '#e8d98a', '#93a3c0'];
  const val = id => $(id).type === 'checkbox' ? ($(id).checked ? '1' : '0') : NUMS.includes(id) ? String(num(id) || '') : id === 'ir' ? String(rate()) : $(id).value;
  const skip = id => (id === 'tier' && !$('snes').checked) || (['plot', 'lf'].includes(id) && !num(id)) || (id === 'lk' && !lkSet);

  // anuiteta: P·r / (1 − (1 + r)^−n), r the monthly rate, n the number of months
  const annuity = (P, pct, years) => { const r = pct / 1200, n = years * 12; return r ? P * r / (1 - Math.pow(1 + r, -n)) : P / n; };
  function finance(total, value, h) {
    if (!lkSet) $('lk').value = total == null ? '' : group(Math.max(0, total - num('lf')));
    const P = num('lk'), pct = rate(), years = +$('lt').value;
    if (!P) { $('fout').innerHTML = '<p class="fnote">Vpišite znesek kredita.</p>'; return; }
    const A = annuity(P, pct, years), paid = A * years * 12;
    // DSTI: the instalment is at most this share of net income, and the minimum creditworthiness must remain after it
    const need = Math.ceil(Math.max(A / (F.dsti / 100), A + F.minCs) / 10) * 10;
    const ltv = value ? Math.round(P / value * 1000) / 10 : 0, plot = num('plot');  // one decimal, shown and compared as is
    const e = F.eko, eA = annuity(Math.min(P, e.max), e.rate, e.years);
    $('fout').innerHTML = `<div class="fstats"><div class="fmain"><span>Mesečni obrok</span><b>${eur(A)}</b><small>${eur(P)} · ${pc(pct)} · ${years} let</small></div>
      <div><span>Skupaj obresti</span><b>${eur(paid - P)}</b></div><div><span>Skupaj vrnete</span><b>${eur(paid)}</b></div></div>
      <p class="fnote">Za ta obrok potrebujete neto dohodek gospodinjstva vsaj <b>~${eur(need)}/mesec</b>: obroki vseh kreditov smejo biti največ ${F.dsti} % neto dohodka,
        po plačilu pa vam mora ostati vsaj ${eur(F.minCs)} (več z vzdrževanimi družinskimi člani). Drugi krediti potrebni dohodek povečajo.</p>
      ${value ? `<p class="fnote">Kredit je <b>${String(ltv).replace('.', ',')} %</b> vrednosti nepremičnine (ocena: celotna naložba ${plot ? 'z zemljiščem' : 'brez zemljišča, ki ga niste vpisali'}, ${eur(value)}).
        ${ltv > F.ltv ? `To je več od ${F.ltv} %, kolikor Banka Slovenije priporoča za dom, v katerem boste živeli; banka lahko zahteva več lastnih sredstev ali dodatno zavarovanje.` : `Banka Slovenije priporoča največ ${F.ltv} % za dom, v katerem boste živeli.`}</p>` : ''}
      <p class="fnote">${$('snes').checked ? 'Ker gradite hišo sNES+, lahko' : 'Če gradite skoraj ničenergijsko hišo sNES+, lahko'} del zneska dobite kot kredit Eko sklada:
        ${pc(e.rate)} fiksno, do ${eur(e.max)} in do ${e.years} let${$('snes').checked ? ` (za ${eur(Math.min(P, e.max))} približno ${eur(eA)} na mesec)` : ''}. <a href="${esc(e.url)}" target="_blank" rel="noopener">Javni poziv Eko sklada</a></p>`;
  }

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
    if (k.co) {
      // the odlok formula, as in data/stroski.json: KP = Σ (plot × Cpo × Dpo + BTP × Cto × Dto × Fn) × psz, BTP = 1,2 × net m²; one total per Fn and road zone
      const co = k.co, pa = num('pa') || 600, btp = h.area * 1.2, zones = co.road_zones && co.road_zones.length ? co.road_zones : [null];
      const tot = co.fn.flatMap(fn => zones.map(z => (z ? [z] : []).concat(co.items).reduce((a, it) => a + (pa * it.cpo * co.dpo + btp * it.cto * co.dto * fn) * it.psz, 0)));
      out.push({ label: 'Komunalni prispevek', lo: Math.min(...tot), hi: Math.max(...tot), conf: k.conf, src: k.src,
        tag: k.conf === 'high' ? 'izračun po odloku' : 'po odloku, ' + TAG[k.conf],
        note: `${k.name}: izračun po odloku za parcelo ${group(pa)} m² in ${Math.round(btp)} m² BTP (1,2 × neto)` + (tot.length > 1 ? (co.road_zones ? ', razpon po conah cest' : ', razpon po faktorju namembnosti') : '') });
    } else out.push({ label: 'Komunalni prispevek', lo: k.lo, hi: k.hi, conf: k.conf, src: k.src, tag: 'ocena za primer, ' + TAG[k.conf],
      note: `${k.name}: ${k.note}; ni prilagojeno vaši hiši in parceli` });
    // projekt_paket already covers PID, so pid_dokument is added only when the documentation comes with the house;
    // the geodetic plan and soil report are the investor's either way, as inputs for the maker's DGD
    const pd = $('pd').checked, snes = $('snes').checked;
    const docs = sum('Projektna dokumentacija in nadzor', (pd ? ['pid_dokument'] : ['projekt_paket', 'mnenja_soglasja'])
      .concat(['geodetski_nacrt', 'geolosko_porocilo', 'gradbeni_nadzor', 'kataster_stavb', 'zakolicba', 'varnostni_nacrt', 'energetska_izkaznica'], snes ? ['phpp'] : []),
      (pd ? 'DGD in PZI v ceni hiše; PID' : 'IDZ, DGD, PZI, PID, mnenja') +
      ', geodetski načrt, geološko poročilo, gradbeni nadzor, kataster stavb, zakoličba, varnostni načrt, energetska izkaznica' + (snes ? ', PHPP' : '') + ', upravna taksa');
    const t = I.upravna_taksa_gd, tax = t.value.base + t.value.rate * Math.max(0, h.price - t.value.above) + t.value.application;
    docs.lo += tax; docs.hi += tax; docs.src = docs.src.concat(t.source_ids);
    out.push(docs);
    const mkcn = $('san').value === 'mkcn', el = 'prikljucek_elektrika_' + $('kw').value + 'kw';
    out.push(sum('Priključki', [el, 'prikljucek_elektrika_izvedba', 'prikljucek_voda', mkcn ? 'mkcn' : 'prikljucek_kanalizacija', 'prikljucek_telekom'],
      `elektrika ${$('kw').value} kW (omrežnina ${eur(rng(el)[0])} in izvedba), voda, ` + (mkcn ? 'MKČN z vgradnjo' : 'kanalizacija') + ', telekomunikacije'));
    const z = $('zem').value, ze = I.zemeljska_dela;
    out.push({ ...sum('Zemeljska dela', ['zemeljska_dela']), ...(z === 'l' ? { lo: ze.easy.min, hi: ze.easy.max, note: 'lahek teren' }
      : z === 't' ? { lo: ze.hard.min, hi: ze.hard.max, note: 'zahteven teren, skala: ' + eur(ze.hard.min) + ' ali več' } : { note: 'od lahkega do zahtevnega terena' }) });
    if ($('zu').checked) out.push(sum('Zunanja ureditev', ['zunanja_ureditev'], 'dovoz, tlakovanje, terasa, ograja, zelenica, ponikovalnica'));
    if ($('snes').checked) {
      const e = I.eko_sklad_snes, rate = D.tiers[+$('tier').value].rate;
      // the call caps the grant at 30 % of eligible costs, and eligible costs at 50 % of a turnkey contract: 15 % of the price
      const byArea = rate * Math.min(h.area, e.max_area_m2), cap = Math.min(e.max_eur, 0.3 * 0.5 * h.price), s = h.sub ? 0 : Math.min(byArea, cap);
      out.push({ ...sum('Subvencija Eko sklada', ['eko_sklad_snes']), lo: -s, hi: -s, note: h.sub ? 'cena te hiše že upošteva subvencijo, zato je ne odštejemo še enkrat'
        : `${rate} €/m² × ${Math.round(Math.min(h.area, e.max_area_m2))} m²` + (cap < byArea ? `, omejeno na ${cap === e.max_eur ? 'najvišji znesek' : '15 % cene hiše'}` : '') });
      // no sourced figure for the upgrade, so it is named, not priced
      out.push({ label: 'Nadgradnja na sNES+', lo: 0, hi: 0, txt: 'ni vključena', tag: 'ni v izračunu',
        note: 'Nadgradnja na standard sNES+ (PHPP, rekuperacija, sončna elektrarna …) ni vključena – zahtevajte ponudbo.' });
    }
    return out;
  }

  function render() {
    const custom = $('h').value === 'lastna';
    $('custom').hidden = !custom;
    $('tierbox').hidden = !$('snes').checked;
    const p = new URLSearchParams();
    for (const id of FIELDS) if ((custom || !CUSTOM.includes(id)) && !skip(id)) p.set(id, val(id));
    history.replaceState(null, '', '#' + p.toString());
    const h = custom ? { price: num('cp'), area: num('ca'), floors: +$('cf').value, slab: !$('cs').checked, sub: false, name: 'Lastna ponudba' } : houses[$('h').value];
    if (!h.price || !h.area) {
      $('total').innerHTML = '<span class="eyebrow">Skupaj</span><b>—</b><p>Vpišite ceno in neto površino hiše.</p>';
      $('lines').innerHTML = '';
      $('stotal').innerHTML = '<span>Vpišite ceno in površino hiše</span>';
      finance(null, 0, h);
      return;
    }
    const ls = lines(h), lo = ls.reduce((a, l) => a + l.lo, 0), hi = ls.reduce((a, l) => a + l.hi, 0);
    const mids = ls.map(l => (l.lo + l.hi) / 2), mid = mids.reduce((a, b) => a + b, 0);
    const costs = mids.reduce((a, v) => a + Math.max(0, v), 0), pctOf = v => costs > 0 ? v / costs * 100 : 0;
    const color = [], parts = [];
    ls.forEach((l, i) => { if (mids[i] > 0) { color[i] = COLORS[parts.length % COLORS.length]; parts.push(i); } });
    const exact = Math.round(lo) === Math.round(hi), sub = ls.find(l => l.lo < 0);
    $('total').innerHTML = `<span class="eyebrow">Skupaj</span><b>${exact ? 'približno ' + eur(lo) : 'od ' + eur(lo) + ' do ' + eur(hi)}</b>
      ${exact ? '' : `<p class="likely">Najverjetneje okoli <strong>${eur(Math.round(mid / 100) * 100)}</strong> (sredina razpona vsake postavke)</p>`}
      <p>${esc(h.name)}, ${Math.round(h.area)} m² neto · na m² od ${eur(lo / h.area)} do ${eur(hi / h.area)}</p>
      <div class="stack" role="img" aria-label="Kam gre denar: ${parts.map(i => `${ls[i].label} ${Math.round(pctOf(mids[i]))} %`).join(', ')}">${parts.map(i =>
        `<i style="width:${pctOf(mids[i]).toFixed(2)}%;background:${color[i]}"></i>`).join('')}</div>
      <ul class="legend" aria-hidden="true">${parts.map(i => `<li><i style="background:${color[i]}"></i>${ls[i].label} <span>${Math.round(pctOf(mids[i]))} %</span></li>`).join('')}${sub
        ? `<li><i class="neg"></i>${sub.label} <span>${eur(sub.lo)}</span></li>` : ''}</ul>`;
    $('stotal').innerHTML = `<span><small>Skupaj</small> ${exact ? eur(lo) : eur(lo) + ' – ' + eur(hi)}</span><span class="go">Razčlenitev ↓</span>`;
    $('lines').innerHTML = `<table class="tbl lines"><thead><tr><th scope="col">Postavka</th><th scope="col" style="text-align:right">Znesek</th></tr></thead><tbody>${ls.map((l, i) => {
      const name = l.house && l.house.slug ? `<a href="../${l.house.slug}/">${esc(l.house.name)}</a><button type="button" class="cmp sm" data-slug="${l.house.slug}" data-name="${esc(l.house.name)}" aria-label="Dodaj ${esc(l.house.name)} v primerjavo">+ Primerjaj</button>` : '';
      const src = (l.src || []).map(s => `<a href="#vir-${s}">[${D.srcNum[s]}]</a>`).join('');
      const pct = Math.min(100, pctOf(Math.abs(mids[i])));
      return `<tr><th scope="row">${l.label}${name ? '<small>' + name + '</small>' : ''}${l.note ? `<small>${esc(l.note)}</small>` : ''}${src ? `<small class="src">Viri: ${src}</small>` : ''}
        ${mids[i] ? `<span class="share" title="${Math.round(pct)} % stroškov"><i class="${mids[i] < 0 ? 'neg' : ''}" style="width:${pct.toFixed(1)}%${color[i] ? ';background:' + color[i] : ''}"></i></span>` : ''}</th>
        <td class="n">${l.txt || span(l.lo, l.hi)}<small>${l.tag || TAG[l.conf]}</small></td></tr>`;
    }).join('')}</tbody></table>`;
    // a bank values a finished house at roughly the whole investment, so LTV is measured against the total (plot included)
    const tot = exact ? lo : Math.round(mid / 100) * 100;
    finance(tot, tot, h);
    window.HVCompare.refresh();
  }

  // Lumar and Jelovica include DGD and PZI in the price: tick the box for their houses unless the link says otherwise
  const docsIn = () => { const h = houses[$('h').value]; return !!(h && h.docs); };
  // the form from the link; again on hashchange (a link or Back/Forward), from the defaults, without a reload
  function load() {
    const q = new URLSearchParams(location.hash.slice(1));
    $('calc').reset();
    $('fin').reset();
    lkSet = q.has('lk');
    for (const id of FIELDS) {
      if (!q.has(id)) continue;
      const el = $(id), before = el.value;
      if (el.type === 'checkbox') el.checked = q.get(id) === '1';
      else { el.value = q.get(id); if (el.tagName === 'SELECT' && !el.value) el.value = before; }
    }
    if (!q.has('pd')) $('pd').checked = docsIn();
    if (q.has('ir')) $('ir').value = $('ir').value.replace('.', ',');
    else $('ir').value = String($('it').value === 'v' ? F.var : F.fix).replace('.', ',');
    NUMS.forEach(fmt);
  }
  load();
  NUMS.forEach(id => $(id).addEventListener('blur', () => fmt(id)));
  // only links that carry calculator state; #lines and the source links [n] just scroll
  window.addEventListener('hashchange', () => { if (location.hash.includes('=')) { load(); render(); } });
  // mobile: a bar with the total while the form is on screen, gone once the result itself is in view
  if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => { $('stotal').hidden = e.isIntersecting; }).observe($('res'));
  $('h').addEventListener('change', () => { $('pd').checked = docsIn(); });
  $('lk').addEventListener('input', () => { lkSet = $('lk').value.trim() !== ''; });
  $('it').addEventListener('change', () => { $('ir').value = String($('it').value === 'v' ? F.var : F.fix).replace('.', ','); });
  for (const f of ['calc', 'fin']) { $(f).addEventListener('input', render); $(f).addEventListener('change', render); }
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


SNES_GROUP = {'I': 'naravna izolacija in lesena okna', 'II': 'mineralna izolacija', 'III': 'sintetična izolacija'}
CONF = {'high': 'uradni podatek', 'medium': 'okvirno', 'low': 'zelo okvirno'}
LOWER = {'high': 'medium', 'medium': 'low', 'low': 'low'}


def snes_tiers(snes):
    """Eko sklad rates (group, rate at QH <= 10, rate at QH <= 15 kWh/m2a), read from the item's text."""
    t = [(g, int(a), int(b)) for a, b, g in re.findall(r'(\d+)/(\d+)(?: EUR/m2)? group (I+)\b', snes['applies'])]
    assert len(t) == 3 and min(x[2] for x in t) == snes['value']['min'] and max(x[1] for x in t) == snes['value']['max'], t
    return t


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

    conf = CONF
    # Financing: rates as the banks publish them (data/financiranje.json), the calculator default is the middle of the typical range
    lim, eko, typ, avg, eurib = FIN['limits'], FIN['eko_sklad'], FIN['typical'], FIN['average_rate'], FIN['euribor_6m']
    banks = [b for b in FIN['banks'] if b.get('fixed') or b.get('variable_margin')]
    fin_used = {s for b in FIN['banks'] for s in b['source_ids']} | {s for x in (lim, eko, avg, eurib) for s in x['source_ids']}
    assert fin_used <= set(src_num), fin_used - set(src_num)
    max_term = lim['max_maturity_years'] or max(b['max_term_years'] for b in FIN['banks'])  # Banka Slovenije sets none, so the banks' longest
    terms = [y for y in typ['terms_years'] if y <= max_term]
    rate_txt = lambda v: f'{v:.2f}'.replace('.', ',') + ' %'
    rr = lambda r: rate_txt(r['min']) if r['min'] == r['max'] else rate_txt(r['min'])[:-2] + '–' + rate_txt(r['max'])
    fin_def = {k: round((typ[k]['min'] + typ[k]['max']) / 2, 1) for k in ('fixed', 'variable')}
    fin_data = {'fix': fin_def['fixed'], 'var': fin_def['variable'], 'dsti': lim['dsti_max'], 'minCs': lim['min_creditworthiness_eur'], 'ltv': lim['ltv_recommended'],
                'eko': {'rate': eko['rate_fixed'], 'max': eko['max_eur'], 'years': eko['max_term_years'], 'url': eko['url']}}
    bank_rows = ''.join(
        f'<tr><th scope="row">{esc(b["bank"])}<small>cenik {ddate(b["valid_from"])}</small></th>'
        f'<td class="n">{rr(b["fixed"]) if b.get("fixed") else "—"}<small>{esc(b.get("fixed_term", ""))}</small></td>'
        f'<td class="n">{esc(b["variable_ref"])} + {rr(b["variable_margin"])}</td><td class="n">{b["max_term_years"]} let</td>'
        f'<td>{esc(b["conditions"])} {cite(*b["source_ids"])}</td></tr>' for b in banks)
    no_rates = [b for b in FIN['banks'] if b not in banks]
    fin_cite = cite(*[s for b in banks for s in b['source_ids']], *lim['source_ids'])
    nat_min, nat_max = re.search(r'min ([^,]+), max ([^,]+)', nat['basis']).groups()
    covered, of = re.search(r'(\d+) of (\d+) municipalities', nat['basis']).groups()

    # Komunalni prispevek: our odlok calculation (600 m² plot, 180 m² BTP) where we have it, else vsevem.si's figure (600 m², 200 m² BTP).
    kps, kp_rows = [], []
    for m in kp['municipalities']:
        c = m.get('calc_600_180')
        lo, hi = m['amount']['min'], m['amount']['max']
        co = m.get('coefficients')
        # N-2: with odlok coefficients the calculator computes KP for the chosen house and plot; else the vsevem.si example, one confidence step lower
        kps.append({'id': slugify(m['obcina']), 'name': m['obcina'], 'lo': lo, 'hi': hi, 'conf': m['confidence'] if co else LOWER[m['confidence']], 'src': m['source_ids'],
                    'co': co and {k: co[k] for k in ('dpo', 'dto', 'fn', 'items', 'road_zones') if k in co},
                    'note': 'ocena za primer: parcela 600 m², 200 m² BTP (izračun vsevem.si)'})
        assert co or not c, m['obcina']  # every odlok figure comes with the coefficients that reproduce it (kp_calc asserts that)
        clo, chi = (c['min'], c['max']) if isinstance(c, dict) else (c, c)
        calc_txt = (eur(clo) if clo == chi else eur(clo) + ' – ' + eur(chi)) if c else '—'
        kp_rows.append(f'<tr><th scope="row"><a href="../{KP}/{slugify(m["obcina"])}/">{esc(m["obcina"])}</a></th><td class="n">{calc_txt}</td><td class="n">{eur(m["vsevem_600_200"])}</td>'
                       f'<td>{conf[m["confidence"]]} {cite(*m["source_ids"])}</td></tr>')
    ni = {'min': nat['typical'], 'max': nat['typical']}
    kps.append({'id': 'druga', 'name': 'Druga občina (slovensko povprečje)', 'lo': ni['min'], 'hi': ni['max'], 'conf': LOWER[nat['confidence']], 'src': nat['source_ids'], 'co': None,
                'note': f'ocena za primer: povprečje {covered} občin za parcelo 600 m² in 200 m² BTP; razpon od {eur(nat["min"])} ({nat_min}) do {eur(nat["max"])} ({nat_max})'})
    kp_opts = ''.join(f'<option value="{k["id"]}"{" selected" if k["id"] == "druga" else ""}>{esc(k["name"])} · '
                      + ('izračun po odloku za vašo hišo' if k['co'] else 'ocena ' + (eur(k["lo"]) if k["lo"] == k["hi"] else eur(k["lo"]) + " – " + eur(k["hi"])) + ' za primer') + '</option>'
                      for k in sorted(kps[:-1], key=lambda k: k['name']) + kps[-1:])
    by_odlok = and_join([k['name'] for k in kps if k['co']])

    snes = items['eko_sklad_snes']
    tiers = [{'rate': t[q], 'label': f'Skupina {t[0]} ({SNES_GROUP[t[0]]}), QH ≤ {10 if q == 1 else 15} kWh/m²a: {t[q]} €/m²'} for q in (1, 2) for t in snes_tiers(snes)]
    low_tier = min(range(len(tiers)), key=lambda i: tiers[i]['rate'])  # the most cautious rate by default
    tier_opts = ''.join(f'<option value="{i}"{" selected" if i == low_tier else ""}>{esc(t["label"])}</option>' for i, t in enumerate(tiers))

    def stage_has(m, *keys):
        return any(k in m['price_stage'].lower() for k in keys)

    priced = [(p, m) for p, m in models if m['price_eur'] and m['area_m2']]
    houses = [{'slug': m['slug'], 'name': f"{p['name']} {m['name']}", 'price': m['price_eur'], 'area': m['area_m2'], 'floors': m['floors'],
               'stage': m['price_stage'], 'slab': stage_has(m, 'brez temeljne plošče'), 'sub': stage_has(m, 'subvencij'),
               'docs': p['id'] in cost['docs_included']['makers']} for p, m in priced]
    plain = sorted((h for h in houses if not h['sub']), key=lambda h: h['price'])
    default = plain[len(plain) // 2]['slug']  # a mid-priced house whose price is not already cut by a subsidy
    house_opts = ''.join(f'<optgroup label="{esc(p["name"])}">' + ''.join(
        f'<option value="{m["slug"]}"{" selected" if m["slug"] == default else ""}>{esc(m["name"])} · {eur(m["price_eur"])}{" · " + price_tag(m) if price_tag(m) else ""}</option>'
        for m in sorted((m for m in p['models'] if m['price_eur'] and m['area_m2']), key=lambda m: (m['area_m2'], m['name']))) + '</optgroup>' for p in data['providers'] if any(m['price_eur'] and m['area_m2'] for m in p['models'])) + \
        '<option value="lastna">Lastna ponudba</option>'

    calc_json = json.dumps({'houses': houses, 'items': items, 'kp': kps, 'tiers': tiers, 'srcNum': src_num, 'fin': fin_data}, ensure_ascii=False).replace('</', '<\\/')

    makers_by = lambda *keys: [p['name'] for p in data['providers'] if any(stage_has(m, *keys) for m in p['models'] if m['price_eur'])]
    no_slab, subsidized = makers_by('brez temeljne plošče'), makers_by('subvencij')
    no_slab_n = sum(1 for h in houses if h['slab'])
    verb = lambda names, one, two, many: one if len(names) == 1 else two if len(names) == 2 else many
    eles = items['prikljucek_elektrika_per_kw']['value']
    eles_txt = f'{eles:.2f}'.replace('.', ',')
    el = lambda kw: eur(round(items[f'prikljucek_elektrika_{kw}kw']['value']))
    ze = items['zemeljska_dela']
    tx = items['upravna_taksa_gd']['value']
    comma = lambda v: f'{v:.2f}'.replace('.', ',')
    tax_250 = eur(round(tx['base'] + tx['rate'] * (250000 - tx['above']) + tx['application']))
    docs_makers = [p['name'] for p in data['providers'] if p['id'] in cost['docs_included']['makers']]
    pr = items['prikljucki_skupaj']
    ddv = items['ddv_stopnja']['value']
    pct = lambda r: f'{r * 100:g}'.replace('.', ',') + ' %'
    slab_lo, slab_hi = rng('temeljna_plosca_m2')
    t_rates = sorted({t['rate'] for t in tiers}, reverse=True)

    desc = (f'Kalkulator stroškov gradnje montažne hiše: komunalni prispevek povprečno {eur(ni["min"])}, '
            f'projektna dokumentacija {span("projekt_paket")}, priključki {span("prikljucki_skupaj")}, temeljna plošča {slab_lo}–{slab_hi} €/m² in subvencija Eko sklada do {eur(snes["max_eur"])}.')
    h1 = 'Koliko stane gradnja montažne hiše?'
    ld = {'@context': 'https://schema.org', '@type': 'Article', 'headline': h1, 'description': desc, 'inLanguage': 'sl', 'url': url,
          'dateModified': cost['as_of'], 'image': SITE + 'img/og/stroski.jpg', 'author': {'@type': 'Organization', 'name': 'Hišni vodič', 'url': SITE}}
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
    Pri vsaki postavki je naveden vir in kako zanesljiva je številka. Na koncu izračuna še mesečni obrok stanovanjskega kredita in dohodek, ki ga zanj potrebujete.</p></div>
  <div class="calc">
    <form class="form" id="calc" onsubmit="return false">
      <label>Hiša<select id="h">{house_opts}</select></label>
      <div class="sub" id="custom" hidden>
        <label>Cena hiše (€)<input type="text" id="cp" inputmode="numeric" autocomplete="off" placeholder="npr. 185.000"></label>
        <label>Neto površina (m²)<input type="text" id="ca" inputmode="numeric" autocomplete="off" placeholder="npr. 120"></label>
        <label>Etaže<select id="cf"><option value="1">pritličje</option><option value="1.5">z mansardo</option><option value="2">pritličje in nadstropje</option></select></label>
        <label class="ck"><input type="checkbox" id="cs"> Temeljna plošča je vključena v ceno</label>
      </div>
      <label>Zemljišče (€)<input type="text" id="plot" inputmode="numeric" autocomplete="off" placeholder="0"><small>Neobvezno; pustite prazno, če parcelo že imate.</small></label>
      <label>Občina (komunalni prispevek)<select id="kp">{kp_opts}</select>
        <small>Za {by_odlok} prispevek izračunamo po formuli iz odloka za izbrano hišo (BTP ≈ 1,2 × neto površina) in vašo parcelo. Za druge občine je znesek ocena
          za primer s parcelo 600 m² in 200 m² BTP, ki se z velikostjo hiše ne spreminja. Dejanska odmera je odvisna še od cone, priključkov in olajšav.</small></label>
      <label>Velikost parcele (m²)<input type="text" id="pa" inputmode="numeric" autocomplete="off" value="600"><small>Vpliva na komunalni prispevek v občinah z izračunom po odloku.</small></label>
      <label>Priključna moč elektrike<select id="kw"><option value="11">11 kW (3 × 16 A)</option><option value="17" selected>17 kW (3 × 25 A), s toplotno črpalko</option><option value="22">22 kW (3 × 32 A)</option></select></label>
      <label>Odpadne vode<select id="san"><option value="kan">Javna kanalizacija (priključek)</option><option value="mkcn">Mala čistilna naprava (MKČN)</option></select>
        <small>Pri MKČN je upoštevana vgrajena naprava: naprava, izkop, vgradnja in ponikovalnica.</small></label>
      <label class="ck"><input type="checkbox" id="pd"> Projektna dokumentacija je že vključena v ceno hiše</label>
      <small>{and_join(docs_makers)} {verb(docs_makers, 'navaja', 'navajata', 'navajajo')}, da sta projekta DGD in PZI vključena v ceno, zato je pri {verb(docs_makers, 'njegovih', 'njunih', 'njihovih')} hišah polje že označeno {cite(*cost['docs_included']['source_ids'])}. Spremenite ga, če vaša ponudba pravi drugače.</small>
      <label>Zemeljska dela<select id="zem"><option value="l">Lahek teren</option><option value="n" selected>Ne vem</option><option value="t">Zahteven teren (skala)</option></select></label>
      <label class="ck"><input type="checkbox" id="zu" checked> Zunanja ureditev (dovoz, tlakovanje, ograja, zelenica)</label>
      <label class="ck"><input type="checkbox" id="snes"> <span>Hiša že izpolnjuje pogoje sNES+ (skoraj ničenergijska hiša), odštej subvencijo Eko sklada</span></label>
      <div class="sub" id="tierbox" hidden>
        <label>Izolacija in potreba po toploti<select id="tier">{tier_opts}</select></label>
        <small>Hiša mora biti skoraj pasivna: izračun PHPP, potreba po toploti in hladu največ 15 kWh/m²a, zrakotesnost n50 ≤ 0,6, rekuperacija z izkoristkom vsaj 80 %,
          zbiralnik deževnice vsaj 6 m³ in sončna elektrarna. Mnoge tipske hiše teh pogojev brez nadgradenj ne izpolnjujejo. Označite le, če proizvajalec potrdi, da hiša pogoje že izpolnjuje:
          cene nadgradnje nimamo, zato je kalkulator ne prišteje. Privzeta je najnižja stopnja subvencije.</small>
      </div>
    </form>
    <div class="res" id="res">
      <div class="total" id="total" aria-live="polite"></div>
      <div class="scroll" id="lines"></div>
      <p class="credit-line">Večina tržnih cen ne navaja, ali vključujejo DDV. Za hišo z uporabno površino do 250 m² velja {pct(ddv['reduced'])} DDV, če gradnjo izvajalec obračuna neposredno investitorju kot gradbeno storitev, sicer {pct(ddv['general'])}.</p>
      <section class="fin" aria-labelledby="fin-h"><h2 id="fin-h">Koliko bo znašal obrok kredita?</h2>
        <form class="form" id="fin" onsubmit="return false">
          <label>Lastna sredstva (€)<input type="text" id="lf" inputmode="numeric" autocomplete="off" placeholder="0"></label>
          <label>Znesek kredita (€)<input type="text" id="lk" inputmode="numeric" autocomplete="off"><small>Najverjetnejši skupni znesek, zmanjšan za lastna sredstva. Lahko ga spremenite; izbrišite ga za samodejni izračun.</small></label>
          <label>Vrsta obrestne mere<select id="it"><option value="f">fiksna</option><option value="v">spremenljiva</option></select></label>
          <label>Obrestna mera (%)<input type="text" id="ir" inputmode="decimal" autocomplete="off" value="{f'{fin_def["fixed"]:g}'.replace('.', ',')}">
            <small>Privzeto sredina običajnega razpona: fiksna {rr(typ['fixed'])}, spremenljiva {rr(typ['variable'])} (6M EURIBOR {rate_txt(eurib['value'])} in pribitek {rr(typ['variable_margin'])}).</small></label>
          <label>Doba odplačila<select id="lt">{''.join(f'<option value="{y}"{" selected" if y == 25 else ""}>{y} let</option>' for y in terms)}</select></label>
        </form>
        <div id="fout" aria-live="polite"></div>
        <p class="credit-line">Informativni izračun, ne ponudba banke. Obrok je anuiteta z enako obrestno mero vso dobo; stroški odobritve, vodenja in zavarovanja niso všteti.
          Obrestne mere so iz objavljenih pogojev bank na dan {ddate(FIN['as_of'])}, pravila za DSTI in LTV od Banke Slovenije {fin_cite}. <a href="#kredit">Obrestne mere po bankah</a></p>
      </section>
      <div class="tools"><button type="button" class="btn line" id="copy">Kopiraj povezavo</button></div>
    </div>
  </div>
  <a class="stotal" id="stotal" href="#lines" data-sticky-bottom hidden></a>
  <section class="prose"><h2>Komunalni prispevek po občinah</h2>
    <p>Komunalni prispevek plačate občini pred izdajo gradbenega dovoljenja. Izračuna se iz površine parcele in bruto tlorisne površine hiše (BTP) ter cen komunalne opreme
      (ceste, vodovod, kanalizacija, javne površine) iz občinskega odloka: KP = Σ (A<sub>parcela</sub> × Cpo × Dpo + A<sub>BTP</sub> × Cto × Dto × Fn) × psz {cite(*kp['source_ids'][:3])}.
      Po izračunu vsevem.si za {covered} od {of} občin (parcela 600 m², 200 m² BTP) je povprečje {eur(nat['typical'])}, najmanj {eur(nat['min'])} ({nat_min}), največ {eur(nat['max'])} ({nat_max}) {cite(*nat['source_ids'])}.
      Odmera se računa s cenami iz veljavnega odloka. Preverjeni odloki (Ljubljana, Koper, Celje, Kranj, Novo mesto, Ptuj) nimajo določbe o indeksaciji, prav tako je nimata zakon ZUreP-3 in nova uredba (Ur. l. RS 53/26, velja od 28. 3. 2026),
      ki za tipično novo hišo pravil odmere ne spreminja {cite('kp-uredba-53-26')}. Za {by_odlok} kalkulator prispevek preračuna za izbrano hišo in vašo parcelo po formuli iz odloka (zneski v prvem stolpcu veljajo za primer 600 m² in 180 m² BTP); za druge občine uporabi izračun vsevem.si za 200 m² BTP, za ostale povprečje {eur(ni['min'])}, ne glede na velikost hiše.
      <a href="../{KP}/">Komunalni prispevek po občinah: formula, izračun in viri</a>.</p>
    <div class="scroll"><table class="tbl">{thead('Občina', 'Po odloku (600 m², 180 m² BTP)', 'Vsevem.si (600 m², 200 m² BTP)', 'Zanesljivost')}<tbody>{''.join(kp_rows)}</tbody></table></div>
    <p class="basis">Zneska se razlikujeta, ker vsevem.si računa za 200 m² BTP in z vso komunalno opremo (mi za 180 m² in brez plinovoda in vročevoda).
      {' '.join(f'{esc(m["obcina"])}: {kp_gap(m)}' for m in KPD['municipalities'] if m.get('vsevem_basis') and kp_gap(m))}</p>
  </section>
  <section class="prose"><h2>Koliko stane projektna dokumentacija za hišo?</h2>
    <p>Za gradbeno dovoljenje potrebujete projekt DGD ({span('projekt_dgd')}) {cite(*items['projekt_dgd']['source_ids'])}, za gradnjo še projekt za izvedbo PZI ({span('projekt_pzi')}),
      pred tem idejno zasnovo ({span('projekt_izp')}) {cite(*items['projekt_izp']['source_ids'])}. Celotna dokumentacija (IDZ, DGD, PZI, PID) stane {span('projekt_paket')} {cite(*items['projekt_paket']['source_ids'])}.
      {and_join(docs_makers)} {verb(docs_makers, 'navaja', 'navajata', 'navajajo')}, da sta DGD in PZI vključena v ceno hiše; Jelovica ju ovrednoti na do 15.000 € {cite(*cost['docs_included']['source_ids'])}.
      Projekt izvedenih del (PID) stane okoli petino DGD, {span('pid_dokument')} {cite('marh-cenik')}.</p>
    <p>Posebej plačate geodetski načrt ({span('geodetski_nacrt')}) {cite(*items['geodetski_nacrt']['source_ids'])}, geološko-geomehansko poročilo s sondažnim izkopom ({span('geolosko_porocilo')}, na zahtevnem terenu lahko precej več) {cite('mm-geomeh')},
      mnenja in soglasja ({span('mnenja_soglasja')}), zakoličbo ({span('zakolicba')}) {cite(*items['zakolicba']['source_ids'])}, varnostni načrt ({span('varnostni_nacrt')}; koordinator za hišo pod 350 m² običajno ni potreben) {cite('projvarnost-vn')},
      obvezni gradbeni nadzor ({span('gradbeni_nadzor')}, običajno 1,5–3 % vrednosti gradnje) {cite(*items['gradbeni_nadzor']['source_ids'])}, energetsko izkaznico ({span('energetska_izkaznica')}) {cite('mm-ei')}
      in elaborat za vpis v kataster stavb ({span('kataster_stavb')}) {cite(*items['kataster_stavb']['source_ids'])}.</p>
    <p>Upravna taksa za gradbeno dovoljenje je {comma(tx['base'])} € in {comma(tx['rate'] * 100)} % vrednosti objekta nad {eur(tx['above'])} ter {comma(tx['application'])} € za vlogo, za hišo za 250.000 € okoli {tax_250} {cite('netteblog-gd')};
      takse za vlogo ni, če jo oddate elektronsko. Mlade družine, ki rešujejo stanovanjski problem (vsaj en otrok, noben od staršev ni starejši od 30 let oziroma 35 let, dokler otrok ni šoloobvezen), so takse oproščene {cite('zut-tarifa')}. Za subvencijo Eko sklada potrebujete še izračun PHPP ({span('phpp')}) {cite('arhim-phpp')}.</p>
  </section>
  <section class="prose"><h2>Koliko stanejo priključki za hišo?</h2>
    <p>Za nov priključek na elektro omrežje plačate omrežnino za priključno moč: {eles_txt} €/kW brez DDV pri nizki napetosti (cenik ELES 2026) {cite('el-eles-2026')}.
      Z DDV to znese {el(11)} za 11 kW, {el(17)} za 17 kW, kolikor običajno potrebuje hiša s toplotno črpalko, in {el(22)} za 22 kW.
      Izvedbo priključka (projekt in soglasje, priključno-merilna omarica, kabel, izkop) plača investitor; stane {span('prikljucek_elektrika_izvedba')}, običajno okoli {eur(items['prikljucek_elektrika_izvedba']['typical'])} {cite(*items['prikljucek_elektrika_izvedba']['source_ids'])}.</p>
    <p>Vodovodni priključek z jaškom, vodomerom, montažo, geodetskim posnetkom in izkopom stane {span('prikljucek_voda')} {cite(*items['prikljucek_voda']['source_ids'])}, kanalizacijski {sewer} {cite(*items['prikljucek_kanalizacija']['source_ids'])}.
      Kjer javne kanalizacije ni, potrebujete malo komunalno čistilno napravo: vgrajena stane {span('mkcn')}, od tega naprava okoli 5.700 €, izkop, vgradnja in ponikovalnica pa 2.000–4.000 € {cite(*items['mkcn']['source_ids'])}.
      Občinske subvencije (npr. Koper 40 %, največ 1.500 €) so večinoma namenjene obstoječim stavbam, zato jih kalkulator ne odšteje. Telekomunikacijski priključek stane okoli {span('prikljucek_telekom')}.
      Vsi priključki skupaj stanejo {span('prikljucki_skupaj')}, brez javne kanalizacije z MKČN {eur(pr['offgrid']['min'])} – {eur(pr['offgrid']['max'])}.</p>
  </section>
  <section class="prose"><h2>Koliko stane temeljna plošča?</h2>
    <p>Toplotno izolirana temeljna plošča, kakršno zahtevajo proizvajalci montažnih hiš (podložni beton, dva sloja XPS, hidroizolacija, armatura in beton), stane {slab_lo}–{slab_hi} € na m² bruto površine plošče {cite('tp-mojmojster-2026')}; to je seštevek cen posameznih del (plošča, XPS, hidroizolacija, podložni beton, instalacije pod ploščo).
      Za ploščo s 100 m² to pomeni {span('temeljna_plosca_primer')}. Okvirne cene na portalih so nižje, 125–200 € na m² {cite('tp-primerjam-2026')}, dejanske ponudbe pa so bližje zgornjemu delu razpona {cite('tp-slotech-2024')}. Izkop in tamponsko nasutje stanejo dodatno okoli {span('izkop_tampon_m2')} na m² {cite('tp-mojmojster-2026')}, zato sta v kalkulatorju pri zemeljskih delih.
      Nižje ocene okoli 100–150 € na m², ki jih najdete na spletu, veljajo za neizolirano armiranobetonsko ploščo.
      Ni vključena v ceno, ki jo {verb(no_slab, 'navaja', 'navajata', 'navajajo')} {and_join(no_slab)} ({no_slab_n} {plural(no_slab_n, 'hiša', 'hiši', 'hiše', 'hiš')} v vodiču), zato jo kalkulator tem hišam prišteje.
      Površino plošče oceni kot tloris pritličja (neto površina, deljena s številom etaž) in 15 % za stene.</p>
  </section>
  <section class="prose"><h2>Koliko stanejo zemeljska dela in zunanja ureditev?</h2>
    <p>Izkop in zemeljska dela stanejo na lahkem terenu {eur(ze['easy']['min'])} – {eur(ze['easy']['max'])} (običajno okoli {eur(ze['typical'])}), na zahtevnem terenu (skala, naklon) {eur(ze['hard']['min'])} ali več {cite(*ze['source_ids'])}.
      Za tloris okoli 140 m² se to sestavi tako: izkop okoli 1.200 €, odvoz in deponija 1.000–1.500 €, tamponsko nasutje 2.100–2.500 €, izkopi za priključke okoli 1.400 €, geotekstil in utrjevanje okoli 400 €, vse brez DDV.</p>
    <p>Zunanja ureditev stane {span('zunanja_ureditev')}, običajno okoli {eur(items['zunanja_ureditev']['typical'])} {cite(*items['zunanja_ureditev']['source_ids'])}. Osnovna ureditev (60 m² asfalta, 20 m² terase, 80 m panelne ograje po okoli 50 € na meter,
      300 m² zelenice in ponikovalnica za meteorno vodo) stane okoli 10.000 €, lepše urejena okolica 20.000–25.000 €.</p>
  </section>
  <section class="prose"><h2>Subvencija Eko sklada za novogradnjo</h2>
    <p>Eko sklad po javnem pozivu 105SUB-sNESOB23 subvencionira skoraj ničenergijske hiše (sNES+): {', '.join(str(r) for r in t_rates[:-1])} ali {t_rates[-1]} € na m² neto ogrevane površine,
      odvisno od vrste izolacije in potrebe po toploti, za največ {snes['max_area_m2']} m² samostoječe hiše, torej do {eur(snes['max_eur'])} {cite('eko-105')}.
      Subvencija je največ 30 % upravičenih stroškov, ti pa so pri gradnji na ključ največ polovica pogodbene vrednosti, torej največ 15 % cene hiše.
      Projekt, nadzor, zunanja ureditev in sončna elektrarna niso upravičeni stroški.</p>
    <p>Pogoji so strogi: izračun PHPP, potreba po toploti in hladu največ 15 kWh/m²a, zrakotesnost n50 ≤ 0,6, rekuperacija vsaj 80 %, zbiralnik deževnice vsaj 6 m³, sončna elektrarna in vsaj 70 % obnovljivih virov. Brez sončne elektrarne do subvencije niste upravičeni; 10 €/m² manj dobite le, če distributer priključitev elektrarne zavrne {cite('eko-105-cistopis')}.
      {and_join(subsidized)} {verb(subsidized, 'navaja', 'navajata', 'navajajo')} ceno, ki že upošteva subvencijo, zato je kalkulator pri teh hišah ne odšteje še enkrat.
      <a href="../{EKO}/">Vodič po subvenciji Eko sklada za novo hišo</a>.</p>
  </section>
  <section class="prose"><h2>Koliko je DDV pri gradnji hiše?</h2>
    <p>Za stanovanjsko hišo velja znižana stopnja {pct(ddv['reduced'])}, če je njena uporabna površina (vsota bivalnih prostorov) največ 250 m² in izvajalec gradnjo obračuna neposredno investitorju
      kot gradbeno storitev {cite('ddv-pravilnik-54')}. Sicer velja {pct(ddv['general'])}. Za hišo v kompletu brez montaže ter za kuhinjo in vgradne omare je lahko stopnja {pct(ddv['general'])}; preverite pri proizvajalcu ali na FURS.
      Večina tržnih cen v tem kalkulatorju ne navaja, ali vključujejo DDV.</p>
  </section>
  <section class="prose" id="kredit"><h2>Koliko stane kredit za hišo?</h2>
    <p>Banke objavljajo izhodiščne obrestne mere za stanovanjske kredite; dejanska je odvisna od komitentstva, zavarovanja in ocene banke. Fiksna obrestna mera ostane enaka vso dobo,
      spremenljiva je EURIBOR in pribitek banke, zato se obrok spreminja. 6M EURIBOR je bil septembra 2026 v povprečju {rate_txt(eurib['value'])} {cite(*eurib['source_ids'])}.
      Povprečna obrestna mera za nove stanovanjske kredite v Sloveniji je bila avgusta 2026 {rate_txt(avg['all'])}, pri spremenljivi obrestni meri {rate_txt(avg['variable'])}, pri fiksni za več kot 10 let {rate_txt(avg['fixed_over_10y'])} {cite(*avg['source_ids'])}.</p>
    <div class="scroll"><table class="tbl">{thead('Banka', 'Fiksna', 'Spremenljiva', 'Najdaljša doba', 'Pogoji')}<tbody>{bank_rows}</tbody></table></div>
    <p>{and_join([b['bank'] for b in no_rates])} na svojih straneh obrestnih mer ne {verb(no_rates, 'navaja', 'navajata', 'navajajo')} v obliki, ki bi jo lahko preverili
      (OTP banka: do 350.000 €, fiksna do 20 let, spremenljiva do 30 let, brez stroškov odobritve {cite('fin-otp')}; Sparkasse: do 400.000 €, do 30 let, do 80 % vrednosti nepremičnine {cite('fin-sparkasse')}).
      Za Addiko Bank in UniCredit aktualnih obrestnih mer za stanovanjske kredite nismo našli.</p>
    <p><b>Pravila Banke Slovenije.</b> Obroki vseh kreditov smejo znašati največ {lim['dsti_max']} % neto dohodka (DSTI), ne glede na višino dohodka, in po plačilu obrokov vam mora ostati vsaj {eur(lim['min_creditworthiness_eur'])} na mesec, več z vzdrževanimi družinskimi člani.
      Za razmerje med kreditom in vrednostjo nepremičnine (LTV) Banka Slovenije priporoča največ {lim['ltv_recommended']} % za dom, v katerem boste živeli, sicer {lim['ltv_recommended_other']} %. Ročnosti stanovanjskih kreditov ne omejuje; banke jih odobrijo do {max_term} let {cite(*lim['source_ids'])}.</p>
    <p><b>Kredit Eko sklada.</b> Za gradnjo skoraj ničenergijske hiše sNES+ Eko sklad po pozivu {eko['call']} odobri kredit s fiksno obrestno mero {rate_txt(eko['rate_fixed'])}, od {eur(eko['min_eur'])} do {eur(eko['max_eur'])} in z dobo do {eko['max_term_years']} let;
      sklenitev stane 1,5 % (od 40 do 175 €), vodenje 45 € na leto. Kredit lahko dobite poleg subvencije, ne pa za nakup že dokončane hiše {cite(*eko['source_ids'])}.
      <a href="{esc(eko['url'])}" target="_blank" rel="noopener">Javni poziv {eko['call']} na strani Eko sklada</a>.</p>
  </section>
  <section class="prose"><h2>Viri</h2><ol class="viri">{viri_html}</ol>
    <p class="credit-line">Vsi viri so bili pregledani {checked}. Okvirne cene z gradbenih portalov so se pri preverjanju izkazale za prenizke ali nepopolne, zato kalkulator, kjer je mogoče, uporablja cenike posameznih del in dejanske ponudbe.
      Komunalni prispevek je najmanj natančna številka: odloki ga računajo od bruto površine, ki jo ocenimo kot 1,2 × neto, cone, faktorji za stanovanjske hiše in olajšave pa znesek spremenijo.
      Večina tržnih cen ne navaja, ali vključujejo DDV; uporabite jih kot razpon, ne kot ponudbo. Izvedba elektro priključka in telekomunikacijski priključek sta groba ocena; cene plinskega priključka nismo našli.</p>
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


KPD = COST['komunalni_prispevek']
GUIDE_CSS = TABLE_CSS + COSTS_CSS + '''
.prose ul { color: #c9d3e6; padding-left: 20px; margin: 0 0 10px; display: grid; gap: 6px; }
.formula { font-family: var(--font-data); font-size: 14px; overflow-x: auto; white-space: nowrap; padding: 12px 14px; border-radius: 12px; box-shadow: inset 0 0 0 1px var(--line); }
.tbl tfoot th, .tbl tfoot td { border-top: 1px solid var(--line); font-weight: 600; }
'''


def ddate(iso):
    y, m, d = iso.split('-')
    return f'{int(d)}. {int(m)}. {y}'


def dec(v, n=2):
    return f'{v:,.{n}f}'.replace(',', ' ').replace('.', ',').replace(' ', '.')


def citer():
    """cite(ids) numbers sources in order of first use; listing() then gives the page's source list with those numbers."""
    order, by_id = [], {s['id']: s for s in viri()}

    def cite(*ids):
        order.extend(i for i in ids if i not in order)
        return ''.join(f'<a href="#vir-{i}">[{order.index(i) + 1}]</a>' for i in ids)

    def listing():
        return '<ol class="viri">' + ''.join(
            f'<li id="vir-{i}"><a href="{esc(by_id[i]["url"])}" target="_blank" rel="noopener">{esc(by_id[i]["title"])}</a> <span>· {esc(by_id[i]["publisher"])}</span></li>'
            for i in order) + '</ol>'
    return cite, listing


def kp_example(m):
    """(lo, hi, text) for the example case: our odlok calculation (600 m² plot, 180 m² BTP), else vsevem.si's (200 m² BTP)."""
    c = m.get('calc_600_180')
    v = c if c is not None else m['vsevem_600_200']
    lo, hi = (v['min'], v['max']) if isinstance(v, dict) else (v, v)
    return lo, hi, eur(lo) if lo == hi else f'{eur(lo)} – {eur(hi)}'


def kp_gap(m):
    """D-4: one line on why our odlok figure and vsevem.si's differ, where both are shown; only reasons the data backs."""
    c, v, vb = m.get('calc_600_180'), m.get('vsevem_600_200'), m.get('vsevem_basis') or {}
    if not c or not v:
        return ''
    lo = c['min'] if isinstance(c, dict) else c
    fn = max((m.get('coefficients') or {}).get('fn') or [1])
    if vb.get('old'):
        return f'Vsevem.si izračuna manj, ker uporablja {esc(vb["old"])}; mi računamo po veljavnem odloku.'
    if v <= lo:
        return ''
    why = ['računa za 200 m² BTP namesto 180 m²',
           f'vključi tudi {esc(vb["extra"])}' if vb.get('extra') else 'vključi vso komunalno opremo, ki jo občina zaračunava (mi brez plinovoda in vročevoda)']
    if vb.get('fn') and vb['fn'] != fn:
        why.append(f'uporabi faktor namembnosti {num_sl(vb["fn"])} namesto {num_sl(fn)}, ki ga odlok določa za enostanovanjske hiše')
    return 'Vsevem.si izračuna več, ker ' + and_join(why) + '.'


def kp_calc(m, plot=600, btp=180):
    """Each variant (Fn, road zone) as (fn, zone, rows, total), rows (item, amount), from the odlok coefficients in the data."""
    co = m['coefficients']
    out = []
    for fn in co['fn']:
        for zone in co.get('road_zones') or [None]:
            rows = [(it, (plot * it['cpo'] * co['dpo'] + btp * it['cto'] * co['dto'] * fn) * it['psz']) for it in ([zone] if zone else []) + co['items']]
            out.append((fn, zone, rows, sum(a for _, a in rows)))
    lo, hi, _ = kp_example(m)
    # the coefficients must reproduce the stored figure, so the worked example can't drift from the table
    assert (round(min(t for *_, t in out)), round(max(t for *_, t in out))) == (lo, hi), (m['obcina'], [t for *_, t in out])
    return out


def article_ld(h1, desc, url, image):
    return {'@context': 'https://schema.org', '@type': 'Article', 'headline': h1, 'description': desc, 'inLanguage': 'sl', 'url': url,
            'dateModified': COST['as_of'], 'image': SITE + image, 'author': {'@type': 'Organization', 'name': 'Hišni vodič', 'url': SITE}}


def kp_hub():
    url = SITE + KP + '/'
    cite, listing = citer()
    nat = KPD['national_range']
    nat_min, nat_max = re.search(r'min ([^,]+), max ([^,]+)', nat['basis']).groups()
    covered, of = re.search(r'(\d+) of (\d+) municipalities', nat['basis']).groups()
    ms = sorted(KPD['municipalities'], key=lambda m: -kp_example(m)[1])
    odloki = [m for m in KPD['municipalities'] if m.get('coefficients')]
    # a function, so its citations are numbered where the table appears, after the lede's
    # N-16/N-17: the two bases (our odlok calculation at 180 m² BTP, vsevem.si at 200 m²) are listed apart, each sorted on its own
    row = lambda m: (f'<tr><th scope="row"><a href="{slugify(m["obcina"])}/">{esc(m["obcina"])}</a></th><td class="n">{kp_example(m)[2]}</td>'
                     f'<td>{"po odloku, parcela 600 m², 180 m² BTP" if m.get("calc_600_180") else "vsevem.si, parcela 600 m², 200 m² BTP"}</td><td>{CONF[m["confidence"]]} {cite(*m["source_ids"])}</td></tr>')
    rows = lambda: (f'<tbody><tr class="grp"><th colspan="4" scope="rowgroup">Izračun po odloku · parcela 600 m², hiša 180 m² BTP</th></tr>' +
                    ''.join(row(m) for m in ms if m.get('calc_600_180')) +
                    f'</tbody><tbody><tr class="grp"><th colspan="4" scope="rowgroup">Izračun vsevem.si · parcela 600 m², hiša 200 m² BTP</th></tr>' +
                    ''.join(row(m) for m in ms if not m.get('calc_600_180')) + '</tbody>')
    h1 = f'Komunalni prispevek za hišo {YEAR}'
    desc = (f'Komunalni prispevek za novo hišo po občinah: od {eur(nat["min"])} do {eur(nat["max"])}, povprečno {eur(nat["typical"])}. '
            f'Formula, izračun za {len(ms)} občin in viri.')
    return f'''{head(f'{h1}: izračun po občinah · Hišni vodič', h1, desc, url, SITE + 'img/og/kp.jpg', article_ld(h1, desc, url, 'img/og/kp.jpg')).replace('</head>', '<style>' + GUIDE_CSS + '</style></head>')}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / <a href="../{COSTS}/">Stroški gradnje</a> / Komunalni prispevek</div>
    <div class="head"><div><h1 class="display">{h1}</h1><div class="prov">Izračun po občinah · podatki preverjeni {ddate(COST['as_of'])}</div></div></div>
  </div>
  <div class="lede"><p>Komunalni prispevek je del stroškov komunalne opreme (ceste, vodovod, kanalizacija, javne površine), ki ga investitor plača občini.
    Plačati ga morate za vsako novo hišo, za katero potrebujete gradbeno dovoljenje; občina ga odmeri pred izdajo dovoljenja {cite('kp-uredba-2026', 'kp-tolmin')}.</p>
    <p>Za {covered} od {of} slovenskih občin je povprečje <b>{eur(nat['typical'])}</b>, najmanj {eur(nat['min'])} ({nat_min}), največ {eur(nat['max'])} ({nat_max}),
    za parcelo 600 m² in 200 m² bruto tlorisne površine {cite(*nat['source_ids'])}. Po oceni arhitekta za 24ur je to običajno okoli desetina naložbe brez zemljišča {cite('kp-24ur-2026')}.</p></div>
  <section><h2>Komunalni prispevek po občinah</h2>
    <div class="scroll"><table class="tbl">{thead('Občina', 'Znesek za primer', 'Osnova', 'Zanesljivost')}{rows()}</table></div>
    <p class="credit-line">Primer: parcela 600 m² in hiša s 180 m² bruto tlorisne površine (BTP, okoli 150 m² neto), izračunano iz občinskega odloka.
      Kjer odloka nismo preračunali, je naveden izračun vsevem.si za 200 m² BTP z vso komunalno opremo; zneska z različno osnovo nista neposredno primerljiva.
      Za občine z izračunom po odloku <a href="../{COSTS}/">kalkulator</a> prispevek preračuna za izbrano hišo in vašo parcelo; za druge uporabi znesek za primer, za ostale občine povprečje {eur(nat['typical'])}.</p>
  </section>
  <section class="prose"><h2>Kako se izračuna komunalni prispevek?</h2>
    <p>Prispevek se izračuna iz površine parcele, bruto tlorisne površine hiše in cen komunalne opreme iz občinskega odloka {cite('kp-koper', 'kp-tolmin', 'kp-uredba-53-26')}:</p>
    <p class="formula">KP = Σ (A<sub>parcela</sub> × Cpo × Dpo + A<sub>BTP</sub> × Cto × Dto × Fn) × psz</p>
    <ul>
      <li><b>Cpo in Cto</b>: cena posamezne vrste komunalne opreme na m² parcele oziroma na m² BTP, določi jo odlok.</li>
      <li><b>Dpo in Dto</b>: delež parcele in delež površine objekta, skupaj 1, na primer 0,3 in 0,7 (Koper, Ptuj, Ljubljana, Novo mesto) ali 0,5 in 0,5 (Maribor, Celje, Kranj, Tolmin).</li>
      <li><b>Fn</b>: faktor namembnosti za enostanovanjske stavbe (CC-SI 1110), na primer 1,0 v Kopru in 0,7 na Ptuju.</li>
      <li><b>psz</b>: prispevna stopnja zavezanca, delež cene, ki ga plača investitor; če je odlok ne določi, 100 %.</li>
    </ul>
    <p>Ceste in javne površine se zaračunajo vedno, vodovod, kanalizacija, plin in daljinsko ogrevanje pa le, če se hiša nanje priključi. Znesek je odvisen od občine, v nekaterih tudi od cone (Koper ima pet con cest).
      Okvir je doslej določala uredba iz leta 2019 (Ur. l. RS 20/19), od 28. 3. 2026 pa nova uredba (Ur. l. RS 53/26) po zakonu ZUreP-3; formula ostaja enaka {cite('kp-uredba-53-26', 'kp-uredba-2026')}.</p>
  </section>
  <section class="prose"><h2>Ali se komunalni prispevek indeksira?</h2>
    <p>Ne. Odmera se računa s cenami iz veljavnega odloka. Odloki, ki smo jih prebrali v celoti ({and_join([m['obcina'] for m in odloki if m['confidence'] == 'high'])}), nimajo določbe o indeksaciji
      {cite(*[i for m in odloki if m['confidence'] == 'high' for i in m['source_ids'] if i in ('kp-lj-ul', 'kp-koper', 'kp-celje-ul', 'kp-kranj-ul', 'kp-nm-npb3', 'kp-ptuj')])},
      prav tako je nimata zakon ZUreP-3 in nova uredba (Ur. l. RS 53/26) {cite('kp-uredba-53-26')}. Ocene, ki zneskom iz odlokov prištevajo indeksacijo, so zato previsoke.</p>
  </section>
  <section class="prose"><h2>Preverite znesek na občini</h2>
    <p>Zneski so ocena za tipičen primer. Dejanska odmera je odvisna od velikosti parcele in hiše, cone, priključkov in sprememb odloka.
      Pred nakupom parcele vprašajte občino, koliko bo znašal komunalni prispevek za konkretno parcelo in hišo.</p>
  </section>
  <div class="actions">
    <a class="btn glow" href="../{COSTS}/">Izračunajte celotne stroške gradnje <span class="arrow">→</span></a>
    <a class="btn line" href="../{EKO}/">Subvencija Eko sklada</a>
    <a class="btn line" href="../{GUIDE}/">Cene montažnih hiš</a>
  </div>
  <section class="prose"><h2>Viri</h2>{listing()}</section>
</main>
{FOOT}
</body>
</html>
'''


KP_IN = {'Ljubljana': 'v Ljubljani', 'Maribor': 'v Mariboru', 'Celje': 'v Celju', 'Kranj': 'v Kranju', 'Koper': 'v Kopru', 'Novo mesto': 'v Novem mestu',
         'Ptuj': 'na Ptuju', 'Domžale': 'v Domžalah', 'Kamnik': 'v Kamniku', 'Škofja Loka': 'v Škofji Loki', 'Murska Sobota': 'v Murski Soboti',
         'Brežice': 'v Brežicah', 'Krško': 'v Krškem', 'Grosuplje': 'v Grosupljem'}  # locative case; other municipalities fall back to "v občini X"


def kp_page(m):
    name, sid = m['obcina'], slugify(m['obcina'])
    url = f'{SITE}{KP}/{sid}/'
    cite, listing = citer()
    lo, hi, amount = kp_example(m)
    co = m.get('coefficients')
    years = re.findall(r'(\d{4})-\d\d-\d\d', m['as_of'])
    others = sorted((o for o in KPD['municipalities'] if o is not m), key=lambda o: o['obcina'])
    h1 = f'Komunalni prispevek {name} {YEAR}'
    if co:
        calc = kp_calc(m)
        fn_txt = ' ali '.join(dec(f, 1) for f in co['fn'])
        psz = sorted({it['psz'] for it in co['items'] + co.get('road_zones', [])})
        basis = (f'Izračun po občinskem odloku (sprejet {years[0]}' + (f', spremenjen {years[1]}' if len(years) > 1 else '') + f') {cite(*m["source_ids"])}: '
                 f'Dpo {dec(co["dpo"], 1)} in Dto {dec(co["dto"], 1)}, faktor namembnosti Fn {fn_txt}, prispevna stopnja '
                 + ('100 % za vso opremo' if psz == [1] else 'od ' + dec(psz[0] * 100, 0) + ' do ' + dec(psz[-1] * 100, 0) + ' %, odvisno od opreme') + '.')
        fn, zone, rows, total = calc[0]
        it, a = rows[0]
        trs = ''.join(f'<tr><th scope="row">{esc(i["name"])}</th><td class="n">{dec(i["cpo"])}</td><td class="n">{dec(i["cto"])}</td><td class="n">{dec(i["psz"] * 100, 0)} %</td><td class="n">{dec(v)} €</td></tr>' for i, v in rows)
        variants = ''
        if len(calc) > 1:
            variants = ('Z drugimi ' + ('conami cest' if zone else 'faktorji namembnosti') + ' znaša prispevek ' + and_join(
                [f'{eur(round(t))} ({esc(z["name"]) if z else "Fn " + dec(f, 1)})' for f, z, _, t in calc[1:]]) + '.')
        example = f'''<section class="prose"><h2>Izračun po korakih</h2>
    <p>Za parcelo 600 m² in 180 m² BTP{' v coni ' + esc(zone['name'].split()[-1]) if zone else ''}{' s Fn ' + dec(fn, 1) if len(co['fn']) > 1 else ''} se za vsako vrsto opreme izračuna (600 × Cpo × {dec(co['dpo'], 1)} + 180 × Cto × {dec(co['dto'], 1)} × {dec(fn, 1)}) × psz {cite(*co['source_ids'])}.
      Za {esc(it['name'])}:</p>
    <p class="formula">(600 × {dec(it['cpo'])} × {dec(co['dpo'], 1)} + 180 × {dec(it['cto'])} × {dec(co['dto'], 1)} × {dec(fn, 1)}) × {dec(it['psz'] * 100, 0)} % = {dec(a)} €</p>
    <div class="scroll"><table class="tbl">{thead('Oprema', 'Cpo (€/m²)', 'Cto (€/m²)', 'psz', 'Znesek')}<tbody>{trs}</tbody>
      <tfoot><tr><th scope="row" colspan="4">Skupaj</th><td class="n">{eur(round(total))}</td></tr></tfoot></table></div>
    <p>{variants}{' Ni upoštevano: ' + esc(co['not_included']) + '.' if co.get('not_included') else ''}</p>
  </section>'''
    else:
        basis = (f'Izračun portala vsevem.si za parcelo 600 m² in 200 m² BTP z vso komunalno opremo, podatki z dne {ddate(m["as_of"])} {cite(*m["source_ids"])}. '
                 'Odloka nismo preračunali, zato koeficientov ne navajamo; za manjšo hišo ali brez priključka na vso opremo bo znesek nižji.')
        example = ''
    why = {'high': 'Znesek smo izračunali iz veljavnega občinskega odloka.',
           'medium': 'Znesek je izračun zasebnega portala, ne občine, in ni preverjen v odloku.',
           'low': 'Spremembo odloka smo povzeli po novicah, ker uradno besedilo ni bilo dosegljivo' + (', faktor namembnosti za hiše pa ni potrjen, zato navajamo razpon.' if co and len(co['fn']) > 1 else '.')}[m['confidence']]
    compare = (f' Za primerjavo: vsevem.si za 200 m² BTP z vso komunalno opremo izračuna {eur(m["vsevem_600_200"])} {cite("kp-vsevem")}. {kp_gap(m)}' if m.get('calc_600_180') else '')
    desc = f'Komunalni prispevek v občini {name} za hišo: {amount} za parcelo 600 m² in {"180" if m.get("calc_600_180") else "200"} m² BTP. Izračun, formula in viri.'
    page_ = f'''{head(f'{h1}: koliko stane za hišo · Hišni vodič', h1, desc, url, SITE + 'img/og/kp.jpg', article_ld(h1, desc, url, 'img/og/kp.jpg')).replace('</head>', '<style>' + GUIDE_CSS + '</style></head>')}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / <a href="../{KP}/">Komunalni prispevek</a> / {esc(name)}</div>
    <div class="head"><div><h1 class="display">{esc(h1)}</h1><div class="prov">Parcela 600 m², hiša {"180" if m.get("calc_600_180") else "200"} m² BTP</div></div></div>
  </div>
  <div class="total"><span class="eyebrow">Komunalni prispevek za primer</span><b>{amount}</b><p>Zanesljivost: {CONF[m['confidence']]}. {why}</p></div>
  <div class="lede"><p>{basis}{compare}</p></div>
  {example}
  <section class="prose"><h2>Preverite znesek na občini</h2>
    <p>To je ocena za tipičen primer. {'Kalkulator stroškov jo po formuli iz odloka preračuna za hišo, ki jo izberete, in za velikost vaše parcele.' if co else 'Kalkulator stroškov uporabi ta znesek za primer ne glede na velikost hiše, ker koeficientov odloka nimamo.'}
      Dejanska odmera je odvisna od velikosti parcele in hiše, priključkov, cone in morebitnih sprememb odloka.
      Pred nakupom parcele vprašajte občino, koliko bo znašal komunalni prispevek za to parcelo in hišo.</p>
  </section>
  <div class="actions">
    <a class="btn glow" href="../{COSTS}/#kp={sid}">Izračunaj celotne stroške gradnje {esc(KP_IN.get(name, 'v občini ' + name))} <span class="arrow">→</span></a>
    <a class="btn line" href="../{KP}/">Vse občine</a>
  </div>
  <section><h2>Komunalni prispevek v drugih občinah</h2><ul class="siblings">{''.join(f'<li><a href="../{KP}/{slugify(o["obcina"])}/">{esc(o["obcina"])}</a> · {kp_example(o)[2]}</li>' for o in others)}</ul></section>
  <section class="prose"><h2>Viri</h2>{listing()}</section>
</main>
{FOOT}
</body>
</html>
'''
    return page_.replace('"../', '"../../')  # written one level deeper than the shared bar, footer and head assume


def eko_page():
    url = SITE + EKO + '/'
    cite, listing = citer()
    items = {it['key']: it for it in COST['items']}
    e = items['eko_sklad_snes']
    tiers = snes_tiers(e)
    rows = ''.join(f'<tr><th scope="row">Skupina {g} <small>{SNES_GROUP[g]}</small></th><td class="n">{a} €/m²</td><td class="n">{b} €/m²</td>'
                   f'<td class="n">{eur(min(a * e["max_area_m2"], e["max_eur"]))}</td></tr>' for g, a, b in tiers)
    top, low = tiers[0][1], tiers[-1][2]
    stage_has = lambda m, k: k in m['price_stage'].lower()
    sub = [p['name'] for p in data['providers'] if any(stage_has(m, 'subvencij') for m in p['models'] if m['price_eur'])]
    plain = sorted(((p, m) for p, m in models if m['price_eur'] and m['area_m2'] and not stage_has(m, 'subvencij') and m['area_m2'] >= e['max_area_m2']), key=lambda pm: pm[1]['price_eur'])
    p, m = plain[len(plain) // 2]  # a mid-priced house of at least 150 m², its price not already cut by a subsidy
    cap15 = round(0.3 * 0.5 * m['price_eur'])
    priced = [o for _, o in models if o['price_eur'] and o['area_m2'] and not stage_has(o, 'subvencij')]
    binds = sum(1 for o in priced if 0.3 * 0.5 * o['price_eur'] < top * min(o['area_m2'], e['max_area_m2']))
    ex = lambda r: min(r * e['max_area_m2'], e['max_eur'], cap15)
    phpp = items['phpp']['value']
    phpp_txt = eur(phpp) if not isinstance(phpp, dict) else f'{eur(phpp["min"])} – {eur(phpp["max"])}'
    h1 = f'Subvencija Eko sklada za novo hišo {YEAR}'
    desc = (f'Eko sklad za novo skoraj ničenergijsko hišo (sNES+) da {low}–{top} € na m², za največ {e["max_area_m2"]} m², torej do {eur(e["max_eur"])}. '
            'Pogoji, omejitve, primer izračuna in katere cene subvencijo že upoštevajo.')
    verb = lambda names, one, two, many: one if len(names) == 1 else two if len(names) == 2 else many
    return f'''{head(f'{h1}: koliko in pod katerimi pogoji · Hišni vodič', h1, desc, url, SITE + 'img/og/eko.jpg', article_ld(h1, desc, url, 'img/og/eko.jpg')).replace('</head>', '<style>' + GUIDE_CSS + '.tbl th small { display: block; font-weight: 400; color: var(--mist); font-size: 12.5px; }</style></head>')}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / <a href="../{COSTS}/">Stroški gradnje</a> / Subvencija Eko sklada</div>
    <div class="head"><div><h1 class="display">{h1}</h1><div class="prov">Javni poziv 105SUB-sNESOB23 · poziv: stanje {ddate(e['as_of'])} · preverjeno {ddate(COST['as_of'])}</div></div></div>
  </div>
  <div class="lede"><p>Eko sklad po javnem pozivu 105SUB-sNESOB23 daje nepovratno subvencijo za novo skoraj ničenergijsko hišo (sNES+): od {low} do {top} € na m² neto ogrevane površine,
    za največ {e['max_area_m2']} m² samostoječe hiše (120 m² pri dvojčku ali vrstni hiši), torej <b>do {eur(e['max_eur'])}</b> {cite('eko-105', 'eko-105-cistopis')}.
    Poziv je odprt, nazadnje spremenjen 12. 3. 2026 {cite('eko-105-spr2026')}; ob preverjanju {ddate(COST['as_of'])} je bil nespremenjen.</p></div>
  <section><h2>Koliko znaša subvencija na m²?</h2>
    <div class="scroll"><table class="tbl">{thead('Izolacija', 'QH ≤ 10 kWh/m²a', 'QH ≤ 15 kWh/m²a', f'Največ za {e["max_area_m2"]} m²')}<tbody>{rows}</tbody></table></div>
    <p class="credit-line">QH je letna potreba po toploti za ogrevanje na m². Znesek na m² je odvisen od vrste toplotne izolacije in od QH {cite('eko-105')}. V Triglavskem narodnem parku je subvencija za 25 % višja.</p>
  </section>
  <section class="prose"><h2>Omejitve: največ 15 % cene hiše</h2>
    <p>Subvencija je največ 30 % upravičenih stroškov. Pri gradnji na ključ so upravičeni stroški največ polovica pogodbene vrednosti, zato subvencija ne preseže okoli 15 % cene hiše {cite('eko-105', 'eko-105-cistopis')}.</p>
    <p><b>Primer:</b> <a href="../{m['slug']}/">{esc(p['name'])} {esc(m['name'])}</a> ima {round(m['area_m2'])} m² in stane {eur(m['price_eur'])}. Subvencija se računa za največ {e['max_area_m2']} m²:
      pri {top} €/m² je to {eur(top * e['max_area_m2'])}, pri {low} €/m² {eur(low * e['max_area_m2'])}. Meja 15 % cene je {eur(cap15)}{', zato je subvencija omejena nanjo' if ex(top) == cap15 else ' in pri tej hiši ne omejuje'}: dobite
      {eur(ex(top))} oziroma {eur(ex(low))}. Pri {top} €/m² meja 15 % odloči le pri hiši, ki stane manj kot okoli {eur(round(top / 0.15))} na m²;
      med {len(priced)} hišami v vodiču z objavljeno ceno brez subvencije {f'je takih {binds}' if binds else 'ni nobene take'}.</p>
    <p><a href="../{COSTS}/#snes=1&amp;h={m['slug']}">Izračunajte celotne stroške te hiše s subvencijo</a> ali v kalkulatorju izberite svojo hišo.</p>
  </section>
  <section class="prose"><h2>Pogoji za subvencijo</h2>
    <ul>
      <li>Izračun energijske bilance s programom PHPP (stane okoli {phpp_txt} {cite(*items['phpp']['source_ids'])}).</li>
      <li>Letna potreba po toploti za ogrevanje (QH) in hlajenje (QK) največ 15 kWh/m².</li>
      <li>Zrakotesnost n50 največ 0,6 izmenjave zraka na uro.</li>
      <li>Prezračevanje z vračanjem toplote (rekuperacija) z izkoristkom vsaj 80 %.</li>
      <li>Zbiralnik deževnice s prostornino vsaj 6 m³.</li>
      <li>Sončna elektrarna, ki pokrije porabo elektrike v hiši, je obvezna: brez nje do subvencije niste upravičeni. 10 €/m² manj dobite le, če distributer priključitev elektrarne zavrne {cite('eko-105-cistopis')}.</li>
      <li>Vsaj 70 % energije iz obnovljivih virov.</li>
    </ul>
    <p>Pred oddajo vloge morate imeti <b>pravnomočno gradbeno dovoljenje</b>. Vloge se obravnavajo po vrstnem redu prejema, dokler so sredstva na voljo; poziv ima 5 milijonov evrov {cite('eko-105-spr2026')}.
      Upravičene so naložbe, začete po 1. 1. 2023, za eno stavbo lahko oddate eno vlogo {cite('eko-105')}.</p>
    <p>Mnoge tipske montažne hiše teh pogojev brez nadgradenj ne izpolnjujejo, zato pri proizvajalcu vprašajte za izvedbo sNES+.</p>
  </section>
  <section class="prose"><h2>Kaj ni upravičen strošek?</h2>
    <p>Projektna dokumentacija, gradbeni nadzor, zunanja ureditev in sončna elektrarna (od spremembe 12. 3. 2026) {cite('eko-105', 'eko-105-spr2026')}.
      Za sončno elektrarno lahko pridobite subvencijo Borzena, poleg subvencije lahko najamete kredit Eko sklada. Drugih nepovratnih spodbud Eko sklada za isto hišo, razen za sončno elektrarno, ne morete pridobiti {cite('eko-105')}.</p>
  </section>
  <section class="prose"><h2>Cene, ki subvencijo že upoštevajo</h2>
    <p>{and_join(sub)} {verb(sub, 'navaja', 'navajata', 'navajajo')} ceno, ki je že zmanjšana za subvencijo Eko sklada (oziroma za subvencije in popuste).
      Pri teh hišah subvencije ne odštejte še enkrat; kalkulator stroškov jo pri njih samodejno izpusti. <a href="../{GUIDE}/">Kaj vključujejo cene posameznih proizvajalcev</a>.</p>
  </section>
  <div class="actions">
    <a class="btn glow" href="../{COSTS}/#snes=1">Izračunajte stroške s subvencijo <span class="arrow">→</span></a>
    <a class="btn line" href="../{KP}/">Komunalni prispevek</a>
    <a class="btn line" href="{esc(next(s['url'] for s in viri() if s['id'] == 'eko-105'))}" target="_blank" rel="noopener">Poziv na strani Eko sklada ↗</a>
  </div>
  <section class="prose"><h2>Viri</h2>{listing()}</section>
</main>
{FOOT}
</body>
</html>
'''


DATE_RE = re.compile(r'(\d{1,2})\. ?(\d{1,2})\. ?(\d{4})')
TODAY = datetime.date.today()


def first_date(text):
    mo = DATE_RE.search(text or '')
    return datetime.date(int(mo.group(3)), int(mo.group(2)), int(mo.group(1))) if mo else None


def upcoming(days):
    """Open days dated on or after the build date: past events drop out when the site is regenerated; undated lines too."""
    return [d for d in days if first_date(d) and first_date(d) >= TODAY]


def is_event(sh):
    """A one-off open day rather than a show house or showroom you can visit."""
    return bool(re.search(r'odprtih vrat', sh['name'], re.I) or first_date(sh.get('hours')))


SHOW_CSS = MFACTS_CSS + """
.shows { display: grid; gap: 36px; }
.shows h2 a { color: var(--ink); text-decoration: none; }
.sh-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr)); gap: 14px; margin-top: 4px; }
.sh { padding: 16px 18px; border-radius: var(--r); background: var(--dusk); box-shadow: 0 0 0 1px var(--line); color: #c9d3e6; font-size: 15px; }
.sh b { display: block; color: var(--ink); font-size: 16px; margin-bottom: 6px; }
.sh p { margin: 4px 0 0; }
.sh .k { color: var(--mist); font: 500 11px/1.4 var(--font-data); letter-spacing: .1em; text-transform: uppercase; margin-right: 6px; }
.sh .tag { display: inline-block; margin-bottom: 8px; color: var(--glow); font: 500 11px/1.4 var(--font-data); letter-spacing: .1em; text-transform: uppercase; }
.days { margin: 10px 0 0; padding-left: 20px; color: #c9d3e6; display: grid; gap: 6px; }
.none { color: var(--mist); margin: 6px 0 0; }
.none a { color: var(--ink); }
"""


def show_page():
    url = SITE + SHOW + '/'
    said = lambda v: v and v != NOT_SAID
    place = lambda sh: ', '.join(esc(v) for v in (sh.get('address'), sh.get('town')) if said(v))
    sections, without, studio_only, n_days = [], [], [], 0
    for p in data['providers']:
        info = INFO.get(p['id'])
        if not info:
            continue
        shs = info.get('show_houses') or []
        perm = [sh for sh in shs if not is_event(sh)]
        events = [(sh, upcoming(sh.get('open_days') or [])) for sh in shs]
        events = [(sh, ds) for sh, ds in events if ds]
        n_days += sum(len(ds) for _, ds in events)
        if not perm:
            without.append(p)
        elif all(sh.get('kind') == 'studio' for sh in perm):
            studio_only.append(p)
        # missing fields are left out, not printed as "ni navedeno"
        cards = ''.join(
            f'<div class="sh">' + ('<span class="tag">Svetovalni studio, ne vzorčna hiša</span>' if sh.get('kind') == 'studio' else
                                   '<span class="tag">V tujini</span>' if sh.get('abroad') else '') +
            f'<b>{esc(sh["name"])}</b>' + (f'<p><span class="k">Kje</span>{place(sh)}</p>' if place(sh) else '') +
            (f'<p><span class="k">Odprto</span>{esc(sh["hours"])}</p>' if said(sh.get('hours')) else '') +
            f'<p>{src_link(sh.get("url")).replace("vir ↗", "stran proizvajalca ↗")}</p></div>' for sh in perm)
        # a show house's own open day may be held elsewhere (Marles: a house near Maribor), so only one-off events name their place
        house = lambda sh: f' · <a href="../{sh["house"]}/">hiša v vodiču</a>' if sh.get('house') in slugs else ''
        days = ''.join(f'<li>{esc(d)}' + (f' · {esc(sh["name"])}{", " + esc(sh["town"]) if said(sh.get("town")) else ""}{house(sh)}' if is_event(sh) else '') +
                       f'{src_link(sh.get("url"))}</li>' for sh, ds in events for d in ds)
        note = info.get('note')
        note_html = (f'<p class="none">{esc(note["text"])}' + ''.join(
            f' · <a href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l["label"])} ↗</a>' for l in note.get('links', [])) + '</p>') if note else ''
        sections.append(
            f'<section id="{p["id"]}"><h2><a href="../{p["id"]}/">{esc(p["name"])}</a></h2>' +
            (f'<div class="sh-grid">{cards}</div>' if cards else '<p class="none">Stalne vzorčne hiše ali salona proizvajalec ne navaja.</p>') +
            (f'<h3 class="eyebrow">Dnevi odprtih vrat</h3><ul class="days">{days}</ul>' if days else '<p class="none">Prihodnjih dni odprtih vrat proizvajalec trenutno ne objavlja.</p>') +
            note_html +
            f'<p class="none"><a href="../{p["id"]}/#dejstva">Garancija, čas gradnje in povpraševanje pri {esc(p["name"])}</a> · preverjeno {ddate(info["checked"])}</p></section>')
    makers_with = [p['name'] for p in data['providers'] if INFO.get(p['id']) and p not in without and p not in studio_only]
    studios = [p['name'] for p in studio_only]
    abroad = [(p['name'], sh['town']) for p in data['providers'] for sh in (INFO.get(p['id']) or {}).get('show_houses') or [] if sh.get('abroad')]
    h1 = 'Kje si ogledati montažne hiše'
    desc = (f'Vzorčne hiše, razstavni saloni in dnevi odprtih vrat slovenskih proizvajalcev montažnih hiš: naslov, odpiralni čas in povezava. '
            f'Stalno vzorčno hišo ali salon navaja {len(makers_with)} od {len(INFO)} proizvajalcev.')
    ld = {'@context': 'https://schema.org', '@type': 'WebPage', 'name': h1, 'url': url, 'description': desc, 'inLanguage': 'sl'}
    return f'''{head(f'{h1}: vzorčne hiše in dnevi odprtih vrat · Hišni vodič', h1, desc, url, SITE + 'img/og/vzorcne.jpg', ld).replace('</head>', '<style>' + SHOW_CSS + '</style></head>')}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / Vzorčne hiše</div>
    <div class="head"><div><h1 class="display">{h1}</h1><div class="prov">Vzorčne hiše, saloni in dnevi odprtih vrat · stanje {ddate(TODAY.isoformat())}</div></div></div>
  </div>
  <div class="lede"><p>Stalno vzorčno hišo ali razstavni salon {verb3(makers_with, 'navaja', 'navajata', 'navajajo')} {and_join(makers_with)}{
    ''.join(f' ({esc(n)} tudi v tujini: {esc(t)})' for n, t in abroad)}{
    f"; {and_join(studios)} {verb3(studios, 'ima', 'imata', 'imajo')} svetovalni studio, ne vzorčne hiše" if studios else ""}.
    {and_join([p['name'] for p in without])} {verb3(without, 'stalne vzorčne hiše ne navaja', 'stalne vzorčne hiše ne navajata', 'stalne vzorčne hiše ne navajajo')};
    nekateri pokažejo hiše na dnevih odprtih vrat. Prikazani so le dnevi od {ddate(TODAY.isoformat())} naprej{'' if n_days else '; trenutno ni objavljen noben'}.
    Pred obiskom preverite termin pri proizvajalcu; za ogled je pogosto potrebna prijava.</p></div>
  <div class="shows">{''.join(sections)}</div>
  <div class="actions">
    <a class="btn glow" href="{SITE}#kviz">Poiščite hišo, ki vam pristaja <span class="arrow">→</span></a>
    <a class="btn line" href="../{GUIDE}/">Cene montažnih hiš</a>
  </div>
</main>
{FOOT}
</body>
</html>
'''


def verb3(names, one, two, many):
    return one if len(names) == 1 else two if len(names) == 2 else many


# TODO(owner): fill these in; while they are None, /o-vodicu/ renders nothing for them.
CONTACT = None  # e-mail for corrections, e.g. 'info@hisomer.si'
OWNER = None  # who runs the guide: a name or company, and a line on why
FUNDING = None  # the funding statement, e.g. 'Brez oglasov, provizij in plačil proizvajalcev.'
UMAMI = 'cloud.umami.is/script.js' in src  # the analytics note is shown only while the script is on the pages


def about_page():
    url = SITE + ABOUT + '/'
    priced = [m for _, m in models if m['price_eur']]
    n_ok = sum(1 for m in priced if ok(m))
    reduced = sorted({p['name'] for p, m in models if m['price_eur'] and not ok(m) and 'osnovni' not in m['price_stage'].lower()})
    basic = sorted({p['name'] for p, m in models if m['price_eur'] and 'osnovni' in m['price_stage'].lower()})
    unpriced = [(p, m) for p, m in models if not m['price_eur']]
    n_est = sum(1 for p, m in unpriced if estimate(p, m))
    checked = max(i['checked'] for i in INFO.values())
    h1 = 'O Hišnem vodiču'
    desc = 'Kaj je Hišni vodič, kako zbiramo in primerjamo cene montažnih hiš, kako preverjamo stroške gradnje in kako pogosto posodabljamo podatke.'
    ld = {'@context': 'https://schema.org', '@type': 'AboutPage', 'name': h1, 'url': url, 'description': desc, 'inLanguage': 'sl'}
    return f'''{head(f'{h1}: neodvisnost, viri in metoda · Hišni vodič', h1, desc, url, SITE + 'img/og/site.jpg', ld).replace('</head>', '<style>' + TABLE_CSS + COSTS_CSS + '</style></head>')}
<body>
{BAR}
<main class="wrap page">
  <div>
    <div class="eyebrow crumbs"><a href="../">Hišni vodič</a> / O vodiču</div>
    <div class="head"><div><h1 class="display">{h1}</h1><div class="prov">Cene hiš: {esc(data['collected'])} · stroški gradnje preverjeni {ddate(COST['as_of'])}</div></div></div>
  </div>
  <section class="prose"><h2>Kaj je Hišni vodič</h2>
    <p>Hišni vodič na enem mestu primerja {len(models)} tipskih montažnih hiš {len(data['providers'])} slovenskih proizvajalcev: ceno in kaj vključuje, velikost, tloris,
      celotne stroške gradnje s komunalnim prispevkom in priključki ter subvencijo Eko sklada.</p>
    <p><b>Neodvisnost.</b> Hišni vodič ni povezan s proizvajalci. Vrstni red hiš in oznake, kot je »najnižja«, določajo samo podatki po pravilih spodaj.</p>
  </section>
  <section class="prose" id="cene"><h2>Kako zbiramo in primerjamo cene</h2>
    <p>Cene prepišemo s spletnih strani, cenikov in ponudbenih brošur proizvajalcev. Pri vsaki hiši je navedeno, kaj cena vključuje in od kod je.
      Cena proizvajalca je vedno glavna številka. Proizvajalci pa navajajo cene za različne pakete, zato jih za razvrščanje izenačimo:</p>
    <ul>
      <li><b>Primerljiva cena</b> je cena proizvajalca, ki ji pri hišah brez temeljne plošče prištejemo oceno plošče: tloris pritličja (neto površina, deljena s številom etaž, in 15 % za stene)
        × {num_sl(SLAB_MID)} €/m², sredina razpona {SLAB['min']}–{SLAB['max']} €/m² iz <a href="../{COSTS}/">kalkulatorja stroškov</a>. Kjer se razlikuje od cene proizvajalca, je navedena pod njo.</li>
      <li><b>Ne razvrščamo</b> cen, ki so že zmanjšane za subvencijo ali popust ({and_join(reduced)}), in osnovnih paketov, ki niso na ključ ({and_join(basic)}).
        Navedemo jih posebej, z opombo, in jih nikoli ne imenujemo najcenejše. Primerljivih je {n_ok} od {len(priced)} objavljenih cen.</li>
      <li><b>Najcenejše hiše in oznaka »najnižja«</b> veljajo le za primerljive cene. V primerjavi hiš oznaka velja za skupno ceno in za ceno na m², ker so večje hiše na m² praviloma cenejše.</li>
      <li><b>Cena na m²</b> je povsod primerljiva cena, deljena z neto bivalno površino.</li>
      <li><b>Okvirna ocena</b> za hiše brez objavljene cene ({len(unpriced)} hiš) je mediana primerljive cene istega proizvajalca na m² (enaka podlaga kot v <a href="../{GUIDE}/">pregledu cen</a>), pomnožena s površino hiše. Navedemo jo le, če ima proizvajalec
        vsaj {EST_MIN} primerljivih cen (zdaj pri {n_est} hišah), in jo vedno označimo kot oceno, ne kot ceno proizvajalca.</li>
    </ul>
  </section>
  <section class="prose" id="stroski"><h2>Kako preverjamo stroške gradnje</h2>
    <p>Stroške v <a href="../{COSTS}/">kalkulatorju</a> preverjamo v primarnih virih: občinskih odlokih o komunalnem prispevku, javnem pozivu Eko sklada, cenikih omrežnin in komunalnih podjetij
      ter cenikih posameznih del (temeljna plošča, priključki, dokumentacija). Okvirne cene z gradbenih portalov so se pri preverjanju izkazale za prenizke ali nepopolne,
      zato jih ne uporabljamo kot končne številke. Pri vsaki postavki sta navedena vir in zanesljivost: uradni podatek, okvirno ali zelo okvirno.</p>
    <p>Komunalni prispevek za občine z odlokom izračunamo po formuli iz odloka za vašo parcelo in hišo; za druge je naveden znesek za primer. <a href="../{KP}/">Komunalni prispevek po občinah</a></p>
    <p>Obrestne mere za izračun obroka kredita preverjamo v objavljenih cenikih bank, pravila za kredite pa pri Banki Slovenije in Eko skladu; zadnjič {ddate(FIN['as_of'])}.
      Banke, ki obrestnih mer ne objavljajo, navedemo brez številk. <a href="../{COSTS}/#kredit">Obrestne mere po bankah</a></p>
  </section>
  {f'''<section class="prose" id="kdo"><h2>Kdo stoji za vodičem</h2>
    {f"<p>{esc(OWNER)}</p>" if OWNER else ""}{f"<p><b>Prihodki.</b> {esc(FUNDING)}</p>" if FUNDING else ""}
    {f'<p><b>Kontakt.</b> Napako ali posodobitev nam sporočite na <a href="mailto:{esc(CONTACT)}">{esc(CONTACT)}</a>.</p>' if CONTACT else ""}
  </section>''' if OWNER or FUNDING or CONTACT else ''}
  {'''<section class="prose" id="analitika"><h2>Analitika</h2>
    <p>Za anonimno statistiko obiskov uporabljamo Umami, brez piškotkov in brez osebnih podatkov. Vidimo le, koliko je obiskov posameznih strani in orodij, ne pa, kdo jih obišče.</p>
  </section>''' if UMAMI else ''}
  <section class="prose"><h2>Kako pogosto posodabljamo</h2>
    <p>Cene hiš preverjamo mesečno, stroške gradnje četrtletno. Zadnje preverjanje: cene hiš {esc(data['collected'])}, stroški gradnje {ddate(COST['as_of'])},
      podatki o proizvajalcih (garancija, čas gradnje, vzorčne hiše) {ddate(checked)}. Cene so informativne; pred odločitvijo preverite aktualno ponudbo pri proizvajalcu.</p>
  </section>
  <div class="actions">
    <a class="btn glow" href="{SITE}#kviz">Poiščite hišo, ki vam pristaja <span class="arrow">→</span></a>
    <a class="btn line" href="../{GUIDE}/">Cene montažnih hiš</a>
    <a class="btn line" href="../{SHOW}/">Kje si ogledati hiše</a>
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
    open(os.path.join(folder, 'index.html'), 'w', encoding='utf-8').write(gloss(card_labels(html_)))


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
write(KP, kp_hub())
for mu in KPD['municipalities']:
    write(os.path.join(KP, slugify(mu['obcina'])), kp_page(mu))
write(EKO, eko_page())
write(SHOW, show_page())
write(ABOUT, about_page())
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
    comp = sorted(((p, m) for p, m in models if m['price_eur'] and m['area_m2'] and ok(m)), key=lambda pm: pm[1]['price_cmp'])
    med_m2 = eur(round(statistics.median(m['price_cmp'] / m['area_m2'] for _, m in comp)))
    fl = lambda pm: f'<a href="{pm[1]["slug"]}/">{esc(pm[0]["name"])} {esc(pm[1]["name"])}</a> ({eur(pm[1]["price_cmp"])})'
    areas = sorted(m['area_m2'] for _, m in models if m['area_m2'])
    mid = [a for a in areas if 120 <= a < 160]
    no_slab = [p['name'] for p in provs if any('brez temeljne plošče' in m['price_stage'].lower() for m in p['models'] if m['price_eur'])]
    warranties = sorted({p['warranty_years'] for p in provs if p.get('warranty_years')})
    by = lambda key: ''.join(f'<li><a href="{p["id"]}/">{esc(p["name"])}</a>: {esc(p[key])}</li>' for p in provs if p.get(key))
    qa = [
        ('Koliko stane montažna hiša?',
         f'<p>Ceno objavlja proizvajalec za {len(priced)} tipskih montažnih hiš. Med {len(comp)} primerljivimi cenami (na ključ, s temeljno ploščo) je najcenejša {fl(comp[0])}, '
         f'najdražja {fl(comp[-1])}. Mediana je {med_m2} na m² bivalne površine. Ostalih {len(priced) - len(comp)} cen je že zmanjšanih za subvencijo ali popust '
         f'ali velja za osnovni paket, zato niso v primerjavi.</p>'
         f'<p>Cene niso neposredno primerljive, ker proizvajalci navajajo cene za različne pakete. <a href="{GUIDE}/">Primerjava cen po proizvajalcih</a></p>'),
        ('Kateri so slovenski proizvajalci montažnih hiš?',
         f'<p>V vodiču je {len(models)} tipskih hiš {len(provs)} proizvajalcev:</p><ul>' +
         ''.join(f'<li><a href="{p["id"]}/">{esc(p["name"])}</a>, {len(p["models"])} {plural(len(p["models"]), "hiša", "hiši", "hiše", "hiš")}</li>' for p in provs) + '</ul>'),
        ('Koliko časa traja gradnja montažne hiše?', f'<p>Proizvajalci, ki čas gradnje objavljajo, navajajo:</p><ul>{by("build_time")}</ul>'),
        ('Kako velike so tipske montažne hiše?',
         f'<p>Od {round(areas[0])} do {round(areas[-1])} m². Površino proizvajalci navajajo za {len(areas)} od {len(models)} hiš v vodiču; '
         f'od teh jih ima {len(mid)} med 120 in 160 m² bivalne površine.</p>'
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

locs = [SITE, SITE + GUIDE + '/', SITE + PLANS + '/', SITE + CHEAP + '/', SITE + SMALL + '/', SITE + COSTS + '/', SITE + KP + '/'] + [f"{SITE}{KP}/{slugify(mu['obcina'])}/" for mu in KPD['municipalities']] + [SITE + EKO + '/', SITE + SHOW + '/', SITE + ABOUT + '/'] + [SITE + p['id'] + '/' for p in data['providers']] + [SITE + s + '/' for s in slugs]
open('sitemap.xml', 'w', encoding='utf-8').write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
                                                  ''.join(f'  <url><loc>{l}</loc></url>\n' for l in locs) + '</urlset>\n')

assert len(slugs) == len(models) and all(os.path.isfile(l[len(SITE):] + 'index.html') for l in locs) and src.count('<li><a href="') >= len(models)
print(f'{len(slugs)} pages, {len(locs)} sitemap URLs')
