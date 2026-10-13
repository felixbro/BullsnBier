/* Sprachausgabe: Piper (Server, natürlich, vorberechnet) oder Systemstimme des Browsers */
var speechOK = 'speechSynthesis' in window;
var audioQ = [], audioBusy = false, audioEl = null, piperWarned = false;

function voices() { return speechOK ? speechSynthesis.getVoices() : []; }
function pickVoice() {
  var lang = (CFG && CFG.caller.lang) || 'de', vs = voices();
  return vs.filter(function (v) { return v.name === LOCAL.voice; })[0] ||
    vs.filter(function (v) { return v.lang.replace('_', '-').toLowerCase().indexOf(lang) === 0; })[0] || null;
}
/* Punkt nach Zahl am Satzende würde als Ordinalzahl gelesen („vierzigster“) */
function cleanSpeech(t) { return String(t).trim().replace(/(\d)\s*\.(?=\s*(?:$|[,;!?]))/g, '$1').replace(/\s+/g, ' '); }
function fill(t, v) { return (t || '').replace(/\{(\w+)\}/g, function (_, k) { return v[k] == null ? '' : v[k]; }); }

function speak(text, force) {
  if (!text || !CFG) return;
  if (!force && (!CFG.caller.enabled || LOCAL.muted)) return;
  text = cleanSpeech(text);
  if (CFG.caller.engine === 'piper') return piperSay(text);
  browserSay(text);
}
function browserSay(text) {
  if (!speechOK) return;
  var u = new SpeechSynthesisUtterance(text), v = pickVoice(), c = CFG.caller;
  if (v) { u.voice = v; u.lang = v.lang; } else u.lang = c.lang === 'de' ? 'de-DE' : 'en-GB';
  u.rate = +c.rate; u.pitch = +c.pitch; u.volume = +c.volume;
  speechSynthesis.speak(u);
}
function piperSay(text) {
  var c = CFG.caller, voice = (c.piper_voice || {})[c.lang] || '';
  audioQ.push(['/api/tts?voice=' + encodeURIComponent(voice) + '&rate=' + c.rate + '&text=' + encodeURIComponent(text), text]);
  playNext();
}
function playNext() {
  if (audioBusy || !audioQ.length) return;
  audioBusy = true;
  var item = audioQ.shift(), fin = false;
  audioEl = new Audio(item[0]); audioEl.volume = +CFG.caller.volume;
  var done = function () { if (fin) return; fin = true; audioBusy = false; playNext(); };
  var fallback = function () { if (fin) return; browserSay(item[1]); done();
    if (!piperWarned) { piperWarned = true; toast('Piper-Stimme fehlt', 'Systemstimme wird genutzt', 'info'); } };
  audioEl.onended = done; audioEl.onerror = fallback;
  var p = audioEl.play(); if (p && p.catch) p.catch(function (e) {
    if (e && e.name === 'NotAllowedError') { fin = true; audioBusy = false; audioQ.unshift(item); needUnlock(); } else fallback(); });
}
/* Browser spielen Ton erst nach einer Berührung ab (Autoplay-Sperre) */
var unlockShown = false;
function needUnlock() {
  if (unlockShown) return; unlockShown = true;
  toast('Einmal tippen für Ton', 'Der Browser gibt Ansagen erst nach einer Berührung frei', 'info', 'unlock');
  var go = function () { document.removeEventListener('pointerdown', go, true); unlockShown = false; clearToast('unlock');
    if (audioQ.length > 3) audioQ.splice(0, audioQ.length - 3); playNext(); };
  document.addEventListener('pointerdown', go, true);
}
function stopSpeech() { clearTimeout(announce.t); clearInterval(announce.w); if (speechOK) speechSynthesis.cancel(); audioQ.length = 0; if (audioEl) { audioEl.pause(); audioBusy = false; } }
/* Soundeffekte (z. B. Bullseye) – unabhängig von der Stimme, aber mit derselben Lautstärke/Stummschaltung */
var SFX = {bull: '/static/sounds/bullseye.mp3', win: '/static/sounds/winner.mp3'}, SFX_WAIT = {bull: 1500}, sfxEl = {};
function sfx(name) {
  if (!CFG || LOCAL.muted) return false;
  var a = sfxEl[name] = sfxEl[name] || new Audio(SFX[name]);
  a.volume = +CFG.caller.volume || 1; a.currentTime = 0;
  var p = a.play(); if (p && p.catch) p.catch(function (e) { if (e && e.name === 'NotAllowedError') needUnlock(); });
  return true;
}

