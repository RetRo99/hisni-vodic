// House comparison picks, shared by every page: "+ Primerjaj" buttons (<button class="cmp" data-slug="...">) and a bar at the
// bottom linking to /primerjava/. Up to 3 house slugs, kept in localStorage so they carry across pages.
(function () {
  var KEY = 'hise-compare', MAX = 3;
  function read() {
    try { var v = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(v) ? v.filter(function (s) { return /^[a-z0-9-]+$/.test(s); }).slice(0, MAX) : []; }
    catch (e) { return []; }
  }
  var picks = read();
  function save() { try { localStorage.setItem(KEY, JSON.stringify(picks)); } catch (e) {} }
  function track(name, data) { try { if (window.umami) window.umami.track(name, data); } catch (e) {} }

  var style = document.createElement('style');
  style.textContent =
    '.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }' +
    'button.cmp:not(.btn) { font: inherit; font-size: 13px; padding: 6px 12px; border: 0; border-radius: 999px; background: transparent; color: var(--ink); box-shadow: inset 0 0 0 1px var(--line); cursor: pointer; white-space: nowrap; }' +
    'button.cmp[aria-pressed="true"] { color: var(--glow); box-shadow: inset 0 0 0 1px var(--glow); }' +
    'button.cmp:disabled { opacity: .45; cursor: not-allowed; }' +
    '.cmp-tray { position: fixed; z-index: 30; left: 50%; bottom: 16px; transform: translateX(-50%); width: min(560px, calc(100% - 32px)); display: flex; align-items: center; gap: 12px; padding: 10px 10px 10px 20px; border-radius: 999px; background: var(--dusk); box-shadow: 0 0 0 1px var(--line), 0 12px 40px rgba(0,0,0,.45); font-size: 14px; }' +
    '.cmp-tray[hidden] { display: none; }' +
    '.cmp-tray span { flex: 1; color: var(--mist); }' +
    '.cmp-tray b { color: var(--ink); }' +
    '.cmp-tray .btn { padding: 10px 18px; }' +
    '.cmp-tray .cmp-clear { font: inherit; font-size: 13px; border: 0; background: none; color: var(--mist); cursor: pointer; padding: 8px; }' +
    'body.has-tray { padding-bottom: 84px; }' +
    '@media (max-width: 480px) { .cmp-tray { border-radius: 18px; padding-left: 16px; gap: 8px; } .cmp-tray span small { display: none; } }';
  document.head.appendChild(style);

  var tray = document.createElement('div');
  tray.className = 'cmp-tray';
  tray.setAttribute('role', 'region');
  tray.setAttribute('aria-label', 'Primerjava hiš');
  document.body.appendChild(tray);
  var onComparePage = document.body.getAttribute('data-page') === 'compare';

  function refresh() {
    var buttons = document.querySelectorAll('button.cmp[data-slug]');
    for (var i = 0; i < buttons.length; i++) {
      var b = buttons[i], on = picks.indexOf(b.getAttribute('data-slug')) >= 0;
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.textContent = on ? '✓ V primerjavi' : '+ Primerjaj';
      b.disabled = !on && picks.length >= MAX;
      b.title = b.disabled ? 'Primerjate lahko največ ' + MAX + ' hiše' : '';
    }
    var n = picks.length;
    tray.hidden = !n || onComparePage;
    document.body.classList.toggle('has-tray', !tray.hidden);
    tray.innerHTML = '<span><b>' + n + '</b> ' + (n === 1 ? 'hiša' : n === 2 ? 'hiši' : 'hiše') + ' v primerjavi' +
      (n < MAX ? '<small> · dodate lahko še ' + (MAX - n) + '</small>' : '') + '</span>' +
      '<a class="btn glow" href="/primerjava/#' + picks.join(',') + '">Primerjaj <span class="arrow">→</span></a>' +
      '<button type="button" class="cmp-clear">Počisti</button>';
  }

  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!(t instanceof Element)) return;
    var b = t.closest('button.cmp[data-slug]');
    if (b) {
      e.preventDefault();
      var s = b.getAttribute('data-slug'), on = picks.indexOf(s) >= 0;
      picks = on ? picks.filter(function (x) { return x !== s; }) : picks.concat(s).slice(0, MAX);
      save(); refresh();
      track('compare-toggle', { house: s, on: !on });
      return;
    }
    if (t.closest('.cmp-clear')) { picks = []; save(); refresh(); }
  });
  window.addEventListener('storage', function (e) { if (e.key === KEY) { picks = read(); refresh(); } });

  window.HVCompare = {
    refresh: refresh,
    get: function () { return picks.slice(); },
    set: function (list) { picks = list.slice(0, MAX); save(); refresh(); }
  };
  refresh();
})();
