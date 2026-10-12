/* Browser-Animationen – gleiche Ereignisse wie WLED */
const FX_DEF = {
  game_start:   {t: () => 'GAME ON', cls: 'pop', col: '#1f9d5c', ms: 1300},
  next_player:  {t: c => pname(c.p), sub: () => 'ist dran', cls: 'slide', col: c => pcolor(c.p), ms: 1200},
  checkout:     {t: c => pname(c.p), sub: c => `Finish ${ST?.game ? (gameRem(c.p) ?? '') : ''}`, cls: 'slide', col: c => pcolor(c.p), ms: 1400},
  dart_single:  {t: c => c.d, cls: 'mini', col: '#ffffff', ms: 600},
  dart_double:  {t: c => c.d, cls: 'flash', col: '#1f9d5c', ms: 900},
  dart_triple:  {t: c => c.d, cls: 'flash', col: '#e2412f', ms: 900},
  dart_bull:    {t: c => c.d === 'BULL' ? 'BULLSEYE' : 'BULL', cls: 'flash', col: '#e2412f', ms: 1100},
  dart_miss:    {t: () => 'MISS', cls: 'shake', col: '#ff7a00', ms: 900},
  score_low:    {t: c => c.points, cls: 'sad', col: '#555', ms: 1000},
  score_100:    {t: c => c.points, cls: 'pop', col: '#f2c14e', ms: 1500},
  score_140:    {t: c => c.points, cls: 'pop big', col: '#f2c14e', ms: 1800},
  score_180:    {t: () => '180', cls: 'rainbow', col: '#ffffff', ms: 2800},
  bust:         {t: () => 'BUST', cls: 'shake', col: '#e2412f', ms: 1600},
  halved:       {t: () => '÷ 2', sub: () => 'Halbiert', cls: 'shake', col: '#e2412f', ms: 1500},
  gotcha:       {t: () => 'GOTCHA', sub: c => `${pname(c.p)} → 0`, cls: 'pop', col: '#a24bff', ms: 1800},
  shanghai:     {t: () => 'SHANGHAI', cls: 'rainbow', col: '#ffffff', ms: 2800},
  high_finish:  {t: c => c.checkout, sub: c => `FINISH · ${pname(c.p)}`, cls: 'rainbow', col: '#f2c14e', ms: 2800},
  leg_won:      {t: () => 'LEG', sub: c => pname(c.p), cls: 'pop', col: c => pcolor(c.p), ms: 2200},
  dart_unknown: {t: () => '?', sub: () => 'Pfeil nicht erkannt', cls: 'shake', col: '#ff7a00', ms: 1600},
  cal_warn:     {t: () => '⚠', sub: () => 'Kalibrierung prüfen', cls: 'shake', col: '#f2c14e', ms: 2000},
  cam_error:    {t: () => '⚠', sub: () => 'Kamera-Problem', cls: 'shake', col: '#e2412f', ms: 2000},
  bulloff:      {t: () => 'BULL-OFF', sub: c => pname(c.p) + ' wirft', cls: 'pop', col: '#e2412f', ms: 1500},
  takeout:      {t: () => 'Pfeile ziehen', cls: 'mini', col: '#ffffff', ms: 900},
  idle:         {t: () => 'DartCam', cls: 'mini', col: '#ffffff', ms: 900},
  paused:       {t: () => 'Pausiert', cls: 'mini', col: '#0040ff', ms: 900},
  match_won:    {t: c => pname(c.p), sub: () => 'GEWINNT', cls: 'win', col: c => pcolor(c.p), ms: 4000},
};
const fxQ = []; let fxBusy = false, lastBase = null;

function gameRem(p) { const v = ST?.game?.state?.views?.[p]; return v?.main; }
function animOn(key) { return CFG?.display?.animations && CFG.display.anim?.[key] !== false && FX_DEF[key]; }
const val = (v, c) => typeof v === 'function' ? v(c) : v;

