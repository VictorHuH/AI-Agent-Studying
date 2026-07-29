# 🧱 LangChain 教程（阶段3笔记）

> 学习日期：2026-07-23
> 定位：阶段 3 框架与工具链。**把手写的 ReAct/RAG 脚手架工业化封装成框架**。
> 路线位置：RAG ✅ -> Prompt ✅ -> FC ✅ -> Agent ✅ -> MCP ✅ -> Skill ✅ -> **LangChain** ✅ -> LangGraph
> 关键词：组件化、LCEL、Runnable、横切能力免费、create_agent、Retriever

---

## 一、本质：为什么手写能跑了还要框架

承接 Agent 站你手写的 `test_agent.py`。那 181 行里混着两类代码：

- **A 类脚手架**（业务无关，换 agent 得重抄）：拼 messages、调模型、解析返回、循环控制、停止判断、回填 Observation ≈ 70 行
- **B 类业务**（这个 agent 特有）：`get_weather`/`calculate` 实现、`SYSTEM_PROMPT` 内容、用户 query ≈ 55 行

脚手架真正烦的不是"行数多"，是三痛点：

1. **重复**：下个 agent 原样再抄 70 行，业务换了一行没省
2. **脆弱**：模型格式一飘 `json.loads` 就炸，容错逻辑本身也是脚手架
3. **难演进**：换记忆策略/换模型供应商，70 行大改

> 🎯 **一句话**：LangChain = 把 A 类脚手架抽象成可复用、可替换的组件，用 LCEL/Runnable 拼起来，让你只写 B 类。

---

## 二、组件拆解：按"职责"拆，不是按"过程步骤"拆

LangChain 七大组件（对应手写 `test_agent.py`）：

| 组件 | 干什么 | 对应手写 |
|---|---|---|
| `ChatModel` | 调模型（封 api_key/base_url/model） | 28-33 行客户端初始化 |
| `PromptTemplate` | prompt 模板化（占位符运行时注入） | 60-97 SYSTEM_PROMPT + 拼 messages |
| `OutputParser` | 模型输出 -> 结构化 | 101-103 正则解析 |
| `Tool` | 工具（`@tool` 自动生成 schema） | 37-53 函数 + TOOL_REGISTRY |
| `Memory` | 短期记忆（messages 管理） | 121/165 行 append |
| `Agent` | 决策大脑 | system prompt |
| `AgentExecutor` | 运行循环 | 107-167 run_agent |

**关键认知**：能复用的是**职责**，不是**步骤**。"循环控制/停止判断/回填"是同一个 for 循环的不同阶段，拆开没意义，封成一个 `AgentExecutor`。

### 前端类比（迁移认知）

| 前端 | LLM 对应 | 说明 |
|---|---|---|
| Vue/React（框架） | **LangChain** | 组件化 + 编排，但管 LLM 编排非 UI 渲染 |
| Element/Antd（组件库） | LangChain 自带组件 | ⚠️ 前端框架和组件库分开，LangChain 揉一起了 |
| Pinia/Vuex（状态管理） | LangGraph State | 状态在节点间流转 |
| **XState**（状态机/状态图） | **LangGraph** | 最贴切：状态+节点+边+条件路由 |
| JSX/template | LCEL (`\|`) | 声明式编排语法 |

前端生态分层清晰（Vue/Antd/Pinia/Vite 各管一摊），**LangChain 想全包**--这就是它臃肿、API 反复横跳（`create_react_agent` 三次搬家）的根源，也是 `langgraph` 被拆出来的原因。

---

## 三、LCEL + Runnable：统一接口换横切能力免费

所有组件实现 `Runnable` 接口（`invoke`/`stream`/`batch`/`ainvoke`/`retry`），用 `|` 重载管道拼：

```python
chain = prompt | model | parser
chain.invoke({"input": "上海比北京热几度？"})
```

| 机制 | 说明 |
|---|---|
| `\|` 重载 | `a \| b` = 把 a 的输出喂给 `b.invoke()` |
| 统一接口 | 所有组件都有 invoke，所以能拼（输入输出契约显式化） |
| 横切能力免费 | stream/batch/async/retry 在基类实现一次，所有组件白嫖 |

