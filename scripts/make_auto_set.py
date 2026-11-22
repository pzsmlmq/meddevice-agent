# -*- coding: utf-8 -*-
"""
扩充评测集：按类别分层，从知识库记录改写生成问句
  每类取 60 条（不足则全取），共约 420 条
  改写要求：用企业老板的口吻，去术语，不提品名
"""
import os
import csv
import json
import random
import re
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DS_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DS_URL = "https://api.deepseek.com/v1/chat/completions"
ROOT = Path(r"C:\Users\A\Documents\deepseek-harness\default-workspace\ict")
SRC = ROOT / "data" / "catalog_utf8.csv"
OUT = ROOT / "data" / "questions" / "auto_set.jsonl"
PER_CLASS = 60

LABELS = ["Ⅰ", "Ⅱ", "Ⅲ", "非医疗器械", "药械组合",
          "不单独作为医疗器械管理", "视具体情况而定"]


def g(r, k):
    return (r.get(k) or "").strip()


def norm(v):
    s = (v or "").strip()
    if not s:
        return None
    c = s.replace(" ", "")
    if c in ("Ⅰ", "I", "1", "I类", "一类", "第一类"):
        return "Ⅰ"
    if c in ("Ⅱ", "II", "2", "II类", "二类", "第二类"):
        return "Ⅱ"
    if c in ("Ⅲ", "III", "3", "III类", "三类", "第三类"):
        return "Ⅲ"
    if "药械组合" in c:
        return "药械组合"
    if "非医疗器械" in c:
        return "非医疗器械"
    if "不单独作为医疗器械管理" in c:
        return "不单独作为医疗器械管理"
    if "视具体情况" in c:
        return "视具体情况而定"
    return None


rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig", newline="")))
pool = defaultdict(list)
for r in rows:
    cls = norm(g(r, "管理类别"))
    desc, use = g(r, "产品描述"), g(r, "预期用途")
    if not cls or not (desc or use):
        continue
    pool[cls].append({"desc": desc, "use": use, "name": g(r, "品名举例"),
                      "src": g(r, "法规文本链接")})

random.seed(7)
picked = []
for cls in LABELS:
    items = pool[cls]
    random.shuffle(items)
    take = items[:PER_CLASS]
    picked.extend([(cls, it) for it in take])
    print("%-16s 池 %4d  取 %d" % (cls, len(items), len(take)))

print("\n共取 %d 条，开始改写...\n" % len(picked))


def build(line):
    idx, (cls, it) = line
    desc = it["desc"][:260]
    use = it["use"][:200]
    prompt = f"""下面是一个医疗器械产品的客观描述。

产品描述：{desc}
预期用途：{use}

请把它改写成一句企业老板向监管人员咨询时说的话。要求：
1. 用第一人称「我们做的是…」或直接描述产品
2. 20 到 45 字，必须提到用途
3. 不要用规格型号、标准编号、专业术语
4. 不要提产品名称，不要提类别
5. 只输出这句话，不要引号，不要解释"""
    body = {"model": "deepseek-flash",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 120, "thinking": {"type": "disabled"}}
    try:
        req = urllib.request.Request(
            DS_URL, data=json.dumps(body, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {DS_KEY}"}, method="POST")
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read().decode())
        q = (d["choices"][0]["message"]["content"] or "").strip().strip('"“”')
    except Exception:
        return None
    if len(q) < 8:
        return None
    return {
        "case_id": "auto-%03d" % idx,
        "question": q,
        "gold_class": cls,
        "source_desc": desc,
        "evidence_clause": it["src"],
        "set": "auto",
    }


with ThreadPoolExecutor(max_workers=8) as ex:
    out = [x for x in ex.map(build, list(enumerate(picked))) if x]

print("生成 %d 条" % len(out))
from collections import Counter
for k, v in Counter(r["gold_class"] for r in out).most_common():
    print("   %-18s %d" % (k, v))

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("\n写入:", OUT)

for r in out[:5]:
    print("  [%s] %s" % (r["gold_class"], r["question"][:52]))
