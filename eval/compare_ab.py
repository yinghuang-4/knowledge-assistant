# -*- coding: utf-8 -*-
"""compare_ab.py —— t37 工具集对照实验的对比脚本（可复现 experiment_toolset.md 的全部数字）

用法： D:\\python3.12\\python.exe eval\\compare_ab.py
数据： runs_a1..a3.csv（A 组 no_pet_care） / runs_b1..b3.csv（B 组 all）
"""
import csv
import glob
import json
import math
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda r: r["judge_pass"] == "True"
G = lambda r: json.loads(r["golden_ids"]) or []
RID = lambda r: json.loads(r["retrieved_ids"])


def wilson(k, n, z=1.96):
    """通过率的 95% Wilson 置信区间（小样本比正态近似更可靠）"""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z / d * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, c - h), min(1.0, c + h)


def group(pats):
    files = []
    for pat in pats:
        files += sorted(glob.glob(os.path.join(HERE, pat)))
    return [(os.path.basename(p), list(csv.DictReader(open(p, encoding="utf-8-sig")))) for p in files]


def summary(files, label):
    rows = [r for _, rs in files for r in rs]
    n = len(rows)
    per = [sum(1 for r in rs if R(r)) / len(rs) * 100 for _, rs in files]
    ok = sum(1 for r in rows if R(r))
    searched = [r for r in rows if RID(r)]
    ikb = [r for r in rows if r["type"] == "in_kb"]
    hit = [r for r in ikb if G(r) and all(x in RID(r) for x in G(r))]
    s_ikb = [r for r in ikb if RID(r)]
    hit_s = [r for r in s_ikb if G(r) and all(x in RID(r) for x in G(r))]
    lat = sorted(int(r["latency_ms"]) for r in rows)
    lo, hi = wilson(ok, n)
    tok_in = sum(int(r["tok_in"]) for r in rows) / n
    print("=== %s（%d 行 / %d 轮）===" % (label, n, len(files)))
    print("  逐轮通过率     : %s" % " / ".join("%.0f%%" % p for p in per))
    print("  均值           : %.1f%%   极差 %.0f pt   标准差 %.1f" %
          (sum(per) / len(per), max(per) - min(per), statistics.pstdev(per)))
    print("  合计通过       : %d/%d = %.1f%%   95%%CI [%.1f%%, %.1f%%]" % (ok, n, ok / n * 100, lo * 100, hi * 100))
    print("  检索发生率     : %d/%d = %.1f%%" % (len(searched), n, len(searched) / n * 100))
    print("  recall@k 主口径: %d/%d = %.1f%%" % (len(hit), len(ikb), len(hit) / len(ikb) * 100))
    print("  recall@k 仅检索: %d/%d = %.1f%%" % (len(hit_s), len(s_ikb), len(hit_s) / len(s_ikb) * 100 if s_ikb else 0))
    print("  平均 token     : in %.0f / out %.0f" % (tok_in, sum(int(r["tok_out"]) for r in rows) / n))
    print("  P50 / P95 延迟 : %d / %d ms" % (lat[n // 2], lat[int(n * 0.95) - 1]))
    print("  出现过失败的题 : %s" % (sorted({r["qid"] for r in rows if not R(r)}) or "无"))
    print()
    return {"per": per, "mean": sum(per) / len(per), "range": max(per) - min(per),
            "rate": ok / n * 100, "ci": (lo * 100, hi * 100), "searched": len(searched) / n * 100,
            "recall": len(hit) / len(ikb) * 100, "recall_s": (len(hit_s) / len(s_ikb) * 100 if s_ikb else 0),
            "tok_in": tok_in, "p50": lat[n // 2], "p95": lat[int(n * 0.95) - 1],
            "fails": sorted({r["qid"] for r in rows if not R(r)})}


A = group(["runs_a*.csv"])
B = group(["runs_b*.csv", "rejudged_runs_r*.csv"])
print("A 组文件:", [n for n, _ in A])
print("B 组文件:", [n for n, _ in B])
print()
a = summary(A, "A 组 · no_pet_care")
b = summary(B, "B 组 · all")
print("=== 假设检验 ===")
print("  H1 通过率 : %.1f%% vs %.1f%%  → %s" % (a["mean"], b["mean"], "支持" if a["mean"] > b["mean"] else "不支持"))
print("  H2 方差   : 极差 %.0f pt vs %.0f pt → %s" % (a["range"], b["range"], "支持" if a["range"] < b["range"] else "不支持"))
print("  机制      : 检索发生率 %.1f%% vs %.1f%% → %s" %
      (a["searched"], b["searched"], "A 组更常查库" if a["searched"] > b["searched"] else "无差异"))
print("  置信区间  : A [%.1f, %.1f] vs B [%.1f, %.1f] → %s" %
      (a["ci"][0], a["ci"][1], b["ci"][0], b["ci"][1],
       "不重叠（差异可信）" if a["ci"][0] > b["ci"][1] else "重叠（差异不足以下结论）"))
print("  延迟代价  : P50 %d → %d ms (%+d)" % (b["p50"], a["p50"], a["p50"] - b["p50"]))
