/* 06 · Live-Spiel: aktiver Werfer groß, Board rechts, Spieler unten (Styleguide §2, §6.3) */
var sel = null;            // {ti, i} Dart zur Korrektur
var fixMode = false;
var hold = null;           // {p, ti, until} Nachlauf: Werfer bleibt kurz sichtbar, damit B-Effekte wirken
var shown = {};            // zuletzt angezeigte Werte je Spieler (für countTo)
var lastDisplayP = null, lastRouteKey = '', lastPull = false;

function modeLine(g) {
  var o = g.opts, out = {single: 'Straight', double: 'Double', master: 'Master'};
  var m = g.mode === 'x01' ? o.start + ' ' + out[o.out] + ' Out' :
    g.mode === 'cricket' ? 'Cricket' + ({cutthroat: ' Cut Throat', noscore: ' No Score'}[o.variant] || '') + (o.numbers === 'tactics' ? ' · Tactics' : '') :
    g.mode === 'gotcha' ? 'Gotcha ' + o.target : g.mode === 'random_checkout' ? 'Random Checkout ' + o.min + '–' + o.max : g.mode_name;
  return m + ' · First to ' + (+o.sets ? o.sets + ' Sets' : o.legs);
}
function marksOf(darts) { return darts.reduce(function (a, d) { return a + (d.seg === 25 ? (d.name === 'BULL' ? 2 : 1) : d.mult || 0); }, 0); }
function isPoints(mode) { return ['x01', 'random_checkout', 'countup'].indexOf(mode) >= 0; }
function chipCls(d) {
  if (!d) return 'empty';
  if (d.name === 'MISS') return 'miss';
  if (d.name === 'BULL' || d.name === '25') return 'bull';
  return {1: 'single', 2: 'double', 3: 'triple'}[d.mult] || 'single';
}
function chipAnim(d) { return d.name === 'MISS' ? 'anim-miss' : d.mult === 3 || d.name === 'BULL' ? 'anim-triple' : d.mult === 2 ? 'anim-double' : 'anim-single'; }
function dartLabel(n) { return n === 'BULL' ? 'Bull' : n === '25' ? '25' : n === 'MISS' ? 'Miss' : n; }
function playerTurns(g, p) { return g.turns.filter(function (t) { return t.p === p; }); }
function pStats(g, p) {
  var ts = playerTurns(g, p), pts = 0, n = 0, hi = 0;
  ts.forEach(function (t) { n += t.darts.length; if (t.closed) { pts += t.pts || 0; hi = Math.max(hi, t.pts || 0); } });
  return {avg: n ? 3 * pts / n : 0, darts: n, high: hi};
}

/* Welcher Spieler steht groß im Bild? */
function displayTurn(m) {
  var g = m.game, s = g.state, hide = CFG.display.hide_previous !== false;
  var lt = s.last_turn;
  if (lt && m.await_takeout && (!hide || (hold && hold.ti === lt.ti && Date.now() < hold.until))) return {p: lt.p, darts: lt.darts, ti: lt.ti, closed: true, lt: lt};
  return {p: s.current, darts: s.turn.darts, ti: s.turn.ti, closed: false};
}

