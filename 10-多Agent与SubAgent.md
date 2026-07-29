# 多 Agent 与 SubAgent

> 2026-07-29 完成。代码 `Code/daily_brief.py` / `Code/research_subagent.py`。
> 衔接 [[09-LangGraph]]：单 Agent 处理复杂任务会顾此失彼（prompt 越写越长、上下文越来越乱）。这一站把多个 Agent 拼起来协作。

## 核心认知

单 Agent 能力有限，复杂任务需要分工。但"多个 Agent"有两种**本质不同**的关系，新手最易混：

> **多 Agent 是对等协作（结构性，图预先画死）；SubAgent 是主从层级（运行时模型动态决定）。**

---

## 1. 多 Agent vs SubAgent

| 维度 | SubAgent（子代理） | Multi-Agent（多代理） |
|---|---|---|
| 关系 | 层级：主 Agent 调用子 Agent，类似函数调用 | 对等 / 协作：多个 Agent 平等协作 |
| 比喻 | 主管把子任务交下属，做完汇报 | 团队同事各自负责一块，互相沟通 |
| 控制权 | 主 Agent 全程掌控 | 无绝对主导者，靠协议协调 |
| 典型实现 | Claude Code Task 工具、嵌套 ReAct | CrewAI、AutoGen 群聊 |

---

## 2. 四种协作模式

- **串行/流水线**：A→B→C，前一个输出是后一个输入。可控但慢。
- **并行**：多个 Agent 同时干，最后汇总。快但合并逻辑复杂。
- **层级**：主 Agent 指挥子 Agent。SubAgent 属于这种。
- **网状/群聊**：Agent 间自由对话，无固定指挥者。灵活但不可控、烧 token。

真实场景多为**混合**（如并行搜集 + 串行加工）。

**拆分维度取决于任务本质**：同一词"博客"，"写文章"按写作流程拆（调研-写作-校对），"建网站"按技术栈拆（前端-后端）。拿到任务先界定本质再拆。

**并行 vs 网状核心区别**：并行是"分活-干活-交活"（子 Agent 间不通信）；网状是"开会-讨论-涌现"（Agent 间互相激发修正）。

---

## 3. 多 Agent 架构落地（daily_brief.py）

系统：每日科技简报生成器 = 并行搜集 + 串行加工（整体层级模式）。

### ① reducer -- 解决并行写同字段冲突

多个并行节点同时写同一字段，默认**覆盖**（后写盖先写）。reducer 声明合并策略：

```python
raw_news: Annotated[List[str], operator.add]   # 并行结果用 + 拼接，不覆盖
```

不加 reducer，三个并行搜集的结果只剩最后一个，前两个丢。**没有这行，并行就废了。**

判据是**合并语义**非类型：累积型（追加）要 reducer；替换型（覆盖）不要。

### ② Send -- 动态扇出

调度者看 sources 列表现派任务，**改数据不改代码**（加源只改输入列表）：

```python
def route_dispatch(state: BriefState) -> list[Send]:
    return [
        Send("collect", {"source": s, "topic": state["topic"]})
        for s in state["sources"]
    ]
```

### ③ 节点管数据，边管控制流（踩坑点）

节点函数只返回 dict（state 更新），**Send 必须放条件边路由函数里**。把 Send 放节点返回值会报 `InvalidUpdateError`。

```python
# ✗ 错：节点返回 Send 列表
def dispatch_node(state):
    return [Send("collect", ...)]   # 报 InvalidUpdateError

# ✓ 对：节点返回 dict，Send 放路由函数
def dispatch_node(state):
    return {}                       # 节点只管数据
def route_dispatch(state):
    return [Send("collect", ...)]   # 控制流在边上
graph.add_conditional_edges("dispatch", route_dispatch)
```

### fan-out + fan-in

- **fan-out**：dispatch 通过 Send 扇出多个并行 collect
- **fan-in**：`add_edge("collect", "summary")` 多入边汇聚，summary 等所有并行 collect 完成才执行（屏障语义）

---

## 4. SubAgent 落地（research_subagent.py）

把子 Agent 做成主 Agent 的一个 **@tool**：

```python
@tool
def delegate_research(question: str) -> str:
    result = sub_app.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content
```

做了四件事：
1. **是个 @tool** -- 对主 Agent 来说和 search/calculate 没区别，主 Agent 不知道它内部跑了整个子图。
2. **sub_app.invoke 启动完整子 ReAct 循环** -- 子 Agent 自己决定搜几次、搜什么。
3. **传全新 messages** -- 子 Agent 在隔离上下文干活，主 Agent 对话历史不进去。
4. **只取最后一条回去** -- 子 Agent 中间搜了什么全留在它自己上下文里，主 Agent 只拿最终结论。

**上下文隔离**是 SubAgent 核心价值：子 Agent 翻江倒海搜索，主 Agent 上下文一字不染，清爽做决策。= **Claude Code Task 工具原理**。

**成本控制**：子 Agent 是会循环的 ReAct，可能不收敛。必须 `recursion_limit` 兜底 + system prompt 引导收敛。ReAct 不收敛是**固有风险**（模型随机性），不是加几行代码能根治。

实测轨迹：
```
[主] tool_calls=['delegate_research']      ← 主 Agent 决策：派子 Agent
  [子] tool_calls=['search', 'search']     ← 子 Agent 并行搜 2 个
  [子] tool_calls=['search']               ← 再搜 1 个
  [子] tool_calls=无(最终回答)              ← 子 Agent 收敛，输出报告
[主] tool_calls=无(最终回答)                ← 主 Agent 整合成最终评估
```

