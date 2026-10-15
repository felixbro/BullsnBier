/* Kameras: eine Kamera groß kalibrieren (Auswahl rechts), 4 Punkte auf der Double-Außenkante am Draht */
var CALK = ['20-1', '6-10', '3-19', '11-14'];
var CALA = {'20-1': 9, '6-10': 99, '3-19': 189, '11-14': 279};   // Winkel im Uhrzeigersinn ab oben
var CAMSEL = '0', CALDRAFT = {}, CAMLIVE = false, CAMMODE = 'cal';

function calLabel(k) { return k.replace('-', ' | '); }
function miniBoard(k) {   // kleines Board mit markiertem Punkt
  var seg = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5], s = '';
  for (var i = 0; i < 20; i++) {
    var a = (i * 18 - 9) * Math.PI / 180, b = (i * 18) * Math.PI / 180;
    s += '<line x1="0" y1="0" x2="' + (Math.sin(a) * 50).toFixed(1) + '" y2="' + (-Math.cos(a) * 50).toFixed(1) + '"/>' +
      '<text x="' + (Math.sin(b) * 60).toFixed(1) + '" y="' + (-Math.cos(b) * 60 + 3.5).toFixed(1) + '">' + seg[i] + '</text>';
  }
  var a2 = CALA[k] * Math.PI / 180;
  return '<svg class="minib" viewBox="-70 -70 140 140" aria-hidden="true"><circle r="50"/><circle r="45"/>' + s +
    '<circle class="pt" cx="' + (Math.sin(a2) * 50).toFixed(1) + '" cy="' + (-Math.cos(a2) * 50).toFixed(1) + '" r="6"/></svg>';
}

function attachLens(box, img, off) {   // Lupe 4x in der gegenüberliegenden Ecke
  var lens = document.createElement('div'); lens.className = 'lens'; box.appendChild(lens);
  box.onpointermove = function (e) {
    if (e.pointerType === 'touch' || (off && off())) return lens.classList.remove('on');
    var r = box.getBoundingClientRect(), k = r.width / box.offsetWidth, w = box.offsetWidth, h = box.offsetHeight,
        x = (e.clientX - r.left) / k, y = (e.clientY - r.top) / k, R = lens.clientWidth / 2, Z = 4;
    lens.classList.toggle('l', x > w / 2); lens.classList.toggle('r', x <= w / 2);
    lens.style.backgroundImage = 'url("' + img.src + '")';
    lens.style.backgroundSize = (w * Z) + 'px ' + (h * Z) + 'px';
    lens.style.backgroundPosition = (R - x * Z) + 'px ' + (R - y * Z) + 'px';
    lens.classList.add('on');
  };
  box.onpointerleave = function () { lens.classList.remove('on'); };
}

