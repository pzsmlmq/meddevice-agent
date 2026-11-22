# -*- coding: utf-8 -*-
"""把两个 MCP server 注册进 Nexent"""
import json
import urllib.request

TOKEN = "mock_access_token"
BASE = "http://localhost:5010"

SERVERS = [
    {
        "name": "medical-knowledge",
        "server_url": "http://host.docker.internal:8001/mcp",
        "description": "医疗器械分类知识库：按自然语言检索目录条目与分类界定记录，可按记录编号取原文。",
        "tags": ["medical-device", "knowledge"],
    },
    {
        "name": "medical-reasoning",
        "server_url": "http://host.docker.internal:8002/mcp",
        "description": "分类判定与决策路径：由产品描述推候选类别、由类别推注册路径与临床评价要求、产出可溯源证据链。",
        "tags": ["medical-device", "reasoning"],
    },
]


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]
    except Exception as e:
        return 0, str(e)[:300]


for s in SERVERS:
    code, res = post("/mcp/add", s)
    print("%-20s HTTP %s" % (s["name"], code))
    print("   ", json.dumps(res, ensure_ascii=False)[:400] if isinstance(res, dict) else res)
    print()
