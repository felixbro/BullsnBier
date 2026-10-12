/* Spielansicht: Board, Scoreboard, Aufnahme, Korrektur */
let sel = null;   // {ti, i} ausgewählter Dart zur Korrektur
let mult = 'S';

function score(x, y) {
  const r = Math.hypot(x, y);
  if (r <= R.bull) return 'BULL'; if (r <= R.ob) return '25'; if (r > R.do) return 'MISS';
  const a = ((Math.atan2(x, y) * 180 / Math.PI) + 360) % 360;
  const s = SEG[Math.floor(((a + 9) % 360) / 18)];
  if (r >= R.ti && r <= R.to) return 'T' + s; if (r >= R.di) return 'D' + s; return 'S' + s;
}
function arc(r1, r2, a1, a2) {
  const p = (r, a) => [r * Math.sin(a), -r * Math.cos(a)];
  const [x1, y1] = p(r2, a1), [x2, y2] = p(r2, a2), [x3, y3] = p(r1, a2), [x4, y4] = p(r1, a1);
  return `M${x1},${y1}A${r2},${r2} 0 0 1 ${x2},${y2}L${x3},${y3}A${r1},${r1} 0 0 0 ${x4},${y4}Z`;
}
(function drawBoard() {
  let s = `<circle r="200" class="b-surround"/>`;
  SEG.forEach((n, i) => {
    const a1 = (i * 18 - 9) * Math.PI / 180, a2 = (i * 18 + 9) * Math.PI / 180, ev = i % 2 === 0;
    const base = ev ? 'b-dark' : 'b-light', ring = ev ? 'b-red' : 'b-green';
    s += `<path d="${arc(R.ob, R.ti, a1, a2)}" class="${base}" data-f="S${n}"/><path d="${arc(R.ti, R.to, a1, a2)}" class="${ring}" data-f="T${n}"/>`;
    s += `<path d="${arc(R.to, R.di, a1, a2)}" class="${base}" data-f="S${n}"/><path d="${arc(R.di, R.do, a1, a2)}" class="${ring}" data-f="D${n}"/>`;
    const m = i * 18 * Math.PI / 180;
    s += `<text x="${186 * Math.sin(m)}" y="${-186 * Math.cos(m) + 6}" class="b-num" data-n="${n}">${n}</text>`;
  });
  s += `<circle r="${R.ob}" class="b-green" data-f="25"/><circle r="${R.bull}" class="b-red" data-f="BULL"/><g id="hits"></g>
    <text id="hover" text-anchor="middle" pointer-events="none"></text>`;
  $('#board').innerHTML = s;
})();
function boardXY(e) {
  const svg = $('#board'), pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
  const p = pt.matrixTransform(svg.getScreenCTM().inverse()); return [p.x, -p.y];
}
$('#board').addEventListener('click', e => {
  const [x, y] = boardXY(e), name = score(x, y);
  if (sel) { api('/api/edit', 'POST', {...sel, name, pos: [x, y]}); sel = null; return; }
  if (ST?.sim) api('/api/sim/throw', 'POST', {x, y});
  else api('/api/dart', 'POST', {name, pos: [x, y]});
});
$('#board').addEventListener('mousemove', e => {
  const [x, y] = boardXY(e), h = $('#hover');
  h.textContent = score(x, y); h.setAttribute('x', x); h.setAttribute('y', -y - 12);
});
$('#board').addEventListener('mouseleave', () => $('#hover').textContent = '');

/* Ziel-Feld auf dem Board hervorheben (ATC, Bermuda, Shanghai, Segment) */
function highlightTarget(g) {
  $$('#board .tgt').forEach(e => e.classList.remove('tgt'));
  const t = g?.state?.targets?.[g.state.current]; if (!t) return;
  const m = String(t).match(/(\d+)/), n = m ? +m[1] : (/bull/i.test(t) ? 25 : null);
  let sel = [];
  if (/beliebiges Doppel/.test(t)) sel = $$('#board [data-f^="D"]');
  else if (/beliebiges Triple/.test(t)) sel = $$('#board [data-f^="T"]');
  else if (/Bullseye/.test(t)) sel = $$('#board [data-f="BULL"]');
  else if (n === 25) sel = $$('#board [data-f="25"],#board [data-f="BULL"]');
  else if (n) {
    const f = /Doppel/.test(t) ? `D${n}` : /Triple/.test(t) ? `T${n}` : /Single/.test(t) ? `S${n}` : null;
    sel = f ? $$(`#board [data-f="${f}"]`) : $$(`#board [data-f$="${n}"]`).filter(e => e.dataset.f.slice(1) == n);
  }
  sel.forEach(e => e.classList.add('tgt'));
}

