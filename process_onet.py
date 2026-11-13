# -*- coding: utf-8 -*-
"""
O*NET 职业数据处理管道
1. 解析 Occupation Data.txt（职业、描述）与 Skills.txt（技能重要性评分）
2. 每个职业的技能重要性(IM, 1-5)归一化为能力分布（总和=1）
3. 结合 AI 能力得分（0-1）计算替代程度分数 = Σ(能力权重 × AI得分)
输出: occupations.json
"""
import csv, json, os, statistics

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "..", "onet_data", "db_29_1_text")

# ---------- AI 能力得分 (0-1)，基于当前 AI（大模型/智能体/机器人）能力判断 ----------
AI_SCORES = {
    "Reading Comprehension": 0.90,
    "Active Listening": 0.75,
    "Writing": 0.88,
    "Speaking": 0.75,
    "Mathematics": 0.90,
    "Science": 0.72,
    "Critical Thinking": 0.60,
    "Active Learning": 0.78,
    "Learning Strategies": 0.70,
    "Monitoring": 0.85,
    "Complex Problem Solving": 0.62,
    "Judgment and Decision Making": 0.50,
    "Systems Analysis": 0.70,
    "Systems Evaluation": 0.65,
    "Programming": 0.92,
    "Operations Analysis": 0.80,
    "Operations Monitoring": 0.85,
    "Quality Control Analysis": 0.70,
    "Technology Design": 0.60,
    "Equipment Selection": 0.55,
    "Installation": 0.25,
    "Equipment Maintenance": 0.25,
    "Repairing": 0.20,
    "Troubleshooting": 0.65,
    "Operation and Control": 0.40,
    "Instructing": 0.60,
    "Coordination": 0.35,
    "Management of Personnel Resources": 0.35,
    "Management of Financial Resources": 0.65,
    "Management of Material Resources": 0.50,
    "Negotiation": 0.35,
    "Persuasion": 0.40,
    "Service Orientation": 0.50,
    "Social Perceptiveness": 0.40,
    "Time Management": 0.70,
}

# SOC 大类
GROUPS = {
    "11": "Management", "13": "Business & Financial", "15": "Computer & Mathematical",
    "17": "Architecture & Engineering", "19": "Life, Physical & Social Science",
    "21": "Community & Social Service", "22": "Legal", "23": "Education & Library",
    "25": "Arts, Media & Design", "27": "Healthcare Practitioners", "29": "Healthcare Support",
    "31": "Protective Service", "33": "Food Preparation & Serving", "35": "Building & Grounds",
    "37": "Personal Care & Service", "39": "Sales & Related", "41": "Office & Administrative",
    "43": "Farming, Fishing & Forestry", "45": "Construction & Extraction",
    "47": "Installation, Maintenance & Repair", "49": "Production", "51": "Transportation",
    "53": "Military",
}

# ---------- 1. 职业列表 ----------
occupations = {}
with open(os.path.join(DATA, "Occupation Data.txt"), encoding="utf-8-sig") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        occupations[row["O*NET-SOC Code"]] = {
            "code": row["O*NET-SOC Code"],
            "title": row["Title"],
            "desc": row["Description"],
            "group": GROUPS.get(row["O*NET-SOC Code"][:2], "Other"),
        }
print("occupations:", len(occupations))

# ---------- 2. 技能重要性 -> 能力分布 ----------
skill_names = {}      # element id -> name
per_occ = {}          # code -> {element_id: importance}
with open(os.path.join(DATA, "Skills.txt"), encoding="utf-8-sig") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        if row["Scale ID"] != "IM":
            continue
        if row["Recommend Suppress"] == "Y":
            continue
        skill_names[row["Element ID"]] = row["Element Name"]
        per_occ.setdefault(row["O*NET-SOC Code"], {})[row["Element ID"]] = float(row["Data Value"])
print("skills:", len(skill_names), "occupations with skills:", len(per_occ))

skill_list = sorted(skill_names.items(), key=lambda kv: kv[1])
skill_index = {eid: i for i, (eid, _) in enumerate(skill_list)}

# 缺失技能数据的职业：优先取同 6 位代码前缀的职业，否则取同大类平均值
group_avg = {}
for code, imps in per_occ.items():
    g = occupations[code]["group"]
    for eid, v in imps.items():
        group_avg.setdefault(g, {})[eid] = group_avg.get(g, {}).get(eid, 0) + v
group_cnt = {}
for code in per_occ:
    g = occupations[code]["group"]
    group_cnt[g] = group_cnt.get(g, 0) + 1
group_avg = {g: {eid: v / group_cnt[g] for eid, v in d.items()} for g, d in group_avg.items()}

for code in list(occupations):
    if code not in per_occ:
        prefix6 = code[:6]
        sibling = next((c for c in per_occ if c.startswith(prefix6)), None)
        if sibling:
            per_occ[code] = dict(per_occ[sibling])
        else:
            per_occ[code] = dict(group_avg.get(occupations[code]["group"],
                                               next(iter(group_avg.values()))))
print("after fill:", len(per_occ))

records = []
scores_all = []
for code, imps in per_occ.items():
    if code not in occupations:
        continue
    # 锐化：权重 ∝ 重要性^3，突出职业特有技能，避免 35 项均匀稀释
    weighted = {eid: v ** 3 for eid, v in imps.items()}
    total = sum(weighted.values())
    dist = [(skill_index[eid], round(v / total, 4)) for eid, v in
            sorted(weighted.items(), key=lambda kv: -kv[1])]
    score = sum((v / total) * AI_SCORES[skill_names[eid]] for eid, v in weighted.items())
    scores_all.append(score)
    occ = occupations[code]
    records.append({
        "c": occ["code"], "t": occ["title"], "d": occ["desc"],
        "g": occ["group"], "s": round(score, 4), "w": dist,
    })

print("records:", len(records))
print("score min/median/max: %.3f / %.3f / %.3f" % (
    min(scores_all), statistics.median(scores_all), max(scores_all)))
for th in (0.55, 0.60, 0.65, 0.70):
    print("  >=%.2f: %d" % (th, sum(1 for s in scores_all if s >= th)))

out = {
    "skills": [name for _, name in skill_list],
    "ai": [AI_SCORES[name] for _, name in skill_list],
    "jobs": records,
}
with open(os.path.join(BASE, "occupations.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print("json size: %.1f KB" % (os.path.getsize(os.path.join(BASE, "occupations.json")) / 1024))
