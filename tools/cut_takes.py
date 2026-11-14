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

def grain_noise(x, target, grain=0.04, seed=1):
    """extend a noise-like sound (s, f, h, r) by overlap-adding Hann-windowed grains from random places"""
    rng = np.random.default_rng(seed)
    g = int(SR * grain); hop = g // 2; n = int(SR * target)
    src = x[int(len(x) * 0.15):int(len(x) * 0.85)]
    if len(src) < g + 1: src = x
    if len(src) < g + 1: return x
    w = np.hanning(g).astype(np.float32); out = np.zeros(n + g, np.float32)
    for pos in range(0, n, hop):
        st = rng.integers(0, len(src) - g); out[pos:pos + g] += src[st:st + g] * w
    rms_src = np.sqrt((src ** 2).mean()); rms_out = np.sqrt((out[:n] ** 2).mean()) + 1e-9
    return out[:n] * (rms_src / rms_out)

def psola_hold(x, target):
    """extend a voiced steady sound (m, n, l, w) by repeating whole pitch periods (TD-PSOLA, same pitch)"""
    mid = x[int(len(x) * 0.2):int(len(x) * 0.8)]
    if len(mid) < int(SR * 0.02): return stretch(x, max(0.1, len(x) / SR / target), True)
    seg = mid - mid.mean()
    ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
    lo, hi = int(SR / 400), int(SR / 120)
    P = lo + int(np.argmax(ac[lo:hi]))
    if ac[P] < 0.3 * ac[0]: return stretch(x, max(0.1, len(x) / SR / target), True)
    # pitch marks: peaks spaced by ~P inside the middle part
    marks = []; i = int(np.argmax(np.abs(mid[:P])))
    while i + P < len(mid):
        j = i + P; a, b = max(0, j - P // 4), min(len(mid), j + P // 4)
        j = a + int(np.argmax(mid[a:b])) if b > a else j
        marks.append(i); i = j
    if len(marks) < 3: return stretch(x, max(0.1, len(x) / SR / target), True)
    n = int(SR * target); out = np.zeros(n + 2 * P, np.float32); w = np.hanning(2 * P).astype(np.float32)
    seq = marks + marks[-2:0:-1]  # ping-pong through the periods
    k = 0
    for pos in range(P, n, P):
        m = seq[k % len(seq)]; k += 1
        a = m - P; b = m + P
        if a < 0 or b > len(mid): continue
        out[pos - P:pos + P] += mid[a:b] * w
    out = out[:n]
    return out * (np.sqrt((mid ** 2).mean()) / (np.sqrt((out[int(SR*0.02):] ** 2).mean()) + 1e-9))

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

def level(x, target_db=-15.5, peak_db=-1.0):
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

def cut_items(x, wins, lead_end=None):
    segs = segments(x)
    out = []
    for w_i, w in enumerate(wins):
        if w is None: out.append(None); continue
        key, say, t0, t1 = w
        ov = [s for s in segs if s[1] > t0 - 0.03 and s[0] < t1 + 0.03]
        if not ov:
            out.append(None); continue
        a, b = ov[0][0], ov[-1][1]
        if w_i == 0 and lead_end is not None and a < lead_end - 0.1:
            # the lead-in ("Lies mit:") ran straight into the first word: split at the quietest spot between them
            db = env_db(x); lo = int(max(a, lead_end - 0.25) / 0.005); hi = int(min(b, t0 + 0.12) / 0.005)
            if hi > lo + 2: a = (lo + int(np.argmin(db[lo:hi]))) * 0.005
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
    # voiced/nasal consonants (m n l w r) and the voiced German s/z: vowel formant band; voiceless: voicing band
    e = env_db(band(seg, 700, 2500) if C in "mnlwrsz" else lowband(seg))
    top = e.max()
    hint = int(c_end_hint / 0.005)
    lo, hi = max(0, hint - 8), min(len(e) - 1, hint + 12)
    if not (0.02 <= c_end_hint <= 0.35):  # aligner is off (happens with v3): search by signal only
        lo, hi = 2, min(len(e) - 1, 70)
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
        _al = take["alignment"]; _tx = "".join(_al["characters"]); _ci = _tx.find(":") if ":" in _tx[:20] else -1
        lead_end = _al["character_end_times_seconds"][_ci] if _ci >= 0 else None
        for c in cut_items(x, wins, lead_end):
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
            if not key.startswith("silbe_") or not (len(syl) == 2 and syl[1] in "aeiou" and syl[0] not in "aeiou"):
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
            if C == "h" and V == "a" and tid.endswith("v3L"):
                encode(fade(level(seg[on:]), 0.002, 0.05), os.path.join(OUT, "_ref_a.mp3"))
            DIAG.append(f"{tid}\t{say}\tseg={len(seg)/SR:.3f}\thint={c_end:.3f}\tonset={on/SR:.3f}\tcons={dur:.3f}")
            if C in HELD and dur >= 0.04:
                # chosen after phoneme checks: grains for steady noise (f, h), a smooth stretch for the rest,
                # z stays natural ("ts"); repeating periods (PSOLA) made w/s wobble like "wa-wa"
                if C == "z":
                    y = fade(level(cons), 0.01, 0.04)
                elif C in "fh":
                    y = fade(level(np.concatenate([cons[:int(SR * 0.02)], grain_noise(cons, 0.42 if C == "h" else 0.55)])), 0.03, 0.12)
                else:
                    target = 0.32 if C == "l" else 0.5
                    y = fade(level(stretch(cons, max(0.1, min(1.0, dur / target)), C in "mnlw")), 0.03, 0.12)
            elif C in VOICELESS_STOP:
                y = fade(level(seg[:on + int(SR * 0.008)]), 0.002, 0.02)
            elif C in VOICED_STOP:
                y = fade(level(seg[:on + int(SR * 0.055)]), 0.002, 0.04)
            else:
                continue
            encode(pad(y), os.path.join(OUT, f"laut_{C}__{tid}-{V}.mp3")); made += 1
            if C in HELD and dur >= 0.04 and os.environ.get("RAWCONS"):  # diagnosis variants
                body = cons
                V_ = {"kurz": fade(level(cons), 0.01, 0.03),
                      "psola": fade(level(np.concatenate([cons[:int(SR * 0.03)], psola_hold(cons, 0.5)])), 0.03, 0.12),
                      "rb": fade(level(stretch(cons, max(0.1, dur / 0.5), C not in "fh")), 0.03, 0.12),
                      "grain": fade(level(np.concatenate([cons[:int(SR * 0.02)], grain_noise(cons, 0.5)])), 0.03, 0.12)}
                for nm, yy in V_.items():
                    encode(pad(yy), os.path.join(OUT, f"laut_{C}__{tid}-{V}~{nm}.mp3")); made += 1
    open(os.path.join(OUT, "_diag.tsv"), "w").write("\n".join(DIAG))
    print(made, "Dateien geschrieben nach", OUT)

if __name__ == "__main__":
    main()
