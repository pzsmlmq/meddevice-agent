"""
reasoning MCP server —— 分类判定与决策路径

职责：基于 knowledge 层取回的记录，做判定、算路径、组证据链。
判定规则外置（CLASS_RULES），改规则不用改代码。

启动：python reasoning_server.py → http://0.0.0.0:8002/mcp
"""
import re

from mcp.server.fastmcp import FastMCP

from kb_common import dumps, fetch

mcp = FastMCP("nexent-reasoning", host="0.0.0.0", port=8002)

# 判定规则表：外置。改判定只动这里。
CLASS_RULES = {
    "Ⅰ": {"reg_path": "备案", "authority": "市级药品监督管理部门", "clinical": "通常可免于临床评价"},
    "Ⅱ": {"reg_path": "注册", "authority": "省级药品监督管理部门", "clinical": "需核对是否在免临床目录内"},
    "Ⅲ": {"reg_path": "注册", "authority": "国家药品监督管理局", "clinical": "通常需提交临床评价资料"},
    "非医疗器械": {"reg_path": "不适用", "authority": "—", "clinical": "不适用"},
    "药械组合": {"reg_path": "注册", "authority": "国家药品监督管理局", "clinical": "按主要作用判定"},
}


def _norm(level: str) -> str:
    s = (level or "").strip().replace("类", "")
    if s in CLASS_RULES:
        return s
    return {"I": "Ⅰ", "II": "Ⅱ", "III": "Ⅲ", "1": "Ⅰ", "2": "Ⅱ", "3": "Ⅲ"}.get(s, s)


def _dedup(recs):
    best = {}
    for r in recs:
        n = r.get("record_no")
        if n is None:
            continue
        if n not in best or r.get("score", 0) > best[n].get("score", 0):
            best[n] = r
    return sorted(best.values(), key=lambda x: -x.get("score", 0))


@mcp.tool()
def classify_product(description: str, top_k: int = 10) -> str:
    """根据产品描述给出候选管理类别，并列出支撑记录。

    参数：
      description: 产品描述，可以很模糊，例如「一个贴的东西」「带灯的钳子」「这个能做吗」
      top_k: 检索条数，默认 10

    返回：候选类别（按票数与相似度排序）、置信度、每条候选的证据记录。JSON 字符串。
    """
    recs = _dedup(fetch(description, top_k))
    if not recs:
        return dumps({"输入": description, "结论": "知识库无匹配，建议申请分类界定", "候选": []})

    votes: dict[str, list] = {}
    for r in recs:
        lv = _norm(r.get("管理类别", ""))
        if not lv:
            continue
        votes.setdefault(lv, []).append({
            "record_no": r.get("record_no"),
            "名称": r.get("title"),
            "score": round(r.get("score", 0), 4),
            "依据": r.get("依据"),
        })

    if not votes:
        return dumps({"输入": description, "结论": "检索到记录但类别无法归一", "候选": []})

    cands = []
    for lv, evs in sorted(votes.items(), key=lambda kv: -max(e["score"] for e in kv[1])):
        cands.append({
            "管理类别": lv,
            "支撑记录数": len(evs),
            "最高相似度": max(e["score"] for e in evs),
            "证据": sorted(evs, key=lambda e: -e["score"])[:3],
        })

    top = cands[0]
    conf = "高" if (len(cands) == 1 or top["最高相似度"] - cands[1]["最高相似度"] > 0.05) \
        and top["最高相似度"] >= 0.9 else ("中" if top["最高相似度"] >= 0.75 else "低")

    return dumps({
        "输入": description,
        "首选": top["管理类别"],
        "置信度": conf,
        "候选": cands,
        "提示": "置信度为低或候选并列时，应先追问产品用途与接触方式，不要直接定论"
                if conf != "高" else "",
    })


@mcp.tool()
def registration_path(management_class: str) -> str:
    """由管理类别推注册路径、受理机关与临床评价要求。

    参数：
      management_class: Ⅰ / Ⅱ / Ⅲ / 非医疗器械 / 药械组合
    """
    lv = _norm(management_class)
    rule = CLASS_RULES.get(lv)
    if not rule:
        return dumps({"error": "未知类别", "输入": management_class,
                      "可选值": list(CLASS_RULES)})
    return dumps({
        "管理类别": lv,
        "办理方式": rule["reg_path"],
        "受理机关": rule["authority"],
        "临床评价": rule["clinical"],
        "规则编号": "class_rules[%s]" % lv,
    })


@mcp.tool()
def clinical_eval_required(management_class: str) -> str:
    """判断是否需要做临床评价。

    参数：
      management_class: 管理类别

    说明：知识库未收录《免于临床评价医疗器械目录》原文，Ⅱ类只能给出「需核对目录」。
    """
    lv = _norm(management_class)
    rule = CLASS_RULES.get(lv)
    if not rule:
        return dumps({"error": "未知类别"})
    return dumps({
        "管理类别": lv,
        "结论": rule["clinical"],
        "可溯源性": "知识库未收录免临床目录原文" if lv == "Ⅱ" else "按类别规则判定",
    })


@mcp.tool()
def evidence_chain(question: str, top_k: int = 10) -> str:
    """给定问题，产出结构化证据链，每一跳都带来源。

    参数：
      question: 用户问题
      top_k: 检索条数，默认 10
    """
    recs = _dedup(fetch(question, top_k))
    if not recs:
        return dumps({"question": question, "hops": [], "结论": "无可引用证据"})

    best = recs[0]
    lv = _norm(best.get("管理类别", ""))
    rule = CLASS_RULES.get(lv, {})

    hops = [
        {"step": 1, "from": "用户描述", "to": "候选记录 %s · %s" % (
            best.get("record_no"), best.get("title")),
         "evidence": {"type": "clause", "ref": best.get("依据") or "记录 %s" % best.get("record_no")},
         "confidence": round(best.get("score", 0), 4)},
        {"step": 2, "from": "记录 %s" % best.get("record_no"), "to": "管理类别 %s" % lv,
         "evidence": {"type": "clause", "ref": best.get("依据") or "目录条目"},
         "confidence": round(best.get("score", 0), 4)},
    ]
    if rule:
        hops.append({"step": 3, "from": "管理类别 %s" % lv,
                     "to": "注册路径 %s / %s" % (rule["reg_path"], rule["authority"]),
                     "evidence": {"type": "rule", "ref": "class_rules[%s]" % lv},
                     "confidence": 1.0})
        hops.append({"step": 4, "from": "注册路径", "to": "临床评价 %s" % rule["clinical"],
                     "evidence": {"type": "rule", "ref": "class_rules[%s]" % lv},
                     "confidence": 1.0})

    others = [{"record_no": r.get("record_no"), "名称": r.get("title"),
               "管理类别": _norm(r.get("管理类别", "")), "score": round(r.get("score", 0), 4)}
              for r in recs[:5]]

    return dumps({
        "question": question,
        "结论": "「%s」，走%s，由%s受理" % (lv, rule.get("reg_path", "—"), rule.get("authority", "—")),
        "hops": hops,
        "备选": others,
        "citations": [{"doc": "医疗器械分类目录", "clause": best.get("依据") or "记录 %s" % best.get("record_no")}],
    })


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
