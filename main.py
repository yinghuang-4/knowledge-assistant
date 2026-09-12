import asyncio
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver        # ← 新
from langchain_core.messages.utils import convert_to_openai_messages  # ← 新
from fastmcp import Client
from openai import OpenAI
import chromadb
import os
import json
import datetime
import sys
MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")

embed_client = OpenAI(api_key=os.environ.get('ZHIPU_API_KEY'),base_url="https://open.bigmodel.cn/api/paas/v4")

#添加长期记忆函数
def save_memory(content):
    #文件不存在时为空列表
    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w",encoding="utf-8") as f:
            json.dump([], f,ensure_ascii=False,indent=2)
    #读取旧记忆
    with open(MEMORY_FILE, "r",encoding="utf-8") as f:
        memory = json.load(f)
    #添加新记忆
    memory.append({
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "content": content,
    })
    with open(MEMORY_FILE, "w",encoding="utf-8") as f:
        json.dump(memory, f,ensure_ascii=False,indent=2)
    return "已记住"+content

#读取长期记忆函数
def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return "未找到记忆文件"
    with open(MEMORY_FILE, "r",encoding="utf-8") as f:
        memory = json.load(f)
        if not memory:  # ← 添加
            return "暂无长期记忆"
    return "\n".join([f"{item['time']}：{item['content']}" for item in memory])

#裁剪函数
def trim_history(messages,keep_num=10):
    system = [m for m in messages if m.type == "system"]
    rest = [m for m in messages if m.type != "system"]
    window = rest[-keep_num:]
    while window and window[0].type == "tool":
        window=window[1:]
    return system + window
#检索函数
def embed(text):
    response = embed_client.embeddings.create(
        model="embedding-3",
        input=text
    )
    return response.data[0].embedding

def search_knowledge(query):
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    collection = chroma_client.get_or_create_collection(name="kb_notes")
    v = embed(query)
    results = collection.query(query_embeddings=[v], n_results=5)
    if not results["documents"][0]:  # ← 添加
        return "未找到相关资料"
    return "\n".join(results["documents"][0])

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
#设置空值提醒
if not DEEPSEEK_API_KEY:
    print("请设置 DEEPSEEK_API_KEY 环境变量")
    exit(1)
LLM = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# 用标准 mcpServers 格式配置 stdio：客户端配置的行业标准 JSON 结构
SERVER_CONFIG = {
    "mcpServers": {
        "学习助手": {
            "command": sys.executable,
            "args": [os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")],
        }
    }
}
SYSTEM_PROMPT = """
            你是个人知识助手，工具返回什么就基于什么说，返回之外一个字不说
            ，知识类问题和工具类问题都绝对禁止用自己的知识编造答案。
            知识类问题必须先调 search_knowledge 查资料；
            资料里没有相关信息时必须回答『这个问题我的知识库里没有资料，无法回答；
            工具类问题正常调用对应工具。当用户说出值得长期记住的信息（名字、偏好、重要结论）时，
            调用 save_memory 保存；回答涉及用户个人信息或偏好的问题前，先调用 load_memory 查记忆。
        """
MCP_CLIENT = None
OPENAI_TOOLS = []

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

async def llm_node(state):
    window = trim_history(state["messages"], keep_num=10)
    conv = convert_to_openai_messages(window)
    resp = LLM.chat.completions.create(
        model="deepseek-chat",
        messages=conv,
        tools=OPENAI_TOOLS)
    return {"messages": [resp.choices[0].message.model_dump()]}

async def tool_node(state):
    msg = state["messages"][-1]
    tool_msgs = []
    for call in msg.tool_calls:          
        args = call["args"] 
        if call["name"] == "search_knowledge":
            content = search_knowledge(call["args"]["query"])
        elif call["name"] == "save_memory":
            content = save_memory(call["args"]["content"])
        elif call["name"] == "load_memory":
            content = load_memory()
        else:           
            result = await MCP_CLIENT.call_tool(call["name"], args)   
            content = result.content[0].text if result.content else str(result)
        tool_msgs.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "content": content,
        })
    return {"messages": tool_msgs}

