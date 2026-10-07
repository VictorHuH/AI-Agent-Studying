# 🤖 Agent 教程（阶段2笔记）

> 学习日期：2026-07-18
> 定位：阶段 2 核心战力。FC 给模型"手脚"，**Agent 给模型"大脑"**--自主规划 + 推理循环 + 记忆。
> 路线位置：RAG ✅ -> Prompt ✅ -> FC ✅ -> **Agent** ✅ -> Skill+MCP -> LangChain

---

## 一、本质：从 FC 到 Agent，差的就一步

FC demo 里模型已经会"决策->执行->回填->再决策"的循环了，那不已经是 Agent 了吗？差在**自主规划**。

- **FC 是被动响应**：你问一句，它调工具答一句。问"上海北京谁热"，一轮并行查完就结束。
- **Agent 是目标导向**：给个目标，自己拆步骤、自己判断何时停。问"查三城天气、找最热、算比最冷高几度"，Agent 会**推理着一步步走**：查上海->看到32->查北京->…->算差值->够了，停。

这个增量学术上叫 **ReAct**（Reasoning + Acting）。

### Agent 是什么（和 FC / Workflow 的边界）

| | 谁决定流程 | 推理是否显式 | 例子 |
|---|---|---|---|
| **Workflow** | 你写死（先A再B再C） | 无 | LangGraph 固定管线 |
| **Function Calling** | 模型决定调哪个工具（单步） | 隐藏（content 常空） | test_function_calling.py |
| **Agent** | 模型自主规划多步 + 判断停止 | 显式（ReAct 的 Thought） | test_agent.py |

> 🎯 **一句话**：FC 给模型"手脚"（执行单步），Agent 给模型"大脑"（规划多步 + 显式推理 + 判断停止）。FC 是 Agent 的腿，Agent 是长出脑子的 FC。

### 和已学知识的钩子兑现

Prompt 阶段埋的 **CoT -> ReAct** 钩子今天兑现：
- **CoT**（"一步一步思考"）只推理不行动--光想不做。
- **ReAct** 把推理和工具调用**交替**--边想边做。
- FC 的循环其实是 ReAct，只是 Thought 藏起来了；ReAct 模式把 Thought 显式化、白盒可见。

---

## 二、ReAct：让推理和行动交替

```
用户目标
   │
   ▼
Thought: 我需要查三城天气，先查上海     ← 推理（CoT 的延伸）
Action:  get_weather(上海)              ← 行动
   │
   ▼
Observation: 32℃，晴                   ← 观察（工具结果回填）
   │
   ▼
Thought: 上海32，查北京……              ← 基于观察继续推理
Action:  get_weather(北京)
   │
   ▼
…… 循环 ……
   │
   ▼
Thought: 信息够了                       ← 停止判断
Action:  Final Answer
```

三要素：**Thought（推理）-> Action（行动）-> Observation（观察）** 循环，直到模型自己判断"信息够了"输出 Final Answer。

### 纯 Prompt ReAct vs FC 结构化版

ReAct 有两种实现，本站先手写前者：

| | 纯 Prompt ReAct（本站） | FC 结构化版（FC demo） |
|---|---|---|
| 工具怎么传 | 写进 system prompt（自然语言） | `tools` 参数（JSON Schema） |
| 模型怎么输出 | 文本 Thought/Action/Action Input | 结构化 tool_call |
| Thought 可见 | ✅ 白盒（模型显式输出） | ❌ 黑盒（content 常为空） |
| 解析 | 自己正则解析文本（脆弱） | API 返回结构（稳定） |
| 工业使用 | 教学清晰但易碎 | LangChain 等框架默认 |

**为什么先手写纯 Prompt 版**：能肉眼看见模型在想什么，这是理解 Agent 的关键。工业上用 FC 版（稳），但那时 Thought 又黑盒了--所以**先白盒理解，再工业封装**。

---

## 三、实战：手写 ReAct Agent

见 `Code/test_agent.py`。复用豆包 `glm-5.2` + 两个工具（`get_weather`/`calculate`，同 FC demo），但**不带 `tools` 参数**，靠 system prompt 约束输出格式。

```bash
cd Code
python test_agent.py
```

### 代码结构：4 个必懂点

**① system prompt = Agent 的"大脑"**

纯 Prompt ReAct 不用 FC 的 `tools` 参数，工具说明、输出格式、few-shot 例子全写进 system prompt。这份 prompt 的质量直接决定 Agent 行不行。关键组成：
- 可用工具的自然语言描述 + 参数
- 严格的输出格式约定（Thought/Action/Action Input）
- **few-shot 例子**（一个完整的多步循环，让模型理解"轮流"而非"一次输出全部"）
- 规则（每次只输出一个三元组、Action 必须是工具名或 Final Answer）

**② 循环四步：Thought -> Action -> Observation -> 回填**

