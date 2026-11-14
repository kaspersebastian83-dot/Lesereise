"""Glue for the syllable/letter-sound pipeline.

  plan     – make sure every syllable and vowel in voice/clips.tsv is part of a list take in voice/takes_plan.json
             (new syllables are grouped into new v3 takes). REDO=key,key adds fresh retakes for those keys' lists.
  install  – copy the chosen candidate for every silbe_/laut_ key from voice/kandidaten to audio/<key>.mp3.
             Choice: voice/auswahl.json (key -> candidate name) if present, otherwise the newest take that has it.
"""
import json, os, random, shutil, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROOT, "voice", "takes_plan.json")
PICK = os.path.join(ROOT, "voice", "auswahl.json")
CAND = os.path.join(ROOT, "voice", "kandidaten")
AUDIO = os.path.join(ROOT, "audio")
LONG = {"a": "ah", "e": "eh", "i": "ie", "o": "oh", "u": "uh"}

def clips():
    out = {}
    for line in open(os.path.join(ROOT, "voice", "clips.tsv"), encoding="utf-8"):
        if "\t" in line:
            k, t = line.rstrip("\n").split("\t", 1); out[k] = t
    return out

def load_plan():
    return json.load(open(PLAN, encoding="utf-8")) if os.path.exists(PLAN) else {"takes": []}

def take(id, items, seed=None):
    t = {"id": id, "model": "eleven_v3", "text": "Lies mit: " + ". ".join(i["say"] for i in items) + ".", "items": items}
    if seed: t["seed"] = seed
    return t

def plan():
    P = load_plan(); T = P["takes"]; C = clips()
    covered = {i["key"] for t in T for i in t["items"]}
    missing = [{"key": k, "say": t} for k, t in C.items() if k.startswith("silbe_") and k not in covered]
    n = sum(1 for t in T if t["id"].startswith("syl_x"))
    for i in range(0, len(missing), 8):
        T.append(take(f"syl_x{n:03d}_v3", missing[i:i + 8])); n += 1
    redo = [k.strip() for k in os.environ.get("REDO", "").split(",") if k.strip()]
    pick = json.load(open(PICK, encoding="utf-8")) if os.path.exists(PICK) else {}
    done = set()
    v3 = [t for t in T if t["model"].startswith("eleven_v3")]
    for k in redo:
        if k.startswith("laut_") and k[5:] in "aeiou":
            src = next((t for t in reversed(v3) if t["id"].startswith("vow_")), None)
        elif k.startswith("laut_"):
            src = next((t for t in reversed(v3) if t["id"].startswith(f"cv_{k[5:]}_")), None)
        else:
            src = next((t for t in reversed(v3) if any(i["key"] == k for i in t["items"])), None)
        if not src or src["id"] in done: continue
        done.add(src["id"])
        base = src["id"].split("_r")[0]
        r = sum(1 for t in T if t["id"].startswith(base + "_r")) + 1
        nt = dict(take(f"{base}_r{r}", src["items"], seed=random.randint(1, 99999)))
        T.append(nt)
        for i in src["items"]: pick.pop(i["key"], None)
        if k.startswith("laut_"): pick.pop(k, None)
    json.dump(P, open(PLAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(pick, open(PICK, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print(f"Plan: {len(T)} Aufnahmen, {len(missing)} neue Silben, {len(done)} Wiederholungen")

def install():
    C = clips(); P = load_plan()
    pick = json.load(open(PICK, encoding="utf-8")) if os.path.exists(PICK) else {}
    order = [t["id"] for t in P["takes"]]
    rank = {tid: i for i, tid in enumerate(order)}
    os.makedirs(AUDIO, exist_ok=True)
    n = 0
    for k in C:
        if not k.startswith(("silbe_", "laut_")): continue
        if pick.get(k) == "alt" and os.path.exists(os.path.join(AUDIO, k + ".mp3")):
            continue  # the earlier single recording was judged better – keep it
        cands = [os.path.basename(f)[:-4] for f in glob.glob(os.path.join(CAND, k + "__*.mp3")) if "~" not in f]
        if not cands: continue
        name = pick.get(k) if pick.get(k) in cands else None
        if not name:
            def r(c):
                tid = c.split("__")[1].split("-")[0]
                v = c.split("-")[1] if "-" in c.split("__")[1] else ""
                v3 = 1 if P and any(t["id"] == tid and t["model"].startswith("eleven_v3") for t in P["takes"]) else 0
                return (v3, rank.get(tid, -1), v == "a")
            name = max(cands, key=r)
        shutil.copyfile(os.path.join(CAND, name + ".mp3"), os.path.join(AUDIO, k + ".mp3")); n += 1
    print(f"{n} Silben/Laute nach audio/ übernommen")

if __name__ == "__main__":
    {"plan": plan, "install": install}[sys.argv[1]]()