> 🎯 **横切能力的数学本质**：N 个组件 × M 种能力，手写 N×M 处，统一接口 N+M 处。**加第 4 种能力时**手写再追加 N 处，统一接口加 1 处。需求永远在变，新横切能力不断冒出来（限流/缓存/trace...），这才是抽象换来的真金白银。

### 数据流（`chain.invoke({...})`）

| 阶段 | 组件 | 输入 | 输出 |
|---|---|---|---|
| ① | `prompt` | dict | `ChatPromptValue`（messages） |
| ② | `model` | `ChatPromptValue` | `AIMessage` |
| ③ | `parser` | `AIMessage` | str |

---

## 四、Tool + Agent：`@tool` + `create_agent`

### Tool：`@tool` 自动生成 schema

```python
@tool
def get_weather(city: str) -> str:
    """查询某城市当前天气。"""
    ...
```

从**函数签名 + docstring** 自动生成 name/description/args_schema。

> 🔗 **呼应已学**：跟 MCP 站 `@mcp.tool()` 同一个思想（schema 从注解自动生成，别手写）；对比 FC 站手写的 `TOOLS_SCHEMA`。docstring = 给模型看的 description（决定模型何时调它）--FC 课"工具 description=给模型看的 Prompt"。

### Agent：`create_agent`（FC 版，非纯 prompt ReAct）

```python
from langchain.agents import create_agent
agent = create_agent(model, [get_weather, calculate])
agent.invoke({"messages": [{"role":"user","content":"..."}]})
```

> ⚠️ **框架演进"三次横跳"**（边界反复调整的活样本）：
> 1. `langchain.agents.AgentExecutor`（经典，已 legacy）
> 2. `langgraph.prebuilt.create_react_agent`（曾主线，v1.0 起 deprecated）
> 3. `langchain.agents.create_agent`（**当前主线**，本站用这个）
>
> langgraph 退回底层运行时（StateGraph/checkpoint），`create_agent` 内部用 LangGraph 跑。装包时 `langgraph` 被自动装，就是证据。

### `create_agent` 内部 = LangGraph 图

```
        ┌──────────────────────────────┐
        │                              │
START -> [agent:调模型] ─条件边①─-> [tools:执行] ─┘ 回环
            │
            └─条件边②(无tool_call)─-> END
```

| 图要素 | 对应手写 `run_agent` |
|---|---|
| `agent` 节点 | 118-121 行：调模型 + 回填 assistant |
| `tools` 节点 | 142-160 行：派发 + 执行 |
| 条件边①（有 tool_call -> tools） | 隐含：解析到 Action 就执行 |
| 条件边②（无 tool_call -> END） | 136-140 行：`if Final Answer: return` |
| `tools -> agent` 回环 | `for step in range(...)` 的下一轮 |

> 🎯 **一句话**：图把"命令式 `for` + `break`"变成"声明式 **边 + 条件路由**"。循环靠回环边表达，停止靠路由到 `END` 表达。这是 LangChain 把 Agent 迁到 LangGraph 的根本原因--图可可视化、可组合、可自定义（加人工审批节点/并行分支都改图结构，不动节点内部）。

**停止有两套机制**：

| 机制 | 触发 | 对应手写 |
|---|---|---|
| 正常停止 | 条件边②路由到 END（模型自主判断"信息够了"） | 136-140 `if Final Answer: return` |
| 兜底停止 | `recursion_limit`（默认 25）超限抛 `GraphRecursionError` | 167 `print("达到最大步数...")` |

模型绝大多数时候走第一套；第二套是"模型卡循环"的保险丝。

### 关键修正：ReAct 范式 vs FC 机制正交

| | 纯 prompt ReAct（`test_agent.py`） | FC 版（`create_agent`） |
|---|---|---|
| 工具调用 | 文本 Action，正则解析 | 结构化 `tool_call` |
| Thought | 白盒可见 | 黑盒（在模型内部） |
| 并行 | 一次一个 Action，逐步串行 | 一轮多 `tool_call`，**并行** |

> 🎯 **修正 Agent 课的印象**："逐步串行"不是 ReAct 的本质，是**纯 prompt 版的实现限制**。ReAct 是推理范式，FC 是工具机制，两者正交。FC 版 ReAct 既能保持循环推理，又能一轮多 `tool_call` 并行。工业版用 FC 不只是"解析稳定"，还白赚并行。

