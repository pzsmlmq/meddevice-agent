# -*- coding: utf-8 -*-
"""
正式三轮评测跑批器
  v0 基线       top_k=3，直接作答，不许拒答
  v1 检索优化   top_k=10，允许输出「信息不足」
  v2 编排增强   v1 + 三档处理与追问规则

用法：python eval_round.py v0
"""
import os
import csv
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
SRC = ROOT / "data" / "questions_200.csv"
OUTDIR = ROOT / "data" / "eval"
OUTDIR.mkdir(parents=True, exist_ok=True)

PROMPTS = {
    "v0": """你是医疗器械分类专家。根据下面检索到的目录条目，判断这个产品属于哪一类。

产品：{q}

检索到的条目：
{c}

只输出一个类别标签，不要解释，不要标点。
标签只能是：Ⅰ、Ⅱ、Ⅲ、非医疗器械、药械组合""",
    "v1": """你是医疗器械分类专家。根据下面检索到的目录条目，判断这个产品属于哪一类。

产品：{q}

检索到的条目：
{c}

规则：
1. 信息足以定位某一类，就输出类别标签
2. 描述太模糊、或条目与描述明显对不上，输出「信息不足」
3. 只输出一个结果，不要解释

输出只能是：Ⅰ、Ⅱ、Ⅲ、非医疗器械、药械组合、不单独作为医疗器械管理、视具体情况而定、信息不足""",
    "v2": """你是医疗器械分类专家，服务对象是医疗器械企业的注册专员。

产品：{q}

检索到的条目：
{c}

按三档处理：
- 信息足够定位：直接给类别
- 信息不足但能定位大类：先输出「信息不足」，再给最可能的类别
- 完全不够：只输出「信息不足」

只输出一个结果，不要解释。""",
    "v3": """你是医疗器械分类专家。判断下面这个产品的管理类别。

产品：{q}

检索到的条目：
{c}

按这个顺序判断：
1. 找与「预期用途」直接对应的条目，用途对得上优先于描述详略
2. 只要有一个类别明显最匹配，就直接输出该类别，即使用户描述很简略
3. 只有当两个不同类别都能合理解释这个产品、无法区分时，才输出「信息不足」
4. 只输出一个结果，不要解释，不要标点

输出只能是：Ⅰ、Ⅱ、Ⅲ、非医疗器械、药械组合、不单独作为医疗器械管理、视具体情况而定、信息不足""",
    # v4 的提示词只在「投票判定可答」时才用，候选限制在前两名
    "v4": """你是医疗器械分类专家。检索结果集中在两个候选类别上：{cands}

产品：{q}

检索到的条目：
{c}

从上面两个候选里选一个最符合「预期用途」的类别。
只输出类别标签，不要解释，不要标点。""",
}
TOP_K = {"v0": 3, "v1": 10, "v2": 10, "v3": 10, "v4": 10}
ALLOW_REFUSE = {"v0": False, "v1": True, "v2": True, "v3": True, "v4": True}

# v4 的判定阈值：第一名占比与领先幅度
V4_MIN_SHARE = 0.50
V4_MIN_MARGIN = 0.18


def post(url, payload, headers):
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def search(q, k):
    res = post(f"{BASE}/indices/search/hybrid",
               {"query": q, "index_names": [INDEX], "top_k": k},
               {"Authorization": f"Bearer {TOKEN}"})
    return res.get("results") or []


def parse(t, allow_refuse):
    t = (t or "").strip()
    if allow_refuse and (REFUSE in t or "不足" in t):
        return REFUSE
    for lb in LABELS:
        if t.startswith(lb):
            return lb
    for lb in LABELS:
        if lb in t:
            return lb
    m = re.search(r"[ⅠⅡⅢ]", t)
    return m.group() if m else "未识别"


REC_HEAD = re.compile(r"^记录\s*\d+\s*｜")
CLS_LINE = re.compile(r"管理类别：\s*(\S+)")


def vote_classes(results):
    """从检索结果里按记录统计类别票数，返回 [(类别, 票数), ...] 降序"""
    from collections import Counter
    votes = Counter()
    for r in results:
        content = r.get("content") or ""
        # 一个切片可能包含多条记录，按记录头拆开
        blocks = re.split(r"(?=^记录\s*\d+\s*｜)", content, flags=re.M)
        for b in blocks:
            m = CLS_LINE.search(b)
            if m:
                votes[m.group(1).strip()] += 1
    return votes.most_common()


