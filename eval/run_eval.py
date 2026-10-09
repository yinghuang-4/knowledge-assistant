import asyncio
import csv
import json
import os
import sys
import time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                      # 让 import judge / obs 生效
sys.path.insert(0, os.path.dirname(HERE))     # 让 import main 生效（上级目录）
import main as core
import obs
from judge import judge, load_rows, is_refusal
from fastmcp import Client
core.MEMORY_FILE = os.path.join(HERE, "memory_eval.json")
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 20
RUN_ID = sys.argv[2] if len(sys.argv) > 2 else "r1"      # ← 新增
OUT = os.path.join(HERE, "runs_%s.csv" % RUN_ID)          # ← 文件名带 run_id
TOOLSET = os.environ.get("TOOLSET", "all")

COLS = ["run_id","toolset", "qid", "type", "question", "golden_ids", "retrieved_ids", "retrieved_texts",
        "answer", "refusal", "latency_ms", "tok_in", "tok_out", "tool_calls",
        "judge_pass", "judge_detail", "needs_manual_review", "ts"]
async def run_one(q):
    cfg = {"configurable": {"thread_id": "eval-%s-%s" % (RUN_ID, q["id"])}}
    obs.reset()                                     # 清空该题缓冲
    # 新 thread 必须先预存 system（照 server.py 的 lifespan）
    await core.graph.ainvoke({"messages": [{"role": "system", "content": core.SYSTEM_PROMPT}]}, config=cfg)
    t0 = time.perf_counter()
    answer = await core.chat(q["question"], cfg)
    ms = int((time.perf_counter() - t0) * 1000)
    snap = obs.snapshot()                           # 取该题的检索/token/工具次数
    passed, detail, manual = judge(q, answer)
    refusal = is_refusal(answer,q)                     # 复用判据引擎里的
    latency_ms = ms
    needs_manual = manual
    if answer.startswith("助手出了点状况"):
        detail = "[ERROR] " + detail
    return {
    "run_id": RUN_ID, "qid": q["id"], "type": q["type"], "question": q["question"],
    "golden_ids": json.dumps(q.get("golden_ids") or [], ensure_ascii=False),
    "retrieved_ids": json.dumps(snap["retrieval"]["ids"], ensure_ascii=False),
    "retrieved_texts": json.dumps(snap["retrieval"]["texts"], ensure_ascii=False),
    "answer": answer,
    "refusal": refusal,
    "latency_ms": latency_ms,
    "tok_in": snap["usage"]["in"], "tok_out": snap["usage"]["out"],
    "tool_calls": snap["tool_calls"],
    "toolset": TOOLSET,
    "judge_pass": passed,                  # ← judge 的第 1 个返回
    "judge_detail": detail,                # ← 第 2 个（哪项命中/未命中）
    "needs_manual_review": needs_manual,   # ← 第 3 个（allow_extra 判不了的标记）
    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
}
async def main():
    if os.path.exists(core.MEMORY_FILE):
        os.remove(core.MEMORY_FILE)
    obs.enable(True)
    async with Client(core.SERVER_CONFIG) as client:
        core.MCP_CLIENT = client
        mcp_tools = await client.list_tools()
        core.OPENAI_TOOLS = core.build_tools_list(mcp_tools) 
        if TOOLSET == "no_pet_care":       # ← 新增
            core.OPENAI_TOOLS = [t for t in core.OPENAI_TOOLS
                                 if t["function"]["name"] != "pet_care"]
        print("TOOLSET=%s → 暴露工具: %s" % (
            TOOLSET, [t["function"]["name"] for t in core.OPENAI_TOOLS]))
        rows = load_rows()
        with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
            for q in rows[:LIMIT]:
                rec = await run_one(q)
                w.writerow(rec)
                f.flush()                        # 边跑边落盘，中途崩了不丢已跑的
                print("%s pass=%s refusal=%s %sms" % (rec["qid"], rec["judge_pass"], rec["refusal"], rec["latency_ms"]))
        print("写出:", OUT)


if __name__ == "__main__":
    asyncio.run(main())