---

## 5. 真调度升级

dispatch 从 `return {}`（假调度，sources 写死在输入）改为调 LLM 动态选源（真调度）：

```python
@tool
def select_sources(sources: List[str]) -> List[str]:
    """根据今日主题，从候选源池中选择 2-4 个最相关的资讯源。"""
    return sources

def dispatch_node(state: BriefState):
    prompt = f"今日主题：{state['topic']} 候选源池：{SOURCE_POOL} ..."
    reply = model.bind_tools([select_sources]).invoke(prompt)   # ① LLM 决策选源
    chosen = reply.tool_calls[0]["args"]["sources"]
    chosen = [s for s in chosen if s in SOURCE_POOL]              # ② 过滤幻觉
    return {"sources": chosen}                                    # ③ 写回 state
```

- 用 `select_sources` 工具让 LLM 结构化输出（复用 [[04-Function-Calling]]）
- 过滤幻觉：LLM 可能编出源池外的源，`if s in SOURCE_POOL` 兜住
- `route_dispatch` 一行没改：**决策（智能，dispatch_node）与执行（机械，route_dispatch）解耦**

换 topic 选不同源，代码一行不改--这就是"调度者是 Agent"的价值。假调度做不到（sources 写死）。

---

## 工程坑

1. **节点返回 Send 报 `InvalidUpdateError`**：Send 必须放条件边路由函数，不能放节点返回值。节点管数据，边管控制流。
2. **ReAct 不收敛是固有风险**：模型随机性，可能死循环（实测 25/60 步两次超限，30 步收敛）。`recursion_limit` 兜底 + system prompt 引导是**必备非可选**。
3. **Windows 控制台 GBK 乱码**：`PYTHONIOENCODING=utf-8` 解决（VSCode 终端默认 UTF-8 不用）。
4. **SubAgent 嵌套调 LLM 延迟叠加**：主调子、子跑多步，比单 Agent 慢。延迟是 SubAgent 真实成本。
5. **dispatch_node 内 bind_tools 的 model 引用**：model 在节点函数定义之后才赋值，但函数体在 `app.invoke` 时才执行，那时 model 已存在。顶层 `dispatch_model = model.bind_tools(...)` 会因 model 未定义而报错 -- 所以 bind 放函数体内。

---

## 代码骨架

**daily_brief.py**（多 Agent 架构 + 真调度）：

```python
class BriefState(TypedDict):
    topic: str
    sources: List[str]
    raw_news: Annotated[List[str], operator.add]   # ① reducer 累积
    summary: str
    brief: str

def dispatch_node(state): ... return {"sources": chosen}      # 真调度（LLM 选源）
def route_dispatch(state): return [Send("collect", ...) ...]  # ② 动态扇出
def collect_node(state): return {"raw_news": [...]}            # 并行搜集
def summary_node(state): return {"summary": ...}               # 汇总
def brief_node(state): return {"brief": ...}                  # 写简报

graph.set_entry_point("dispatch")
graph.add_conditional_edges("dispatch", route_dispatch)       # ③ Send 在路由函数
graph.add_edge("collect", "summary")                           # fan-in 屏障
graph.add_edge("summary", "brief")
graph.add_edge("brief", END)
```

**research_subagent.py**（SubAgent）：

```python
# 子 Agent = 标准 ReAct 图（复用 test_langgraph_agent.py 模式），编译成 sub_app
sub_app = sub_graph.compile()

@tool
def delegate_research(question: str) -> str:                  # 子 Agent 当主 Agent 的工具
    result = sub_app.invoke({"messages": [...question...]})    # 隔离上下文启动子 ReAct
    return result["messages"][-1].content                      # 只取最终结论回去

# 主 Agent = 另一个 ReAct，工具集 = [delegate_research]
main_app = main_graph.compile()
```

---

## 呼应已学

- **[[04-Function-Calling]]**：`select_sources` 工具让 LLM 结构化输出（FC 复用）；SubAgent 把子 Agent 当 @tool；过滤幻觉呼应"工具 description = 给模型看的 Prompt"。
- **[[05-Agent]]**：SubAgent 的子 ReAct 就是 Agent 站的 ReAct 循环；recursion_limit 兜底呼应 Agent 停止判断。
- **[[08-LangChain]]**：`create_agent` 内部是 LangGraph 图，本站直接手画多 Agent 图。
- **[[09-LangGraph]]**：State / reducer / 条件边是本站基础；**Send** 是新的动态扇出机制；"节点管数据、边管控制流"是 LangGraph 设计哲学的延续。

## 价值边界

多 Agent + SubAgent 换"复杂任务分工协作 + 上下文隔离 + 动态调度"，不换单 Agent 能力上限。架构是组织方式，模型能力是基础。SubAgent 不是免费调用（延迟叠加 + 不收敛风险 + token 成本），简单任务别硬拆。

## 概念照进现实

- **Claude Code 派子 Agent（Task 工具）** = 本站 SubAgent 模式产品化：主 Agent 把子任务当工具调用，子 Agent 独立上下文干活。
- **多 Agent 架构** = LangGraph 图的产品化：并行 fan-out + 汇总 fan-in 是生产级 Agent 系统的常见骨架。

## 下一步

- 工程化：流式输出（stream）+ FastAPI 部署 + 评估 + 护栏
- 或多 Agent 框架对比（CrewAI / AutoGen vs 手写 LangGraph，横向理解框架取舍）
