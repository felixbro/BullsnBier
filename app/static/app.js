const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const SEG = [20,1,18,4,13,6,10,15,2,17,3,19,7,16,8,11,14,9,12,5];
const R = {bull:6.35, ob:15.9, ti:99, to:107, di:162, do:170};
let ST = null, sel = null, mult = 'S', voice = localStorage.getItem('voice') !== '0';

const api = (p, m = 'GET', b) => fetch(p, {method: m, headers: {'Content-Type': 'application/json'},
  body: b ? JSON.stringify(b) : undefined}).then(r => r.json());
const toast = t => { const e = $('#toast'); e.textContent = t; e.classList.add('show');
  clearTimeout(e._t); e._t = setTimeout(() => e.classList.remove('show'), 2200); };

/* ---------- Caller ---------- */
let CFG = null;                       // Server-Einstellungen
const LOCAL = (() => { try { return JSON.parse(localStorage.getItem('dc_local') || '{}'); } catch { return {}; } })();
const saveLocal = () => { try { localStorage.setItem('dc_local', JSON.stringify(LOCAL)); } catch {} };
// LOCAL.muted: dieses Gerät stumm · LOCAL.voice: Stimmen-Name auf diesem Gerät
const speechOK = 'speechSynthesis' in window;
let queue = [];

function voices() { return speechOK ? speechSynthesis.getVoices() : []; }
function pickVoice() {
  const lang = CFG?.caller.lang || 'de', vs = voices();
  return vs.find(v => v.name === LOCAL.voice) || vs.find(v => v.lang.replace('_', '-').toLowerCase().startsWith(lang)) || null;
}
function speak(text, force) {
  if (!speechOK || !text || !CFG) return;
  if (!force && (!CFG.caller.enabled || LOCAL.muted)) return;
  const u = new SpeechSynthesisUtterance(text), v = pickVoice(), c = CFG.caller;
  if (v) { u.voice = v; u.lang = v.lang; } else u.lang = c.lang === 'de' ? 'de-DE' : 'en-GB';
  u.rate = +c.rate; u.pitch = +c.pitch; u.volume = +c.volume;
  speechSynthesis.speak(u);
}
function fill(t, vars) { return (t || '').replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? ''); }
function spokenName(i) {
  const p = ST?.game?.players?.[i]; if (!p) return '';
  return (p.spoken || '').trim() || p.name;
}
function dartText(name, T) {
  if (name === 'BULL') return T.bull; if (name === '25') return T.outer; if (name === 'MISS') return T.miss;
  return fill({S: T.single, D: T.double, T: T.triple}[name[0]], {n: name.slice(1)});
}
function callText(c) {
  const C = CFG.caller, T = CFG.texts[C.lang] || CFG.texts.de, name = spokenName(c.p);
  switch (c.k) {
    case 'start': return C.say_start ? fill(T.start, {name}) : '';
    case 'dart': return C.say_dart ? dartText(c.d, T) : '';
    case 'turn': if (!C.say_turn) return '';
      return c.points === 180 ? T.t180 : c.points === 0 ? T.noscore : fill(T.turn, {points: c.points});
    case 'bust': return C.say_bust ? T.bust : '';
    case 'leg': return C.say_leg ? fill(T.leg, {name}) : '';
    case 'match': return C.say_match ? fill(T.match, {name}) : '';
    case 'corrected': return C.say_correction ? fill(T.corrected, {dart: dartText(c.d, T)}) : '';
    case 'takeout': return C.say_takeout ? T.takeout : '';
    case 'next': {
      const rem = c.score != null && (C.say_remaining === 'always' || (C.say_remaining === 'finish' && c.finish));
      if (rem) return fill(C.say_next ? T.next_remaining : T.remaining, {name, score: c.score});
      return C.say_next && (ST?.game?.players?.length || 0) > 1 ? fill(T.next, {name}) : '';
    }
  }
  return '';
}
function announce(calls) {
  if (!calls?.length || !CFG) return;
  const txt = calls.map(callText).filter(Boolean);
  if (!txt.length) return;
  // Neuer Wurf unterbricht alte Ansage-Reste nur bei Dart-Ereignissen
  if (calls[0].k === 'dart' && speechOK) speechSynthesis.cancel();
  txt.forEach(t => speak(t));
}
function muteIcon() { $('#voice').textContent = (!CFG?.caller.enabled || LOCAL.muted) ? '🔇' : '🔊'; }
$('#voice').onclick = () => { LOCAL.muted = !LOCAL.muted; saveLocal(); muteIcon();
  if (!LOCAL.muted) speak(CFG?.caller.lang === 'en' ? 'Caller on' : 'Ansage an'); else speechSynthesis?.cancel(); };
