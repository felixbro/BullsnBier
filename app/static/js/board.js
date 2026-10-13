/* Dartboard-Komponente (Styleguide §6.3): Draht Slate, Singles Ink/Paper, Double/Triple Coral/Mint,
   Treffermarker Lime, Checkout-Ziele Aqua gestrichelt. Koordinaten in mm, y nach oben. */
var SEG = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5];
var R = {bull: 6.35, ob: 15.9, ti: 99, to: 107, di: 162, do: 170};
var FIELD_D = {};

function scoreAt(x, y) {
  var r = Math.hypot(x, y);
  if (r <= R.bull) return 'BULL'; if (r <= R.ob) return '25'; if (r > R.do) return 'MISS';
  var a = ((Math.atan2(x, y) * 180 / Math.PI) + 360) % 360, s = SEG[Math.floor(((a + 9) % 360) / 18)];
  if (r >= R.ti && r <= R.to) return 'T' + s; if (r >= R.di) return 'D' + s; return 'S' + s;
}
function fieldPoint(name) {
  if (name === 'BULL') return [0, 0]; if (name === '25') return [0, 11];
  var m = /^([SDT])(\d+)$/.exec(name); if (!m) return null;
  var r = {S: 135, D: 166, T: 103}[m[1]], a = SEG.indexOf(+m[2]) * 18 * Math.PI / 180;
  return [r * Math.sin(a), r * Math.cos(a)];
}
function arc(r1, r2, a1, a2) {
  var p = function (r, a) { return [r * Math.sin(a), -r * Math.cos(a)]; };
  var A = p(r2, a1), B = p(r2, a2), C = p(r1, a2), D = p(r1, a1);
  return 'M' + A + 'A' + r2 + ',' + r2 + ' 0 0 1 ' + B + 'L' + C + 'A' + r1 + ',' + r1 + ' 0 0 0 ' + D + 'Z';
}
(function drawBoard() {
  var s = '<circle r="208" fill="var(--b-surround)"></circle>';
  SEG.forEach(function (n, i) {
    var a1 = (i * 18 - 9) * Math.PI / 180, a2 = (i * 18 + 9) * Math.PI / 180, dark = i % 2 === 0;
    var base = dark ? 'var(--b-dark)' : 'var(--b-light)', ring = dark ? 'var(--b-red)' : 'var(--b-green)';
    var parts = [['S' + n, R.ob, R.ti, base], ['T' + n, R.ti, R.to, ring], ['S' + n, R.to, R.di, base], ['D' + n, R.di, R.do, ring]];
    parts.forEach(function (q) { var d = arc(q[1], q[2], a1, a2); (FIELD_D[q[0]] = FIELD_D[q[0]] || []).push(d);
      s += '<path class="seg-f" d="' + d + '" fill="' + q[3] + '"></path>'; });
    var m = i * 18 * Math.PI / 180;
    s += '<text x="' + (188 * Math.sin(m)).toFixed(1) + '" y="' + (-188 * Math.cos(m)).toFixed(1) + '">' + n + '</text>';
  });
  s += '<g class="bullg" id="bullg"><circle class="seg-f" r="' + R.ob + '" fill="var(--b-green)"></circle><circle class="seg-f" r="' + R.bull + '" fill="var(--b-red)"></circle></g>' +
    '<g id="tgts"></g><g id="hits"></g><text class="hover" id="hover"></text>';
  $('#board').innerHTML = s;
})();

function boardXY(e) {
  var svg = $('#board'), pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
  var p = pt.matrixTransform(svg.getScreenCTM().inverse()); return [p.x, -p.y];
}
$('#board').addEventListener('mousemove', function (e) {
  var xy = boardXY(e), h = $('#hover');
  h.textContent = scoreAt(xy[0], xy[1]); h.setAttribute('x', xy[0]); h.setAttribute('y', -xy[1] - 14);
});
$('#board').addEventListener('mouseleave', function () { $('#hover').textContent = ''; });
$('#board').addEventListener('click', function (e) {
  var xy = boardXY(e), name = scoreAt(xy[0], xy[1]);
  if (typeof boardRipple === 'function') boardRipple(xy);   // D2
  if (typeof onBoardClick === 'function') onBoardClick(name, xy);
});

function drawHits(darts, selIdx) {
  $('#hits').innerHTML = (darts || []).map(function (d, i) {
    return d.pos ? '<circle class="hit' + (i === selIdx ? ' sel' : '') + '" cx="' + d.pos[0].toFixed(1) + '" cy="' + (-d.pos[1]).toFixed(1) + '" r="5.5"></circle>' : '';
  }).join('');
}
/* Checkout-Weg: Aqua gestrichelte Kreise · Ziele (ATC …): gestrichelte Feldkontur */
function drawTargets(route, fields) {
  var s = '';
  (route || []).forEach(function (n) { var p = fieldPoint(n); if (p) s += '<circle class="cotgt" cx="' + p[0].toFixed(1) + '" cy="' + (-p[1]).toFixed(1) + '" r="12"></circle>'; });
  (fields || []).forEach(function (f) {
    if (f === 'BULL') s += '<circle class="tgt" r="' + R.bull + '"></circle>';
    else if (f === '25') s += '<circle class="tgt" r="' + R.ob + '"></circle>';
    else (FIELD_D[f] || []).forEach(function (d) { s += '<path class="tgt" d="' + d + '"></path>'; });
  });
  $('#tgts').innerHTML = s;
}
/* Ziel-Text (aus Spiel-Engine) → Felder */
function targetFields(t) {
  if (!t) return [];
  var m = /(\d+)/.exec(t), n = m ? +m[1] : null, out = [];
  if (/beliebiges Doppel/.test(t)) return Object.keys(FIELD_D).filter(function (k) { return k[0] === 'D'; }).concat(['BULL']);
  if (/beliebiges Triple/.test(t)) return Object.keys(FIELD_D).filter(function (k) { return k[0] === 'T'; });
  if (/Bullseye/.test(t)) return ['BULL'];
  if (/Bull/.test(t)) return ['25', 'BULL'];
  if (!n || n > 20) return [];
  if (/Doppel/.test(t)) return ['D' + n];
  if (/Triple/.test(t)) return ['T' + n];
  if (/Single/.test(t)) return ['S' + n];
  return ['S' + n, 'D' + n, 'T' + n];
}
