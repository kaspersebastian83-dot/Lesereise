# Funkels Lesereise

Lesen-lern-Spiel für Kinder ab ca. 3 Jahren – eine einzige HTML-Datei, offline nutzbar, keine Abhängigkeiten.

## Stationen
1. **Flüsterwald (Laute hören)** – Laut hören, Buchstaben finden
2. **Mondwiese (Anlaut)** – Womit fängt das Wort an?
3. **Zauberbrücke (Zusammenschieben)** – zwei Laute zu einer Silbe verbinden (M + A → MA)
4. **Sternenturm (Wörter lesen)** – Wort in farbigen Silben lesen, passendes Bild antippen

Buchstaben kommen in fünf Stufen dazu: `M A L O I` → `S N E` → `R T U` → `D H P F` → `B K W G Z`.

## Einhörner
Funkel und 15 Einhorn-Freundinnen. Nach jeder geschafften Runde kommt eine neue dazu – jede mit eigener kleiner
Geschichte und Animation (aus der Wolke, vom Regenbogen, hinter dem Mond …). Auf der Einhornwiese (🦄-Knopf) wohnen alle;
antippen = Name hören. Nach jeder richtigen Antwort fliegt ein Einhorn mit Glitzerspur vorbei.

## Zauberreise (🗺️)
Einhorn aussuchen → Ort aussuchen (Zauberwald, Glitzermeer, Blumenwiese, Wolkenschloss, Zuckerland, Sternenreise) →
Ritt durch die Landschaft, unterwegs Glitzer fangen → am Ziel wartet ein kleines Abenteuer: Jemand braucht Hilfe
(Eule, Waldfee, Meerjungfrau, Papagei Polly, Marienkäfer, Schmetterling, Wolkenprinzessin, kleiner Drache, Bäcker-Bär,
Maus, Astronautin Mia, Sternchen). Drei Dinge werden gesucht – das Wort steht groß in Silbenfarben da und wird vorgelesen.
Zum Dank gibt es ein Geschenk für die Schatzkiste (🎁, 12 Geschenke, 2 Abenteuer je Ort). Danach freies Antippen.

## Märchenbuch (📖)
Sechs eigene Märchen, jedes in sieben Szenen interaktiv erzählt (antippen, alles einsammeln, wählen, suchen):
Die kleine Laterne · Die Prinzessin, die nicht lachen konnte · Die kleine Welle · Der Bär, der einen Mond backen wollte ·
Die Schneeflocke und der Frühling · Der kleine Drache und der Glitzer. Das gewählte Einhorn ist immer dabei.
Niemand bleibt hängen: nach 7 s leuchtet das Richtige und die Bitte wird wiederholt, nach 2 falschen Tipps leuchtet es sofort,
nach 22 s löst sich die Szene selbst und das Märchen geht weiter. Dasselbe gilt für die Abenteuer auf den Reisen.

**Neue Märchenbühne (zuerst: Die kleine Laterne).** Jede Szene ist eine Bühne mit Tiefenebenen (Himmel, Ferne, Mitte, Spielebene,
Vordergrund) in CSS-3D: Das Buch klappt auf, die Kamera fliegt von Ort zu Ort, die Ebenen bewegen sich leicht mit dem Finger.
Eine Zeichenfläche darüber macht Licht und Dunkelheit (die Laterne leuchtet wirklich), Glühwürmchen, Wind, Blätter und Glitzer.
Alles ohne Bibliotheken, offline. Gesten (ein Finger): Staub wegreiben, gedrückt halten, ziehen und ablegen, einem Weg nachfahren,
wegwischen, antippen. Sicherheitsnetz für jede Geste: Beim Start zeigt ein Geisterfinger 👆 einmal die Bewegung; nach 7 s und
14,5 s zeigt er sie wieder und der Hinweis wird gesprochen; nach 2 Fehlversuchen sofort; nach 22 s macht die Szene es selbst
(spätestens nach 45 s). Was das Kind tut, löst das Nächste aus; die Erzählung danach ist in Stücke geteilt, damit Bild und
Stimme genau zusammenpassen. Aufnahmen: `t2_<märchen>_<szene>` (Erzählung), `…h` (Hinweis), `…d1, d2 …` (was passiert ist).

## Elternbereich
Zahnrad auf dem Startbildschirm 1,5 Sekunden gedrückt halten: Stufe, Schrift (GROSS / Groß-klein), Rundenlänge, Stimme.

## Stimme
Ohne Aufnahmen spricht die Gerätestimme. Im Elternbereich steht die Liste aller Aufnahmen (Dateiname + Text),
z. B. `laut_m.mp3`, `silbe_ma.mp3`, `wort_mama.mp3`; dort lassen sich die Dateien auch importieren.

## Stimmen mit ElevenLabs erzeugen (einmalig)
1. Repo → **Settings → Secrets and variables → Actions → New repository secret**:
   Name `ELEVENLABS_API_KEY`, Wert = API-Key aus ElevenLabs (Profil → API Keys).
2. Repo → **Actions → „Stimmen erzeugen“ → Run workflow**.
   Die Aktion erzeugt alle Aufnahmen aus `voice/clips.tsv` nach `audio/` und committet sie.
   Standardstimme: Carlotta (deutsch, Kinderbücher), ca. 1 000 Zeichen insgesamt.
3. Einzelne Aufnahmen neu machen: beim Start im Feld „Nur diese Aufnahmen“ z. B. `laut_t,laut_p` eintragen.

Reihenfolge beim Abspielen: auf dem Gerät importierte Aufnahme → Aufnahme aus `audio/` → Gerätestimme.
Wenn Wörter im Spiel geändert werden, muss `voice/clips.tsv` mitgeändert werden.

## Silben und Laute
Silben werden nicht einzeln vorgelesen (das klang oft englisch oder seltsam), sondern als Liste
wie bei einer Lehrerin („Lies mit: Mah. Meh. Mie. Moh. Muh.“, ElevenLabs v3 mit Zeitmarken) und dann geschnitten.
Die Einzellaute werden aus diesen Aufnahmen gebaut: Vokale gehalten, M/N/L/S/W/R gedehnt, F/H verlängert, T/P/K/B/D/G kurz.
Das passiert automatisch in „Stimmen erzeugen“. Einzelne Silben/Laute neu: bei „Nur diese Aufnahmen“ z. B. `silbe_me,laut_m` eintragen –
dann wird die ganze Zeile neu aufgenommen.

„Aufnahmen prüfen“ (kostet keine Credits) lässt eine Lauterkennung hören, was in den Dateien gesprochen wird; Ergebnis im Log.
Auswahl je Silbe/Laut: `voice/auswahl.json` (`alt` = frühere Einzelaufnahme behalten).
