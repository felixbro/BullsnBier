/* 09 · Start: Begrüßung, Weiterspielen/Revanche, 4 Kacheln, Tageswertung, letzte Spiele */
var RECENT = [];
function greeting() {
  var h = new Date().getHours();
  return h < 5 ? 'Gute Nacht' : h < 11 ? 'Guten Morgen' : h < 17 ? 'Guten Tag' : 'Guten Abend';
}
function fmtTime(ts) { var d = new Date(ts * 1000); return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2); }
function gameLine(r) {
  var o = r.opts || {}, short = r.mode === 'x01' ? o.start + ' ' + ({double: 'DO', single: 'SO', master: 'MO'}[o.out] || '') : r.mode_name;
  if (!r.winner) return short;
  var legs = r.legs || [], wi = r.players.indexOf(r.winner);
  var others = legs.filter(function (_, k) { return k !== wi; });
  var sc = r.players.length > 1 && legs.length && (+o.legs > 1 || +o.sets) ? ' ' + legs[wi] + ' : ' + Math.max.apply(null, others.concat([0])) : '';
  return short + ' · ' + r.winner + ' gewinnt' + sc;
}
function loadStart() {
  var now = new Date(), host = hostPlayer();
  $('#startDate').textContent = now.toLocaleDateString('de-DE', {weekday: 'long', day: 'numeric', month: 'long'}) + ' · ' + fmtTime(now / 1000);
  $('#greet').innerHTML = esc(greeting()) + ',<br>' + esc(host ? host.name : 'Bude') + '.';
  var cams = ST && ST.detector && ST.detector.cams || [], calOk = cams.length && cams.every(function (c) { return c.ok && c.cal; });
  $('#startLead').textContent = 'Willkommen bei Bulls’n’Bier. Die Bude ist offen, ' + (ST && ST.sim ? 'Simulator läuft' : calOk ? 'Board kalibriert' : 'Board noch kalibrieren') + ', Bier kalt.';
  $('#heroLogo').innerHTML = '<div class="idle-mark">' + logo(380) + '</div>';
  Promise.all([api('/api/today'), api('/api/games')]).then(function (r) {
    var day = r[0]; RECENT = r[1];
    var acts = '<button class="btn-primary lime-text" data-page="new" type="button">Neues Spiel +</button>';
    var g = ST && ST.game;
    if (g && g.state.winner === null) acts += '<button class="btn-glass" data-page="live" type="button">Weiterspielen<small>Leg ' + (g.state.leg + 1) + ' · ' + esc(g.mode_name) + ' · ' + g.players.length + ' Spieler</small></button>';
    var last = RECENT[0];
    if (last) acts += '<button class="btn-glass" id="btnRevanche" type="button">Revanche<small>' + esc(last.mode_name) + ' · ' + esc(last.players.slice(0, 3).join(' vs. ')) + '</small></button>';
    $('#heroActions').innerHTML = acts;
    if (last) $('#btnRevanche').onclick = function () {
      var ps = last.players.map(function (n, i) { return last.player_ids[i] != null ? last.player_ids[i] : n; });
      var o = JSON.parse(JSON.stringify(last.opts)); delete o.seed; delete o.first;
      api('/api/game', 'POST', {mode: last.mode, players: ps, opts: o}).then(function () { showPage('live'); });
    };
    var byId = {}; PLAYERS.forEach(function (p) { byId[p.id] = p; });
    $('#dayRank').innerHTML = day.rank.length ? day.rank.slice(0, 6).map(function (x, i) {
      var p = byId[x.id] || {name: x.name, color: PALETTE[(i + 3) % 8]};
      return '<div class="r"><span class="n">' + (i + 1) + '</span>' + avatar(p, 40) + '<span>' + esc(x.name) + '</span><span class="v">' + x.avg3.toFixed(1) + '</span><span class="l">' + x.legs + '</span></div>';
    }).join('') : '<p class="lead">Heute noch kein Spiel – Zeit für den ersten Pfeil.</p>';
    if (typeof stagger === 'function') stagger($('#dayRank'));   // D4
    $('#tilePlayers').innerHTML = '<div class="avs">' + PLAYERS.slice(0, 6).map(function (p) { return avatar(p, 48); }).join('') + '</div>';
    $('#tilePlayersMeta').textContent = day.players + ' Stammspieler · ' + day.guests + ' Gäste';
    $('#tileAvg').textContent = day.avg3 ? day.avg3.toFixed(1) : '–';
    $('#tileStatsMeta').textContent = day.t180 + ' × 180 · High Finish ' + (day.high || '–');
    $('#recentGames').innerHTML = RECENT.slice(0, 4).map(function (r) {
      return '<div><span>' + esc(gameLine(r)) + '</span><span>' + fmtTime(r.ts) + '</span></div>'; }).join('') || '<div><span class="meta">Noch keine Spiele.</span></div>';
  });
  $('#tileCams').innerHTML = '<div class="cams">' + (cams.length ? cams.map(function (c) { return '<span class="' + (c.ok ? '' : 'off') + '">Cam ' + (+c.id + 1) + '</span>'; }).join('') : '<span>Simulator</span>') + '</div>';
  $('#tileCamsMeta').textContent = cams.length ? cams.filter(function (c) { return c.cal; }).length + ' / ' + cams.length + ' kalibriert' : 'ohne Kameras';
  var nAnim = Object.keys(CFG.display.anim).filter(function (k) { return CFG.display.anim[k]; }).length;
  $('#tileSet').innerHTML = '<div class="chk"><span><i class="dot ' + (CFG.caller.enabled ? 'ok' : 'warn') + '"></i>Sprachausgabe ' + (CFG.caller.enabled ? 'an' : 'aus') + '</span>' +
    '<span><i class="dot ' + (CFG.wled.enabled ? 'ok' : 'warn') + '"></i>WLED ' + (CFG.wled.enabled ? 'aktiv' : 'aus') + '</span>' +
    '<span><i class="dot ok"></i>' + (CFG.display.animations ? nAnim + ' Animationen aktiv' : 'Animationen aus') + '</span></div>';
}
pageHooks.start = loadStart;