```python
for step in range(1, max_steps + 1):
    resp = client.chat.completions.create(model=CHAT_MODEL, messages=messages)  # 不带 tools！
    text = resp.choices[0].message.content.strip()
    messages.append({"role": "assistant", "content": text})        # 记回（短期记忆）
    # 解析 Thought 打印 -> 解析 Action -> 若 Final Answer 则停 -> 否则执行工具
    messages.append({"role": "user", "content": f"Observation: {observation}"})  # 结果回填
```

**③ Observation 用 `user` 角色拼回**

API 没有 `observation` 角色。惯例用 `user` 塞 `"Observation: ..."` 模拟"环境给模型的反馈"。模型下一轮看到这行就知道工具结果，继续推理。

**④ 解析容错 = 纯 Prompt ReAct 的命门**

```python
try:
    args = json.loads(raw_input)
except json.JSONDecodeError:
    observation = f"参数不是合法 JSON：{raw_input}，请严格输出 JSON。"
```

模型格式飘了（Action Input 不是合法 JSON）就解析失败。这里不报错崩溃，而是把"你格式错了"作为 Observation 喂回去让模型自我纠正。**这就是纯 Prompt ReAct 的脆弱点--工业版用 FC 的 `tools` 参数规避（API 返回结构化 tool_call，不靠解析文本）。**

正则还兼容中英文冒号（`Action:` vs `Action：`），因为模型可能混用。

### 演示任务：多步规划（已跑通 ✅）

```
用户：查上海、北京、广州天气，找最热的，算它比最冷的高多少度。
```

实际运行结果（2026-07-18 跑通）：
```
第1步 Thought: 先从上海开始查。          Action: get_weather(上海)  -> 32℃
第2步 Thought: 上海32，查北京。          Action: get_weather(北京)  -> 30℃
第3步 Thought: 北京30，查广州。          Action: get_weather(广州)  -> 35℃
第4步 Thought: 广州35最热、北京30最冷，算温差。  Action: calculate(35-30) -> 5
第5步 Thought: 信息已齐全。             Action: Final Answer
✅ 最终答案: 最热广州35℃，比最冷的北京(30℃)高5℃。建议去广州，注意雷阵雨带伞。
```

三个看点印证：
1. **逐步查没并行**--推理驱动行动，每步看完 Observation 再决定下一步（对比 FC 的并行）。
2. **停止判断模型自己做**--第5步"信息已齐全"，不是写死循环次数。
3. **目标导向**--主动建议"去广州、带伞"，超越机械报数据，理解了"旅游"目标。

> 💡 Thought 全程白盒可调试，是 ReAct 最大的教学价值。

---

## 四、三层记忆模型

`run_agent` 每次新建 messages = 无记忆。补齐三层记忆才是完整 Agent：

| 层 | 是什么 | 实现 | 生命周期 |
|---|---|---|---|
| **短期记忆** | 本次会话的对话历史 | `messages` 列表跨轮复用 | 会话内 / 上下文窗口内 |
| **工作记忆** | 当前任务的中间状态/草稿 | ReAct 的 Thought/Action/Observation 序列（就在 messages 里） | 单次任务 |
| **长期记忆** | 跨会话的事实/偏好 | Chroma 存储 + 检索 | 永久（持久化） |

三个关键认知：
- **短期记忆** FC 阶段已学（messages 跨轮复用，见 `chat_multi_turn`）。把 `messages` 提到外层跨轮复用就有了。
- **工作记忆在 ReAct 里是"免费的"**--Thought/Action/Observation 序列天然就是当前任务的 scratchpad，存在 messages 里，不用额外代码。这是 ReAct 相比纯 FC 的隐形好处：**思考过程被记录成工作记忆**，可回溯、可调试。
- **长期记忆是新的**：Chroma 存事实，跨会话。复用 RAG 那套（Chroma + 豆包 embedding），数据源从"简历 PDF"换成"对话事实"。

> 🎯 **一句话区分**：短期是"这次聊过啥"(messages)，工作是"这个任务想到哪了"(Thought 序列)，长期是"我记住这个人/这件事"(Chroma)。

---

## 五、长期记忆闭环（实战）

见 `Code/test_agent_memory.py`。在 ReAct Agent 上加长期记忆，形成闭环：

```
用户输入
   │
   ▼
① 检索长期记忆（Chroma 查相关事实）
   │
   ▼
② 塞进 system prompt（"你记得这些关于用户的事"）
   │
   ▼
③ ReAct 循环（短期 messages + 工作记忆 Thought 序列）
   │
   ▼
④ Final Answer
   │
   ▼
⑤ 提取这轮值得记的事实 -> 存进 Chroma
   │
   ▼（下次对话回到①，形成闭环）
```

这个闭环 = RAG 的"检索-生成"加上"提取-存储"，数据源从 PDF 换成对话事实。

### 代码结构：3 个必懂点

**① 长期记忆 = Chroma 封装（复用 RAG）**

```python
def save_memory(text, collection):           # 存：文本 -> embedding -> Chroma
    mid = hashlib.md5(text.encode()).hexdigest()[:16]  # md5 当 id：跨进程稳定 + 天然去重
    collection.add(ids=[mid], embeddings=[embed(text)], documents=[text])

def recall(query, collection, k=3):          # 查：问题 -> embedding -> Top-K 相似记忆
    if collection.count() == 0: return []
    res = collection.query(query_embeddings=[embed(query)], n_results=k)
    return res["documents"][0]
```

