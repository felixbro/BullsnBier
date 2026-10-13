/* 11 · Spieler der Bude: Raster + Formular (Name, Ansage-Name, Spitzname, Farbe, Avatar, Wurfhand) */
var editId = null, draft = null, CARDS = [];
function blank() { var used = PLAYERS.map(function (p) { return p.color; });
  return {name: '', spoken: '', nick: '', seed: '', hand: 'R', color: randColor(used), av_style: '', av_bg: 'player', av_accent: 'ci'}; }
/* Zufällige CI-Farbe, bevorzugt eine noch freie */
function randColor(avoid) { var free = PALETTE.filter(function (c) { return avoid.indexOf(c) < 0; }); free = free.length ? free : PALETTE;
  return free[Math.floor(Math.random() * free.length)]; }
function rndSeed(base) { return (base || 'Spieler') + '-' + Math.random().toString(36).slice(2, 6); }
function avP(d, extra) { return Object.assign({color: d.color, seed: d.seed || d.name || 'Spieler', av_style: d.av_style, av_bg: d.av_bg, av_accent: d.av_accent}, extra || {}); }
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
  draft = p ? {name: p.name, spoken: p.spoken, nick: p.nick, seed: p.seed, hand: p.hand, color: p.color, av_style: p.av_style, av_bg: p.av_bg, av_accent: p.av_accent} : blank();
  $$('#pgrid .ptile[data-id]').forEach(function (t) { t.classList.toggle('sel', +t.dataset.id === id); });
  renderForm();
}
function renderForm() {
  var d = draft, T = CFG.texts[CFG.caller.lang], say = fill(T.next, {name: d.spoken || d.name || 'Name'});
  var f = $('#pform');
  f.innerHTML = '<div class="card-head"><h2 class="h">' + (editId != null ? 'Spieler bearbeiten' : 'Neuer Spieler') + '</h2><span class="meta">Spieler ' + (editId != null ? editId : PLAYERS.length + 1) + '</span></div>' +
    '<div class="who"><span id="pfAv">' + avatar(avP(d), 136, true) + '</span><div><div class="nm" id="pfName">' + esc(d.name || 'Name') + '</div>' +
    '<div class="say"><span id="pfSay">Ansage: „' + esc(cleanSpeech(say)) + '“</span><button class="btn-icon" type="button" id="pfPlay" aria-label="Probehören">' + PLAY_ICO + '</button></div></div></div>' +
    '<div class="row"><label class="field"><span>Name</span><input id="f_name" value="' + esc(d.name) + '" required></label>' +
    '<label class="field"><span>Spitzname</span><input id="f_nick" value="' + esc(d.nick) + '" placeholder="z. B. Der Wirt"></label></div>' +
    '<label class="field"><span>Ansage-Name für die Sprachausgabe</span><input id="f_spoken" value="' + esc(d.spoken) + '" placeholder="wie es klingen soll, z. B. Ma-rei"></label>' +
    '<div class="field"><span>Spielerfarbe · Anzeige und WLED</span><div class="swatches">' + PALETTE.map(function (c) {
      return '<button type="button" data-c="' + c + '" style="--c:' + c + '" class="' + (c === d.color ? 'on' : '') + '" aria-label="Farbe ' + c + '"></button>'; }).join('') +
      '<button type="button" class="rnd" id="pfRndColor">Zufall</button></div></div>' +
    '<div class="field"><span>Avatar · Stil, Motiv und Farben</span><button class="btn-glass avbtn" type="button" id="pfAvEdit"><span id="pfAvMini"></span>Avatar anpassen …</button></div>' +
    '<div class="field"><span>Wurfhand</span><div class="seg" id="f_hand"><button data-v="R">Rechts</button><button data-v="L">Links</button></div></div>' +
    (editId != null ? '<button class="btn-glass del" type="button" id="pfDel">Spieler löschen</button>' : '') +
    '<div class="btns"><button class="btn-glass" type="button" id="pfCancel">Abbrechen</button><button class="btn-cta" type="submit">Spieler speichern</button></div>';
  var upd = function () {
    d.name = $('#f_name').value; d.nick = $('#f_nick').value; d.spoken = $('#f_spoken').value;
    $('#pfName').textContent = d.name || 'Name';
    $('#pfSay').textContent = 'Ansage: „' + cleanSpeech(fill(T.next, {name: d.spoken || d.name || 'Name'})) + '“';
  };
  ['f_name', 'f_nick', 'f_spoken'].forEach(function (k) { $('#' + k).oninput = upd; });
  var big = function () { $('#pfAv').innerHTML = avatar(avP(d), 136, true); $('#pfAvMini').innerHTML = avatar(avP(d), 40); };
  big();
  $('#pfAv').onclick = $('#pfAvEdit').onclick = function () { openAvSheet(d, big); };
  $('#f_name').onchange = function () { upd(); big(); };
  var setColor = function (c) { d.color = c; $$('.swatches [data-c]', f).forEach(function (x) { x.classList.toggle('on', x.dataset.c === c); }); big(); };
  $$('.swatches [data-c]', f).forEach(function (b) { b.onclick = function () { setColor(b.dataset.c); }; });
  $('#pfRndColor').onclick = function () { setColor(randColor([d.color])); };
  segment($('#f_hand'), d.hand, function (v) { d.hand = v; });
  $('#pfPlay').onclick = function () { speak(fill(T.next, {name: d.spoken || d.name}), true); };
  $('#pfCancel').onclick = function () { edit(null); };
  if ($('#pfDel')) {
    var del = function () { api('/api/players/' + editId, 'DELETE').then(function () { toast('Spieler gelöscht', d.name + ' · Statistik bleibt erhalten', 'ok'); editId = null; draft = null; refreshPlayers().then(loadPlayers); }); };
    if (typeof holdToConfirm === 'function') holdToConfirm($('#pfDel'), del, {hint: 'Gedrückt halten zum Löschen'});   // D1
    else $('#pfDel').onclick = function () { if (confirm(d.name + ' löschen? Statistik bleibt erhalten.')) del(); };
  }
  f.onsubmit = function (e) {
    e.preventDefault(); upd();
    if (!d.name.trim()) return toast('Name fehlt', '', 'info');
    var body = {name: d.name, nick: d.nick, spoken: d.spoken, seed: d.seed || d.name, hand: d.hand, color: d.color, av_style: d.av_style || '', av_bg: d.av_bg || 'player', av_accent: d.av_accent || 'ci'};
    (editId != null ? api('/api/players/' + editId, 'PUT', body) : api('/api/players', 'POST', body)).then(function (p) {
      toast('Spieler gespeichert', p.name, 'ok'); editId = p.id; draft = null; preloadAvatars([p]); refreshPlayers().then(loadPlayers);
    }, function (e2) { toast('Nicht gespeichert', e2 && e2.detail, 'warn'); });
  };
}
function refreshPlayers() { return api('/api/players').then(function (ps) { PLAYERS = ps; applyDisplay(); }); }

