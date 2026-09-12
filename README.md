# 个人知识助手
这是基于 LangGraph 编排的个人知识助手，三个引擎：长期记忆、本地知识库 RAG、MCP 外部工具，双界面。

## 功能
- 长期记忆
- 本地知识库 RAG（可检索增强生成）
- MCP 外部工具
- 双界面（REPL+网页）

# 启动
## 先设置环境变量再跑
```bash
$env:DEEPSEEK_API_KEY="your_dskey_here"
$env:ZHIPU_API_KEY="your_zpkey_here"
pip install langgraph fastmcp openai chromadb fastapi uvicorn
python build_kb.py #仓库自带 chroma_db，如需重建才跑
python main.py     #|
uvicorn server:app #|——REPL 与网页任选其一
```

# 技术栈
LangGraph / Chroma / FastMCP / FastAPI / React

# 项目结构
```
知识助手/
├── main.py          # 核心逻辑：ReAct 图、工具定义、记忆、RAG、REPL 循环
├── server.py        # FastAPI 网页外壳（lifespan 连接 MCP、/chat 接口）
├── index.html       # 网页前端（React 单文件，无构建）
├── mcp_server.py    # 自建 MCP Server（add 计算 / pet_care 宠物护理，stdio）
├── notes.txt        # 知识库源文本（7 条，喂给 build_kb.py）
├── build_kb.py      # 知识库重建脚本：切块 → 向量化 → 写入 Chroma
├── chroma_db/       # 向量库（仓库自带，可随时用 build_kb.py 重建）
├── test_core.py     # router 防死循环四用例测试（python test_core.py）
├── Spec.md          # 项目设计文档：功能/架构/数据流/验收标准
└── README.md
#memory.json 为运行时生成（记忆数据），已排除出版本库
```

# 演示脚本
## 开场（15 秒）
这是基于 LangGraph 编排的个人知识助手，三个引擎：长期记忆、本地知识库 RAG、MCP 外部工具，双界面。
解决大模型知识滞后、只会聊不会做

## 第一站：记忆
台词 + 操作：自我介绍「我叫小明」→ 退出重进 → 「我叫什么」→ 答出小明
长期记忆跨会话，存在 memory.json，外壳无关

## 第二站：工具
台词 + 操作：123+456=? → 579
MCP 六站调用链：发现→转换→模型决策→call_tool→回填→再推理

## 第三站：RAG 
台词 + 操作：小猫护理 → 有据回答
小猫护理三条有据，点「主动声明资料边界」

## 第四站：拒答
台词 + 操作：如何写周报→拒答句+检索说明
知识库没有不编造，点「不编造边界」

## 第五站：长对话稳定
台词 + 操作：先说小明→连聊十句→再问「我叫什么」仍答出
点滑动窗口裁的是送进模型的上下文

## 高光站：
「今天天气怎么样」→ 模型主动澄清只能基于工具返回，点硬规则「工具返回之外一个字不说」

## 收尾（10 秒）
[翻车预案一句话：API 挂了兜底文案就是现场演示错误处理的机会]