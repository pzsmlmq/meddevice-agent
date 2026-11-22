#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
契约校验器
==========

用法：

    # 校验一份 JSONL（每行一条记录）
    python validate.py product   data/clean.jsonl

    # 校验本体（整份 JSON）
    python validate.py ontology  ontology/ontology.json

    # 校验评测集（JSONL），同时检查训练/测试/反馈集有没有泄漏
    python validate.py eval      eval/questions.jsonl

    # 自检：跑一遍内置样例，确认校验器本身是好的
    python validate.py selftest

退出码：0 全过；1 有失败。放进 CI 或流水线最后一步。
"""

import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft7Validator
except ImportError:
    sys.exit("缺少依赖：pip install jsonschema")

HERE = Path(__file__).resolve().parent
SCHEMAS = {
    "product": HERE / "product.schema.json",
    "ontology": HERE / "ontology.schema.json",
    "trace": HERE / "trace.schema.json",
    "eval": HERE / "eval.schema.json",
}


def load_schema(name: str) -> dict:
    with open(SCHEMAS[name], encoding="utf-8-sig") as f:
        return json.load(f)


def iter_records(path: Path):
    """支持 .jsonl（每行一条）和 .json（数组或单对象）"""
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return
    if path.suffix == ".jsonl" or (not text.startswith(("{", "["))):
        for i, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield i, json.loads(line)
            except json.JSONDecodeError as e:
                yield i, e
        return
    obj = json.loads(text)
    if isinstance(obj, list):
        for i, item in enumerate(obj, 1):
            yield i, item
    else:
        yield 1, obj


def check_schema(name: str, path: Path) -> int:
    schema = load_schema(name)
    validator = Draft7Validator(schema)
    total = failed = 0

    for lineno, rec in iter_records(path):
        total += 1
        if isinstance(rec, Exception):
            failed += 1
            print(f"  [FAIL] 第 {lineno} 行 JSON 解析失败: {rec}")
            continue
        errors = sorted(validator.iter_errors(rec), key=lambda e: list(e.path))
        if errors:
            failed += 1
            print(f"  [FAIL] 第 {lineno} 行:")
            for e in errors:
                where = "/".join(str(x) for x in e.path) or "(根)"
                print(f"      {where}: {e.message}")

    print(f"\n{path.name}: {total - failed}/{total} 通过，{failed} 失败")
    return failed


def check_ontology(path: Path) -> int:
    """本体额外查两件事：悬挂边、重复节点"""
    failed = check_schema("ontology", path)
    with open(path, encoding="utf-8-sig") as f:
        obj = json.load(f)

    ids = [c["id"] for c in obj.get("concepts", [])]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        print(f"  [FAIL] 重复节点 {len(dup)} 个: {sorted(dup)[:5]}")
        failed += 1

    idset = set(ids)
    dangling = [
        r for r in obj.get("relations", [])
        if r.get("src") not in idset or r.get("dst") not in idset
    ]
    if dangling:
        print(f"  [FAIL] 悬挂边 {len(dangling)} 条（src/dst 找不到节点）:")
        for r in dangling[:5]:
            print(f"      {r.get('src')} -{r.get('rel')}-> {r.get('dst')}")
        failed += 1

    print(f"  节点 {len(ids)} 个，边 {len(obj.get('relations', []))} 条")
    return failed


def check_eval_leakage(path: Path) -> int:
    """评测集额外查：同一个 category_l2_id 是否跨 split"""
    split_map: dict[str, set] = {}
    for _, rec in iter_records(path):
        if isinstance(rec, Exception):
            continue
        cid = rec.get("category_l2_id")
        sp = rec.get("split")
        if cid and sp:
            split_map.setdefault(cid, set()).add(sp)

    leaked = {k: v for k, v in split_map.items() if len(v) > 1}
    if leaked:
        print(f"\n  [FAIL] 数据泄漏：{len(leaked)} 个二级类别同时出现在多个 split")
        for cid, splits in list(leaked.items())[:5]:
            print(f"      {cid} -> {sorted(splits)}")
        print("  [!] 这会让准确率虚高，必须重新分层切分")
        return len(leaked)
    print("  [OK] 无跨 split 泄漏")
    return 0


def selftest() -> int:
    """内置正反样例，确认 schema 和校验器都能正确拒绝坏数据"""
    schema = load_schema("product")
    v = Draft7Validator(schema)

    good = {
        "record_id": "catalog-0001",
        "source_table": "catalog",
        "catalog": "01有源手术器械",
        "category_l1": "手术器械-夹",
        "category_l2": "内窥镜用手术器械",
        "product_desc": "由钳头、套管和手柄组成。",
        "intended_use": "用于内镜下夹持组织。",
        "name_examples": ["内镜活检钳"],
        "class_level": "Ⅱ",
        "class_level_raw": "II",
        "source_clause": "2017年第104号公告-06-01",
        "source_doc": "2017年第104号公告",
        "confidence": 1.0,
        "origin": "rule",
        "pending": [],
    }

    bad_cases = {
        "管理类别用英文字母": {**good, "class_level": "II"},
        "record_id 格式不对": {**good, "record_id": "1"},
        "多了一个未定义字段": {**good, "备注": "随便加的"},
        "confidence 超出 0~1": {**good, "confidence": 1.5},
    }

    ok = True
    if v.is_valid(good):
        print("  [OK] 正样例通过")
    else:
        print("  [FAIL] 正样例竟然没通过，schema 有问题")
        ok = False

    for name, rec in bad_cases.items():
        if v.is_valid(rec):
            print(f"  [FAIL] 反样例「{name}」被放过了，schema 太松")
            ok = False
        else:
            print(f"  [OK] 反样例「{name}」被正确拒绝")

    return 0 if ok else 1


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    cmd = sys.argv[1]
    if cmd == "selftest":
        return selftest()

    if cmd not in SCHEMAS:
        print(f"未知类型：{cmd}，可选 {list(SCHEMAS)} 或 selftest")
        return 1

    if len(sys.argv) < 3:
        print(f"用法: python validate.py {cmd} <文件路径>")
        return 1

    path = Path(sys.argv[2])
    if not path.exists():
        print(f"文件不存在：{path}")
        return 1

    print(f"校验 {cmd}: {path}")
    if cmd == "ontology":
        failed = check_ontology(path)
    elif cmd == "eval":
        failed = check_schema("eval", path) + check_eval_leakage(path)
    else:
        failed = check_schema(cmd, path)

    if failed:
        print(f"\n结果：失败 {failed} 项")
        return 1
    print("\n结果：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