**并行边界**：**此刻参数都已知则并行，有依赖必须分轮**。
- 三个 `get_weather` 互相无依赖（参数是城市名，来自用户）-> 一轮并行
- `calculate(35-30)` 依赖前面天气结果 -> 不能同轮。第一轮时模型还不知道 35 和 30，**物理上无法构造**这个 tool_call（不是"不该"，是"不可能"）

> 判断"能不能并行"就一句话：**这些调用的参数，此刻都已知吗？**

---

## 五、Retriever：把 RAG 接进链

```python
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt | model | StrOutputParser()
)
chain.invoke("他用过什么部署技术？")   # 命中 Nginx + Docker
```

`as_retriever()` 把向量库变成 Runnable（这一站的魔法），接你已有的 `./chroma_db` 简历库，复用不重建。

数据流：query -> 并行算 `context`（`retriever | format_docs`）和 `question`（`RunnablePassthrough` 透传）-> prompt -> model -> parser。`RunnablePassthrough` 解决"query 要分两路用"（retriever 要检索、prompt 要当问题）。

> 🎯 **价值边界**：Retriever 跟你手写 `retrieve` **等价**（同一个 Chroma、同一个豆包 embedding）。框架只是把检索"组件化接进链"，**不提升检索质量**。检索上限还是 RAG 课那套（切分/rerank/父子块）决定。**框架是放大器，不是能力来源。**

---

## 六、工程坑：OpenAI 兼容 = 部分兼容

`langchain_openai` 接火山豆包 embedding 报 400：`expected a string, but got [43511 11883 ...]`

- **原因**：`OpenAIEmbeddings` 默认 `check_embedding_ctx_length=True`，用 tiktoken 把文本分词成 **token id 数组**再传；OpenAI 官方端点吃 token id，但**火山豆包端点只吃字符串**。
- **修复**：`OpenAIEmbeddings(..., check_embedding_ctx_length=False)`
- **认知**：chat 接口兼容（`create_agent`/FC 都顺），embedding 的 token id 传法不兼容。**接国产端点（豆包/通义/Kimi/DeepSeek）embedding 经常要这个参数。**

---

## 七、总收尾

带走六件事：

1. **LangChain = 脚手架组件化 + Runnable 拼接**。换"复用 + 标准化 + 横切能力免费"，不换检索/生成质量。框架是放大器非能力来源。
2. **按职责拆非按过程**。七大组件对应手写代码各部分；"循环/停止/回填"封成一个 `AgentExecutor`。
3. **LCEL + Runnable**：统一接口换横切能力免费（N×M -> N+M，加新能力手写 N 处统一接口 1 处）。
4. **`create_agent` FC 版**：内部 LangGraph 图，`for`+`break` 变边+条件路由。停止两套（条件边 END + `recursion_limit` 兜底）。框架三次横跳，当前主线 `langchain.agents.create_agent`。
5. **ReAct 范式 vs FC 机制正交**：FC 版可并行，边界 = 此刻参数都已知。
6. **Retriever = 检索组件化**：`as_retriever` 接进链，但不提升检索质量。

### 四大组件全过手

| 组件 | 代码 | 对应手写 |
|---|---|---|
| LCEL 链 | `Code/test_langchain.py` | `test_agent.py` 拼 prompt/调模型/解析 |
| Tool + Agent | `Code/test_langchain_agent.py` | `test_agent.py` ReAct 循环 |
| Retriever | `Code/test_langchain_rag.py` | `test.py` retrieve + answer |

### 价值边界（铁律再印一次）

- **检索决定上限**（RAG 课管：切分/rerank/父子块）
- **生成决定下限**（Prompt 课管：角色/结构化/Rule）
- **框架换复用 + 标准化 + 横切免费**，不换上限也不换下限

> 🔗 **下一站钩子（LangGraph）**：
> - `create_agent` 内部已是 LangGraph 图，你已间接接触。下一站深入：`State` + 自定义 `nodes`/`edges`。
> - LangGraph 一举覆盖：**Memory**（State 里的 messages，1.x 后 Memory 不是独立组件，`ConversationBufferMemory` 等 legacy）+ **Workflow 编排** + "图怎么兜底死循环"。
> - 简单场景用 LangChain 现成组件（`create_agent`）就够；需要自己画节点/边/分支时，下沉到 LangGraph 自定义图。
>
> LangChain 站完成。下一站：**LangGraph**。
