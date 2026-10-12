/* Start: Einstellungen + Ereignisliste laden, dann WebSocket */
function connect() {
  const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
  ws.onmessage = e => { const m = JSON.parse(e.data);
    if (m.type === 'state') { render(m); handleFx(m); announce(m.calls); }
    if (m.type === 'settings') { CFG = m.settings; muteIcon(); }
    if (m.type === 'fx_test') playFx(m.fx.trigger, demoCtx(m.fx.trigger), true);
    if (m.type === 'warn') toast(m.msg);
    if (m.type === 'dart_free') toast(m.score.name); };
  ws.onopen = () => $('#dot').classList.add('ok');
  ws.onclose = () => { $('#dot').classList.remove('ok'); setTimeout(connect, 1500); };
}
Promise.all([api('/api/settings'), api('/api/events')]).then(async ([s, ev]) => {
  CFG = s; EVENTS = ev; muteIcon();
  await initSetup();
  connect();
});
