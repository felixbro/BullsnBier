/* Start: Daten laden, WebSocket, Ereignisse verteilen */
var lastThrow = Date.now();
function render(m) {
  if (!m) return;
  ST = m;
  renderHeader(m);
  if (PAGE === 'live' || m.game || m.bulloff) renderLive(m, render.delay || 0);
  render.delay = 0;
}
function renderHeader(m) {
  var d = m.detector || {}, cams = d.cams || [], cs = $('#camStatus');
  if (m.sim) { cs.classList.add('hidden'); }
  else {
    cs.classList.remove('hidden');
    var ok = cams.filter(function (c) { return c.ok && c.cal; }).length;
    cs.innerHTML = '<span class="dot' + (ok === cams.length && cams.length ? '' : ' warn') + '"></span>' + cams.length + ' Kameras · ' + (ok === cams.length && cams.length ? 'bereit' : ok + ' bereit');
  }
  $('#simPill').classList.toggle('hidden', !m.sim);
  $('#badgePaused').classList.toggle('hidden', !d.paused);                       // C3
  // C2: Fehler bleiben stehen, bis behoben
  var keys = (m.errors || []).map(function (e) { return 'err:' + e.msg; });
  $$('#toasts [data-key^="err:"]').forEach(function (t) { if (keys.indexOf(t.getAttribute('data-key')) < 0) t.remove(); });
  (m.errors || []).forEach(function (e) { if (!$('#toasts [data-key="err:' + e.msg + '"]')) toast(e.msg.replace(/ \(.*\)/, ''), 'Kameras prüfen', 'warn', 'err:' + e.msg); });
  var blob = $('#blobPlayer'), g = m.game;
  blob.style.background = g ? 'radial-gradient(closest-side, ' + pcolorOf(g.state.current) + '29, ' + pcolorOf(g.state.current) + '00)' : '';
}
function onMessage(m) {
  if (m.type === 'state') {
    var calls = m.calls || [];
    if (calls.some(function (c) { return c.k === 'dart' || c.k === 'start'; })) lastThrow = Date.now();
    var prevGame = ST && ST.game;
    // Spiel neu gestartet -> Live zeigen, Avatare vorladen
    if (calls.some(function (c) { return c.k === 'start' || c.k === 'bulloff'; }) && m.game !== undefined) {
      preloadAvatars((m.game || m.bulloff || {}).players);
      if (PAGE !== 'live') showPage('live');
      shown = {}; lastDisplayP = null;
    }
    if (!m.game && !m.bulloff) stopA();
    if (m.game && m.game.state.winner === null && fxCur && fxCur.key === 'match_won') stopA();
    // Nachlauf: Werfer bleibt kurz groß, damit Bust/100+/Ups sichtbar sind
    var closed = calls.some(function (c) { return ['turn', 'bust', 'halved', 'leg', 'match'].indexOf(c.k) >= 0; });
    ST = m;
    var delay = runEffects(m);
    if (closed && m.game && m.game.state.last_turn) {
      hold = {ti: m.game.state.last_turn.ti, until: Date.now() + Math.max(1700, delay)};
      clearTimeout(onMessage.ht); onMessage.ht = setTimeout(function () { render(ST); }, Math.max(1700, delay) + 30);
    }
    render.delay = delay;
    render(m);
    if (PAGE === 'live' || m.game) cardEffects(m);
    if (calls.some(function (c) { return c.k === 'unknown'; })) toast('Pfeil nicht erkannt', 'Bitte Wurf korrigieren', 'warn', 'unknown');
    if (calls.some(function (c) { return c.k === 'cal_warn'; })) toast('Kalibrierung ungenau', 'Kameras weichen voneinander ab', 'warn', 'calwarn');
    if (calls.some(function (c) { return c.k === 'dart'; })) { clearToast('unknown'); }
    announce(calls);
    if (PAGE === 'cams' && m.detector && m.detector.running && calls.length === 0) {} // Kameraseite lädt nur auf Wunsch neu
  }
  if (m.type === 'settings') { CFG = m.settings; applyDisplay(); }
  if (m.type === 'fx_test') { var k = m.fx.trigger; if (FXA[k] && PAGE === 'live') playA(k, demoData(k), true); }
  if (m.type === 'warn') toast(m.msg, '', 'warn', 'w:' + m.msg);
  if (m.type === 'dart_free') toast('Treffer ' + dartLabel(m.score.name), 'kein Spiel aktiv', 'info', 'free');
}
function connect() {
  var ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
  ws.onmessage = function (e) { onMessage(JSON.parse(e.data)); };
  ws.onclose = function () { setTimeout(connect, 1500); };
}
/* C4 Leerlauf: nach 5 min ohne Wurf und ohne Spiel → Start mit schwebendem Logo */
setInterval(function () {
  if (Date.now() - lastThrow > 5 * 60 * 1000 && !(ST && ST.game && ST.game.state.winner === null) && PAGE !== 'start' && PAGE !== 'settings') showPage('start');
}, 30000);

$('#logoMark').innerHTML = logo(52);
$('#simPill').onclick = function () { $('#simMenu').classList.toggle('hidden'); };
$$('#simMenu [data-aim]').forEach(function (b) { b.onclick = function () { api('/api/sim/throw', 'POST', {aim: b.dataset.aim, spread: 14}); }; });
$$('#simMenu [data-ev]').forEach(function (b) { b.onclick = function () { api('/api/sim/event/' + b.dataset.ev, 'POST'); }; });
$('#simTakeout').onclick = function () { api('/api/sim/takeout', 'POST'); };
document.addEventListener('click', function (e) { var mn = $('#simMenu'); if (!mn.classList.contains('hidden') && !e.target.closest('#simMenu') && !e.target.closest('#simPill')) mn.classList.add('hidden'); });

Promise.all([api('/api/settings'), api('/api/events'), api('/api/players'), api('/api/modes'), api('/api/state')]).then(function (r) {
  CFG = r[0]; EVENTS = r[1]; PLAYERS = r[2]; ST = r[4];
  applyDisplay();
  initNew(r[3]);
  var start = (location.hash || '').slice(1) || (ST.game && ST.game.state.winner === null ? 'live' : 'start');
  showPage(start);
  render(ST);
  connect();
});
