# -*- coding: utf-8 -*-
"""统一口径：算出全项目共用的一套数字，写进 data/_canonical.json"""
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\Users\A\Documents\deepseek-harness\default-workspace\ict")
SRC = ROOT / "data" / "catalog_utf8.csv"
OUT = ROOT / "data" / "_canonical.json"

rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig", newline="")))


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


raw_total = len(rows)

# 行类型：目录条目 / 分类界定 / 空行
kinds = Counter()
for r in rows:
    c2 = g(r, "二级产品类别")
    cls = g(r, "管理类别")
    if not c2 and not cls and not g(r, "品名举例"):
        kinds["空行/分组标题"] += 1
    elif c2 in ("分类界定", "分类调整"):
        kinds["分类界定"] += 1
    else:
        kinds["目录条目"] += 1

# 真实子目录：目录列里以两位数字开头的
catalogs = {g(r, "目录") for r in rows if re.match(r"^\d{2}", g(r, "目录"))}

# 二级类别：去掉占位值
l2 = {g(r, "二级产品类别") for r in rows}
l2.discard("")
l2.discard("分类界定")
l2.discard("分类调整")

l1 = {g(r, "一级产品类别") for r in rows}
l1.discard("")

with_src = sum(1 for r in rows if g(r, "法规文本链接"))

# 管理类别分布（全部行）
cls_all = Counter(norm(g(r, "管理类别")) for r in rows)
cls_all.pop(None, None)

# 入库口径：有类别且内容非空
kept = [r for r in rows
        if norm(g(r, "管理类别")) and (g(r, "品名举例") or g(r, "产品描述") or g(r, "预期用途"))]
cls_kept = Counter(norm(g(r, "管理类别")) for r in kept)

data = {
    "原始行数": raw_total,
    "行类型": dict(kinds),
    "有效子目录": len(catalogs),
    "子目录取值": len({g(r, "目录") for r in rows if g(r, "目录")}),
    "一级类别": len(l1),
    "二级类别": len(l2),
    "带法规出处": with_src,
    "管理类别_全部行": dict(cls_all),
    "入库记录": len(kept),
    "管理类别_入库": dict(cls_kept),
}

OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

print("=== 统一口径 ===")
for k, v in data.items():
    if isinstance(v, dict):
        print("%s:" % k)
        for kk, vv in sorted(v.items(), key=lambda x: -x[1]):
            print("   %-16s %d" % (kk, vv))
    else:
        print("%-16s %d" % (k, v))
print()
print("写入:", OUT)
