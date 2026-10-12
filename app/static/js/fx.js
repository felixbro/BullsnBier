/* Effekte nach Styleguide §8: A Vollbild (Rang-Logik, immer nur einer), B am Bauteil, C Hinweise */
var FX_RANK = {match_won: 8, leg_won: 7, score_180: 6, high_finish: 5, shanghai: 4, dart_bull: 3, dart_triple: 2, game_start: 1};
var fxCur = null;   // {key, el, until}

function pulse() { return '<div class="fx__pulse"><i></i><i></i><i></i></div>'; }
function rep(n, s) { var o = ''; for (var i = 0; i < n; i++) o += s; return o; }
function dartChipColor(n) { return n === 'BULL' || n === '25' || n[0] === 'T' ? '#FF6B5E' : n[0] === 'D' ? '#3DBB7A' : 'rgba(255,255,255,.75)'; }
var STAR = function (c) { return '<svg class="fx__star ' + c + '" viewBox="0 0 40 40" aria-hidden="true"><path d="M20 0C21 13 27 19 40 20C27 21 21 27 20 40C19 27 13 21 0 20C13 19 19 13 20 0Z" fill="#FFFFFF" stroke="#202020" stroke-width="1.5"></path></svg>'; };
var BEER = '<svg viewBox="0 0 100 100" width="190" height="190" fill="none" stroke="#202020" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
  '<path d="M70 38h8a10 10 0 0 1 10 10v14a10 10 0 0 1-10 10h-8" stroke-width="5"></path><path d="M70 45h6a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5h-6"></path>' +
  '<path d="M22 30h48v54a6 6 0 0 1-6 6H28a6 6 0 0 1-6-6z" fill="#FFD66B"></path>' +
  '<path d="M33 44v36M46 44v36M59 44v36" stroke="#FFFFFF" stroke-opacity=".75" stroke-width="4"></path>' +
  '<circle cx="40" cy="62" r="2" fill="#FFFFFF" stroke="none"></circle><circle cx="53" cy="72" r="1.6" fill="#FFFFFF" stroke="none"></circle><circle cx="64" cy="56" r="1.8" fill="#FFFFFF" stroke="none"></circle>' +
  '<path d="M18 34c-4-7 2-15 10-13c1-8 12-11 18-5c5-6 16-4 18 4c8-2 13 6 9 13c-2 5-9 6-13 3c-4 4-11 4-14 0c-4 4-12 4-15-1c-5 3-11 2-13-1z" fill="#DDF96A"></path>' +
  '<path d="M64 33c2 6-1 11 2 15c3 3 6 1 6-4" fill="#DDF96A"></path></svg>';

