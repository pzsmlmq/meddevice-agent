# -*- coding: utf-8 -*-
"""
知识库文档 v4：八类管理类别全收
  Ⅰ Ⅱ Ⅲ 非医疗器械 药械组合 不单独作为医疗器械管理 视具体情况而定 其他
比 v3 多收 263 条（215 + 48），这些也是真实判定结果
"""
import csv
import re
from pathlib import Path

ROOT = Path(r"C:\Users\A\Documents\deepseek-harness\default-workspace\ict")
SRC = ROOT / "data" / "catalog_utf8.csv"
OUT = ROOT / "data" / "kb_catalog_v4.md"


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
    return "其他"


def year_of(src):
    ys = re.findall(r"(?:19|20)\d{2}", src)
    return max(int(y) for y in ys) if ys else None


rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig", newline="")))

recs = []
for r in rows:
    name, desc, use = g(r, "品名举例"), g(r, "产品描述"), g(r, "预期用途")
    c2, src = g(r, "二级产品类别"), g(r, "法规文本链接")
    cls = norm(g(r, "管理类别"))
    if not cls or not (name or desc or use):
        continue
    y = year_of(src)
    if y is None:
        y = 2017 if c2 not in ("分类界定", "分类调整") else None
    recs.append({
        "name": name, "desc": desc, "use": use, "cls": cls, "l2": c2,
        "catalog": g(r, "目录"), "l1": g(r, "一级产品类别"),
        "src": src, "year": y,
        "is_def": c2 in ("分类界定", "分类调整") or not c2,
    })

L = [
    "医疗器械分类目录与历年分类界定结果（全量汇编）",
    "",
    "本文档收录两类记录：目录条目（2017 年版主目录）与分类界定记录（2018 年起历年新产品判定结果）。",
    "管理类别包含：Ⅰ、Ⅱ、Ⅲ、非医疗器械、药械组合、不单独作为医疗器械管理、视具体情况而定。",
    "每条记录以「记录编号」开头，含记录类型、年份、所属目录、产品类别、产品描述、预期用途、品名举例、管理类别与法规出处。",
    "",
    "================================================================================",
    "",
]

for i, r in enumerate(recs, 1):
    head = (re.split(r"[、，,]", r["name"])[0] if r["name"] else r["desc"][:20])
    if not r["is_def"] and r["l2"]:
        head = r["l2"]
    head = (head or "未命名")[:30]

    L.append("记录 %d ｜ %s ｜ %s" % (i, "分类界定" if r["is_def"] else "目录条目", head))
    L.append("")
    if r["year"]:
        L.append("年份：%d" % r["year"])
    if r["catalog"]:
        L.append("目录：%s" % r["catalog"])
    if r["l1"]:
        L.append("一级产品类别：%s" % r["l1"])
    if r["l2"] and not r["is_def"]:
        L.append("二级产品类别：%s" % r["l2"])
    if r["desc"]:
        L.append("产品描述：%s" % r["desc"])
    if r["use"]:
        L.append("预期用途：%s" % r["use"])
    if r["name"]:
        L.append("品名举例：%s" % r["name"])
    L.append("管理类别：%s" % r["cls"])
    if r["src"]:
        L.append("依据：%s" % r["src"])
    L.append("")
    L.append("--------------------------------------------------------------------------------")
    L.append("")

text = "\n".join(L)
OUT.write_text(text, encoding="utf-8")

from collections import Counter
print("生成:", OUT)
print("记录数: %d" % len(recs))
print("字符数: %d (%.1f MB)" % (len(text), len(text.encode()) / 1024 / 1024))
print("类别分布:")
for k, v in Counter(r["cls"] for r in recs).most_common():
    print("   %-18s %d" % (k, v))
