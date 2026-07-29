"""
最小 LangGraph Agent（FC 版 ReAct）
- 1 个 agent 节点（调模型决策）+ 1 个 tools 节点（执行工具）
- 普通边 tools -> agent（回环）
- 条件边 agent -> tools 或 END
复用 FC 站 / LangChain 站的 get_weather / calculate 工具
"""
import os
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

# ===== 1. 工具：@tool 装饰器从签名+docstring 自动生成 schema =====
@tool
def get_weather(city: str) -> str:
    """查询指定城市的天气"""
    fake = {"上海": "32度晴", "北京": "35度晴", "广州": "30度雷阵雨"}
    return fake.get(city, "未知")

@tool
def calculate(expression: str) -> str:
    """数学表达式计算，如 '3*4'"""
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"计算失败: {e}"

TOOLS = [get_weather, calculate]
TOOL_BY_NAME = {t.name: t for t in TOOLS}   # 派发表（呼应 FC 站 TOOL_REGISTRY）

# ===== 2. 模型（豆包/火山 ARK，复用 LangChain 站配置）+ 绑定工具 =====
model = ChatOpenAI(
    model="glm-5.2",
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
).bind_tools(TOOLS)

# ===== 3. State：messages 用 reducer 自动累积 =====
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# ===== 4. 节点函数 =====
def agent_node(state: AgentState):
    reply = model.invoke(state["messages"])   # 读 state，调模型
    return {"messages": [reply]}              # 只返回新增的，reducer 自动追加

def tools_node(state: AgentState):
    last = state["messages"][-1]
    results = []
    for tc in last.tool_calls:                # 模型的 tool_calls 列表（可并行多个）
        fn = TOOL_BY_NAME[tc["name"]]
        output = fn.invoke(tc["args"])
        results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))  # 带上 tool_call_id
    return {"messages": results}

def route_fn(state: AgentState) -> str:
    last = state["messages"][-1]
    if last.tool_calls:                       # 模型要调工具
        return "continue"
    return "end"                              # 模型给最终答案了

# ===== 5. 拼图：节点 + 边 + 入口 + 编译 =====
graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tools", tools_node)
graph.add_edge("tools", "agent")                                       # 回环边
graph.add_conditional_edges("agent", route_fn, {"continue": "tools", "end": END})
graph.set_entry_point("agent")
app = graph.compile()

# ===== 6. 跑 =====
result = app.invoke({
    "messages": [{"role": "user", "content": "查上海和北京的天气，告诉我哪个更热"}]
})

# 打印完整轨迹
for msg in result["messages"]:
    role = msg.__class__.__name__
    print(f"[{role}] {msg.content}")
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        print(f"  -> tool_calls: {msg.tool_calls}")
