/* 11 · Spieler der Bude: Raster + Formular (Name, Ansage-Name, Spitzname, Farbe, Avatar, Wurfhand) */
var editId = null, draft = null, CARDS = [];
function blank() { var used = PLAYERS.map(function (p) { return p.color; });
  return {name: '', spoken: '', nick: '', seed: '', hand: 'R', color: PALETTE.filter(function (c) { return used.indexOf(c) < 0; })[0] || PALETTE[0]}; }
function loadPlayers() {
  api('/api/players/cards').then(function (cards) {
    CARDS = cards;
    $('#playersMeta').textContent = cards.length + ' Spieler · Farbe gilt für Anzeige und WLED';
    $('#pgrid').innerHTML = cards.map(function (p) {
      return '<div class="ptile' + (p.id === editId ? ' sel' : '') + '" data-id="' + p.id + '" style="--pc:' + p.color + '"><div class="who">' + avatar(p, 72) +
        '<div><div class="nm">' + esc(p.name) + '</div><div class="nk">' + esc(p.nick || '') + '</div></div></div>' +
        '<div class="ks"><div><div class="k">Ø 3 Darts</div><div class="v">' + (p.avg3 ? p.avg3.toFixed(1) : '–') + '</div></div>' +
        '<div><div class="k">Spiele</div><div class="v">' + p.games + '</div></div><div><div class="k">Fav. Double</div><div class="v">' + esc(p.fav_double) + '</div></div></div></div>';
    }).join('') + '<div class="ptile add" id="addTile"><span class="plus">+</span>Spieler anlegen</div>';
    $$('#pgrid .ptile[data-id]').forEach(function (t) { t.onclick = function () { edit(+t.dataset.id); }; });
    $('#addTile').onclick = function () { edit(null); };
    if (!draft) edit(editId);
  });
}
pageHooks.players = function () { draft = null; loadPlayers(); };
function edit(id) {
  editId = id;
  var p = id != null ? CARDS.filter(function (c) { return c.id === id; })[0] : null;
  draft = p ? {name: p.name, spoken: p.spoken, nick: p.nick, seed: p.seed, hand: p.hand, color: p.color} : blank();
  $$('#pgrid .ptile[data-id]').forEach(function (t) { t.classList.toggle('sel', +t.dataset.id === id); });
  renderForm();
}
function renderForm() {
  var d = draft, T = CFG.texts[CFG.caller.lang], say = fill(T.next, {name: d.spoken || d.name || 'Name'});
  var f = $('#pform');
  f.innerHTML = '<div class="card-head"><h2 class="h">' + (editId != null ? 'Spieler bearbeiten' : 'Neuer Spieler') + '</h2><span class="meta">Spieler ' + (editId != null ? editId : PLAYERS.length + 1) + '</span></div>' +
    '<div class="who"><span id="pfAv">' + avatar({color: d.color, seed: d.seed || d.name}, 136, true) + '</span><div><div class="nm" id="pfName">' + esc(d.name || 'Name') + '</div>' +
    '<div class="say"><span id="pfSay">Ansage: „' + esc(cleanSpeech(say)) + '“</span><button class="btn-icon" type="button" id="pfPlay" aria-label="Probehören">' + PLAY_ICO + '</button></div></div></div>' +
    '<div class="row"><label class="field"><span>Name</span><input id="f_name" value="' + esc(d.name) + '" required></label>' +
    '<label class="field"><span>Spitzname</span><input id="f_nick" value="' + esc(d.nick) + '" placeholder="z. B. Der Wirt"></label></div>' +
    '<label class="field"><span>Ansage-Name für die Sprachausgabe</span><input id="f_spoken" value="' + esc(d.spoken) + '" placeholder="wie es klingen soll, z. B. Ma-rei"></label>' +
    '<div class="field"><span>Spielerfarbe · Anzeige und WLED</span><div class="swatches">' + PALETTE.map(function (c) {
      return '<button type="button" data-c="' + c + '" style="--c:' + c + '" class="' + (c === d.color ? 'on' : '') + '" aria-label="Farbe ' + c + '"></button>'; }).join('') + '</div></div>' +
    '<div class="field"><span>Avatar-Motiv (DiceBear)</span><div class="seedrow"><input id="f_seed" value="' + esc(d.seed) + '" placeholder="leer = Name">' +
    '<button class="btn-icon" type="button" id="pfDice" aria-label="Neu würfeln">⟳</button></div></div>' +
    '<div class="field"><span>Wurfhand</span><div class="seg" id="f_hand"><button data-v="R">Rechts</button><button data-v="L">Links</button></div></div>' +
    (editId != null ? '<button class="btn-glass del" type="button" id="pfDel">Spieler löschen</button>' : '') +
    '<div class="btns"><button class="btn-glass" type="button" id="pfCancel">Abbrechen</button><button class="btn-cta" type="submit">Spieler speichern</button></div>';
  var upd = function () {
    d.name = $('#f_name').value; d.nick = $('#f_nick').value; d.spoken = $('#f_spoken').value; d.seed = $('#f_seed').value;
    $('#pfName').textContent = d.name || 'Name';
    $('#pfSay').textContent = 'Ansage: „' + cleanSpeech(fill(T.next, {name: d.spoken || d.name || 'Name'})) + '“';
  };
  ['f_name', 'f_nick', 'f_spoken'].forEach(function (k) { $('#' + k).oninput = upd; });
  $('#f_seed').onchange = function () { upd(); $('#pfAv').innerHTML = avatar({color: d.color, seed: d.seed || d.name}, 136, true); };
  $('#f_name').onchange = $('#f_seed').onchange;
  $('#pfDice').onclick = function () { d.seed = (d.name || 'Spieler') + '-' + Math.random().toString(36).slice(2, 6); $('#f_seed').value = d.seed; $('#f_seed').onchange(); };
  $$('.swatches button', f).forEach(function (b) { b.onclick = function () { d.color = b.dataset.c;
    $$('.swatches button', f).forEach(function (x) { x.classList.toggle('on', x === b); }); $('#pfAv').innerHTML = avatar({color: d.color, seed: d.seed || d.name}, 136, true); }; });
  segment($('#f_hand'), d.hand, function (v) { d.hand = v; });
  $('#pfPlay').onclick = function () { speak(fill(T.next, {name: d.spoken || d.name}), true); };
  $('#pfCancel').onclick = function () { edit(null); };
  if ($('#pfDel')) $('#pfDel').onclick = function () {
    if (!confirm(d.name + ' löschen? Statistik bleibt erhalten.')) return;
    api('/api/players/' + editId, 'DELETE').then(function () { editId = null; draft = null; refreshPlayers().then(loadPlayers); }); };
  f.onsubmit = function (e) {
    e.preventDefault(); upd();
    if (!d.name.trim()) return toast('Name fehlt', '', 'info');
    var body = {name: d.name, nick: d.nick, spoken: d.spoken, seed: d.seed || d.name, hand: d.hand, color: d.color};
    (editId != null ? api('/api/players/' + editId, 'PUT', body) : api('/api/players', 'POST', body)).then(function (p) {
      toast('Spieler gespeichert', p.name, 'ok'); editId = p.id; draft = null; preloadAvatars([p]); refreshPlayers().then(loadPlayers);
    }, function (e2) { toast('Nicht gespeichert', e2 && e2.detail, 'warn'); });
  };
}
function refreshPlayers() { return api('/api/players').then(function (ps) { PLAYERS = ps; applyDisplay(); }); }
