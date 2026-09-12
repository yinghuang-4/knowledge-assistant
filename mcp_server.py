# -*- coding: utf-8 -*-
"""11.ex-t16a.py 手写 MCP Server：用 FastMCP 定义两个工具"""
from fastmcp import FastMCP

mcp = FastMCP("我的学习助手")

@mcp.tool()
def add(a: int, b: int) -> int:
    """两个整数相加。"""
    return a + b

@mcp.tool()
def pet_care(topic: str) -> str:
    """查询宠物护理知识。topic 可传：牛奶、洋葱、发烧"""
    kb = {
        "牛奶": "猫咪普遍乳糖不耐受，喝牛奶容易腹泻，应喂宠物专用奶。",
        "洋葱": "洋葱对猫狗有毒，会引起溶血性贫血，绝不能喂食。",
        "发烧": "猫发烧可摸耳尖发热、鼻头干，持续发烧应立即就医。",
    }
    for key, val in kb.items():
        if key in topic:
            return val
    return f"知识库暂无「{topic}」相关内容。"

if __name__ == "__main__":
    mcp.run()  # 默认 stdio 传输：等待 Client 从标准输入发 JSON-RPC