function renderLive(m, fxDelay) {
  updEnd(m);
  var card = $('#activeCard'), g = m.game;
  card.classList.remove('anim-bust', 'anim-turn', 'play');
  $('#liveLeft').textContent = m.sim ? 'Simulator' : 'Live-Erkennung';
  if (m.bulloff) return renderBulloff(m);
  $('#bullg').classList.remove('anim-bulloff', 'play');
  if (!g) {
    card.innerHTML = '<div class="empty-live"><div class="idle idle-mark">' + logo(220) + '</div><h1 class="h1">Kein Spiel läuft</h1>' +
      '<p class="lead">Neues Spiel starten – freie Würfe werden trotzdem erkannt.</p><a class="btn-cta" data-page="new">Neues Spiel +</a></div>';
    $('#plist').innerHTML = ''; $('#pullHint').classList.add('hidden'); drawHits([]); drawTargets();
    lastDisplayP = null; return;
  }
  var s = g.state, dt = displayTurn(m), p = dt.p, pl = g.players[p], v = s.views[p] || {};
  var sets = +g.opts.sets, darts = dt.darts;
  var main = v.main, isNum = typeof main === 'number';
  var sum = darts.reduce(function (a, d) { return a + d.value; }, 0);
  var bust = dt.closed && dt.lt && dt.lt.bust;
  var startScore = isPoints(g.mode) && isNum ? (bust ? main : main + (g.mode === 'countup' ? -sum : sum)) : null;
  var st = pStats(g, p);
  var lastPts = playerTurns(g, p).filter(function (t) { return t.closed && t.leg === s.leg; }).slice(-4).reverse();

  var chips = '';
  for (var i = 0; i < 3; i++) {
    var d = darts[i], on = sel && sel.ti === dt.ti && sel.i === i;
    chips += d ? '<div class="dart ' + chipCls(d) + (on ? ' sel' : '') + '" data-i="' + i + '"><b>' + dartLabel(d.name) + '</b><small>' + d.value + '</small>' + (bust ? '<span class="strike"></span>' : '') + '</div>'
      : '<div class="dart empty">Dart ' + (i + 1) + '</div>';
  }
  var box = '';
  var route = !dt.closed && s.checkout ? s.checkout : null;
  if (route) box = '<div class="checkout" id="coBox"><div class="lbl"><span class="dot"></span>Checkout · ' + route.length + (route.length === 1 ? ' Dart' : ' Darts') + '</div>' +
    '<div class="way">' + route.map(dartLabel).join(' · ') + '</div><div class="alt">Rest ' + main + '</div></div>';
  else if (v.marks) box = crTable(g);
  else if (s.targets && s.targets[p]) box = '<div class="infobox"><div class="lbl"><span class="dot" style="background:var(--aqua-strong)"></span>Ziel</div><div class="way">' + esc(s.targets[p]) + '</div>' + (v.sub ? '<div class="alt">' + esc(v.sub) + '</div>' : '') + '</div>';
  else if (g.mode === 'gotcha') box = '<div class="infobox"><div class="lbl">Bis ' + g.opts.target + '</div><div class="way">noch ' + (g.opts.target - main) + '</div></div>';
  else if (v.sub) box = '<div class="infobox"><div class="lbl">Stand</div><div class="way" style="font-size:32px">' + esc(v.sub) + '</div></div>';

  var who = '<div class="lc-who">' + avatar(pl, 104, true) + '<div><div class="lc-name">' + esc(pl.name) + '</div><div class="lc-sub">Spieler ' + (p + 1) +
    ' · Legs ' + s.legs_won[p] + (sets ? ' · Sets ' + s.sets_won[p] : '') + '</div></div></div>';
  var info = (sets ? 'Set ' + (s.set + 1) + ' · ' : '') + 'Leg ' + (s.leg + 1) + ' · ' + modeLine(g) + (s.round_limit ? ' · Runde ' + Math.min(s.round, s.round_limit) + '/' + s.round_limit : '');
  var tag = s.winner !== null ? '<span class="tag active">Sieger</span>' : dt.closed ? '<span class="tag wait">Aufnahme vorbei</span>' : '<span class="tag active">Am Wurf</span>';
  card.innerHTML = '<span class="flash"></span><div class="lc-left">' +
    '<div class="row">' + tag + '<span class="meta" style="font-size:var(--fs-ui)">' + esc(info) + '</span></div>' + who +
    '<div class="score bust-score' + (isNum ? (String(main).length >= 3 ? ' m' : '') : ' txt') + '" id="bigScore">' + esc(main) + '</div><span class="stamp bust-stamp">Überworfen</span></div>' +
    '<div class="lc-right"><div class="lc-turnhead"><span>Aufnahme</span><span><span class="anim-score" id="turnSumWrap"><b id="turnSum">' + (bust ? 0 : g.mode === 'cricket' ? (dt.lt ? dt.lt.marks || 0 : marksOf(darts)) + ' Marks' : sum) + '</b>' +
    '<span class="sticker" style="left:-78px; top:-6px">Ups</span></span>' + (startScore != null && g.mode !== 'countup' ? ' von ' + startScore : '') + '</span></div>' +
    '<div class="chips" id="chips">' + chips + '</div>' + box +
    (lastPts.length ? '<div class="meta">Letzte Aufnahmen</div><div class="lastturns">' + lastPts.map(function (t) { return '<span>' + (t.pts || 0) + '</span>'; }).join('') + '</div>' : '') +
    '<div class="lc-stats">' + (isPoints(g.mode) ? '<div><div class="k">Ø 3 Darts</div><div class="v">' + st.avg.toFixed(1) + '</div></div>' : '<div><div class="k">Runde</div><div class="v">' + s.round + '</div></div>') +
    '<div><div class="k">Darts</div><div class="v">' + st.darts + '</div></div><div><div class="k">High</div><div class="v">' + st.high + '</div></div></div></div>';
  $$('#chips .dart[data-i]').forEach(function (c) { c.onclick = function () { pickSel(dt.ti, +c.dataset.i); }; });

  // Score zählt (B14) – bei Vollbild-Effekt ab 85 % seiner Dauer
  var big = $('#bigScore');
  fitScore(big);
  if (isNum) countTo(big, main, {from: shown[p] != null && lastDisplayP === p ? shown[p] : main, delay: fxDelay ? fxDelay * .85 : 0});
  shown[p] = isNum ? main : null;
  if (lastDisplayP !== null && lastDisplayP !== p && animOn('next_player')) playCard('anim-turn');   // B5 Nächster Spieler
  lastDisplayP = p;
  var rk = route ? p + ':' + route.join() : '';
  if (route && rk !== lastRouteKey) { var cb = $('#coBox'); cb.classList.add('anim-finishrange'); play(cb); }   // B6
  else if (route) { $('#coBox').classList.add('anim-finishrange', 'play'); }
  lastRouteKey = rk;

  renderPlist(g, m);
  // Board
  $('#liveRight').innerHTML = darts.length ? 'Treffer <b>' + dartLabel(darts[darts.length - 1].name) + '</b>' : '';
  drawHits(darts, sel && sel.ti === dt.ti ? sel.i : -1);
  drawTargets(route, s.targets && !dt.closed ? targetFields(s.targets[s.current]) : []);
  var pull = m.await_takeout && s.winner === null, ph = $('#pullHint');
  ph.classList.toggle('hidden', !pull);
  $('.boardcard .card-head').style.visibility = pull ? 'hidden' : '';
  if (pull && !lastPull) play(ph);                                      // B12
  lastPull = pull;
  $('#btnNext').textContent = m.await_takeout ? 'Nächster Spieler' : 'Aufnahme beenden';
  renderManual();
}

