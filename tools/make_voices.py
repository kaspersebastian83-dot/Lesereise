"""Generate all game clips with ElevenLabs into audio/<key>.mp3 and write audio/manifest.json.

Env: ELEVENLABS_API_KEY (required), VOICE_ID, MODEL_ID, ONLY_MISSING ("true"/"false"), ONLY_KEYS (comma list, optional)
"""
import json, os, sys, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO = os.path.join(ROOT, "audio")
KEY = os.environ.get("ELEVENLABS_API_KEY", "").strip()
VOICE = os.environ.get("VOICE_ID", "").strip() or "hSzY2zmYNQPukJaIll7k"
MODEL = os.environ.get("MODEL_ID", "").strip() or "eleven_multilingual_v2"
ONLY_MISSING = os.environ.get("ONLY_MISSING", "true").lower() != "false"
ONLY_KEYS = {k.strip() for k in os.environ.get("ONLY_KEYS", "").split(",") if k.strip()}

if not KEY:
    sys.exit("ELEVENLABS_API_KEY fehlt (Repo → Settings → Secrets and variables → Actions).")

os.makedirs(AUDIO, exist_ok=True)
clips = []
with open(os.path.join(ROOT, "voice", "clips.tsv"), encoding="utf-8") as f:
    for line in f:
        if "\t" in line:
            k, t = line.rstrip("\n").split("\t", 1)
            clips.append((k, t))

LANG = {"on": True}  # force German; switched off automatically if the model refuses language_code

def tts(text):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_64"
    payload = {
        "text": text,
        "model_id": MODEL,
        "voice_settings": {"stability": 0.6, "similarity_boost": 0.8, "style": 0.2, "speed": 0.9},
    }
    if LANG["on"]:
        payload["language_code"] = "de"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "xi-api-key": KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

made, failed = 0, []
for k, t in clips:
    if k.startswith(("silbe_", "laut_")):
        continue  # syllables and letter sounds come from list takes (tools/syllable_pipeline.py)
    if ONLY_KEYS and k not in ONLY_KEYS:
        continue
    path = os.path.join(AUDIO, k + ".mp3")
    if ONLY_MISSING and not ONLY_KEYS and os.path.exists(path):
        continue
    for attempt in range(3):
        try:
            data = tts(t)
            with open(path, "wb") as f:
                f.write(data)
            made += 1
            print(f"ok   {k}: {t}")
            break
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            if e.code in (400, 422) and LANG["on"] and "language" in msg.lower():
                LANG["on"] = False
                print("Modell akzeptiert language_code nicht – ohne weiter.")
                continue
            if e.code in (401, 402, 403):
                sys.exit(f"ElevenLabs lehnt ab ({e.code}): {msg}")
            print(f"retry {k} ({e.code}): {msg}")
            time.sleep(3 * (attempt + 1))
        except Exception as e:
            print(f"retry {k}: {e}")
            time.sleep(3 * (attempt + 1))
    else:
        failed.append(k)

have = sorted(f[:-4] for f in os.listdir(AUDIO) if f.endswith(".mp3"))
with open(os.path.join(AUDIO, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump({"voice": VOICE, "model": MODEL, "clips": have}, f, ensure_ascii=False, indent=0)
print(f"\n{made} neu erzeugt, {len(have)} von {len(clips)} vorhanden.")
if failed:
    print("Fehlgeschlagen:", ", ".join(failed))