def run_one(args):
    tag, row = args
    q = row["question"]
    t0 = time.time()
    try:
        res = search(q, TOP_K[tag])
        c = "\n\n".join(
            "[%d] %s" % (i, (r.get("content") or "").replace("\n", " ").strip()[:600])
            for i, r in enumerate(res, 1))

        if tag == "v4":
            ranked = vote_classes(res)
            total = sum(n for _, n in ranked)
            if total == 0 or len(ranked) < 2:
                pred = REFUSE
            else:
                (c1, n1), (c2, n2) = ranked[0], ranked[1]
                share = n1 / total
                margin = (n1 - n2) / total
                if share >= V4_MIN_SHARE and margin >= V4_MIN_MARGIN:
                    body = {"model": "deepseek-flash",
                            "messages": [{"role": "user", "content": PROMPTS[tag].format(
                                q=q, c=c, cands="%s（%d 票）与 %s（%d 票）" % (c1, n1, c2, n2))}],
                            "max_tokens": 20, "thinking": {"type": "disabled"}}
                    d = post(DS_URL, body, {"Authorization": f"Bearer {DS_KEY}"})
                    pred = parse(d["choices"][0]["message"]["content"], True)
                else:
                    pred = REFUSE
        else:
            body = {"model": "deepseek-flash",
                    "messages": [{"role": "user", "content": PROMPTS[tag].format(q=q, c=c)}],
                    "max_tokens": 20, "thinking": {"type": "disabled"}}
            d = post(DS_URL, body, {"Authorization": f"Bearer {DS_KEY}"})
            pred = parse(d["choices"][0]["message"]["content"], ALLOW_REFUSE[tag])
    except Exception as e:
        pred = "ERROR"
    return {
        "case_id": row["case_id"],
        "question": q,
        "gold": row["gold_class"],
        "pred": pred,
        "ms": int((time.time() - t0) * 1000),
    }


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


def load_rows(kind):
    if kind == "human":
        return list(csv.DictReader(open(SRC, encoding="utf-8-sig", newline="")))
    p = ROOT / "data" / "questions" / "auto_set.jsonl"
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            out.append({"case_id": d["case_id"], "question": d["question"],
                        "gold_class": d["gold_class"]})
    return out


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "v0"
    kind = sys.argv[2] if len(sys.argv) > 2 else "human"
    rows = load_rows(kind)
    print("轮次 %s ｜ 数据集 %s ｜ 题数 %d ｜ top_k=%d ｜ 允许拒答=%s\n"
          % (tag, kind, len(rows), TOP_K[tag], ALLOW_REFUSE[tag]))

    with ThreadPoolExecutor(max_workers=6) as ex:
        done = list(ex.map(run_one, [(tag, r) for r in rows]))

    answered = [r for r in done if r["pred"] in LABELS]
    refused = [r for r in done if r["pred"] == REFUSE]
    other = [r for r in done if r["pred"] in ("ERROR", "未识别")]
    acc_ans = sum(1 for r in answered if r["pred"] == r["gold"]) / len(answered) if answered else 0
    acc_all = sum(1 for r in done if r["pred"] == r["gold"]) / len(done)
    f1 = macro_f1([(r["gold"], r["pred"]) for r in answered]) if answered else 0
    ms = sorted(r["ms"] for r in done)
    p50 = ms[len(ms) // 2]

    summary = {
        "round": tag,
        "dataset": kind,
        "n": len(done),
        "top_k": TOP_K[tag],
        "allow_refuse": ALLOW_REFUSE[tag],
        "answered": len(answered),
        "refused": len(refused),
        "other": len(other),
        "refuse_rate": len(refused) / len(done),
        "acc_answered": acc_ans,
        "acc_overall": acc_all,
        "macro_f1": f1,
        "p50_ms": p50,
    }

    print("%-14s %s" % ("题数", len(done)))
    print("%-14s %d（拒答 %.0f%%）" % ("作答", len(answered), len(refused) / len(done) * 100))
    print("%-14s %.1f%%" % ("直接判定准确率", acc_ans * 100))
    print("%-14s %.1f%%" % ("总体正确率", acc_all * 100))
    print("%-14s %.3f" % ("Macro-F1", f1))
    print("%-14s %d ms" % ("中位耗时", p50))
    if other:
        print("%-14s %d" % ("异常", len(other)))

    name = "%s_%s_result.json" % (kind, tag)
    (OUTDIR / name).write_text(
        json.dumps({"summary": summary, "rows": done}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print("\n写入:", OUTDIR / name)

if __name__ == "__main__":
    main()
