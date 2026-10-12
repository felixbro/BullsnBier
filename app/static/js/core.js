/* Gemeinsame Helfer + globaler Zustand */
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const SEG = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5];
const R = {bull: 6.35, ob: 15.9, ti: 99, to: 107, di: 162, do: 170};
let ST = null;      // letzter Server-Zustand
let CFG = null;     // Einstellungen
let EVENTS = {};    // Ereignis-Schlüssel → Bezeichnung

const api = (p, m = 'GET', b) => fetch(p, {method: m, headers: {'Content-Type': 'application/json'},
  body: b ? JSON.stringify(b) : undefined}).then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e)));
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const toast = t => { const e = $('#toast'); e.textContent = t; e.classList.add('show');
  clearTimeout(e._t); e._t = setTimeout(() => e.classList.remove('show'), 2600); };

const LOCAL = (() => { try { return JSON.parse(localStorage.getItem('dc_local') || '{}'); } catch { return {}; } })();
const saveLocal = () => { try { localStorage.setItem('dc_local', JSON.stringify(LOCAL)); } catch {} };

function pcolor(i) { const c = CFG?.display?.player_colors || ['#2f80ed']; return c[(i ?? 0) % c.length]; }
function pname(i) { return ST?.game?.players?.[i]?.name ?? ST?.bulloff?.players?.[i]?.name ?? ''; }

/* Einstellungen: lokal sofort, Server gebündelt */
let _pending = null, _saveT = null;
function deepMerge(a, b) { for (const k in b) (b[k] && typeof b[k] === 'object' && !Array.isArray(b[k])) ? deepMerge(a[k] ??= {}, b[k]) : a[k] = b[k]; return a; }
function setPath(obj, path, v) { const ks = path.split('.'); let o = obj; ks.slice(0, -1).forEach(k => o = o[k] ??= {}); o[ks.at(-1)] = v; }
function getPath(obj, path) { return path.split('.').reduce((o, k) => o?.[k], obj); }
function saveSettings(patch) {
  deepMerge(CFG, structuredClone(patch));
  _pending = deepMerge(_pending || {}, patch);
  clearTimeout(_saveT); _saveT = setTimeout(() => { api('/api/settings', 'PUT', _pending); _pending = null; }, 350);
  if (typeof onSettingsChanged === 'function') onSettingsChanged();
}
function patchFor(path, v) { const p = {}; setPath(p, path, v); return p; }

/* Segment-Buttons */
function seg(el, val, fn) {
  el.querySelectorAll('button').forEach(b => { b.classList.toggle('on', b.dataset.v == val);
    b.onclick = () => { el.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); fn(b.dataset.v); }; });
}
function segHTML(opts, val) { return opts.map(([v, l]) => `<button data-v="${v}" class="${v == val ? 'on' : ''}">${l}</button>`).join(''); }

/* Tabs */
const tabHooks = {};
$$('nav button').forEach(b => b.onclick = () => {
  $$('nav button').forEach(x => x.classList.toggle('on', x === b));
  $$('.tab').forEach(t => t.classList.toggle('on', t.id === b.dataset.tab));
  tabHooks[b.dataset.tab]?.();
});
const showTab = id => $(`nav button[data-tab=${id}]`).click();
