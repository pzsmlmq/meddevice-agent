# -*- coding: utf-8 -*-
"""把 9 个 MCP 工具绑到智能体上，并去掉那个测试工具"""
import json
import urllib.request

TOKEN = "mock_access_token"
BASE = "http://localhost:5010"
AGENT = 2
TOOL_IDS = [36, 37, 38, 39, 40, 41, 42, 43, 44]
DROP = [35]   # 测试工具，去掉


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


for tid in TOOL_IDS:
    code, res = post("/tool/update", {"tool_id": tid, "agent_id": AGENT, "params": {}, "enabled": True})
    print("tool %d -> %s %s" % (tid, code, "" if code == 200 else str(res)[:120]))

for tid in DROP:
    code, res = post("/tool/update", {"tool_id": tid, "agent_id": AGENT, "params": {}, "enabled": False})
    print("tool %d (disable) -> %s" % (tid, code))

info = post("/agent/search_info", {"agent_id": AGENT})[1]
print("\n=== 绑定结果 ===")
for t in info.get("tools") or []:
    print("  %-24s %-8s enabled=%s" % (t.get("name"), t.get("source"), t.get("enabled")))
