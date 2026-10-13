/* 13 · Einstellungen: Anzeige, Sprachausgabe, Ansagetexte, WLED, Kameras, System + Vorschau */
var SUB = LOCAL.sub || 'display', pvKey = 'dart_triple', wledInfo = null;
var TEXT_LABELS = {start: 'Spielstart', single: 'Single', double: 'Double', triple: 'Triple', bull: 'Bullseye (50)', outer: 'Bull (25)', miss: 'Daneben',
  turn: 'Aufnahme-Punkte', noscore: '0 Punkte', t180: '180', bust: 'Überworfen', next: 'Nächster Spieler', remaining: 'Rest (Einzelspieler)',
  next_remaining: 'Nächster Spieler + Rest', target: 'Ziel (ATC, Bermuda …)', leg: 'Leg gewonnen', match: 'Spiel gewonnen', corrected: 'Korrektur',
  takeout: 'Pfeile ziehen', bulloff: 'Bull-Off: wer wirft', bulloff_win: 'Bull-Off: Sieger', shanghai: 'Shanghai', gotcha: 'Gotcha', halved: 'Halbiert',
  unknown: 'Nicht erkannt', cam_error: 'Kamera-Problem'};
var SAMPLE = {name: 'Buschi', score: 40, points: 100, n: 20, dart: 'Triple 20', target: 'Doppel 14'};
var WLED_FX = [[0, 'Solid'], [1, 'Blink'], [2, 'Breathe'], [3, 'Wipe'], [9, 'Rainbow'], [12, 'Fade'], [14, 'Theater Rainbow'], [20, 'Sparkle'],
  [23, 'Strobe'], [24, 'Strobe Rainbow'], [25, 'Multi Strobe'], [28, 'Chase'], [40, 'Scanner'], [41, 'Comet'], [42, 'Fireworks']];
var GROUP_ORDER = ['Status', 'Spiel', 'Wurf', 'Aufnahme', 'Sieg', 'Fehler'];
/* Welche Animation (A/B/C) gehört zu welchem Ereignis – für Vorschau-Text */
var ANIM_INFO = {idle: ['C4', 'Logo schwebt, Tageswertung'], paused: ['C3', 'Badge im Header'], game_start: ['A1', '1,4 s'], bulloff: ['B13', 'Bull pulsiert'],
  next_player: ['B5', '0,6 s'], checkout: ['B6', 'Checkout fährt rein'], takeout: ['B12', 'bis Board leer'], dart_single: ['B1', '0,26 s'], dart_double: ['B2', '0,62 s'],
  dart_triple: ['A2 + B3', '1,2 s'], dart_bull: ['A3', '1,4 s'], dart_miss: ['B4', '0,56 s'], score_100: ['B7', '0,7 s'], score_140: ['B7', '0,7 s'],
  score_180: ['A4', '2,4 s'], score_low: ['B8', '0,6 s'], bust: ['B9', '0,9 s'], halved: ['B10', '0,78 s'], gotcha: ['B11', '0,8 s'], shanghai: ['A6', '1,6 s'],
  high_finish: ['A5', '1,6 s'], leg_won: ['A7', '2,2 s'], match_won: ['A8', 'bis Tippen'], dart_unknown: ['C2', 'bleibt bis behoben'], cal_warn: ['C2', 'bleibt bis behoben'], cam_error: ['C2', 'bleibt bis behoben']};

function loadSettings() {
  $$('.sitem').forEach(function (b) { b.classList.toggle('on', b.dataset.sub === SUB); b.onclick = function () {
    if (b.dataset.sub === 'cams') return showPage('cams');
    SUB = b.dataset.sub; LOCAL.sub = SUB; saveLocal(); loadSettings(); }; });
  $('#sm_voice').textContent = CFG.caller.enabled ? 'an' : 'aus';
  $('#sm_texts').textContent = Object.keys(TEXT_LABELS).length;
  $('#sm_wled').textContent = CFG.wled.enabled ? (wledInfo ? 'verbunden' : 'aktiv') : 'aus';
  var cams = ST && ST.detector && ST.detector.cams;
  $('#sm_cams').textContent = cams ? cams.filter(function (c) { return c.cal; }).length + ' / ' + cams.length : 'Sim';
  ({display: subDisplay, voice: subVoice, texts: subTexts, wled: subWled, system: subSystem}[SUB] || subDisplay)();
  segment($('#intensity'), CFG.display.intensity, function (v) { saveSettings({display: {intensity: v}}); });
  setPreview(pvKey);
}
pageHooks.settings = loadSettings;

