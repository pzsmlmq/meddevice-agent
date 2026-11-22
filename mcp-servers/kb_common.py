"""
共用的 KB 访问与解析（两个 MCP server 都用）

切片可能在一条记录中间断开：编号在上一片末尾，字段在下一片开头。
所以做法是——按「记录 N ｜」逐段解析，再把同编号的多段合并，取字段最全的那份。
"""
import json
import os
import re
from typing import Any

import httpx

NEXENT = os.environ.get("NEXENT_URL", "http://localhost:5010")
INDEX = os.environ.get("KB_INDEX", "6-9535c32bff594df4bf46c245a5731965")
TOKEN = os.environ.get("NEXENT_TOKEN", "mock_access_token")

HEAD = re.compile(r"^记录\s*(\d+)\s*｜\s*([^｜]+?)\s*｜\s*(.+)$")
FIELD = re.compile(r"^([^：]{2,10})：(.+)$")
KEY_FIELDS = ("管理类别", "依据", "目录", "二级产品类别", "预期用途", "品名举例")


def search(query: str, top_k: int = 8) -> list[dict]:
    try:
        with httpx.Client(timeout=60) as c:
            r = c.post(
                f"{NEXENT}/indices/search/hybrid",
                json={"query": query, "index_names": [INDEX], "top_k": top_k},
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
            r.raise_for_status()
            return r.json().get("results") or []
    except Exception as e:
        return [{"error": str(e), "content": ""}]


def parse_records(content: str, score: float = 0.0) -> list[dict]:
    recs: list[dict] = []
    cur: dict[str, Any] | None = None
    for raw in content.split("\n"):
        line = raw.strip()
        if not line or set(line) <= set("-"):
            continue
        m = HEAD.match(line)
        if m:
            if cur:
                recs.append(cur)
            cur = {"record_no": int(m.group(1)),
                   "记录类型": m.group(2).strip(),
                   "title": m.group(3).strip(),
                   "score": score}
            continue
        if cur is None:
            continue
        fm = FIELD.match(line)
        if fm:
            cur.setdefault(fm.group(1).strip(), fm.group(2).strip())
    if cur:
        recs.append(cur)
    return recs


def _richness(r: dict) -> int:
    return sum(1 for k in KEY_FIELDS if r.get(k))


def fetch(query: str, top_k: int = 8) -> list[dict]:
    """检索并合并同编号记录，返回按分数降序、字段最全的记录"""
    merged: dict[int, dict] = {}
    for r in search(query, top_k):
        if r.get("error"):
            continue
        for rec in parse_records(r.get("content") or "", r.get("score", 0)):
            n = rec["record_no"]
            old = merged.get(n)
            if old is None:
                merged[n] = rec
            else:
                # 取字段更多的那个作为底，补齐缺的
                base, other = (rec, old) if _richness(rec) > _richness(old) else (old, rec)
                for k, v in other.items():
                    base.setdefault(k, v)
                base["score"] = max(base.get("score", 0), other.get("score", 0))
                merged[n] = base

    result = sorted(merged.values(), key=lambda x: -x.get("score", 0))

    # 切片可能把编号和字段切散，前几条若缺关键字段，按编号补一次
    for rec in result[:3]:
        if rec.get("管理类别") and rec.get("依据"):
            continue
        n = rec["record_no"]
        for r in search("记录 %d" % n, 6):
            if r.get("error"):
                continue
            for extra in parse_records(r.get("content") or "", 0):
                if extra.get("record_no") == n:
                    for k, v in extra.items():
                        if k in ("score", "record_no"):
                            continue
                        rec.setdefault(k, v)

    return result


def brief(rec: dict) -> dict:
    return {
        "record_no": rec.get("record_no"),
        "类型": rec.get("记录类型"),
        "名称": rec.get("title"),
        "年份": rec.get("年份"),
        "管理类别": rec.get("管理类别"),
        "二级产品类别": rec.get("二级产品类别"),
        "依据": rec.get("依据"),
        "score": round(rec.get("score", 0), 4),
    }


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)
