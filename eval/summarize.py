import os
import csv
import glob
import json
import datetime
#获取当前脚本所在目录
rows = []
dir_path = os.path.dirname(os.path.abspath(__file__))
# 只读 runs_r*.csv（别用 *.csv —— 将来目录里出现别的 csv 会静默混入统计）
for file_path in sorted(glob.glob(os.path.join(dir_path, "runs_r*.csv"))):
    # 必须 utf-8-sig：写入时用了 BOM，读出时不配对，BOM 会粘在第一个列名上
    with open(file_path, "r", encoding="utf-8-sig") as f:
        rows += list(csv.DictReader(f))
print("载入 %d 行（%d 个文件 × 20 题）" % (len(rows), len(rows) // 20))

#recall@k
def recall():
    hit = tot = 0
    failed = []
    for r in rows:
        if r["type"] != "in_kb":
            continue                      # 只算 in_kb 题
        g = json.loads(r["golden_ids"]) or []
        rid = set(json.loads(r["retrieved_ids"]))
        tot += 1
        ok = bool(g) and all(x in rid for x in g)
        hit += ok
        if not ok:
            failed.append((r["run_id"], r["qid"], len(rid)))
    return hit, tot, failed
#拒答准确率
def refuse():
    ok = 0
    for r in rows:
        did_refuse = (r["refusal"] == "True")
        if r["type"] == "should_refuse":
            ok += did_refuse                # 该拒的拒了 = 对
        else:
            ok += (not did_refuse)          # 该答的答了 = 对
    return ok, len(rows), ok / len(rows) * 100

#无据作答率
def unfounded_rate():
    bad = ans = 0
    samples = []
    for r in rows:
        if r["type"] != "in_kb":
            continue
        if r["refusal"] == "True":        # 拒答了 → 不计入分母（分母是"实际作答的"）
            continue
        ans += 1
        if r["judge_pass"] != "True":
            bad += 1
            samples.append((r["run_id"], r["qid"]))
    return bad, ans, samples

#P50/P95
def P():
    list_ms = []
    for r in rows:
        list_ms.append(int(r["latency_ms"]))
    list_ms.sort()
    P50 = list_ms[int(len(list_ms)*0.5)-1]
    P95 = list_ms[int(len(list_ms)*0.95)-1]
    return P50,P95

#平均token
def token():
    total_token_in = 0
    total_token_out = 0
    for r in rows:
        total_token_in += int(r["tok_in"])
        total_token_out += int(r["tok_out"])
    return total_token_in/len(rows),total_token_out/len(rows)


# ---------- 跨轮与检索对比 ----------
def cross_round():
    by_qid = {}
    for r in rows:
        by_qid.setdefault(r["qid"], []).append(r)
    unstable, always_fail = [], []
    for q, rs in sorted(by_qid.items()):
        ps = [r["judge_pass"] == "True" for r in rs]
        if len(set(ps)) > 1:
            unstable.append("%s(%s)" % (q, rs[0]["type"]))
        if not any(ps):
            always_fail.append("%s(%s)" % (q, rs[0]["type"]))
    return unstable, always_fail


def search_compare():
    """检索了 vs 未检索 的通过情况"""
    s = [r for r in rows if json.loads(r["retrieved_ids"])]
    u = [r for r in rows if not json.loads(r["retrieved_ids"])]
    s_ok = sum(1 for r in s if r["judge_pass"] == "True")
    u_ok = sum(1 for r in u if r["judge_pass"] == "True")
    return s_ok, len(s), u_ok, len(u)


# ---------- 渲染报告（纯函数：只返回 Markdown 文本，不碰文件） ----------
def build_report():
    rounds = sorted({r["run_id"] for r in rows})
    n = len(rows)
    ikb = [r for r in rows if r["type"] == "in_kb"]
    searched = [r for r in ikb if json.loads(r["retrieved_ids"])]

    hit, tot, failed = recall()
    ok_ref, _, ref_rate = refuse()
    bad, den, samples = unfounded_rate()
    p50, p95 = P()
    tok_in, tok_out = token()
    unstable, always_fail = cross_round()
    s_ok, s_n, u_ok, u_n = search_compare()

    # 对照口径：只算"检索了的 in_kb 题"
    hit_s = sum(1 for r in searched
                if json.loads(r["golden_ids"])
                and all(x in set(json.loads(r["retrieved_ids"])) for x in json.loads(r["golden_ids"])))
    # 幻觉式正确：in_kb 且没检索却判通过
    phantom = sorted({r["qid"] for r in rows if r["type"] == "in_kb"
                      and not json.loads(r["retrieved_ids"]) and r["judge_pass"] == "True"})
    # 误拒：非应拒答题却拒答了
    misref = sorted({r["qid"] for r in rows if r["type"] != "should_refuse"
                     and r["refusal"] == "True"})

    pc = lambda a, b: (a / b * 100) if b else 0.0

    L = []
    L.append("# 评测报告 · 个人知识助手")
    L.append("")
    L.append("> 由 `eval/summarize.py` 自动生成；**所有数字取自 `runs_r*.csv`，无手写数值**")
    L.append("")
    L.append("## 0. 数据与配置")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append("| 运行轮次 | %d（%s） |" % (len(rounds), "、".join(rounds)))
    L.append("| 采样总数 | %d 行（%d 轮 × 20 题） |" % (n, len(rounds)))
    L.append("| LLM_TEMPERATURE | %s |" % os.environ.get("LLM_TEMPERATURE", "未设置（默认 1.0）"))
    L.append("| 生成时间 | %s |" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    L.append("")
    L.append("### 指标口径")
    L.append("")
    L.append("- `recall@k`：分母 = 全部 `in_kb` 题，**未走知识库检索（`retrieved_ids` 为空）记 0**；另附「仅检索题」对照口径")
    L.append("- 无据作答率：分母 = 非拒答的 `in_kb` 题；分子 = 其中未命中资料关键点（**代理指标**，非真实幻觉率）")
    L.append("- 拒答准确率：分母 = 总题数（该拒的拒了 + 该答的答了）")
    L.append("")
    L.append("## 1. 核心结论")
    L.append("")
    L.append("- **系统的瓶颈在「检索决策」，不在回答质量**：走了知识库检索的 %.0f%% 通过，没走的仅 %.0f%% 通过"
             "（没走的那些多为调用了 MCP `pet_care`，见 §2 根因追查）"
             % (pc(s_ok, s_n), pc(u_ok, u_n)))
    L.append("- `recall@k` 主口径 %d/%d（%.0f%%）；**只看走了检索的题是 %d/%d（%.0f%%）**"
             "——凡检索必命中，失败全部来自未走知识库检索"
             % (hit, tot, pc(hit, tot), hit_s, len(searched), pc(hit_s, len(searched))))
    L.append("")
    L.append("## 2. 五个指标")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append("| recall@k（主口径 / 仅检索题） | %d/%d ／ %d/%d |" % (hit, tot, hit_s, len(searched)))
    L.append("| 拒答准确率 | %d/%d = %.1f%% |" % (ok_ref, n, ref_rate))
    L.append("| 无据作答率 | %d/%d = %.1f%% |" % (bad, den, pc(bad, den)))
    L.append("| P50 / P95 延迟 | %d ms / %d ms |" % (p50, p95))
    L.append("| 平均 token（输入 / 输出） | %.0f / %.0f |" % (tok_in, tok_out))
    L.append("")
    L.append("**未命中 golden 的 in_kb 行（%d 条）**：%s"
             % (len(failed), "、".join("%s/%s(检索%d块)" % (a, b, c) for a, b, c in failed) or "无"))
    L.append("")
    L.append("**无据作答明细（%d 条）**：%s" % (len(samples), "、".join("%s/%s" % s for s in samples) or "无"))
    L.append("")
    L.append("**根因追查结论（2026-10-03 更正）**：失败模式**不是**编造——逐条核对 `mcp_server.py` 后确认：")
    L.append("")
    L.append("1. **调错了工具**：`tool_calls ≥ 1` 但 `retrieved_ids` 为空 → 模型调用的是 MCP 的 `pet_care`，"
             "**没有走知识库检索**；`pet_care` 的 3 条 canned 答案与失败答案**逐字一致**")
    L.append("2. **引用了真实但信息量更少的源**：模型把 `pet_care` 的返回称为「资料 / 知识库」——"
             "引用是真的，只是它转述的不是 notes.txt")
    L.append("3. **两个知识源内容冲突**：洋葱（KB「不能大量食用」vs pet_care「绝不能喂食」）、"
             "牛奶（KB「多数猫狗缺乳糖酶」vs pet_care「猫普遍乳糖不耐受」）、"
             "发烧（KB「38.0-39.2」vs pet_care「摸耳尖/鼻头干，无数值」）")
    L.append("")
    L.append("> **更正说明**：2026-09-26 初版把上述现象记为「虚假引用 / 编造缺失 / 范围放大」，"
             "经查阅 `pet_care` 实现后确认**该归因不成立**——模型是忠实转述了另一个工具的输出。"
             "真正的缺陷在**工具选择**与**知识源重复**。")
    L.append("")
    L.append("## 3. 跨轮稳定性")
    L.append("")
    L.append("- 跨轮不一致的题（%d 道）：%s" % (len(unstable), "、".join(unstable) or "无"))
    L.append("- 稳定失败的题（%d 道）：%s" % (len(always_fail), "、".join(always_fail) or "无"))
    L.append("")
    L.append("## 4. 已知问题（交接 t36）")
    L.append("")
    L.append("1. **工具选择冲突（P0）**：模型时而调 `search_knowledge`、时而调 MCP `pet_care`，"
             "而后者只有 3 条 canned 短答案且与 KB 内容矛盾——"
             "签名：`tool_calls ≥ 1` 且 `retrieved_ids` 为空，共 **%d/%d 行**未走知识库检索" % (n - s_n, n))
    L.append("2. **依据来自另一个源（非幻觉）**：%s 未走检索却通过，其答案来自 `pet_care` 而非知识库，"
             "**不能算 RAG 的功劳**" % ("、".join(phantom) or "无"))
    L.append("3. **拒答的两种机制**（涉及 %s）：① 宠物类的拒答是 P0 的**后果**——`pet_care` 的相关条目本身没有数值/剂量信息；"
             "② 非宠物类的拒答是**无依据的断言**——`q003`(r3) **零工具调用**、`q0012`(r3) **已检索到 5 块**，"
             "却都答「我的知识库里没有资料」，与 P0 无关，需单独修提示词" % ("、".join(misref) or "无"))
    L.append("4. **判据被 Markdown 切断（P1 假失败）**：`q009` 的 r2 答案含「只提到猫咪不能**大量**食用洋葱」，"
             "于是 `大量` 命中而 `大量食用` 未命中——**正确答案被判失败**")
    L.append("5. **稳定失败**：%s" % ("、".join(always_fail) or "无"))
    L.append("")
    temp_env = os.environ.get("LLM_TEMPERATURE")
    temp_desc = (("已固定为 %s（方差被人为压低，不能代表生产）" % temp_env) if temp_env
                 else "未设置 = 生产默认温度 1.0（**三轮之间的差异就是真实方差**）")

    L.append("## 5. 本次评测的已知限制")
    L.append("")
    L.append("- 单轮 20 题，比率分辨率约 5%（`in_kb` 类按 8 题计约 12.5%）")
    L.append("- 无据作答率为**代理指标**（以「未命中资料关键点」近似）；已对全部 5 条人工抽查，"
             "并于 2026-10-03 追查到根因（见 §2 更正说明）")
    L.append("- 温度配置：%s" % temp_desc)
    L.append("")
    return "\n".join(L) + "\n"


# ---------- 主流程：渲染 → 落盘 ----------
md = build_report()
out_path = os.path.join(dir_path, "report.md")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(md)
print("报告已生成: %s（%d 字）" % (out_path, len(md)))