function chk(path, label, extra) {
  var v = path.split('.').reduce(function (o, k) { return o && o[k]; }, CFG);
  return '<label class="chk"><input type="checkbox" data-s="' + path + '"' + (v ? ' checked' : '') + '>' + label + (extra || '') + '</label>';
}
function bindChecks(root) {
  $$('[data-s]', root).forEach(function (el) { el.onchange = function () {
    var p = {}, ks = el.dataset.s.split('.'), o = p; ks.slice(0, -1).forEach(function (k) { o = o[k] = {}; }); o[ks[ks.length - 1]] = el.checked;
    saveSettings(p); }; });
}

/* ---------- Anzeige ---------- */
function subDisplay() {
  var groups = {};
  Object.keys(EVENTS).forEach(function (k) { (groups[EVENTS[k].group] = groups[EVENTS[k].group] || []).push(k); });
  var cols = GROUP_ORDER.map(function (g) {
    return '<div><div class="grp">' + g + '</div>' + (groups[g] || []).map(function (k) {
      return chk('display.anim.' + k, EVENTS[k].label, '<button class="btn-icon' + (k === pvKey ? ' on' : '') + '" type="button" data-pv="' + k + '" aria-label="Vorschau ' + esc(EVENTS[k].label) + '">' + PLAY_ICO + '</button>'); }).join('') + '</div>';
  }).join('');
  $('#scontent').innerHTML =
    '<div class="glass card"><h2 class="h">Anzeige</h2>' + chk('display.hide_previous', 'Würfe des Vorspielers ausblenden, sobald der Nächste dran ist') +
    chk('game.auto_next_sim', 'Simulator: nach 3 Darts startet der nächste Klick direkt die nächste Aufnahme') +
    '<div class="field"><span>Cricket · Feld geschlossen</span><div class="seg" id="crfx"><button data-v="sweep">Lichtband</button><button data-v="stamp">Stempel</button><button data-v="burst">Funkenregen</button><button data-v="off">Aus</button></div></div>' +
    '<div class="field"><span>Fassung</span><div class="seg" id="theme"><button data-v="light">Hell</button><button data-v="night">Nacht</button></div></div>' +
    '<div class="field"><span>Gastgeber · Begrüßung und Avatar oben rechts</span><div class="pick" id="hostPick">' + PLAYERS.map(function (p) {
      return '<button type="button" class="pchip' + (hostPlayer() && hostPlayer().id === p.id ? ' on' : '') + '" data-id="' + p.id + '" style="--pc:' + p.color + '">' + avatar(p, 40) + esc(p.name) + '</button>'; }).join('') + '</div></div>' +
    '<label class="field"><span>Standard-Avatarstil · für Gäste und Spieler ohne eigenen Stil</span><select id="avDef"></select></label>' +
    '<div class="field"><span>Spielerfarben · Anzeige und WLED (Farbe wählst du je Spieler)</span><div class="palette">' + PALETTE.map(function (c, i) {
      return '<span><i style="--c:' + c + '"></i>Spieler ' + (i + 1) + '</span>'; }).join('') + '</div></div></div>' +
    '<div class="glass card"><div class="card-head"><h2 class="h">Animationen</h2>' + chk('display.animations', 'Animationen aktiv') + '</div><div class="checks">' + cols + '</div></div>';
  bindChecks($('#scontent'));
  segment($('#theme'), CFG.display.theme, function (v) { saveSettings({display: {theme: v}}); });
  segment($('#crfx'), CFG.display.cricket_fx || 'sweep', function (v) { saveSettings({display: {cricket_fx: v}}); });
  api('/api/avatar/styles').then(function (r) { var sel = $('#avDef'); if (!sel) return;
    sel.innerHTML = r.styles.map(function (x) { return '<option value="' + x[0] + '"' + (x[0] === CFG.display.avatar_style ? ' selected' : '') + '>' + esc(x[1]) + '</option>'; }).join('');
    sel.onchange = function () { saveSettings({display: {avatar_style: sel.value}}); }; });
  $$('#hostPick .pchip').forEach(function (b) { b.onclick = function () { saveSettings({display: {host: +b.dataset.id}}); subDisplay(); }; });
  $$('[data-pv]').forEach(function (b) { b.onclick = function (e) { e.preventDefault(); setPreview(b.dataset.pv, true);
    $$('[data-pv]').forEach(function (x) { x.classList.toggle('on', x === b); }); }; });
}

