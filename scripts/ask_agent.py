# -*- coding: utf-8 -*-
"""抓取智能体回答：只保留最后一次 attempt 的输出，避免重复"""
import json
import sys
import urllib.request

TOKEN = "mock_access_token"
URL = "http://localhost:5014/agent/run"
QUERY = sys.argv[1] if len(sys.argv) > 1 else "我们有个一次性无菌的贴敷材料，含银离子，贴创面上，算几类？"

body = json.dumps({"query": QUERY, "agent_id": 2, "is_debug": True}, ensure_ascii=False).encode()
req = urllib.request.Request(URL, data=body,
                             headers={"Content-Type": "application/json",
                                      "Authorization": f"Bearer {TOKEN}"},
                             method="POST")

buf: dict[str, list] = {}
order: list[str] = []
tools = []
final_text = None

with urllib.request.urlopen(req, timeout=300) as r:
    for raw in r:
        line = raw.decode("utf-8", "ignore").strip()
        if not line.startswith("data:"):
            continue
        try:
            ev = json.loads(line[5:].strip())
        except Exception:
            continue
        t = ev.get("type")
        if t == "tool":
            tools.append(ev.get("tool_name"))
        elif t == "final_answer":
            ph = ev.get("answer_phase")
            if ph == "delta":
                a = ev.get("attempt_id") or "?"
                if a not in buf:
                    buf[a] = []
                    order.append(a)
                buf[a].append(ev.get("content") or "")
            elif ev.get("content") and len(ev.get("content")) > 40:
                final_text = ev.get("content")

text = final_text or ("".join(buf[order[-1]]) if order else "")

# 直接写 UTF-8 文件，避开 Windows 终端编码
from pathlib import Path
out_path = Path(r"C:\Users\A\Documents\deepseek-harness\default-workspace\ict\data\samples\answer_sample.txt")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(
    "调用工具：" + " → ".join(tools) + "\n\n" + "=" * 50 + "\n" + text.strip(),
    encoding="utf-8")
print("saved:", out_path)
print("chars:", len(text))
