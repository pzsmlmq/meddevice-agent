# -*- coding: utf-8 -*-
"""
本体浏览页 · 医疗器械分类目录（角色 C 交付物）

做三件事（对应项目分工 v3 · C 的 W3 任务）：
  1. 从 33 个子目录展开，点到一级、二级
  2. 每个二级类别能看到「管理类别」和「依据」
  3. 一眼看到规模：5,363 条记录 / 1,163 个二级类别 / 204 个一级类别

数据源：data/catalog_utf8.csv（B 的清洗产物，官方分类目录汇编版）
不连后端、不连知识库。

运行：
    cd ict
    streamlit run ontology_browse.py
"""

import csv
import re
from collections import OrderedDict, defaultdict
from pathlib import Path

import streamlit as st

from ui_theme import THEME_CSS, cards, esc, hero

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "data" / "catalog_utf8.csv"

# 「分类界定」不是真的二级类别，是原始表里标记「这条是分类界定结果」的占位值
LB_MARK = "分类界定"
NO_L1 = "（未标注一级类别）"
NO_L2 = "（未标注二级类别）"
NO_CAT = "（未标注子目录）"

# 分类目录本身出自这份公告；个别行有调整公告，以调整公告为准
DEFAULT_CLAUSE = "《医疗器械分类目录》2017年第104号公告"

CLASS_COLORS = {
    "Ⅰ": ("#15803d", "#e8f6ec"),
    "Ⅱ": ("#1d4f86", "#eaf2fb"),
    "Ⅲ": ("#b91c1c", "#fdeceb"),
}

# 长结论压成短标签（悬停能看到原文）
CLASS_SHORT = {
    "非医疗器械": "非医疗器械",
    "药械组合": "药械组合",
    "药械组合产品": "药械组合",
    "不单独作为医疗器械管理": "不单独管理",
    "该产品为以医疗器械为主的药械组合产品": "药械组合·械为主",
    "该产品为以药品为主的药械组合产品": "药械组合·药为主",
    "不属于药械组合产品，应按药品申请注册": "应按药品注册",
    "不属于药械组合产品，应按医疗器械申请注册": "应按器械注册",
    "视具体情况而定": "视情况而定",
    "Ⅲ（药械组合产品）": "Ⅲ·药械组合",
    "药品": "药品",
    "": "未标注",
}

PAGE_CSS = """
<style>
.l1row { display: flex; align-items: baseline; gap: 10px; margin: 16px 0 7px;
         padding-bottom: 6px; border-bottom: 1px solid #f0f2f4; }
.l1row .t { font-size: 13.5px; font-weight: 600; color: #17324a !important; }
.l1row .n { font-size: 11.5px; color: #9aa1a9 !important; }
.l1row:first-child { margin-top: 4px; }
table.alt td.l2 { font-weight: 500; color: #1f364d !important; }
table.alt td.cls { white-space: nowrap; }
table.alt .hint { color: #9aa1a9 !important; font-size: 11.5px; }
.empty { font-size: 12px; color: #9aa1a9 !important; margin: 2px 0 4px 2px; }
.path { color: #9aa1a9 !important; font-size: 11.5px; }
</style>
"""


def norm_class(value: str) -> str:
    v = (value or "").strip().replace("\n", " ")
    return {"I": "Ⅰ", "II": "Ⅱ", "III": "Ⅲ", "1": "Ⅰ", "2": "Ⅱ", "3": "Ⅲ"}.get(v, v)


def class7(value: str) -> str:
    """统一口径：管理类别归一到 7 类（Ⅰ/Ⅱ/Ⅲ/非医疗器械/药械组合/不单独管理/视情况）。"""
    v = norm_class(value).replace("\n", " ")
    if v in ("Ⅰ", "Ⅱ", "Ⅲ", "非医疗器械", "不单独作为医疗器械管理", "视具体情况而定"):
        return v
    if "药械组合" in v or "药品" in v:
        return "药械组合"
    return v or "未标注"