/* ---------- Sprachausgabe ---------- */
function subVoice() {
  var C = CFG.caller;
  var slider = function (k, l, mn, mx) { return '<label class="slider"><span>' + l + '</span><input type="range" min="' + mn + '" max="' + mx + '" step="0.05" data-r="' + k + '" value="' + C[k] + '"><output>' + (+C[k]).toFixed(2) + '</output></label>'; };
  $('#scontent').innerHTML =
    '<div class="glass card"><div class="card-head"><h2 class="h">Sprachausgabe</h2><span class="meta" id="warmInfo"></span></div>' +
    '<div class="checks two">' + chk('caller.enabled', 'Ansagen aktiv (alle Geräte)') + '<label class="chk"><input type="checkbox" id="localMute"' + (LOCAL.muted ? ' checked' : '') + '>Dieses Gerät stumm</label></div>' +
    '<div class="field"><span>Sprache</span><div class="seg" id="lang"><button data-v="de">Deutsch</button><button data-v="en">English</button></div></div>' +
    '<div class="field"><span>Stimme</span><div class="seg" id="engine"><button data-v="piper">Natürlich (Piper, offline)</button><button data-v="browser">System / Browser</button></div></div>' +
    '<div id="engineBox" class="voices"></div>' + slider('rate', 'Tempo', .6, 1.6) + slider('pitch', 'Tonhöhe', .5, 1.5) + slider('volume', 'Lautstärke', 0, 1) +
    '<div class="row"><button class="btn-glass" id="voiceTest" type="button">Probe abspielen</button></div></div>' +
    '<div class="glass card"><h2 class="h">Was wird angesagt?</h2><div class="checks">' +
    [['say_start', 'Spielstart + wer beginnt'], ['say_dart', 'Jeder einzelne Dart'], ['say_turn', 'Punkte der Aufnahme'], ['say_bust', 'Überworfen'],
     ['say_next', 'Wer als Nächstes dran ist'], ['say_target', 'Ziel (ATC, Bermuda …)'], ['say_specials', 'Shanghai / Gotcha / Halbiert'], ['sfx_bull', 'Sound bei Bullseye (Ansage 1,5 s später)'], ['say_leg', 'Leg gewonnen'],
     ['say_match', 'Spiel gewonnen'], ['say_correction', 'Korrekturen'], ['say_takeout', '„Pfeile ziehen“'], ['say_errors', 'Fehler (Kamera, nicht erkannt)']]
      .map(function (x) { return chk('caller.' + x[0], x[1]); }).join('') + '</div>' +
    '<div class="field"><span>Restpunkte ansagen</span><div class="seg" id="remain"><button data-v="off">Nie</button><button data-v="finish">Nur im Finish-Bereich</button><button data-v="always">Immer</button></div></div></div>';
  bindChecks($('#scontent'));
  $('#localMute').onchange = function (e) { LOCAL.muted = e.target.checked; saveLocal(); if (LOCAL.muted) stopSpeech(); };
  segment($('#lang'), C.lang, function (v) { saveSettings({caller: {lang: v}}); LOCAL.voice = ''; saveLocal(); renderEngine(); });
  segment($('#engine'), C.engine, function (v) { saveSettings({caller: {engine: v}}); renderEngine(); });
  segment($('#remain'), C.say_remaining, function (v) { saveSettings({caller: {say_remaining: v}}); });
  $$('[data-r]').forEach(function (el) { el.oninput = function () { el.nextElementSibling.textContent = (+el.value).toFixed(2); var p = {caller: {}}; p.caller[el.dataset.r] = +el.value; saveSettings(p); }; });
  $('#voiceTest').onclick = function () { var T = CFG.texts[CFG.caller.lang];
    [fill(T.triple, {n: 20}), T.t180, fill(T.next_remaining, {name: (hostPlayer() || {}).name || 'Buschi', score: 40})].forEach(function (t) { speak(t, true); }); };
  renderEngine();
}
function renderEngine() {
  var box = $('#engineBox'), lang = CFG.caller.lang;
  if (!box) return;
  if (CFG.caller.engine === 'browser') {
    var vs = voices().filter(function (v) { return v.lang.toLowerCase().indexOf(lang) === 0; });
    box.innerHTML = (vs.length ? vs.map(function (v) { var on = (pickVoice() || {}).name === v.name;
      return '<button type="button" class="vrow' + (on ? ' on' : '') + '" data-v="' + esc(v.name) + '">' + esc(v.name) + '<span class="meta">' + esc(v.lang) + '</span></button>'; }).join('')
      : '<p class="lead">Keine passende Systemstimme – „Natürlich (Piper)“ klingt ohnehin besser.</p>');
    $$('.vrow', box).forEach(function (b) { b.onclick = function () { LOCAL.voice = b.dataset.v; saveLocal(); renderEngine(); speak(fill(CFG.texts[lang].next, SAMPLE), true); }; });
    return;
  }
  api('/api/tts/voices').then(function (st) {
    var w = st.warm || {}; $('#warmInfo').textContent = w.pending ? 'Ansagen werden vorbereitet … noch ' + w.pending : 'Ansagen vorbereitet';
    if (!st.available) { box.innerHTML = '<p class="lead">Piper fehlt auf dem Rechner: <code>pip install piper-tts</code>, dann neu starten.</p>'; return; }
    var cur = CFG.caller.piper_voice[lang];
    box.innerHTML = st.catalog.filter(function (v) { return v.id.indexOf(lang) === 0; }).map(function (v) {
      return '<div class="vrow' + (v.id === cur ? ' on' : '') + '"><span>' + esc(v.label) + '</span><span class="meta">' + (v.installed ? 'installiert' : v.mb + ' MB') + '</span>' +
        (v.installed ? '<button class="btn-glass" type="button" data-use="' + v.id + '">' + (v.id === cur ? 'Aktiv' : 'Nutzen') + '</button><button class="btn-icon" type="button" data-try="' + v.id + '" aria-label="Probehören">' + PLAY_ICO + '</button>'
          : '<button class="btn-glass" type="button" data-dl="' + v.id + '">Laden</button>') + '</div>'; }).join('');
    $$('[data-use]', box).forEach(function (b) { b.onclick = function () { var p = {caller: {piper_voice: {}}}; p.caller.piper_voice[lang] = b.dataset.use; saveSettings(p); setTimeout(renderEngine, 400); }; });
    $$('[data-try]', box).forEach(function (b) { b.onclick = function () { var old = CFG.caller.piper_voice[lang]; CFG.caller.piper_voice[lang] = b.dataset.try;
      speak(fill(CFG.texts[lang].next_remaining, SAMPLE), true); CFG.caller.piper_voice[lang] = old; }; });
    $$('[data-dl]', box).forEach(function (b) { b.onclick = function () { b.disabled = true; b.textContent = 'Lädt …';
      api('/api/tts/download', 'POST', {voice: b.dataset.dl}).then(function () { toast('Stimme installiert', b.dataset.dl, 'ok'); renderEngine(); },
        function (e) { toast('Download fehlgeschlagen', e && e.detail, 'warn'); renderEngine(); }); }; });
  });
}
if (speechOK) speechSynthesis.onvoiceschanged = function () { if (PAGE === 'settings' && SUB === 'voice') renderEngine(); };

