/* Neues Spiel: Modus, Optionen, Match, Spieler */
const OUT = [['single', 'Straight'], ['double', 'Double'], ['master', 'Master']];
const ROUNDS = [[0, '∞'], [10, '10'], [15, '15'], [20, '20'], [30, '30']];
const MODES = {
  x01: {desc: 'Von 301/501 … auf genau 0 spielen.', opts: {
    start: ['Startwert', [[101, '101'], [201, '201'], [301, '301'], [501, '501'], [701, '701'], [901, '901']]],
    in: ['In', OUT], out: ['Out', OUT],
    bull: ['Bull', [['25/50', '25 / 50'], ['50/50', '50 / 50']]],
    max_rounds: ['Max. Runden (danach gewinnt der niedrigste Rest)', ROUNDS]}},
  cricket: {desc: '15–20 + Bull je 3× schließen, offene Felder punkten.', opts: {
    variant: ['Variante', [['standard', 'Standard'], ['cutthroat', 'Cut Throat'], ['noscore', 'No Score']]],
    numbers: ['Felder', [['cricket', 'Cricket 15–20'], ['tactics', 'Tactics 10–20']]],
    max_rounds: ['Max. Runden', ROUNDS]}},
  bermuda: {desc: '13 Runden: 12, 13, 14, Doppel, 15, 16, 17, Triple, 18, 19, 20, Bull, Bullseye. Keinen Treffer = Punkte halbiert.', opts: {}},
  shanghai: {desc: 'Runde = Zielzahl. Single + Double + Triple in einer Aufnahme = Shanghai (Sofortsieg).', opts: {
    range: ['Felder', [['1-20', '1–20'], ['1-7', '1–7']]]}},
  gotcha: {desc: 'Von 0 hochzählen auf genau den Zielwert. Wer den Stand eines Gegners trifft, schickt ihn auf 0.', opts: {
    target: ['Ziel', [[301, '301'], [501, '501'], [701, '701']]], out: ['Out', OUT], max_rounds: ['Max. Runden', ROUNDS]}},
  atc: {desc: 'Alle Zahlen der Reihe nach treffen, zum Schluss das Bull.', opts: {
    field: ['Zählende Felder', [['*', 'Alle'], ['S', 'Single'], ['O', 'Single außen'], ['D', 'Double'], ['T', 'Triple']]],
    order: ['Reihenfolge', [['asc', '1 → 20 → Bull'], ['desc', '20 → 1 → Bull'], ['random', 'Zufällig → Bull']]],
    hits: ['Treffer pro Feld', [[1, '1'], [2, '2'], [3, '3']]], max_rounds: ['Max. Runden', ROUNDS]}},
  rtw: {desc: 'Wie Around the Clock, jedes Feld einmal. Getroffene Punkte zählen mit.', opts: {
    order: ['Reihenfolge', [['asc', '1 → 20 → Bull'], ['desc', '20 → 1 → Bull'], ['random', 'Zufällig → Bull']]],
    max_rounds: ['Max. Runden', ROUNDS]}},
  countup: {desc: 'So viele Punkte wie möglich in festen Runden.', opts: {
    max_rounds: ['Runden', [[5, '5'], [8, '8'], [10, '10'], [15, '15'], [20, '20']]]}},
  random_checkout: {desc: 'Zufällige Checkout-Zahl (für alle gleich) auschecken – jedes Leg eine neue.', opts: {
    min: ['Minimum', [[2, '2'], [41, '41'], [61, '61'], [101, '101']]], max: ['Maximum', [[60, '60'], [100, '100'], [121, '121'], [170, '170']]],
    out: ['Out', OUT], max_rounds: ['Max. Runden', ROUNDS]}},
  segment: {desc: 'Ein Segment trainieren – Trefferquote zählt.', opts: {
    segment: ['Segment', [...Array(20)].map((_, i) => [i + 1, i + 1]).concat([[25, 'Bull']])],
    field: ['Feld', [['S', 'Single'], ['O', 'Single außen'], ['D', 'Double'], ['T', 'Triple'], ['random', 'Zufällig']]],
    end: ['Ende nach', [['darts', 'Darts'], ['hits', 'Treffern']]],
    count: ['Anzahl', null]}},
};
let MODE_NAMES = {}, setup = Object.assign({mode: 'x01', opts: {}, legs: 1, sets: 0, order: 'list'}, LOCAL.setup || {});
let picked = LOCAL.picked || [];