/* Bauplan je Effekt: Klasse, Dauer, HTML aus Daten */
var FXA = {
  game_start: {cls: 'fx--start', d: 1400, html: function (o) {
    return '<div class="fx__band"></div><div class="fx__word">Game on</div><div class="fx__sub">' + esc(o.sub || '') + '</div>'; }},
  dart_triple: {cls: 'fx--triple', d: 1200, html: function (o) {
    return '<div class="fx__glow"></div>' + pulse() + '<div class="fx__tag"><span>TREBLE · DART ' + (o.n || 1) + '</span></div>' +
      '<div class="fx__word grad-text">' + esc(o.d || 'T20') + '</div><div class="fx__plus" data-count="' + (o.value || 60) + '" data-prefix="+" data-count-at="200">+' + (o.value || 60) + '</div>'; }},
  dart_bull: {cls: 'fx--bull', d: 1400, html: function (o) {
    var outer = o.d === '25';
    return '<div class="fx__glow"></div><div class="fx__ring r2"></div><div class="fx__ring r1"></div>' + pulse() +
      '<div class="fx__target"><div class="fx__outer"><div class="fx__core"></div></div></div><div class="fx__tag" style="top:120px"><span>DART ' + (o.n || 1) + ' · ' + (outer ? 'OUTER BULL' : 'INNER BULL') + '</span></div>' +
      '<div class="fx__word">' + (outer ? 'BULL' : 'BULLSEYE') + '</div><div class="fx__plus" data-count="' + (outer ? 25 : 50) + '" data-prefix="+" data-count-at="640">+' + (outer ? 25 : 50) + '</div>'; }},
  score_180: {cls: 'fx--180', d: 2400, html: function (o) {
    var ch = (o.darts || ['T20', 'T20', 'T20']).map(function (d) { return '<span>' + esc(d) + '</span>'; }).join('');
    return '<div class="fx__glow"></div><div class="fx__burst">' + rep(12, '<span><i></i></span>') + '</div>' +
      '<div class="fx__word grad-text" data-count="180" data-count-at="120" data-count-dur="700">180</div><div class="fx__sub">ONE HUNDRED AND EIGHTY</div><div class="fx__chips">' + ch + '</div>'; }},
  high_finish: {cls: 'fx--finish', d: 1600, html: function (o) {
    var way = (o.darts || []).map(function (d) { return '<span style="background:' + dartChipColor(d) + '">' + esc(d === 'BULL' ? 'Bull' : d) + '</span>'; }).join('');
    return '<div class="fx__glow"></div><div class="fx__ring r1"></div><div class="fx__ring r2"></div><div class="fx__tag"><span>HIGH FINISH · ' + esc(o.out || 'DOUBLE OUT') + '</span></div>' +
      '<div class="fx__word grad-text" data-count="' + (o.checkout || 100) + '" data-count-at="100" data-count-dur="600">' + (o.checkout || 100) + '</div><div class="fx__way">' + way + '</div>'; }},
  shanghai: {cls: 'fx--shanghai', d: 1600, html: function (o) {
    var n = o.n || 20;
    return '<div class="fx__glow"></div><div class="fx__chips"><span style="background:rgba(255,255,255,.75)">S' + n + '</span><span style="background:#3DBB7A">D' + n + '</span><span style="background:#FF6B5E">T' + n + '</span></div><div class="fx__word">SHANGHAI!</div>'; }},
  leg_won: {cls: 'fx--leg', d: 2200, html: function (o) {
    return '<div class="fx__band" style="--pc:' + o.color + '"></div><div class="fx__band2"></div><div class="fx__who">' + avatar(o.player, 220, true) +
      '<div><b>' + esc(o.name) + '</b><small>' + esc(o.sub || 'Leg gewonnen') + '</small></div></div>'; }},
  match_won: {cls: 'fx--winner', d: 4000, html: function (o) {
    var fw = function (n) { return '<div class="fw fw' + n + '">' + rep(10, '<span><i></i></span>') + '</div>'; };
    return '<div class="fx__rays"></div><div class="fx__glow"></div>' + fw(1) + fw(2) + fw(3) + fw(4) + '<div class="fx__confetti">' + rep(24, '<i></i>') + '</div>' +
      '<div class="fx__trophy">' + BEER + '</div>' + STAR('s1') + STAR('s2') + STAR('s3') +
      '<div class="fx__banner"><span>Gewinner haben Bier verdient!</span></div>' +
      '<div class="fx__pulse" style="--pulse-c:' + o.color + '; --pulse-g:' + o.color + '66"><i></i><i></i><i></i></div>' +
      '<div class="fx__who">' + avatar(o.player, 200, true) + '<b>' + esc(o.name) + ' gewinnt</b><small>' + esc(o.sub || '') + '</small></div>' +
      '<div class="fx__actions"><button class="btn-cta" type="button" data-act="rematch">Revanche</button><button class="btn-glass" type="button" data-act="home">Zur Übersicht</button></div>'; }}
};

function animOn(key) { return CFG && CFG.display.animations && CFG.display.anim[key] !== false; }

function buildFx(key, data) {
  var f = FXA[key], el = document.createElement('div');
  el.className = 'fx ' + f.cls; el.setAttribute('aria-hidden', 'true');
  el.innerHTML = '<div class="fx__veil"></div><div class="fx__stage">' + f.html(data || {}) + '</div>';
  return el;
}
function startCounts(el) {
  $$('[data-count]', el).forEach(function (c) {
    var to = +c.getAttribute('data-count'), pre = c.getAttribute('data-prefix') || '';
    c.textContent = pre + '0'; c.setAttribute('data-value', 0);
    setTimeout(function () { countTo(c, to, {prefix: pre, from: 0, dur: +(c.getAttribute('data-count-dur') || 500)}); }, +(c.getAttribute('data-count-at') || 0));
  });
}

/* Vollbild-Effekt abspielen. Liefert die Dauer (für verzögertes Zählen des Scores, §8 B14) */
function playA(key, data, force) {
  if (!FXA[key] || (!force && !animOn(key))) return 0;
  var f = FXA[key], now = Date.now();
  if (fxCur && fxCur.until > now && FX_RANK[fxCur.key] > FX_RANK[key]) return 0;   // niedriger Rang wird verworfen
  stopA();
  var el = buildFx(key, data), root = $('#fxroot'), dezent = CFG && CFG.display.intensity === 'dezent' && !force;
  if (dezent && key !== 'match_won') el.style.setProperty('--fx-d', '200ms');
  root.appendChild(el);
  play(el); startCounts(el);
  var d = dezent && key !== 'match_won' ? 200 : f.d;
  fxCur = {key: key, el: el, until: key === 'match_won' ? Infinity : now + d};
  if (key === 'match_won') {
    $$('[data-act]', el).forEach(function (b) { b.onclick = function () { stopA(); b.dataset.act === 'rematch' ? rematch() : showPage('start'); }; });
  } else {
    el.__t = setTimeout(function () { if (el.parentNode) el.remove(); if (fxCur && fxCur.el === el) fxCur = null; nextChain(); }, d);
  }
  return d;
}
function stopA() { if (fxCur && fxCur.el) { clearTimeout(fxCur.el.__t); fxCur.el.remove(); } fxCur = null; }
var fxChain = [];
function nextChain() { var n = fxChain.shift(); if (n) playA(n[0], n[1]); }

