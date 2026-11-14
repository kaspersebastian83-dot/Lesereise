"""Cut single syllables out of list-reading takes and build the letter sounds (Laute) from them.

Input:  voice/raw/<take>.mp3 + .json (alignment from raw_takes.py)
Output: <OUT>/<key>__<take>.mp3 for every syllable item, plus letter sounds:
        vowels   laut_a..u   = the read vowel, stretched to ~0.75 s
        held     m n l s f w r h z = consonant part of a syllable, stretched to ~0.6 s
        short    t p k (burst only), b d g (burst + a hint of vowel)
Env: OUT (default voice/kandidaten), TAKES (comma list of take ids or prefixes; default all)
Needs ffmpeg with rubberband and numpy.
"""
import json, os, subprocess, sys, glob
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "voice", "raw")
OUT = os.path.join(ROOT, os.environ.get("OUT", "voice/kandidaten"))
SEL = [s.strip() for s in os.environ.get("TAKES", "").split(",") if s.strip()]
SR = 44100
HOP = int(SR * 0.005)  # 5 ms frames
os.makedirs(OUT, exist_ok=True)

HELD = set("mnlsfwrhz")
VOICELESS_STOP = set("tpk")
VOICED_STOP = set("bdg")

def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()

def encode(x, path, filt=None):
    x = np.asarray(x, dtype=np.float32)
    args = ["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-"]
    if filt:
        args += ["-af", filt]
    args += ["-ac", "1", "-ar", str(SR), "-b:a", "64k", path]
    subprocess.run(args, input=x.tobytes(), check=True)

def stretch(x, tempo, voiced=True):
    """time-stretch with rubberband (tempo < 1 = longer), pitch unchanged"""
    opts = "window=long:phase=laminar:transients=smooth" if voiced else "window=standard:transients=smooth"
    out = []
    t = tempo
    while t < 0.999:  # rubberband handles big ratios, but chain for very long stretches
        step = max(t, 0.25); t /= step
        raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                              "-af", f"rubberband=tempo={step:.4f}:{opts}", "-f", "f32le", "-"],
                             input=np.asarray(x, np.float32).tobytes(), capture_output=True, check=True).stdout
        y = np.frombuffer(raw, dtype=np.float32).copy()
        if len(y) < len(x):  # rubberband needs some input; pad and retry once
            xp = np.concatenate([x, np.zeros(int(SR * 0.25), np.float32)])
            raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                                  "-af", f"rubberband=tempo={step:.4f}:{opts}", "-f", "f32le", "-"],
                                 input=xp.tobytes(), capture_output=True, check=True).stdout
            y = np.frombuffer(raw, dtype=np.float32).copy()[:int(len(x) / step)]
        x = y
    return x

def env_db(x):
    n = len(x) // HOP
    f = x[:n * HOP].reshape(n, HOP)
    return 20 * np.log10(np.sqrt((f ** 2).mean(1)) + 1e-9)

def lowband(x, cutoff=900.0):
    from scipy.signal import butter, sosfiltfilt
    return sosfiltfilt(butter(4, cutoff, "low", fs=SR, output="sos"), x).astype(np.float32)

