# -*- coding: utf-8 -*-
"""把 6 个 Skill 绑到智能体，同时保留已有的 10 个工具"""
import json
import urllib.request

TOKEN = "mock_access_token"
BASE = "http://localhost:5010"
AGENT = 2
TOOLS = [19, 36, 37, 38, 39, 40, 41, 42, 43, 44]
SKILLS = [7, 8, 9, 10, 11, 12]


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


code, res = post("/agent/update", {
    "agent_id": AGENT,
    "name": "医疗器械分类界定助手",
    "display_name": "医疗器械分类界定助手",
    "model_ids": [5, 7],
    "enabled_tool_ids": TOOLS,
    "enabled_skill_ids": SKILLS,
    "max_steps": 12,
    "is_main_agent": True,
    "enabled": True,
})
print("update:", code, str(res)[:120])

info = post("/agent/search_info", {"agent_id": AGENT})[1]
print("\n工具 %d 个：" % len(info.get("tools") or []))
for t in info.get("tools") or []:
    print("  %-24s %s" % (t.get("name"), t.get("source")))
print("\nSkill %d 个：" % len(info.get("skills") or []))
for s in info.get("skills") or []:
    print("  %-30s %s" % (s.get("name"), s.get("description", "")[:40]))
