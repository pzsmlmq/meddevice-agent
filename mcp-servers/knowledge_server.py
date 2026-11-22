"""
knowledge MCP server —— 医疗器械分类知识库查询

职责：只负责「查」。不推理、不下结论。
数据来源：Nexent 索引（5322 条记录，按记录编号可溯源）

启动：python knowledge_server.py  → http://0.0.0.0:8001/mcp
"""
from mcp.server.fastmcp import FastMCP

from kb_common import INDEX, brief, dumps, fetch

mcp = FastMCP("nexent-knowledge", host="0.0.0.0", port=8001)


@mcp.tool()
def search_concept(query: str, top_k: int = 10) -> str:
    """按自然语言检索医疗器械分类目录与历年分类界定记录。

    参数：
      query: 检索词。可以是产品名、用途描述或一句口语，例如「内镜手术用的钳子」「一个贴的东西」
      top_k: 检索条数，默认 10，范围 1-20

    返回：候选记录列表，每条含记录编号、类型、管理类别、法规出处。JSON 字符串。
    """
    top_k = max(1, min(int(top_k or 10), 20))
    recs = fetch(query, top_k)
    # 同一记录可能被多个切片命中，按编号去重，保留最高分
    best: dict[int, dict] = {}
    for r in recs:
        n = r.get("record_no")
        if n is None:
            continue
        if n not in best or r.get("score", 0) > best[n].get("score", 0):
            best[n] = r
    items = sorted(best.values(), key=lambda x: -x.get("score", 0))
    return dumps({"query": query, "count": len(items), "items": [brief(i) for i in items]})


@mcp.tool()
def get_concept(record_no: int) -> str:
    """按记录编号取完整记录（含产品描述、预期用途、品名举例、法规出处）。

    参数：
      record_no: 记录编号，来自 search_concept 的返回值
    """
    recs = fetch("记录 %d" % record_no, 20)
    for r in recs:
        if r.get("record_no") == record_no:
            return dumps({k: v for k, v in r.items() if k != "score"})
    return dumps({"error": "未找到该记录", "record_no": record_no})


@mcp.tool()
def list_children(catalog: str, limit: int = 15) -> str:
    """列出某个子目录或一级产品类别下的记录。

    参数：
      catalog: 子目录名或一级类别名，例如「01有源手术器械」「手术器械」
      limit: 最多返回条数，默认 15
    """
    recs = fetch(catalog, 20)
    hits = [r for r in recs if r.get("目录") == catalog or r.get("一级产品类别") == catalog]
    if not hits:
        hits = recs
    seen, out = set(), []
    for r in hits:
        n = r.get("record_no")
        if n in seen:
            continue
        seen.add(n)
        out.append(brief(r))
        if len(out) >= limit:
            break
    return dumps({"catalog": catalog, "count": len(out), "items": out})


@mcp.tool()
def get_clause(record_no: int) -> str:
    """取某条记录的法规出处与原文片段，用于证据链引用。

    参数：
      record_no: 记录编号
    """
    recs = fetch("记录 %d" % record_no, 20)
    for r in recs:
        if r.get("record_no") == record_no:
            return dumps({
                "record_no": record_no,
                "管理类别": r.get("管理类别"),
                "依据": r.get("依据"),
                "品名举例": r.get("品名举例"),
                "预期用途": r.get("预期用途"),
            })
    return dumps({"error": "未找到该记录"})


@mcp.tool()
def index_info() -> str:
    """返回当前知识库的索引标识，用于排查配置问题。"""
    return dumps({"index": INDEX, "tools": ["search_concept", "get_concept",
                                            "list_children", "get_clause"]})


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
