# -*- coding: utf-8 -*-
"""11.ex-t16a.py 手写 MCP Server：用 FastMCP 定义两个工具"""
from fastmcp import FastMCP
import os

mcp = FastMCP("我的学习助手")

NOTES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes.txt")
@mcp.tool()
def add(a: int, b: int) -> int:
    """两个整数相加。"""
    return a + b

@mcp.tool()
def pet_care(topic: str) -> str:
    """查询宠物护理知识。topic 可传：牛奶、洋葱、发烧"""
    try:
        lines = [l.strip() for l in open(NOTES, encoding="utf-8") if l.strip()]
    except OSError as e:
        return "pet_care 读取知识库失败：%s" % e
    grams = {topic[i:i+2] for i in range(len(topic) - 1)} or ({topic} if topic else set())
    hits = [l for l in lines if any(g in l for g in grams)]
    if not hits:
        return "pet_care 未匹配到「%s」，请改用 search_knowledge 查询知识库。" % topic
    return "\n".join(hits)

if __name__ == "__main__":
    mcp.run()  # 默认 stdio 传输：等待 Client 从标准输入发 JSON-RPC
