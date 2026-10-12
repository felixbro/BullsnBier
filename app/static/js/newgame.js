/* 10 · Neues Spiel: 10 Modi als Kacheln, Optionen als Segmente, Match, Spieler-Reihenfolge, „Game on“ */
var OUT = [['single', 'Straight'], ['double', 'Double'], ['master', 'Master']];
var ROUNDS = [[0, '∞'], [10, '10'], [15, '15'], [20, '20'], [30, '30']];
var MODES = {
  x01: {short: '301/501 auf genau 0', desc: 'Von 301/501 … auf genau 0 spielen', opts: [
    ['start', 'Startwert', [[101, '101'], [201, '201'], [301, '301'], [501, '501'], [701, '701'], [901, '901']], 1],
    ['in', 'In', OUT], ['out', 'Out', OUT], ['bull', 'Bull', [['25/50', '25 / 50'], ['50/50', '50 / 50']]],
    ['max_rounds', 'Max. Runden · danach gewinnt der niedrigste Rest', ROUNDS]]},
  cricket: {short: '15–20 und Bull schließen', desc: 'Felder 3× schließen, offene Felder punkten', opts: [
    ['variant', 'Variante', [['standard', 'Standard'], ['cutthroat', 'Cut Throat'], ['noscore', 'No Score']], 1],
    ['numbers', 'Felder', [['cricket', 'Cricket 15–20'], ['tactics', 'Tactics 10–20']]], ['max_rounds', 'Max. Runden', ROUNDS]]},
  bermuda: {short: 'Ziel verfehlt = halbiert', desc: '13 Runden: 12 · 13 · 14 · Doppel · 15 · 16 · 17 · Triple · 18 · 19 · 20 · Bull · Bullseye', opts: []},
  shanghai: {short: 'S, D, T einer Zahl', desc: 'Runde = Zielzahl, Single + Double + Triple = Sofortsieg', opts: [
    ['range', 'Felder', [['1-20', '1–20'], ['1-7', '1–7']], 1]]},
  gotcha: {short: 'Gegner einholen = auf 0', desc: 'Von 0 auf genau den Zielwert – wer einen Stand trifft, schickt ihn auf 0', opts: [
    ['target', 'Ziel', [[301, '301'], [501, '501'], [701, '701']], 1], ['out', 'Out', OUT], ['max_rounds', 'Max. Runden', ROUNDS]]},
  atc: {short: '1 bis 20 der Reihe nach', desc: 'Alle Zahlen der Reihe nach, zum Schluss das Bull', opts: [
    ['field', 'Zählende Felder', [['*', 'Alle'], ['S', 'Single'], ['O', 'Single außen'], ['D', 'Double'], ['T', 'Triple']], 1],
    ['order', 'Reihenfolge', [['asc', '1 → 20 → Bull'], ['desc', '20 → 1 → Bull'], ['random', 'Zufällig → Bull']], 1],
    ['hits', 'Treffer pro Feld', [[1, '1'], [2, '2'], [3, '3']]], ['max_rounds', 'Max. Runden', ROUNDS]]},
  rtw: {short: 'Alle Segmente, D und T', desc: 'Jedes Feld einmal, getroffene Punkte zählen mit', opts: [
    ['order', 'Reihenfolge', [['asc', '1 → 20 → Bull'], ['desc', '20 → 1 → Bull'], ['random', 'Zufällig → Bull']], 1], ['max_rounds', 'Max. Runden', ROUNDS]]},
  countup: {short: 'Punkte sammeln', desc: 'So viele Punkte wie möglich in festen Runden', opts: [
    ['max_rounds', 'Runden', [[5, '5'], [8, '8'], [10, '10'], [15, '15'], [20, '20']], 1]]},
  random_checkout: {short: 'Zufällige Finishes', desc: 'Gleiche Zufallszahl für alle auschecken – jedes Leg neu', opts: [
    ['min', 'Minimum', [[2, '2'], [41, '41'], [61, '61'], [101, '101']]], ['max', 'Maximum', [[60, '60'], [100, '100'], [121, '121'], [170, '170']]],
    ['out', 'Out', OUT], ['max_rounds', 'Max. Runden', ROUNDS]]},
  segment: {short: 'Ein Feld gezielt üben', desc: 'Ein Segment trainieren – Trefferquote zählt', opts: [
    ['segment', 'Segment', [], 1], ['field', 'Feld', [['S', 'Single'], ['O', 'Single außen'], ['D', 'Double'], ['T', 'Triple'], ['random', 'Zufällig']], 1],
    ['end', 'Ende nach', [['darts', 'Darts'], ['hits', 'Treffern']]], ['count', 'Anzahl', []]]}
};
var MODE_NAMES = {};
var setup = Object.assign({mode: 'x01', opts: {}, legs: 1, sets: 0, order: 'list'}, LOCAL.setup || {});
var picked = LOCAL.picked || [];

