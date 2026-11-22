# -*- coding: utf-8 -*-
"""
追问补回实验
  T4 / T3 里被拒答的题，模拟「智能体追问 → 用户补充信息 → 重新判定」
  补充的信息用原始专业问法代替（同一产品的准确描述，不含答案）
  看补回率、追问后准确率
"""
import os
import json
import re
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

ROOT = Path(r"C:\Users\A\Documents\deepseek-harness\default-workspace\ict")
RES = ROOT / "data" / "questions" / "tier_result.json"
OUT = ROOT / "data" / "questions" / "clarify_result.json"


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


PROMPT_JUDGE = """你是医疗器械分类专家。下面是用户描述和检索到的目录条目。

用户描述：{q}

检索到的条目：
{c}

判断管理类别。规则：
1. 信息足以定位就输出类别标签
2. 太模糊或条目对不上就输出「信息不足」
3. 只输出一个结果，不要解释

输出只能是：Ⅰ、Ⅱ、Ⅲ、非医疗器械、药械组合、信息不足"""


def judge(q):
    c = "\n\n".join("[%d] %s" % (i, (r.get("content") or "").replace("\n", " ").strip()[:600])
                    for i, r in enumerate(search(q), 1))
    return parse(ds(PROMPT_JUDGE.format(q=q, c=c), 20))


def parse(t):
    t = (t or "").strip()
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


ASK_PROMPT = """你在帮企业判断一个产品属于第几类医疗器械。用户只说了「{q}」，信息不够。

请只问一个最关键的问题，用来判断它的管理类别。
要求：一句话，不超过 30 字，必须说明为什么问。
只输出问题本身。"""


def run(row):
    q = row["question"]
    ask = ds(ASK_PROMPT.format(q=q), 80).strip().strip('"“”')
    supplement = row["original"]          # 模拟用户补充：给出准确的产品描述
    new_q = "%s\n补充说明：%s" % (q, supplement)
    after = judge(new_q)
    return {
        "tier": row["tier"],
        "case_id": row["case_id"],
        "vague": q,
        "ask": ask,
        "supplement": supplement,
        "gold": row["gold_class"],
        "before": row["pred"],
        "after": after,
        "fixed": after == row["gold_class"],
    }


def main():
    rows = json.loads(RES.read_text(encoding="utf-8"))
    target = [r for r in rows if r["pred"] == REFUSE and r["tier"] in ("T3", "T4")]
    print("被拒答的题：%d 道（T3+T4）\n" % len(target))

    with ThreadPoolExecutor(max_workers=5) as ex:
        out = list(ex.map(run, target))

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    fixed = [r for r in out if r["fixed"]]
    still_refuse = [r for r in out if r["after"] == REFUSE]
    wrong = [r for r in out if r["after"] not in (REFUSE,) and not r["fixed"]]

    print("补回（判对了）：%d / %d = %.0f%%" % (len(fixed), len(out), len(fixed) / len(out) * 100))
    print("仍然拒答：      %d" % len(still_refuse))
    print("给了错答案：    %d" % len(wrong))
    print()

    print("=== 追问样例（前 5 条）===")
    for r in out[:5]:
        print("\n[%s] 用户说：%s" % (r["tier"], r["vague"][:36]))
        print("     追问：%s" % r["ask"][:60])
        print("     追问后判：%s   真：%s   %s" % (
            r["after"], r["gold"], "✓" if r["fixed"] else "✗"))

    # 汇总：加上追问后，T3/T4 的最终正确率
    by_tier = {}
    for tier in ("T3", "T4"):
        before_rows = [r for r in rows if r["tier"] == tier]
        before_acc = sum(1 for r in before_rows if r["pred"] == r["gold_class"]) / len(before_rows)
        after_fixed_here = sum(1 for r in fixed if r["tier"] == tier)
        after_acc = before_acc + after_fixed_here / len(before_rows)
        by_tier[tier] = {"before": before_acc, "after": after_acc}
        print("\n%s 总体正确率：%.1f%% → %.1f%%" % (tier, before_acc * 100, after_acc * 100))

    (ROOT / "data" / "questions" / "clarify_summary.json").write_text(
        json.dumps(by_tier, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
