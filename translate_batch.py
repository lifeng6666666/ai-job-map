# -*- coding: utf-8 -*-
"""
批量翻译：直接调用 Google gtx 接口，多条文本合并为一次请求（分隔符拆回），失败逐条回退。
缓存 translation_cache.json 支持断点续跑。输出 occupations_zh.json
"""
import json, os, time, urllib.request, urllib.parse, re

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE, "translation_cache.json")
SEP = "@@SEP@@"

cache = {}
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, encoding="utf-8") as f:
        cache = json.load(f)

def save_cache(force=False):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

def gtx(text):
    """单段翻译，<=5000字符，通过 curl 子进程（自动重试）"""
    url = ("https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q="
           + urllib.parse.quote(text))
    import subprocess
    for attempt in range(5):
        p = subprocess.run(
            ["curl.exe", "-s", "--max-time", "30", "--retry", "3", "--retry-all-errors",
             "-A", "Mozilla/5.0", url],
            capture_output=True, timeout=60)
        if p.returncode == 0 and p.stdout.strip():
            data = json.loads(p.stdout.decode("utf-8", "replace"))
            return "".join(seg[0] for seg in data[0])
        time.sleep(1 + attempt)
    raise RuntimeError("gtx failed after retries")

def translate_batch(texts):
    """批量：合并 -> 翻译 -> 拆回。返回与 texts 等长的列表。"""
    results = [cache.get(t) for t in texts]
    todo = [i for i, r in enumerate(results) if r is None]
    if not todo:
        return results
    # 分块（每块合并文本 <= 4200 字符）
    chunks, cur, cur_len = [], [], 0
    for i in todo:
        t = texts[i]
        if cur and cur_len + len(SEP) + len(t) > 4200:
            chunks.append(cur); cur, cur_len = [], 0
        cur.append(t); cur_len += len(t) + len(SEP)
    if cur: chunks.append(cur)

    for chunk in chunks:
        merged = SEP.join(chunk)
        ok = False
        for attempt in range(3):
            try:
                out = gtx(merged)
                parts = re.split(r"\s*@@\s*SEP\s*@@\s*", out)
                if len(parts) == len(chunk):
                    for t, p in zip(chunk, parts):
                        cache[t] = p.strip()
                    ok = True
                    break
                # 分隔符被改写，逐条重试
                for t in chunk:
                    if cache.get(t) is None:
                        cache[t] = gtx(t)
                        time.sleep(0.4)
                ok = True
                break
            except Exception as e:
                print("  chunk retry %d: %s" % (attempt, str(e)[:60]), flush=True)
                time.sleep(2)
        if not ok:
            for t in chunk:
                if cache.get(t) is None:
                    raise RuntimeError("failed: " + t[:50])
        time.sleep(0.6)
        print("  chunk done (%d items, %d/%d)" % (len(chunk), sum(1 for t in texts if cache.get(t) is not None), len(texts)), flush=True)
        save_cache()
    return [cache[t] for t in texts]

def main():
    with open(os.path.join(BASE, "occupations.json"), encoding="utf-8") as f:
        data = json.load(f)

    print("== skills ==", flush=True)
    skills_zh = translate_batch(data["skills"])
    print(skills_zh[:10], flush=True)

    print("== groups ==", flush=True)
    groups = sorted(set(j["g"] for j in data["jobs"]))
    groups_zh = dict(zip(groups, translate_batch(groups)))

    print("== titles ==", flush=True)
    titles = [j["t"] for j in data["jobs"]]
    titles_zh = translate_batch(titles)
    save_cache()

    print("== descs ==", flush=True)
    descs = [j["d"] for j in data["jobs"]]
    descs_zh = translate_batch(descs)
    save_cache(True)

    for j, tz, dz in zip(data["jobs"], titles_zh, descs_zh):
        j["t"], j["d"], j["g"] = tz, dz, groups_zh[j["g"]]
        j["te"], j["de"] = j["t"], j["d"]
    # 恢复英文原名/原描述
    en = {x["c"]: x for x in json.load(open(os.path.join(BASE, "occupations.json"), encoding="utf-8"))["jobs"]}
    for j in data["jobs"]:
        j["te"], j["de"] = en[j["c"]]["t"], en[j["c"]]["d"]

    out = {"skills": skills_zh, "ai": data["ai"], "jobs": data["jobs"]}
    with open(os.path.join(BASE, "occupations_zh.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("DONE. size: %.1f KB" % (os.path.getsize(os.path.join(BASE, "occupations_zh.json")) / 1024), flush=True)

if __name__ == "__main__":
    main()