/* ---------- Ansagetexte ---------- */
function subTexts() {
  var lang = CFG.caller.lang, T = CFG.texts[lang];
  $('#scontent').innerHTML = '<div class="glass card"><div class="card-head"><h2 class="h">Ansagetexte · ' + (lang === 'de' ? 'Deutsch' : 'English') + '</h2><span class="meta">Feld leeren = Standard</span></div>' +
    '<p class="meta">Platzhalter: {name} Spieler · {score} Rest · {points} Punkte · {n} Zahl · {dart} Feld · {target} Ziel</p><div class="texts">' +
    Object.keys(TEXT_LABELS).map(function (k) { return '<label class="field"><span>' + TEXT_LABELS[k] + '</span><div class="row"><input data-t="' + k + '" value="' + esc(T[k]) + '">' +
      '<button class="btn-icon" type="button" data-play="' + k + '" aria-label="Abspielen">' + PLAY_ICO + '</button></div></label>'; }).join('') + '</div>' +
    '<div class="row"><button class="btn-glass" id="resetSettings" type="button">Alle Einstellungen auf Standard</button></div></div>';
  $$('[data-t]').forEach(function (el) { el.oninput = function () { var p = {texts: {}}; p.texts[lang] = {}; p.texts[lang][el.dataset.t] = el.value; saveSettings(p); }; });
  $$('[data-play]').forEach(function (b) { b.onclick = function () { speak(fill(CFG.texts[lang][b.dataset.play], SAMPLE), true); }; });
  $('#resetSettings').onclick = function () { if (!confirm('Alle Einstellungen zurücksetzen?')) return;
    api('/api/settings', 'DELETE').then(function (s) { CFG = s; applyDisplay(); loadSettings(); }); };
}