/* ---------- Render ---------- */
function render(m) {
  ST = m;
  $('#sim').classList.toggle('hidden', !m.sim);
  renderErrors(m);
  const g = m.game, sb = $('#scoreboard');
  if (m.bulloff) return renderBulloff(m);
  if (!g) {
    $('#gamebar').innerHTML = '';
    sb.innerHTML = `<div class="pl empty"><div class="nm">Kein Spiel</div><div class="meta">„Neu“ → Spiel starten. Freie Würfe werden trotzdem erkannt.</div></div>`;
    $('#turn').innerHTML = ''; $('#checkout').textContent = ''; $('#info').innerHTML = ''; highlightTarget(null); drawHits([]);
    return;
  }
  const s = g.state, hide = CFG?.display?.hide_previous !== false;
  const legs = +g.opts.legs, sets = +g.opts.sets;
  $('#gamebar').innerHTML = `<b>${esc(g.mode_name)}</b> ${modeSummary(g)}
    <span>${sets ? `Set ${s.set + 1} · ` : ''}Leg ${s.leg + 1}${s.round_limit ? ` · Runde ${Math.min(s.round, s.round_limit)}/${s.round_limit}` : ` · Runde ${s.round}`}</span>
    <button id="endGame" class="ghost">Beenden</button>`;
  $('#endGame').onclick = () => confirm('Spiel beenden?') && api('/api/game', 'DELETE');

  sb.innerHTML = g.players.map((p, i) => {
    const v = s.views[i] || {}, cur = i === s.current && s.winner === null;
    const last = s.last_by_player?.[i];
    const lastHTML = hide && last ? `<div class="last">${last.darts.map((d, k) =>
      `<span data-ti="${last.ti}" data-i="${k}" class="${sel && sel.ti === last.ti && sel.i === k ? 'sel' : ''}">${d.name}</span>`).join('')}
      <em>${last.bust ? 'BUST' : last.points != null ? last.points : ''}</em></div>` : '';
    const marks = v.marks ? `<div class="cr">${Object.entries(v.marks).sort((a, b) => (a[0] == 25) - (b[0] == 25) || b[0] - a[0]).map(([k, n]) =>
      `<div class="${n >= 3 ? 'c3' : ''}"><b>${k === '25' ? 'B' : k}</b>${['', '/', '✕', 'ⓧ'][n]}</div>`).join('')}</div>` : '';
    const sl = sets ? `<span class="sets">${'◆'.repeat(s.sets_won[i])}</span>` : '';
    return `<div class="pl ${cur ? 'cur' : ''}" style="--pc:${pcolor(i)}">
      <div class="nm"><span>${esc(p.name)}</span><span class="legs">${sl}${'●'.repeat(s.legs_won[i])}${'○'.repeat(Math.max(0, legs - s.legs_won[i]))}</span></div>
      <div class="sc">${v.main ?? ''}</div>
      <div class="meta">${[esc(v.sub || ''), avgFor(g, i)].filter(Boolean).join(' · ')}</div>
      ${s.targets?.[i] && cur ? `<div class="tg">Ziel: <b>${esc(s.targets[i])}</b></div>` : ''}
      ${marks}${lastHTML}</div>`;
  }).join('');
  $$('#scoreboard .last span').forEach(e => e.onclick = ev => { ev.stopPropagation(); pickSel(+e.dataset.ti, +e.dataset.i); });

  // Aufnahme: bei hide_previous immer die (neue) aktuelle; sonst bis zum Ziehen die letzte
  const showLast = !hide && m.await_takeout && s.last_turn;
  const darts = showLast ? s.last_turn.darts : s.turn.darts;
  const ti = showLast ? s.last_turn.ti : s.turn.ti;
  const who = showLast ? s.last_turn.p : s.current;
  let html = '';
  for (let i = 0; i < 3; i++) { const d = darts[i], on = sel && sel.ti === ti && sel.i === i;
    html += `<div class="d ${d ? '' : 'empty'} ${on ? 'sel' : ''}" data-i="${i}">${d ? d.name : ''}</div>`; }
  html += `<div class="d sum">${darts.reduce((a, d) => a + d.value, 0)}</div>`;
  $('#turn').innerHTML = html;
  $('#turn').style.setProperty('--pc', pcolor(who));
  $$('#turn .d[data-i]').forEach(e => e.onclick = () => { if (darts[+e.dataset.i]) pickSel(ti, +e.dataset.i); });
  $('#checkout').textContent = s.checkout ? s.checkout.join('  ·  ') : '';
  $('#info').innerHTML = s.winner !== null ? `<div class="banner win">🏆 ${esc(g.players[s.winner].name)}</div>`
    : m.await_takeout ? `<div class="banner take">Pfeile ziehen · ${esc(g.players[s.current].name)} ist dran</div>`
    : `<div class="banner who" style="--pc:${pcolor(s.current)}">${esc(g.players[s.current].name)}</div>`;
  $('#btnNext').textContent = m.await_takeout ? 'Pfeile gezogen ⟶' : 'Aufnahme beenden ⟶';
  drawHits(darts, ti);
  highlightTarget(g);
}
function pickSel(ti, i) {
  sel = sel && sel.ti === ti && sel.i === i ? null : {ti, i};
  render(ST); if (sel) toast('Aufs Board tippen oder manuell eingeben zum Korrigieren');
}
function drawHits(darts, ti) {
  $('#hits').innerHTML = darts.map((d, i) => d.pos ?
    `<circle class="hit ${sel && sel.ti === ti && sel.i === i ? 'sel' : ''}" cx="${d.pos[0]}" cy="${-d.pos[1]}" r="5"/>` : '').join('');
}
function avgFor(g, i) {
  if (!['x01', 'random_checkout', 'countup'].includes(g.mode)) return '';
  let pts = 0, n = 0;
  (g.turns || []).filter(t => t.p === i).forEach(t => { n += t.darts.length; pts += t.pts || 0; });
  return n ? `Ø ${(3 * pts / n).toFixed(1)}` : '';
}
function renderBulloff(m) {
  const b = m.bulloff;
  $('#gamebar').innerHTML = `<b>Bull-Off</b><span>${b.round > 1 ? 'Stechen · ' : ''}Wer näher am Bull ist, beginnt</span>`;
  $('#scoreboard').innerHTML = b.players.map((p, i) => { const t = b.throws.find(x => x.p === i);
    return `<div class="pl ${b.current === i ? 'cur' : ''}" style="--pc:${pcolor(i)}"><div class="nm"><span>${esc(p.name)}</span></div>
      <div class="sc">${t ? t.d : '–'}</div><div class="meta">${t ? t.dist + ' mm vom Bull' : b.current === i ? 'wirft' : ''}</div></div>`; }).join('');
  $('#turn').innerHTML = ''; $('#checkout').textContent = '';
  $('#info').innerHTML = `<div class="banner who">${esc(b.players[b.current]?.name || '')} – auf das Bull werfen</div>`;
  drawHits([]); highlightTarget(null);
  $$('#board [data-f="BULL"],#board [data-f="25"]').forEach(e => e.classList.add('tgt'));
}
function renderErrors(m) {
  const errs = [...(m.errors || []).map(e => e.msg)];
  if (m.detector?.paused) errs.push('Erkennung pausiert');
  const b = $('#errbar'); b.classList.toggle('hidden', !errs.length);
  b.innerHTML = errs.map(e => `<span>⚠ ${esc(e)}</span>`).join('') + (errs.length ? `<button onclick="showTab('cams')">Kameras</button>` : '');
}
function modeSummary(g) {
  const o = g.opts, out = {single: 'Straight', double: 'Double', master: 'Master'};
  if (g.mode === 'x01') return `<span>${o.start} · ${out[o.in]} In · ${out[o.out]} Out${o.bull === '50/50' ? ' · Bull 50/50' : ''}</span>`;
  if (g.mode === 'cricket') return `<span>${{standard: 'Standard', cutthroat: 'Cut Throat', noscore: 'No Score'}[o.variant]}${o.numbers === 'tactics' ? ' · Tactics' : ''}</span>`;
  if (g.mode === 'gotcha') return `<span>${o.target} · ${out[o.out]} Out</span>`;
  if (g.mode === 'random_checkout') return `<span>${o.min}–${o.max} · ${out[o.out]} Out</span>`;
  return '';
}