/* Großer Score passt nicht? Nur per transform verkleinern (§7: nur transform/opacity) */
function fitScore(el) {
  el.style.transform = ''; el.style.webkitTransform = '';
  var avail = el.parentNode.clientWidth, w = el.scrollWidth;
  if (w > avail && avail > 0) { var s = 'scale(' + (avail / w).toFixed(3) + ')'; el.style.transform = s; el.style.webkitTransform = s; }
}

function crTable(g) {
  var s = g.state, nums = Object.keys(s.views[0].marks).sort(function (a, b) { return (a == 25) - (b == 25) || b - a; });
  var cols = 'grid-template-columns:44px repeat(' + g.players.length + ',minmax(0,1fr))';
  var sym = ['', '/', '✕', 'Ⓧ'];
  var h = '<div class="infobox crtable"><div class="crow" style="' + cols + '"><span></span>' + g.players.map(function (p) { return '<span class="hd">' + avatar(p, 24) + '</span>'; }).join('') + '</div>';
  nums.forEach(function (n) {
    h += '<div class="crow" style="' + cols + '"><span class="num">' + (n == 25 ? 'B' : n) + '</span>' + g.players.map(function (_, i) {
      var k = s.views[i].marks[n]; return '<span class="m' + (k >= 3 ? ' c3' : '') + '">' + sym[k] + '</span>'; }).join('') + '</div>';
  });
  return h + '</div>';
}

function renderPlist(g, m) {
  var s = g.state, n = g.players.length, next = (s.current + 1) % n;
  $('#plist').innerHTML = g.players.map(function (p, i) {
    var v = s.views[i] || {}, cur = i === s.current && s.winner === null, isNext = !cur && i === next && n > 1 && s.winner === null;
    var rem = typeof v.main === 'number' && isPoints(g.mode) && g.mode !== 'countup' ? v.main : null;
    var fin = !cur && rem != null && rem <= 170 && [169, 168, 166, 165, 163, 162, 159].indexOf(rem) < 0 && rem > 1;
    var state = s.winner === i ? 'Sieger' : cur ? 'am Wurf' : isNext ? 'als Nächstes' : fin ? 'im Finish' : 'wartet';
    var stt = pStats(g, i);
    return '<div class="pcard' + (cur ? ' active' : isNext ? ' next' : '') + '" data-p="' + i + '"><span class="flash"></span><span class="stamp bust-stamp">Erwischt!</span>' +
      '<div class="top">' + avatar(p, 40) + '<div style="min-width:0"><div class="who">' + esc(p.name) + '</div><div class="state">' + state + '</div></div>' +
      '<span class="legs">' + (+g.opts.sets ? 'Sets ' + s.sets_won[i] + ' · ' : '') + 'Legs ' + s.legs_won[i] + '</span></div>' +
      '<div class="bot"><span>' + (isPoints(g.mode) ? 'Ø ' + stt.avg.toFixed(1) + '<br>' : '') + stt.darts + ' Darts</span><span class="rest' + (cur || isNext ? '' : ' dim') + '" data-p="' + i + '">' + esc(v.main) + '</span></div></div>';
  }).join('');
  $$('#plist .rest').forEach(function (el) {
    var i = +el.dataset.p, v = s.views[i] && s.views[i].main;
    if (typeof v === 'number') { countTo(el, v, {from: shown['l' + i] != null ? shown['l' + i] : v}); shown['l' + i] = v; }
  });
  var act = $('#plist .pcard.active'); if (act && act.scrollIntoView) act.scrollIntoView({block: 'nearest', inline: 'nearest'});
}

