/* Sprachausgabe: Browser-Stimmen oder Piper (Server, natürlich klingend) */
const speechOK = 'speechSynthesis' in window;
const audioQ = []; let audioBusy = false, audioEl = null;

function voices() { return speechOK ? speechSynthesis.getVoices() : []; }
function pickVoice() {
  const lang = CFG?.caller.lang || 'de', vs = voices();
  return vs.find(v => v.name === LOCAL.voice) || vs.find(v => v.lang.replace('_', '-').toLowerCase().startsWith(lang)) || null;
}
/* Punkt nach Zahl wird sonst als Ordinalzahl gelesen („vierzigster“) */
function cleanSpeech(t) { return String(t).trim().replace(/(\d)\s*\.(?=\s*(?:$|[,;!?]))/g, '$1').replace(/\s+/g, ' '); }

function speak(text, force) {
  if (!text || !CFG) return;
  if (!force && (!CFG.caller.enabled || LOCAL.muted)) return;
  text = cleanSpeech(text);
  if (CFG.caller.engine === 'piper') return piperSay(text);
  browserSay(text);
}
function browserSay(text) {
  if (!speechOK) return;
  const u = new SpeechSynthesisUtterance(text), v = pickVoice(), c = CFG.caller;
  if (v) { u.voice = v; u.lang = v.lang; } else u.lang = c.lang === 'de' ? 'de-DE' : 'en-GB';
  u.rate = +c.rate; u.pitch = +c.pitch; u.volume = +c.volume;
  speechSynthesis.speak(u);
}
function piperSay(text) {
  const c = CFG.caller, voice = c.piper_voice?.[c.lang] || '';
  audioQ.push([`/api/tts?voice=${encodeURIComponent(voice)}&rate=${c.rate}&text=${encodeURIComponent(text)}`, text]);
  playNext();
}
function playNext() {
  if (audioBusy || !audioQ.length) return;
  audioBusy = true;
  const [url, text] = audioQ.shift();
  audioEl = new Audio(url); audioEl.volume = +CFG.caller.volume;
  let fin = false;
  const done = () => { if (fin) return; fin = true; audioBusy = false; playNext(); };
  const fallback = () => { if (fin) return; browserSay(text); done();   // keine Piper-Stimme -> Systemstimme
    if (!playNext._warned) { playNext._warned = 1; toast('Piper-Stimme fehlt – Systemstimme wird genutzt (Einstellungen › Sprachausgabe)'); } };
  audioEl.onended = done;
  audioEl.onerror = fallback;
  audioEl.play().catch(e => e.name === 'NotAllowedError' ? done() : fallback());
}
function stopSpeech() { if (speechOK) speechSynthesis.cancel(); audioQ.length = 0; if (audioEl) { audioEl.pause(); audioBusy = false; } }

function fill(t, vars) { return (t || '').replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? ''); }
function spokenName(i) {
  const p = ST?.game?.players?.[i] ?? ST?.bulloff?.players?.[i]; if (!p) return '';
  return (p.spoken || '').trim() || p.name;
}
function dartText(name, T) {
  if (name === 'BULL') return T.bull; if (name === '25') return T.outer; if (name === 'MISS') return T.miss;
  return fill({S: T.single, D: T.double, T: T.triple}[name[0]], {n: name.slice(1)});
}
function callText(c) {
  const C = CFG.caller, T = CFG.texts[C.lang] || CFG.texts.de, name = spokenName(c.p);
  const multi = (ST?.game?.players?.length || 0) > 1;
  switch (c.k) {
    case 'start': return C.say_start ? fill(T.start, {name}) : '';
    case 'dart': return C.say_dart ? dartText(c.d, T) : '';
    case 'turn': if (!C.say_turn) return '';
      return c.points === 180 ? T.t180 : c.points === 0 ? T.noscore : fill(T.turn, {points: c.points});
    case 'bust': return C.say_bust ? T.bust : '';
    case 'halved': return C.say_specials ? T.halved : '';
    case 'gotcha': return C.say_specials ? fill(T.gotcha, {name}) : '';
    case 'shanghai': return C.say_specials ? T.shanghai : '';
    case 'leg': return C.say_leg ? fill(T.leg, {name}) : '';
    case 'match': return C.say_match ? fill(T.match, {name}) : '';
    case 'corrected': return C.say_correction ? fill(T.corrected, {dart: dartText(c.d, T)}) : '';
    case 'takeout': return C.say_takeout ? T.takeout : '';
    case 'bulloff': return C.say_next ? fill(T.bulloff, {name}) : '';
    case 'bulloff_win': return C.say_start ? fill(T.bulloff_win, {name}) : '';
    case 'unknown': return C.say_errors ? T.unknown : '';
    case 'cam_error': return C.say_errors ? T.cam_error : '';
    case 'next': {
      const rem = c.score != null && (C.say_remaining === 'always' || (C.say_remaining === 'finish' && c.finish));
      if (rem) return fill(C.say_next && multi ? T.next_remaining : T.remaining, {name, score: c.score});
      if (c.target && C.say_target) return fill(T.target, {name, target: c.target});
      return C.say_next && multi ? fill(T.next, {name}) : '';
    }
  }
  return '';
}
function announce(calls) {
  if (!calls?.length || !CFG) return;
  // 'start' direkt nach Bull-Off-Sieger nicht doppelt
  const list = calls.some(c => c.k === 'bulloff_win') ? calls.filter(c => c.k !== 'start') : calls;
  const txt = list.map(callText).filter(Boolean);
  if (!txt.length) return;
  if (calls[0].k === 'dart') stopSpeech();
  txt.forEach(t => speak(t));
}
function muteIcon() { $('#voice').textContent = (!CFG?.caller.enabled || LOCAL.muted) ? '🔇' : '🔊'; }
$('#voice').onclick = () => { LOCAL.muted = !LOCAL.muted; saveLocal(); muteIcon();
  if (!LOCAL.muted) speak(CFG?.caller.lang === 'en' ? 'Caller on' : 'Ansage an'); else stopSpeech();
  const lm = $('#localMute'); if (lm) lm.checked = !!LOCAL.muted; };