if (speechOK) speechSynthesis.onvoiceschanged = () => { if ($('#settings').classList.contains('on')) renderVoices(); };

/* ---------- Tabs ---------- */
$$('nav button').forEach(b => b.onclick = () => {
  $$('nav button').forEach(x => x.classList.toggle('on', x === b));
  $$('.tab').forEach(t => t.classList.toggle('on', t.id === b.dataset.tab));
  if (b.dataset.tab === 'stats') loadStats();
  if (b.dataset.tab === 'setup') loadSetup();
  if (b.dataset.tab === 'cams') loadCams();
  if (b.dataset.tab === 'settings') loadSettings();
});

/* ---------- Board ---------- */
function score(x, y) {
  const r = Math.hypot(x, y);
  if (r <= R.bull) return 'BULL'; if (r <= R.ob) return '25'; if (r > R.do) return 'MISS';
  const a = ((Math.atan2(x, y) * 180 / Math.PI) + 360) % 360;
  const s = SEG[Math.floor(((a + 9) % 360) / 18)];
  if (r >= R.ti && r <= R.to) return 'T' + s; if (r >= R.di) return 'D' + s; return 'S' + s;
}
function arc(r1, r2, a1, a2) {
  const p = (r, a) => [r * Math.sin(a), -r * Math.cos(a)];
  const [x1, y1] = p(r2, a1), [x2, y2] = p(r2, a2), [x3, y3] = p(r1, a2), [x4, y4] = p(r1, a1);
  return `M${x1},${y1}A${r2},${r2} 0 0 1 ${x2},${y2}L${x3},${y3}A${r1},${r1} 0 0 0 ${x4},${y4}Z`;
}
function drawBoard() {
  let s = `<circle r="200" fill="#111"/>`;
  SEG.forEach((n, i) => {
    const a1 = (i * 18 - 9) * Math.PI / 180, a2 = (i * 18 + 9) * Math.PI / 180, even = i % 2 === 0;
    const base = even ? '#15181a' : '#efe6cf', ring = even ? '#e2412f' : '#1f9d5c';
    s += `<path d="${arc(R.ob, R.ti, a1, a2)}" fill="${base}"/><path d="${arc(R.ti, R.to, a1, a2)}" fill="${ring}"/>`;
    s += `<path d="${arc(R.to, R.di, a1, a2)}" fill="${base}"/><path d="${arc(R.di, R.do, a1, a2)}" fill="${ring}"/>`;
    const m = i * 18 * Math.PI / 180;
    s += `<text x="${186 * Math.sin(m)}" y="${-186 * Math.cos(m) + 6}" fill="#eef1f2" font-size="17" font-weight="700" text-anchor="middle">${n}</text>`;
  });
  s += `<circle r="${R.ob}" fill="#1f9d5c"/><circle r="${R.bull}" fill="#e2412f"/><g id="hits"></g><text id="hover" text-anchor="middle" font-size="16" font-weight="800" fill="#fff" stroke="#000" stroke-width="3" paint-order="stroke" pointer-events="none"></text>`;
  $('#board').innerHTML = s;
}
drawBoard();
function boardXY(e) {
  const svg = $('#board'), pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
  const p = pt.matrixTransform(svg.getScreenCTM().inverse()); return [p.x, -p.y];
}
$('#board').addEventListener('click', e => {
  const [x, y] = boardXY(e), name = score(x, y);
  if (sel !== null) { api('/api/edit', 'POST', {i: sel, name, pos: [x, y]}); sel = null; return; }
  if (ST?.sim) api('/api/sim/throw', 'POST', {x, y});        // Simulator: exakter Treffer
  else api('/api/dart', 'POST', {name, pos: [x, y]});        // Live: manueller Eintrag
});
$('#board').addEventListener('mousemove', e => {
  const [x, y] = boardXY(e), h = $('#hover'); if (!h) return;
  h.textContent = score(x, y); h.setAttribute('x', x); h.setAttribute('y', -y - 10);
});
$('#board').addEventListener('mouseleave', () => { const h = $('#hover'); if (h) h.textContent = ''; });

