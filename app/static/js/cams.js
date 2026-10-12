/* ---------- Kameras ---------- */
const CALK = ['20', '6', '3', '11'];
async function loadCams() {
  const info = ST?.detector;
  if (!info?.running) { $('#camlist').innerHTML = '<div class="card hint">Simulator-Modus oder Erkennung läuft nicht.</div>'; return; }
  $('#fps').textContent = `${info.fps} fps`;
  $('#detPause').textContent = info.paused ? 'Erkennung fortsetzen' : 'Erkennung pausieren';
  const cal = await api('/api/cal');
  $('#camlist').innerHTML = info.cams.map(c => `
    <div class="cam" data-id="${c.id}">
      <div class="row"><b>Kamera ${+c.id + 1}</b><span class="hint">${esc(c.src)}</span>
        <span class="badge ${c.ok ? 'ok' : ''}">${c.ok ? 'verbunden' : 'offline'}</span>
        <span class="badge ${c.cal ? 'ok' : ''}">${c.cal ? 'kalibriert' : 'nicht kalibriert'}</span></div>
      <div class="bar">${CALK.map((k, i) => `<button data-k="${k}" class="${i === 0 ? 'on' : ''}">Punkt ${k}</button>`).join('')}
        <button class="live">Live</button><button class="save big" style="width:auto">Speichern</button></div>
      <div class="img"><img src="/api/cam/${c.id}.jpg?overlay=1&t=${Date.now()}"></div>
    </div>`).join('');
  $$('.cam').forEach(el => {
    const id = el.dataset.id, pts = {...(cal[id] || {})}; let cur = '20', live = false;
    const img = el.querySelector('img'), box = el.querySelector('.img');
    const marks = () => { box.querySelectorAll('.mk').forEach(m => m.remove());
      if (!img.naturalWidth) return;
      Object.entries(pts).forEach(([k, p]) => { const m = document.createElement('div'); m.className = 'mk';
        m.style.left = (p[0] / img.naturalWidth * 100) + '%'; m.style.top = (p[1] / img.naturalHeight * 100) + '%';
        m.textContent = k; box.appendChild(m); }); };
    img.onload = marks;
    el.querySelectorAll('[data-k]').forEach(b => b.onclick = () => { cur = b.dataset.k;
      el.querySelectorAll('[data-k]').forEach(x => x.classList.toggle('on', x === b)); });
    box.onclick = e => { const r = img.getBoundingClientRect();
      pts[cur] = [(e.clientX - r.left) / r.width * img.naturalWidth, (e.clientY - r.top) / r.height * img.naturalHeight];
      marks(); const n = CALK[(CALK.indexOf(cur) + 1) % 4]; el.querySelector(`[data-k="${n}"]`).click(); };
    el.querySelector('.save').onclick = async () => {
      if (Object.keys(pts).length < 4) return toast('Alle 4 Punkte setzen');
      await api('/api/cal/' + id, 'POST', {points: pts}); toast('Gespeichert');
      img.src = `/api/cam/${id}.jpg?overlay=1&t=${Date.now()}`; };
    el.querySelector('.live').onclick = b => { live = !live; b.target.classList.toggle('on', live);
      img.src = live ? `/api/cam/${id}/stream?overlay=1` : `/api/cam/${id}.jpg?overlay=1&t=${Date.now()}`; };
  });
}
$('#detPause').onclick = async () => { await api('/api/detect/pause', 'POST', {paused: !ST?.detector?.paused}); setTimeout(loadCams, 300); };
$('#detReset').onclick = () => api('/api/detect/reset', 'POST').then(() => toast('Referenz gesetzt'));


tabHooks.cams = loadCams;
