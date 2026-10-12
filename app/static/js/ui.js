/* Bulls'n'Bier – Grundbausteine (Styleguide §2, §6, §8.4) */
var $ = function (s, c) { return (c || document).querySelector(s); };
var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
var ROOT = document.documentElement;
var ST = null, CFG = null, EVENTS = {}, PLAYERS = [];
var REDUCED = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
var PALETTE = ['#6FA8FF', '#FF7A6B', '#5FCB92', '#FFD66B', '#B79CFF', '#FFB27A', '#7FDDEB', '#FF8FC2'];

function api(p, m, b) {
  return fetch(p, {method: m || 'GET', headers: {'Content-Type': 'application/json'}, body: b ? JSON.stringify(b) : undefined})
    .then(function (r) { return r.ok ? r.json() : r.json().then(function (e) { return Promise.reject(e); }); });
}
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
var LOCAL = (function () { try { return JSON.parse(localStorage.getItem('bnb_local') || '{}'); } catch (e) { return {}; } })();
function saveLocal() { try { localStorage.setItem('bnb_local', JSON.stringify(LOCAL)); } catch (e) {} }

/* Bühne 1920 × 1080 einpassen (§2) */
var STAGE = $('#stage'), SCALE = 1;
function fit() {
  if (!STAGE) return;   // /remote hat keine Bühne
  SCALE = Math.min(innerWidth / 1920, innerHeight / 1080);
  STAGE.style.transform = 'scale(' + SCALE + ')'; STAGE.style.webkitTransform = 'scale(' + SCALE + ')';
  var ox = (innerWidth - 1920 * SCALE) / 2, oy = (innerHeight - 1080 * SCALE) / 2;
  STAGE.style.left = ox + 'px'; STAGE.style.top = oy + 'px';
  STAGE.style.setProperty('--ox', Math.ceil(ox / SCALE) + 2 + 'px'); STAGE.style.setProperty('--oy', Math.ceil(oy / SCALE) + 2 + 'px');
}
addEventListener('resize', fit); fit();

/* Effekt neu starten (§8.4) */
function play(el) { if (!el) return; el.classList.remove('play'); void el.offsetWidth; el.classList.add('play'); }

/* Zahlen zählen (B14) */
function countTo(el, to, opt) {
  if (!el) return;
  opt = opt || {};
  var dec = opt.dec || 0, pre = opt.prefix || '';
  if (typeof to !== 'number' || isNaN(to)) { el.textContent = to == null ? '' : to; el.removeAttribute('data-value'); return; }
  var cur = el.getAttribute('data-value');
  var from = opt.from != null ? opt.from : (cur != null ? parseFloat(cur) : NaN);
  if (isNaN(from)) from = to;
  var dur = opt.dur || Math.max(350, Math.min(900, 300 + Math.abs(to - from) * 4));
  var raf = window.requestAnimationFrame || function (f) { return setTimeout(function () { f(Date.now()); }, 16); };
  var caf = window.cancelAnimationFrame || clearTimeout;
  if (el.__count) caf(el.__count);
  if (el.__wait) clearTimeout(el.__wait);
  el.setAttribute('data-value', to);
  var go = function () {
    if ((REDUCED && !ROOT.classList.contains('force-motion')) || from === to) { el.textContent = pre + to.toFixed(dec); return; }
    var t0 = null;
    (function step(t) { if (t0 === null) t0 = t; var k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = pre + (from + (to - from) * e).toFixed(dec); if (k < 1) el.__count = raf(step); else el.__count = null; })(performance.now());
  };
  if (opt.delay) el.__wait = setTimeout(go, opt.delay); else go();
}

/* Segment mit gleitender Markierung (§6.2) */
function segment(g, val, fn) {
  var btns = $$('button', g), thumb = $('.seg__thumb', g);
  if (!thumb) { thumb = document.createElement('span'); thumb.className = 'seg__thumb'; g.insertBefore(thumb, g.firstChild); g.classList.add('js'); }
  g.style.setProperty('--n', btns.length);
  function set(i) { btns.forEach(function (x, k) { x.classList.toggle('on', k === i); x.setAttribute('aria-pressed', k === i ? 'true' : 'false'); }); g.style.setProperty('--i', i); }
  var start = 0;
  btns.forEach(function (b, k) { if (String(b.dataset.v) === String(val)) start = k; b.type = 'button';
    b.onclick = function () { set(k); if (fn) fn(b.dataset.v, k); }; });
  set(start);
}
function segHTML(opts) { return opts.map(function (o) { return '<button type="button" data-v="' + esc(o[0]) + '">' + esc(o[1]) + '</button>'; }).join(''); }

