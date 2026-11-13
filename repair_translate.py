# -*- coding: utf-8 -*-
"""修复翻译：清除缓存中"原文==译文"的脏条目并重新翻译，更新 occupations_zh.json"""
import json, os, time, subprocess, urllib.parse, re

BASE = os.path.dirname(os.path.abspath(__file__))
SEP = "@@SEP@@"

CACHE = os.path.join(BASE, "translation_cache.json")
ZH = os.path.join(BASE, "occupations_zh.json")
cache = json.load(open(CACHE, encoding="utf-8"))

def gtx(text):
    url = ("https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q="
           + urllib.parse.quote(text))
    for attempt in range(5):
        p = subprocess.run(["curl.exe", "-s", "--max-time", "30", "--retry", "3", "--retry-all-errors",
                            "-A", "Mozilla/5.0", url], capture_output=True, timeout=60)
        if p.returncode == 0 and p.stdout.strip():
            return "".join(seg[0] for seg in json.loads(p.stdout.decode("utf-8", "replace"))[0])
        time.sleep(1 + attempt)
    raise RuntimeError("gtx failed")

def translate_batch(texts):
    todo = [t for t in texts if cache.get(t) in (None, t)]
    chunks, cur, n = [], [], 0
    for t in todo:
        if cur and n + len(SEP) + len(t) > 4200:
            chunks.append(cur); cur, n = [], 0
        cur.append(t); n += len(t) + len(SEP)
    if cur: chunks.append(cur)
    for chunk in chunks:
        for attempt in range(3):
            try:
                out = gtx(SEP.join(chunk))
                parts = re.split(r"\s*@@SEP@@\s*", out)
                if len(parts) != len(chunk):
                    for t in chunk:
                        cache[t] = gtx(t); time.sleep(0.4)
                else:
                    for t, p in zip(chunk, parts):
                        cache[t] = p.strip()
                break
            except Exception as e:
                print("retry:", str(e)[:60], flush=True); time.sleep(2)
        else:
            raise RuntimeError("chunk failed")
        time.sleep(0.5)
        print("chunk done", flush=True)
    return [cache[t] for t in texts]

if __name__ == "__main__":
    d = json.load(open(ZH, encoding="utf-8"))
    bad = [j["te"] for j in d["jobs"] if j["t"] == j["te"]]
    print("bad titles:", len(bad), flush=True)
    fixed = translate_batch(bad)
    fix_map = dict(zip(bad, fixed))
    for j in d["jobs"]:
        if j["t"] == j["te"]:
            j["t"] = fix_map[j["te"]]
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(d, open(ZH, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    left = sum(1 for j in d["jobs"] if j["t"] == j["te"])
    print("remaining bad:", left, flush=True)
    for j in d["jobs"][:5]:
        print(j["t"], "|", j["te"], flush=True)
