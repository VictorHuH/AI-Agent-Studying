# LangGraph

> 2026-07-27 完成。代码 `Code/test_langgraph_agent.py`。
> 衔接 [[08-LangChain]]：`create_agent` 内部本身就是一张 LangGraph 图。这一站把壳拆掉，直接画图。

## 核心认知

LangChain 是「组件 + 管道」（LCEL 的 `prompt | model | parser`），适合**线性流水线**；LangGraph 是「**状态 + 图**」，适合**有分支、有循环、有并行**的复杂流程。

- `langchain.agents.create_agent` 是"预制菜"：假设标准形状 = 1 个模型节点 + 1 个工具节点 + 条件路由。流程不是这个形状就不够用。
- LangGraph 把壳拆掉，让你**直接画图**。`create_agent` 内部就是 LangGraph 图。
- 类比：LangChain 像 Vue 组件 + 模板（声明式拼装），LangGraph 像 XState 状态机（显式画状态、画边、画条件路由）。

需要直接画图的三个典型场景：
1. **Workflow 混 Agent**：检索（写死）-> 模型判断要不要查工具（自主）-> 生成 -> 自检。确定性和自主性混在一起。
2. **多 Agent 协作**：写代码 / review / 执行，节点不止两个，边是网状。
3. **人在回路（HITL）**：执行某步前要人确认，需要打断图、等人输入、再续上。

核心心智模型一句话：**状态在 State 里，逻辑在节点里，路由在边上。** 三者分离。

---

## 1. State -- 整张图共享的数据结构

State 就是一个 TypedDict，定义图里有哪些字段在节点间流动：

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]   # 加 reducer
    step: int
    done: bool
```

节点函数：**接收 state、干活、返回"更新"**：

```python
def agent_node(state: AgentState) -> dict:
    msgs = state["messages"]             # 读
    reply = model.invoke(msgs)           # 干活
    return {"messages": [reply]}         # 返回更新（只写要改的字段）
```

三个关键点：
1. **节点返回的是「更新」不是完整 state** -- 只写这次要改的字段，没改的保留。
2. **图自动 merge**：把返回值合并回 state，下一个节点拿到新 state。
3. **为什么能支撑回环边**：state 在循环**外面**。每次回到 agent 节点，state 已含上一轮 tools 节点写回的结果。循环不是"重新执行"，而是"带着累积的状态再走一圈"。

对照手写 `test_agent.py`：`messages.append(...)` 那行本质就是手动做了 state merge，LangGraph 把它自动化、显式化了。

---

## 2. reducer -- 字段合并的命门

默认 merge 是**覆盖**。两种写法效果不同：

```python
# 写法 A：只返回新增的一条
return {"messages": [result]}
# 写法 B：手动拼整个列表
return {"messages": state["messages"] + [result]}
```

- 没 reducer 时，写法 A 会让 messages 只剩这一条，**历史全丢**；写法 B 能对但每个节点都要手动拼。
- 有 reducer 时，写法 A 就够了 -- 图自动追加。

给字段加 reducer：

```python
messages: Annotated[list, add_messages]   # add_messages = 追加 + 按 id 去重
```

**真正的判据是合并语义，不是类型**：

| 字段 | 合并语义 | 类型 | 要 reducer？ |
|---|---|---|---|
| `messages` | 追加（新消息拼到旧消息后） | list | ✅ 要 |
| `step` | 覆盖（直接 set step=2） | int | ❌ 不要 |
| `done` | 覆盖 | bool | ❌ 不要 |
| `turn_count`（每步 +1） | 累加 | int | ✅ 要 |
| `candidates`（整体替换） | 覆盖 | list | ❌ 不要 |

**更深的认知：reducer 是「便利」不是「必须」。**

- **替换型**字段：不用 reducer（默认覆盖）。
- **累积型**字段有两条路：
  - 用 reducer：节点只返回增量，图自动合并。适合 messages 这种"纯追加、每个节点都追加"的简单语义。
  - 不用 reducer：节点自己读旧值、算好、返回完整新值。适合 retry_count 这种"有时累加有时重置"的混合语义。
- messages 选前者省事；retry_count 选后者更直接。
- `MessagesState` 是内置版，已声明好 `messages: Annotated[list, add_messages]`，省得手写。

---

## 3. 拼图 -- Node + Edge

```python
from langgraph.graph import StateGraph, END

graph = StateGraph(AgentState)

# 1. 加节点：名字 -> 函数
graph.add_node("agent", agent_node)
graph.add_node("tools", tools_node)

# 2. 加边：两种
#    a) 普通边（固定流转）：A 完了一定去 B
graph.add_edge("tools", "agent")      # 回环边

