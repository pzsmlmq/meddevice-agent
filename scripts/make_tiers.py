# -*- coding: utf-8 -*-
"""
把 204 道专业问法改写成四档口语程度，每档 50 道
  档1  专业原句（不动）
  档2  轻度口语：去掉型号和行话，保留关键信息
  档3  明显口语：说用途，不说产品名
  档4  极简：三五个字，只给一个模糊印象
"""
import os
import csv
import json
import random
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DS_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DS_URL = "https://api.deepseek.com/v1/chat/completions"
ROOT = Path(r"C:\Users\A\Documents\deepseek-harness\default-workspace\ict")
SRC = ROOT / "data" / "questions_200.csv"
OUT = ROOT / "data" / "questions" / "tiers.jsonl"
OUT.parent.mkdir(parents=True, exist_ok=True)

rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig", newline="")))
print("原始题目 %d 道" % len(rows))

random.seed(11)
random.shuffle(rows)
TIERS = {"T1": rows[0:50], "T2": rows[50:100], "T3": rows[100:150], "T4": rows[150:200]}

PROMPT = {
    "T2": """把下面这句医疗行业内的专业问法，改写成企业老板平时会说的话。
要求：保留关键信息（产品用途、材料、是否接触人体），去掉型号、标准编号、行业术语。
只输出改写后的一句话，不要引号，不要解释。

原句：{q}""",
    "T3": """把下面这句医疗行业内的专业问法，改写成不懂技术的人随口问的话。
要求：只说用途或外观，不提具体产品名和术语。
只输出改写后的一句话，不要引号，不要解释。

原句：{q}""",
    "T4": """把下面这个医疗器械产品，改写成外行极简的一句疑问，不超过 12 个字。
要求：只保留一个模糊印象，不提供用途、材料等关键信息。
只输出改写后的一句话，不要引号，不要解释。

产品描述：{q}""",
}


def ds(prompt, max_tokens=80):
    body = {"model": "deepseek-flash",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "thinking": {"type": "disabled"}}
    req = urllib.request.Request(
        DS_URL, data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {DS_KEY}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read().decode())
    return (d["choices"][0]["message"]["content"] or "").strip().strip('"“”')


def rewrite(tier, row):
    q = row["question"]
    if tier == "T1":
        return q
    try:
        return ds(PROMPT[tier].format(q=q))
    except Exception:
        return q


def build(tier):
    out = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        texts = list(ex.map(lambda r: rewrite(tier, r), TIERS[tier]))
    for row, q in zip(TIERS[tier], texts):
        out.append({
            "tier": tier,
            "case_id": row["case_id"],
            "question": q,
            "original": row["question"],
            "gold_class": row["gold_class"],
            "gold_answer": row["gold_answer"],
            "evidence_clause": row["evidence_clause"],
        })
    return out


allrows = []
for tier in ("T1", "T2", "T3", "T4"):
    print("生成 %s ..." % tier)
    allrows.extend(build(tier))

with open(OUT, "w", encoding="utf-8") as f:
    for r in allrows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print("\n共 %d 条，写入 %s" % (len(allrows), OUT))
print()
for tier in ("T1", "T2", "T3", "T4"):
    s = [r for r in allrows if r["tier"] == tier][:3]
    print("%s 样例：" % tier)
    for r in s:
        print("   问：%s" % r["question"][:60])
        print("   原：%s" % r["original"][:50])
    print()