/* Avatar: Silhouette auf Spielerfarbe + DiceBear-Bild darüber (§6.3) */
var SIL = '<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="26" r="11" fill="#202020" fill-opacity=".55"></circle>' +
  '<path d="M10 64c1.5-13 10.5-21 22-21s20.5 8 22 21z" fill="#202020" fill-opacity=".55"></path></svg>';
function avatarURL(p) {
  p = p || {};
  var style = p.av_style || (CFG && CFG.display.avatar_style) || 'notionists';
  return '/api/avatar?seed=' + encodeURIComponent(p.seed || p.name || '') + '&style=' + style + '&accent=' + encodeURIComponent(p.av_accent || 'ci');
}
/* Avatar: Grund = Spielerfarbe, CI-Farbe oder hell (av_bg), Motiv = DiceBear-SVG darüber */
var AV_OK = {};   // schon geladene Avatar-URLs → beim Neuzeichnen keine Silhouette aufblitzen lassen
function avLoaded(img) { AV_OK[img.getAttribute('src')] = 1; if (img.parentNode) img.parentNode.classList.add('ok'); }
function avatar(p, size, ring, cls) {
  p = p || {};
  var seed = p.seed || p.name || '', bg = p.av_bg || 'player', url = seed ? avatarURL(p) : '', ok = url && AV_OK[url];
  var img = url ? '<img src="' + url + '" width="' + size + '" height="' + size + '" alt="" decoding="' + (ok ? 'sync' : 'async') + '" onload="avLoaded(this)" onerror="this.parentNode&&this.parentNode.removeChild(this)">' : '';
  var bgs = bg === 'player' ? '' : bg === 'none' ? '; background:rgba(255,255,255,.85)' : '; background:var(--grad-avatar-light), ' + bg;
  return '<span class="avatar' + (ok ? ' ok' : '') + (ring ? ' ring' : '') + (cls ? ' ' + cls : '') + '" style="--pc:' + (p.color || PALETTE[0]) + '; --av:' + size + 'px' + bgs + '">' + (ok ? '' : SIL) + img + '</span>';
}
function preloadAvatars(ps) { (ps || []).forEach(function (p) { var i = new Image(), u = avatarURL(p); i.onload = function () { AV_OK[u] = 1; }; i.src = u; }); }

/* Logo-Zeichen (§6.3) */
function logo(s, dark) {
  var foam = '<circle cx="30" cy="34" r="15"></circle><circle cx="51" cy="25" r="18"></circle><circle cx="75" cy="27" r="16"></circle>' +
    '<circle cx="93" cy="38" r="12"></circle><rect x="18" y="34" width="84" height="12" rx="6"></rect><circle cx="40" cy="48" r="6"></circle><circle cx="72" cy="50" r="7"></circle>';
  return '<svg width="' + s + '" height="' + s + '" viewBox="0 0 120 120" role="img" aria-label="Bulls’n’Bier Logo" style="display:block">' +
    '<circle cx="60" cy="68" r="46" fill="#202020"' + (dark ? ' stroke="#EDF0F1" stroke-width="3"' : '') + '></circle>' +
    '<circle cx="60" cy="68" r="33" fill="#3DBB7A"></circle><circle cx="60" cy="68" r="22" fill="#202020"></circle><circle cx="60" cy="68" r="11" fill="#FF6B5E"></circle>' +
    '<g fill="#202020" stroke="#202020" stroke-width="6" stroke-linejoin="round">' + foam + '</g><g fill="#DDF96A">' + foam + '</g>' +
    '<circle cx="44" cy="22" r="4" fill="#FFFFFF" fill-opacity=".75"></circle>' +
    (s >= 24 ? '<circle cx="99" cy="14" r="4" fill="#DDF96A" stroke="#202020" stroke-width="2.5"></circle><circle cx="108" cy="25" r="2.5" fill="#DDF96A" stroke="#202020" stroke-width="2"></circle>' : '') +
    '</svg>';
}
var DART_ICO = '<i><svg width="18" height="44" viewBox="0 0 18 44" aria-hidden="true"><path d="M9 0v30" stroke="#202020" stroke-width="2.5"></path><path d="M9 28l-7 9h14z" fill="#DDF96A" stroke="#202020" stroke-width="2" stroke-linejoin="round"></path><path d="M9 34v10" stroke="#202020" stroke-width="2"></path></svg></i>';
var PLAY_ICO = '<svg width="10" height="12" viewBox="0 0 10 12" aria-hidden="true"><path d="M1 1l8 5-8 5z" fill="currentColor"></path></svg>';

