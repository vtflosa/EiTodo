# EiTodo — Hilfe

## Die Eisenhower-Matrix

EiTodo ordnet Aufgaben in die vier Quadranten der Eisenhower-Matrix
ein und kreuzt dabei zwei Dimensionen: **Dringlichkeit** und
**Wichtigkeit**.

|                 | Dringend       | Nicht dringend           |
| --------------- | -------------- | ------------------------ |
| **Wichtig**     | Sofort erledigen | Einplanen              |
| **Unwichtig**   | Delegieren     | Verwerfen / Freizeit     |

- **Dringend & Wichtig** — Brände, die Sie selbst löschen müssen,
  und zwar jetzt.
- **Nicht dringend & Wichtig** — die langfristige Arbeit, auf die
  es ankommt. Tragen Sie sie in den Kalender ein, bevor die
  dringenden Dinge sie verdrängen.
- **Dringend & Unwichtig** — Unterbrechungen und die Prioritäten
  anderer. Delegieren Sie, wenn möglich; sagen Sie nein, wenn
  nicht.
- **Nicht dringend & Unwichtig** — Ablenkungen. Verwerfen Sie sie
  oder heben Sie sie für die Freizeit auf.

Jeder Quadrant hat zwei Bereiche: oben einen Editor für die
laufende Aufgabenliste, und darunter einen schreibgeschützten
Bereich, der die zuletzt erledigten Aufgaben sammelt. Wenn Sie
eine Zeile aus dem Editor löschen, erscheint sie dort
durchgestrichen. *Alle erledigten Aufgaben löschen* im Menü leert
diese unteren Bereiche in allen vier Quadranten auf einmal.

## Aufgaben umsortieren und verschieben

Neben dem direkten Tippen helfen einige Tastaturkürzel und
Rechtsklick-Aktionen, Aufgaben zu organisieren:

- **Strg+Hoch / Strg+Runter** — verschiebt die Zeile mit dem
  Cursor um eine Position nach oben oder unten (nur nicht-leere
  Zeilen).
- **Strg+Klick auf einen Link** — öffnet einen erkannten
  Weblink (`http://`, `https://` oder `www.`) im Browser. Hält
  man Strg über einem Link gedrückt, erscheint ein Hand-Cursor.

**Rechtsklick auf eine aktive Aufgabe** öffnet ein Menü mit:

- **Link öffnen** — wenn unter dem Cursor eine URL erkannt wird.
- **Nach oben / Nach unten** — entspricht den Strg-Pfeil-Kürzeln.
- **Als erledigt markieren** — entfernt die Aufgabe aus dem
  Editor und legt sie unten in den durchgestrichenen Bereich.
- **In Quadrant verschieben ▸** — Untermenü mit den drei
  anderen Quadranten; die Aufgabe verschwindet hier und
  erscheint oben in der aktiven Liste des gewählten Quadranten.

**Rechtsklick auf eine erledigte Aufgabe** (durchgestrichener
Bereich) öffnet:

- **In aktive Liste zurück** — bringt die Aufgabe oben in die
  aktive Liste desselben Quadranten zurück.
- **In Quadrant zurück ▸** — Untermenü mit den drei anderen
  Quadranten; stellt die Aufgabe in der aktiven Liste eines
  anderen Quadranten wieder her.
- **Endgültig löschen** — entfernt die Aufgabe dauerhaft aus
  der Liste der erledigten Aufgaben.

## Wo Ihre Daten gespeichert sind

Ihre Aufgaben werden in einer einzigen **JSON-Datei** gespeichert
(Standardname `param.json`), zusammen mit einem `save/`-Ordner,
der die zeitgestempelten Sicherungen enthält. EiTodo
kommuniziert mit keinem Server — alles bleibt auf Ihrer
Festplatte.

Der Pfad der Datendatei steht in `config.INI` unter
`[PATH] → json_file_path`. Sie können ihn über
**Menü → Speicherort ändern** ansehen oder anpassen, das zwei
Möglichkeiten anbietet:

- **Auf vorhandene Datei verweisen** — die aktuelle Datei wird
  aufgegeben, und EiTodo liest/schreibt fortan eine andere
  `.json`-Datei, die Sie bereits besitzen. Der Pfad bleibt aktiv,
  bis Sie ihn erneut ändern.
- **Aktuelle Datei verschieben** — die aktuelle Datendatei (mit
  ihrem Inhalt) wird physisch an einen neuen Ort mit neuem Namen
  verschoben und von dort aus weiterverwendet.

Beim ersten Start oder wenn die konfigurierte Datendatei fehlt,
stellt EiTodo dieselbe Frage, bevor irgendetwas erstellt wird:
Standardspeicherort behalten, auf eine vorhandene Datei
verweisen, oder eine neue Standarddatei an einem anderen Ort
anlegen.

Sicherheitsnetz: Bei jedem Wechsel des Speicherorts oder Laden
einer Sicherung schreibt EiTodo zuerst eine Sicherung der
*aktuellen* Daten in den Save-Ordner. Es geht nichts verloren,
falls Sie es sich anders überlegen.

## Aufgaben über mehrere Rechner hinweg teilen

Da die Daten in einer einzigen JSON-Datei liegen, reicht es,
sie über einen Datei-Synchronisationsdienst (Dropbox, MEGA,
Nextcloud, Syncthing, Google Drive usw.) zu synchronisieren, um
dieselbe Matrix auf mehreren Rechnern zu teilen.