function playFx(key, ctx = {}, force) {
  if (!force && !animOn(key)) return;
  // veraltete "ist dran"-Einblendungen verwerfen, sobald neue Würfe kommen
  if (!['next_player', 'checkout', 'bulloff'].includes(key)) for (let i = fxQ.length - 1; i >= 0; i--)
    if (['next_player', 'checkout', 'bulloff'].includes(fxQ[i][0])) fxQ.splice(i, 1);
  fxQ.push([key, ctx]); if (fxQ.length > 3) fxQ.splice(0, fxQ.length - 3);
  runFx();
}
function runFx() {
  if (fxBusy || !fxQ.length) return;
  const [key, c] = fxQ.shift(), d = FX_DEF[key], el = $('#fx');
  fxBusy = true;
  el.className = 'fx';
  el.style.setProperty('--fx', val(d.col, c));
  el.querySelector('.fx-text').textContent = val(d.t, c) ?? '';
  el.querySelector('.fx-sub').textContent = d.sub ? val(d.sub, c) : '';
  void el.offsetWidth;
  el.classList.add('show', ...d.cls.split(' '));
  if (key === 'score_180' || key === 'high_finish' || key === 'shanghai') confetti(80);
  setTimeout(() => { el.className = 'fx'; fxBusy = false; runFx(); }, d.ms);
}

/* Server-Ereignis verarbeiten */
function handleFx(m) {
  const fx = m.fx; if (!fx) return;
  if (fx.trigger) {
    const data = (m.calls || []).find(c => c.d || c.points != null || c.checkout) || {};
    playFx(fx.trigger, {...data, ...fx.ctx});
  }
  const base = fx.base + ':' + (fx.base_ctx?.p ?? '');
  if (base !== lastBase) {
    if (lastBase !== null && ['next_player', 'checkout', 'bulloff'].includes(fx.base) && !m.takeout_only) playFx(fx.base, fx.base_ctx);
    lastBase = base;
  }
  winner(fx.base === 'match_won' ? fx.base_ctx.p : null);
  document.body.dataset.base = fx.base;
  document.body.style.setProperty('--cur', pcolor(fx.base_ctx?.p ?? ST?.game?.state?.current));
}

/* Sieger-Overlay bleibt bis Klick / neues Spiel */
let winShown = null;
function winner(p) {
  let w = $('#winner');
  if (p == null) { w?.remove(); winShown = null; return; }
  if (winShown === p || !CFG?.display?.animations || CFG.display.anim?.match_won === false) return;
  winShown = p;
  w?.remove(); w = document.createElement('div'); w.id = 'winner'; w.className = 'winner';
  w.style.setProperty('--fx', pcolor(p));
  w.innerHTML = `<div class="trophy">🏆</div><div class="wname">${esc(pname(p))}</div><div class="wsub">gewinnt!</div>
    <div class="row"><button id="wAgain" class="big">Nochmal</button><button id="wClose">Schließen</button></div>`;
  document.body.appendChild(w);
  w.querySelector('#wClose').onclick = () => w.remove();
  w.querySelector('#wAgain').onclick = () => { w.remove(); rematch(); };
  confetti(160);
}
function rematch() {
  const g = ST?.game; if (!g) return;
  const ps = g.players.map(p => p.id ?? p.name);
  const opts = {...g.opts}; delete opts.seed;
  api('/api/game', 'POST', {mode: g.mode, players: [...ps.slice(1), ps[0]], opts});
}
function confetti(n) {
  const box = document.createElement('div'); box.className = 'confetti';
  const cols = ['#e2412f', '#1f9d5c', '#f2c14e', '#2f80ed', '#ffffff', '#a24bff'];
  for (let i = 0; i < n; i++) {
    const s = document.createElement('i');
    s.style.left = Math.random() * 100 + 'vw'; s.style.background = cols[i % cols.length];
    s.style.animationDelay = Math.random() * .6 + 's'; s.style.animationDuration = 1.8 + Math.random() * 1.6 + 's';
    s.style.transform = `rotate(${Math.random() * 360}deg)`;
    box.appendChild(s);
  }
  document.body.appendChild(box); setTimeout(() => box.remove(), 4200);
}