#工具路由加ReAct循环
def router(state) -> str:
    msgs = state["messages"]
    # 找最后一个用户消息的位置：LangChain 里用户消息的类型名是 "human"
    last_user = -1
    for i, m in enumerate(msgs):
        if m.type == "human":
            last_user = i
    # 防死循环：只数「本轮」（最后一个 user 消息之后）的 tool 往返
    tool_rounds = sum(1 for m in msgs[last_user + 1:] if m.type == "tool")
    if tool_rounds > 3:
        return "end"
    if msgs[-1].tool_calls:
        return "tools"
    return "end"

#langgraph结构图
builder = StateGraph(AgentState)
builder.add_node("llm", llm_node)
builder.add_node("tools", tool_node)
builder.add_edge(START, "llm")
builder.add_conditional_edges("llm", router, {"tools": "tools", "end": END})
builder.add_edge("tools", "llm")
graph = builder.compile(checkpointer=InMemorySaver())#存档

async def chat(msg, cfg):
    """核心服务函数：给一句用户消息，返回助手回复。外壳无关。"""
    #如果出现429类错误，请等待2秒后重试
    try:
        r = await graph.ainvoke({"messages": [{"role": "user", "content": msg}]}, config=cfg)
    except Exception as e:
        if "429" in str(e):  # ← 添加
            await asyncio.sleep(2)
            try:
                r = await graph.ainvoke({"messages": [{"role": "user", "content": msg}]}, config=cfg)
            except Exception as e2:
                return f"助手出了点状况：{e2}"
        else:
            return f"助手出了点状况：{e}"
    #react循环并行调用过程
    # for m in r["messages"]:
    #         calls = getattr(m, "tool_calls", None)
    #         if calls:
    #             for c in calls:
    #                 print(f"[行动] {c['name']}({c['args']})")
    #         if m.content:
    #             print(f"[观察] {m.content[:60]}")
    return r["messages"][-1].content     

def build_tools_list(mcp_tools):
    OPENAI_TOOLS = [{
                            "type": "function",
                            "function": {
                                "name": t.name,
                                "description": t.description,
                                "parameters": t.inputSchema,
                            },
                        }
                        for t in mcp_tools]   # ← 照抄 t18b
    OPENAI_TOOLS.append({
                "type": "function",
                "function": {
                    "name": "search_knowledge",
                    "description": "搜索本地知识库，返回与问题相关的资料片段",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "要检索的问题或关键词"}
                    },
                    "required": ["query"],
                    },
                },
            })
    OPENAI_TOOLS.append({
                "type": "function",
                "function": {
                    "name": "save_memory",
                    "description": "当用户说出值得长期记住的信息（名字、偏好、重要结论）时保存到长期记忆文件",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "要长期记住的信息"}
                    },
                    "required": ["content"],
                    }
                }
            })
    OPENAI_TOOLS.append({
                "type": "function",
                "function": {
                    "name": "load_memory",
                    "description": "加载记忆",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            })
    return OPENAI_TOOLS

async def run():
    global MCP_CLIENT, OPENAI_TOOLS
    async with Client(SERVER_CONFIG) as client:
        MCP_CLIENT = client
        mcp_tools = await client.list_tools()
        OPENAI_TOOLS = build_tools_list(mcp_tools)
        cfg = {"configurable": {"thread_id": "知识咨询1"}}   # ← 会话门牌号：同号连续追加，异号互不可见（InMemorySaver 存内存，非文件）
        try:
            r1 = await graph.ainvoke({"messages": [{"role": "system", "content": SYSTEM_PROMPT},]}, config=cfg)
        except Exception as e:
            print(f"助手出了点状况：{e}")
        while True:
            print("[输入]", end="")
            msg = input()
            if msg.strip() in ("退出", "exit", "quit"):
                break
            r2 = await chat(msg, cfg)  
            print("[输出]",r2) 
if __name__ == "__main__":
    asyncio.run(run())