/* Vorschau im Mini-Screen (Einstellungen) */
function previewFx(key, data) {
  var box = $('#pvStage');
  if (!FXA[key]) { box.innerHTML = ''; return; }
  box.innerHTML = '<div class="blob lime" style="left:-160px; top:-120px; width:1100px; height:900px"></div><div class="blob aqua" style="left:1300px; top:80px; width:800px; height:800px"></div>';
  var el = buildFx(key, data); box.appendChild(el); play(el); startCounts(el);
}

/* Daten für Effekte aus dem Spielzustand */
function fxData(key, ctx) {
  var g = ST && ST.game, s = g && g.state, p = ctx && ctx.p != null ? ctx.p : (s ? s.current : 0), pl = pOf(p) || {name: 'Buschi', color: PALETTE[0]};
  var o = {player: pl, name: pl.name, color: pl.color || PALETTE[0]};
  for (var k in ctx) o[k] = ctx[k];
  if (key === 'match_won' && g) {
    var lw = s.legs_won, sw = s.sets_won, sets = +g.opts.sets, i = s.winner;
    var other = Math.max.apply(null, (sets ? sw : lw).filter(function (_, k) { return k !== i; }).concat([0]));
    var turns = g.turns.filter(function (t) { return t.p === i; }), pts = 0, n = 0;
    turns.forEach(function (t) { pts += t.pts || 0; n += t.darts.length; });
    var parts = [];
    if (g.players.length > 1) parts.push((sets ? sw[i] : lw[i]) + ' : ' + other + (sets ? ' Sets' : ' Legs'));
    if (['x01', 'random_checkout', 'countup'].indexOf(g.mode) >= 0 && n) parts.push('Ø ' + (3 * pts / n).toFixed(1).replace('.', ','));
    o.sub = parts.join(' · ');
  }
  if (key === 'leg_won' && g) {
    var lw2 = s.legs_won.slice(), w = p;
    var oth = Math.max.apply(null, lw2.filter(function (_, k) { return k !== w; }).concat([0]));
    o.sub = 'Leg gewonnen' + (g.players.length > 1 ? ' · ' + lw2[w] + ' : ' + oth : '');
  }
  if (key === 'game_start' && g) o.sub = modeLine(g) + ' · ' + g.players[g.state.current].name + ' beginnt';
  return o;
}
function rematch() {
  var g = ST && ST.game; if (!g) return;
  var ps = g.players.map(function (p) { return p.id != null ? p.id : p.name; });
  var opts = JSON.parse(JSON.stringify(g.opts)); delete opts.seed; delete opts.first;
  api('/api/game', 'POST', {mode: g.mode, players: ps, opts: opts}).then(function () { showPage('live'); });
}

/* Server-Ereignisse → Effekte (A + B), Rückgabe: Verzögerung für Score-Zählen */
function runEffects(m, prev) {
  var calls = m.calls || [], g = m.game, s = g && g.state, delay = 0;
  if (!calls.length) return 0;
  var has = function (k) { return calls.filter(function (c) { return c.k === k; })[0]; };
  var dart = has('dart'), turn = has('turn'), leg = has('leg'), match = has('match');
  var lt = s && s.last_turn;
  fxChain = [];
  // A-Effekte nach Rang
  if (has('start')) delay = Math.max(delay, playA('game_start', fxData('game_start', {p: 0})));
  if (dart && g) {
    var n = (lt && turn && lt.darts) ? lt.darts.length : (s.turn.darts.length || 1);
    var isClosed = !!(turn || has('bust') || leg || match || has('halved'));
    var dIdx = isClosed && lt ? lt.darts.length : s.turn.darts.length;
    if (dart.d[0] === 'T' && !(turn && turn.points === 180)) delay = Math.max(delay, playA('dart_triple', {d: dart.d, n: dIdx, value: 3 * +dart.d.slice(1)}));
    if (dart.d === 'BULL' || dart.d === '25') delay = Math.max(delay, playA('dart_bull', {d: dart.d, n: dIdx}));
  }
  if (turn && turn.points === 180) delay = Math.max(delay, playA('score_180', {darts: lt ? lt.darts.map(function (d) { return d.name; }) : null}));
  if (has('shanghai')) delay = Math.max(delay, playA('shanghai', {n: lt && lt.darts[0] ? lt.darts[0].seg : 20}));
  if (leg || match) {
    var w = match ? match.p : leg.p, co = leg ? leg.checkout : (lt && lt.checkout) || 0;
    var after = match ? ['match_won', fxData('match_won', {p: w})] : ['leg_won', fxData('leg_won', {p: w})];
    if (co >= 100 && animOn('high_finish')) {
      delay = Math.max(delay, playA('high_finish', {checkout: co, darts: lt ? lt.darts.map(function (d) { return d.name; }) : [],
        out: ({single: 'STRAIGHT OUT', double: 'DOUBLE OUT', master: 'MASTER OUT'})[g.opts.out] || ''}));
      if (fxCur && fxCur.key === 'high_finish') fxChain.push(after); else playA(after[0], after[1]);
    } else delay = Math.max(delay, playA(after[0], after[1]));
  }
  return delay;
}
