/* Fernbedienung fürs Handy (/remote): aktueller Werfer + Board zum Eintragen und Korrigieren.
   Keine Sprachausgabe, keine Vollbild-Effekte. */
var rsel = null;   // {ti, i} gewählter Dart
var rmult = 'S';   // Korrektur-Tabelle: Single/Double/Triple

function dartLabel(n) { return n === 'BULL' ? 'Bull' : n === '25' ? '25' : n === 'MISS' ? 'Miss' : n; }
function chipCls(d) {
  if (d.name === 'MISS') return 'miss';
  if (d.name === 'BULL' || d.name === '25') return 'bull';
  return {1: 'single', 2: 'double', 3: 'triple'}[d.mult] || 'single';
}
function rTurn(m) {
  var s = m.game.state, lt = s.last_turn;
  if (lt && m.await_takeout && !s.turn.darts.length) return {p: lt.p, darts: lt.darts, ti: lt.ti, closed: true, bust: lt.bust};
  return {p: s.current, darts: s.turn.darts, ti: s.turn.ti, closed: false};
}

function render(m) {
  var eb = $('#btnEnd'), eg = m.game || m.bulloff;
  eb.classList.toggle('hidden', !eg);
  if (eg) eb.textContent = m.game && m.game.state.winner !== null ? 'Spiel beenden' : 'Spiel abbrechen';
  var who = $('#who'), hint = $('#hint');
  if (m.bulloff) {
    var b = m.bulloff, p = b.players[b.current];
    who.innerHTML = '<div class="rm-top">' + avatar(p, 56, true) + '<div><div class="rm-name">' + esc(p.name) + '</div><div class="meta">Bull-Off · auf das Bull werfen</div></div></div>';
    hint.textContent = 'Wurf aufs Board tippen'; drawHits([]); drawTargets(); return;
  }
  var g = m.game;
  if (!g) {
    who.innerHTML = '<div class="rm-top">' + logo(56) + '<div><div class="rm-name">Kein Spiel</div><div class="meta">Spiel am großen Bildschirm starten</div></div></div>';
    hint.textContent = ''; drawHits([]); drawTargets(); $('#btnNext').disabled = true; return;
  }
  $('#btnNext').disabled = false;
  var s = g.state, t = rTurn(m), pl = g.players[t.p], v = s.views[t.p] || {};
  if (rsel && rsel.ti !== t.ti && !(s.last_turn && rsel.ti === s.last_turn.ti)) rsel = null;
  var chips = '';
  for (var i = 0; i < 3; i++) {
    var d = t.darts[i];
    chips += d ? '<button type="button" class="dart ' + chipCls(d) + (rsel && rsel.ti === t.ti && rsel.i === i ? ' sel' : '') + '" data-i="' + i + '"><b>' + dartLabel(d.name) + '</b><small>' + d.value + '</small></button>'
      : '<span class="dart empty">' + (i + 1) + '</span>';
  }
  var route = !t.closed && s.checkout ? s.checkout : null;
  var line = route ? '<span class="dot"></span>Checkout ' + route.map(dartLabel).join(' · ') : v.sub ? esc(v.sub) : s.targets && s.targets[t.p] ? 'Ziel ' + esc(s.targets[t.p]) : '';
  var nxt = g.players[(s.current + (t.closed ? 0 : 1)) % g.players.length];
  var tag = s.winner !== null ? 'Sieger' : t.closed ? 'Pfeile ziehen' : 'Am Wurf';
  who.innerHTML = '<div class="rm-top">' + avatar(pl, 56, true) + '<div class="rm-mid"><span class="tag active">' + tag + '</span><div class="rm-name">' + esc(pl.name) + '</div></div>' +
    '<div class="rm-score">' + esc(v.main) + '</div></div>' +
    '<div class="rm-chips" id="chips">' + chips + '</div>' +
    '<div class="rm-line">' + line + (g.players.length > 1 && s.winner === null ? '<span class="rm-next">Danach: ' + esc(nxt.name) + '</span>' : '') + '</div>';
  $$('#chips [data-i]').forEach(function (c) { c.onclick = function () {
    var i = +c.dataset.i; rsel = rsel && rsel.ti === t.ti && rsel.i === i ? null : {ti: t.ti, i: i}; render(ST); }; });
  renderPad();
  hint.innerHTML = rsel ? '<b>Dart ' + (rsel.i + 1) + ' korrigieren</b> – richtigen Wert wählen' :
    t.closed ? 'Aufnahme fertig – „Weiter“ wenn die Pfeile gezogen sind' : (m.sim ? 'Simulator: Wurf aufs Board tippen' : 'Wurf eintragen: Feld tippen · Korrigieren: Dart oben antippen');
  $('#btnNext').textContent = t.closed || t.darts.length >= 3 ? 'Nächster Spieler' : 'Aufnahme beenden';
  drawHits(t.darts, rsel && rsel.ti === t.ti ? rsel.i : -1);
  drawTargets(route, s.targets && !t.closed ? targetFields(s.targets[s.current]) : []);
}

