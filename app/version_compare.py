# -*- coding: utf-8 -*-
"""
版本对比页 · 本体与知识库（角色 C 交付物）

对应项目分工 v3 · C 的 W4：把两个版本并排显示，标出新增了什么、改了什么。
「可进化」只有在这一页能被看见。

两个对比口径都能选：
  A 本体演进   v1.0 截至 2021  →  v1.1 人工修正回灌（+13 条）
  B 数据版本   2021 切片        →  2022 切片（+439 条）

数据源：data/evolution/kb_old.md / kb_new.md / kb_learned.md
        data/evolution/result_v2.json / result_v4.json（指标）
运行：
    cd ict
    streamlit run version_compare.py
"""

import json
import re
from collections import Counter
from pathlib import Path

import streamlit as st

from ui_theme import THEME_CSS, cards, esc, hero

ROOT = Path(__file__).resolve().parent
EVO = ROOT / "data" / "evolution"
KB = {
    "old": EVO / "kb_old.md",
    "new": EVO / "kb_new.md",
    "learned": EVO / "kb_learned.md",
}
RESULT_V2 = EVO / "result_v2.json"
RESULT_V4 = EVO / "result_v4.json"

PAGE_CSS = """
<style>
.side { background: #fff; border: 1px solid #e5e8ec; border-radius: 10px; padding: 14px 16px; }
.side.right { border-color: #cfe3d4; box-shadow: 0 1px 0 #e8f6ec; }
.vh { font-size: 12px; color: #8a9199 !important; letter-spacing: .6px; margin-bottom: 2px; }
.vt { font-size: 15px; font-weight: 600; color: #17324a !important; margin-bottom: 10px; }
.vr { display: flex; justify-content: space-between; font-size: 12.5px;
      padding: 5px 0; border-top: 1px solid #f0f2f4; }
.vr:first-of-type { border-top: none; }
.vr .k { color: #8a9199 !important; }
.vr .v { color: #1f364d !important; font-weight: 600; font-variant-numeric: tabular-nums; }
.vr .v.up { color: #15803d !important; }
table.alt td.before, table.alt td.after { white-space: nowrap; }
table.alt td.before { color: #8a9199 !important; }
table.alt td.after { color: #15803d !important; font-weight: 600; }
.metric { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
.metric .m { background: #f7f9fb; border-radius: 8px; padding: 10px 12px; }
.metric .m .n { font-size: 19px; font-weight: 700; color: #17324a !important; }
.metric .m .l { font-size: 11.5px; color: #8a9199 !important; margin-top: 2px; }
</style>
"""

FIELD_ORDER = ["记录类型", "年份", "目录", "产品描述", "预期用途", "品名举例",
               "管理类别", "原始判断", "修正后管理类别", "依据", "审核说明"]


@st.cache_data(show_spinner=False)
def parse_kb(path_str: str):
    """把 kb_*.md 拆成记录：## 记录 N · 名称 + 若干「- 字段：值」行。"""
    text = Path(path_str).read_text(encoding="utf-8")
    out = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        lines = block.split("\n")
        title = lines[0].strip()
        fields = {}
        for line in lines[1:]:
            m = re.match(r"^- ([^：]+)：(.*)$", line.strip())
            if m:
                fields[m.group(1).strip()] = m.group(2).strip()
        if not title:
            continue
        out.append({"title": title, "name": title.split(" · ", 1)[-1], "fields": fields})
    return out


def rkey(rec):
    """判断「同一条」的口径：品名 + 产品描述前 60 字。编号会重排，不能用编号。"""
    return (rec["name"], (rec["fields"].get("产品描述") or "")[:60])


def diff(old, new):
    ko = {rkey(r): r for r in old}
    kn = {rkey(r): r for r in new}
    added = [kn[k] for k in kn if k not in ko]
    removed = [ko[k] for k in ko if k not in kn]
    changed = []
    for k in set(ko) & set(kn):
        a, b = ko[k]["fields"], kn[k]["fields"]
        diffs = {f: (a.get(f), b.get(f)) for f in set(a) | set(b) if a.get(f) != b.get(f)}
        if diffs:
            changed.append((kn[k], diffs))
    return added, removed, changed


@st.cache_data(show_spinner=False)
def load_metrics():
    out = {}
    if RESULT_V2.exists():
        data = json.load(open(RESULT_V2, encoding="utf-8"))
        for key, rows in data.items():
            ok = sum(1 for r in rows if r.get("gold") == r.get("pred"))
            out[key] = {"acc": ok / len(rows) if rows else 0, "n": len(rows), "ok": ok}
    if RESULT_V4.exists():
        data = json.load(open(RESULT_V4, encoding="utf-8"))
        out["topk"] = {
            k: {"acc": v.get("acc"), "f1": v.get("f1"), "n": len(v.get("rows", []))}
            for k, v in data.items()
        }
    return out