**Direkte Netzwerkfreigaben sind nicht empfohlen** (NAS
Samba/NFS, Ordner, die von einem anderen Computer freigegeben
werden). EiTodo überwacht die Datendatei über die lokalen
Dateisystem-Benachrichtigungen des Betriebssystems, die nicht
ausgelöst werden, wenn ein anderer Rechner auf eine
Netzwerkfreigabe schreibt. Bei einer Netzwerkfreigabe müssten
Sie die App auf jedem Rechner neu starten, um die Änderungen
der anderen Seite zu erhalten. Ein Cloud-Synchronisationsdienst
schreibt auf Ihre lokale Festplatte und löst daher die
Live-Aktualisierung korrekt aus — bleiben Sie dabei.

Einrichtung:

1. Datendatei in einen synchronisierten Ordner legen — zum
   Beispiel über **Speicherort ändern → Aktuelle Datei
   verschieben**.
2. Auf jedem weiteren Rechner EiTodo installieren und
   **Speicherort ändern → Auf vorhandene Datei verweisen**
   verwenden, um die geteilte Datei auszuwählen.

Im laufenden Betrieb überwacht EiTodo die Datendatei auf
externe Änderungen. Sobald der Synchronisationsdienst eine
neue Version auf der Festplatte ablegt, erkennen die anderen
Instanzen das binnen Sekunden und aktualisieren ihre Editoren
automatisch — die App muss nicht neu gestartet werden.

Gleichzeitige Änderungen auf verschiedenen Rechnern:

- Eine `.lock`-Datei neben der Datendatei koordiniert die
  Schreibvorgänge.
- Jedes Speichern bewahrt die Quadranten, die Sie nicht
  bearbeitet haben, und überschreibt nur den tatsächlich
  geänderten Quadranten. Wenn zwei Rechner zur selben Zeit
  *unterschiedliche* Quadranten bearbeiten, bleiben beide
  Änderungen erhalten.
- Wenn zwei Rechner **denselben** Quadranten nahezu zeitgleich
  bearbeiten, gewinnt der zuletzt geschriebene Stand für
  diesen Quadranten — die vorherige Version lässt sich aus
  `save/` wiederherstellen (siehe unten).
- Synchronisationsdienste brauchen meist einige Sekunden zur
  Verteilung. Wenn Sie auf zwei Rechnern gleichzeitig tippen,
  geben Sie der Synchro einen Moment Zeit, bevor Sie auf dem
  anderen weitermachen.

## Automatische Sicherungen

EiTodo schreibt Sicherungen in den `save/`-Ordner (Pfad in
`config.INI` unter `[PATH] → save_folder_path`). Die Dateien
heißen `YYYY_MM_DD_HHMMSS_<Datendatei>.json`, eine einfache
alphabetische Sortierung listet sie also bereits chronologisch.

Sicherungen werden geschrieben:

- **Stündlich** während die App läuft.
- **Beim Beenden**, egal aus welchem Grund: *Beenden* im Menü,
  Abmelden, Neustart, Herunterfahren oder `SIGTERM`.
- **Vor riskanten Aktionen**: Laden einer Sicherung, Verschieben
  der Datendatei oder Wechsel auf eine andere Datendatei.

Damit die Festplatte nicht mit identischen Kopien volläuft,
wenn sich die Matrix nicht geändert hat, dedupliziert EiTodo:
Stimmen die aktuellen Daten mit der jüngsten Sicherung überein
(Sync-Metadaten ausgenommen), wird die bestehende Sicherung
einfach mit dem neuen Zeitstempel umbenannt, statt erneut
kopiert zu werden.

Die Anzahl der aufbewahrten Sicherungen wird über
**Menü → Anzahl der Sicherungen…** gesteuert: jeder Wert ab
**20** aufwärts (Standard **100**, keine Obergrenze). Die
Einstellung steht in `config.INI` unter
`[CONFIG] → backups_to_keep`. Überschüssige Sicherungen werden
sofort entfernt, wenn Sie den Wert ändern; danach werden die
ältesten Sicherungen jeweils dann gelöscht, wenn die Grenze
erneut überschritten wird.

Zum Wiederherstellen einer Sicherung **Menü → Sicherung laden**:
eine `.json`-Datei aus dem Save-Ordner auswählen und
bestätigen. Vor dem Ersetzen der aktuellen Aufgaben schreibt
EiTodo eine frische Sicherung der *aktuellen* Matrix, so dass
auch das Laden selbst rückgängig gemacht werden kann.

## Reaktionsfähigkeit der Oberfläche

Nachdem Sie aufhören zu tippen, wartet EiTodo einen kurzen
Moment, bevor die Zeile formatiert und gespeichert wird — dieses
„Debounce“ vermeidet Arbeit bei jedem Tastendruck. **Menü →
Reaktionsfähigkeit der Oberfläche…** öffnet einen Schieberegler
mit Rasten: nach links für eine kürzere Verzögerung (reaktiver,
etwas häufigere Arbeit) oder nach rechts für eine längere
Verzögerung (ressourcenschonender). Die Rasten reichen von 200
bis 1000 ms in 100-ms-Schritten; **Standardwerte
wiederherstellen** setzt auf 400 ms zurück. Die Änderung wirkt
sofort.