#    b) 条件边（动态路由）：A 完了去哪，看 state
graph.add_conditional_edges(
    "agent",                          # 从哪个节点出发
    route_fn,                         # 路由函数：接收 state，返回字符串
    {"continue": "tools", "end": END} # 路由表：返回值 -> 目标节点
)

# 3. 设入口 + 编译
graph.set_entry_point("agent")
app = graph.compile()
```

**普通边 vs 条件边**：

|  | 普通边 `add_edge` | 条件边 `add_conditional_edges` |
|---|---|---|
| 流转 | 写死：A -> B | 动态：A -> ? |
| 决定者 | 代码（编译期写死） | state（运行时由 route_fn 决定） |
| 例子 | tools -> agent | agent -> tools 或 END |

**路由函数**：

```python
def route_fn(state: AgentState) -> str:
    last = state["messages"][-1]
    if last.tool_calls:           # 模型要调工具
        return "continue"         # -> 路由表查到去 tools
    return "end"                  # 模型给最终答案了 -> 去 END
```

路由函数就是：**接收 state、返回字符串**，图拿这个字符串去路由表查下一步去哪。

边数算法：按分支数算，1 条普通边 + 2 条条件分支 = 3 条边；按调用次数算，1 + 1 = 2 条。工程上习惯按分支数。

---

## 4. 跑起来 + 对照手写版

```
[1] HumanMessage "查上海和北京..."               ← 初始输入，进 agent 节点（入口）
[2] AIMessage + tool_calls(上海,北京)           ← agent 第1轮：调模型，决策并行查两城
[3] ToolMessage "32度晴"                         ← tools 节点执行第1个 tool_call
[4] ToolMessage "35度晴"                         ← tools 节点执行第2个 tool_call
[5] AIMessage "北京更热..."                      ← agent 第2轮：看结果，给最终答案
```

图怎么转：入口 agent -> 条件边(continue) -> tools -> 普通边(回环) -> agent -> 条件边(end) -> END。

**对照 `test_agent.py`**：

| test_agent.py（手写） | LangGraph |
|---|---|
| `for step in range(max_steps)` | 回环边 `tools -> agent` |
| `if action == "Final Answer": break` | 条件边路由到 END |
| `messages.append(...)` 手动追加 | reducer 自动累积 |

**图就是 for+break 循环的可视化。**

**并行 vs 串行**：本次模型一轮并行查上海+北京（一个 AIMessage 两个 tool_calls，tools 节点一轮处理两个）。对比 test_agent.py 纯 prompt ReAct 是逐步串行。印证 LangChain 站讲的：**FC 版一轮多 tool_call 并行，纯 prompt ReAct 只能一次一个**。

**条件边的价值**：闲聊（"你是谁"）只走 1 跳（agent -> END），不必走完整个循环。手写版 `if Final Answer: break` 在 LangGraph 里就是条件边路由到 END。

---

## 5. Checkpointer -- 让图能存盘、能续跑

默认图每次 `app.invoke(...)` 无状态：跑完 state 就没了。checkpointer 把 state 存盘，实现**会话接续**。

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
app = graph.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "user-001"}}

# 第一次：自我介绍
app.invoke({"messages": [{"role": "user", "content": "我叫小明"}]}, config)
# 第二次：只传新消息，不传历史
app.invoke({"messages": [{"role": "user", "content": "我叫什么？"}]}, config)
# -> 模型能答出"小明" -- checkpointer 自动取回上次 state
```

三个关键点：
1. **thread_id = 会话标识**。同一个 thread_id，state 跨 invoke 累积；不同 thread_id 互不干扰（多用户隔离）。
2. **第二次 invoke 只传新消息**，checkpointer 自动取回上次 state、追加新消息、再跑图。
3. **每次节点执行后都存盘** -- 中途崩了，下次同 thread_id 能从最近 checkpoint 恢复。

**和 Agent 站 Chroma 长期记忆的区别（别混淆！）**：

|  | LangGraph checkpointer | Agent 站 Chroma 长期记忆 |
|---|---|---|
| 存什么 | 完整 state（messages 全量） | 从对话提取的事实 |
| 怎么取 | 按 thread_id **精确取回** | 按**语义相似度检索** |
| 解决什么 | 会话接续（接着上次聊） | 跨会话知识（记得用户去过上海） |

一句话：**checkpointer = 会话级持久化（把短期记忆存盘）；Chroma = 跨会话语义记忆（提取事实做检索）。** 两者可共存：checkpointer 管会话接续，Chroma 管跨会话知识。

---

## 6. Human-in-the-loop -- 图能暂停等人确认

checkpointer 最酷的用法。危险工具执行前要人确认。

