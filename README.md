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
Ritt durch die Landschaft, unterwegs Glitzer fangen → am Ziel Dinge antippen: sie hüpfen, sagen ihr Wort und zeigen es
groß in Silbenfarben.

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