/* Toasts C1/C2 – max. 3, neuester oben */
var ICO = {
  info: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#202020" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 11v6M12 7.5v.5"></path></svg>',
  ok: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#202020" stroke-width="2" aria-hidden="true"><path d="M5 12l5 5 9-10"></path></svg>',
  warn: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#202020" stroke-width="2" aria-hidden="true"><path d="M12 4l9 16H3z"></path><path d="M12 10v4M12 17v.5"></path></svg>'
};
function toast(title, sub, kind, key) {
  kind = kind || 'info';
  var box = $('#toasts'), stay = kind === 'warn';
  if (key) { var old = $('[data-key="' + key + '"]', box); if (old) old.remove(); }
  var t = document.createElement('div');
  t.className = 'toast ' + kind + (stay ? ' stay' : '');
  if (key) t.setAttribute('data-key', key);
  t.innerHTML = '<span class="ico">' + ICO[kind] + '</span><span><b style="font-weight:500">' + esc(title) + '</b>' + (sub ? '<br><small>' + esc(sub) + '</small>' : '') + '</span>' +
    (stay ? '<button class="x" type="button" aria-label="Schließen">×</button>' : '');
  box.insertBefore(t, box.firstChild);
  while (box.children.length > 3) box.removeChild(box.lastChild);
  play(t);
  if (stay) $('.x', t).onclick = function () { t.remove(); };
  else setTimeout(function () { t.remove(); }, 3600);
  $('#live').textContent = title + (sub ? ', ' + sub : '');
  return t;
}
function clearToast(key) { var t = $('#toasts [data-key="' + key + '"]'); if (t) t.remove(); }

/* Navigation */
var PAGE = 'start', pageHooks = {};
function showPage(id) {
  if (!$('#p-' + id)) id = 'start';
  PAGE = id;
  $$('.page').forEach(function (p) { p.classList.toggle('on', p.id === 'p-' + id); });
  $$('#nav a').forEach(function (a) { a.classList.toggle('on', a.dataset.page === id); });
  $('#ctaNew').classList.toggle('hidden', id === 'live' || id === 'new');
  if (location.hash !== '#' + id) history.replaceState(null, '', '#' + id);
  if (pageHooks[id]) pageHooks[id]();
  if (typeof updEnd === 'function') updEnd(ST);   // Exit-Knopf nur auf Live
}
addEventListener('hashchange', function () { var h = location.hash.slice(1); if (h && h !== PAGE) showPage(h); });
document.addEventListener('click', function (e) {
  var a = e.target.closest && e.target.closest('[data-page]');
  if (a) { e.preventDefault(); showPage(a.dataset.page); }
});

function pcolorOf(i) { var g = ST && ST.game; var p = g ? g.players[i] : (ST && ST.bulloff ? ST.bulloff.players[i] : null); return p && p.color || PALETTE[(i || 0) % 8]; }
function pOf(i) { var g = ST && ST.game; return g ? g.players[i] : (ST && ST.bulloff ? ST.bulloff.players[i] : null); }
function hostPlayer() { var h = CFG && CFG.display.host; return PLAYERS.filter(function (p) { return p.id === h; })[0] || PLAYERS[0]; }
function saveSettings(patch) {
  deepMerge(CFG, JSON.parse(JSON.stringify(patch)));
  saveSettings.p = deepMerge(saveSettings.p || {}, patch);
  clearTimeout(saveSettings.t);
  saveSettings.t = setTimeout(function () { api('/api/settings', 'PUT', saveSettings.p); saveSettings.p = null; }, 350);
  applyDisplay();
}
function deepMerge(a, b) { for (var k in b) { if (b[k] && typeof b[k] === 'object' && !Array.isArray(b[k])) { a[k] = a[k] || {}; deepMerge(a[k], b[k]); } else a[k] = b[k]; } return a; }
function applyDisplay() {
  if (!CFG) return;
  if (CFG.display.theme === 'night') ROOT.setAttribute('data-theme', 'night'); else ROOT.removeAttribute('data-theme');
  ROOT.classList.toggle('force-motion', CFG.display.intensity === 'ballern');
  var h = hostPlayer(); if ($('#hostAvatar')) $('#hostAvatar').innerHTML = h ? avatar(h, 44) : avatar({color: PALETTE[0]}, 44);
}