function loadCams() {
  segment($('#camMode'), CAMMODE, function (v) { CAMMODE = v; loadCams(); });
  $('.cams-hint').textContent = CAMMODE === 'train'
    ? 'Jeder Wurf wird mit Bildern gespeichert. Hier die Spitze je Kamera bestätigen oder genau anklicken – daraus lernt später ein neuronales Netz.'
    : 'Kamera rechts wählen · 4 Punkte ins Bild tippen · Speichern. Das gelbe Raster muss danach genau auf dem Board liegen.';
  if (CAMMODE === 'train') return loadTrain();
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
  if (!info.cams.some(function (c) { return c.id === CAMSEL; })) CAMSEL = info.cams[0].id;
  Promise.all([api('/api/cal'), api('/api/cal/quality').catch(function () { return {}; })]).then(function (rr) {
    var cal = rr[0], q = rr[1] || {};
    var c = info.cams.filter(function (x) { return x.id === CAMSEL; })[0], id = c.id;
    var pts = CALDRAFT[id] || (CALDRAFT[id] = {});
    if (!Object.keys(pts).length) CALK.forEach(function (k) { if (cal[id] && cal[id][k]) pts[k] = cal[id][k]; });
    var cur = CALK.filter(function (k) { return !pts[k]; })[0] || CALK[0];
    var src = function () { return CAMLIVE ? '/api/cam/' + id + '/stream?overlay=1' : '/api/cam/' + id + '.jpg?overlay=1&t=' + Date.now(); };

    $('#camgrid').innerHTML =
      '<div class="glass cam big" data-id="' + id + '"><div class="img"><img src="' + src() + '" alt="Kamerabild ' + (+id + 1) + '"></div></div>' +
      '<div class="calside">' +
        '<div class="glass campick">' + info.cams.map(function (x) {
          return '<button type="button" class="cp' + (x.id === id ? ' on' : '') + '" data-id="' + x.id + '"><b>Cam ' + (+x.id + 1) + '</b><small>' + esc(x.src) + '</small>' +
            '<span class="tagrow"><span class="tag ' + (x.ok ? 'ok' : 'bad') + '">' + (x.ok ? 'verbunden' : 'offline') + '</span><span class="tag ' + (x.cal && !(q[x.id] > 6) ? 'ok' : 'bad') + '">' + (!x.cal ? 'offen' : q[x.id] > 6 ? 'ungenau – neu klicken' : 'kalibriert') + '</span>' + (x.cal && q[x.id] != null ? '<span class="calq">± ' + q[x.id] + ' px</span>' : '') + '</span></button>';
        }).join('') + '</div>' +
        '<div class="glass calpanel"><div class="calhead"><div><h2 class="h">Cam ' + (+id + 1) + '</h2><span class="meta">Punkt <b class="stepn">0 / 4</b></span></div><div id="miniB"></div></div>' +
          '<p class="calhelp">Auf die <b>Außenkante des Double-Rings</b> genau dort tippen, wo der <b>Draht zwischen <span id="calNow"></span></b> sie kreuzt.</p>' +
          '<div class="calpts stepper">' + CALK.map(function (k) { return '<button type="button" data-v="' + k + '">' + calLabel(k) + '</button>'; }).join('') + '</div>' +
          '<div class="step-bar"><i></i></div>' +
          '<div class="acts"><button class="btn-glass live' + (CAMLIVE ? ' on' : '') + '" type="button">' + (CAMLIVE ? 'Standbild' : 'Live-Bild') + '</button><button class="btn-cta save" type="button">Speichern</button></div>' +
        '</div></div>';

    var el = $('#camgrid .cam'), img = $('img', el), box = $('.img', el);
    attachLens(box, img, function () { return CAMLIVE; });
    var setCur = function (k) {
      cur = k; $('#calNow').textContent = k.split('-').join(' und ');
      $('#miniB').innerHTML = miniBoard(k);
      $$('.calpts button').forEach(function (b) { b.classList.toggle('cur', b.dataset.v === k); });
    };
    var marks = function () {
      var n = CALK.filter(function (k) { return pts[k]; }).length;
      $$('.calpts button').forEach(function (b) { b.classList.toggle('done', !!pts[b.dataset.v]); });
      $('.stepn').textContent = n + ' / 4'; $('.step-bar i').style.setProperty('--p', n / 4);
      $$('.mk', box).forEach(function (m) { m.remove(); }); if (!img.naturalWidth) return;
      CALK.forEach(function (k) { if (!pts[k]) return; var m = document.createElement('div'); m.className = 'mk';
        m.style.left = (pts[k][0] / img.naturalWidth * 100) + '%'; m.style.top = (pts[k][1] / img.naturalHeight * 100) + '%';
        m.innerHTML = '<span>' + calLabel(k) + '</span>'; box.appendChild(m); });
    };
    img.onload = function () { if (img.naturalWidth) box.style.aspectRatio = img.naturalWidth + ' / ' + img.naturalHeight; marks(); };
    $$('.calpts button').forEach(function (b) { b.onclick = function () { setCur(b.dataset.v); }; });
    setCur(cur);
    box.onclick = function (e) {
      var r = img.getBoundingClientRect();
      pts[cur] = [(e.clientX - r.left) / r.width * img.naturalWidth, (e.clientY - r.top) / r.height * img.naturalHeight];
      marks();
      var next = CALK.filter(function (k) { return !pts[k]; })[0];
      setCur(next || CALK[(CALK.indexOf(cur) + 1) % 4]);
    };
    $$('#camgrid .cp').forEach(function (b) { b.onclick = function () { CAMSEL = b.dataset.id; loadCams(); }; });
    $('#camgrid .save').onclick = function () {
      var send = {}; CALK.forEach(function (k) { if (pts[k]) send[k] = pts[k]; });
      if (Object.keys(send).length < 4) return toast('Alle 4 Punkte setzen', CALK.map(calLabel).join(' · '), 'info');
      api('/api/cal/' + id, 'POST', {points: send}).then(function (r) {
        toast(r.calibrated ? 'Kalibrierung gespeichert' : 'Kalibrierung unplausibel', 'Cam ' + (+id + 1), r.calibrated ? 'ok' : 'warn');
        delete CALDRAFT[id];
        var nxt = info.cams.filter(function (x) { return x.id !== id && !x.cal; })[0];
        if (r.calibrated && nxt) CAMSEL = nxt.id;
        setTimeout(loadCams, 400);
      });
    };
    $('#camgrid .live').onclick = function () { CAMLIVE = !CAMLIVE; loadCams(); };
  });
}
pageHooks.cams = loadCams;
$('#detPause').onclick = function () { api('/api/detect/pause', 'POST', {paused: !(ST && ST.detector && ST.detector.paused)}).then(function () { setTimeout(loadCams, 300); }); };
$('#detReset').onclick = function () { api('/api/detect/reset', 'POST').then(function () { toast('Referenz gesetzt', 'Board ist leer', 'ok'); }); };