和 RAG 的 `retrieve` 一模一样，只是 collection 从 `resume` 换成 `agent_memory`，数据从"简历块"换成"对话事实"。

> ⚠️ **id 用 md5 不用 `hash(text)`**：Python 3.3+ 默认 `PYTHONHASHSEED` 随机化，`hash()` 跨进程不一致，第二次运行相同事实会被当成新条目重复存。md5 跨进程稳定，且相同事实 md5 相同 -> Chroma `add` 走 upsert -> 天然去重。

**② 提取事实 = LLM 当"记忆筛选器"**

```python
def extract_facts(user_query, agent_answer):
    # 让 LLM 从一轮对话提取"值得长期记住的事实"，闲聊返回空列表
    ... return facts  # 如 ["用户打算下周去上海旅游"]
```

不是所有对话都值得记（"你好"不用记）。让 LLM 判断"这轮有什么值得记的"，自动过滤噪音。**记忆写入要有选择性，否则全是噪音**--这是长期记忆质量的关键。

**③ 闭环 = 每轮 检索->对话->提取->存储**

```python
for q in queries:
    mems = recall(q, collection)                    # ① 检索
    answer, messages = run_agent(q, messages, ...)  # ②③ 对话（短期 messages + 长期 memory）
    for f in extract_facts(q, answer):              # ④⑤ 提取+存储
        save_memory(f, collection)
```

### 演示：三层记忆都看得见

```
第1轮 "我打算下周去上海旅游，查下天气"
  🧠 检索长期记忆: （空）          <- 首次运行，长期记忆空
  ReAct: get_weather(上海) -> 32℃
  💾 存入长期记忆: ["用户打算下周去上海旅游"]

第2轮 "我刚才说要去哪旅游来着？那边天气怎么样？"
  🧠 检索长期记忆: ["用户打算下周去上海旅游"]   <- 长期记忆也命中（会话内已存）
  ReAct: 从短期记忆(messages)知道是上海 -> get_weather(上海) -> 32℃   <- 短期记忆生效！
```

**跨会话验证**（长期记忆的真正价值）：再运行一次 `python test_agent_memory.py`，第1轮就能从 Chroma 召回"用户打算去上海旅游"--这就是长期记忆，跨会话不丢。短期记忆会话结束就没了，长期记忆不会。

### 短期记忆的窗口隐患

`messages` 跨轮复用会一直膨胀（每轮 ReAct 还会追加 Thought/Action/Observation）。短期记忆只能记住"上下文窗口内"的，超窗口会被截断或报错。**这是短期记忆的天花板**，长期记忆（Chroma）就是用来突破它的--把重要事实从 messages 沉淀到 Chroma，窗口满了也不丢。窗口管理（截断/摘要）是阶段4工程化话题。

---

## 六、Agent 站总收尾

带走五件事：

1. **Agent = FC + 自主规划 + ReAct + 停止判断**。FC 单步执行，Agent 目标导向多步规划。
2. **ReAct = Thought/Action/Observation 交替**。CoT 是前身，ReAct 边想边做且推理白盒可调试。
3. **纯 Prompt ReAct vs FC 版是 trade-off**：白盒可调试但解析脆弱 vs 稳定但黑盒。先白盒理解，再工业封装。
4. **三层记忆**：短期（messages）/ 工作（Thought 序列，ReAct 免费）/ 长期（Chroma）。
5. **长期记忆闭环 = RAG 的检索-生成 + 提取-存储**，数据源从 PDF 换成对话事实。简历 RAG 代码直接复用。

### Agent 的进化位置

```
Function Calling              ← 手脚：单步执行 ✅
        │  + 自主规划 + ReAct + 停止判断
        ▼
Agent (ReAct 循环)            ← 大脑：多步规划 ✅
        │  + 三层记忆 + 长期记忆闭环
        ▼
有记忆的 Agent                ← 本站完成 ✅
        │
        ▼
Multi-Agent / Skill / MCP     ← 下一站
```

> 🔗 **下一站钩子**：
> - **Agent -> Skill / MCP**：Agent 的工具是手写的 Python 函数；Skill 是"工具的能力封装"（带 prompt + 资源），MCP 是"标准化工具接入协议"（让 Agent 接外部工具服务器）。Function -> Tool -> Skill 进化链。
> - **Agent -> Multi-Agent**：一个 Agent 干不完的复杂任务，拆给多个 Agent 协作（SubAgent）。
> - **Agent -> LangChain/LangGraph**：手写 ReAct 理解原理后，用框架的 Agent（结构化 FC 版）做工程。LangGraph 编排多 Agent / Workflow。
> - **概念点出**：你正在用的 Claude Code 就是一个 **Harness**（Agent 运行壳），它的 Skill、TodoWrite、工具调用都是本站学的东西的工业实现。
>
> Agent 站完成。下一站按路线：**Skill + MCP**（或先 LangChain 把 Agent 工程化）。