function spokenName(i) { var p = pOf(i); return p ? ((p.spoken || '').trim() || p.name) : ''; }
function dartText(name, T) {
  if (name === 'BULL') return T.bull; if (name === '25') return T.outer; if (name === 'MISS') return T.miss;
  return fill({S: T.single, D: T.double, T: T.triple}[name[0]], {n: name.slice(1)});
}
function callText(c) {
  var C = CFG.caller, T = CFG.texts[C.lang] || CFG.texts.de, name = spokenName(c.p);
  var multi = ((ST && ST.game && ST.game.players.length) || 0) > 1;
  switch (c.k) {
    case 'start': return C.say_start ? fill(T.start, {name: name}) : '';
    case 'dart': return C.say_dart ? dartText(c.d, T) : '';
    case 'turn': if (!C.say_turn) return '';
      return c.points === 180 ? T.t180 : c.points === 0 ? T.noscore : fill(T.turn, {points: c.points});
    case 'bust': return C.say_bust ? T.bust : '';
    case 'halved': return C.say_specials ? T.halved : '';
    case 'gotcha': return C.say_specials ? fill(T.gotcha, {name: name}) : '';
    case 'shanghai': return C.say_specials ? T.shanghai : '';
    case 'leg': return C.say_leg ? fill(T.leg, {name: name}) : '';
    case 'match': return C.say_match ? fill(T.match, {name: name}) : '';
    case 'corrected': return C.say_correction ? fill(T.corrected, {dart: dartText(c.d, T)}) : '';
    case 'takeout': return C.say_takeout ? T.takeout : '';
    case 'bulloff': return C.say_next ? fill(T.bulloff, {name: name}) : '';
    case 'bulloff_win': return C.say_start ? fill(T.bulloff_win, {name: name}) : '';
    case 'unknown': return C.say_errors ? T.unknown : '';
    case 'cam_error': return C.say_errors ? T.cam_error : '';
    case 'next':
      var rem = c.score != null && (C.say_remaining === 'always' || (C.say_remaining === 'finish' && c.finish));
      if (rem) return fill(C.say_next && multi ? T.next_remaining : T.remaining, {name: name, score: c.score});
      if (c.target && C.say_target) return fill(T.target, {name: name, target: c.target});
      return C.say_next && multi ? fill(T.next, {name: name}) : '';
  }
  return '';
}
function announce(calls) {
  if (!calls || !calls.length || !CFG) return;
  var list = calls.some(function (c) { return c.k === 'bulloff_win'; }) ? calls.filter(function (c) { return c.k !== 'start'; }) : calls;
  var txt = list.map(callText).filter(Boolean);
  if (calls.some(function (c) { return c.k === 'start' || c.k === 'bulloff'; })) { clearInterval(announce.w); if (sfxEl.win) sfxEl.win.pause(); }   // neues Spiel → Jingle aus
  var win = CFG.caller.sfx_win !== false && calls.some(function (c) { return c.k === 'match'; });
  var fx = !win && CFG.caller.sfx_bull !== false && calls.some(function (c) { return c.k === 'dart' && c.d === 'BULL'; }) ? 'bull' : null;
  if (calls[0].k === 'dart') stopSpeech();
  if (win) {   // Sieg: erst Ansage, dann – wenn alles gesagt ist und der Sieger-Screen steht – der Jingle
    txt.forEach(function (t) { speak(t); });
    var t0 = Date.now();
    clearInterval(announce.w);
    announce.w = setInterval(function () {
      var talking = audioBusy || audioQ.length || (speechOK && speechSynthesis.speaking);
      if ((!talking && Date.now() - t0 > 2200) || Date.now() - t0 > 15000) { clearInterval(announce.w); sfx('win'); }
    }, 200);
    return;
  }
  if (fx && sfx(fx)) {   // erst Sound, dann Ansage
    if (txt.length) announce.t = setTimeout(function () { txt.forEach(function (t) { speak(t); }); }, SFX_WAIT[fx]);
    return;
  }
  if (!txt.length) return;
  txt.forEach(function (t) { speak(t); });
}