/* Avatar-Editor: alle Stile, viele Motive, Grund- und Akzentfarbe (nur CI) – Vorschau live */
var AV_STYLES = null;
var AV_BG = [['player', 'Spielerfarbe'], ['none', 'Hell'], ['#DDF96A', 'Lime'], ['#F3FFAC', 'Lime hell'], ['#FF6B5E', 'Coral'], ['#3DBB7A', 'Mint'],
  ['#7FDDEB', 'Aqua'], ['#2AAFC4', 'Aqua stark'], ['#FFD66B', 'Sonne'], ['#BDC8CB', 'Slate'], ['#202020', 'Ink']];
var AV_ACC = [['ci', 'CI-Mix'], ['#DDF96A', 'Lime'], ['#FF6B5E', 'Coral'], ['#3DBB7A', 'Mint'], ['#7FDDEB', 'Aqua'], ['#2AAFC4', 'Aqua stark'],
  ['#FFD66B', 'Sonne'], ['#BDC8CB', 'Slate'], ['#202020', 'Ink']];
function openAvSheet(d, done) {
  if (!AV_STYLES) return api('/api/avatar/styles').then(function (r) { AV_STYLES = r.styles; openAvSheet(d, done); });
  var w = {seed: d.seed || d.name || 'Spieler', av_style: d.av_style || CFG.display.avatar_style || 'notionists', av_bg: d.av_bg || 'player', av_accent: d.av_accent || 'ci'};
  var seeds = [w.seed]; while (seeds.length < 24) seeds.push(rndSeed(d.name));
  var el = document.createElement('div'); el.className = 'avsheet'; $('#stage').appendChild(el);
  var P = function (x) { return Object.assign({color: d.color}, w, x || {}); };
  var sw = function (list, cur, k) { return list.map(function (c) { var bg = c[0] === 'player' ? d.color : c[0] === 'none' ? '#FFFFFF' : c[0] === 'ci' ? 'conic-gradient(#DDF96A,#FF6B5E,#3DBB7A,#7FDDEB,#FFD66B,#DDF96A)' : c[0];
    return '<button type="button" data-' + k + '="' + c[0] + '" class="' + (c[0] === cur ? 'on' : '') + '" title="' + c[1] + '"><i style="background:' + bg + '"></i>' + c[1] + '</button>'; }).join(''); };
  var draw = function () {
    var acc = AV_STYLES.filter(function (x) { return x[0] === w.av_style; })[0];
    el.innerHTML = '<div class="glass card hi avbox"><div class="card-head"><h2 class="h">Avatar · ' + esc(d.name || 'Spieler') + '</h2><span class="meta">DiceBear · Bilder werden einmal geladen und lokal gespeichert</span></div>' +
      '<div class="avgrid"><div class="avleft"><div class="avbig">' + avatar(P(), 260, true) + '</div>' +
      '<div class="field"><span>Hintergrund</span><div class="avsw">' + sw(AV_BG, w.av_bg, 'bg') + '</div></div>' +
      (acc && acc[2] ? '<div class="field"><span>Akzent (Kleidung/Form)</span><div class="avsw">' + sw(AV_ACC, w.av_accent, 'acc') + '</div></div>' : '<p class="meta">Dieser Stil hat keine Akzentfarbe – Farbe kommt über den Hintergrund.</p>') +
      '</div><div class="avright"><div class="field"><span>Stil · ' + AV_STYLES.length + ' Stile</span><div class="avstyles">' + AV_STYLES.map(function (x) {
        return '<button type="button" data-style="' + x[0] + '" class="' + (x[0] === w.av_style ? 'on' : '') + '">' + avatar(P({av_style: x[0]}), 72) + '<small>' + esc(x[1]) + '</small></button>'; }).join('') + '</div></div>' +
      '<div class="field"><span>Motiv · antippen</span><div class="avseeds">' + seeds.map(function (sd) {
        return '<button type="button" data-seed="' + esc(sd) + '" class="' + (sd === w.seed ? 'on' : '') + '">' + avatar(P({seed: sd}), 64) + '</button>'; }).join('') + '</div></div></div></div>' +
      '<div class="btns"><button class="btn-glass" type="button" data-more>⟳ Neue Vorschläge</button><span style="flex:1"></span><button class="btn-glass" type="button" data-x>Abbrechen</button><button class="btn-cta" type="button" data-ok>Übernehmen</button></div></div>';
    $$('[data-style]', el).forEach(function (b) { b.onclick = function () { w.av_style = b.dataset.style; draw(); }; });
    $$('[data-seed]', el).forEach(function (b) { b.onclick = function () { w.seed = b.dataset.seed; draw(); }; });
    $$('[data-bg]', el).forEach(function (b) { b.onclick = function () { w.av_bg = b.dataset.bg; draw(); }; });
    $$('[data-acc]', el).forEach(function (b) { b.onclick = function () { w.av_accent = b.dataset.acc; draw(); }; });
    $('[data-more]', el).onclick = function () { seeds = [w.seed]; while (seeds.length < 24) seeds.push(rndSeed(d.name)); draw(); };
    $('[data-x]', el).onclick = function () { el.remove(); };
    $('[data-ok]', el).onclick = function () { d.seed = w.seed; d.av_style = w.av_style; d.av_bg = w.av_bg; d.av_accent = w.av_accent; el.remove(); done(); };
  };
  draw();
}