/* Trainingsdaten: Spitze je Kamera bestätigen/markieren */
var TRS = null, TRCAM = null, TRTIPS = {};
function loadTrain(after) {
  Promise.all([api('/api/train'), api('/api/train/next' + (after ? '?after=' + encodeURIComponent(after) : ''))]).then(function (r) {
    var st = r[0], m = r[1];
    $('#camsMeta').textContent = st.total + ' Würfe gesammelt · ' + st.ok + ' markiert · ' + st.todo + ' offen';
    var head = '<label class="trcollect"><input type="checkbox" id="trCollect"' + (st.collect ? ' checked' : '') + '> Beim Spielen sammeln</label>';
    if (!m || !m.sid) {
      $('#camgrid').innerHTML = '<div class="glass nocams"><h2 class="h">Nichts zu markieren</h2><p class="lead">Einfach spielen – jeder Wurf landet hier. Korrigierte und nicht erkannte Würfe kommen zuerst.</p>' + head + '</div><div class="glass trsync" id="trSync"></div>';
      $('#trCollect').onchange = function (e) { api('/api/train/collect', 'POST', {on: e.target.checked}); };
      loadSync();
      return;
    }
    TRS = m; var cams = Object.keys(m.size || {}).sort();
    TRTIPS = {};
    cams.forEach(function (c) { var t = (m.tips || {})[c]; TRTIPS[c] = t !== undefined ? t : ((m.proposal || {})[c] || (m.cam_tips || {})[c] || null); });
    if (cams.indexOf(TRCAM) < 0) TRCAM = cams[0];
    var label = {auto: 'automatisch erkannt', corrected: 'korrigiert', unknown: 'nicht erkannt', ok: 'markiert'}[m.status] || m.status;
    $('#camgrid').innerHTML =
      '<div class="glass cam big"><div class="img"><img src="/api/train/' + m.sid + '/' + TRCAM + '.jpg" alt=""></div></div>' +
      '<div class="calside"><div class="glass campick">' + cams.map(function (c) {
          return '<button type="button" class="cp trthumb' + (c === TRCAM ? ' on' : '') + '" data-c="' + c + '"><img src="/api/train/' + m.sid + '/' + c + '.jpg" alt=""><b>Cam ' + (+c + 1) + '</b>' +
            '<span class="tag ' + (TRTIPS[c] ? 'ok' : 'bad') + '">' + (TRTIPS[c] ? 'Spitze gesetzt' : 'nicht sichtbar') + '</span></button>'; }).join('') + '</div>' +
        '<div class="glass calpanel"><div class="calhead"><div><h2 class="h">' + esc(m.name || '?') + '</h2><span class="meta">' + label + (m.detected ? ' · erkannt war ' + esc(m.detected) : '') + '</span></div></div>' +
          '<p class="calhelp">Gelber Kreis = Spitze des <b>neuen</b> Pfeils (dort, wo er im Board steckt). Liegt er falsch: genau auf die Spitze klicken.</p>' +
          '<div class="acts"><button class="btn-glass" id="trHide" type="button">Nicht sichtbar</button><button class="btn-cta" id="trOk" type="button">Passt · weiter</button></div>' +
          '<div class="acts"><button class="btn-glass" id="trSkip" type="button">Überspringen</button><button class="btn-glass" id="trDel" type="button">Löschen</button></div>' +
          head + '</div><div class="glass trsync" id="trSync"></div></div>';
    var box = $('#camgrid .cam .img'), img = $('img', box);
    attachLens(box, img);
    var mark = function () {
      $$('.mk', box).forEach(function (x) { x.remove(); });
      var t = TRTIPS[TRCAM]; if (!t || !img.naturalWidth) return;
      var k = document.createElement('div'); k.className = 'mk';
      k.style.left = (t[0] / img.naturalWidth * 100) + '%'; k.style.top = (t[1] / img.naturalHeight * 100) + '%'; box.appendChild(k);
    };
    img.onload = function () { box.style.aspectRatio = img.naturalWidth + ' / ' + img.naturalHeight; mark(); };
    var nextCam = function () { var i = cams.indexOf(TRCAM); if (i < cams.length - 1) { TRCAM = cams[i + 1]; redraw(); } };
    var redraw = function () {
      img.src = '/api/train/' + m.sid + '/' + TRCAM + '.jpg';
      $$('#camgrid .trthumb').forEach(function (b) { var c = b.dataset.c; b.classList.toggle('on', c === TRCAM);
        var tg = $('.tag', b); tg.className = 'tag ' + (TRTIPS[c] ? 'ok' : 'bad'); tg.textContent = TRTIPS[c] ? 'Spitze gesetzt' : 'nicht sichtbar'; });
    };
    box.onclick = function (e) { var r = img.getBoundingClientRect();
      TRTIPS[TRCAM] = [(e.clientX - r.left) / r.width * img.naturalWidth, (e.clientY - r.top) / r.height * img.naturalHeight];
      mark(); setTimeout(nextCam, 250); };
    $$('#camgrid .trthumb').forEach(function (b) { b.onclick = function () { TRCAM = b.dataset.c; redraw(); }; });
    $('#trHide').onclick = function () { TRTIPS[TRCAM] = null; mark(); redraw(); nextCam(); };
    var done = function (body) { TRCAM = null; api('/api/train/' + m.sid, 'POST', body).then(function () { loadTrain(m.sid); }); };
    $('#trOk').onclick = function () { done({tips: TRTIPS}); };
    $('#trSkip').onclick = function () { done({skip: true}); };
    $('#trDel').onclick = function () { done({delete: true}); };
    $('#trCollect').onchange = function (e) { api('/api/train/collect', 'POST', {on: e.target.checked}); };
    loadSync();
  });
}

