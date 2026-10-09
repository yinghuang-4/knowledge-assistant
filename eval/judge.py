# -*- coding: utf-8 -*-
"""判据引擎：把 questions.jsonl 里 expected 的语义实现成可执行判定。

设计约定（来自 t32 / t33 / t34 课堂）：
  - must_include            : 列表内**全部**关键词都要出现在答案里（「且」语义）
  - must_include_any        : 列表内**至少一个**关键词出现（「或」语义）
  - need_boundary_statement : 答案必须声明边界（v1 用信号词近似）
  - refuse / allow_extra    : should_refuse 类；refuse 判是否拒答，allow_extra 判是否多嘴
  - golden_ids              : in_kb 类必需的知识块 id，供 recall@k 使用，**不参与本函数判定**

重要约定：无法自动判定的项，必须通过返回值的第三项 needs_manual_review 显式标出，
          绝不能假装判过——假装判了 = 悄悄给出错数字。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# 拒答信号词（v1 近似判据）
REFUSAL_SIGNALS = ["没有", "未找到", "无法回答", "不知道", "不在", "未收录", "拒绝"]
# 边界声明信号词（v1 近似判据）
BOUNDARY_SIGNALS = ["资料", "知识库", "未提及", "没有提到", "建议", "需结合", "咨询", "不能确定"]

def normalize(text):
    """规范化：供所有关键词匹配使用（去 Markdown 标记、换行折成空格）"""
    text = text.replace("*", "")
    text = text.replace("`", "").replace("_", "")
    text = text.replace("\n", " ")
    return text.strip()

def is_refusal(answer, row=None):
    if not any(s in answer for s in REFUSAL_SIGNALS):
        return False
    if row:
        exp = row.get("expected", {})
        keys = list(exp.get("must_include", [])) + list(exp.get("must_include_any", []))
        if keys and any(k in answer for k in keys):
            return False          # 已给出实质内容 → 不是整题拒答
    return True

def has_boundary_statement(answer):
    """TODO(你)：判断答案是否声明了资料/判断边界。
    提示：命中任一 BOUNDARY_SIGNALS 即认为声明了。返回 bool。"""
    for s in BOUNDARY_SIGNALS:
        if s in answer:
            return True
    return False

def _hit_detail(name, words, answer):
    """生成 'must_include 1/2 命中：15；未命中：超时' 这样的明细"""
    hit = [w for w in words if w in answer]
    miss = [w for w in words if w not in answer]
    s = "%s %d/%d 命中" % (name, len(hit), len(words))
    if hit:
        s += "：" + "、".join(hit)
    if miss:
        s += "；未命中：" + "、".join(miss)
    return s

def judge(row, answer):
    answer = normalize(answer)
    """按 row['expected'] 判定一条答案。

    返回三元组 (passed: bool, detail: str, needs_manual_review: bool)

      - type == "should_refuse"：refuse 为真才算通过；
        **allow_extra=false（是否多嘴）无法自动判定 -> needs_manual_review 置 True**，
        并在 detail 里写明"refuse 已判，多嘴与否待人工复核"
      - 其余类型：must_include 全部命中 且 must_include_any 至少一个命中
        且 （若 need_boundary_statement）已声明边界

    detail 必须写清**哪一项命中、哪一项没命中**（t36 诊断失败题要靠它）。
    """
    exp = row.get("expected", {})
    t = row.get("type")

    if t == "should_refuse":
        # TODO(你)：实现 refuse 判定 + 把 allow_extra 标为待人工复核
        passed = is_refusal(answer,row)
        needs_manual_review = not exp.get("allow_extra", True)
        if needs_manual_review:
            detail = "refuse 判定：%s；是否多嘴（allow_extra=false）自动判不了，待人工复核" % passed
        else:
            detail = "refuse 判定：%s" % passed
        return passed, detail, needs_manual_review

    # TODO(你)：实现 must_include（且）/ must_include_any（或）/ need_boundary_statement
    #          注意空列表的语义：must_include 为空表示"没有必须逐字出现的词"，
    #          此时不要判它失败
    else:
        mi = exp.get("must_include", [])
        ma = exp.get("must_include_any", [])
        bd = exp.get("need_boundary_statement", False)
        parts = []
        if mi:
            parts.append(_hit_detail("must_include", mi, answer))
        if ma:
            parts.append(_hit_detail("must_include_any", ma, answer))
        if bd:
            parts.append("边界声明：" + ("有" if has_boundary_statement(answer) else "无"))
        needs_manual_review = False
        detail = "；".join(parts) or "无判据"
        passed = all(w in answer for w in mi) and (not ma or any(w in answer for w in ma)) \
         and (not bd or has_boundary_statement(answer))
    return passed, detail, needs_manual_review


def load_rows(path=None):
    """读 questions.jsonl，返回 dict 列表。"""
    path = path or os.path.join(HERE, "questions.jsonl")
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


if __name__ == "__main__":
    rs = {r["id"]: r for r in load_rows()}
    print("载入", len(rs), "条题目")
    print("填完 TODO 后可手动试跑，例如：")
    print('  judge(rs["q001"], "建议把超时设为 15 秒")')
