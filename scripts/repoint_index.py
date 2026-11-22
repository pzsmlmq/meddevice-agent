# -*- coding: utf-8 -*-
"""把智能体与 MCP 全部指向新的全量索引"""
import json
import re
import subprocess
import urllib.request
from pathlib import Path

TOKEN = "mock_access_token"
BASE = "http://localhost:5010"
NEW_INDEX = "6-9535c32bff594df4bf46c245a5731965"


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


# 1. 智能体的知识库工具
res = post("/tool/update", {
    "tool_id": 19, "agent_id": 2, "enabled": True,
    "params": {
        "top_k": 10,
        "index_names": [NEW_INDEX],
        "search_mode": "hybrid",
        "rerank": True,
        "rerank_model_name": "BAAI/bge-reranker-v2-m3",
    },
})
print("agent KB tool ->", res["tool_instance"]["params"]["index_names"])

# 2. MCP 服务的默认索引
for path in (r"C:\WSL\mcp-servers\kb_common.py", "/root/mcp-servers/kb_common.py"):
    p = Path(path)
    if not p.exists():
        continue
    s = p.read_text(encoding="utf-8")
    s2 = re.sub(r'INDEX = os\.environ\.get\("KB_INDEX", "[^"]*"\)',
                'INDEX = os.environ.get("KB_INDEX", "%s")' % NEW_INDEX, s)
    if s2 != s:
        p.write_text(s2, encoding="utf-8")
        print("updated:", path)
