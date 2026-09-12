# 个人知识助手
这是基于 LangGraph 编排的个人知识助手，三个引擎：长期记忆、本地知识库 RAG、MCP 外部工具，双界面。

## 功能
- 长期记忆
- 本地知识库 RAG（可检索增强生成）
- MCP 外部工具
- 双界面（REPL+网页）

# 启动
# 先设置环境变量再跑
pip install langgraph fastmcp openai chromadb fastapi uvicorn
python main.py
uvicorn server:app

## 技术栈
LangGraph / Chroma / FastMCP / FastAPI / React

# 演示脚本
## 开场（15 秒）
这是基于 LangGraph 编排的个人知识助手，三个引擎：长期记忆、本地知识库 RAG、MCP 外部工具，双界面。
今天重点看两件事：它怎么做到「不编造」，以及挂了怎么优雅兜底。

## 第一站：记忆
台词 + 操作：自我介绍「我叫小明」→ 退出重进 → 「我叫什么」→ 答出小明
长期记忆跨会话，存在 memory.json，外壳无关

## 第二站：工具
台词 + 操作：123+456=? → 579
MCP 六站调用链：发现→转换→模型决策→call_tool→回填→再推理

## 第三站：RAG + 拒答
台词 + 操作：小猫护理 → 有据回答；「如何写周报」→ 拒答句
有据才说 + 不编造边界

## 收尾（10 秒）
[翻车预案一句话：API 挂了兜底文案就是现场演示错误处理的机会]