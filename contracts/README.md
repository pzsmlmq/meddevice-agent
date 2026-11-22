# 数据契约 v1.0.0

> 冻结日期：2026-11-16
> 适用管线：`01_ingest → 02_clean → 03_extract → 05_merge → MCP → 前端`
> 校验器：`validate.py`

---

## 一、四份契约管什么

| 文件 | 管什么 | 谁产出 | 谁消费 |
|---|---|---|---|
| `product.schema.json` | 一条清洗后的产品记录 | 02_clean | 03_extract、评测集 |
| `ontology.schema.json` | 概念（节点）与关系（边） | 03_extract / 05_merge | MCP knowledge、本体浏览页 |
| `trace.schema.json` | 一次问答的推理路径 | reasoning MCP | 证据链侧栏、反馈回流 |
| `eval.schema.json` | 一条评测样本 | 人工出题 | 三轮对照评测 |

**顺序不能乱。** product 是地基，ontology 建在它上面，trace 是跑起来之后才有的，eval 贯穿全程。

---

## 二、三条铁律

**1. 每一跳必须有依据。**
`trace.hops[].evidence` 是必填。没有 evidence 的跳，从结果里删掉，不要留一个空 evidence 假装有。

**2. confidence 和 source_clause 从第一天就写。**
这两个字段事后补，等于把整条管线重做一遍。证据链完全由它们生成。

**3. 同一个 category_l2_id 不许跨 split。**
`validate.py eval` 会自动查。查出来就必须重新分层切分，不然准确率虚高二十个点，答辩一测就露。

---

## 三、字段速查

### product（产品记录）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `record_id` | string | 是 | `catalog-0001` 格式，不要用行号 |
| `source_table` | enum | 是 | catalog / definition / adjustment |
| `catalog` | string | 是 | 子目录，33 个 |
| `category_l1` | string/null | 否 | 一级类别，分类界定记录可能推不出 |
| `category_l2` | string | 是 | 二级类别，1164 个，判定的目标 |
| `product_desc` | string/null | 否 | 产品描述，LLM 抽属性的输入 |
| `intended_use` | string/null | 否 | 预期用途，决定管理类别 |
| `name_examples` | string[] | 否 | 品名举例，顿号拆成数组 |
| `class_level` | enum | 是 | **罗马数字** Ⅰ/Ⅱ/Ⅲ，不是 I/II/III |
| `class_level_raw` | string/null | 否 | 归一前原值，显示时给用户看这个 |
| `source_clause` | string/null | 否 | 法规出处，证据链的根 |
| `confidence` | number | 是 | 0~1，规则=1.0，LLM 按采样一致率 |
| `origin` | enum | 是 | rule / llm / human |
| `pending` | string[] | 否 | 待补字段清单，别用空字符串蒙 |

### ontology（本体）

| 字段 | 说明 |
|---|---|
| `concept.id` | 格式 `L2:超声诊断设备`，冒号前是类型代号 |
| `concept.ctype` | 9 种：SubCatalog / CategoryL1 / CategoryL2 / ProductExample / ClassLevel / RegPath / ClinicalEval / RegulationDoc / Clause |
| `concept.status` | active / pending_review / deprecated，废弃的保留下来做版本对比 |
| `relation.rel` | 8 种：belongs_to / has_class / determines / requires / based_on / cited_in / similar_to / instance_of |
| `relation.confidence` | **低于 0.5 的边不参与多跳推理** |

### trace（证据链）

| 字段 | 说明 |
|---|---|
| `hops[]` | 每一跳 `{step, from, to, evidence, confidence}` |
| `evidence.type` | clause（引原文）/ rule（命中规则）/ not_in（阴性证据）/ human（人工） |
| `evidence.text` | **直接抄原文，不许改写、不许摘要** |
| `confidence` | 各跳连乘，低于阈值要在 answer 里明说「需人工确认」 |
| `ontology_version` | 版本对比页靠它区分 v1 和 v2 |

### eval（评测）

| 字段 | 说明 |
|---|---|
| `question` | 像真人问的，不要写成「请判断以下产品的管理类别」 |
| `gold_class` | 只有 classification 类型要填，算 Macro-F1 用 |
| `evidence` | 没有出处的题不许进评测集 |
| `split` | train / test / feedback，三者互斥 |
| `difficulty` | easy / medium / hard，统计要分层报告 |

---

## 四、变更规则

契约一旦冻结，改字段要走这四步：

1. 在 `CHANGELOG.md` 写一条：改什么、为什么、影响哪些文件
2. 版本号 +1。加字段/加枚举值升次版本号（1.0.0 → 1.1.0）；删字段/改含义升主版本号（1.0.0 → 2.0.0）
3. 改完跑一遍 `python validate.py <类型> <数据文件>`，全过才算完
4. 同步更新本 README 的字段速查表

**不许做的事**：悄悄加字段、改字段含义但不改版本号、在代码里用 `dict.get()` 兜住缺字段来掩盖结构变了。

---

## 五、怎么用

```bash
# 校验产品记录（JSONL，每行一条）
py validate.py product  ../data/clean.jsonl

# 校验本体（会额外查重复节点和悬挂边）
py validate.py ontology ../ontology/ontology.json

# 校验评测集（会额外查跨 split 泄漏）
py validate.py eval     ../eval/questions.jsonl

# 校验器本身的健康检查，改了 schema 之后跑一遍
py validate.py selftest
```

退出码 0 = 全过，1 = 有失败。**放进管线最后一步**，跟 `python 05_merge.py && python ../contracts/validate.py ontology ...` 这样串起来。

---

## 六、为什么这么较真

这套东西真正的读者不是队友，是**三个月后的你**，和**你手里的 AI**。

AI 生成代码风格一次一个样。有 schema 兜着，它每次生成都得符合；没有，它每次自由发挥。

而且答辩时评委翻文档，看到有 schema、有校验脚本、有 CHANGELOG 的项目，和看到一堆脚本堆在一起，印象是两个物种。评分里「架构完整、分层清晰」那一条，就是这个东西。
