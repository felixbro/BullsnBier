/* ---------- Statistik ---------- */
let statPid = null;
async function loadStats() {
  const ps = await api('/api/players');
  $('#plist').innerHTML = ps.map(p => `<button data-id="${p.id}" class="${p.id === statPid ? 'on' : ''}">${esc(p.name)}</button>`).join('');
  $$('#plist button').forEach(b => b.onclick = () => { statPid = +b.dataset.id; loadStats(); });
  if (statPid) {
    const s = await api('/api/stats/' + statPid), name = ps.find(p => p.id === statPid)?.name;
    const k = (v, l) => `<div class="kpi"><b>${v ?? 0}</b><span>${l}</span></div>`;
    const pl = ps.find(p => p.id === statPid);
    $('#pstats').innerHTML = `<h2>${esc(name)} <button id="delP" style="float:right">Löschen</button></h2>
      <div class="row" style="margin-bottom:14px"><input id="pName" value="${esc(pl.name)}" placeholder="Name">
        <input id="pSpoken" value="${esc(pl.spoken)}" placeholder="Aussprache (optional, z. B. Ma-rei)">
        <button id="pHear">▶</button><button id="pSave">Speichern</button></div><div class="kpis">
      ${k(s.avg3, '3-Dart-Ø')}${k(s.first9, 'First 9 Ø')}${k(s.co_pct + '%', 'Checkout-Quote')}${k(s.best_co, 'Höchstes Finish')}
      ${k(s.t180, '180er')}${k(s.t140, '140+')}${k(s.t100, '100+')}${k(s.all_wins + '/' + s.all_games, 'Siege/Spiele')}</div>
      ${spark(s.history.map(h => h.avg || 0))}`;
    $('#pHear').onclick = () => { const T = CFG.texts[CFG.caller.lang];
      speak(fill(T.next, {name: $('#pSpoken').value.trim() || $('#pName').value.trim()}), true); };
    $('#pSave').onclick = async () => { await api('/api/players/' + statPid, 'PUT',
      {name: $('#pName').value, spoken: $('#pSpoken').value}); toast('Gespeichert'); loadStats(); };
    $('#delP').onclick = async () => { if (confirm('Spieler löschen?')) { await api('/api/players/' + statPid, 'DELETE'); statPid = null; loadStats(); } };
  } else $('#pstats').innerHTML = '<span class="hint">Spieler antippen für Statistik.</span>';
  const gs = await api('/api/games');
  $('#glist').innerHTML = gs.map(g => `<div class="glist"><div><span>${new Date(g.ts * 1000).toLocaleString('de-DE')} · ${MODE_NAMES[g.mode] || g.mode} · ${g.players.map(esc).join(', ')}</span><b>${esc(g.winner || '')}</b></div></div>`).join('') || '<span class="hint">Noch keine Spiele.</span>';
}
function spark(v) {
  if (v.length < 2) return '';
  const mx = Math.max(...v, 1), mn = Math.min(...v, 0), w = 300, h = 80;
  const pts = v.map((y, i) => `${i * w / (v.length - 1)},${h - 6 - (y - mn) / (mx - mn || 1) * (h - 12)}`).join(' ');
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="#f2c14e" stroke-width="2" vector-effect="non-scaling-stroke"/></svg><div class="hint">3-Dart-Ø der letzten ${v.length} Spiele</div>`;
}
$('#addPlayer').onclick = async () => { const n = $('#newPlayer').value.trim(); if (!n) return;
  await api('/api/players', 'POST', {name: n}); $('#newPlayer').value = ''; loadStats(); };


tabHooks.stats = loadStats;
$('#newPlayer').onkeydown = e => e.key === 'Enter' && $('#addPlayer').click();
