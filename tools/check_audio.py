"""Check what each clip actually sounds like, with a phoneme recognizer (no ElevenLabs credits).

Recognizer: facebook/wav2vec2-lv-60-espeak-cv-ft (outputs IPA phones).
Expected phones: espeak-ng German for the clip text, or fixed IPA for single letter sounds.
Env: FOLDERS (comma list, default "audio"), KEYS (prefix filter, e.g. "laut_,silbe_"), WITH_PROMPTS
Files are matched to clips.tsv by name: "<key>.mp3" or "<key>__<variant>.mp3".
Prints lines: CHK <file> <key> <expected> <heard> <distance> <verdict>
"""
import os, re, subprocess, sys, glob
import numpy as np, torch
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDERS = [f.strip() for f in os.environ.get("FOLDERS", "audio").split(",") if f.strip()]
KEYS = [k.strip() for k in os.environ.get("KEYS", "laut_,silbe_,wort_").split(",") if k.strip()]

LAUT = {"m": "m", "l": "l", "s": "z", "n": "n", "r": "ʁ", "t": "t", "d": "d", "h": "h", "p": "p", "f": "f",
        "b": "b", "k": "k", "w": "v", "g": "ɡ", "z": "ts", "a": "aː", "e": "eː", "i": "iː", "o": "oː", "u": "uː"}
texts = {}
for line in open(os.path.join(ROOT, "voice", "clips.tsv"), encoding="utf-8"):
    if "\t" in line:
        k, t = line.rstrip("\n").split("\t", 1); texts[k] = t

def espeak(text):
    out = subprocess.run(["espeak-ng", "-v", "de", "-q", "--ipa", text], capture_output=True, text=True).stdout
    return out.strip()

EQ = [("ɡ", "g"), ("ɛ", "e"), ("ɪ", "i"), ("ɔ", "o"), ("ʊ", "u"), ("ʏ", "y"), ("œ", "ø"), ("ɐ", "a"),
      ("ʁ", "r"), ("ɾ", "r"), ("χ", "r"), ("ʀ", "r"), ("z", "s"), ("w", "v"), ("ʋ", "v"), ("ɑ", "a"), ("æ", "e"), ("ə", "e")]
def norm(ipa):
    ipa = " ".join(t[:-1] if t in ("ph", "th", "kh") else t for t in ipa.split())
    ipa = re.sub(r"[0-9ˈˌː̩̯ˑ\s\.\-ʰʔ'|]", "", ipa)
    for a, b in EQ:
        ipa = ipa.replace(a, b)
    return ipa

def lev(a, b):
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        p, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (ca != cb))
    return d[-1]

def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)

name = "facebook/wav2vec2-lv-60-espeak-cv-ft"
proc = Wav2Vec2Processor.from_pretrained(name)
model = Wav2Vec2ForCTC.from_pretrained(name).eval()

files = []
for f in FOLDERS:
    files += sorted(glob.glob(os.path.join(ROOT, f, "*.mp3")))
n_ok = n_bad = 0
for path in files:
    fn = os.path.basename(path)[:-4]
    key = fn.split("__")[0]
    if not any(key.startswith(k) for k in KEYS) or key not in texts:
        continue
    exp = LAUT[key[5:]] if key.startswith("laut_") else espeak(texts[key])
    wav = load(path)
    if len(wav) < 1600:
        print(f"CHK\t{fn}\t{key}\t{exp}\t(leer)\t9\tbad"); n_bad += 1; continue
    wav = np.pad(wav, (3200, 3200))
    x = proc(wav, sampling_rate=16000, return_tensors="pt").input_values
    with torch.no_grad():
        ids = model(x).logits.argmax(-1)
    heard = proc.batch_decode(ids)[0]
    a, b = norm(exp), norm(heard)
    dist = lev(a, b)
    verdict = "ok" if dist == 0 else ("near" if dist == 1 and len(a) >= 3 else "bad")
    n_ok += verdict == "ok"; n_bad += verdict == "bad"
    print(f"CHK\t{fn}\t{key}\t{exp}\t{heard}\t{dist}\t{verdict}", flush=True)
print(f"\nSUMMARY ok={n_ok} bad={n_bad}")