/* ---------- Render ---------- */
function render(m) {
  ST = m;
  $('#dot').classList.toggle('ok', !!(m.sim || m.detector?.running));
  $('#sim').classList.toggle('hidden', !m.sim);
  const g = m.game, sb = $('#scoreboard');
  if (!g) { sb.innerHTML = `<div class="pl"><div class="nm">Kein Spiel</div><div class="meta">Tab „Neu“ → Spiel starten. Freie Würfe werden trotzdem erkannt.</div></div>`;
    $('#turn').innerHTML = ''; $('#checkout').textContent = ''; return; }
  const s = g.state;
  sb.innerHTML = g.players.map((p, i) => {
    const ps = s.players[i] || {}, cur = i === s.current && s.winner === null;
    let main = '', extra = '';
    if (g.mode === 'x01') { main = cur && s.live_score != null ? s.live_score : ps.score;
      extra = `Ø ${avg(g, i)}`; }
    if (g.mode === 'cricket') { main = ps.points;
      extra = `<div class="cr">${Object.entries(ps.marks).sort((a, b) => b[0] - a[0]).map(([k, v]) =>
        `<div class="${v >= 3 ? 'c3' : ''}"><b>${k === '25' ? 'B' : k}</b>${['·', '/', 'X', 'Ⓧ'][v]}</div>`).join('')}</div>`; }
    if (g.mode === 'atc') main = ps.target > 20 ? 'Bull' : ps.target;
    return `<div class="pl ${cur ? 'cur' : ''}"><div class="nm"><span>${esc(p.name)}</span><span class="legs">${'●'.repeat(s.legs_won[i])}</span></div>
      <div class="sc">${main}</div><div class="meta">${extra}</div></div>`;
  }).join('');
  const darts = s.turn?.darts || [];
  const last = m.await_takeout && s.last_turn ? s.last_turn.darts : darts;
  const show = m.await_takeout ? last : darts;
  let html = '';
  for (let i = 0; i < 3; i++) { const d = show[i];
    html += `<div class="d ${d ? '' : 'empty'} ${sel === i ? 'sel' : ''}" data-i="${i}">${d ? d.name : '–'}</div>`; }
  html += `<div class="d sum">${show.reduce((a, d) => a + d.value, 0)}</div>`;
  $('#turn').innerHTML = html;
  $$('#turn .d[data-i]').forEach(e => e.onclick = () => {
    const i = +e.dataset.i; if (!show[i]) return;
    sel = sel === i ? null : i; render(ST); if (sel !== null) toast('Aufs Board tippen zum Korrigieren'); });
  $('#checkout').textContent = s.checkout ? s.checkout.join('  ·  ') : '';
  // Treffer aufs Board
  const hits = $('#hits'); if (hits) hits.innerHTML = show.map((d, i) => d.pos ?
    `<circle class="hit ${sel === i ? 'sel' : ''}" cx="${d.pos[0]}" cy="${-d.pos[1]}" r="5"/>` : '').join('');
  const b = $('#banner'); b.className = 'banner';
  if (s.winner !== null) { b.textContent = `🏆 ${g.players[s.winner].name}`; b.classList.add('show', 'win'); }
  else if (m.await_takeout && s.last_turn?.bust) { b.textContent = 'BUST'; b.classList.add('show', 'bust'); }
  $('#btnNext').textContent = m.await_takeout ? 'Pfeile gezogen ⟶' : 'Aufnahme beenden ⟶';
}
function avg(g, i) {
  let pts = 0, n = 0;
  (g.turns || []).filter(t => t.p === i).forEach(t => { n += t.darts.length; pts += t.pts || 0; });
  return n ? (3 * pts / n).toFixed(1) : '–';
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

/* ---------- WebSocket ---------- */
function connect() {
  const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
  ws.onmessage = e => { const m = JSON.parse(e.data);
    if (m.type === 'state') render(m);
    if (m.type === 'settings') { CFG = m.settings; muteIcon(); }
    if (m.type === 'warn') toast(m.msg);
    if (m.type === 'dart_free') toast(m.score.name);
    announce(m.calls); };
  ws.onopen = () => $('#dot').classList.add('ok');
  ws.onclose = () => { $('#dot').classList.remove('ok'); setTimeout(connect, 1500); };
}
api('/api/settings').then(s => { CFG = s; muteIcon(); connect(); });

/* ---------- Aktionen ---------- */
$('#btnNext').onclick = () => { sel = null; api('/api/next', 'POST'); };
$('#btnUndo').onclick = () => { sel = null; api('/api/undo', 'POST'); };
$('#btnMiss').onclick = () => api('/api/dart', 'POST', {name: 'MISS'});
$$('.mult button').forEach(b => b.onclick = () => { mult = b.dataset.m;
  $$('.mult button').forEach(x => x.classList.toggle('on', x === b)); });
$('#nums').innerHTML = [...Array(20)].map((_, i) => `<button>${i + 1}</button>`).join('') +
  `<button data-n="25">25</button><button data-n="BULL">Bull</button>`;
$$('#nums button').forEach(b => b.onclick = () => {
  const name = b.dataset.n || mult + b.textContent;
  if (sel !== null) { api('/api/edit', 'POST', {i: sel, name}); sel = null; } else api('/api/dart', 'POST', {name}); });
$$('#sim button[data-aim]').forEach(b => b.onclick = () => api('/api/sim/throw', 'POST', {aim: b.dataset.aim}));
$('#simOut').onclick = () => api('/api/sim/takeout', 'POST');
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('#btnNext').click(); }
  if (e.key === 'Backspace') $('#btnUndo').click();
});

