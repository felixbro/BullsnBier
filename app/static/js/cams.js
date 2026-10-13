/* Kameras: Status, Kalibrierung (4 Punkte je Kamera), Live-Bild mit Raster */
var CALK = ['20', '6', '3', '11'];
function loadCams() {
  var info = ST && ST.detector;
  $('#detPause').classList.toggle('hidden', !info || !info.running);
  $('#detReset').classList.toggle('hidden', !info || !info.running);
  if (!info || !info.running) {
    $('#camsMeta').textContent = 'Simulator';
    $('#camgrid').innerHTML = '<div class="glass nocams"><h2 class="h">Simulator – keine Kameras</h2><p class="lead">Würfe werden per Klick aufs Board eingegeben. Für den Live-Betrieb ohne <code>--sim</code> starten.</p></div>';
    return;
  }
  $('#camsMeta').textContent = info.cams.filter(function (c) { return c.ok; }).length + ' / ' + info.cams.length + ' verbunden · ' + info.fps + ' fps';
  $('#detPause').textContent = info.paused ? 'Erkennung fortsetzen' : 'Erkennung pausieren';
  api('/api/cal').then(function (cal) {
    $('#camgrid').innerHTML = info.cams.map(function (c) {
      return '<div class="glass cam" data-id="' + c.id + '"><div class="card-head"><h2 class="h">Cam ' + (+c.id + 1) + '</h2><span class="meta">' + esc(c.src) + '</span></div>' +
        '<div class="tagrow"><span class="tag ' + (c.ok ? 'ok' : 'bad') + '">' + (c.ok ? 'verbunden' : 'offline') + '</span><span class="tag ' + (c.cal ? 'ok' : 'bad') + '">' + (c.cal ? 'kalibriert' : 'nicht kalibriert') + '</span></div>' +
        '<div class="img"><img src="/api/cam/' + c.id + '.jpg?overlay=1&t=' + Date.now() + '" alt="Kamerabild ' + (+c.id + 1) + '"></div>' +
        '<div class="field"><span>Kalibrierpunkt · Außenkante Double · <b class="stepn">0 / 4</b></span><div class="seg pts stepper">' + CALK.map(function (k) { return '<button data-v="' + k + '">' + k + '</button>'; }).join('') + '</div><div class="step-bar"><i></i></div></div>' +
        '<div class="acts"><button class="btn-glass live" type="button">Live-Bild</button><button class="btn-cta save" type="button">Speichern</button></div></div>';
    }).join('');
    $$('#camgrid .cam').forEach(function (el) {
      var id = el.dataset.id, pts = JSON.parse(JSON.stringify(cal[id] || {})), cur = '20', live = false, img = $('img', el), box = $('.img', el), sg = $('.pts', el);
      var steps = function () {   // D7 Stepper: erledigte Punkte + Fortschritt
        var n = CALK.filter(function (k) { return pts[k]; }).length;
        $$('.pts button', el).forEach(function (b) { b.classList.toggle('done', !!pts[b.dataset.v]); });
        $('.stepn', el).textContent = n + ' / 4'; $('.step-bar i', el).style.setProperty('--p', n / 4);
      };
      var marks = function () { steps(); $$('.mk', box).forEach(function (m) { m.remove(); }); if (!img.naturalWidth) return;
        Object.keys(pts).forEach(function (k) { var m = document.createElement('div'); m.className = 'mk';
          m.style.left = (pts[k][0] / img.naturalWidth * 100) + '%'; m.style.top = (pts[k][1] / img.naturalHeight * 100) + '%'; m.textContent = k; box.appendChild(m); }); };
      img.onload = marks;
      segment(sg, cur, function (v) { cur = v; });
      box.onclick = function (e) { var r = img.getBoundingClientRect();
        pts[cur] = [(e.clientX - r.left) / r.width * img.naturalWidth, (e.clientY - r.top) / r.height * img.naturalHeight];
        marks(); var n = CALK[(CALK.indexOf(cur) + 1) % 4]; cur = n; segment(sg, n, function (v) { cur = v; }); };
      $('.save', el).onclick = function () {
        if (Object.keys(pts).length < 4) return toast('Alle 4 Punkte setzen', '20 · 6 · 3 · 11', 'info');
        api('/api/cal/' + id, 'POST', {points: pts}).then(function (r) { toast(r.calibrated ? 'Kalibrierung gespeichert' : 'Kalibrierung unplausibel', 'Cam ' + (+id + 1), r.calibrated ? 'ok' : 'warn'); img.src = '/api/cam/' + id + '.jpg?overlay=1&t=' + Date.now(); }); };
      $('.live', el).onclick = function (e) { live = !live; e.target.classList.toggle('on', live); e.target.textContent = live ? 'Standbild' : 'Live-Bild';
        img.src = live ? '/api/cam/' + id + '/stream?overlay=1' : '/api/cam/' + id + '.jpg?overlay=1&t=' + Date.now(); };
    });
  });
}
pageHooks.cams = loadCams;
$('#detPause').onclick = function () { api('/api/detect/pause', 'POST', {paused: !(ST && ST.detector && ST.detector.paused)}).then(function () { setTimeout(loadCams, 300); }); };
$('#detReset').onclick = function () { api('/api/detect/reset', 'POST').then(function () { toast('Referenz gesetzt', 'Board ist leer', 'ok'); }); };