function renderBulloff(m) {
  var b = m.bulloff, card = $('#activeCard');
  var rows = b.players.map(function (p, i) { var t = b.throws.filter(function (x) { return x.p === i; })[0];
    return '<div><span style="display:flex; align-items:center; gap:12px">' + avatar(p, 40) + esc(p.name) + '</span><span>' + (t ? dartLabel(t.d) + ' · ' + t.dist + ' mm' : b.current === i ? 'wirft …' : '–') + '</span></div>'; }).join('');
  var cur = b.players[b.current] || {};
  card.innerHTML = '<div class="lc-left"><div class="row"><span class="tag active">Bull-Off</span><span class="meta" style="font-size:var(--fs-ui)">' + (b.round > 1 ? 'Stechen · ' : '') + 'Wer näher am Bull ist, beginnt</span></div>' +
    '<div class="lc-who">' + avatar(cur, 104, true) + '<div><div class="lc-name">' + esc(cur.name || '') + '</div><div class="lc-sub">wirft auf das Bull</div></div></div></div>' +
    '<div class="lc-right"><h2 class="h">Wer ist näher dran?</h2><div class="list">' + rows + '</div></div>';
  $('#plist').innerHTML = ''; drawHits([]); drawTargets([], ['25', 'BULL']);
  var bg = $('#bullg'); if (!bg.classList.contains('play')) { bg.classList.add('anim-bulloff'); play(bg); }   // B13
  $('#pullHint').classList.toggle('hidden', !m.await_takeout);
}

function playCard(kind) { var c = $('#activeCard'); c.classList.remove('anim-bust', 'anim-turn', 'play'); c.classList.add(kind); play(c); }

/* B-Effekte aus Ereignissen */
function cardEffects(m) {
  var calls = m.calls || [], has = function (k) { return calls.filter(function (c) { return c.k === k; })[0]; };
  var dart = has('dart'), turn = has('turn');
  if (dart && animOn(dart.d === 'MISS' ? 'dart_miss' : dart.d === 'BULL' || dart.d === '25' ? 'dart_bull' : {T: 'dart_triple', D: 'dart_double'}[dart.d[0]] || 'dart_single')) {
    var cs = $$('#chips .dart:not(.empty)'), c = cs[cs.length - 1];
    if (c) { var d = {name: dart.d, mult: dart.d[0] === 'T' ? 3 : dart.d[0] === 'D' ? 2 : 1}; c.classList.add(chipAnim(d)); play(c); }
  }
  if (turn && turn.points >= 100 && animOn(turn.points >= 140 ? 'score_140' : 'score_100')) {
    var w = $('#turnSumWrap'); w.classList.toggle('s140', turn.points >= 140); play(w);
  } else if (turn && turn.x01 && turn.points < 20 && animOn('score_low')) {
    var u = $('#turnSumWrap'); u.classList.remove('anim-score'); u.classList.add('anim-ups'); play(u);
  }
  if (has('bust') && animOn('bust')) playCard('anim-bust');
  if (has('halved') && animOn('halved')) {
    var b = $('#bigScore'), nv = b.getAttribute('data-value') || b.textContent, ov = 2 * +nv + 1;
    b.innerHTML = '<span class="anim-halved play" style="position:relative; display:inline-block"><span class="old">' + ov + '</span><span class="new" style="position:absolute; left:0; top:0">' + nv + '</span></span>';
  }
  calls.filter(function (c) { return c.k === 'gotcha'; }).forEach(function (c) {
    if (!animOn('gotcha')) return;
    var pc = $('#plist .pcard[data-p="' + c.p + '"]'); if (pc) { pc.classList.add('anim-gotcha'); play(pc); }
  });
  if (has('bust') && animOn('bust')) {
    var lt = m.game && m.game.state.last_turn, pc2 = lt && $('#plist .pcard[data-p="' + lt.p + '"]');
    if (pc2 && $('#activeCard .lc-name').textContent !== m.game.players[lt.p].name) {
      $('.bust-stamp', pc2).textContent = 'Überworfen'; pc2.classList.add('anim-gotcha'); play(pc2);
    }
  }
}

