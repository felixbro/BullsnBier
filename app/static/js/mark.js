/* Markieren am Handy (/mark): Spitze je Kamera setzen – Lupe + langsames Ziehen für Genauigkeit */
var M = null, CAMS = [], CI = 0, TIPS = {}, POS = null, IMGW = 0, IMGH = 0, POLL = null;
var SPEED = +(LOCAL.markSpeed || 0.2), ALL = !!LOCAL.markAll, ZOOM = 5;
var view = $('#view'), img = $('#img'), cross = $('#cross'), lens = $('#lens');

function buzz(ms) { if (navigator.vibrate) navigator.vibrate(ms || 12); }
function uvOf(side, c) { return side && side.uv && side.uv[c] || null; }

function load(after) {
  clearTimeout(POLL);
  api('/api/train').then(function (t) { $('#count').textContent = t.review + ' prüfen · ' + t.todo + ' offen'; });
  api('/api/train/next?prio=' + (ALL ? 0 : 1) + (after ? '&after=' + encodeURIComponent(after) : '')).then(function (m) {
    if (!m || !m.sid) return empty();
    M = m; CAMS = Object.keys(m.size || {}).sort(); CI = 0; TIPS = {};
    show();
  });
}

function empty() {
  M = null;
  $('#info').innerHTML = '<div class="rm-top">' + logo(48) + '<div><div class="rm-name">Alles erledigt</div><div class="meta">Neue Würfe erscheinen hier automatisch</div></div></div>';
  $('#cams').innerHTML = ''; $('#acts').innerHTML = ''; view.classList.add('hidden'); $('.mk-tools').classList.add('hidden');
  POLL = setTimeout(load, 5000);
}

function show() {
  var m = M, rev = m.status === 'review', c = CAMS[CI];
  view.classList.remove('hidden'); $('.mk-tools').classList.remove('hidden');
  var label = {auto: 'automatisch erkannt', corrected: 'korrigiert', unknown: 'nicht erkannt', review: 'Autodarts-Abgleich'}[m.status] || m.status;
  $('#info').innerHTML = '<div class="mk-top"><div class="rm-name">' + esc(m.name || '?') + '</div><span class="tag">' + label + '</span></div>' +
    (rev ? '<div class="trvs"><span class="mkdot bnb"></span><b>BnB</b> ' + esc((m.bnb || {}).name || '–') + '<span class="mkdot ad"></span><b>Autodarts</b> ' + esc((m.ad || {}).name || '–') + '</div>' : '');
  $('#cams').innerHTML = CAMS.map(function (k, i) {
    var st = TIPS[k] === undefined ? '' : TIPS[k] ? ' ok' : ' no';
    return '<button type="button" class="mk-cam' + (i === CI ? ' on' : '') + st + '" data-i="' + i + '">Cam ' + (+k + 1) + '</button>';
  }).join('');
  $$('#cams .mk-cam').forEach(function (b) { b.onclick = function () { CI = +b.dataset.i; show(); }; });

  POS = TIPS[c] || uvOf(m.ad, c) || (m.tips || {})[c] || (m.proposal || {})[c] || (m.cam_tips || {})[c] || uvOf(m.bnb, c) || null;
  img.onload = function () { IMGW = img.naturalWidth; IMGH = img.naturalHeight; view.style.aspectRatio = IMGW + ' / ' + IMGH; if (!POS) POS = [IMGW / 2, IMGH / 2]; place(); };
  img.src = '/api/train/' + m.sid + '/' + c + '.jpg';
  if (img.complete && img.naturalWidth) img.onload();

  var last = CI === CAMS.length - 1;
  var pick = rev ? '<div class="mk-row">' +
      '<button class="btn-cta" data-a="ad" type="button"' + (m.ad && m.ad.uv && Object.keys(m.ad.uv).length ? '' : ' disabled') + '><span class="mkdot ad"></span>Autodarts stimmt</button>' +
      '<button class="btn-glass" data-a="bnb" type="button"' + (m.bnb && m.bnb.uv && Object.keys(m.bnb.uv).length ? '' : ' disabled') + '><span class="mkdot bnb"></span>BnB stimmt</button></div>' : '';
  $('#acts').innerHTML = pick +
    '<div class="mk-row"><button class="btn-glass" data-a="hide" type="button">Nicht sichtbar</button>' +
    '<button class="btn-primary" data-a="ok" type="button">' + (last ? 'Passt · fertig' : 'Passt · Cam ' + (+CAMS[CI + 1] + 1) + ' →') + '</button></div>' +
    '<div class="mk-row small"><button class="btn-glass" data-a="skip" type="button">' + (rev ? 'Verwerfen' : 'Überspringen') + '</button>' +
    '<button class="btn-glass" data-a="del" type="button">Löschen</button></div>';
  $$('#acts [data-a]').forEach(function (b) { b.onclick = function () { act(b.dataset.a); }; });
}