/* ---------- Setup ---------- */
let picked = [];
function segPick(id) { $$(`#${id} button`).forEach(b => b.onclick = () => {
  $$(`#${id} button`).forEach(x => x.classList.toggle('on', x === b));
  if (id === 'mode') $('#x01opts').classList.toggle('hidden', b.dataset.v !== 'x01'); }); }
['mode', 'start', 'in', 'out', 'legs'].forEach(segPick);
const segVal = id => $(`#${id} button.on`).dataset.v;
async function loadSetup() {
  const ps = await api('/api/players');
  const all = [...ps, ...picked.filter(p => typeof p === 'string').map(n => ({id: n, name: n}))];
  $('#pick').innerHTML = all.map(p => { const k = picked.indexOf(p.id);
    return `<button data-id="${p.id}" class="${k >= 0 ? 'on' : ''}"><span class="n">${k >= 0 ? k + 1 : ''}</span> ${esc(p.name)}</button>`; }).join('')
    || '<span class="hint">Noch keine Spieler – unter „Statistik“ anlegen oder Gast hinzufügen.</span>';
  $$('#pick button').forEach(b => b.onclick = () => {
    const id = isNaN(+b.dataset.id) ? b.dataset.id : +b.dataset.id, k = picked.indexOf(id);
    k >= 0 ? picked.splice(k, 1) : picked.push(id); loadSetup(); });
}
$('#addGuest').onclick = () => { const n = $('#guest').value.trim(); if (n && !picked.includes(n)) picked.push(n); $('#guest').value = ''; loadSetup(); };
$('#startGame').onclick = async () => {
  if (!picked.length) return toast('Spieler wählen');
  await api('/api/game', 'POST', {mode: segVal('mode'), players: picked,
    opts: {start: +segVal('start'), in: segVal('in'), out: segVal('out'), legs: +segVal('legs')}});
  $('nav button[data-tab=play]').click();
};

