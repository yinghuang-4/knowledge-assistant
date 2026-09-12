"""test_core.py：第一层纯函数测试 —— router"""
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from main import router

# 造一条「带工具调用」的 AI 消息：tool_calls 里 name/args/id 三件套
def make_tool_call_ai():
    return AIMessage(content="", tool_calls=[{
        "name": "add",
        "args": {"a": 1, "b": 2},
        "id": "call_1",
    }])

def test_正常结束():
    msgs = [
        HumanMessage(content="你好"),
        AIMessage(content="你好"),
    ]
    assert router({"messages": msgs}) == "end"

def test_继续工具():
    msgs = [
        HumanMessage(content="帮我算 1+2"),
        make_tool_call_ai(),
    ]
    assert router({"messages": msgs}) == "tools"   # 空2

def test_防死循环():
    # 本轮已经往返 4 次（4 条 ToolMessage），模型还想继续调工具
    msgs = [HumanMessage(content="帮我算 1+2")]
    for i in range(4):
        msgs.append(ToolMessage(content="结果", tool_call_id=f"call_{i}"))
    msgs.append(make_tool_call_ai())
    assert router({"messages": msgs}) == "end"   # 空3

def test_历史不计入本轮():
    # 错题 5 的守护测试：历史里有 4 条 tool 消息，但最后一个 human 之后是干净的
    msgs = [HumanMessage(content="第一轮")]
    for i in range(4):
        msgs.append(ToolMessage(content="旧结果", tool_call_id=f"old_{i}"))
    msgs.append(HumanMessage(content="第二轮新问题"))
    msgs.append(make_tool_call_ai())
    assert router({"messages": msgs}) == "tools"   # 空4：旧代码（数全历史）会返回 "end"，修好后的代码应该返回？

if __name__ == "__main__":
    test_正常结束()
    test_继续工具()
    test_防死循环()
    test_历史不计入本轮()
    print("全部 PASS")