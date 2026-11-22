# -*- coding: utf-8 -*-
"""
V5：带追问闭环的判定
  第一轮  v1 提示词直接判
  第二轮  自查是否与其他类别冲突（只输出 确定 / 歧义:类别）
  第三轮  有歧义时生成一个追问，用知识库原文充当用户补充，再判一次

用法：python eval_v5.py auto
"""
import os
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TOKEN = "mock_access_token"
BASE = "http://localhost:5010"
DS_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DS_URL = "https://api.deepseek.com/v1/chat/completions"
INDEX = "6-9535c32bff594df4bf46c245a5731965"

LABELS = ["Ⅰ", "Ⅱ", "Ⅲ", "非医疗器械", "药械组合",
          "不单独作为医疗器械管理", "视具体情况而定"]
REFUSE = "信息不足"

ROOT = Path(r"C:\Users\A\Documents\deepseek-harness\default-workspace\ict")
OUT = ROOT / "data" / "eval"

JUDGE_V1 = """你是医疗器械分类专家。根据下面检索到的目录条目，判断这个产品属于哪一类。

产品：{q}

检索到的条目：
{c}

规则：
1. 信息足以定位某一类，就输出类别标签
2. 描述太模糊、或条目与描述明显对不上，输出「信息不足」
3. 只输出一个结果，不要解释

输出只能是：Ⅰ、Ⅱ、Ⅲ、非医疗器械、药械组合、不单独作为医疗器械管理、视具体情况而定、信息不足"""

CHECK = """你把一个产品判为「{pred}」。

产品描述：{q}

检索条目摘要：
{c}

问：检索到的条目里，有没有另一个管理类别也能合理解释这个产品？
只按下面两种格式回答，不要别的字：
  确定
  歧义:<另一个类别>|<一句话说明分歧点>"""

ASK = """你在帮企业判断产品的医疗器械管理类别。已知它有歧义：{issue}

产品描述：{q}

请只问一个最关键的问题，用来消除这个歧义。不超过 25 字，只输出问题本身。"""

JUDGE_AFTER = """你是医疗器械分类专家。根据检索条目和用户补充的信息，判断产品类别。

产品最初描述：{q}
用户补充说明：{sup}

检索到的条目：
{c}

只输出一个类别标签，不要解释。
标签只能是：Ⅰ、Ⅱ、Ⅲ、非医疗器械、药械组合、不单独作为医疗器械管理、视具体情况而定"""


def post(url, payload, headers):
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def ds(prompt, max_tokens=60):
    d = post(DS_URL, {"model": "deepseek-flash",
                      "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": max_tokens, "thinking": {"type": "disabled"}},
             {"Authorization": f"Bearer {DS_KEY}"})
    return (d["choices"][0]["message"]["content"] or "").strip()


def search(q, k=10):
    res = post(f"{BASE}/indices/search/hybrid",
               {"query": q, "index_names": [INDEX], "top_k": k},
               {"Authorization": f"Bearer {TOKEN}"})
    return res.get("results") or []


def parse(t):
    t = (t or "").strip()
    if REFUSE in t or "不足" in t:
        return REFUSE
    for lb in LABELS:
        if t.startswith(lb):
            return lb
    for lb in LABELS:
        if lb in t:
            return lb
    m = re.search(r"[ⅠⅡⅢ]", t)
    return m.group() if m else "未识别"


def ctx(results, n=600):
    return "\n\n".join("[%d] %s" % (i, (r.get("content") or "").replace("\n", " ").strip()[:n])
                       for i, r in enumerate(results, 1))


def run(row):
    q = row["question"]
    t0 = time.time()
    rec = {"case_id": row["case_id"], "question": q, "gold": row["gold_class"],
           "pred1": None, "ambiguous": False, "other": None, "issue": None,
           "ask": None, "pred2": None, "final": None}
    try:
        res = search(q)
        c = ctx(res)
        rec["pred1"] = parse(ds(JUDGE_V1.format(q=q, c=c), 20))

        chk = ds(CHECK.format(pred=rec["pred1"], q=q, c=ctx(res, 260)), 80)
        if "歧义" in chk:
            rec["ambiguous"] = True
            body = chk.split("歧义", 1)[1].lstrip(":：")
            parts = body.split("|")
            rec["other"] = parts[0].strip()[:20]
            rec["issue"] = parts[1].strip()[:60] if len(parts) > 1 else ""
            rec["ask"] = ds(ASK.format(issue=rec["issue"] or rec["other"], q=q), 60)
            sup = row.get("source_desc") or ""
            res2 = search(q + " " + sup[:80])
            rec["pred2"] = parse(ds(
                JUDGE_AFTER.format(q=q, sup=sup[:300], c=ctx(res2)), 20))
            rec["final"] = rec["pred2"]
        else:
            rec["final"] = rec["pred1"]
    except Exception as e:
        rec["final"] = "ERROR"
    rec["ms"] = int((time.time() - t0) * 1000)
    return rec


def macro_f1(pairs):
    labels = sorted({g for g, _ in pairs})
    fs = []
    for lb in labels:
        tp = sum(1 for g, p in pairs if g == lb and p == lb)
        fp = sum(1 for g, p in pairs if g != lb and p == lb)
        fn = sum(1 for g, p in pairs if g == lb and p != lb)
        pre = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        fs.append(2 * pre * rec / (pre + rec) if pre + rec else 0)
    return sum(fs) / len(fs) if fs else 0


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else "auto"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    p = ROOT / "data" / "questions" / "auto_set.jsonl"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    if limit:
        rows = rows[:limit]
    print("V5 ｜ 数据集 auto ｜ %d 题\n" % len(rows))

    with ThreadPoolExecutor(max_workers=6) as ex:
        done = list(ex.map(run, rows))

    amb = [r for r in done if r["ambiguous"]]
    answered1 = [r for r in done if r["pred1"] in LABELS]
    final_ans = [r for r in done if r["final"] in LABELS]

    acc1 = sum(1 for r in done if r["pred1"] == r["gold"]) / len(done)
    accf = sum(1 for r in done if r["final"] == r["gold"]) / len(done)

    print("首轮准确率          %.1f%%" % (acc1 * 100))
    print("判定有歧义          %d 题 (%.0f%%)" % (len(amb), len(amb) / len(done) * 100))
    if amb:
        fixed = [r for r in amb if r["pred1"] != r["gold"] and r["final"] == r["gold"]]
        broke = [r for r in amb if r["pred1"] == r["gold"] and r["final"] != r["gold"]]
        still = [r for r in amb if r["final"] != r["gold"]]
        print("追问后改对          %d (%+.1f pp)" % (len(fixed), len(fixed) / len(done) * 100))
        print("追问后改错          %d" % len(broke))
        print("追问后仍错          %d" % len(still))
    print("最终总体准确率       %.1f%%" % (accf * 100))
    print("最终 Macro-F1        %.3f" % macro_f1(
        [(r["gold"], r["final"]) for r in final_ans]))
    ms = sorted(r["ms"] for r in done)
    print("中位耗时            %d ms" % ms[len(ms) // 2])

    print("\n=== 歧义样例（前 5）===")
    for r in amb[:5]:
        print("\n[%s -> 最终 %s，真值 %s]" % (r["pred1"], r["final"], r["gold"]))
        print("  问：%s" % r["question"][:44])
        print("  歧义：%s" % (r["issue"] or "")[:50])
        print("  追问：%s" % (r["ask"] or "")[:50])

    (OUT / "auto_v5_result.json").write_text(
        json.dumps({"rows": done}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n写入:", OUT / "auto_v5_result.json")


if __name__ == "__main__":
    main()
