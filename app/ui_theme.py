# -*- coding: utf-8 -*-
"""
三个页面共用的样式与小工具（证据链侧栏 / 本体浏览 / 版本对比）。

只放「长得一样」的东西：页头、小节标题、卡片、徽章、表格、警示框。
页面自己的特殊组件（比如 hops 卡片）留在各自文件里。
"""

import html

THEME_CSS = """
<style>
html, body, [data-testid="stAppViewContainer"] { background: #f4f6f8; }
body, p, div, span, li, td, th, input, label,
[data-testid="stMarkdownContainer"] {
  font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
}
#MainMenu, header[data-testid="stHeader"], footer, [data-testid="stToolbar"] { display: none; }
.block-container { max-width: 1180px; padding: 26px 20px 44px; }

/* ---------- 页头 ---------- */
.hero {
  background: linear-gradient(135deg, #1f364d 0%, #2d5175 100%);
  border-radius: 14px; padding: 22px 26px; margin-bottom: 22px;
  box-shadow: 0 2px 10px rgba(31,54,77,.14);
}
.hero .kicker { font-size: 11.5px; letter-spacing: 1.2px; color: #a3bcd4 !important; }
.hero .hero-title {
  font-size: 23px; font-weight: 600; margin: 7px 0 6px; letter-spacing: .5px;
  color: #ffffff !important; line-height: 1.35;
}
.hero .sub { font-size: 13px; color: #cbdaea !important; line-height: 1.6; }

/* ---------- 小节标题 ---------- */
.sec-label {
  font-size: 12.5px; font-weight: 600; color: #8a9199 !important;
  letter-spacing: .8px; margin: 0 0 7px;
}
.sec-label.mt { margin-top: 20px; }

/* ---------- 数字卡片 ---------- */
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }
.card { background: #fff; border: 1px solid #e5e8ec; border-radius: 10px; padding: 14px 16px; }
.card .num { font-size: 24px; font-weight: 700; color: #17324a !important; letter-spacing: -.3px; line-height: 1.2; }
.card .lbl { font-size: 12px; color: #8a9199 !important; margin-top: 3px; }
.card .sub { font-size: 11.5px; color: #9aa1a9 !important; margin-top: 6px; }
.card.up .num { color: #15803d !important; }
.card.warn .num { color: #c2410c !important; }

/* ---------- 白卡片 ---------- */
.panel { background: #fff; border: 1px solid #e5e8ec; border-radius: 10px; padding: 16px 18px; }
.panel + .panel { margin-top: 12px; }

/* ---------- 徽章 ---------- */
.badge {
  display: inline-block; font-size: 11px; font-weight: 600; line-height: 1;
  padding: 4px 8px; border-radius: 999px; letter-spacing: .3px; white-space: nowrap;
}
.badge-clause { background: #eaf2fb; color: #1d4f86 !important; }
.badge-rule   { background: #eeeafc; color: #5533a4 !important; }
.badge-neg    { background: #fdf0e3; color: #a35a09 !important; }
.badge-other  { background: #eef1f4; color: #52606d !important; }
.badge-add    { background: #e8f6ec; color: #15803d !important; }
.badge-mod    { background: #fff4e5; color: #b45309 !important; }
.badge-del    { background: #fdeceb; color: #b91c1c !important; }
.mono { font-family: Consolas, "Courier New", monospace; }
.muted { color: #9aa1a9 !important; font-size: 12px; }

/* ---------- 表格 ---------- */
table.alt { width: 100%; border-collapse: collapse; font-size: 12.5px;
            background: #fff; border: 1px solid #e5e8ec; border-radius: 10px; overflow: hidden; }
table.alt th { text-align: left; font-weight: 600; font-size: 11.5px; color: #8a9199 !important;
               background: #f7f9fb; padding: 7px 10px; border-bottom: 1px solid #e5e8ec; white-space: nowrap; }
table.alt td { padding: 7px 10px; border-bottom: 1px solid #f0f2f4; color: #3f4854 !important; vertical-align: top; }
table.alt tr:last-child td { border-bottom: none; }
table.alt td.num { text-align: right; font-variant-numeric: tabular-nums; color: #6b7280 !important; }
table.alt tr.add td { background: #f6fbf7; }
table.alt tr.mod td { background: #fffcf5; }

/* ---------- 警示 / 引用 / 脚注 ---------- */
.warn {
  background: #fff7ed; border: 1px solid #fbd9ae; border-left: 4px solid #f59e0b;
  border-radius: 10px; padding: 12px 14px; font-size: 12.5px; line-height: 1.7; color: #92400e !important;
  margin: 14px 0 0;
}
.warn .h { font-weight: 600; color: #b45309 !important; display: block; margin-bottom: 3px;
           font-size: 12px; letter-spacing: .5px; }
.cites { font-size: 11.5px; color: #9aa1a9 !important; line-height: 1.95; margin-top: 14px; }
.cites b { color: #6b7280 !important; font-weight: 600; }
.foot { text-align: center; font-size: 11.5px; color: #9aa1a9 !important; margin-top: 24px; line-height: 1.8; }

/* ---------- Streamlit 原生 expander 改造 ---------- */
[data-testid="stExpander"] {
  border: 1px solid #e5e8ec !important; border-radius: 10px !important;
  background: #fff; margin-bottom: 8px; overflow: hidden;
}
[data-testid="stExpander"] summary { padding: 9px 14px !important; }
[data-testid="stExpander"] summary p {
  font-size: 13px !important; font-weight: 500; color: #33404f !important; line-height: 1.55;
}
[data-testid="stExpander"] summary:hover { background: #f7f9fb; }
[data-testid="stExpander"] [data-testid="stExpanderDetails"] { padding: 2px 14px 12px !important; }
</style>
"""


