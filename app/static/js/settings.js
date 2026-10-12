/* Einstellungen: Anzeige, Sprachausgabe, Texte, WLED */
const TEXT_LABELS = {start: 'Spielstart', single: 'Single', double: 'Double', triple: 'Triple', bull: 'Bullseye (50)',
  outer: 'Bull (25)', miss: 'Daneben', turn: 'Aufnahme-Punkte', noscore: '0 Punkte', t180: '180', bust: 'Überworfen',
  next: 'Nächster Spieler', remaining: 'Rest (Einzelspieler)', next_remaining: 'Nächster Spieler + Rest', target: 'Ziel (ATC, Bermuda …)',
  leg: 'Leg gewonnen', match: 'Spiel gewonnen', corrected: 'Korrektur', takeout: 'Pfeile ziehen',
  bulloff: 'Bull-Off: wer wirft', bulloff_win: 'Bull-Off: Sieger', shanghai: 'Shanghai', gotcha: 'Gotcha', halved: 'Halbiert',
  unknown: 'Nicht erkannt', cam_error: 'Kamera-Problem'};
const SAMPLE = {name: 'Felix', score: 40, points: 100, n: 20, dart: 'Triple 20', target: 'Doppel 14'};
const WLED_FX = [[0, 'Solid'], [1, 'Blink'], [2, 'Breathe'], [3, 'Wipe'], [9, 'Rainbow'], [12, 'Fade'], [14, 'Theater Rainbow'],
  [20, 'Sparkle'], [23, 'Strobe'], [24, 'Strobe Rainbow'], [25, 'Multi Strobe'], [28, 'Chase'], [40, 'Scanner'], [41, 'Comet'], [42, 'Fireworks']];
let wledInfo = null;

$$('#subnav button').forEach(b => b.onclick = () => {
  $$('#subnav button').forEach(x => x.classList.toggle('on', x === b));
  $$('#settings .sub').forEach(s => s.classList.toggle('on', s.id === b.dataset.sub));
});

function loadSettings() {
  // generische Felder data-s="pfad"
  $$('#settings [data-s]').forEach(el => {
    const path = el.dataset.s, v = getPath(CFG, path);
    if (el.type === 'checkbox') { el.checked = !!v; el.onchange = () => saveSettings(patchFor(path, el.checked)); }
    else if (el.type === 'range') { el.value = v; const o = el.nextElementSibling; o.textContent = (+v).toFixed(2);
      el.oninput = () => { o.textContent = (+el.value).toFixed(2); saveSettings(patchFor(path, +el.value)); }; }
  });
  $('#localMute').checked = !!LOCAL.muted;
  $('#localMute').onchange = e => { LOCAL.muted = e.target.checked; saveLocal(); muteIcon(); };
  seg($('#lang'), CFG.caller.lang, v => { saveSettings({caller: {lang: v}}); LOCAL.voice = ''; saveLocal(); renderEngine(); renderTexts(); });
  seg($('#remain'), CFG.caller.say_remaining, v => saveSettings({caller: {say_remaining: v}}));
  seg($('#engine'), CFG.caller.engine, v => { saveSettings({caller: {engine: v}}); renderEngine(); });
  $('#voiceTest').onclick = () => { const T = CFG.texts[CFG.caller.lang];
    [fill(T.triple, {n: 20}), T.t180, fill(T.next_remaining, {name: 'Felix', score: 40})].forEach(t => speak(t, true)); };
  $('#resetSettings').onclick = async () => { if (!confirm('Alle Einstellungen zurücksetzen?')) return;
    CFG = await api('/api/settings', 'DELETE'); loadSettings(); };
  renderColors(); renderAnims(); renderEngine(); renderTexts(); renderWled();
}
tabHooks.settings = loadSettings;
function onSettingsChanged() { muteIcon(); if (ST) render(ST); }

/* ---------- Anzeige ---------- */
function renderColors() {
  const cols = CFG.display.player_colors;
  $('#pcolors').innerHTML = cols.map((c, i) => `<label class="pc"><input type="color" value="${c}" data-i="${i}"><span>Spieler ${i + 1}</span></label>`).join('');
  $$('#pcolors input').forEach(el => el.oninput = () => { const c = [...CFG.display.player_colors]; c[+el.dataset.i] = el.value;
    saveSettings({display: {player_colors: c}}); });
}
function renderAnims() {
  const groups = {};
  for (const [k, e] of Object.entries(EVENTS)) if (FX_DEF[k]) (groups[e.group] ??= []).push([k, e.label]);
  $('#animList').innerHTML = Object.entries(groups).map(([g, list]) => `<div><label>${g}</label>${list.map(([k, l]) =>
    `<label class="sw"><input type="checkbox" data-a="${k}" ${CFG.display.anim[k] !== false ? 'checked' : ''}> ${l}
     <button class="mini" data-play="${k}">▶</button></label>`).join('')}</div>`).join('');
  $$('#animList [data-a]').forEach(el => el.onchange = () => saveSettings({display: {anim: {[el.dataset.a]: el.checked}}}));
  $$('#animList [data-play]').forEach(b => b.onclick = e => { e.preventDefault(); playFx(b.dataset.play, demoCtx(b.dataset.play), true); });
}
function demoCtx(k) { return {p: 0, d: k === 'dart_double' ? 'D16' : k === 'dart_triple' ? 'T20' : k === 'dart_bull' ? 'BULL' : 'S5',
  points: k === 'score_140' ? 140 : k === 'score_low' ? 7 : 100, checkout: 121}; }

