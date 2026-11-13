# -*- coding: utf-8 -*-
"""
将 occupations.json 全部翻译为中文（技能名、职业大类、职业名、职业描述）
- 缓存至 translation_cache.json，支持断点续跑
- 主引擎 Google，失败回退 Alibaba / Sogou
输出: occupations_zh.json
"""
import json, os, time, sys

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE, "translation_cache.json")
cache = {}
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, encoding="utf-8") as f:
        cache = json.load(f)

_cache_dirty = 0

def save_cache(force=False):
    global _cache_dirty
    if force or _cache_dirty >= 30:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
        _cache_dirty = 0

def translate(text):
    if not text or not text.strip():
        return text
    if text in cache:
        return cache[text]
    for attempt in range(3):
        for engine, kwargs in (("google", {"to_language": "zh-CN"}),
                               ("alibaba", {"to_language": "zh"}),
                               ("sogou", {"to_language": "zh"})):
            try:
                import translators as ts
                r = ts.translate_text(text, translator=engine, from_language="en", **kwargs)
                if r and r.strip():
                    cache[text] = r
                    globals()["_cache_dirty"] += 1
                    save_cache()
                    time.sleep(0.35)
                    return r
            except Exception as e:
                print("  [%s] %s: %s" % (engine, attempt, str(e)[:60]), flush=True)
                time.sleep(1.5 * (attempt + 1))
        time.sleep(3)
    raise RuntimeError("translate failed: " + text[:60])

def main():
    with open(os.path.join(BASE, "occupations.json"), encoding="utf-8") as f:
        data = json.load(f)

    print("== skills ==", flush=True)
    skills_zh = [translate(s) for s in data["skills"]]
    print("== groups ==", flush=True)
    groups = sorted(set(j["g"] for j in data["jobs"]))
    groups_zh = {g: translate(g) for g in groups}
    print("== jobs ==", flush=True)
    jobs = data["jobs"]
    for i, j in enumerate(jobs):
        j["t"] = translate(j["t"])
        j["d"] = translate(j["d"])
        j["g"] = groups_zh[j["g"]]
        if (i + 1) % 20 == 0:
            print("progress %d/%d" % (i + 1, len(jobs)), flush=True)
            save_cache()
    save_cache(True)

    # 保留英文原名用于搜索与展示
    with open(os.path.join(BASE, "occupations.json"), encoding="utf-8") as f:
        en = json.load(f)
    en_by_code = {x["c"]: x for x in en["jobs"]}
    for j in jobs:
        j["te"] = en_by_code[j["c"]]["t"]
        j["de"] = en_by_code[j["c"]]["d"]

    out = {"skills": skills_zh, "ai": data["ai"], "jobs": jobs}
    with open(os.path.join(BASE, "occupations_zh.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("DONE. size: %.1f KB" % (os.path.getsize(os.path.join(BASE, "occupations_zh.json")) / 1024))

if __name__ == "__main__":
    main()