def chips(values) -> str:
    out, seen = [], set()
    for raw in values:
        v = class7(raw)
        if v in seen:
            continue
        seen.add(v)
        fg, bg = CLASS_COLORS.get(v, ("#52606d", "#eef1f4"))
        label = CLASS_SHORT.get(v, v)
        out.append(
            f'<span class="badge" style="background:{bg};color:{fg}" title="{esc(raw)}">{esc(label)}</span>'
        )
    return " ".join(out)


def class_sort(values):
    order = {"Ⅰ": 1, "Ⅱ": 2, "Ⅲ": 3}
    return sorted(values, key=lambda v: (v == "", order.get(class7(v), 9), str(v)))


@st.cache_data(show_spinner=False)
def load_catalog():
    """把 CSV 拆成「目录行」（有三级结构）和「分类界定行」（只有结论的产品实例）。"""
    with open(CATALOG, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    def get(r, k):
        return (r.get(k) or "").strip()

    tree = OrderedDict()          # 目录 -> 一级 -> {二级 -> {...}}
    lb_of = defaultdict(int)      # (目录, 一级) -> 分类界定条数
    lb_total = orphan = cat_rows = empty_rows = pseudo_rows = 0

    for r in rows:
        cat, l1, l2 = get(r, "目录"), get(r, "一级产品类别"), get(r, "二级产品类别")

        if l2 == LB_MARK:
            lb_total += 1
            if not cat:
                orphan += 1
                continue
            tree.setdefault(cat, OrderedDict()).setdefault(l1, OrderedDict())
            lb_of[(cat, l1)] += 1
            continue

        if not l2:
            # 统一口径：有品名或管理类别的算「目录行」，只是缺二级类别；两样都没有的是空行
            if not (get(r, "品名举例") or get(r, "管理类别")):
                empty_rows += 1
                continue
            l2 = NO_L2
            pseudo_rows += 1

        cat_rows += 1
        item = (tree.setdefault(cat, OrderedDict())
                    .setdefault(l1, OrderedDict())
                    .setdefault(l2, {"n": 0, "classes": set(), "clauses": set(),
                                     "examples": "", "desc": ""}))
        item["n"] += 1
        item["classes"].add(norm_class(get(r, "管理类别")))
        clause = get(r, "法规文本链接")
        if clause:
            item["clauses"].add(clause)
        if not item["examples"] and get(r, "品名举例"):
            item["examples"] = get(r, "品名举例")
        if not item["desc"] and get(r, "产品描述"):
            item["desc"] = get(r, "产品描述")

    l2_names = {n for c in tree for m in tree[c].values() for n in m if n != NO_L2}
    l2_edges = sum(1 for c in tree for m in tree[c].values() for n in m if n != NO_L2)
    l1_names = {l1 for c in tree for l1 in tree[c] if l1}
    mixed = sum(
        1 for c in tree for m in tree[c].values() for n, it in m.items()
        if n != NO_L2 and len({class7(v) for v in it["classes"]}) > 1
    )

    stats = {
        "rows": len(rows),
        "dirs_all": len({get(r, "目录") for r in rows if get(r, "目录")}),
        "cat_rows": cat_rows,
        "lb_total": lb_total,
        "empty_rows": empty_rows,
        "pseudo_rows": pseudo_rows,
        "orphan": orphan,
        "cats": len([c for c in tree if c]),
        "l1": len(l1_names),
        "l2": len(l2_names),
        "l2_edges": l2_edges,
        "mixed": mixed,
        "no_cat": sum(it["n"] for m in tree.get("", {}).values() for it in m.values()),
    }

    # 排序：目录按名字；一级按记录数降序，未标注一级的排最后
    ordered = OrderedDict()
    for cat in sorted(tree, key=lambda x: (x == "", x)):
        l1s = sorted(
            tree[cat].items(),
            key=lambda kv: (kv[0] == "", -sum(i["n"] for i in kv[1].values()) - lb_of.get((cat, kv[0]), 0)),
        )
        ordered[cat] = OrderedDict(l1s)
    return stats, ordered, dict(lb_of)


def l2_table(l2map) -> str:
    if not l2map:
        return ""
    head = ("<tr><th>二级类别</th><th>管理类别</th><th class='num'>记录</th>"
            "<th>依据</th></tr>")
    body = []
    for name, item in l2map.items():
        clause = "；".join(sorted(item["clauses"])) or DEFAULT_CLAUSE
        clause_short = clause if len(clause) <= 44 else clause[:44] + "…"
        body.append(
            "<tr>"
            f'<td class="l2">{esc(name)}'
            + (f'<div class="hint">{esc(item["examples"][:34])}</div>' if item["examples"] else "")
            + "</td>"
            f'<td class="cls">{chips(class_sort(item["classes"]))}</td>'
            f'<td class="num">{item["n"]}</td>'
            f'<td><span title="{esc(clause)}">{esc(clause_short)}</span></td>'
            "</tr>"
        )
    return f'<table class="alt">{head}{"".join(body)}</table>'


def search(tree, query: str):
    pat = re.compile(re.escape(query.strip()), re.I)
    hits = []
    for cat, l1map in tree.items():
        for l1, l2map in l1map.items():
            for name, item in l2map.items():
                hay = " ".join([name, l1, cat, item["examples"], item["desc"]])
                if pat.search(hay):
                    hits.append((cat, l1 or NO_L1, name, item))
    return hits


def main() -> None:
    st.set_page_config(page_title="本体浏览 · 分类目录", page_icon="🌳", layout="wide",
                       initial_sidebar_state="collapsed")
    st.markdown(THEME_CSS + PAGE_CSS, unsafe_allow_html=True)

    if not CATALOG.exists():
        st.error(f"找不到数据文件：{CATALOG}")
        st.stop()

    stats, tree, lb_of = load_catalog()
    cats = [c for c in tree if c]

    st.markdown(
        hero(
            "第十一届华为 ICT 大赛 · 创新赛 · 赛题 3",
            "本体浏览 · 医疗器械分类目录",
            f'{stats["cats"]} 个有结构的子目录 → {stats["l1"]} 个一级类别 → '
            f'{stats["l2"]:,} 个二级类别。每个二级类别都挂着管理类别和依据，判到哪一层都能往回查。',
        ),
        unsafe_allow_html=True,
    )

    st.markdown(
        cards([
            (f'{stats["rows"]:,}', "原始记录",
             f'目录 {stats["cat_rows"]:,} + 界定 {stats["lb_total"]:,} + 空行 {stats["empty_rows"]}'),
            ("5,322", "入库记录", "空行与重复不入库"),
            ("5,474", "切片", "知识库检索的块"),
            (f'{stats["cats"]}', "子目录", f'33 个目录值里的有效项'),
            (f'{stats["l1"]}', "一级类别", ""),
            (f'{stats["l2"]:,}', "二级类别", f'其中 {stats["mixed"]} 个 Ⅱ/Ⅲ 并存'),
            ("7", "管理类别", "已归一化"),
        ]),
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1.3, 1])
    with col1:
        query = st.text_input(
            "搜索", placeholder="二级类别名、品名举例、产品描述关键词，例如：敷料 / 内窥镜 / 超声",
            label_visibility="collapsed",
        )
    with col2:
        opts = ["全部子目录"] + cats
        want = st.query_params.get("cat", "全部子目录")
        if want.isdigit():                      # ?cat=14 也行，省得敲中文
            want = cats[int(want)] if int(want) < len(cats) else "全部子目录"
        pick = st.selectbox(
            "只看某个子目录", opts,
            index=opts.index(want) if want in opts else 0,
            label_visibility="collapsed",
        )

    if query.strip():
        hits = search(tree, query)
        st.markdown(f'<div class="sec-label">命中 {len(hits)} 个二级类别</div>',
                    unsafe_allow_html=True)
        if not hits:
            st.markdown('<div class="warn"><span class="h">没有命中</span>'
                        "换个词试试：品名举例和产品描述也一起搜了。</div>",
                        unsafe_allow_html=True)
        else:
            rows = []
            for cat, l1, name, item in hits[:60]:
                clause = "；".join(sorted(item["clauses"])) or DEFAULT_CLAUSE
                rows.append(
                    "<tr>"
                    f'<td class="path">{esc(cat)} ／ {esc(l1)}</td>'
                    f'<td class="l2">{esc(name)}</td>'
                    f'<td>{chips(class_sort(item["classes"]))}</td>'
                    f'<td class="num">{item["n"]}</td>'
                    f'<td>{esc(clause[:30])}</td>'
                    "</tr>"
                )
            head = ("<tr><th>路径</th><th>二级类别</th><th>管理类别</th>"
                    "<th class='num'>记录</th><th>依据</th></tr>")
            st.markdown(f'<table class="alt">{head}{"".join(rows)}</table>',
                        unsafe_allow_html=True)
            if len(hits) > 60:
                st.markdown(f'<p class="muted">只显示前 60 条，共 {len(hits)} 条。</p>',
                            unsafe_allow_html=True)
    else:
        shown = [c for c in cats if pick in ("全部子目录", c)]
        focus = pick != "全部子目录"
        hint = "（点开看一级和二级）" if not focus else "（已展开）"
        st.markdown(f'<div class="sec-label mt">目录结构 · {len(shown)} 个子目录{hint}</div>',
                    unsafe_allow_html=True)

        for cat in shown:
            l1map = tree[cat]
            n_l1 = sum(1 for l1 in l1map if l1)
            n_l2 = sum(1 for m in l1map.values() for n in m if n != NO_L2)
            n_rec = sum(i["n"] for m in l1map.values() for i in m.values())
            n_lb = sum(lb_of.get((cat, l1), 0) for l1 in l1map)
            with st.expander(
                f"{cat or NO_CAT}\u3000·\u3000{n_l1} 个一级\u3000·\u3000{n_l2} 个二级\u3000·\u3000{n_rec + n_lb:,} 条记录",
                expanded=focus,
            ):
                blocks = []
                for l1, l2map in l1map.items():
                    lb = lb_of.get((cat, l1), 0)
                    bits = []
                    if l2map:
                        bits.append(f"{len(l2map)} 个二级")
                    if lb:
                        bits.append(f"分类界定 {lb} 条")
                    blocks.append(
                        f'<div class="l1row"><span class="t">{esc(l1) or NO_L1}</span>'
                        f'<span class="n">{"\u3000·\u3000".join(bits)}</span></div>'
                    )
                    table = l2_table(l2map)
                    if table:
                        blocks.append(table)
                    if lb and l2map:
                        blocks.append(
                            f'<div class="empty">另有 {lb} 条分类界定结果挂在这一级下'
                            "（只有结论、没有二级类别）</div>"
                        )
                st.markdown("".join(blocks), unsafe_allow_html=True)

    st.markdown(
        f'<p class="foot">统一口径：原始 {stats["rows"]:,} 行 = 目录 {stats["cat_rows"]:,} + '
        f'分类界定 {stats["lb_total"]:,} + 空行 {stats["empty_rows"]}；入库 5,322 行、切片 5,474 块\u3000|\u3000'
        f'{stats["pseudo_rows"]} 条目录行缺二级类别，{stats["no_cat"]} 条没有子目录归属<br>'
        "目录行的依据默认是《医疗器械分类目录》（2017年第104号公告），带调整公告的行以公告为准\u3000|\u3000"
        f'33 个目录值里 {stats["dirs_all"] - stats["cats"]} 个是空分组行（非医疗器械产品、药械组合产品等），'
        "08 / 15注输 两行是疑似重复的目录名，未删。</p>",
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main()