/* ---------- WLED ---------- */
var CI_WLED = [['player', 'Spieler'], ['#DDF96A', 'Lime'], ['#F3FFAC', 'Lime hell'], ['#FF6B5E', 'Coral'], ['#3DBB7A', 'Mint'], ['#7FDDEB', 'Aqua'],
  ['#2AAFC4', 'Aqua stark'], ['#FFD66B', 'Sonne'], ['#BDC8CB', 'Slate'], ['#FFFFFF', 'Weiß'], ['#000000', 'Aus']];
function subWled() {
  var fx = (wledInfo && wledInfo.effects.length ? wledInfo.effects.map(function (n, i) { return [i, n]; }) : WLED_FX.slice())
    .filter(function (x) { return x[1] && x[1] !== 'RSVD' && x[1] !== '-'; })
    .sort(function (a, b) { return a[1].localeCompare(b[1], 'de'); });          // nach Namen sortiert
  var presets = Object.keys((wledInfo && wledInfo.presets) || {}).map(function (k) { return [k, wledInfo.presets[k]]; })
    .sort(function (a, b) { return a[1].localeCompare(b[1], 'de'); });
  var groups = {};
  Object.keys(EVENTS).forEach(function (k) { (groups[EVENTS[k].group] = groups[EVENTS[k].group] || []).push(k); });
  var color = function (k, n, c) {
    if (k === 'match_won') { var pl = c === 'player';   // Gewinner darf frei bunt sein
      return '<span class="col"><input type="color" data-f="' + n + '" value="' + (pl ? PALETTE[0] : c) + '"' + (pl ? ' disabled' : '') + '><label title="Spielerfarbe"><input type="checkbox" data-pl="' + n + '"' + (pl ? ' checked' : '') + '>Sp.</label></span>'; }
    var cur = String(c).toUpperCase(), bg = c === 'player' ? 'conic-gradient(' + PALETTE.join(',') + ',' + PALETTE[0] + ')' : cur;
    return '<span class="cisel" style="--c:' + bg + '"><i></i><select data-f="' + n + '" title="Farbe (CI)">' + CI_WLED.map(function (x) {
      return '<option value="' + x[0] + '"' + ((x[0] === 'player' ? c === 'player' : x[0] === cur) ? ' selected' : '') + '>' + x[1] + '</option>'; }).join('') + '</select></span>'; };
  var rows = GROUP_ORDER.map(function (g) { return '<div class="grp meta" style="margin-top:14px">' + g + '</div>' + (groups[g] || []).map(function (k) {
    var e = CFG.wled.effects[k] || {};
    var mid = e.type === 'preset' ? (presets.length ? '<select data-f="ps">' + presets.map(function (p) { return '<option value="' + p[0] + '"' + (p[0] == e.ps ? ' selected' : '') + '>' + esc(p[1]) + '</option>'; }).join('') + '</select>'
        : '<input type="number" data-f="ps" min="1" max="250" value="' + (e.ps || 1) + '" title="Preset-Nummer">') + '<span></span><span></span>'
      : e.type === 'off' ? '<span></span><span></span><span></span>'
      : '<select data-f="fx">' + fx.map(function (x) { return '<option value="' + x[0] + '"' + (x[0] == e.fx ? ' selected' : '') + '>' + esc(x[1]) + '</option>'; }).join('') + '</select>' + color(k, 'c1', e.c1) + color(k, 'c2', e.c2);
    var num = function (f, mn, mx, st) { return e.type === 'fx' || f === 'dur' ? '<input type="number" data-f="' + f + '" min="' + mn + '" max="' + mx + '" step="' + (st || 1) + '" value="' + e[f] + '">' : '<span></span>'; };
    return '<div class="fxrow' + (e.on ? '' : ' off') + '" data-k="' + k + '"><label class="chk"><input type="checkbox" data-f="on"' + (e.on ? ' checked' : '') + '>' + esc(EVENTS[k].label) + '</label>' +
      '<select data-f="type"><option value="fx"' + (e.type === 'fx' ? ' selected' : '') + '>Effekt</option><option value="preset"' + (e.type === 'preset' ? ' selected' : '') + '>Preset</option><option value="off"' + (e.type === 'off' ? ' selected' : '') + '>LEDs aus</option></select>' +
      mid + num('sx', 0, 255) + num('ix', 0, 255) + num('bri', 1, 255) + num('dur', 0, 30, .1) + '<button class="btn-icon" type="button" data-test="' + k + '" aria-label="Testen">' + PLAY_ICO + '</button></div>'; }).join(''); }).join('');
  $('#scontent').innerHTML = '<div class="glass card"><h2 class="h">WLED</h2>' + chk('wled.enabled', 'WLED-Steuerung aktiv') +
    '<label class="field sfield"><span>IP-Adresse(n) · mehrere mit Komma</span><div class="row"><input id="wledHosts" style="flex:1" value="' + esc(CFG.wled.hosts) + '" placeholder="192.168.1.50"><button class="btn-glass" id="wledCheck" type="button">Verbindung prüfen</button></div></label>' +
    '<div class="meta" id="wledInfo">' + (wledInfo ? '✓ ' + esc(wledInfo.name) + ' · WLED ' + esc(wledInfo.ver) + ' · ' + wledInfo.leds + ' LEDs · ' + wledInfo.effects.length + ' Effekte · ' + Object.keys(wledInfo.presets).length + ' Presets' : 'Effektliste kommt vom Gerät, sobald verbunden.') + '</div></div>' +
    '<div class="glass card"><div class="card-head"><h2 class="h">Effekte je Ereignis</h2><span class="meta">Dauer 0 = bleibt · Vorschau endet nach spätestens 10 s</span></div>' +
    '<div class="wide"><div class="fxrow fxhead"><span>Ereignis</span><span>Art</span><span>Effekt / Preset</span><span>Farbe 1</span><span>Farbe 2</span><span>Tempo</span><span>Intens.</span><span>Hell.</span><span>Dauer s</span><span></span></div>' + rows + '</div></div>';
  bindChecks($('#scontent'));
  $('#wledHosts').onchange = function (e) { saveSettings({wled: {hosts: e.target.value.trim()}}); };
  $('#wledCheck').onclick = function () { saveSettings({wled: {hosts: $('#wledHosts').value.trim()}}); $('#wledInfo').textContent = 'Prüfe …';
    setTimeout(function () { api('/api/wled/info').then(function (r) { if (!r.ok) { wledInfo = null; $('#wledInfo').textContent = 'Nicht erreichbar: ' + r.error; return; } wledInfo = r; subWled(); }); }, 450); };
  $$('.fxrow[data-k]').forEach(function (row) {
    var k = row.dataset.k, set = function (f, v) { var p = {wled: {effects: {}}}; p.wled.effects[k] = {}; p.wled.effects[k][f] = v; saveSettings(p); };
    $$('[data-f]', row).forEach(function (el) { el.onchange = function () {
      var f = el.dataset.f, v = el.type === 'checkbox' ? el.checked : (el.type === 'number' || f === 'fx' || f === 'ps') ? +el.value : el.value;
      set(f, v); if (f === 'type' || f === 'on' || el.closest('.cisel')) subWled(); }; });
    $$('[data-pl]', row).forEach(function (el) { el.onchange = function () { set(el.dataset.pl, el.checked ? 'player' : '#DDF96A'); subWled(); }; });
    $('[data-test]', row).onclick = function () { setPreview(k, true);
      api('/api/wled/test/' + k, 'POST', {p: 0, color: (hostPlayer() || {}).color}).then(function (r) {
        if (CFG.wled.hosts && !r.ok) toast('WLED nicht erreichbar', r.error, 'warn', 'wled'); }); };
  });
}

