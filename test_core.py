"""test_core.py：第一层纯函数测试 —— router"""
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from main import router
import pytest

# 造一条「带工具调用」的 AI 消息：tool_calls 里 name/args/id 三件套
@pytest.fixture
def tool_call_ai():
    def _make(call_id="call_1"):
        return AIMessage(content="", tool_calls=[{
            "name": "add",
            "args": {"a": 1, "b": 2},
            "id": call_id,
        }])
    return _make

def _seq_normal(mk):
    return [HumanMessage(content="你好"), AIMessage(content="你好")]

def _seq_tools(mk):
    return [HumanMessage(content="帮我算 1+2"), mk()]

def _seq_rounds4(mk):
    msgs = [HumanMessage(content="帮我算 1+2")]
    msgs += [ToolMessage(content="结果", tool_call_id=f"call_{i}") for i in range(4)]
    msgs.append(mk())
    return msgs

def _seq_history(mk):
    msgs = [HumanMessage(content="第一轮")]
    msgs += [ToolMessage(content="旧结果", tool_call_id=f"old_{i}") for i in range(4)]
    msgs += [HumanMessage(content="第二轮新问题"), mk()]
    return msgs


@pytest.mark.parametrize("build,expected", [
    pytest.param(_seq_normal,  "end",   id="正常结束"),
    pytest.param(_seq_tools,   "tools", id="有工具调用→走工具"),
    pytest.param(_seq_rounds4, "end",   id="超过阈值→强制收工"),
    pytest.param(_seq_history, "tools", id="历史不计入本轮"),
])
def test_router(tool_call_ai, build, expected):
    assert router({"messages": build(tool_call_ai)}) == expected

