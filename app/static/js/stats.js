/* 12 · Statistik: Spielerwahl, Zeitraum, 6 Kennzahlen, Verlauf Ø, Lieblingsfelder, Rekorde */
var statPid = null, statPeriod = LOCAL.period || '30d';
function loadStats() {
  if (!PLAYERS.length) { $('#kpis').innerHTML = '<p class="lead">Noch keine Spieler angelegt.</p>'; return; }
  if (!statPid || !PLAYERS.some(function (p) { return p.id === statPid; })) statPid = (hostPlayer() || PLAYERS[0]).id;
  $('#statPlayers').innerHTML = PLAYERS.map(function (p) {
    return '<button type="button" class="pchip' + (p.id === statPid ? ' on' : '') + '" data-id="' + p.id + '" style="--pc:' + p.color + '">' + avatar(p, 40) + esc(p.name) + '</button>'; }).join('');
  $$('#statPlayers .pchip').forEach(function (b) { b.onclick = function () { statPid = +b.dataset.id; loadStats(); }; });
  segment($('#period'), statPeriod, function (v) { statPeriod = v; LOCAL.period = v; saveLocal(); loadStats(); });
  var p = PLAYERS.filter(function (x) { return x.id === statPid; })[0];
  Promise.all([api('/api/stats/' + statPid + '?period=' + statPeriod), api('/api/records')]).then(function (r) {
    var s = r[0], diff = s.avg3_prev != null && s.avg3 ? (s.avg3 - s.avg3_prev) : null;
    var k = function (lbl, v, sub, dec, unit) { return '<div class="glass kpi"><div class="k">' + lbl + '</div><div class="v"><span data-n="' + v + '" data-dec="' + (dec || 0) + '">' + v + '</span>' + (unit || '') + '</div><div class="s">' + esc(sub) + '</div></div>'; };
    $('#kpis').innerHTML = k('Ø 3 Darts', s.avg3, diff != null ? (diff >= 0 ? '+' : '') + diff.toFixed(1).replace('.', ',') + ' zum Vorzeitraum' : s.darts + ' Darts', 1) +
      k('First 9 Ø', s.first9, 'erste drei Aufnahmen je Leg', 1) +
      k('Checkout-Quote', s.co_pct, s.co_hit + ' von ' + s.co_att + ' Versuchen', 0, ' %') +
      k('180er', s.t180, s.t180_7d + ' in den letzten 7 Tagen') +
      k('High Finish', s.best_co, s.best_co_way.length ? s.best_co_way.join(' · ') : '–') +
      k('Legs gewonnen', s.legs_won, 'von ' + s.legs + ' gespielt');
    $$('#kpis [data-n]').forEach(function (el) { var to = +el.dataset.n, dec = +el.dataset.dec; el.textContent = '0'; countTo(el, to, {from: 0, dec: dec}); });
    $('#chartTitle').textContent = p.name + ' · Ø 3 Darts je Spiel';
    var h = s.history;
    $('#chartMeta').textContent = h.length ? 'letzte ' + h.length + ' Spiele' + (h.length > 1 ? ' · Trend ' + ((h[h.length - 1].avg - h[0].avg) >= 0 ? '+' : '') + (h[h.length - 1].avg - h[0].avg).toFixed(1).replace('.', ',') : '') : 'noch keine X01-Spiele';
    $('#chart').innerHTML = chart(h, p.color);
    $('#favs').innerHTML = s.favorites.length ? s.favorites.map(function (f) {
      return '<div class="f" style="--pc:' + p.color + '"><span>' + esc(f.field) + '</span><span class="bar"><i style="width:' + Math.max(3, f.pct / s.favorites[0].pct * 100) + '%"></i></span><span>' + f.pct + ' %</span></div>'; }).join('')
      : '<p class="lead">Noch keine Würfe in diesem Zeitraum.</p>';
    $$('#favs .bar i').forEach(function (i, n) { i.style.transform = 'scaleX(0)'; setTimeout(function () { i.style.transition = 'transform 600ms cubic-bezier(.2,.7,.2,1)'; i.style.transform = 'scaleX(1)'; }, 40 + n * 60); });
    $('#records').innerHTML = r[1].length ? r[1].map(function (x) { return '<div><span>' + esc(x.label) + '</span><span>' + esc(x.value) + '</span></div>'; }).join('') : '<div><span class="meta">Noch keine Rekorde.</span></div>';
  });
}
pageHooks.stats = loadStats;
function chart(h, color) {
  var W = 1140, H = 560, L = 70, B = 60, T = 60, Rr = 30;
  if (!h.length) return '';
  var vals = h.map(function (x) { return x.avg; }), mn = Math.floor(Math.min.apply(null, vals) / 5) * 5, mx = Math.ceil(Math.max.apply(null, vals) / 5) * 5;
  if (mx - mn < 10) { mn = Math.max(0, mn - 5); mx = mn + 20; }
  var X = function (i) { return L + (h.length === 1 ? (W - L - Rr) / 2 : i * (W - L - Rr) / (h.length - 1)); };
  var Y = function (v) { return T + (H - T - B) * (1 - (v - mn) / (mx - mn)); };
  var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" aria-label="Verlauf Ø 3 Darts">';
  for (var g = 0; g <= 4; g++) { var v = mn + (mx - mn) * g / 4, y = Y(v);
    s += '<line x1="' + L + '" x2="' + (W - Rr) + '" y1="' + y + '" y2="' + y + '" stroke="#BDC8CB" stroke-width="1"/><text x="' + (L - 14) + '" y="' + (y + 5) + '" text-anchor="end">' + Math.round(v) + '</text>'; }
  var pts = vals.map(function (v, i) { return X(i).toFixed(1) + ',' + Y(v).toFixed(1); });
  s += '<polygon points="' + X(0) + ',' + (H - B) + ' ' + pts.join(' ') + ' ' + X(vals.length - 1) + ',' + (H - B) + '" fill="' + color + '" fill-opacity=".18"/>';
  s += '<polyline points="' + pts.join(' ') + '" fill="none" stroke="' + color + '" stroke-width="3" stroke-linejoin="round"/>';
  var li = vals.length - 1;
  s += '<line x1="' + X(li) + '" x2="' + X(li) + '" y1="' + Y(vals[li]) + '" y2="' + (H - B) + '" stroke="' + color + '" stroke-dasharray="4 4"/>';
  s += '<circle cx="' + X(li) + '" cy="' + Y(vals[li]) + '" r="8" fill="' + color + '" stroke="#fff" stroke-width="3"/>';
  s += '<text x="' + X(li) + '" y="' + (Y(vals[li]) - 22) + '" text-anchor="end" style="font-size:28px; fill:#202020">Ø ' + vals[li].toFixed(1).replace('.', ',') + '</text>';
  s += '<text x="' + X(0) + '" y="' + (H - 18) + '" text-anchor="start">Spiel 1</text><text x="' + X(li) + '" y="' + (H - 18) + '" text-anchor="end">' + h.length + '</text>';
  return s + '</svg>';
}