/* ---------- System ---------- */
function subSystem() {
  $('#scontent').innerHTML = '<div class="glass card"><h2 class="h">System</h2><div class="list">' +
    '<div><span>App</span><span>Bulls’n’Bier v1.0</span></div><div><span>Modus</span><span>' + (ST && ST.sim ? 'Simulator' : 'Live mit Kameras') + '</span></div>' +
    '<div><span>Avatare</span><span>DiceBear „Notionists“ · lokal gespeichert</span></div>' +
    '<div><span>Stimmen</span><span>Piper (offline)</span></div></div>' +
    '<p class="meta">Avatare werden beim ersten Anzeigen einmal von api.dicebear.com geladen und danach lokal genutzt – ohne Netz bleibt die Silhouette. Lizenz des Stils: siehe dicebear.com/styles/notionists.</p>' +
    '<div class="row"><button class="btn-glass" id="resetSettings" type="button">Alle Einstellungen auf Standard</button></div></div>';
  $('#resetSettings').onclick = function () { if (!confirm('Alle Einstellungen zurücksetzen?')) return;
    api('/api/settings', 'DELETE').then(function (s) { CFG = s; applyDisplay(); loadSettings(); }); };
}

/* ---------- Vorschau ---------- */
function demoData(k) {
  var h = hostPlayer() || {name: 'Buschi', color: PALETTE[0], seed: 'Buschi'};
  return {d: k === 'dart_bull' ? 'BULL' : 'T20', n: 1, value: 60, darts: k === 'high_finish' ? ['T20', 'T11', 'D14'] : ['T20', 'T20', 'T20'], checkout: 121,
    out: 'DOUBLE OUT', player: h, name: h.name, color: h.color, sub: k === 'match_won' ? '3 : 1 Legs · Ø 84,6' : k === 'leg_won' ? 'Leg gewonnen · 2 : 1' : '501 · Double Out · ' + h.name + ' beginnt'};
}
function setPreview(k, autoplay) {
  pvKey = k;
  var ev = EVENTS[k] || {label: k}, info = ANIM_INFO[k] || ['', ''], e = CFG.wled.effects[k] || {};
  $('#pvName').textContent = ev.label;
  var fxName = (WLED_FX.filter(function (x) { return x[0] == e.fx; })[0] || [0, 'Effekt ' + e.fx])[1];
  if (wledInfo && wledInfo.effects[e.fx]) fxName = wledInfo.effects[e.fx];
  $('#pvRows').innerHTML = '<div><span>Animation</span><span>' + info[0] + ' · ' + info[1] + '</span></div>' +
    '<div><span>WLED</span><span>' + (!e.on ? 'aus' : e.type === 'preset' ? 'Preset ' + e.ps : e.type === 'off' ? 'LEDs aus' : fxName + (e.c1 === 'player' ? ' · Spielerfarbe' : '')) + '</span></div>';
  var demo = demoData(k);
  if (FXA[k]) previewFx(k, demo); else previewB(k, demo);
  $('#pvFull').onclick = function () { if (FXA[k]) { showPage('live'); setTimeout(function () { playA(k, demo, true); }, 60); } else previewB(k, demo); };
  $('#pvFull').disabled = false;
}
function previewB(k, d) {
  var box = $('#pvStage'), dart = function (cls, txt, v, anim) { return '<div class="dart ' + cls + ' ' + anim + '" style="width:300px; height:220px"><b style="font-size:96px">' + txt + '</b><small style="font-size:28px">' + v + '</small></div>'; };
  var body = {
    dart_single: dart('single', 'S5', 5, 'anim-single'), dart_double: dart('double', 'D16', 32, 'anim-double'), dart_miss: dart('miss', 'Miss', 0, 'anim-miss'),
    score_100: '<span class="anim-score" style="font-size:300px; font-weight:200">100</span>', score_140: '<span class="anim-score s140" style="font-size:300px; font-weight:200">140</span>',
    score_low: '<span class="anim-ups" style="font-size:300px; font-weight:200">12<span class="sticker" style="right:-140px; top:0; font-size:40px">Ups</span></span>',
    bust: '<div class="glass anim-bust" style="position:relative; padding:40px 60px; display:flex; gap:40px; align-items:center"><span class="flash"></span><span class="bust-score score" style="font-size:300px">32</span><span class="stamp bust-stamp" style="right:-20px; top:-20px; font-size:40px">Überworfen</span></div>',
    halved: '<span class="anim-halved" style="position:relative; display:inline-block; font-size:300px; font-weight:200"><span class="old">164</span><span class="new" style="position:absolute; left:0; top:0">82</span></span>',
    gotcha: '<div class="pcard anim-gotcha" style="position:relative; width:700px; height:300px; padding:30px"><span class="flash"></span><span class="stamp bust-stamp" style="right:-20px; top:-20px; font-size:40px">Erwischt!</span><div class="top">' + avatar(d.player, 100) + '<div class="who" style="font-size:48px">' + esc(d.name) + '</div></div><div class="bot"><span></span><span class="rest" style="font-size:120px">0</span></div></div>',
    takeout: '<div class="glass hi anim-pull" style="padding:40px 60px; display:flex; gap:30px; align-items:center; font-size:64px"><span class="darts3" style="transform:scale(2.4); margin:0 60px">' + DART_ICO + DART_ICO + DART_ICO + '</span>Pfeile ziehen</div>',
    checkout: '<div class="checkout anim-finishrange" style="width:900px; padding:40px"><div class="lbl" style="font-size:32px"><span class="dot"></span>Checkout · 2 Darts</div><div class="way" style="font-size:150px">T19 · D12</div></div>',
    next_player: '<div class="glass active anim-turn" style="width:1200px; height:520px; padding:60px; display:flex; align-items:center; gap:50px">' + avatar(d.player, 240, true) + '<div style="font-size:140px; font-weight:300">' + esc(d.name) + '</div></div>',
    bulloff: '<div class="anim-bulloff" style="width:420px; height:420px; border-radius:50%; background:#3DBB7A; display:flex; align-items:center; justify-content:center"><div style="width:170px; height:170px; border-radius:50%; background:#FF6B5E"></div></div>',
    idle: '<div class="idle-mark">' + logo(520) + '</div>', paused: '<span class="badge-paused" style="font-size:64px; padding:30px 50px"><span class="dot" style="width:30px; height:30px"></span>Erkennung pausiert</span>',
    dart_unknown: toastHTML('warn', 'Pfeil nicht erkannt', 'Bitte Wurf korrigieren'), cal_warn: toastHTML('warn', 'Kalibrierung ungenau', 'Kameras weichen 31 mm ab'),
    cam_error: toastHTML('warn', 'Kamera 2 fehlt', 'USB-Verbindung prüfen')
  }[k] || '';
  box.innerHTML = '<div class="blob lime" style="left:-160px; top:-120px; width:1100px; height:900px"></div><div class="blob aqua" style="left:1300px; top:80px; width:800px; height:800px"></div>' +
    '<div style="position:absolute; left:0; top:0; width:1920px; height:1080px; display:flex; align-items:center; justify-content:center">' + body + '</div>';
  var el = $('[class*="anim-"], .toast', box); if (el) play(el);
  $$('.anim-halved, .anim-score, .anim-ups, .anim-bust, .anim-gotcha, .anim-turn, .anim-finishrange, .anim-pull, .anim-bulloff', box).forEach(play);
}
function toastHTML(kind, t, s) { return '<div style="transform:scale(2.6); -webkit-transform:scale(2.6)"><div class="toast ' + kind + ' stay" style="position:relative; right:auto; top:auto"><span class="ico">' + ICO[kind] + '</span><span><b style="font-weight:500">' + t + '</b><br><small>' + s + '</small></span></div></div>'; }
