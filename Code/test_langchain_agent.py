"""
LangChain 第二站：接 Tool + 做成 Agent
用 langgraph.prebuilt.create_react_agent 重写 test_agent.py 的 ReAct Agent。

【现状（必读）】
  LangChain Agent 演进三代（"三次横跳"，框架边界反复调整的活样本）：
    1. langchain.agents.AgentExecutor（经典，已 legacy）
    2. langgraph.prebuilt.create_react_agent（曾主线，v1.0 起标 deprecated）
    3. langchain.agents.create_agent（当前主线，本文件用这个）
  现在的定位：langgraph 退回底层运行时（StateGraph/checkpoint），
  prebuilt agent 重新归入 langchain.agents，改名 create_agent（不再绑定 ReAct 范式）。
  底层还是 langgraph 在跑，只是入口回到了 langchain.agents。

【ReAct 两种实现】
  - test_agent.py：纯 prompt ReAct（正则解析 Thought/Action 文本）
  - 本文件：FC 版（tools 参数，模型输出结构化 tool_call，不靠解析文本）
  这正是 Agent 笔记里"先白白盒理解原理，再工业封装"的工业封装落地。

用法：
  cd Code
  python test_langchain_agent.py
"""
import os
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_agent

# ===== 0. 模型组件（同 test_langchain.py）=====
model = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
    model="glm-5.2",
)

# ===== 1. 工具组件（对应手写 test_agent.py 37-53 行）=====
# 手写：普通函数 + 手写 TOOL_REGISTRY 字典；FC 版还要手写 TOOLS_SCHEMA（JSON schema）
# LangChain：@tool 装饰器自动从【函数签名 + docstring】生成 name/description/args_schema
# 【呼应 MCP】：跟 FastMCP 的 @mcp.tool() 同一个思想--schema 从注解自动生成，别手写。
# docstring 就是给模型看的 description（决定模型何时调它）--呼应 FC 课"工具 description=给模型看的 Prompt"。

@tool
def get_weather(city: str) -> str:
    """查询某城市当前天气。参数 city 为城市名。"""
    fake = {"上海": "32℃，晴", "北京": "30℃，多云", "广州": "35℃，雷阵雨"}
    return fake.get(city, f"{city}：28℃，晴")


@tool
def calculate(expression: str) -> str:
    """精确计算数学表达式，如 "35-30"。"""
    try:
        result = eval(expression, {"__builtins__": {}}, {})  # 受限 eval，生产环境别用
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算失败: {e}"


# ===== 2. 拼成 Agent（对应手写 test_agent.py 107-167 行整个 run_agent）=====
# 手写 run_agent 干了 5 件事：拼 messages、调模型、解析、派发工具、回填 Observation、停止判断
# create_react_agent 把这 5 件事全封进一个 prebuilt 组件，你只传 model + tools。
# 【可替换性体现】换记忆策略/换循环策略不用动这里（prebuilt 内部用 LangGraph state 管）。
agent = create_agent(model, [get_weather, calculate])


# ===== 3. 调用（对应手写 run_agent("查三城天气找最热...")）=====
# 注意 invoke 入参变了：不再是 {question:...}，而是 {messages:[...]}。
# 因为 Agent 的"输入"是会话消息列表（短期记忆），不是单个模板变量。
result = agent.invoke({
    "messages": [{"role": "user", "content":
        "我想去中国最热的城市旅游，候选是上海、北京、广州。"
        "帮我查这三个城市的天气，找出最热的，并算出它比最冷的高多少度。"}]
})

# 返回的是整个 messages 历史（含每步模型的 tool_call 和工具返回的 ToolMessage）
# 对比手写：手写是你自己 print Thought/Action/Observation；这里 messages 全在，官方格式化打印。
for msg in result["messages"]:
    msg.pretty_print()
