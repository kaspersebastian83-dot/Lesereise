"""Generate all game clips with ElevenLabs into audio/<key>.mp3 and write audio/manifest.json.

Env: ELEVENLABS_API_KEY (required), VOICE_ID, MODEL_ID, ONLY_MISSING ("true"/"false"), ONLY_KEYS (comma list, optional),
     ALIGN_PREFIXES (comma list, default "t2_flaumi_,t2_eefje_,t2_feenfest_,t2_klonki_,t2_peppio_,t2_tasse_,t2_kiki_,t2_picknick_,t2_einkauf_"): these clips are made with character timestamps; next to the mp3 the
     script writes audio/align/<key>.json = {"d": seconds, "cs": [start of every character of the text in 1/100 s], "e": loudness
     every 20 ms as digits 0-9}. The game uses it to time animations to the exact word and to move a character's mouth.
"""
import base64, difflib, json, os, subprocess, sys, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO = os.path.join(ROOT, "audio")
KEY = os.environ.get("ELEVENLABS_API_KEY", "").strip()
VOICE = os.environ.get("VOICE_ID", "").strip() or "hSzY2zmYNQPukJaIll7k"
MODEL = os.environ.get("MODEL_ID", "").strip() or "eleven_multilingual_v2"
ONLY_MISSING = os.environ.get("ONLY_MISSING", "true").lower() != "false"
ONLY_KEYS = {k.strip() for k in os.environ.get("ONLY_KEYS", "").split(",") if k.strip()}
ALIGN_PREFIXES = tuple(p.strip() for p in (os.environ.get("ALIGN_PREFIXES", "") or "t2_flaumi_,t2_eefje_,t2_feenfest_,t2_klonki_,t2_peppio_,t2_tasse_,t2_kiki_,t2_picknick_,t2_einkauf_").split(",") if p.strip())
ALIGN_DIR = os.path.join(AUDIO, "align")

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

def tts(text, stamps=False):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}{'/with-timestamps' if stamps else ''}?output_format=mp3_44100_64"
    payload = {
        "text": text,
        "model_id": MODEL,
        "voice_settings": {"stability": 0.6, "similarity_boost": 0.8, "style": 0.2, "speed": 0.9},
    }
    if LANG["on"]:
        payload["language_code"] = "de"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "xi-api-key": KEY, "Content-Type": "application/json", "Accept": "application/json" if stamps else "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
    if not stamps:
        return data, None
    j = json.loads(data)
    return base64.b64decode(j["audio_base64"]), j.get("alignment") or j.get("normalized_alignment")


def char_starts(text, al):
    """start time (1/100 s) for every character of text, from the alignment ElevenLabs returns"""
    chars = al.get("characters") or []
    st = al.get("character_start_times_seconds") or []
    got = "".join(chars)
    out = [None] * len(text)
    if got == text:
        out = [round(s * 100) for s in st]
    else:
        sm = difflib.SequenceMatcher(None, text, got, autojunk=False)
        for a, b, n in sm.get_matching_blocks():
            for i in range(n):
                out[a + i] = round(st[b + i] * 100)
        last = 0
        for i, v in enumerate(out):  # fill gaps with the time before them
            if v is None:
                out[i] = last
            else:
                last = v
    return out


def envelope(path):
    """loudness every 20 ms as digits 0-9 (for the mouth), and the length in s"""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    hop = 320
    n = len(x) // hop
    if n == 0:
        return "", 0
    rms = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    top = float(np.percentile(rms, 98)) or 1.0
    lv = np.clip(np.round(rms / top * 9), 0, 9).astype(int)
    return "".join(str(v) for v in lv), round(len(x) / 16000, 3)

made, failed = 0, []
for k, t in clips:
    if k.startswith(("silbe_", "laut_", "wort_", "u_", "s_")):
        continue  # syllables and letter sounds come from list takes (tools/syllable_pipeline.py)
    if ONLY_KEYS and k not in ONLY_KEYS:
        continue
    path = os.path.join(AUDIO, k + ".mp3")
    if ONLY_MISSING and not ONLY_KEYS and os.path.exists(path):
        continue
    for attempt in range(3):
        try:
            stamps = k.startswith(ALIGN_PREFIXES)
            data, al = tts(t, stamps)
            with open(path, "wb") as f:
                f.write(data)
            if stamps:
                os.makedirs(ALIGN_DIR, exist_ok=True)
                env, dur = envelope(path)
                rec = {"d": dur, "e": env}
                if al:
                    rec["cs"] = char_starts(t, al)
                with open(os.path.join(ALIGN_DIR, k + ".json"), "w", encoding="utf-8") as f:
                    json.dump(rec, f, separators=(",", ":"))
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