def rec_class(rec) -> str:
    """人工修正记录没有「管理类别」，判定看「修正后管理类别」。"""
    f = rec["fields"]
    v = (f.get("管理类别") or f.get("修正后管理类别") or "").strip()
    return v or "未标注"


def class_dist(records):
    return Counter(rec_class(r) for r in records)


def bar_rows(counter, total) -> str:
    rows = []
    for k, v in counter.most_common(8):
        pct = 100.0 * v / total if total else 0
        rows.append(
            f'<div class="vr"><span class="k">{esc(k)}</span>'
            f'<span class="v">{v:,}　<span class="muted">{pct:.0f}%</span></span></div>'
        )
    return "".join(rows)


def main() -> None:
    st.set_page_config(page_title="版本对比 · 可进化", page_icon="🔀", layout="wide",
                       initial_sidebar_state="collapsed")
    st.markdown(THEME_CSS + PAGE_CSS, unsafe_allow_html=True)

    for p in KB.values():
        if not p.exists():
            st.error(f"找不到知识库文件：{p}")
            st.stop()

    st.markdown(
        hero(
            "第十一届华为 ICT 大赛 · 创新赛 · 赛题 3",
            "版本对比 · 本体与知识库的进化",
            "左边是上一版，右边是这一版。新增多少、改了什么、有没有变好，都在这一页上。",
        ),
        unsafe_allow_html=True,
    )

    modes = ["本体演进 v1.0 → v1.1（人工修正回灌）", "数据版本 2021 → 2022（目录扩充）"]
    mode = st.radio(
        "对比口径",
        modes,
        index=1 if st.query_params.get("mode") == "b" else 0,
        horizontal=True,
        label_visibility="collapsed",
    )
    is_evolve = mode.startswith("本体演进")

    old = parse_kb(str(KB["old"]))
    new = parse_kb(str(KB["learned"] if is_evolve else KB["new"]))
    added, removed, changed = diff(old, new)

    v1_label = "v1.0 · 截至 2021"
    v2_label = "v1.1 · 修正回灌后" if is_evolve else "2022 版 · 目录扩充后"

    st.markdown(
        cards([
            (f"{len(old):,}", "上一版记录"),
            (f"{len(new):,}", "这一版记录"),
            (f"+{len(added)}", "新增", "带依据的新记录", "up"),
            (f"{len(changed)}", "修改", "同一条的字段变了"),
            (f"{len(removed)}", "删除", "这一版没有的", "warn" if removed else ""),
        ]),
        unsafe_allow_html=True,
    )

    # ---------- 左右两栏：两版并排 ----------
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown(
            f'<div class="side"><div class="vh">{esc(v1_label)}</div>'
            f'<div class="vt">上一版</div>'
            f'<div class="vr"><span class="k">记录数</span><span class="v">{len(old):,}</span></div>'
            f'<div class="vr"><span class="k">分类界定记录</span>'
            f'<span class="v">{sum(1 for r in old if r["fields"].get("记录类型") == "分类界定"):,}</span></div>'
            f'<div class="vr"><span class="k">人工修正记录</span>'
            f'<span class="v">{sum(1 for r in old if "修正" in (r["fields"].get("记录类型") or "")):,}</span></div>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="sec-label mt">管理类别分布</div>'
            f'<div class="panel" style="padding:10px 14px">{bar_rows(class_dist(old), len(old))}</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="side right"><div class="vh">{esc(v2_label)}</div>'
            f'<div class="vt">这一版</div>'
            f'<div class="vr"><span class="k">记录数</span>'
            f'<span class="v up">{len(new):,}（+{len(new) - len(old)}）</span></div>'
            f'<div class="vr"><span class="k">分类界定记录</span>'
            f'<span class="v">{sum(1 for r in new if r["fields"].get("记录类型") == "分类界定"):,}</span></div>'
            f'<div class="vr"><span class="k">人工修正记录</span>'
            f'<span class="v">{sum(1 for r in new if "修正" in (r["fields"].get("记录类型") or "")):,}</span></div>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="sec-label mt">管理类别分布</div>'
            f'<div class="panel" style="padding:10px 14px">{bar_rows(class_dist(new), len(new))}</div>',
            unsafe_allow_html=True,
        )

    # ---------- 变更明细 ----------
    st.markdown('<div class="sec-label mt">新增了什么（左：上一版没有　右：这一版新增）</div>',
                unsafe_allow_html=True)

    if not added:
        st.markdown('<div class="warn"><span class="h">没有新增</span>两版记录完全一致。</div>',
                    unsafe_allow_html=True)
    else:
        limit = st.slider("显示条数", 5, max(5, len(added)), min(15, len(added)), step=1)
        rows = []
        for rec in added[:limit]:
            f = rec["fields"]
            name = rec["name"]
            name = name if len(name) <= 24 else name[:24] + "…"
            if is_evolve:
                before = (f.get("原始判断") or "—").replace("（错误）", "")
                after = f.get("修正后管理类别") or "—"
                clause = f.get("依据") or ""
                note = ""
            else:
                before = "—"
                after = f.get("管理类别") or "未标注"
                clause = f.get("依据") or f.get("法规文本链接") or ""
                note = f.get("品名举例") or ""
            cells = (
                f'<td class="l2">{esc(name)}</td>'
                f'<td class="before">{esc(before)}</td>'
                f'<td class="after">{esc(after)}</td>'
                f'<td>{esc(clause[:46])}</td>'
            )
            if not is_evolve:
                cells += f'<td class="hint">{esc(note[:40])}</td>'
            rows.append(f'<tr class="add">{cells}</tr>')
        head = ('<tr><th>记录</th><th>左 · 原判断</th><th>右 · 修正后</th><th>依据</th>'
                + ("" if is_evolve else "<th>品名举例</th>") + "</tr>")
        st.markdown(f'<table class="alt">{head}{"".join(rows)}</table>',
                    unsafe_allow_html=True)
        if len(added) > limit:
            st.markdown(f'<p class="muted">共 {len(added)} 条，当前显示前 {limit} 条，拖动上面的滑条看更多。</p>',
                        unsafe_allow_html=True)

    if changed:
        st.markdown(f'<div class="sec-label mt">改了什么（{len(changed)} 条）</div>',
                    unsafe_allow_html=True)
        rows = []
        for rec, diffs in changed[:20]:
            parts = []
            for field, (a, b) in diffs.items():
                parts.append(f"{field}：{a or '—'} → {b or '—'}")
            rows.append(f'<tr class="mod"><td>{esc(rec["name"][:26])}</td>'
                        f'<td colspan="4">{esc("；".join(parts)[:150])}</td></tr>')
        st.markdown('<table class="alt"><tr><th>记录</th><th colspan="4">字段变化</th></tr>'
                    + "".join(rows) + "</table>", unsafe_allow_html=True)
    else:
        st.markdown(
            '<p class="cites">修改 0 条：这一版只做加法，没有改动任何一条已有判定。</p>',
            unsafe_allow_html=True,
        )

    # ---------- 折算到本体 ----------
    old_classes = {rec_class(r) for r in old} - {"未标注"}
    new_classes = {rec_class(r) for r in new} - {"未标注"}
    st.markdown(
        cards([
            (f"+{len(added)}", "产品实例概念", "记录 → ProductExample 节点", "up"),
            (f"+{len(added)}", "has_class 关系", "每条记录带一个管理类别"),
            (f"+{len(new_classes - old_classes)}", "类别节点", "没有出现新的管理类别"),
            (f"+{len(removed)}", "失效关系", "旧版有、新版没有"),
        ]),
        unsafe_allow_html=True,
    )

    # ---------- 指标 ----------
    m = load_metrics()
    if is_evolve and "base" in m and "learned" in m:
        base, learned = m["base"], m["learned"]
        topk = m.get("topk", {})
        st.markdown('<div class="sec-label mt">这一版有没有变好（同一套题，同样配置只换知识库）</div>',
                    unsafe_allow_html=True)
        metric_cells = [
            (f'{base["acc"]:.1%}', f'基线（{base["ok"]}/{base["n"]} 题）'),
            (f'{learned["acc"]:.1%}', f'修正回灌后（{learned["ok"]}/{learned["n"]} 题）'),
        ]
        for k in sorted(topk, key=lambda x: int(x)):
            cell = topk[k]
            metric_cells.append((f'{cell["acc"]:.1%}',
                                 f'topk={k}　F1 {cell["f1"]:.3f}'))
        st.markdown(
            '<div class="metric">' + "".join(
                f'<div class="m"><div class="n">{esc(n)}</div><div class="l">{esc(l)}</div></div>'
                for n, l in metric_cells
            ) + "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="warn" style="margin-top:14px"><span class="h">怎么读这组数</span>'
            "50 道题，±1 题就是 ±2 个百分点：回灌前后 74% → 72% 是一道题的差别，"
            "说明「往知识库里加 13 条修正」在这套题上还没有体现出收益，样本太小看不出来。"
            "真正拉开差距的是检索档位：topk 从 3 提到 8，准确率 74% → 78%，"
            "F1 从 0.668 到 0.721；再提到 15，准确率不变、F1 涨到 0.791（区分得更细）。</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<p class="foot">数据源 data/evolution/kb_old.md → kb_{"learned" if is_evolve else "new"}.md'
        f'（{len(old):,} / {len(new):,} 条）　|　'
        "口径：品名 + 产品描述前 60 字判同一条，编号重排不算变化<br>"
        "「产品实例概念 / has_class 关系」是按本体契约的折算口径，不是 A 的抽取管线输出。</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