```python
app = graph.compile(
    checkpointer=memory,
    interrupt_before=["tools"]   # 进入 tools 节点前暂停
)

config = {"configurable": {"thread_id": "1"}}

# 第一次 invoke：图跑到 tools 前就停了
result = app.invoke({"messages": [{"role": "user", "content": "删掉用户表"}]}, config)

# 人工看一眼：模型要调什么工具？
print(result["messages"][-1].tool_calls)

# 确认没问题，让图继续跑（传 None = "接着上次停的地方跑"）
result = app.invoke(None, config)
```

关键点：
1. `interrupt_before=["tools"]` 告诉图"进入 tools 前先停一下"。也有 `interrupt_after`、节点内 `interrupt()` 函数动态中断。
2. 第一次 invoke 跑到 tools 前就停，state 存 checkpointer。**没 checkpointer 这事做不到** -- 图停下来 state 不能丢。
3. `invoke(None, config)` 传 None 表示"不传新输入，接着上次停的地方跑"。

价值：危险工具拦截 / 审批流 / 纠偏。呼应 Agent 站护栏：工具滥用不能光靠 prompt 规则约束（Rule 是最弱护栏），用 interrupt 在**执行前硬拦截**。Rule 是软约束，interrupt 是硬约束。

---

## 工程坑（火山 ARK）

1. **base_url 要用 coding 端点**：`https://ark.cn-beijing.volces.com/api/coding/v3`，不是标准 `/api/v3`。`glm-5.2` 模型只在 coding 端点可用，走标准端点报 `404 - glm-5.2 does not exist`。
2. **环境变量名对齐项目**：前几站都用 `OPENAI_API_KEY`，别自作主张改成 `ARK_API_KEY`，否则 `KeyError`。

---

## 代码 `Code/test_langgraph_agent.py`

```python
import os
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

# 1. 工具：@tool 装饰器自动生成 schema
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
TOOL_BY_NAME = {t.name: t for t in TOOLS}

# 2. 模型 + 绑定工具
model = ChatOpenAI(
    model="glm-5.2",
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
).bind_tools(TOOLS)

# 3. State
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# 4. 节点函数
def agent_node(state: AgentState):
    reply = model.invoke(state["messages"])
    return {"messages": [reply]}

def tools_node(state: AgentState):
    last = state["messages"][-1]
    results = []
    for tc in last.tool_calls:
        fn = TOOL_BY_NAME[tc["name"]]
        output = fn.invoke(tc["args"])
        results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
    return {"messages": results}

def route_fn(state: AgentState) -> str:
    last = state["messages"][-1]
    if last.tool_calls:
        return "continue"
    return "end"

# 5. 拼图
graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tools", tools_node)
graph.add_edge("tools", "agent")
graph.add_conditional_edges("agent", route_fn, {"continue": "tools", "end": END})
graph.set_entry_point("agent")
app = graph.compile()

# 6. 跑
result = app.invoke({
    "messages": [{"role": "user", "content": "查上海和北京的天气，告诉我哪个更热"}]
})
for msg in result["messages"]:
    role = msg.__class__.__name__
    print(f"[{role}] {msg.content}")
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        print(f"  -> tool_calls: {msg.tool_calls}")
```

---

## 呼应已学

- **[[04-Function-Calling]]**：`@tool` 装饰器自动生成 schema（呼应 FC 站手写 TOOLS_SCHEMA）；`tool_call_id` 是工具回填命脉；模型只决策不执行。
- **[[05-Agent]]**：图 = 手写 `run_agent` 的 for+break 循环可视化；条件边路由到 END = `if Final Answer: break`；reducer 自动累积 = 手写 `messages.append`；checkpointer 会话级持久化 vs Chroma 跨会话语义记忆（两层不冲突可叠加）。
- **[[06-MCP]]**：`@mcp.tool()` / FC description / `@tool` 三层 name+description 同构。
- **[[07-Skill]]**：HITL 的 interrupt 是"硬护栏"，对比 Skill body 里的 Rule 是"软护栏"。
- **[[08-LangChain]]**：`create_agent` 内部就是 LangGraph 图（agent 节点 + tools 节点 + 条件边 + recursion_limit=25 兜底）；框架演进三次横跳 AgentExecutor -> create_react_agent(v1.0 deprecated) -> create_agent(主线)，langgraph 退回底层运行时。

## 价值边界

LangGraph 换"图编排 + 状态持久化 + HITL"，不换检索质量（RAG 课的切分/rerank/父子块）和生成质量（prompt + 模型）。框架是放大器非能力来源。

## 下一步

- 工程化：流式输出（stream）+ FastAPI 部署 + 评估 + 护栏
- 或更深的 LangGraph：多 Agent 协作、子图、Send API（map-reduce 并行）
- 按推荐顺序：流式+部署 -> 评估+护栏 -> 按需深挖
