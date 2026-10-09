# -*- coding: utf-8 -*-
"""questions.jsonl 红测：逐行解析 + 结构校验 + 类型配额检查

用法（在 作品/知识助手 目录下）：
    D:\\python\\python.exe eval\\check_questions.py

校验项：
  1. 每行必须是合法 JSON（能 json.loads）
  2. 必须有 id / type / question / expected / note 五个字段
  3. type 只能是 in_kb / should_refuse / boundary
  4. expected 必须是对象（dict）——写成字符串就说明它是"答案文本"而非"可判定判据"
  5. id 不能重复
  6. 报告类型分布，对照目标配额 in_kb 8 / should_refuse 8 / boundary 4

退出码：0 = 全绿且满 40 条；1 = 有问题（交给 CI 就能当门禁用）
"""
import json
import os
import sys
from collections import Counter

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "questions.jsonl")
REQUIRED = ("id", "type", "question", "expected", "note")
TYPES = ("in_kb", "should_refuse", "boundary")
QUOTA = {"in_kb": 8, "should_refuse": 8, "boundary": 4}
TOTAL = sum(QUOTA.values())


def main():
    if not os.path.exists(PATH):
        print("找不到文件:", PATH)
        return 1

    ok = bad = 0
    types = Counter()
    seen = {}

    with open(PATH, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception as e:
                print("第 %d 行 JSON 非法 -> %s: %s" % (i, type(e).__name__, e))
                bad += 1
                continue
            if not isinstance(d, dict):
                print("第 %d 行不是对象" % i)
                bad += 1
                continue
            miss = [k for k in REQUIRED if k not in d]
            if miss:
                print("第 %d 行缺字段 %s" % (i, miss))
                bad += 1
                continue
            if d["type"] not in TYPES:
                print("第 %d 行 type 非法: %r" % (i, d["type"]))
                bad += 1
                continue
            if not isinstance(d["expected"], dict):
                print("第 %d 行 expected 不是对象（%s）——按知识点 1，expected 必须是可判定判据"
                      % (i, type(d["expected"]).__name__))
                bad += 1
                continue
            gids = d.get('golden_ids')
            if d['type'] == 'in_kb' and not (isinstance(gids, list) and gids
                                             and all(isinstance(x, str) for x in gids)):
                print('第 %d 行 in_kb 的 golden_ids 必须是非空字符串数组（形如 ["0"]）；当前 %r' % (i, gids))
                bad += 1
                continue
            if d["id"] in seen:
                print("第 %d 行 id 重复: %s（首见于第 %d 行）" % (i, d["id"], seen[d["id"]]))
                bad += 1
                continue
            seen[d["id"]] = i
            types[d["type"]] += 1
            ok += 1

    print("\n合法 %d 条 / 非法 %d 条（目标共 %d 条）" % (ok, bad, TOTAL))
    for t in TYPES:
        got, want = types.get(t, 0), QUOTA[t]
        flag = "OK " if got == want else "差"
        print("  %-14s %2d / %2d  %s" % (t, got, want, flag))
    if bad == 0 and ok != TOTAL:
        print("\n提示：条数未达 %d，继续写。" % TOTAL)
    return 0 if (bad == 0 and ok == TOTAL) else 1


if __name__ == "__main__":
    sys.exit(main())