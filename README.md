# AMBIConnect für Home Assistant

Bindet eine **Ambibox ambiCHARGE Home** über deren MQTT-Schnittstelle (IPC) in
Home Assistant ein — Messwerte, Zustand der Ladesitzung und, ausdrücklich
freizuschalten, die Steuerung.

Entwickelt und gemessen an Firmware **0.4.8 (Manny)**.

Eine Schwesterimplementierung für ioBroker liegt unter
[iebl/ioBroker.ambiconnect](https://github.com/iebl/ioBroker.ambiconnect).

## Warum nicht einfach MQTT-Discovery

Weil ein beschreibbares Zahlenfeld bei dieser Box kein Bedienelement ist,
sondern eine Falle. Die Box nimmt Werte an, die sie nicht fahren kann, und
verliert daran die Ladesitzung — im ungünstigen Fall so, dass nur noch
körperliches Aus- und Einstecken am Fahrzeug hilft.

Die Integration bringt deshalb eine Sicherheitsschicht mit, deren Regeln alle an
der realen Box gemessen sind:

- **Untergrenze.** Unterhalb des Arbeitspunkts der Leistungsendstufe löst diese
  aus und beendet die Sitzung. Gemessen: 510 W laufen, 459 W lösen aus. Die Box
  begrenzt *nicht* selbst — sie übernimmt den Wert wortwörtlich.
- **Null ist keine Pause.** Ein Limit von 0 ohne Stopp hält rund 66 s, dann ist
  die Sitzung endgültig weg.
- **Rampe.** Absenkungen laufen in Schritten, mit Abstand zum Nachgewiesenen.
- **Stoppen nur im Ladebetrieb.** Ein Stopp während des Startvorgangs wirft die
  Box in `ERROR` und verlangt Neustecken.
- **Wecken mit Maß.** Ein zweiter Weckruf in einen laufenden SLAC-Aufruf hinein
  kippt die Box. Die Integration liest `wakeUpBlocked` und `replugRequired`,
  statt Wartezeiten anzunehmen — und weckt nicht nach, wenn das Fahrzeug die
  letzte Sitzung selbst beendet hat.

Die `number`-Entität erzwingt die Untergrenze zusätzlich in der Oberfläche: der
Schieberegler geht gar nicht tiefer.

## Nur ein Regler

Die Box verträgt **keinen zweiten Regler auf demselben Stellglied**. Läuft
daneben evcc oder das box-eigene ChargeControl, brechen Ladevorgänge an
willkürlichen Punkten ab. Die Steuerung ist deshalb standardmäßig gesperrt und
wird in den Optionen freigeschaltet.

## Entitäten

| Art | Inhalt |
|---|---|
| `sensor` | Leistung AC/DC, Ströme, Spannungen, Energie, SoC, Temperatur, Sitzungszustand |
| `binary_sensor` | Fahrzeug verbunden, Neustecken nötig, Wecken gesperrt |
| `number` | Ladegrenze (DC-seitig), mit erzwungenem Minimum |
| `button` | Ladung starten, Ladung beenden |

Die Energiezähler tragen `state_class: total_increasing` und erscheinen damit im
Energie-Dashboard.

## Eigenheiten der Firmware 0.4.8

- `setSleep` wird **nicht gelesen**. Der Broker nimmt das Topic an, kein Prozess
  der Box wertet es aus. Eine Pause ohne Ladeende gibt es nicht.
- `limitChargePower` hat **keine Rückmeldung**. Die gesetzte Grenze zeigt die
  Integration aus eigenem Gedächtnis; die Wirkung steht in *Ladeleistung DC*.
- Das Limit wirkt auf die **DC-Seite**. Die AC-Aufnahme liegt im Teillastbetrieb
  deutlich darüber (700 W Grenze ≙ 682 W DC ≙ 875 W AC).
- `inverterError` meldet nur `OTHER_ALARM`. Der genaue Fehlercode steht
  ausschließlich in den Modbus-Registern 4044 und 4096.

## Installation

Über HACS als benutzerdefiniertes Repository, oder von Hand: den Ordner
`custom_components/ambiconnect` nach `<config>/custom_components/` kopieren und
Home Assistant neu starten. Danach *Einstellungen → Geräte & Dienste →
Integration hinzufügen → AMBIConnect*.

## Lizenz

MIT