function initNew(modes) {
  for (var k in modes) { MODE_NAMES[k] = modes[k].name; MODES[k].defaults = modes[k].defaults; }
  $('#modes').innerHTML = Object.keys(MODES).map(function (k) { return '<button class="mode" type="button" data-v="' + k + '"><b>' + esc(modes[k].name) + '</b><small>' + esc(MODES[k].short) + '</small></button>'; }).join('');
  $$('#modes .mode').forEach(function (b) { b.onclick = function () { setup.mode = b.dataset.v; renderModes(); storeSetup(); }; });
  $('#o_legs').innerHTML = segHTML([1, 2, 3, 4, 5, 7, 11].map(function (n) { return [n, n]; }));
  segment($('#o_legs'), setup.legs, function (v) { setup.legs = +v; storeSetup(); summary(); });
  $('#o_sets').innerHTML = segHTML([[0, 'Aus'], [2, '2'], [3, '3'], [4, '4'], [5, '5'], [7, '7']]);
  segment($('#o_sets'), setup.sets, function (v) { setup.sets = +v; storeSetup(); summary(); });
  segment($('#o_order'), setup.order, function (v) { setup.order = v; storeSetup(); });
  renderModes();
}
function modeOpts() { var m = setup.mode; return setup.opts[m] = setup.opts[m] || JSON.parse(JSON.stringify(MODES[m].defaults || {})); }
function renderModes() {
  $$('#modes .mode').forEach(function (b) { b.classList.toggle('on', b.dataset.v === setup.mode); });
  var m = MODES[setup.mode], o = modeOpts();
  $('#optsTitle').textContent = MODE_NAMES[setup.mode] + ' · Optionen';
  $('#optsDesc').textContent = m.desc;
  var h = m.opts.length ? '' : '<p class="lead full">Keine Optionen – einfach loslegen.</p>';
  m.opts.forEach(function (q) {
    var ch = q[2];
    if (q[0] === 'segment') ch = [[25, 'Bull']].concat([20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1].map(function (n) { return [n, n]; }));
    if (q[0] === 'count') ch = o.end === 'hits' ? [[5, '5'], [10, '10'], [20, '20'], [50, '50']] : [[33, '33'], [66, '66'], [99, '99']];
    if (o[q[0]] == null || !ch.some(function (c) { return String(c[0]) === String(o[q[0]]); })) o[q[0]] = ch[0][0];
    h += '<div class="field' + (q[3] ? ' full' : '') + '"><span>' + esc(q[1]) + '</span><div class="seg' + (ch.length > 8 ? ' many' : '') + '" data-k="' + q[0] + '">' + segHTML(ch) + '</div></div>';
  });
  $('#modeOpts').innerHTML = h;
  $$('#modeOpts .seg').forEach(function (g) {
    var k = g.dataset.k;
    segment(g, o[k], function (v) { o[k] = isNaN(+v) || v === '' ? v : +v; storeSetup(); summary(); if (k === 'end') renderModes(); });
  });
  summary();
}
function storeSetup() { LOCAL.setup = setup; LOCAL.picked = picked; saveLocal(); }
function summary() {
  var o = modeOpts(), out = {single: 'Straight', double: 'Double', master: 'Master'};
  var parts = [MODE_NAMES[setup.mode]];
  if (setup.mode === 'x01') parts.push(o.start, out[o.out] + ' Out');
  parts.push('First to ' + (setup.sets ? setup.sets + ' Sets' : setup.legs));
  parts.push(picked.length + ' Spieler');
  $('#gameonSub').textContent = parts.join(' · ');
}
function loadNew() {
  var ids = PLAYERS.map(function (p) { return p.id; });
  picked = picked.filter(function (id) { return typeof id === 'string' || ids.indexOf(id) >= 0; });
  var all = PLAYERS.map(function (p) { return {id: p.id, p: p}; }).concat(picked.filter(function (x) { return typeof x === 'string'; })
    .map(function (n, i) { return {id: n, p: {name: n, seed: n, color: PALETTE[(PLAYERS.length + i) % 8]}, guest: true}; }));
  $('#pick').innerHTML = all.map(function (x) {
    var k = picked.indexOf(x.id);
    return '<button type="button" class="pchip' + (k >= 0 ? ' on' : '') + (x.guest ? ' guest' : '') + '" data-id="' + esc(x.id) + '">' + avatar(x.p, 44) + esc(x.p.name) + '<span class="no">' + (k + 1) + '</span></button>';
  }).join('') || '<p class="lead">Noch keine Spieler – unter „Spieler“ anlegen oder Gast hinzufügen.</p>';
  $$('#pick .pchip').forEach(function (b) { b.onclick = function () {
    var id = isNaN(+b.dataset.id) ? b.dataset.id : +b.dataset.id, k = picked.indexOf(id);
    if (k >= 0) picked.splice(k, 1); else picked.push(id);
    storeSetup(); loadNew(); }; });
  summary();
}
pageHooks['new'] = loadNew;
$('#addGuest').onclick = function () { var n = $('#guest').value.trim(); if (n && picked.indexOf(n) < 0) picked.push(n); $('#guest').value = ''; storeSetup(); loadNew(); };
$('#guest').onkeydown = function (e) { if (e.key === 'Enter') $('#addGuest').click(); };
$('#startGame').onclick = function () {
  if (!picked.length) return toast('Spieler wählen', 'Reihenfolge = Antippen', 'info');
  var opts = Object.assign({}, modeOpts(), {legs: setup.legs, sets: setup.sets});
  preloadAvatars(PLAYERS.filter(function (p) { return picked.indexOf(p.id) >= 0; }));
  api('/api/game', 'POST', {mode: setup.mode, players: picked, opts: opts, random_order: setup.order === 'random', bulloff: setup.order === 'bulloff'})
    .then(function () { showPage('live'); }, function (e) { toast('Spiel startet nicht', e && e.detail, 'warn'); });
};