/* ---------- Stimme ---------- */
async function renderEngine() {
  const box = $('#engineBox'), lang = CFG.caller.lang;
  if (CFG.caller.engine === 'browser') {
    const vs = voices(), match = vs.filter(v => v.lang.toLowerCase().startsWith(lang)), other = vs.filter(v => !match.includes(v));
    box.innerHTML = `<label>Systemstimme (nur dieses Gerät)</label><select id="voiceSel"><option value="">Automatisch</option>${
      [...match, ...other].map(v => `<option ${v.name === LOCAL.voice ? 'selected' : ''}>${esc(v.name)}</option>`).join('')}</select>
      <p class="hint">${!speechOK ? 'Dieser Browser hat keine Sprachausgabe.' : !vs.length ? 'Keine Stimmen gefunden.' :
      !match.length ? 'Keine passende Stimme installiert.' : `Aktiv: ${esc(pickVoice()?.name || '')}`} Systemstimmen klingen oft künstlich – „Natürlich (Piper)“ ist deutlich besser.</p>`;
    $('#voiceSel').onchange = e => { LOCAL.voice = e.target.value; saveLocal(); renderEngine(); };
    return;
  }
  box.innerHTML = '<p class="hint">Lade Stimmen …</p>';
  const st = await api('/api/tts/voices');
  if (!st.available) { box.innerHTML = '<p class="hint warn">Piper ist auf dem DartCam-Rechner nicht installiert: <code>pip install piper-tts</code> (in der .venv), dann neu starten.</p>'; return; }
  const cur = CFG.caller.piper_voice[lang];
  const list = st.catalog.filter(v => v.id.startsWith(lang));
  box.innerHTML = `<label>Piper-Stimme (${lang === 'de' ? 'Deutsch' : 'English'}) – läuft lokal, gilt für alle Geräte</label>
    <div class="voices">${list.map(v => `<div class="vrow ${v.id === cur ? 'on' : ''}">
      <label class="sw"><input type="radio" name="pv" value="${v.id}" ${v.id === cur ? 'checked' : ''} ${v.installed ? '' : 'disabled'}> ${esc(v.label)}</label>
      ${v.installed ? `<button class="mini" data-try="${v.id}">▶</button>` : `<button class="mini" data-dl="${v.id}">Laden (${v.mb} MB)</button>`}</div>`).join('')}</div>
    <p class="hint">Stimmen werden einmalig vom DartCam-Rechner heruntergeladen (Internet nötig), danach offline.</p>`;
  $$('#engineBox [name=pv]').forEach(r => r.onchange = () => { saveSettings({caller: {piper_voice: {[lang]: r.value}}}); renderEngine(); });
  $$('#engineBox [data-try]').forEach(b => b.onclick = () => { const T = CFG.texts[lang], old = CFG.caller.piper_voice[lang];
    CFG.caller.piper_voice[lang] = b.dataset.try; speak(fill(T.next_remaining, {name: 'Felix', score: 40}), true); CFG.caller.piper_voice[lang] = old; });
  $$('#engineBox [data-dl]').forEach(b => b.onclick = async () => {
    b.disabled = true; b.textContent = 'Lädt …';
    try { await api('/api/tts/download', 'POST', {voice: b.dataset.dl});
      if (!list.some(v => v.installed)) saveSettings({caller: {piper_voice: {[lang]: b.dataset.dl}}});
      toast('Stimme installiert'); } catch (e) { toast(e.detail || 'Download fehlgeschlagen'); }
    renderEngine(); });
}
if (speechOK) speechSynthesis.onvoiceschanged = () => { if ($('#settings').classList.contains('on') && CFG.caller.engine === 'browser') renderEngine(); };

/* ---------- Texte ---------- */
function renderTexts() {
  const lang = CFG.caller.lang, T = CFG.texts[lang];
  $('#textsLang').textContent = lang === 'de' ? '(Deutsch)' : '(English)';
  $('#texts').innerHTML = Object.keys(TEXT_LABELS).map(k => `<label>${TEXT_LABELS[k]}
    <div class="row"><input data-t="${k}" value="${esc(T[k] ?? '')}"><button data-play="${k}">▶</button></div></label>`).join('');
  $$('#texts input').forEach(el => el.oninput = () => saveSettings({texts: {[lang]: {[el.dataset.t]: el.value}}}));
  $$('#texts [data-play]').forEach(b => b.onclick = () => speak(fill(CFG.texts[lang][b.dataset.play], SAMPLE), true));
}

