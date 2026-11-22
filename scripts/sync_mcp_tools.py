# -*- coding: utf-8 -*-
"""把两个 MCP 服务里的工具补进 Nexent 的工具表，让智能体的工具选择器能看到"""
import json
import urllib.request
from pathlib import Path

TOKEN = "mock_access_token"
BASE = "http://localhost:5010"
OUT = Path(r"C:\WSL\insert_mcp_tools.sql")


def get(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def q(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


rows = []
for mcp_id in (1, 2):
    data = get(f"/mcp/tools?mcp_id={mcp_id}")
    for t in data.get("tools") or []:
        rows.append({
            "name": t["name"],
            "description": (t.get("description") or "")[:900],
            "inputs": t.get("inputs") or "{}",
            "output_type": t.get("output_type") or "object",
        })

print("抓到 %d 个工具: %s" % (len(rows), ", ".join(r["name"] for r in rows)))

sql = ["-- 补登记 MCP 工具，让工具选择器可见",
       "DELETE FROM nexent.ag_tool_info_t WHERE source='mcp' AND name <> 'local_test_tool_name';"]

for r in rows:
    sql.append(
        "INSERT INTO nexent.ag_tool_info_t "
        "(name, class_name, description, source, author, usage, params, inputs, output_type, "
        " is_available, created_by, updated_by, origin_name, category, labels, is_user_selectable) "
        "VALUES (%s, %s, %s, 'mcp', 'tenant_id', 'outer-apis', '[]'::json, %s, %s, true, "
        "'user_id', 'user_id', %s, '', null, true);" % (
            q(r["name"]), q(r["name"]), q(r["description"]), q(r["inputs"]),
            q(r["output_type"]), q(r["name"])))

OUT.write_text("\n".join(sql), encoding="utf-8")
print("SQL 已写:", OUT)
