# Funkels Lesereise

Lesen-lern-Spiel für Kinder ab ca. 3 Jahren – eine einzige HTML-Datei, offline nutzbar, keine Abhängigkeiten.

## Stationen
1. **Flüsterwald (Laute hören)** – Laut hören, Buchstaben finden
2. **Mondwiese (Anlaut)** – Womit fängt das Wort an?
3. **Zauberbrücke (Zusammenschieben)** – zwei Laute zu einer Silbe verbinden (M + A → MA)
4. **Sternenturm (Wörter lesen)** – Wort in farbigen Silben lesen, passendes Bild antippen

Buchstaben kommen in fünf Stufen dazu: `M A L O I` → `S N E` → `R T U` → `D H P F` → `B K W G Z`.

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