# 证据链侧栏那页专有的组件（问答卡、跳数卡），别的页面用不到
EVIDENCE_CSS = """
<style>
.q-card {
  background: #fff; border: 1px solid #e5e8ec; border-left: 3px solid #9fb3c8;
  border-radius: 10px; padding: 15px 18px; font-size: 17px; line-height: 1.6;
  color: #1f2329 !important; margin-bottom: 22px;
}
.a-card { background: #fff; border: 1px solid #e5e8ec; border-radius: 10px; padding: 18px 20px 16px; }
.a-lead {
  font-size: 18px; font-weight: 600; color: #17324a !important; line-height: 1.6;
  border-left: 4px solid #2d5175; padding-left: 12px; margin-bottom: 18px;
}
.a-sub { font-size: 12px; font-weight: 600; color: #8a9199 !important; letter-spacing: .8px; margin: 0 0 8px; }
ul.a-list { margin: 0 0 2px 4px; padding: 0; list-style: none; }
ul.a-list li { margin-bottom: 13px; padding-left: 14px; position: relative; }
ul.a-list li:before {
  content: ""; position: absolute; left: 0; top: 9px;
  width: 5px; height: 5px; border-radius: 50%; background: #b6c4d2;
}
ul.a-list .src { font-size: 11.5px; color: #8a9199 !important; line-height: 1.6; margin-bottom: 2px; }
ul.a-list .txt { font-size: 13px; color: #3f4854 !important; line-height: 1.75; }

.side-head { display: flex; align-items: baseline; justify-content: space-between; margin: 0 0 10px; }
.side-head .t { font-size: 15px; font-weight: 600; color: #17324a !important; }
.side-head .n { font-size: 12px; color: #8a9199 !important; }
.concl {
  background: #fff; border: 1px solid #e5e8ec; border-radius: 10px;
  padding: 14px 16px; margin-bottom: 14px;
}
.concl .lbl { font-size: 11.5px; font-weight: 600; color: #8a9199 !important; letter-spacing: .8px; margin-bottom: 5px; }
.concl .val { font-size: 14.5px; line-height: 1.65; color: #17324a !important; font-weight: 600; }

.hop-meta { display: flex; align-items: center; gap: 8px; margin: 2px 0 10px; }
.conf { font-size: 11.5px; color: #6b7280 !important; }
.ev-label { font-size: 11px; font-weight: 600; color: #9aa1a9 !important; letter-spacing: .8px; margin: 9px 0 3px; }
.ev-ref { font-size: 12.5px; color: #1f364d !important; line-height: 1.6; }
.ev-quote {
  font-size: 12.5px; line-height: 1.75; color: #3f4854 !important;
  background: #f7f9fb; border-left: 3px solid #cbd6e2; border-radius: 0 6px 6px 0;
  padding: 9px 12px;
}
</style>
"""


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=False)


def hero(kicker: str, title: str, sub: str) -> str:
    return (
        '<div class="hero">'
        f'<div class="kicker">{esc(kicker)}</div>'
        f'<div class="hero-title">{title}</div>'
        f'<div class="sub">{esc(sub)}</div>'
        "</div>"
    )


def cards(items) -> str:
    """items: [(数字, 说明, 附加说明 or '', 样式 or '')]"""
    out = []
    for item in items:
        num, label = item[0], item[1]
        sub = item[2] if len(item) > 2 else ""
        cls = item[3] if len(item) > 3 else ""
        out.append(
            f'<div class="card {cls}"><div class="num">{num}</div>'
            f'<div class="lbl">{esc(label)}</div>'
            + (f'<div class="sub">{esc(sub)}</div>' if sub else "")
            + "</div>"
        )
    return f'<div class="cards">{"".join(out)}</div>'
