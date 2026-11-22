# -*- coding: utf-8 -*-
"""
四档口语化评测
  指标：拒答率（该问的时候有没有问）、直接判定里的准确率、总体正确率、Macro-F1
"""
import os
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TOKEN = "mock_access_token"
BASE = "http://localhost:5010"
DS_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DS_URL = "https://api.deepseek.com/v1/chat/completions"
INDEX = "5-021a09e4ee684fe8ad539aae23125f3a"
LABELS = ["Ⅰ", "Ⅱ", "Ⅲ", "非医疗器械", "药械组合"]
REFUSE = "信息不足"
TOP_K = 10

ROOT = Path(r"C:\Users\A\Documents\deepseek-harness\default-workspace\ict")
SRC = ROOT / "data" / "questions" / "tiers.jsonl"
OUT = ROOT / "data" / "questions" / "tier_result.json"


def post(url, payload, headers):
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def search(q):
    res = post(f"{BASE}/indices/search/hybrid",
               {"query": q, "index_names": [INDEX], "top_k": TOP_K},
               {"Authorization": f"Bearer {TOKEN}"})
    return res.get("results") or []


PROMPT = """你是医疗器械分类专家。下面是从《医疗器械分类目录》检索到的条目，以及用户的一句话描述。

用户描述：{q}

检索到的条目：
{c}

请判断管理类别。规则：
1. 描述里的信息足以定位到某一类，就直接输出类别标签
2. 描述太模糊、或者检索到的条目与描述明显对不上，就输出「信息不足」
3. 只输出一个结果，不要解释，不要标点

输出只能是：Ⅰ、Ⅱ、Ⅲ、非医疗器械、药械组合、信息不足"""


def ask(q, results):
    c = "\n\n".join("[%d] %s" % (i, (r.get("content") or "").replace("\n", " ").strip()[:600])
                    for i, r in enumerate(results, 1))
    body = {"model": "deepseek-flash",
            "messages": [{"role": "user", "content": PROMPT.format(q=q, c=c)}],
            "max_tokens": 20, "thinking": {"type": "disabled"}}
    d = post(DS_URL, body, {"Authorization": f"Bearer {DS_KEY}"})
    return (d["choices"][0]["message"]["content"] or "").strip()


def parse(t):
    t = t.strip()
    if REFUSE in t or "不足" in t or "无法" in t:
        return REFUSE
    for lb in LABELS:
        if t.startswith(lb):
            return lb
    for lb in LABELS:
        if lb in t:
            return lb
    m = re.search(r"[ⅠⅡⅢ]", t)
    return m.group() if m else "未识别"


def run(row):
    t0 = time.time()
    try:
        pred = parse(ask(row["question"], search(row["question"])))
    except Exception:
        pred = "ERROR"
    return {**row, "pred": pred, "ms": int((time.time() - t0) * 1000)}


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
    rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    print("题目 %d 道\n" % len(rows))

    with ThreadPoolExecutor(max_workers=6) as ex:
        done = list(ex.map(run, rows))

    OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")

    print("%-5s %-6s %-10s %-12s %-12s %-10s" % ("档", "题数", "拒答率", "直接判定准确率", "总体正确率", "Macro-F1"))
    print("-" * 68)
    summary = {}
    for tier in ("T1", "T2", "T3", "T4"):
        sub = [r for r in done if r["tier"] == tier]
        answered = [r for r in sub if r["pred"] in LABELS]
        refused = sum(1 for r in sub if r["pred"] == REFUSE)
        acc_ans = sum(1 for r in answered if r["pred"] == r["gold_class"]) / len(answered) if answered else 0
        acc_all = sum(1 for r in sub if r["pred"] == r["gold_class"]) / len(sub)
        f1 = macro_f1([(r["gold_class"], r["pred"]) for r in answered]) if answered else 0
        summary[tier] = {
            "n": len(sub), "refuse_rate": refused / len(sub),
            "acc_answered": acc_ans, "acc_all": acc_all, "f1": f1,
        }
        print("%-5s %-6d %-10s %-12s %-12s %-10s" % (
            tier, len(sub), "%.0f%%" % (refused / len(sub) * 100),
            "%.1f%%" % (acc_ans * 100), "%.1f%%" % (acc_all * 100), "%.3f" % f1))

    print()
    print("=== 各档样例（前 2 条）===")
    for tier in ("T1", "T2", "T3", "T4"):
        sub = [r for r in done if r["tier"] == tier][:2]
        print("\n%s" % tier)
        for r in sub:
            print("  问：%s" % r["question"][:50])
            print("  判：%s   真：%s" % (r["pred"], r["gold_class"]))

    (ROOT / "data" / "questions" / "tier_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