def fade(x, fin=0.004, fout=0.03):
    x = x.copy(); a = min(int(SR * fin), len(x) // 3); b = min(int(SR * fout), len(x) // 2)
    if a: x[:a] *= np.linspace(0, 1, a)
    if b: x[-b:] *= np.linspace(1, 0, b) ** 1.5
    return x

def level(x, target_db=-19.0, peak_db=-1.5):
    act = x[np.abs(x) > 10 ** (-50 / 20)]
    rms = np.sqrt((act ** 2).mean()) if len(act) else 1e-6
    g = 10 ** (target_db / 20) / max(rms, 1e-6)
    pk = np.abs(x).max() * g
    if pk > 10 ** (peak_db / 20):
        g *= 10 ** (peak_db / 20) / pk
    return x * g

def pad(x, pre=0.03, post=0.08):
    return np.concatenate([np.zeros(int(SR * pre), np.float32), x, np.zeros(int(SR * post), np.float32)])

def item_windows(take):
    """[(key, say, t0, t1)] from character alignment"""
    al = take["alignment"]; text = take["text"]
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    joined = "".join(chars)
    if joined != text:  # alignment text may differ slightly; fall back to search in joined
        text = joined
    pos = text.find(":") + 1 if ":" in text[:20] else 0
    res = []
    for it in take["items"]:
        i = text.find(it["say"], pos)
        if i < 0:
            print("  !! nicht gefunden:", it["say"], "in", take["id"]); res.append(None); continue
        j = i + len(it["say"]) - 1
        res.append((it["key"], it["say"], st[i], en[j])); pos = j + 1
    return res

def segments(x, thr_rel=-56.0, min_sil=0.07):
    """speech segments separated by >= min_sil of silence (frame-based)"""
    db = env_db(x); thr = db.max() + thr_rel
    loud = db > thr
    segs = []; i = 0; n = len(loud); ms = int(min_sil / 0.005)
    while i < n:
        if loud[i]:
            j = i
            while j < n:
                if not loud[j]:
                    k = j
                    while k < n and not loud[k]: k += 1
                    if k - j >= ms or k >= n: break
                    j = k
                else:
                    j += 1
            segs.append((i * 0.005, min(j, n) * 0.005)); i = j
        else:
            i += 1
    return segs

def cut_items(x, wins):
    segs = segments(x)
    out = []
    for w_i, w in enumerate(wins):
        if w is None: out.append(None); continue
        key, say, t0, t1 = w
        ov = [s for s in segs if s[1] > t0 - 0.03 and s[0] < t1 + 0.03]
        if not ov:
            out.append(None); continue
        a, b = ov[0][0], ov[-1][1]
        # never reach into the neighbours' aligned windows
        if w_i > 0 and wins[w_i - 1]: a = max(a, (wins[w_i - 1][3] + t0) / 2 if ov[0][0] < wins[w_i - 1][3] else a)
        if w_i + 1 < len(wins) and wins[w_i + 1]: b = min(b, (t1 + wins[w_i + 1][2]) / 2 if ov[-1][1] > wins[w_i + 1][2] else b)
        out.append((key, say, a, b, t0, t1))
    return out

def band(x, lo, hi):
    from scipy.signal import butter, sosfiltfilt
    return sosfiltfilt(butter(4, [lo, hi], "band", fs=SR, output="sos"), x).astype(np.float32)

def vowel_onset(seg, c_end_hint, C):
    """sample index where the vowel starts inside a CV syllable segment.
    Nasals/liquids are judged by the 1-4 kHz band (vowel formants), the rest by the voicing band (<900 Hz).
    The search stays within -40/+60 ms of the aligner's estimate."""
    e = env_db(band(seg, 1000, 4000) if C in "mnlwr" else lowband(seg))
    top = e.max()
    hint = int(c_end_hint / 0.005)
    lo, hi = max(0, hint - 8), min(len(e) - 1, hint + 12)
    for k in range(lo, hi + 1):
        if e[k] > top - 10:
            return k * HOP
    return hint * HOP

DIAG = []
def main():
    takes = sorted(glob.glob(os.path.join(RAW, "*.json")))
    made = 0
    for jp in takes:
        take = json.load(open(jp, encoding="utf-8")); tid = take["id"]
        if SEL and not any(tid == s or tid.startswith(s) for s in SEL):
            continue
        x = decode(jp[:-5] + ".mp3")
        wins = item_windows(take)
        for c in cut_items(x, wins):
            if c is None: continue
            key, say, a, b, t0, t1 = c
            seg = x[int(a * SR):int(b * SR)]
            if len(seg) < SR * 0.08: print("  !! zu kurz", key, tid); continue
            if key.startswith("laut_"):          # vowel takes: "A. E. I. O. U."
                core = seg
                tempo = max(0.3, min(1.0, (len(core) / SR) / 0.75))
                y = stretch(core, tempo)
                encode(pad(fade(level(y), 0.01, 0.12)), os.path.join(OUT, f"{key}__{tid}.mp3")); made += 1
                continue
            encode(pad(fade(level(seg), 0.004, 0.04)), os.path.join(OUT, f"{key}__{tid}.mp3")); made += 1
            # letter sounds from CV syllables
            syl = key[6:]
            if not (len(syl) == 2 and syl[1] in "aeiou" and syl[0] not in "aeiou"):
                continue
            C, V = syl[0], syl[1]
            # aligned consonant end = start of 2nd char of the item
            al = take["alignment"]; text = "".join(al["characters"])
            idx = text.find(say, text.find(":") + 1 if ":" in text[:20] else 0)
            # search the right occurrence (items are in order, so use t0 proximity)
            best = None
            for i in range(len(text)):
                if text.startswith(say, i) and abs(al["character_start_times_seconds"][i] - t0) < 0.02:
                    best = i; break
            if best is None: best = idx
            c_end = al["character_start_times_seconds"][best + 1] - a
            on = vowel_onset(seg, max(0.0, c_end), C)
            cons = seg[:max(on - int(SR * 0.012), int(SR * 0.01))]
            dur = len(cons) / SR
            DIAG.append(f"{tid}\t{say}\tseg={len(seg)/SR:.3f}\thint={c_end:.3f}\tonset={on/SR:.3f}\tcons={dur:.3f}")
            if C in HELD and dur >= 0.04:
                if C == "z":   # keep the t-burst, stretch the s
                    k = int(SR * 0.03); y = np.concatenate([cons[:k], stretch(cons[k:], max(0.12, (dur - 0.03) / 0.45), False)])
                elif C in "sfh":
                    y = stretch(cons, max(0.08, dur / (0.45 if C == "h" else 0.6)), False)
                else:
                    y = stretch(cons, max(0.08, dur / 0.6), True)
                y = fade(level(y), 0.02, 0.12)
            elif C in VOICELESS_STOP:
                y = fade(level(seg[:on + int(SR * 0.008)]), 0.002, 0.02)
            elif C in VOICED_STOP:
                y = fade(level(seg[:on + int(SR * 0.055)]), 0.002, 0.04)
            else:
                continue
            encode(pad(y), os.path.join(OUT, f"laut_{C}__{tid}-{V}.mp3")); made += 1
    open(os.path.join(OUT, "_diag.tsv"), "w").write("\n".join(DIAG))
    print(made, "Dateien geschrieben nach", OUT)

if __name__ == "__main__":
    main()
