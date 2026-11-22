---
name: evidence-chain-build
description: |
  产出结构化的逐跳证据链，每一跳都带出处，用于界面侧栏展示与人工复核。
  当用户问「依据是什么」、或系统需要给出可核验的推理过程时使用。
allowed-tools:
  - evidence_chain
  - get_clause
tags:
  - medical-device
  - traceability
  - composite
---

# 证据链构建

## 什么时候用

需要把一次性回答展开成「可被逐条核验的推理过程」时。这是本项目的核心交付物之一。

## 结构

```json
{
  "question": "含银离子的创面敷料属于几类",
  "结论": "Ⅲ类，注册，国家药监局受理",
  "hops": [
    {"step": 1, "from": "用户描述", "to": "记录 2270 · 13含银敷料",
     "evidence": {"type": "clause", "ref": "《医疗器械分类目录》14注输、护理和防护器械"}},
    {"step": 2, "from": "记录 2270", "to": "管理类别 Ⅲ",
     "evidence": {"type": "clause", "ref": "同上"}},
    {"step": 3, "from": "管理类别 Ⅲ", "to": "注册路径 注册 / 国家药监局",
     "evidence": {"type": "rule", "ref": "class_rules[Ⅲ]"}}
  ]
}
```

## 铁律

**没有 evidence 的跳，删掉。** 宁可三跳，不要四跳里有一跳是编的。

## evidence 的四种类型

| 类型 | 含义 | 例 |
|---|---|---|
| clause | 引用某条款原文 | 记录 2270 的分类依据 |
| rule | 命中判定规则 | class_rules[Ⅲ] |
| not_in | 阴性证据 | 不在《免于临床评价目录》内 |
| human | 人工判定 | 人工审核修正 |

阴性证据容易被忽略，但很重要：「查了没有」本身就是一种证据。

## 交付前自查

1. 每一跳的 ref 是否真的存在
2. 从 from 到 to 是不是真的能推出来
3. 结论里的每个断言，能不能在 hops 里找到对应的一跳