/* Korrektur über die Tabelle statt übers Board */
function renderPad() {
  var pad = $('#pad'), on = !!rsel;
  pad.classList.toggle('hidden', !on); $('#board').classList.toggle('hidden', on);
  if (!on) return;
  var nums = ''; for (var n = 1; n <= 20; n++) nums += '<button type="button" data-n="' + n + '">' + n + '</button>';
  pad.innerHTML = '<div class="seg" id="padMult"><button data-v="S">Single</button><button data-v="D">Double</button><button data-v="T">Triple</button></div>' +
    '<div class="rm-nums">' + nums + '</div><div class="rm-specials"><button type="button" data-f="25">25</button><button type="button" data-f="BULL">Bull</button>' +
    '<button type="button" data-f="MISS">Miss</button><button type="button" class="x" data-x>Abbrechen</button></div>';
  segment($('#padMult'), rmult, function (v) { rmult = v; });
  $$('#pad [data-n], #pad [data-f]').forEach(function (b) { b.onclick = function () {
    if (navigator.vibrate) navigator.vibrate(15);
    var name = b.dataset.f || (rmult + b.dataset.n), body = {ti: rsel.ti, i: rsel.i, name: name};
    rsel = null; rmult = 'S'; api('/api/edit', 'POST', body); }; });
  $('#pad [data-x]').onclick = function () { rsel = null; render(ST); };
}

function onBoardClick(name, xy) {
  if (navigator.vibrate) navigator.vibrate(15);
  if (ST && ST.sim) return api('/api/sim/throw', 'POST', {x: xy[0], y: xy[1]});
  api('/api/dart', 'POST', {name: name, pos: xy});
}
function rDone() { return !!(ST && ST.game && ST.game.state.winner !== null); }
function rEnd() { rsel = null; api('/api/game', 'DELETE'); }
$('#btnEnd').onclick = function () { if (rDone()) rEnd(); else if (typeof holdToConfirm !== 'function' && confirm('Spiel abbrechen? Es wird nicht gewertet.')) rEnd(); };
if (typeof holdToConfirm === 'function') holdToConfirm($('#btnEnd'), rEnd, {when: function () { return !rDone(); }, hint: 'Gedrückt halten'});   // D1
$('#btnUndo').onclick = function () { rsel = null; api('/api/undo', 'POST'); };
$('#btnNext').onclick = function () { rsel = null; api('/api/next', 'POST'); };

function connect() {
  var ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
  ws.onopen = function () { $('#conDot').className = 'dot ok'; $('#conTxt').textContent = 'verbunden'; };
  ws.onmessage = function (e) {
    var m = JSON.parse(e.data);
    if (m.type === 'state') { ST = m; render(m); }
    if (m.type === 'settings') { CFG = m.settings; applyDisplay(); }
  };
  ws.onclose = function () { $('#conDot').className = 'dot warn'; $('#conTxt').textContent = 'getrennt …'; setTimeout(connect, 1500); };
}
$('#logoMark').innerHTML = logo(28);
api('/api/settings').then(function (c) { CFG = c; applyDisplay(); });
api('/api/state').then(function (m) { ST = m; render(m); });
connect();
function markCount() { api('/api/train').then(function (t) { $('#lnkMark').textContent = 'Pfeile markieren' + (t.review ? ' (' + t.review + ' prüfen)' : ''); }).catch(function () {}); }
markCount(); setInterval(markCount, 15000);