/* Korrektur / manuelle Eingabe */
function pickSel(ti, i) {
  sel = sel && sel.ti === ti && sel.i === i ? null : {ti: ti, i: i};
  if (sel && !fixMode) { fixMode = true; }
  render(ST);
}
function renderManual() {
  var box = $('#manual'); $('#btnFix').classList.toggle('on', fixMode);
  box.classList.toggle('hidden', !fixMode);
  box.parentNode.classList.toggle('fixing', !!(fixMode && ST && ST.game));   // Board schrumpft, Panel liegt darunter statt darüber
  if (!fixMode || !ST || !ST.game) { if (!ST || !ST.game) box.classList.add('hidden'); return; }
  var s = ST.game.state, turns = [];
  if (s.turn.darts.length) turns.push(['Aktuell', s.turn.ti, s.turn.darts]);
  if (s.last_turn) turns.push([ST.game.players[s.last_turn.p].name, s.last_turn.ti, s.last_turn.darts]);
  var prev = turns.map(function (t) { return '<span class="meta">' + esc(t[0]) + '</span>' + t[2].map(function (d, i) {
    return '<button type="button" data-ti="' + t[1] + '" data-i="' + i + '" class="' + (sel && sel.ti === t[1] && sel.i === i ? 'sel' : '') + '">' + dartLabel(d.name) + '</button>'; }).join(''); }).join('');
  box.innerHTML = '<div class="sel-info">' + (sel ? 'Dart gewählt ✓ – jetzt Feld auf dem Board tippen (außerhalb = Miss)' : 'Dart antippen, dann Feld auf dem Board tippen – ohne Auswahl wird ein Wurf eingetragen') + '</div>' +
    '<div class="prev">' + prev + '<button type="button" class="done" data-close>Fertig</button></div>';
  $$('.prev button', box).forEach(function (b) { b.onclick = function () {
    if (b.hasAttribute('data-close')) { fixMode = false; sel = null; return render(ST); }
    pickSel(+b.dataset.ti, +b.dataset.i); }; });
}
function manualDart(name, pos) {
  var body = {name: name}; if (pos) body.pos = pos;
  if (sel) { body.ti = sel.ti; body.i = sel.i; sel = null; api('/api/edit', 'POST', body); }
  else api('/api/dart', 'POST', body);
}
function onBoardClick(name, xy) {
  if (sel || fixMode) return manualDart(name, xy);
  if (ST && ST.sim) api('/api/sim/throw', 'POST', {x: xy[0], y: xy[1]});
  else toast('Korrigieren antippen', 'um Würfe von Hand einzutragen', 'info', 'fixhint');
}
$('#btnUndo').onclick = function () { stopA(); sel = null; hold = null; api('/api/undo', 'POST'); };
$('#btnFix').onclick = function () { fixMode = !fixMode; if (!fixMode) sel = null; render(ST); };
/* Spiel abbrechen (läuft noch, wird nicht gewertet) bzw. beenden (Sieger steht fest, ist schon gespeichert) */
function updEnd(m) {
  var b = $('#btnEnd'), g = m && (m.game || m.bulloff);
  b.classList.toggle('hidden', !g);
  if (g) b.textContent = m.game && m.game.state.winner !== null ? 'Spiel beenden' : 'Spiel abbrechen';
}
$('#btnEnd').onclick = function () {
  var done = ST && ST.game && ST.game.state.winner !== null;
  if (!done && !confirm('Spiel abbrechen? Es wird nicht gewertet.')) return;
  stopA(); sel = null; hold = null; fixMode = false;
  api('/api/game', 'DELETE').then(function () { showPage('start'); });
};
$('#btnNext').onclick = function () { sel = null; hold = null; api('/api/next', 'POST'); };
$('#darts3').innerHTML = DART_ICO + DART_ICO + DART_ICO;
document.addEventListener('keydown', function (e) {
  if (['INPUT', 'SELECT', 'TEXTAREA'].indexOf(e.target.tagName) >= 0 || PAGE !== 'live') return;
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('#btnNext').click(); }
  if (e.key === 'Backspace') $('#btnUndo').click();
  if (e.key === 'Escape') { sel = null; fixMode = false; render(ST); }
});
