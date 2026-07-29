"""
研究助手（SubAgent 版）
- 主 Agent（研究助手）：ReAct 循环，工具 = [delegate_research]
- 子 Agent（调研员）：ReAct 循环，工具 = [search]，被 delegate_research 调用
- 核心招式：把"派子 Agent"做成主 Agent 的一个工具，模型运行时决策是否调用
- 上下文隔离：子 Agent 用 SubState，主 Agent 用 MainState，messages 互不污染
"""
import os
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

# 模型（复用 ReAct demo 配置）
model = ChatOpenAI(
    model="glm-5.2",
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
)


# ===== ① 子 Agent：调研员（独立 ReAct 循环，有自己的工具和上下文）=====
@tool
def search(query: str) -> str:
    """搜索互联网获取信息。"""
    # mock：模糊匹配，确保子 Agent 搜一两次就能拿到足够信息（避免不收敛）
    if "GLM" in query:
        return ("GLM-5.2 是智谱AI 2025 年发布的大模型：支持 128K 上下文；"
                "代码与多轮推理能力强；长文档总结稳定；"
                "但超长上下文(>100K)检索略弱；多模态能力有限。")
    return f"（mock搜索）关于 '{query}'：暂无相关信息。"


SUB_TOOLS = [search]
SUB_TOOL_BY_NAME = {t.name: t for t in SUB_TOOLS}
sub_model = model.bind_tools(SUB_TOOLS)


class SubState(TypedDict):
    messages: Annotated[list, add_messages]


def sub_agent_node(state: SubState):
    reply = sub_model.invoke(state["messages"])
    calls = reply.tool_calls
    print(f"  [子] tool_calls={[c['name'] for c in calls] if calls else '无(最终回答)'}")
    return {"messages": [reply]}


def sub_tools_node(state: SubState):
    last = state["messages"][-1]
    results = []
    for tc in last.tool_calls:
        output = SUB_TOOL_BY_NAME[tc["name"]].invoke(tc["args"])
        results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
    return {"messages": results}


def sub_route(state: SubState) -> str:
    return "continue" if state["messages"][-1].tool_calls else "end"


sub_graph = StateGraph(SubState)
sub_graph.add_node("sub_agent", sub_agent_node)
sub_graph.add_node("sub_tools", sub_tools_node)
sub_graph.add_edge("sub_tools", "sub_agent")                                  # 回环
sub_graph.add_conditional_edges("sub_agent", sub_route, {"continue": "sub_tools", "end": END})
sub_graph.set_entry_point("sub_agent")
sub_app = sub_graph.compile()   # 子 Agent 编译成一个可调用的 app


# ===== ② 主 Agent 工具：派子 Agent（SubAgent 的灵魂）=====
@tool
def delegate_research(question: str) -> str:
    """把需要深入调研的问题交给调研子 Agent，它会多步搜索后返回总结。"""
    # 内部启动一个完整的子 ReAct 循环——子 Agent 用自己的上下文独立干活
    result = sub_app.invoke(
        {"messages": [
            {"role": "system", "content": "你是调研员。搜索 1-2 次拿到信息后立即总结，不要过度搜索。"},
            {"role": "user", "content": question},
        ]},
        config={"recursion_limit": 30},
    )
    # 子 Agent 的最终回答，作为本工具的返回值，交回主 Agent
    return result["messages"][-1].content


# ===== ③ 主 Agent：研究助手（ReAct 循环，工具 = [delegate_research]）=====
MAIN_TOOLS = [delegate_research]
MAIN_TOOL_BY_NAME = {t.name: t for t in MAIN_TOOLS}
main_model = model.bind_tools(MAIN_TOOLS)


class MainState(TypedDict):
    messages: Annotated[list, add_messages]


def main_agent_node(state: MainState):
    reply = main_model.invoke(state["messages"])
    calls = reply.tool_calls
    print(f"[主] tool_calls={[c['name'] for c in calls] if calls else '无(最终回答)'}")
    return {"messages": [reply]}


def main_tools_node(state: MainState):
    last = state["messages"][-1]
    results = []
    for tc in last.tool_calls:
        # ★ 这里调用 delegate_research，会触发子 Agent 整个 ReAct 循环
        output = MAIN_TOOL_BY_NAME[tc["name"]].invoke(tc["args"])
        results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
    return {"messages": results}


def main_route(state: MainState) -> str:
    return "continue" if state["messages"][-1].tool_calls else "end"


main_graph = StateGraph(MainState)
main_graph.add_node("main_agent", main_agent_node)
main_graph.add_node("main_tools", main_tools_node)
main_graph.add_edge("main_tools", "main_agent")                                  # 回环
main_graph.add_conditional_edges("main_agent", main_route, {"continue": "main_tools", "end": END})
main_graph.set_entry_point("main_agent")
main_app = main_graph.compile()


# ===== ④ 跑 =====
if __name__ == "__main__":
    try:
        result = main_app.invoke(
            {"messages": [{"role": "user", "content": "帮我研究一下 GLM-5.2 的能力边界，给个评估"}]},
            config={"recursion_limit": 30},
        )
        print("\n===== 主 Agent 完整轨迹 =====")
        for msg in result["messages"]:
            role = msg.__class__.__name__
            text = (msg.content[:300] + "...") if len(msg.content) > 300 else msg.content
            print(f"[{role}] {text}")
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                print(f"  -> tool_calls: {msg.tool_calls}")
    except Exception as e:
        print(f"[error] 运行失败：{type(e).__name__}: {e}")
        print("（图已编译成功；若是连接错误，请在配代理的终端跑）")
