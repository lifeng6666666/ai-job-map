# -*- coding: utf-8 -*-
"""用 git credential manager 里存的 GitHub 凭据创建仓库（token 不打印）"""
import subprocess, json, urllib.request, sys

inp = "protocol=https\nhost=github.com\n\n"
p = subprocess.run(["git", "credential", "fill"], input=inp, capture_output=True, text=True)
cred = {}
for line in p.stdout.strip().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        cred[k] = v
token = cred.get("password")
if not token:
    print("NO TOKEN:", p.stdout[:200], p.stderr[:200]); sys.exit(1)
print("user:", cred.get("username"))

name = "ai-job-map"
body = json.dumps({
    "name": name,
    "description": "职业 AI 替代程度地图：基于美国劳工部 O*NET 1016 个职业的能力分布与 AI 能力得分评估替代程度",
    "private": False,
}).encode()
req = urllib.request.Request(
    "https://api.github.com/user/repos",
    data=body, method="POST",
    headers={"Authorization": "Bearer " + token,
             "Accept": "application/vnd.github+json",
             "User-Agent": "ai-job-map"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.load(r)
        print("CREATED:", out["html_url"])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:300])