/* ---------- Statistik ---------- */
let statPid = null;
async function loadStats() {
  const ps = await api('/api/players');
  $('#plist').innerHTML = ps.map(p => `<button data-id="${p.id}" class="${p.id === statPid ? 'on' : ''}">${esc(p.name)}</button>`).join('');
  $$('#plist button').forEach(b => b.onclick = () => { statPid = +b.dataset.id; loadStats(); });
  if (statPid) {
    const s = await api('/api/stats/' + statPid), name = ps.find(p => p.id === statPid)?.name;
    const k = (v, l) => `<div class="kpi"><b>${v ?? 0}</b><span>${l}</span></div>`;
    const pl = ps.find(p => p.id === statPid);
    $('#pstats').innerHTML = `<h2>${esc(name)} <button id="delP" style="float:right">Löschen</button></h2>
      <div class="row" style="margin-bottom:14px"><input id="pName" value="${esc(pl.name)}" placeholder="Name">
        <input id="pSpoken" value="${esc(pl.spoken)}" placeholder="Aussprache (optional, z. B. Ma-rei)">
        <button id="pHear">▶</button><button id="pSave">Speichern</button></div><div class="kpis">
      ${k(s.avg3, '3-Dart-Ø')}${k(s.first9, 'First 9 Ø')}${k(s.co_pct + '%', 'Checkout-Quote')}${k(s.best_co, 'Höchstes Finish')}
      ${k(s.t180, '180er')}${k(s.t140, '140+')}${k(s.t100, '100+')}${k(s.all_wins + '/' + s.all_games, 'Siege/Spiele')}</div>
      ${spark(s.history.map(h => h.avg || 0))}`;
    $('#pHear').onclick = () => { const T = CFG.texts[CFG.caller.lang];
      speak(fill(T.next, {name: $('#pSpoken').value.trim() || $('#pName').value.trim()}), true); };
    $('#pSave').onclick = async () => { await api('/api/players/' + statPid, 'PUT',
      {name: $('#pName').value, spoken: $('#pSpoken').value}); toast('Gespeichert'); loadStats(); };
    $('#delP').onclick = async () => { if (confirm('Spieler löschen?')) { await api('/api/players/' + statPid, 'DELETE'); statPid = null; loadStats(); } };
  } else $('#pstats').innerHTML = '<span class="hint">Spieler antippen für Statistik.</span>';
  const gs = await api('/api/games');
  $('#glist').innerHTML = gs.map(g => `<div class="glist"><div><span>${new Date(g.ts * 1000).toLocaleString('de-DE')} · ${g.mode.toUpperCase()} · ${g.players.map(esc).join(', ')}</span><b>${esc(g.winner || '')}</b></div></div>`).join('') || '<span class="hint">Noch keine Spiele.</span>';
}
function spark(v) {
  if (v.length < 2) return '';
  const mx = Math.max(...v, 1), mn = Math.min(...v, 0), w = 300, h = 80;
  const pts = v.map((y, i) => `${i * w / (v.length - 1)},${h - 6 - (y - mn) / (mx - mn || 1) * (h - 12)}`).join(' ');
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="#f2c14e" stroke-width="2" vector-effect="non-scaling-stroke"/></svg><div class="hint">3-Dart-Ø der letzten ${v.length} Spiele</div>`;
}
$('#addPlayer').onclick = async () => { const n = $('#newPlayer').value.trim(); if (!n) return;
  await api('/api/players', 'POST', {name: n}); $('#newPlayer').value = ''; loadStats(); };

/* ---------- Kameras ---------- */
const CALK = ['20', '6', '3', '11'];
async function loadCams() {
  const info = ST?.detector;
  if (!info?.running) { $('#camlist').innerHTML = '<div class="card hint">Simulator-Modus oder Erkennung läuft nicht.</div>'; return; }
  $('#fps').textContent = `${info.fps} fps`;
  $('#detPause').textContent = info.paused ? 'Erkennung fortsetzen' : 'Erkennung pausieren';
  const cal = await api('/api/cal');
  $('#camlist').innerHTML = info.cams.map(c => `
    <div class="cam" data-id="${c.id}">
      <div class="row"><b>Kamera ${+c.id + 1}</b><span class="hint">${esc(c.src)}</span>
        <span class="badge ${c.ok ? 'ok' : ''}">${c.ok ? 'verbunden' : 'offline'}</span>
        <span class="badge ${c.cal ? 'ok' : ''}">${c.cal ? 'kalibriert' : 'nicht kalibriert'}</span></div>
      <div class="bar">${CALK.map((k, i) => `<button data-k="${k}" class="${i === 0 ? 'on' : ''}">Punkt ${k}</button>`).join('')}
        <button class="live">Live</button><button class="save big" style="width:auto">Speichern</button></div>
      <div class="img"><img src="/api/cam/${c.id}.jpg?overlay=1&t=${Date.now()}"></div>
    </div>`).join('');
  $$('.cam').forEach(el => {
    const id = el.dataset.id, pts = {...(cal[id] || {})}; let cur = '20', live = false;
    const img = el.querySelector('img'), box = el.querySelector('.img');
    const marks = () => { box.querySelectorAll('.mk').forEach(m => m.remove());
      if (!img.naturalWidth) return;
      Object.entries(pts).forEach(([k, p]) => { const m = document.createElement('div'); m.className = 'mk';
        m.style.left = (p[0] / img.naturalWidth * 100) + '%'; m.style.top = (p[1] / img.naturalHeight * 100) + '%';
        m.textContent = k; box.appendChild(m); }); };
    img.onload = marks;
    el.querySelectorAll('[data-k]').forEach(b => b.onclick = () => { cur = b.dataset.k;
      el.querySelectorAll('[data-k]').forEach(x => x.classList.toggle('on', x === b)); });
    box.onclick = e => { const r = img.getBoundingClientRect();
      pts[cur] = [(e.clientX - r.left) / r.width * img.naturalWidth, (e.clientY - r.top) / r.height * img.naturalHeight];
      marks(); const n = CALK[(CALK.indexOf(cur) + 1) % 4]; el.querySelector(`[data-k="${n}"]`).click(); };
    el.querySelector('.save').onclick = async () => {
      if (Object.keys(pts).length < 4) return toast('Alle 4 Punkte setzen');
      await api('/api/cal/' + id, 'POST', {points: pts}); toast('Gespeichert');
      img.src = `/api/cam/${id}.jpg?overlay=1&t=${Date.now()}`; };
    el.querySelector('.live').onclick = b => { live = !live; b.target.classList.toggle('on', live);
      img.src = live ? `/api/cam/${id}/stream?overlay=1` : `/api/cam/${id}.jpg?overlay=1&t=${Date.now()}`; };
  });
}
$('#detPause').onclick = async () => { await api('/api/detect/pause', 'POST', {paused: !ST?.detector?.paused}); setTimeout(loadCams, 300); };
$('#detReset').onclick = () => api('/api/detect/reset', 'POST').then(() => toast('Referenz gesetzt'));

/* ---------- Einstellungen ---------- */
const TEXT_LABELS = {start: 'Spielstart', single: 'Single', double: 'Double', triple: 'Triple', bull: 'Bullseye (50)',
  outer: 'Bull (25)', miss: 'Daneben', turn: 'Aufnahme-Punkte', noscore: '0 Punkte', t180: '180', bust: 'Überworfen',
  next: 'Nächster Spieler', remaining: 'Rest (ohne „dran“)', next_remaining: 'Nächster Spieler + Rest',
  leg: 'Leg gewonnen', match: 'Spiel gewonnen', corrected: 'Korrektur', takeout: 'Pfeile ziehen'};
let saveT = null;
function saveSettings(patch) {
  // lokale Kopie sofort aktualisieren, Server gebündelt
  const merge = (a, b) => { for (const k in b) (b[k] && typeof b[k] === 'object' && !Array.isArray(b[k])) ? merge(a[k] ??= {}, b[k]) : a[k] = b[k]; };
  merge(CFG, patch); muteIcon();
  saveLocal.pending = saveLocal.pending || {}; merge(saveLocal.pending, patch);
  clearTimeout(saveT); saveT = setTimeout(() => { api('/api/settings', 'PUT', saveLocal.pending); saveLocal.pending = null; }, 400);
}
function renderVoices() {
  const lang = CFG.caller.lang, vs = voices();
  const match = vs.filter(v => v.lang.toLowerCase().startsWith(lang)), other = vs.filter(v => !match.includes(v));
  const cur = pickVoice()?.name;
  $('#voiceSel').innerHTML = '<option value="">Automatisch</option>' +
    [...match, ...other].map(v => `<option ${v.name === LOCAL.voice ? 'selected' : ''}>${esc(v.name)}</option>`).join('');
  $('#voiceHint').textContent = !speechOK ? 'Dieser Browser hat keine Sprachausgabe.' :
    !vs.length ? 'Keine Stimmen gefunden – unter Linux: sudo apt install speech-dispatcher espeak-ng (oder Tablet/Handy als Anzeige nutzen).' :
    !match.length ? `Keine ${lang === 'de' ? 'deutsche' : 'englische'} Stimme installiert – es wird ${cur || 'die Standardstimme'} verwendet.` :
    `${match.length} passende Stimme(n). Aktiv: ${cur}`;
}
function loadSettings() {
  const C = CFG.caller;
  $$('#settings [data-c]').forEach(el => {
    const k = el.dataset.c;
    if (el.type === 'checkbox') { el.checked = !!C[k]; el.onchange = () => saveSettings({caller: {[k]: el.checked}}); }
    else { el.value = C[k]; const o = el.nextElementSibling; o.textContent = (+C[k]).toFixed(2);
      el.oninput = () => { o.textContent = (+el.value).toFixed(2); saveSettings({caller: {[k]: +el.value}}); }; }
  });
  $$('#settings [data-g]').forEach(el => { el.checked = !!CFG.game[el.dataset.g];
    el.onchange = () => saveSettings({game: {[el.dataset.g]: el.checked}}); });
  $('#localMute').checked = !!LOCAL.muted;
  $('#localMute').onchange = e => { LOCAL.muted = e.target.checked; saveLocal(); muteIcon(); };
  const seg = (id, val, fn) => $$(`#${id} button`).forEach(b => { b.classList.toggle('on', b.dataset.v === val);
    b.onclick = () => { $$(`#${id} button`).forEach(x => x.classList.toggle('on', x === b)); fn(b.dataset.v); }; });
  seg('lang', C.lang, v => { saveSettings({caller: {lang: v}}); LOCAL.voice = ''; saveLocal(); renderVoices(); renderTexts(); });
  seg('remain', C.say_remaining, v => saveSettings({caller: {say_remaining: v}}));
  $('#voiceSel').onchange = e => { LOCAL.voice = e.target.value; saveLocal(); renderVoices(); };
  $('#voiceTest').onclick = () => { const T = CFG.texts[CFG.caller.lang];
    speak([fill(T.triple, {n: 20}), T.t180, fill(T.next_remaining, {name: 'Felix', score: 40})].join('. '), true); };
  $('#resetSettings').onclick = async () => { if (!confirm('Alle Einstellungen zurücksetzen?')) return;
    CFG = await api('/api/settings', 'DELETE'); loadSettings(); };
  renderVoices(); renderTexts();
}
function renderTexts() {
  const lang = CFG.caller.lang, T = CFG.texts[lang];
  $('#textsLang').textContent = lang === 'de' ? '(Deutsch)' : '(English)';
  $('#texts').innerHTML = Object.keys(TEXT_LABELS).map(k => `<label>${TEXT_LABELS[k]}
    <div class="row"><input data-t="${k}" value="${esc(T[k] ?? '')}"><button data-play="${k}">▶</button></div></label>`).join('');
  $$('#texts input').forEach(el => el.oninput = () => saveSettings({texts: {[lang]: {[el.dataset.t]: el.value}}}));
  $$('#texts [data-play]').forEach(b => b.onclick = () => speak(fill(CFG.texts[lang][b.dataset.play],
    {name: 'Felix', score: 40, points: 100, n: 20, dart: 'Triple 20'}), true));
}
