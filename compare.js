// House comparison picks, shared by every page: "+ Primerjaj" buttons (<button class="cmp" data-slug="..." [data-name="..."]>) and a bar at the
// bottom linking to /primerjava/. Up to 3 house slugs, kept in localStorage so they carry across pages.
(function () {
  var KEY = 'hise-compare', NAMES = 'hise-compare-names', MAX = 3;
  function read() {
    try { var v = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(v) ? v.filter(function (s) { return /^[a-z0-9-]+$/.test(s); }).slice(0, MAX) : []; }
    catch (e) { return []; }
  }
  function readNames() { try { var v = JSON.parse(localStorage.getItem(NAMES) || '{}'); return v && typeof v === 'object' ? v : {}; } catch (e) { return {}; } }
  var picks = read(), names = readNames(), note = ''; // names: slug -> { n: house name, x: 1 when it has no photo }
  function save() {
    var keep = {}; picks.forEach(function (s) { if (names[s]) keep[s] = names[s]; }); names = keep;
    try { localStorage.setItem(KEY, JSON.stringify(picks)); localStorage.setItem(NAMES, JSON.stringify(names)); } catch (e) {}
  }
  function track(name, data) { try { if (window.umami) window.umami.track(name, data); } catch (e) {} }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  // the house name: data-name, else the title of the row or card the button sits in, else the page heading
  function nameOf(b) {
    var n = b.getAttribute('data-name');
    if (n) return n;
    var box = b.closest('tr, article, li, .alt, .card'), el = box && box.querySelector('h1, h2, h3, a');
    el = el || document.querySelector('h1');
    return el ? el.textContent.trim() : b.getAttribute('data-slug');
  }
  function label(s) { return (names[s] && names[s].n) || s.replace(/-/g, ' '); }

  var style = document.createElement('style');
  style.textContent =
    '.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }' +
    'button.cmp:not(.btn) { font: inherit; font-size: 13px; padding: 6px 12px; border: 0; border-radius: 999px; background: transparent; color: var(--ink); box-shadow: inset 0 0 0 1px var(--line); cursor: pointer; white-space: nowrap; }' +
    'button.cmp[aria-pressed="true"] { color: var(--glow); box-shadow: inset 0 0 0 1px var(--glow); }' +
    'button.cmp.full { color: var(--mist); }' +
    '.cmp-tray { position: fixed; z-index: 30; left: 50%; bottom: max(16px, env(safe-area-inset-bottom, 0px)); transform: translateX(-50%); width: min(600px, calc(100% - 32px)); display: flex; flex-wrap: wrap; align-items: center; gap: 10px 12px; padding: 10px 10px 10px 16px; border-radius: 22px; background: var(--dusk); box-shadow: 0 0 0 1px var(--line), 0 12px 40px rgba(0,0,0,.45); font-size: 14px; }' +
    '.cmp-tray[hidden] { display: none; }' +
    '.cmp-tray .cmp-n { flex: 1; min-width: 0; color: var(--mist); }' +
    '.cmp-tray b { color: var(--ink); }' +
    '.cmp-tray .btn { padding: 10px 18px; }' +
    '.cmp-thumbs { display: flex; gap: 8px; }' +
    '.cmp-th { position: relative; width: 52px; height: 36px; border-radius: 8px; background: var(--slate); box-shadow: inset 0 0 0 1px var(--line); }' +
    '.cmp-th img { width: 100%; height: 100%; object-fit: cover; border-radius: 8px; display: block; }' +
    '.cmp-th button { position: absolute; top: -8px; right: -8px; width: 24px; height: 24px; border-radius: 50%; border: 0; padding: 0; background: var(--ink); color: var(--night); font: 700 15px/1 var(--font-body, sans-serif); cursor: pointer; }' +
    '.cmp-th button::after { content: ""; position: absolute; inset: -10px; }' +
    '.cmp-tray .cmp-clear { font: inherit; font-size: 13px; border: 0; background: none; color: var(--mist); cursor: pointer; padding: 12px 8px; }' +
    '.cmp-msg { flex: 1 1 100%; order: -1; margin: 0; padding: 2px 4px 0; font-size: 13px; color: var(--glow); }' +
    '.cmp-msg[hidden] { display: none; }' +
    'body.has-tray { padding-bottom: 96px; }' +
    // phones: one row (thumbs, Primerjaj, Počisti), at most 64 px tall
    '@media (max-width: 480px) { .cmp-tray { padding: 8px 8px 8px 12px; gap: 6px 8px; width: calc(100% - 32px); }' +
    ' .cmp-tray .cmp-n { display: none; } .cmp-thumbs { flex: 1; min-width: 0; gap: 6px; } .cmp-th { width: 42px; height: 32px; }' +
    ' .cmp-tray .btn { padding: 10px 14px; } .cmp-tray .cmp-clear { padding: 12px 4px; } body.has-tray { padding-bottom: 84px; } }';
  document.head.appendChild(style);

  var tray = document.createElement('div');
  tray.className = 'cmp-tray';
  tray.setAttribute('role', 'region');
  tray.setAttribute('aria-label', 'Primerjava hiš');
  document.body.appendChild(tray);
  var onComparePage = document.body.getAttribute('data-page') === 'compare';

  // a bar stuck to the bottom of the screen (marked [data-sticky-bottom], e.g. the calculator total): sit the tray above it
  function place() {
    var sb = document.querySelector('[data-sticky-bottom]'), off = 0;
    if (sb && !tray.hidden) {
      var r = sb.getBoundingClientRect();
      if (r.height && r.top < innerHeight && r.bottom > innerHeight - 48) off = Math.round(innerHeight - r.top);
    }
    tray.style.bottom = off ? (off + 8) + 'px' : '';
  }
  var placing = 0;
  function schedule() { if (!placing) placing = requestAnimationFrame(function () { placing = 0; place(); }); }
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule);
  // the bar may show or hide without a scroll (e.g. toggled by an IntersectionObserver)
  var sticky = document.querySelector('[data-sticky-bottom]');
  if (sticky && window.ResizeObserver) new ResizeObserver(schedule).observe(sticky);

  function refresh() {
    var buttons = document.querySelectorAll('button.cmp[data-slug]');
    for (var i = 0; i < buttons.length; i++) {
      var b = buttons[i], s = b.getAttribute('data-slug'), on = picks.indexOf(s) >= 0;
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.setAttribute('aria-label', 'Primerjaj: ' + nameOf(b));
      b.textContent = on ? '✓ V primerjavi' : '+ Primerjaj';
      b.disabled = false;
      b.removeAttribute('title');
      b.classList.toggle('full', !on && picks.length >= MAX);
    }
    var n = picks.length;
    tray.hidden = !n || onComparePage;
    document.body.classList.toggle('has-tray', !tray.hidden);
    tray.innerHTML = '<p class="cmp-msg" role="status"' + (note ? '' : ' hidden') + '>' + esc(note) + '</p>' +
      '<div class="cmp-thumbs">' + picks.map(function (s) {
        return '<span class="cmp-th" title="' + esc(label(s)) + '">' + (names[s] && names[s].x ? '' : '<img src="/img/' + s + '.jpg" alt="" data-s="' + s + '">') +
          '<button type="button" class="cmp-rm" data-rm="' + s + '" aria-label="Odstrani iz primerjave: ' + esc(label(s)) + '">×</button></span>';
      }).join('') + '</div>' +
      '<span class="cmp-n"><b>' + n + '</b> ' + (n === 1 ? 'hiša' : n === 2 ? 'hiši' : 'hiše') + ' v primerjavi' +
      (n < MAX ? '<small> · dodate lahko še ' + (MAX - n) + '</small>' : '<small> · največ ' + MAX + '</small>') + '</span>' +
      '<a class="btn glow" href="/primerjava/#' + picks.join(',') + '">Primerjaj <span class="arrow">→</span></a>' +
      '<button type="button" class="cmp-clear">Počisti</button>';
    place();
  }

  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!(t instanceof Element)) return;
    var b = t.closest('button.cmp[data-slug]');
    if (b) {
      e.preventDefault();
      var s = b.getAttribute('data-slug'), on = picks.indexOf(s) >= 0;
      if (!on && picks.length >= MAX) {
        // full: say so in the bar (visible on touch too) instead of a disabled button with a tooltip
        note = 'Primerjava je polna (največ ' + MAX + ' hiše). Odstranite eno s × in nato dodajte ' + nameOf(b) + '.';
        refresh();
        return;
      }
      // a row or card without a photo means /img/<slug>.jpg does not exist either; skip the request
      var box = b.closest('tr, .alt');
      if (!on) names[s] = { n: nameOf(b), x: box && !box.querySelector('img') ? 1 : 0 };
      picks = on ? picks.filter(function (x) { return x !== s; }) : picks.concat(s).slice(0, MAX);
      note = '';
      save(); refresh();
      track('compare-toggle', { house: s, on: !on });
      return;
    }
    var rm = t.closest('.cmp-rm');
    if (rm) { var r = rm.getAttribute('data-rm'); picks = picks.filter(function (x) { return x !== r; }); note = ''; save(); refresh(); track('compare-toggle', { house: r, on: false }); return; }
    if (t.closest('.cmp-clear')) { picks = []; note = ''; save(); refresh(); }
  });
  tray.addEventListener('error', function (e) {
    var s = e.target.getAttribute && e.target.getAttribute('data-s');
    if (s) { e.target.remove(); names[s] = { n: label(s), x: 1 }; save(); }
  }, true);
  window.addEventListener('storage', function (e) { if (e.key === KEY || e.key === NAMES) { picks = read(); names = readNames(); refresh(); } });

  window.HVCompare = {
    refresh: refresh,
    get: function () { return picks.slice(); },
    set: function (list) { picks = list.slice(0, MAX); save(); refresh(); }
  };
  refresh();
})();
