# -*- coding: utf-8 -*-
"""
证据链侧栏 · 演示页（角色 C 交付物）

只做三件事（见 C-证据链侧栏需求.docx 第二节）：
  1. 读 data/samples/evidence_mock.json，结论显示在最上面
  2. hops 数组逐条列出，每条一行
  3. 点某一步，展开它的原文和出处

运行：
    cd ict
    streamlit run evidence_chain.py

截图 / 录像时可以先定好状态：
    http://localhost:8501/?sample=2     直接打开第 2 条样例
    http://localhost:8501/?open=1       推理链全部展开

不连后端、不连知识库、不需要 Nexent，纯本地 JSON 渲染。
"""

import json
from pathlib import Path

import streamlit as st

from ui_theme import EVIDENCE_CSS, THEME_CSS, esc

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "samples" / "evidence_mock.json"

# 证据类型 → (中文标签, 样式类)。not_in 是「查过但没有」的阴性证据，颜色要区分开。
TYPE_META = {
    "clause": ("条款", "badge-clause"),
    "rule": ("规则", "badge-rule"),
    "not_in": ("阴性证据", "badge-neg"),
    "": ("依据", "badge-other"),
}

CSS = THEME_CSS + EVIDENCE_CSS


def load_items():
    with open(DATA_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def hop_label(hop: dict) -> str:
    """收起状态也要能看出「从什么推出什么」和这一步的可信度。"""
    label = f'{hop.get("step", "?")}. {hop.get("from", "—")} → {hop.get("to", "—")}'
    conf = hop.get("confidence")
    if isinstance(conf, (int, float)):
        label += f"　·　{conf:.0%}"
    return label


def hop_body(hop: dict) -> str:
    ev = hop.get("evidence") or {}
    type_name, type_cls = TYPE_META.get(ev.get("type", ""), ("依据", "badge-other"))
    conf = hop.get("confidence")
    conf_txt = f"{conf:.1%}" if isinstance(conf, (int, float)) else "未给出"
    return (
        '<div class="hop-meta">'
        f'<span class="badge {type_cls}">{esc(type_name)}</span>'
        f'<span class="conf">这一跳的可信度 {esc(conf_txt)}</span>'
        "</div>"
        '<div class="ev-label">依据出处</div>'
        f'<div class="ev-ref">{esc(ev.get("ref") or "（这一步没有给出处）")}</div>'
        '<div class="ev-label">原文</div>'
        f'<div class="ev-quote">{esc(ev.get("text") or "（无原文）")}</div>'
    )


def alt_table(alts) -> str:
    if not alts:
        return '<p class="cites">（这条没有备选记录）</p>'
    rows = []
    for a in alts:
        score = a.get("score")
        score_txt = f"{score:.3f}" if isinstance(score, (int, float)) else "—"
        rows.append(
            "<tr>"
            f'<td class="mono">{esc(a.get("record_no"))}</td>'
            f'<td>{esc(a.get("名称"))}</td>'
            f'<td>{esc(a.get("管理类别"))}</td>'
            f'<td class="num">{esc(score_txt)}</td>'
            "</tr>"
        )
    head = (
        "<tr><th>记录</th><th>名称</th><th>管理类别</th>"
        '<th class="num">相似度</th></tr>'
    )
    return f'<table class="alt">{head}{"".join(rows)}</table>'


def answer_html(item: dict) -> str:
    """左栏回答正文：结论 + 依据。依据只用 hops 里已有的出处和原文，不另外编。"""
    seen, bullets = set(), []
    for hop in item.get("hops", []):
        ev = hop.get("evidence") or {}
        key = (ev.get("ref"), ev.get("text"))
        if not key[1] or key in seen:
            continue
        seen.add(key)
        bullets.append(
            "<li>"
            f'<div class="src">{esc(ev.get("ref") or "依据")}</div>'
            f'<div class="txt">{esc(ev.get("text"))}</div>'
            "</li>"
        )

    parts = [f'<div class="a-lead">{esc(item.get("结论"))}</div>']
    if bullets:
        parts.append('<div class="a-sub">依据</div><ul class="a-list">' + "".join(bullets) + "</ul>")
    return f'<div class="a-card">{"".join(parts)}</div>'


def sample_label(item: dict, i: int) -> str:
    q = item.get("question", "")
    short = q if len(q) <= 12 else q[:12] + "…"
    return f"样例 {i + 1} · {short}"


def query_int(name: str, default: int, low: int, high: int) -> int:
    """支持 ?sample=2 直接打开某条样例，录像和截图时省一次点击。"""
    try:
        return max(low, min(high, int(st.query_params.get(name, default))))
    except (TypeError, ValueError):
        return default


def main() -> None:
    st.set_page_config(
        page_title="分类界定 · 证据链",
        page_icon="🧾",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(CSS, unsafe_allow_html=True)

    if not DATA_FILE.exists():
        st.error(f"找不到样例数据：{DATA_FILE}")
        st.stop()

    try:
        items = load_items()
    except json.JSONDecodeError as exc:
        st.error(f"JSON 解析失败（{DATA_FILE.name} 第 {exc.lineno} 行）：{exc.msg}")
        st.stop()

    st.markdown(
        '<div class="hero">'
        '<div class="kicker">第十一届华为 ICT 大赛 · 创新赛 · 赛题 3</div>'
        '<div class="hero-title">医疗器械分类界定 · 证据链</div>'
        '<div class="sub">产品描述 → 二级类别 → 管理类别 → 注册路径 → 临床评价要求，'
        "每一步都能点开、指回原文。</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.06, 1], gap="large")

    with left:
        st.markdown('<div class="sec-label">提问</div>', unsafe_allow_html=True)
        idx = st.selectbox(
            "选择样例",
            range(len(items)),
            index=query_int("sample", 1, 1, len(items)) - 1,
            format_func=lambda i: sample_label(items[i], i),
            label_visibility="collapsed",
        )
        item = items[idx]
        hops = item.get("hops", [])

        st.markdown(f'<div class="q-card">{esc(item["question"])}</div>', unsafe_allow_html=True)
        st.markdown('<div class="sec-label">回答</div>', unsafe_allow_html=True)
        st.markdown(answer_html(item), unsafe_allow_html=True)

        st.markdown(
            '<div class="sec-label mt">备选记录</div>', unsafe_allow_html=True
        )
        st.markdown(alt_table(item.get("备选")), unsafe_allow_html=True)

    with right:
        st.markdown(
            '<div class="side-head"><span class="t">证据链</span>'
            f'<span class="n">{len(hops)} 步 · 点开看原文</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="concl"><div class="lbl">结论</div>'
            f'<div class="val">{esc(item.get("结论"))}</div></div>',
            unsafe_allow_html=True,
        )

        open_all = st.checkbox(
            "全部展开", value=st.query_params.get("open") == "1"
        )
        for hop in hops:
            with st.expander(hop_label(hop), expanded=open_all or hop.get("step") == 1):
                st.markdown(hop_body(hop), unsafe_allow_html=True)

        if item.get("需确认"):
            st.markdown(
                '<div class="warn"><span class="h">需确认</span>'
                f'{esc(item["需确认"])}</div>',
                unsafe_allow_html=True,
            )

        cites = item.get("citations") or []
        if cites:
            lines = "<br>".join(
                f'· <b>{esc(c.get("doc"))}</b> ／ {esc(c.get("clause"))}' for c in cites
            )
            st.markdown(f'<div class="cites"><b>引用</b><br>{lines}</div>', unsafe_allow_html=True)

    st.markdown(
        '<p class="cites" style="margin-top:22px;text-align:center">'
        f'演示数据：ict/data/samples/{esc(DATA_FILE.name)}（两条真实样例）　|　'
        "本页不连后端，只把 JSON 渲染成可点开的证据链</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
