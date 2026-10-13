# Styleguide-Erweiterung D · Micro-Interaktionen

Ergänzt Styleguide v01 §8 (A Vollbild · B Bauteil · C Hinweise) um **D – kleine Rückmeldungen auf Bedienung**.
Vorlage: Muster von [interior.dev](https://www.interior.dev/docs), nachgebaut ohne React/Bibliotheken.

**Regeln (wie §8):** nur `transform`/`opacity` animieren · CI-Farben · `-webkit-`-Präfixe · `prefers-reduced-motion` respektieren.
**Technik:** eigene Ebene `app/static/micro.css` + `app/static/js/micro.js`. Alles hängt an eigenen Klassen – fehlt die Ebene, läuft die App unverändert (Fallback: normale Klicks / Rückfrage).

| Nr. | Muster | Einsatz | Ablauf | Klasse / Funktion |
|---|---|---|---|---|
| D1 | Hold to Confirm | Spiel abbrechen (Live + Handy), Spieler löschen | gedrückt halten 900 ms → Coral-Füllung läuft von links, Haptik, Aktion. Kurzer Klick → Hinweis „Gedrückt halten“ | `.hold` · `holdToConfirm(btn, fn, {ms, hint, when})` |
| D2 | Ripple | Board (Simulator, Korrektur, Handy) | zwei Ringe (Lime + Weiß) wachsen ab Treffpunkt, 620 ms | `.ripple` · `boardRipple(xy)` |
| D3 | Value Flash | Spielerleiste (Rest) | Zahl pulst kurz, Leiste in Spielerfarbe läuft unten durch, 700–900 ms | `.vflash` · `valueFlash(el, card)` |
| D4 | Poll Results | Tageswertung | Zeilen steigen gestaffelt auf (70 ms Versatz) | `.stagger` · `stagger(box)` |
| D5 | Text Reveal | Sieger-Screen „… gewinnt“ | Buchstaben steigen nacheinander auf (45 ms Versatz) | `.reveal` · `revealHTML(text, delay)` |
| D6 | Loading Button | WLED „Verbindung prüfen“, Stimme laden | Text weicht drei pulsierenden Punkten, Klicks gesperrt | `.is-loading` · `btnLoading(btn, promise)` |
| D7 | Stepper | Kamera-Kalibrierung 20 → 6 → 3 → 11 | Haken an erledigten Punkten, „n / 4“, Mint-Fortschrittsbalken | `.stepper`, `.step-bar` |

**Neue Bausteine nachrüsten:** Muster in `micro.css` (Abschnitt D8 …) + Helfer in `micro.js`, dann am Bauteil per Klasse/Funktion anhängen – bestehender Code bleibt unberührt.

Mögliche nächste: Reorder List (Spielerreihenfolge ziehen), Slider Detents (Tempo/Lautstärke/WLED), Long Press (Handy-Korrektur).