/* ---------- WLED ---------- */
function renderWled() {
  $('#wledHosts').value = CFG.wled.hosts || '';
  $('#wledHosts').onchange = e => saveSettings({wled: {hosts: e.target.value.trim()}});
  $('#wledCheck').onclick = checkWled;
  const fxList = wledInfo?.effects?.length ? wledInfo.effects.map((n, i) => [i, n]) : WLED_FX;
  const presets = Object.entries(wledInfo?.presets || {});
  const groups = {};
  for (const [k, e] of Object.entries(EVENTS)) (groups[e.group] ??= []).push(k);
  $('#wledFx').innerHTML = Object.entries(groups).map(([g, keys]) => `<h3>${g}</h3>` + keys.map(k => {
    const e = CFG.wled.effects[k] || {}, isP = c => c === 'player';
    const color = (n, c) => `<label class="col"><input type="color" data-f="${n}" value="${isP(c) ? pcolor(0) : c}" ${isP(c) ? 'disabled' : ''}>
      <span><input type="checkbox" data-pl="${n}" ${isP(c) ? 'checked' : ''}> Spieler</span></label>`;
    return `<div class="fxrow ${e.on ? '' : 'off'}" data-k="${k}">
      <label class="sw name"><input type="checkbox" data-f="on" ${e.on ? 'checked' : ''}> ${EVENTS[k].label}</label>
      <select data-f="type"><option value="fx" ${e.type === 'fx' ? 'selected' : ''}>Effekt</option><option value="preset" ${e.type === 'preset' ? 'selected' : ''}>Preset</option><option value="off" ${e.type === 'off' ? 'selected' : ''}>LEDs aus</option></select>
      ${e.type === 'preset'
        ? (presets.length ? `<select data-f="ps">${presets.map(([id, n]) => `<option value="${id}" ${id == e.ps ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select>`
                          : `<input type="number" data-f="ps" min="1" max="250" value="${e.ps || 1}" title="Preset-Nummer">`)
        : e.type === 'off' ? '' : `<select data-f="fx">${fxList.map(([i, n]) => `<option value="${i}" ${i == e.fx ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select>
          ${color('c1', e.c1)}${color('c2', e.c2)}
          <label class="num">Tempo<input type="number" data-f="sx" min="0" max="255" value="${e.sx}"></label>
          <label class="num">Intens.<input type="number" data-f="ix" min="0" max="255" value="${e.ix}"></label>
          <label class="num">Hell.<input type="number" data-f="bri" min="1" max="255" value="${e.bri}"></label>`}
      <label class="num">Dauer s<input type="number" data-f="dur" min="0" max="30" step="0.1" value="${e.dur}"></label>
      <button class="mini" data-test="${k}">▶</button></div>`; }).join('')).join('');
  $$('#wledFx .fxrow').forEach(row => {
    const k = row.dataset.k, set = (f, v) => saveSettings({wled: {effects: {[k]: {[f]: v}}}});
    row.querySelectorAll('[data-f]').forEach(el => el.onchange = () => {
      const f = el.dataset.f, v = el.type === 'checkbox' ? el.checked : el.type === 'number' || f === 'fx' || f === 'ps' ? +el.value : el.value;
      set(f, v); if (f === 'type' || f === 'on') renderWled(); });
    row.querySelectorAll('[data-pl]').forEach(el => el.onchange = () => {
      set(el.dataset.pl, el.checked ? 'player' : '#ffffff'); renderWled(); });
    row.querySelector('[data-test]').onclick = async () => {
      const r = await api(`/api/wled/test/${k}`, 'POST', {p: 0});
      if (!r.ok && CFG.wled.enabled) toast('WLED: ' + r.error);
      else if (!CFG.wled.enabled || !CFG.wled.hosts) toast('Nur Browser-Animation – WLED ist aus oder ohne IP');
    };
  });
}
async function checkWled() {
  saveSettings({wled: {hosts: $('#wledHosts').value.trim()}});
  await new Promise(r => setTimeout(r, 450));
  $('#wledInfo').textContent = 'Prüfe …';
  const r = await api('/api/wled/info');
  if (!r.ok) { $('#wledInfo').innerHTML = `<span class="warn">Nicht erreichbar: ${esc(r.error)}</span>`; wledInfo = null; return; }
  wledInfo = r;
  $('#wledInfo').innerHTML = `✓ <b>${esc(r.name)}</b> · WLED ${esc(r.ver)} · ${r.leds} LEDs · ${r.effects.length} Effekte · ${Object.keys(r.presets).length} Presets`;
  renderWled();
}