function place() {
  if (!POS || !IMGW) return;
  var r = view.getBoundingClientRect(), k = r.width / IMGW, x = POS[0] * k, y = POS[1] * k, c = CAMS[CI];
  cross.style.left = x + 'px'; cross.style.top = y + 'px';
  [['#dotAd', M.ad], ['#dotBnb', M.bnb]].forEach(function (d) {
    var el = $(d[0]), p = M.status === 'review' && uvOf(d[1], c);
    el.classList.toggle('hidden', !p);
    if (p) { el.style.left = p[0] * k + 'px'; el.style.top = p[1] * k + 'px'; }
  });
  // Lupe: über dem Kreuz, oben am Rand darunter; ganz links/rechts nach innen schieben
  var R = lens.offsetWidth / 2 || 70, lx = Math.min(Math.max(x, R), r.width - R), ly = y - R - 46 < -20 ? y + R + 46 : y - R - 46;
  lens.style.left = lx + 'px'; lens.style.top = ly + 'px';
  lens.style.backgroundImage = 'url("' + img.src + '")';
  lens.style.backgroundSize = (r.width * ZOOM) + 'px ' + (r.height * ZOOM) + 'px';
  lens.style.backgroundPosition = (R - x * ZOOM) + 'px ' + (R - y * ZOOM) + 'px';
}

/* Ziehen bewegt das Kreuz um SPEED × Fingerweg – der Finger verdeckt nie die Spitze */
var drag = null, hideT = null;
view.addEventListener('pointerdown', function (e) {
  if (!M || !IMGW) return;
  view.setPointerCapture(e.pointerId);
  drag = {x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, moved: false};
  clearTimeout(hideT); lens.classList.add('on'); place();
});
view.addEventListener('pointermove', function (e) {
  if (!drag) return;
  if (!drag.moved && Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) < 6) return;
  drag.moved = true;
  var k = IMGW / view.getBoundingClientRect().width;
  POS = [Math.min(Math.max(POS[0] + (e.clientX - drag.x) * k * SPEED, 0), IMGW - 1),
         Math.min(Math.max(POS[1] + (e.clientY - drag.y) * k * SPEED, 0), IMGH - 1)];
  drag.x = e.clientX; drag.y = e.clientY;
  place();
});
function up(e) {
  if (!drag) return;
  if (!drag.moved) {   // Tippen → Kreuz springt dorthin, dann fein nachziehen
    var r = view.getBoundingClientRect(), k = IMGW / r.width;
    POS = [(e.clientX - r.left) * k, (e.clientY - r.top) * k]; place(); buzz(8);
  }
  drag = null;
  hideT = setTimeout(function () { lens.classList.remove('on'); }, 900);
}
view.addEventListener('pointerup', up);
view.addEventListener('pointercancel', up);
addEventListener('resize', place);

function act(a) {
  var c = CAMS[CI];
  buzz();
  if (a === 'ad' || a === 'bnb') return send({pick: a});
  if (a === 'skip') return send({skip: true});
  if (a === 'del') return send({delete: true});
  TIPS[c] = a === 'hide' ? null : [Math.round(POS[0] * 10) / 10, Math.round(POS[1] * 10) / 10];
  var open = CAMS.filter(function (k) { return TIPS[k] === undefined; });
  if (!open.length) {
    if (!CAMS.some(function (k) { return TIPS[k]; })) return toast('Keine Spitze gesetzt', 'Mindestens eine Kamera markieren oder verwerfen', 'info');
    return send({tips: TIPS});
  }
  CI = CAMS.indexOf(open[0]); show();
}

function send(body) {
  var sid = M.sid;
  api('/api/train/' + sid, 'POST', body).then(function () { toast('Gespeichert', '', 'ok'); load(sid); },
    function (e) { toast('Fehlgeschlagen', e && e.detail, 'warn'); });
}

segment($('#speed'), String(SPEED), function (v) { SPEED = +v; LOCAL.markSpeed = SPEED; saveLocal(); });
$('#all').checked = ALL;
$('#all').onchange = function (e) { ALL = e.target.checked; LOCAL.markAll = ALL; saveLocal(); load(); };
$('#logoMark').innerHTML = logo(28);
api('/api/settings').then(function (c) { CFG = c; if (typeof applyDisplay === 'function') applyDisplay(); }).catch(function () {});
load();
