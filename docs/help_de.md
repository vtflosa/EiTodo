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

Alternativ können Sie die Datei in einem Ordner ablegen, der
über das lokale Netzwerk geteilt wird — eine NAS-Freigabe
(Samba/NFS) oder jede andere Freigabe, die auf jedem Rechner
eingehängt ist. Im LAN werden Änderungen praktisch sofort
übernommen: eine Bearbeitung auf einem Rechner erscheint
binnen einer Sekunde auf den anderen, ohne Umweg über die
Cloud.

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
