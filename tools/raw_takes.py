"""Record list-reading takes ("Mah. Meh. Mie. Moh. Muh.") with character timestamps.

Reads a plan JSON: {"takes":[{"id","model","text","items":[{"key","say"}]}]}
Writes voice/raw/<id>.mp3 and voice/raw/<id>.json (alignment + items).
Env: ELEVENLABS_API_KEY, PLAN (path), VOICE_ID, ONLY_MISSING ("true"/"false"), ONLY_IDS (comma list)
"""
import base64, json, os, sys, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "voice", "raw")
KEY = os.environ.get("ELEVENLABS_API_KEY", "").strip()
PLAN = os.environ.get("PLAN", "").strip() or "voice/takes_plan.json"
VOICE = os.environ.get("VOICE_ID", "").strip() or "hSzY2zmYNQPukJaIll7k"
ONLY_MISSING = os.environ.get("ONLY_MISSING", "true").lower() != "false"
ONLY_IDS = {k.strip() for k in os.environ.get("ONLY_IDS", "").split(",") if k.strip()}
if not KEY:
    sys.exit("ELEVENLABS_API_KEY fehlt.")
os.makedirs(RAW, exist_ok=True)
plan = json.load(open(os.path.join(ROOT, PLAN), encoding="utf-8"))
lang_off = set()

def call(text, model, use_lang, seed=4242):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?output_format=mp3_44100_128"
    p = {"text": text, "model_id": model, "seed": seed,
         "voice_settings": {"stability": 0.6, "similarity_boost": 0.8, "style": 0.1, "speed": 0.85}}
    if model.startswith("eleven_v3"):
        p["voice_settings"] = {"stability": 0.5, "similarity_boost": 0.8}
    if use_lang:
        p["language_code"] = "de"
    req = urllib.request.Request(url, data=json.dumps(p).encode(), method="POST",
                                 headers={"xi-api-key": KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

chars = made = 0
for t in plan["takes"]:
    if ONLY_IDS and t["id"] not in ONLY_IDS:
        continue
    base = os.path.join(RAW, t["id"])
    if ONLY_MISSING and not ONLY_IDS and os.path.exists(base + ".json"):
        continue
    for attempt in range(3):
        try:
            res = call(t["text"], t["model"], t["model"] not in lang_off, t.get("seed", 4242))
            break
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            if e.code in (400, 422) and "language" in msg.lower() and t["model"] not in lang_off:
                lang_off.add(t["model"]); print("language_code nicht unterstützt für", t["model"]); continue
            if e.code in (401, 402, 403):
                sys.exit(f"ElevenLabs lehnt ab ({e.code}): {msg}")
            print(f"retry {t['id']} ({e.code}): {msg}"); time.sleep(4 * (attempt + 1))
        except Exception as e:
            print(f"retry {t['id']}: {e}"); time.sleep(4 * (attempt + 1))
    else:
        print("FEHLER", t["id"]); continue
    open(base + ".mp3", "wb").write(base64.b64decode(res["audio_base64"]))
    json.dump({"id": t["id"], "model": t["model"], "voice": VOICE, "text": t["text"], "items": t["items"],
               "alignment": res.get("alignment")}, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False)
    chars += len(t["text"]); made += 1
    print(f"ok   {t['id']}: {t['text']}")
print(f"\n{made} Aufnahmen, {chars} Zeichen.")