/* Abgleich mit dem Trainings-Rechner (Nextcloud) */
function loadSync() {
  var box = $('#trSync'); if (!box) return;
  api('/api/sync').then(function (st) {
    if (!st.configured) {
      box.innerHTML = '<h2 class="h">Abgleich</h2><p class="calhelp">Noch nicht eingerichtet: <code>SYNC_URL</code>, <code>SYNC_USER</code>, <code>SYNC_PASS</code> in <code>config.env</code> eintragen.</p>';
      return;
    }
    var lm = (st.model && st.model.version) || 'keins', rm = st.remote_model && st.remote_model.version;
    var newer = rm && rm !== lm;
    box.innerHTML = '<h2 class="h">Abgleich · ' + esc(st.setup) + '</h2>' +
      (st.error ? '<p class="calhelp" style="color:var(--coral)">' + esc(st.error) + '</p>' : '') +
      '<p class="calhelp"><b>' + st.ready + '</b> Würfe bereit · ' + st.todo + ' noch markieren · ' + st.uploaded + ' schon hochgeladen</p>' +
      '<div class="acts"><button class="btn-cta" id="syUp" type="button"' + (st.ready ? '' : ' disabled') + '>Hochladen</button></div>' +
      '<p class="calhelp">Modell hier: <b>' + esc(lm) + '</b>' + (rm ? ' · in der Cloud: <b>' + esc(rm) + '</b>' + (st.remote_model.map ? ' (Genauigkeit ' + st.remote_model.map + ')' : '') : '') + '</p>' +
      '<div class="acts"><button class="btn-glass" id="syModel" type="button"' + (newer ? '' : ' disabled') + '>' + (newer ? 'Neues Modell installieren' : 'Modell aktuell') + '</button>' +
      '<button class="btn-glass" id="syBack" type="button"' + (st.can_rollback ? '' : ' disabled') + '>Altes Modell</button></div>';
    var run = function (btn, url, body, ok) {
      var pr = api(url, 'POST', body || {}); if (typeof btnLoading === 'function') btnLoading(btn, pr);
      pr.then(function (r) { toast(ok(r), '', 'ok'); loadSync(); }, function (e) { toast('Fehlgeschlagen', e && e.detail, 'warn'); });
    };
    $('#syUp').onclick = function () { run(this, '/api/sync/upload', null, function (r) { return r.sent + ' Würfe hochgeladen (' + r.mb + ' MB)'; }); };
    $('#syModel').onclick = function () { run(this, '/api/sync/model', null, function (r) { return 'Modell ' + r.version + ' installiert'; }); };
    $('#syBack').onclick = function () { run(this, '/api/sync/model', {rollback: true}, function (r) { return 'Zurück auf Modell ' + (r.version || 'vorher'); }); };
  });
}