async function initSetup() {
  const ms = await api('/api/modes');
  for (const k in ms) { MODE_NAMES[k] = ms[k].name; MODES[k].defaults = ms[k].defaults; }
  $('#modes').innerHTML = Object.keys(MODES).map(k => `<button data-v="${k}">${ms[k].name}</button>`).join('');
  seg($('#modes'), setup.mode, v => { setup.mode = v; renderModeOpts(); storeSetup(); });
  renderModeOpts();
  $('#o_legs').innerHTML = segHTML([1, 2, 3, 4, 5, 7, 11].map(n => [n, n]), setup.legs);
  seg($('#o_legs'), setup.legs, v => { setup.legs = +v; storeSetup(); });
  $('#o_sets').innerHTML = segHTML([[0, 'Aus'], [2, '2'], [3, '3'], [4, '4'], [5, '5'], [7, '7']], setup.sets);
  seg($('#o_sets'), setup.sets, v => { setup.sets = +v; storeSetup(); });
  seg($('#o_order'), setup.order, v => { setup.order = v; storeSetup(); });
}
function modeOpts() { const m = setup.mode; return setup.opts[m] ??= {...MODES[m].defaults}; }
function renderModeOpts() {
  const m = MODES[setup.mode], o = modeOpts();
  let h = `<p class="hint">${m.desc}</p>`;
  for (const [k, [label, choices]] of Object.entries(m.opts)) {
    let ch = choices;
    if (k === 'count') ch = o.end === 'hits' ? [[5, '5'], [10, '10'], [20, '20'], [50, '50']] : [[33, '33'], [66, '66'], [99, '99']];
    if (o[k] == null || !ch.some(c => c[0] == o[k])) o[k] = ch[0][0];
    h += k === 'segment'
      ? `<label>${label}</label><select data-k="${k}">${ch.map(([v, l]) => `<option value="${v}" ${v == o[k] ? 'selected' : ''}>${l}</option>`).join('')}</select>`
      : `<label>${label}</label><div class="row seg" data-k="${k}">${segHTML(ch, o[k])}</div>`;
  }
  $('#modeOpts').innerHTML = h;
  $$('#modeOpts .seg').forEach(el => seg(el, o[el.dataset.k], v => {
    o[el.dataset.k] = isNaN(+v) || v === '' ? v : +v; storeSetup(); if (el.dataset.k === 'end') renderModeOpts(); }));
  $$('#modeOpts select').forEach(el => el.onchange = () => { o[el.dataset.k] = +el.value; storeSetup(); });
}
function storeSetup() { LOCAL.setup = setup; LOCAL.picked = picked; saveLocal(); }

async function loadSetup() {
  const ps = await api('/api/players');
  picked = picked.filter(id => typeof id === 'string' || ps.some(p => p.id === id));
  const all = [...ps, ...picked.filter(p => typeof p === 'string').map(n => ({id: n, name: n + ' (Gast)'}))];
  $('#pick').innerHTML = all.map(p => { const k = picked.indexOf(p.id);
    return `<button data-id="${esc(p.id)}" class="${k >= 0 ? 'on' : ''}" style="${k >= 0 ? `--pc:${pcolor(k)}` : ''}"><span class="n">${k >= 0 ? k + 1 : ''}</span> ${esc(p.name)}</button>`; }).join('')
    || '<span class="hint">Noch keine Spieler – unter „Statistik“ anlegen oder Gast hinzufügen.</span>';
  $$('#pick button').forEach(b => b.onclick = () => {
    const id = isNaN(+b.dataset.id) ? b.dataset.id : +b.dataset.id, k = picked.indexOf(id);
    k >= 0 ? picked.splice(k, 1) : picked.push(id); storeSetup(); loadSetup(); });
}
tabHooks.setup = loadSetup;
$('#addGuest').onclick = () => { const n = $('#guest').value.trim(); if (n && !picked.includes(n)) picked.push(n); $('#guest').value = ''; storeSetup(); loadSetup(); };
$('#guest').onkeydown = e => e.key === 'Enter' && $('#addGuest').click();
$('#startGame').onclick = async () => {
  if (!picked.length) return toast('Spieler wählen');
  try {
    await api('/api/game', 'POST', {mode: setup.mode, players: picked, opts: {...modeOpts(), legs: setup.legs, sets: setup.sets},
      random_order: setup.order === 'random', bulloff: setup.order === 'bulloff'});
    showTab('play');
  } catch (e) { toast(e.detail || 'Fehler'); }
};
