# -*- coding: utf-8 -*-
"""用当前 judge 重新判定历史 runs —— 不重新调用模型"""
import csv, glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from judge import judge, is_refusal, load_rows

QS = {q["id"]: q for q in load_rows()}          # qid -> 题目行（含 expected）

def rejudge(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    changed = []
    for r in rows:
        q = QS[r["qid"]]
        r["toolset"] = "all"
        old = r["judge_pass"]
        passed, detail, manual = judge(q, r["answer"])
        r["judge_pass"] = str(passed)
        r["judge_detail"] = detail
        r["needs_manual_review"] = str(manual)
        r["refusal"] = str(is_refusal(r["answer"], q))
        if str(passed) != old:
            changed.append((r["run_id"], r["qid"], old, str(passed)))
    return rows, changed

for p in sorted(glob.glob(os.path.join(HERE, "runs_*.csv"))):
    rows, changed = rejudge(p)
    out = os.path.join(HERE, "rejudged_" + os.path.basename(p))     # ← 不覆盖原件
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
    print("%s → %s  判定变化 %d 处: %s" % (os.path.basename(p), os.path.basename(out), len(changed), changed))