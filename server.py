"""server.py：知识助手网页外壳（FastAPI + uvicorn）"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import main as core  # 核心逻辑都在 main.py

CFG = {"configurable": {"thread_id": "网页咨询1"}}  # 网页自己的会话门牌号（与 REPL 的「知识咨询1」隔离）

@asynccontextmanager
async def lifespan(app):
    # 启动时：连接 MCP Server、发现工具（和 run() 开头同款三件套）
    core.MCP_CLIENT = core.Client(core.SERVER_CONFIG)
    await core.MCP_CLIENT.__aenter__()
    client = core.MCP_CLIENT
    tools = await client.list_tools()
    core.OPENAI_TOOLS = core.build_tools_list(tools)
    # 预存 system 消息（和 run() 里 r1 同款）
    await core.graph.ainvoke(
        {"messages": [{"role": "system", "content": core.SYSTEM_PROMPT}]}, config=CFG)
    yield
    # 关闭时：断开 MCP 连接
    await core.MCP_CLIENT.__aexit__(None, None, None)

app = FastAPI(lifespan=lifespan)

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat_api(req: ChatRequest):
    reply = await core.chat(req.message, CFG)
    return {"reply": reply}

@app.get("/")
async def home():
    return FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"))