/* ---------- Aktionen ---------- */
$('#btnNext').onclick = () => { sel = null; api('/api/next', 'POST'); };
$('#btnUndo').onclick = () => { sel = null; api('/api/undo', 'POST'); };
$('#btnMiss').onclick = () => manual('MISS');
function manual(name) { if (sel) { api('/api/edit', 'POST', {...sel, name}); sel = null; } else api('/api/dart', 'POST', {name}); }
$$('.mult button').forEach(b => b.onclick = () => { mult = b.dataset.m; $$('.mult button').forEach(x => x.classList.toggle('on', x === b)); });
$('#nums').innerHTML = [...Array(20)].map((_, i) => `<button>${i + 1}</button>`).join('') + `<button data-n="25">25</button><button data-n="BULL">Bull</button>`;
$$('#nums button').forEach(b => b.onclick = () => manual(b.dataset.n || mult + b.textContent));
$$('#sim [data-aim]').forEach(b => b.onclick = () => api('/api/sim/throw', 'POST', {aim: b.dataset.aim}));
$$('#sim [data-ev]').forEach(b => b.onclick = () => api('/api/sim/event/' + b.dataset.ev, 'POST'));
$('#simOut').onclick = () => api('/api/sim/takeout', 'POST');
document.addEventListener('keydown', e => {
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('#btnNext').click(); }
  if (e.key === 'Backspace') $('#btnUndo').click();
  if (e.key === 'Escape') { sel = null; ST && render(ST); }
});
