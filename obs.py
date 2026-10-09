# -*- coding: utf-8 -*-
"""可观测性钩子（默认关闭 = 零开销）

为什么单独一个模块：
  - 产品运行时**不开启**：record_* 立即返回，不产生任何记录、不改行为
  - 评测 / 调试时：runner 调 enable(True)，之后 record_* 把数据累积到"当前一轮"缓冲，
    runner 每题开始前 reset()、跑完取 snapshot()
  - 这样 main.py 里只多两行调用，评测脚手架不会长在产品代码里

命名说明：故意不叫 trace.py —— 那会遮蔽 Python 标准库的 trace 模块。
"""
_ENABLED = False

_current = {
    "retrieval": {"ids": [], "texts": []},   # 检索层：一题可能多轮，故为列表
    "usage": {"in": 0, "out": 0},            # 性能层：一题内累加
    "tool_calls": 0,                         # 工具调用次数（t32 的 D 类指标）
}


def enable(flag=True):
    """打开/关闭钩子。默认关闭。"""
    global _ENABLED
    _ENABLED = flag
    return _ENABLED


def reset():
    """每题开始前调用：清空当前轮缓冲。**即使未开启也清空**，避免残留。"""
    _current["retrieval"] = {"ids": [], "texts": []}
    _current["usage"] = {"in": 0, "out": 0}
    _current["tool_calls"] = 0


def record_retrieval(ids, texts):
    """记录一次检索结果。ids/texts 都是列表（n_results 条）。追加而非覆盖。"""
    if not _ENABLED:
        return
    _current["retrieval"]["ids"].extend(ids or [])
    _current["retrieval"]["texts"].extend(texts or [])


def record_usage(prompt_tokens, completion_tokens):
    """记录一次模型调用的 token 用量。累加。"""
    if not _ENABLED:
        return
    _current["usage"]["in"] += int(prompt_tokens or 0)
    _current["usage"]["out"] += int(completion_tokens or 0)


def record_tool_call(n=1):
    """记录工具调用次数。"""
    if not _ENABLED:
        return
    _current["tool_calls"] += int(n)


def snapshot():
    """取走当前轮缓冲（返回副本，避免被后续修改）。"""
    return {
        "retrieval": {"ids": list(_current["retrieval"]["ids"]),
                      "texts": list(_current["retrieval"]["texts"])},
        "usage": dict(_current["usage"]),
        "tool_calls": _current["tool_calls"],
    }
