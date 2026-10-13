/* Bulls’n’Bier · Styleguide-Erweiterung D · Micro-Interaktionen (Helfer, ohne Abhängigkeiten) */

/* D1 · Hold to Confirm: gedrückt halten (ms), dann fn(). Kurzer Klick zeigt einen Hinweis. */
function holdToConfirm(btn, fn, opts) {
  if (!btn || btn._hold) return; btn._hold = true;
  opts = opts || {};
  var ms = opts.ms || 900, t = null, hint = document.createElement('span');
  btn.classList.add('hold'); btn.style.setProperty('--hold', ms + 'ms');
  hint.className = 'hold-hint'; hint.textContent = opts.hint || 'Gedrückt halten';
  btn.style.overflow = 'visible'; btn.appendChild(hint);
  if (getComputedStyle(btn).position === 'static') btn.style.position = 'relative';
  var start = function (e) {
    if (opts.when && !opts.when()) return;   // Bedingung nicht erfüllt → normaler Klick
    e.preventDefault(); btn.classList.add('holding'); hint.classList.remove('on');
    t = setTimeout(function () { t = null; btn.classList.remove('holding'); btn.classList.add('done');
      setTimeout(function () { btn.classList.remove('done'); }, 400); if (navigator.vibrate) navigator.vibrate(30); fn(); }, ms);
  };
  var stop = function () {
    if (!btn.classList.contains('holding')) return;
    btn.classList.remove('holding'); if (t) { clearTimeout(t); t = null;
      hint.classList.add('on'); clearTimeout(btn._ht); btn._ht = setTimeout(function () { hint.classList.remove('on'); }, 1400); }
  };
  btn.addEventListener('pointerdown', start);
  ['pointerup', 'pointerleave', 'pointercancel'].forEach(function (ev) { btn.addEventListener(ev, stop); });
  btn.addEventListener('click', function (e) { if (!opts.when || opts.when()) { e.preventDefault(); e.stopImmediatePropagation(); } else if (opts.click) opts.click(); }, true);
  btn.addEventListener('keydown', function (e) { if ((e.key === 'Enter' || e.key === ' ') && !e.repeat) start(e); });
  btn.addEventListener('keyup', function (e) { if (e.key === 'Enter' || e.key === ' ') stop(); });
}

/* D2 · Ripple auf dem Board (SVG-Koordinaten in mm, y nach oben) */
function boardRipple(xy) {
  var g = document.getElementById('hits'); if (!g || !xy) return;
  var ns = 'http://www.w3.org/2000/svg';
  ['', ' r2'].forEach(function (c) {
    var r = document.createElementNS(ns, 'circle');
    r.setAttribute('class', 'ripple' + c); r.setAttribute('cx', xy[0].toFixed(1)); r.setAttribute('cy', (-xy[1]).toFixed(1)); r.setAttribute('r', 10);
    g.parentNode.appendChild(r); setTimeout(function () { r.remove(); }, 800);
  });
}

/* D3 · Value Flash: Element kurz aufblitzen lassen */
function valueFlash(el, card) {
  if (!el) return;
  el.classList.remove('vflash'); void el.offsetWidth; el.classList.add('vflash');
  if (card) { card.classList.remove('vflash-card'); void card.offsetWidth; card.classList.add('vflash-card'); }
}

/* D4 · Liste gestaffelt einblenden */
function stagger(box) { if (!box) return; box.classList.remove('stagger'); Array.prototype.forEach.call(box.children, function (c, i) { c.style.setProperty('--i', i); }); void box.offsetWidth; box.classList.add('stagger'); }

/* D5 · Text Reveal: Text in Buchstaben-Spans zerlegen (HTML-sicher) */
function revealHTML(text, delayMs) {
  return '<span class="reveal" style="--d0:' + (delayMs || 0) + 'ms">' + Array.from(String(text)).map(function (ch, i) {
    return '<span style="--i:' + i + '">' + esc(ch) + '</span>'; }).join('') + '</span>';
}

/* D6 · Button lädt, solange das Promise läuft */
function btnLoading(btn, promise) {
  if (!btn) return promise; btn.classList.add('is-loading');
  var end = function () { btn.classList.remove('is-loading'); };
  promise.then(end, end); return promise;
}

