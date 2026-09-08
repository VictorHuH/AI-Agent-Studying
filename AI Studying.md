



# AI Studying（方向：大模型应用开发、核心：业务 + AI）

## 基本概念

1. 大模型工作原理：逐词判断下个字出现的概率
2. Token：模型处理数据的最小单位，可能是若干/半个英文/中文，分输入 Token 和输出 Token
3. 费用：输入 Token × 输入单价 + 输出 Token × 输出单价。
4. 对AI来说，Markdown格式是最友好的



## Prompt

**定义：**给大模型输入的“自然语言指令”，特点在于 **轻量、灵活、非强约束**，局限在于 **幻觉、不稳定、输出漂移*

**本质：**模型是概率机器，Prompt 决定从概率分布里采哪个结果

**结构化指令（以下每一项不是必要的，非常重要！！！）：**

（1） 【角色】：给AI定义一个匹配任务的角色（可以把问题收敛，减少二义性），如：你是一位软件工程师

（2） 【上下文】：给出背景信息（如 RAG查资料）

（3）【任务】：任务的总体要求（如 ：分析用户评论，输出情绪类别和具体问题）

（4）【输入】：任务的输入信息（如： 耳机音质还行，但戴了半小时耳朵就疼，客服回复也很慢）

（5）【输出格式】：输出的格式描述（ 如： - 情绪：正面/负面/中性） ->   具体如结构化输出（深化"机器可解析"的格式）

（6）【约束】：约束输出（如：只基于评论内容判断，不要脑补）->   具体如Rule（深化"约束怎么写才有效"）

（7）【示例】：必要时给出例子

**分隔符：**（【】、`###`、`---`、XML 标签 `<input>...</input>`）不只是好看，它帮模型区分**指令**和**数据**。

**CoT 思维链** — 让模型"想一想"再答（如：**请一步步思考**）

（1）原理：模型直接给答案没纠错空间，**先写推理等于强制走完推理链**。 

（2）局限简单任务别用：输出变长 = 变贵变慢。

（3）触发方式：

| 方式 | 写法 | 适用 |
|------|------|------|
| Zero-shot CoT | 末尾加"让我们一步一步思考" | 通用，最省事 |
| Few-shot CoT | 例子里带推理过程 | 格式/推理风格要固定时 |
| 显式结构 | "先分析X，再计算Y，最后给答案" | 步骤要可控时 |

**结构化输出** — 要求模型按固定格式（如JSON）输出，让结果***\*可被程序解析\****。

（1）原理：模型直接给答案没纠错空间，**先写推理等于强制走完推理链**。 

（2）**三个层级**：

| 层级 | 做法 | 可靠性 |
|------|------|--------|
| L1 纯 Prompt | 要求"输出格式 JSON" + 给 schema/例子 | 中，偶尔漂 |
| L2 JSON Mode | API 层强制合法 JSON（`response_format`） | 高，但字段不保证 |
| L3 Schema 强制 | Function Calling / Structured Output | 最高，按 schema 校验 |

**Rule 规则约束** — 明确"必须做 / 禁止做"的硬边界，用规则压住模型的概率漂移。

（1）要点：**具体可验证**（"不超过 50 字"可验证，"要友好"等于没说），**抓核心 3-5 条**（太多模型会忽略部分）

（2）写法：

​	\- 正向（必须）：必须用中文、必须先道歉再给方案、必须不超过 50 字

​	\- 负向（禁止）：禁止编造、禁止承诺退款、禁止使用 markdown

​	- 优先级：规则冲突时明确"规则 A 优先于规则 B"。

（3）类似于结构化指令中的**【约束】**



## Function Calling

**定义：** 一种 LLM 调用外部函数的机制。让模型按预先定义好的**工具说明书（JSON Schema）**，决定是否调用工具，调哪个工具，然后由外部代码真正去执行。

**要点（很重要！！！）：**

- 模型自己不执行任何函数（只负责"决策"）， 输入schema，输出**调用结构化请求**
- 模型不一定每次都调工具，由模型自身决定
- 模型进行循环调用，非一次调用解决问题

**Schema例举：**

```
# ===== 1. 工具派发表：模型决策出"调哪个工具"后，代码靠这张表找到对应函数去执行 =====
TOOL_REGISTRY = {
    "get_weather": get_weather,
    "calculate": calculate,
}

# ===== 2. 工具说明书（给模型看的 JSON Schema）=====
# 关键：模型只看这份说明书决策，它看不见上面的函数实现。
# description 写清楚"什么场景该用/不该用"，直接影响模型决策质量（相当于给工具写 Prompt）
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的当前天气。用于查询实时天气信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如'北京'、'上海'"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "精确计算数学表达式。用于大数乘除、复杂运算等模型可能算错的场景。"
                "简单的加减法或两个数比大小不需要调用，模型自己能判断。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '1234*5678'、'(10+20)*3'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]

```

**注意：**

- 工具的 description 就是给模型看的 Prompt
- 模型的 tool_call 消息必须原样回填
- `tool_call_id` 是并行的命脉

**对比RAG：**

- **RAG 解决"模型不知道"** —— 往 context 里塞知识，模型读完再答。本质是**给模型喂资料**。

- **Function Calling 解决"模型做不到"** —— 让模型去调外部能力（API、数据库、计算器、代码解释器）。本质是**给模型装手脚**。

  

## Agent

**定义：**通过LLM，能够自主理解、规划、执行复杂任务的系统

**和 FC关联：**

（1）Agent = Function Calling + **自主规划（循环本身 + Thought 的"计划"） + 显式推理（ReAct) + 停止判断（Final Answer）**。

（2）FC是"单步执行"，Agent 是"给个目标，自己拆步骤、调工具、判断何时停"

（3）FC 是模型"手脚"，Agent 是模型"大脑"。

**核心：** 显式推理、三层记忆模型、停止条件（Final Answer）+ 多步编排（多轮 Thought/Action/Observation 串联成链）

**ReAct 模式**：

1. 一种推理范式，Thought - Action - Observation （推理 - 行动 - 观察）循环交替，模型先"想"(Thought)再"做"(Action)，看完结果(Observation)再想下一步，直到信息够给 Final Answer
2. 有**prompt 版** ReAct（模型格式飘容易解析失败，白盒可见）、**FC版**ReAct（结构化输出稳定，且支持tool_call并行，黑盒不可见）
3. FC Thought 黑盒；ReAct Thought 白盒
4. 除了ReAct -- 还有 Reflexion（带反思）、Plan-and-Execute（先规划再执行）等模式

**三层记忆模型**：

| 层           | 是什么             | 实现                                                         | 生命周期        |
| ------------ | ------------------ | ------------------------------------------------------------ | --------------- |
| **短期记忆** | 本次会话对话历史   | `messages` 跨轮复用                                          | 会话内 / 窗口内 |
| **工作记忆** | 当前任务的中间草稿 | ReAct 的 Thought/Action/Observation 序列（就在 messages 里） | 单次任务        |
| **长期记忆** | 跨会话的事实/偏好  | 如RAG：Chroma 存储+检索                                      | 永久            |

- **工业长期记忆方式**（选一种或组合）：向量库（Chroma/Pinecone/Milvus/pgvector，存事实语义检索）/ KV 库或数据库（Redis/Postgres，存结构化用户画像）/ 知识图谱（实体+关系，多跳推理）/ 摘要文本（定期把对话 LLM 压缩成 summary）。

**和 FC / Workflow 的边界：**

|                      | 谁决定流程                         | 推理是否显式             | 例子                     |
| -------------------- | ---------------------------------- | ------------------------ | ------------------------ |
| **Workflow**         | 你写死（先A再B再C）                | 无                       | LangGraph 固定管线       |
| **Function Calling** | 模型决定调哪个工具（单步）         | 隐藏（content 常空）     | test_function_calling.py |
| **Agent**            | 模型自主规划 + 显示推理 + 判断停止 | 显式（ReAct 的 Thought） | test_agent.py（本站）    |

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

**典型结构：**用户目标 ->Prompt  ->  Planner（任务规划）  ->  调用 Skill  ->  调用 MCP 工具  ->  RAG 查知识  ->  执行任务  -> 输出结果

**Harness **

（1）Agent 的运行壳/运行时，包在模型外面，负责模型不干的"工程杂活"：

- 跑 Agent 循环（调模型 -> 解析输出 -> 执行工具 -> 回填结果）--就是你 `run_agent` 那个循环的工业化版
- 工具注册与调度（提供文件/shell/搜索等工具）
- 上下文与记忆管理（messages、窗口压缩、memory）
- 权限与安全（工具调用授权、危险操作要你确认）
- UI 与流式输出（终端渲染）

（2）**关键区分**：

- Harness 不做决策（不决定调哪个工具）；Agent（模型）做决策。
- **Claude Code = Harness + Agent**。Claude Code  = 一个 Harness（管循环/工具/权限/UI）+ 里面的模型做 Agent 决策。
- 类比：Harness 像游戏引擎，Agent 像游戏逻辑；日常说"Claude Code 是 Agent"指它整体表现出 Agent 行为，精确说是**"跑在 Harness 里的 Agent"**。



## MCP

**背景**：工具侧需要适配 Agent 的格式，Host 侧也要写工具适配代码  ->  M 个 Host × N 个工具

MCP（Model Context Protocol，Anthropic 2024-11 推出）的思路很朴素：

> 别让 Host 和工具直接两两对接了。大家**都去对接同一个标准协议**。

- Host 这边：实现一次"我会讲 MCP 协议" -> M 份
- 工具这边：实现一次"我懂 MCP 协议" -> N 份
- 总成本：**M + N**，不是 M×N
- MCP 是 AI 调工具的"USB-C "，标准化了"模型用工具"

**定义：**AI 与外部系统连接的标准协议，提供统一调用外部的能力，能联系设计工具、数据库、浏览器

**和 FC区别与联系 **：

1. **FC**：LLM 怎么**表达**"我要调工具"（输出 `tool_call`）-- **直接面向 LLM**
2. **MCP**：Host 怎么**跨进程发现和执行**那个工具--面向 Host/Client，**LLM 看不见 MCP**
3. FC 是嘴（模型决策调啥），MCP 是手的标准化接口（怎么跨进程调到）

**工业版 Agent**：FC 决策 + MCP 执行

```
用户提问
   ↓
① LLM 决策：要调 get_weather(上海)        ← FC（嘴）：输出 tool_call
   ↓
② Host 拿到决策，派 MCP Client 去调        ← MCP（手）：标准化执行
   weather Server 的 get_weather
   ↓
③ Server 返回 "32℃，晴"
   ↓
④ 结果回填给 LLM，生成最终回答
```

**本质：**1 个 Host （如Claude Code）装多个 Client，每个 Client 1:1 连一个 Server（自定义服务），故 Host 能同时连多个 Server

```
┌─────────────────────────────┐
│  Host（宿主应用）            │   跑 LLM、做决策的应用
│  ┌─────────┐  ┌─────────┐   │  例：Cursor、Claude Code
│  │ Client  │  │ Client  │   │     
│  └────┬────┘  └────┬────┘   │
└───────┼────────────┼────────┘
        │            │  JSON-RPC（每个 Client 1:1 连一个 Server）
        ▼            ▼
   ┌─────────┐  ┌─────────┐
   │ Server  │  │ Server  │       独立进程，暴露工具/资源/提示词
   │  天气    │  │  GitHub │       例：天气 Server、GitHub Server
   └─────────┘  └─────────┘
```

> **例子： Claude Code 就是 Host**：它里面装着一堆 Client，连着 `Bash`、`Read`、`Edit` 这些内置工具（背后就是 Server）

| 角色       | 是什么                                   | 你见过的例子                 |
| ---------- | ---------------------------------------- | ---------------------------- |
| **Host**   | 跑 LLM 的应用，装着若干 Client           | Cursor、Claude Code          |
| **Client** | Host 内部的连接器，**1:1 连一个 Server** | （本站代码里你会写）         |
| **Server** | 暴露能力的独立进程                       | 天气 Server、GitHub Server： |

> **类比：** Client 是 Host 的"采购员"，管一条到 Server 的连接"封装成黑盒。Host 只管发指令（调哪个工具），不操心怎么连。每个工具一条独立连接、一个独立 Client，互不干扰。

**Client 和 Server 之间的传输分两层：**

1. **协议层：JSON-RPC 2.0** -- 规定"传输内容"
2. **传输层：stdio / Streamable HTTP** -- 规定"怎么传输"

JSON-RPC 2.0： "远程调函数的标准格式"，就三个动作：

| MCP 方法     | 作用                      | 对作用 FC demo 里的                                    |
| ------------ | ------------------------- | ------------------------------------------------------ |
| `initialize` | 握手，交换版本和能力      | （FC 没有，因为 FC 是直接调 API）                      |
| `tools/list` | "你有哪些工具？"          | `TOOLS_SCHEMA`（但 FC 是写死的，MCP 是**动态问**来的） |
| `tools/call` | "帮我调这个工具，参数是…" | `TOOL_REGISTRY[name](**args)`（执行那一步）            |

> **Host 和工具彻底解耦，靠运行时发现，不靠编译时绑定**（**Host 换一个新 Server，Host不用改一行代码**）

stdio / Streamable HTTP："怎么把话传过去"，就两种：

| 传输                | 怎么传                                              | 什么时候用       | 语法                                 |
| ------------------- | --------------------------------------------------- | ---------------- | ------------------------------------ |
| **stdio**           | Server 当子进程跑，靠**标准输入/输出**收发 JSON-RPC | 本地、教学、最简 | mcp.run(transport="stdio")           |
| **Streamable HTTP** | 走 HTTP，一次请求可升级成流式                       | 远程、生产       | mcp.run(transport="streamable-http") |

**总体流程图：**

```
Host 持有多个 Client ──(JSON-RPC over stdio/HTTP)──> 多个 Server
                                    │
                          initialize / tools/list / tools/call
                          （动态发现 + 调用，Host 不绑定具体工具）
```

**stdio模式：**

1. Server是"被调用的服务"，启动后就在**阻塞等标准输入**（stdin）
2. Client 需要拉起子进程并接好 stdin/stdout 管道，通过管道给Server发 JSON-RPC 请求
3. 直接跑Server，没有 Client 给它发请求，啥也不运行

**构建：**任何能将 JSON-RPC 的实现都能算 MCP 实现，推荐用**官方 Node.js/TypeScript SDK** 开发本地服务：

（1）**TypeScript/Node.js**：基于官方 `@modelcontextprotocol/sdk`，自动生成 Zod 参数校验、类型定义、传输层代码

（2）**Python**：基于 FastMCP 框架，自动（@mcp.tool() 装饰器）从函数签名和类型提示生成Schema（读**类型注解** `city: str` -> 生成参数、读**docstring** -> 生成 `description`），无需手写 JSON Schema



## CLI

**定义：**CLI = Command - Line Interface，命令行程序，**三要素**：

- **输入**：命令 + 参数（`--input xx.txt --format json`）
- **输出**：打印到终端（stdout/stderr）
- **结果**：退出码（0 = 成功，非 0 = 失败）

**本质：**Agent 有 **Bash 工具**（ Function Calling：LLM 决定调用 `bash` 这个函数，参数是命令字符串）。 **Agent 天然能用任何 CLI 工具** —— 不需要 MCP，LLM 自己“看”着 `--help` 输出，拼出正确的命令。

> **Agent 能自动调用 CLI，是因为它的 Harness 给它注册了执行 shell 命令的工具；模型负责拼命令，Harness 负责跑命令。**

```
模型（Agent 的大脑）
   ↓  决策：调用 bash 工具，参数 = 命令字符串     ← 这是模型干的唯一一件事
Harness（运行壳，如 Claude Code）
   ↓  执行：在操作系统里真的起进程跑这条命令
操作系统 → 运行 CLI → stdout/退出码回填给模型
```

**调用过程示例：**

```
Claude Code对话框：帮我检查这份合同的风险
LLM 第 1 轮：我不了解这个工具 → 调用 bash("contract-check --help")
              ↓ 运行时执行，--help 输出回填
LLM 第 2 轮：明白了，有 --file 和 --format → bash("contract-check --file a.pdf --format json")
              ↓ stdout 的 JSON 结果回填
LLM 第 3 轮：读结果，总结风险点给你
```

**和MCP区别：**

|          | MCP 形式                                                    | CLI 形式                                  |
| -------- | ----------------------------------------------------------- | ----------------------------------------- |
| 谁来调用 | Cursor、Claude Code 这类 MCP 宿主                           | 人、脚本、CI、任何有 shell 的 Agent       |
| 工具发现 | 宿主启动时自动 `tools/list`，结构化注册                     | LLM 要自己跑 `--help` 去发现              |
| 怎么调用 | 走 MCP 协议，工具以结构化的 `tools/list`、`tools/call` 暴露 | 直接跑命令：`contract-check --file a.pdf` |
| 参数传递 | JSON Schema，类型化、有描述                                 | 字符串参数 + 帮助文档（`--help`）         |

> **MCP 是为 LLM 量身定制的接口，CLI 是为操作系统已有的通用接口——而 Agent 的 Bash 工具让 LLM “降级兼容”了后者。**

**在连接器中的应用：**

| 原文                        | 人话                                                         |
| --------------------------- | ------------------------------------------------------------ |
| **MCP + CLI（标准化协议）** | 连接器是个 MCP Server，通过协议自动注册到模型工具列表里；Server 本身是个命令行程序 |
| **Skill + CLI（内置脚本）** | 连接器是个技能包，模型读说明书学会用法，再通过跑内置脚本来干活 |

一句话压缩：

> **+CLI 是“活谁来干”（都是命令行程序干）；MCP 和 Skill 是“模型怎么学会用它”（协议自动注册 vs 读说明书自学）。**







## Skill

**定义：**把"完成任务所需的一切，如**指令（Prompt：怎么用）+ 工具（Tool：能做什么，如MCP）+ 资源（Resource：参考文件/模板/脚本）**"打包成**按需加载（渐进式披露）**的**可复用**能力包。

**渐进式披露（progressive disclosure）**：

1. 平时包就躺在文件系统里，不占上下文；只有当用户请求匹配到这个 Skill时，Agent 才把它加载进上下文
2. 通常先只加载SKILL 的摘要，加载时才查看具体内容

**渐进式披露解决的问题**：（1） token 浪费 （2）注意力稀释（3） 可能撑爆上下文

**（1）三个层次：**

| 层                                   | 何时加载                    | 装什么                   | 成本 |
| ------------------------------------ | --------------------------- | ------------------------ | ---- |
| L0：frontmatter 的 `description`     | 常驻，模型总扫得到          | 一句话：我是干啥的       | 极低 |
| L1：SKILL.md 的 body                 | 匹配到 Skill 后加载         | 步骤 + 何时用 + 注意事项 | 中   |
| L2：scripts / templates / references | body 指明要用时才 Read/运行 | 大块知识、模板、脚本     | 按需 |

**（2）运行流水线：**

```
① Claude Code 启动
   └─ 扫描 .claude/skills/*/SKILL.md
      └─ 只读 frontmatter（name + description）
         └─ description 进「可用 skill 列表」常驻          ← L0（一直在）

② 你发一句话："考我 RAG"
   └─ 模型拿这句话，和所有 skill 的 description 做语义匹配
      └─ 命中 self-test 的 description（"考我""自测"对上了）
         └─ 加载这个 SKILL.md 的 body 进上下文            ← L1（此刻才进）

③ body 步骤 1 写着"运行 scripts/extract_topics.py"
   └─ 执行脚本，拿 stdout 考点清单                       ← L2（用到才执行）
   body 步骤 3 写着"参考 references/bloom_taxonomy.md"
   └─ Read 这个文件，把 6 层知识注入上下文                ← L2（用到才读）
```

**（3）执行方：**

**「按需加载」是 Harness 干的，不是模型自己干的。**

模型只负责一件事：**判断要不要用这个 Skill**（读 description 语义匹配）。至于扫描目录、读 frontmatter、把 body 注入上下文--**全是 Claude Code 这个 Harness（Agent 运行壳）在做**。模型自己没法"去文件系统翻一个 SKILL.md 进来"。这呼应 MCP 那站"Claude Code 即 Host + Agent"--你写的 self-test，本质上是给这个 Harness 装一个新能力插件。



**标准目录结构：**

```
my-skill/
├── SKILL.md            # 必需。说明书：封面 + 目录 + 操作手册
├── scripts/            # 可选。可执行脚本（Python）
│   └── convert.py
├── templates/          # 可选。模板文件
│   └── report.md
├── references/         # 可选。大块参考文档（按需读，平时不加载）
│   └── api_docs.md
└── assets/             # 可选。其他资源
```

**（1）SKILL.md（根文件，简单SKILL就写这一个）**

**作用**：技能的大脑 + 操作手册，只定义**规则、流程、触发条件、角色、输出规范**，只写自然语言逻辑。

**内容：**包含 **YAML 元数据** 和 **Markdown 正文结构**

**·** **YAML 元数据：**

**核心原则**：描述要**具体明确**，包含 "做什么" 和 "何时用"

| 字段              | 必要性 | 说明                              | 约束                                                         |
| ----------------- | ------ | --------------------------------- | ------------------------------------------------------------ |
| **name**          | ✅ 必需 | 唯一标识符，被引用时的 key        | 小写字母 + 数字 + 连字符，1-64 字符，不首尾连字符，无连续连字符 |
| **description**   | ✅ 必需 | **语义招牌**，技能功能 + 触发条件 | 不超过 1024 字符，包含用户可能使用的关键词（如 "PDF"、"Excel"） |
| **license**       | 推荐   | 开源协议                          | 如 Apache-2.0、MIT，便于共享与复用                           |
| **compatibility** | 可选   | 适配 Agent 框架                   | 如 "Claude Code >= 3.0"、"OpenAI API v1"                     |
| **allowed-tools** | 可选   | 允许调用的工具                    | 如 "web-search"、"file-writer"、"code-interpreter"           |
| **metadata**      | 可选   | 附加信息                          | 如 author、version、created-date 等                          |

> Tool：模型决定"要不要用这个 Skill"，靠的是**读 `description` 做语义匹配**，而非 `name` 

**· Markdown 正文结构：**

**核心原则**：**职责单一**（一个 Skill 只做一件事）、**步骤清晰**（可执行性强）、**容错性**（包含失败处理策略）

| 章节                        | 必要性 | 说明                                              |
| --------------------------- | ------ | ------------------------------------------------- |
| **标题（H1）**              | ✅ 必需 | Skill 名称，与 YAML 中 name 一致                  |
| **何时使用（When to Use）** | ✅ 必需 | 详细触发条件，列举用户可能的提问方式              |
| **角色（Role）**            | 推荐   | 定义 AI 执行该技能时的身份（如 "资深数据分析师"） |
| **操作步骤（Steps）**       | ✅ 必需 | 分步骤执行指南，可标注顺序性（sequential=true）   |
| **输入输出规范**            | 推荐   | 明确输入格式、必填参数、输出格式与示例            |
| **注意事项（Caveats）**     | 推荐   | 边界情况、错误处理、安全风险提示                  |
| **示例（Examples）**        | 推荐   | 输入输出完整示例，帮助 AI 理解预期结果            |
| **参考资料（References）**  | 可选   | 相关文档、API 链接、标准规范等                    |

**（2）scripts/ 脚本目录（可选：帮 AI 干活的代码）**

**作用**：存放**可运行代码**，把 SKILL.md 里描述的复杂计算、接口调用、工具操作等写成自动化脚本。

**放什么文件**：Python / JS / Shell 脚本；API 请求封装、数据处理、文件解析操作；第三方工具调用代码

**（3）resources/ 资源目录（可选：AI 的素材库）**

**作用**：存放**模板、配置、规范、参考文档**，LLM 需要参考但不常驻的活（规范、领域知识）

**放什么文件**：

· 输出模板：邮件模板、会议纪要模板、报告模板（md/json/txt）

· 配置文件：工具参数、关键词库、停用词表

· 参考资料：行业规范、格式标准、话术库

· 示例文件：标准输入输出样例

**（4） tests/ 测试目录（可选：检查技能是否正常）**

**作用**：存放**测试用例、边界用例、自动化测试脚本**，用来验证你的 Skill 有没有逻辑漏洞、异常处理是否正常。

**放什么文件**：输入 → 预期输出 的测试用例；空输入等异常用例；自动化测试脚本



**存放位置（二选一）**：

- **用户级**：`C:\Users\Administrator\.claude\skills\self-test\`（全局，所有项目都能用，推荐--学习本来跨项目）
- **项目级**：`<项目>\.claude\skills\self-test\`（只在该项目里生效）



**SKILL和Prompt、Rules的区别：**

| 对比维度              | Prompt（提示词）             | Rules（规则）                    | Skill（技能）                                 |
| --------------------- | ---------------------------- | -------------------------------- | --------------------------------------------- |
| **颗粒度**            | 最小，单次临时指令           | 中等，约束条款                   | 最大，完整能力包                              |
| **结构形式**          | 纯自由文本，无格式           | 一条条约束条款                   | 标准化工程目录：SKILL.md + 脚本 + 资源 + 测试 |
| **复用性**            | **不可复用**，每次要重新输入 | 可复用，但只是规矩，不能独立执行 | **高度可复用**，一次编写，反复调用            |
| **是否带工具 / 代码** | 无                           | 无                               | 可绑定脚本、文件读取、接口调用                |
| **是否有完整流程**    | 无执行步骤                   | 无执行步骤                       | 有明确执行步骤、触发条件、异常处理            |
| **适用场景**          | 日常临时提问                 | 规范单次输出                     | Agent 长期挂载、企业级自动化                  |
| **生命周期**          | 一次性，用完消失             | 临时约束                         | 可迭代、可测试、可上架                        |

**Skill = 结构化 Prompt + 标准化 Rules + 脚本 + 资源 + 测试**：

（1）极简 Skill：只有`SKILL.md`，本质就是**固定化、结构化的长 Prompt + 规则**

（2）完整 Skill：在此基础上，增加`scripts`执行代码、`resources`模板、`tests`测试

**SKILL和MCP、RAG的区别：**

| 维度               | SKILL（技能）                  | MCP（协议）            | RAG（检索技术）            |
| ------------------ | ------------------------------ | ---------------------- | -------------------------- |
| **定位**           | 业务能力 / 功能模块            | 调用通信标准 / 接口    | 知识获取技术               |
| **层级**           | 上层：业务应用层               | 中层：调度 / 接口层    | 底层：数据 / 知识层        |
| **本质**           | 一套完整干活流程               | 一套对话规则、传输格式 | 检索向量库、文档库         |
| **是否可直接干活** | ✅ 能独立执行任务               | ❌ 只是协议，不能干活   | ❌ 只是查资料，不能执行流程 |
| **落地形态**       | 文件夹：SKILL.md + 脚本 + 资源 | 接口、服务、SDK        | 向量数据库、文档库         |

层级关系：**RAG 提供素材 → MCP 提供调用通道 → SKILL 封装成完整能力给 Agent 使用**



**注意：**

1. 简单的请求即使 description 完美匹配也可能不触发，因为模型判断用基础能力就能处理，会跳过SKILL



**SKILL仓库：**

（1）官方skills仓库：https://github.com/anthropics/skills

（2）skills定义：https://agentskills.io/home

**高效 SKILL：**

（1）Superpower：

**本质：** 一套软件工程方法论框架

**作用：**用方法论约束行为，让能力转化为可靠产出     

https://people.blog.csdn.net/article/details/160896808

https://github.com/obra/superpowers





## Plugin

**定义：**Plugin 是容器，内部可包含一个或多个 Skill、Prompt、MCP 等

**本质：** 能力的分发和管理方式，类似于VS Code Extension

**结构：**

plugin-name/
├── .claude-plugin/
│   └── plugin.json      # Plugin metadata (required)
├── .mcp.json            # MCP server configuration (optional)
├── commands/            # Slash commands (optional)	
├── agents/              # Agent definitions (optional)
├── skills/              # Skill definitions (optional)
└── README.md            # Documentation

**Plugin仓库：**

（1）官方plugin仓库：https://github.com/anthropics/claude-plugins-official

（2）plugins, skills, and MCP servers综合集：https://claudemarketplaces.com/

（3）纯skills仓库：https://skillsmp.com/zh





**主流通信模式：**

- **stdio 模式**：通过命令行启动进程，用标准输入输出通信，**本地个人使用首选**，零网络开销、配置最简单
- **HTTP 模式**：部署成网络服务，适合团队共享、远程调用

**支持 MCP 的主流客户端（2026）：**
- Claude / Claude Code
- ChatGPT（2026 新增 MCP 支持）
- Visual Studio Code（Copilot Chat 支持 MCP）
- Cursor
- MCPJam

**核心理念：** "Build once, integrate everywhere"——一次构建，处处集成



## Rag

**定义：**Retrieval-Augmented Generation（检索增强生成），**先检索，再生成**。

本质：	    

1. 让大模型在回答问题前，先去你的私有数据里"查资料"
2. 所有的向量化操作在喂给大模型之前就完成了！！！

**作用与优势：**

| 问题                       | 说明                               |
| -------------------------- | ---------------------------------- |
| ⏰ 知识截止（数据随时更新） | 训练数据有截止日期，不知道最新信息 |
| 🔒 不识私有数据             | 你的公司文档、个人笔记，它从没见过 |
| 🤥 会幻觉（回答有依据）     | 不知道也硬编，无法溯源原文         |
| 💰 微调成本高               | 更新知识要重新训练，又贵又慢       |

**关键：**【检索】，检索决定上限，生成决定下限。

**核心流程：**

```
1. 索引阶段（离线，一次性）
   文档 → 切块(Chunking) → 向量化(Embedding) → 存入向量库

2. 检索阶段（在线，每次提问）
   用户问题 → 向量化 → 在向量库中找最相似的 Top-K 块

3. 生成阶段（在线）
   [检索到的块 + 用户问题] → 拼成 Prompt → 大模型生成回答
```

**ChunkSize（块大小）**：

|          | 块太大                                                       | 块太小                                             |
| -------- | ------------------------------------------------------------ | -------------------------------------------------- |
| **问题** | 一个块里混了多个主题，检索到了但 LLM 要从一堆无关内容里找答案；还浪费 token | 一个块信息不全，检索到了也答不全；还可能丢失上下文 |
| **类比** | 给 LLM 一整本书让它找答案                                    | 给 LLM 一句半截的话                                |

| 策略                      | 怎么切                                                 | 优缺点                               |
| ------------------------- | ------------------------------------------------------ | ------------------------------------ |
| **固定大小**              | 按字符数切，带重叠                                     | 简单粗暴，但会从语义中间硬切断       |
| **递归切分** ⭐            | 先按段落切，太大再按句子，再按字符，逐级兜底           | 兼顾结构完整和大小限制，**工业默认** |
| **语义切分**              | 用 embedding 算相邻句子相似度，相似度突变处切          | 最智能，但要调 embedding，贵         |
| **父子块 (Small-to-Big)** | 用**小块**检索（精准），返回**大块**给 LLM（上下文全） | 解决"检索精度"和"上下文完整"的矛盾   |

**（1）递归切分：**

① 大块切碎（超 size 时降级字符切）；

② 小块合并（相邻短段落攒到 size 为止）

（2）**父子块 Small-to-Big**

普通检索：**切小了检索准但上下文碎，切大了上下文全但检索糊**。

Small-to-Big ：**检索用小块（精准定位），返回用大块（上下文完整）。**

```
文档 ──切父块(大:整段项目)──▶ 每个父块再切子块(小:几句话)
                                     │
                            子块做 embedding 检索  ← 语义集中，定位准
                                     │
                            命中子块 ──返回所属父块──▶ 给 LLM  ← 上下文全
```

**类比**：父块 = 一整章，子块 = 章里的段落。找的时候按段落定位（精准），读的时候给整章（完整）。

**实现思路：**

1. 切**父块**（大，~600字），每个父块再切**子块**（小，~150字）
2. **只对子块做 embedding**，存入 Chroma；**父块文本存 metadata**
3. 检索命中子块后，从 metadata 取出**父块**返回（去重，多个子块可能同属一个父块）

**Small-to-Big 的代价**

- ✅ **好处**：跨块问题答得全，上下文完整
- ❌ **代价**：返回更多 token（更贵更慢）；父块里可能夹带命中子块无关的内容（命中框架子块，返回整个项目父块）

所以 Small-to-Big **不是默认开启**，而是用在"**信息跨块、需要完整上下文**"的场景（如长文档问答、代码库问答）。简单事实查询用普通检索更省。



**Re-ranking（重排序）:**

一般检索：问题 -> embedding -> 直接取 top-3，问题在于 embedding 检索是**"双塔"粗排**：

> 问题和文档**各自独立**编码成向量，再算相似度。

Re-ranking 改成**两段式**：

```
问题 ──[embedding 粗排]──▶ 召回 10 块（宁多勿漏）──[LLM/cross-encoder 精排]──▶ 取最相关 3 块
       快但粗                    精排：把问题+每个候选拼一起，精细判断相关度
```

**类比**：embedding 检索 = **海选**（快速筛掉绝大部分）；Re-ranking = **决赛评委**（对少量候选精挑细选）。

**粗排是"沾边排序"（看关键词/语义相似），精排是"意图理解"（LLM 判断到底相不相关）**



**检索质量评估**

RAG 评估分两**量化指标**：**检索质量**（关键）+ **生成质量**。

**两个核心检索指标**：

| 指标                | 含义                                | 例子                                       |
| ------------------- | ----------------------------------- | ------------------------------------------ |
| **Hit@K**（命中率） | top-K 里有没有正确块。最朴素。      | 6 题里 4 题命中 -> Hit@3 = 4/6 = 67%       |
| **MRR**（平均排名） | 正确块排名越靠前越好。比 Hit 更细。 | 排第1=1.0，排第2=0.5，排第3=0.33，没命中=0 |

> Hit@K 只看"有没有"，MRR 还看"排第几"。排第1比排第3好，MRR 能体现这个差异。

**关键前提**：评估需要**标注数据**（一组"问题 + 正确块编号"的对照）

**没有标注就没有评估，没有评估就没有优化，标注质量决定评估质量。**



**Agentic RAG（2026 生产范式）：** 用 Agent 动态编排检索流程——判断是否需要检索、检索哪些源、是否需要多轮检索/多路召回、结果如何综合。相比朴素 RAG（固定切块→向量检索→生成），Agentic RAG 显著提升复杂问题回答质量。

**生产级 RAG 关键能力：**
- 混合检索：向量 + 关键词（BM25）+ 知识图谱
- 重排（Reranking）：Cross-encoder 精排
- 查询路由：Agent 根据问题类型选择数据源
- 评估体系：检索准确率 / 答案相关性 / 忠实度三元评估
- 权限与多租户：企业级数据隔离

**详细知识节点：** [[RAG/production-agentic-rag.md]]

**关键概念：**

**1. Embedding（向量化）**

把文本变成一串数字（向量），让计算机能计算**语义相似度**。

- "猫" 和 "小猫咪" → 向量距离很近 ✅
- "猫" 和 "汽车" → 向量距离很远 ❌

这是 RAG 能做**语义检索**（而非关键词匹配）的根本原因。用户问"年假"，能命中写"带薪休假"的文档。

**2. Chunking（切块）**

文档太长，模型一次吃不下，要切成小块。

- 块太大 → 检索不精准，浪费 token
- 块太小 → 丢失上下文
- 常见策略：按字符数切（如 500 字），带重叠（overlap 50 字，防止切断语义）

**3. 向量数据库**

专门存向量、做相似度搜索的数据库。

- 主流：Pinecone、Milvus、Chroma、Qdrant、Weaviate
- 也能用现有数据库：PostgreSQL + pgvector 插件

**4. 相似度检索**

用**余弦相似度（Cosine Similarity）**算两个向量的"方向"是否一致，越接近 1 越相似。

**向量数据库：**

 存向量 + 查向量 + 索引加速 + 持久化

**向量模型和向量数据库：**一个负责把文本变成数字，一个负责存数字、查数字

|               | 向量模型（你申请的豆包 `doubao-embedding-vision`） | 向量数据库（Chroma）          |
| ------------- | -------------------------------------------------- | ----------------------------- |
| **干什么**    | 把文本 → 向量（一串数字）                          | 存向量 + 原文，按相似度查向量 |
| **输入/输出** | 输入文本，输出向量                                 | 输入向量，输出最相似的原文    |
| **算向量吗**  | ✅ 它就是干这个的                                   | ❌ 它不会算，只会存和查        |
| **存数据吗**  | ❌ 不存，调完就忘                                   | ✅ 持久化到磁盘                |
| **类比**      | 翻译官                                             | 档案室                        |





## Memory

**定义：** Agent **持久存储、读取历史交互信息**的模块，让 Agent 能**记住跨会话的信息**，解决上下文有限、对话结束即遗忘的缺陷

**简单分类：**

1.  **短期记忆（Short-Term Memory / Context Window）**
   - 载体：当前对话上下文窗口
   - 时效：单次会话临时存储，窗口满自动丢弃旧内容
   - 存储内容：本轮聊天所有问答、工具调用记录
   - 特点：无需检索，模型直接读取；容量受 token 限制（8k/32k/128k）
2. **长期记忆（Long-Term Memory / External Memory）**
   - 载体：向量数据库（Chroma、Pinecone、Milvus）、本地文件存储
   - 时效：永久保存，可随时检索调取
   - 存储内容：历史聊天摘要、用户偏好、过往任务经验、知识库、人物设定
   - 工作流程：
     1. 记忆写入：对话结束 / 定时触发 → 文本向量化（Embedding）→ 存入向量库
     2. 记忆召回：新提问时，将用户问题做向量匹配，检索相似度最高的历史记忆
     3. 记忆压缩：长对话自动摘要，减少冗余 token，避免占用窗口

**实现类型：**

1.  **ConversationBufferMemory 对话缓存记忆**
   - 最简单实现，完整保存所有原始对话，直接拼接进 prompt。
   - 缺点：长对话 token 爆炸，仅适合短对话场景。
2. **ConversationSummaryMemory 摘要记忆** ⭐
   - 不存完整对话，定时用模型压缩**生成对话摘要**存入长期库。
   - 优势：大幅节省上下文长度，适合长时间连续聊天。
3. **VectorStoreMemory 向量库记忆（工业主流）** ⭐
   - 把历史对话转为向量，语义检索，**只召回和当前问题相关的历史**，而非全部历史。
   - 用户今天问 “怎么学 Vue”，只会召回之前前端相关记忆，过滤无关闲聊。
4. **Entity Memory 实体记忆 **⭐
   - 专门提取人物、物品、偏好、参数等**实体信息**单独存储
   - 示例：记住 “用户喜欢无糖咖啡、家住杭州、从事前端开发”，独立结构化存储。。
5. **Window Memory 滑动窗口记忆**
   - 短期记忆只保留最近 N 轮对话，旧对话自动压缩存入长期库，平衡实时性与成本。

**Claude Code Memory系统：**

1. **底层存储：文件式摘要记忆（ConversationSummaryFileMemory）**

- 不使用向量数据库、无 Embedding 语义检索，靠结构化 Markdown 文本存储对话摘要、实体信息；
- 每次会话达到 token 阈值后，Claude 自动把本轮对话**压缩摘要**，提取用户背景、偏好、项目配置等关键实体写入`MEMORY.md`与**分主题记忆文件**；
- 有硬容量限制（MEMORY.md 默认 200 行上限），超过会自动裁剪老旧无关记忆，内置简易遗忘机制。

2. **信息存储形式：Entity 实体记忆 + 会话摘要记忆二合一**

- **实体记忆**：单独提取结构化关键信息（你的 3 年前端背景、Python 偏好、RAG 学习进度、代码文件路径），分类记录，新开对话直接读取实体不用重复告知；
- **摘要记忆**：完整对话过程压缩成简短笔记，记录任务经验、踩坑记录、项目配置，延续项目开发上下文。

3. **触发加载模式：启动预加载 + 按需读取**

- 会话初始化自动载入核心`MEMORY.md`索引；
- 对话中识别到相关主题（你输入「继续学 Agent」），会主动读取对应分主题记忆文件补全上下文，属于 “按需召回” 的持久记忆设计。

**记忆类型（2026 LangChain 分类）：**

| 类型 | 说明 | 实现方式 |
|------|------|---------|
| Short-term | 当前会话上下文 | LLM 上下文窗口 |
| Conversation | 对话历史 | 消息摘要 + 关键信息 |
| User Preferences | 用户偏好持久化 | 结构化存储 |
| Entity Memory | 客户/产品等实体信息 | 知识图谱/数据库 |
| Wiki Memory | 持久化知识层 | Agent 维护的文件系统 |

**Wiki Memory（2026 新范式）：** 用 Agent 将原始数据压缩为持久化、Agent 可读的知识层。

**和 RAG 的区别**：

1. Memory：存储**自身交互历史、用户私人信息**，服务对话连续性

   RAG：存储**外部公共知识库（文档、网页）**，补充外部专业知识

2. RAG 查询时检索原始块，Wiki Memory 预计算并维护高级别合成。

**实践示例：** DeepWiki（Cognition 为 GitHub 仓库生成文档）、LLM Wiki（Karpathy 通用文件知识压缩）、[[GBrain]]（个人知识管理系统）

**关联系统：** LangMem / Letta / Mem0 / Zep

**主动记忆（2026-07-14 新增）：** OpenWiki Brains 让 Agent 拥有主动记忆——连接 Gmail、Notion、Git 等数据源自动构建 Wiki 知识库。内置记忆是被动的（记住你告诉它的），OpenWiki Brain 是主动的（从你工作的地方获取信息）。参考：[[AI Tools/openwiki-brains.md]]、[[AI Agent/agent-memory.md#OpenWiki Brains]]

**Claude Science（2026-07-15 新增）：** Anthropic 推出面向科学家的 AI 工作台，60+ 科学技能和数据库通过 MCP 连接，Agent 编排 + 审查 Agent 自动检查引用，计算管理自动调度 HPC/GPU，适合学习多 Agent 协作架构。参考：[[AI Tools/claude-science.md]]

**详细知识节点：** [[AI Agent/agent-memory.md]]



## LangChain

**定义：**把脚手架代码抽象成可复用组件，然后用"声明式"的方式（**LCEL**）把它们拼起来的**的编排框架**

**核心组件：**

| 基础代码                                   | LangChain 组件                           |
| ------------------------------------------ | ---------------------------------------- |
| (1) 客户端初始化                           | `ChatModel`                              |
| (2) 提示词                                 | `PromptTemplate`（动态注入工具说明）     |
| (3) 调模型                                 | `ChatModel`（调模型）                    |
| (4) 文本回填                               | `Memory`（管 messages）                  |
| (5) 循环控制 + 停止判断 + Observation 回填 | `AgentExecutor`（运行器）                |
| (6) 工具派发                               | `Tool` + `Toolkit`                       |
| (7) 解析正则 + JSON 容错                   | `OutputParser`--把模型文本变成结构化数据 |
| (8) 从知识库、文档库检索相关文本的模块     | `Retriever` 检索器                       |

> 拆分的目的：避免功能耦合在一个函数里，防止"难演进"

**问题**：每个组件的"调用方式"都不一样。模型用 `create()`，解析用 `search()`，工具用 `fn()`，如果想把它们串成一条流水线，就得为每两个组件之间写一段"胶水代码"。

**LangChain 的解法（LCEL，LangChain Expression Language）**：让所有组件都实现同一个接口 `Runnable`，每个组件都有 `.invoke()` 方法，然后**重载 `|` 操作符**（prompt 的输出喂给 model，model 的输出喂给 parser）：

```python
chain = prompt | model | output_parser
result = chain.invoke({"input": "上海比北京热几度？"})
```

**数据链：**

| 阶段 | 组件                | 输入                                      | 输出                                                         |
| ---- | ------------------- | ----------------------------------------- | ------------------------------------------------------------ |
| 入口 | `chain.invoke(...)` | `dict: {"tool_desc":..., "question":...}` | ——                                                           |
| ①    | `prompt`            | 这个 dict                                 | `ChatPromptValue`（≈ messages 列表 `[SystemMessage, HumanMessage]`） |
| ②    | `model`             | `ChatPromptValue`                         | `AIMessage`（`.content` = 模型那段中文回复）                 |
| ③    | `parser`            | `AIMessage`                               | `str`（纯字符串，就是你 print 出来的那段）                   |

**对比手写**：手写时，每一步的输入输出类型需要维护的messages` 是 list、`resp` 是对象、`content` 是 str），类型对不上就运行时报错。LangChain 把这些"输入输出契约"显式化了，组件拼接时甚至能提前检查兼容性。

**好处：**

1. 连接性：统一接口让"上一阶段输出直接喂下一阶段输入"成立

2. 横切能力："横切关注点"（cross-cutting concerns）在基类里实现一次，所有组件自动获得（每个组件都需要，但和本职无关）：

   | 横切能力            | 你手写时要怎么做         | LangChain（Runnable 统一接口）              |
   | ------------------- | ------------------------ | ------------------------------------------- |
   | **流式输出 stream** | 自己拆 token、自己 yield | `chain.stream()` 直接用，免费               |
   | **批处理 batch**    | 自己写循环、自己并发     | `chain.batch([...])`，免费                  |
   | **异步 ainvoke**    | 自己 `asyncio` 包        | `chain.ainvoke()`，免费                     |
   | **重试 / 回退**     | 自己 try/except + 重试   | `.with_retry()` / `.with_fallbacks()`，免费 |

   > `Runnable` 基类把 `stream`/`batch`/`ainvoke`/`retry` 这些方法实现一次，任何继承它的组件（`ChatModel`、`PromptTemplate`、`OutputParser`）自动白嫖。拼出来的 `chain = prompt | model | parser` 也就自动有这些能力。


**LangChain 的 Agent ：**

1. **`AgentExecutor`（经典版，已 legacy）**：你早期资料里看到的 `from langchain.agents import initialize_agent` / `create_react_agent` + `AgentExecutor`。还能用，但官方标弃用。
2. **`langgraph.prebuilt.create_react_agent`（曾主线，v1.0 起标 deprecated）**：你装包时 `langgraph` 被自动装，就是因为 langchain 1.x 把 Agent 主推到 LangGraph 了。
3. **langchain.agents.create_agent（当前主线，本文件用这个）：** langgraph 退回底层运行时（StateGraph/checkpoint）， prebuilt agent 重新归入 langchain.agents，改名 create_agent（不再绑定 ReAct 范式）。

**并行 tool_call：**

1. Prompt版ReAct只能逐步串行（一个天气查完拿到结果才能走下一个）
2. FC版ReAct可以一轮并行多个 tool_call

**依赖感知：**

1. 第二轮工具如果没跟第一轮一起并行，模型判断了"**第一轮无依赖可并行，而第二轮有依赖要等第一轮的结果**"
2. **数据依赖：模型一轮能输出哪些 tool_call，取决于它"此刻"掌握了哪些信息**

**create_agent 黑盒：**

Prompt ReAct中的`run_agent` 中 `for` 循环 + `if Final Answer: break`，替换为了**LangGraph 图**：

```
        ┌──────────────────────────────┐
        │                              │
START → [agent: 调模型] ──条件边①──→ [tools: 执行工具] ──┘ 回环
            │
            └──条件边②(无tool_call)──→ END
```

| 图要素                 | 干什么                                          | 对应手写 `run_agent`                  |
| ---------------------- | ----------------------------------------------- | ------------------------------------- |
| `tools → agent` 回环边 | 执行完，回模型继续推理                          | `for step in range(...)` 的下一轮     |
| `agent` 节点           | 调模型，拿 `AIMessage`（可能含 `tool_calls`）   | 118-121 行：`create` + 回填 assistant |
| `tools` 节点           | 执行所有 `tool_call`，结果作 `ToolMessage` 追加 | 142-160 行：派发 + 执行               |
| 条件边①（agent→tools） | 有 `tool_call`？去执行                          | 隐含：解析到 Action 就执行            |
| 条件边②（agent→END）   | 没有 `tool_call`？任务完成                      | 136-140 行：`if Final Answer: return` |

**关键认知**：

1. 图把"命令式的 `for` + `break`"变成了"声明式的 **边 + 条件路由**"
2. **循环**（for）靠 `tools → agent` 回环边表达
3. **停止**（break）靠"条件边路由到 `END`"表达



**LangChain 把 Agent 迁到 LangGraph 的根本原因：**

1. 图是声明式的，可可视化、可组合、可自定义，而命令式的 `for` 只能跑这一种循环
2. 想加个"人工审批节点"、想加个"并行分支"、想改停止条件，都是改图结构，不动节点内部逻辑。



**recursion_limit（递归上限，LangGraph 默认 25）：**

- 它**不在图结构里**（非边非节点），是运行引擎的外部约束，跟图本身分离
- 每经过一个节点计数 +1，超过 25 就抛 `GraphRecursionError` 强制停，是运行时的硬计数器
- **停止其实有两套机制**：1、条件边②路由到 `END`（模型自主判断"信息够了"）；2、`recursion_limit` 超限抛错（防死循环）



**Retriever：**

1. 原RAG代码里，需要手动调 `retrieve方法` -> 拿 docs -> 调 `answer(q, docs)`，**检索和生成是分开写的两步**

2. **LangChain 的 Retriever** 是个 `Runnable`（跟 `model` 一样），能用 `|` 接进链，跟你学的 `prompt | model | parser` 拼一起，

   是将RAG 课三步（索引/检索/生成）里**"检索"**被组件化的样子

   输入：query 字符串

   输出：`Document` 列表（每个 Document 有 `page_content` 和 `metadata`）

   关键：`vectorstore.as_retriever()` 把向量库**变成** Runnable

   ```python
   chain = retriever | format_docs | prompt | model | parser
   #              ↑ Runnable，输出 Document 列表
   #                          ↑ 把 Document 列表拼成字符串
   ```

   ```python
   # ===== 1. 向量库 + Retriever（对应手写 test.py 18-26、95-102 行）=====
   # 手写：chromadb.PersistentClient + get_collection + retrieve 函数（独立调用）
   # LangChain：Chroma 封装 + as_retriever() 把向量库变成 Runnable
   # 【这一站的魔法】as_retriever()：把"查向量库"这个动作变成"链的一环"
   vectorstore = Chroma(
       collection_name="resume",          # 同 test.py COLLECTION_NAME
       embedding_function=embeddings,
       persist_directory="./chroma_db",   # 同 test.py，复用已有数据，不重建
   )
   retriever = vectorstore.as_retriever(search_kwargs={"k": 3})   # 对应 retrieve 的 k=3
   
   # ===== 4. 拼成 RAG chain（对应手写 test.py 主流程的 retrieve -> answer 两步）=====
   # 这是这一站的核心：retriever 接进链，跟 prompt/model 平起平坐。
   # 数据流见下方"数据流图"。
   chain = (
       {"context": retriever | format_docs, "question": RunnablePassthrough()}
       | prompt | model | StrOutputParser()
   )
   ```

   **`RunnablePassthrough()`**：query 字符串要**分两路**用--retriever 要拿它去检索，prompt 也要拿它当问题。`RunnablePassthrough()` 就是"原样透传输入"，让 query 既能进 retriever，又能原样当 question。

   **数据流图**

   ```
   输入: "他用过什么部署技术？"  (字符串)
      │
      ▼
   ┌─────────────────────────────────────────────────────┐
   │ {"context": retriever|format_docs, "question": ...} │  ← 并行字典：同时算两路
   └─────────────────────────────────────────────────────┘
      │ query 分两路                          │
      ▼                                       ▼
   retriever(query)                    RunnablePassthrough()
   → [Doc, Doc, Doc]                   → 原样透传 query 字符串
      │                                       │
      ▼                                       │
   format_docs()                              │
   → "块1\n---\n块2\n---\n块3"              │
      │                                       │
      └───────────────┬───────────────────────┘
                      ▼
               dict {context: "...", question: "..."}
                      │
                      ▼
               prompt 填 {context} {question}
                      │
                      ▼
               model → AIMessage
                      │
                      ▼
               StrOutputParser → 最终答案字符串
   ```



**LangChain 和 LangGraph 的关系：**LangChain 是高层组件库（写应用用的），LangGraph 是底层图引擎（真正跑循环/状态的）。

|          | LangChain                              | LangGraph                                         |
| -------- | -------------------------------------- | ------------------------------------------------- |
| 角色     | 组件超市 + 快捷菜谱                    | 厨房灶台（执行引擎）                              |
| 给你看的 | `ChatModel`/`Tool`/`create_agent`/LCEL | `StateGraph`/`State`/`nodes`/`edges`/`checkpoint` |
| 何时用   | 简单链、标准 Agent（用现成的）         | 复杂工作流：多节点/分支/并行/人工审批/断点恢复    |

演进关系：早期 LangChain 用 `AgentExecutor`（命令式 `for` 循环）做 Agent；后来发现 Agent 本质是"有状态、有循环、有分支"的图，命令式 `for` 表达不了复杂场景，于是造了 LangGraph 做图引擎；**1.x 后**：`langchain.agents.create_agent` 是入口，**内部用 LangGraph 跑**。

所以你装包时 `langgraph` 自动装--它不是可选的，是 LangChain 跑 Agent 的底层引擎。

边界建议：简单场景用 LangChain 现成组件（如 `create_agent`）就够；需要自己画节点/边/分支时，下沉到 LangGraph 自定义图。



**LangChain 的 `create_agent`和Claude Code关系：**

1. 两者都是同一个 ReAct/Agent 循环**：消息 -> 模型决策调工具（推理） -> 执行 -> 结果回填观察 -> 再决策 -> 直到完成。**
2. 差异只在规模：Claude Code 工具更多（Read/Write/Bash/Grep...）、有 Harness（管上下文/权限/子 Agent/记忆）、模型是 Claude（agentic 训练更深），但核心架构同构。



**LangChain 与 Vue/React：**

1. 共同点：都是"组件化 + 声明式编排"的框架思维。Vue 用 `template` 把 UI 组件拼起来，LangChain 用 LCEL (`|`) 把 LLM 组件拼起来。

2. 管的领域不同：Vue 管"数据怎么变成界面"（UI 渲染），LangChain 管"prompt/model/tool 怎么拼成应用"（LLM 编排）

3. 映射表：

   | 前端                          | LLM 对应                               | 说明                                                         |
   | ----------------------------- | -------------------------------------- | ------------------------------------------------------------ |
   | Vue/React（框架）             | **LangChain**                          | 组件化 + 编排                                                |
   | Element Plus / Antd（组件库） | LangChain 自带的 ChatModel/Tool/Prompt | ⚠️ 前端框架和组件库是分开的，LangChain 揉一起了               |
   | Pinia / Vuex（状态管理）      | **LangGraph State**                    | 状态在节点/组件间流转                                        |
   | **XState**（状态机/状态图库） | **LangGraph**                          | **最贴切**：都是"状态 + 节点 + 边 + 条件路由"表达有循环有分支的流程 |
   | JSX / template（编排语法）    | LCEL (`|`)                             | 声明式编排语法                                               |
   | Vite / Webpack（构建）        | （无直接对应）                         | LLM 应用部署走 FastAPI，不是构建打包                         |

   **LangGraph ≈ XState** 这个类比特别值得记住：你 `create_agent` 内部那张图（agent/tools 节点 + 条件边 + END），跟 XState 的"状态机"是同一个东西。前端做复杂交互流（多步表单、引导流程）会上 XState；LLM 做复杂 Agent/工作流就上 LangGraph。

4. 关键差异：

   **前端生态分层清晰**：Vue 管渲染、Antd 管组件、Pinia 管状态、Vite 管构建--各管一摊，可替换。

   **LLM 生态 LangChain 想全包**：框架、组件库、编排、状态、甚至文档加载/评估/部署，全揉一起。这就是为什么它**臃肿、API 反复横跳**、依赖拉一大串。也是为什么 `langgraph` 被拆出来--大家受不了"一坨"，需要个专注的图引擎。

5. LLM 领域有类似 Vue/Antd 这样的框架吗：有竞品，但**还在混战，没有 Vue/React 双雄那样的稳定格局**：

   | 框架                        | 定位               | 类比                   |
   | --------------------------- | ------------------ | ---------------------- |
   | **LangChain**               | 全能型，组件最多   | 像"什么都做的全栈框架" |
   | **LlamaIndex**              | 偏 RAG/数据连接    | 更像"数据层框架"       |
   | **Haystack**（deepset）     | 偏企业/搜索        | 偏企业级               |
   | **Semantic Kernel**（微软） | 多语言、偏 C# 生态 | 微软系                 |

   前LLM 这边选哪个框架，更多是看你做啥（Agent 偏 LangChain，RAG 偏 LlamaIndex），且**很多团队选择"不用框架、自己拼"**--因为框架的抽象成本有时比它省的多。





## LangGraph

**定义：**LangChain和LangGraph都是大模型本地应用构建框架。

LangChain 是「组件 + 管道」（LCEL 的 `prompt | model | parser`），适合线性流水线；

LangGraph 是「状态 + 图」**，适合**有分支、有循环、有并行的复杂流程

```HT
        ┌──────────────────────────────┐
        │                              │
START → [agent: 调模型] ──条件边①──→ [tools: 执行工具] ──┘ 回环
            │
            └──条件边②(无tool_call)──→ END
```

| 图要素                 | 干什么                                          | 对应手写 `run_agent`                  |
| ---------------------- | ----------------------------------------------- | ------------------------------------- |
| `agent` 节点           | 调模型，拿 `AIMessage`（可能含 `tool_calls`）   | 118-121 行：`create` + 回填 assistant |
| `tools` 节点           | 执行所有 `tool_call`，结果作 `ToolMessage` 追加 | 142-160 行：派发 + 执行               |
| 条件边①（agent→tools） | 有 `tool_call`？去执行                          | 隐含：解析到 Action 就执行            |
| 条件边②（agent→END）   | 没有 `tool_call`？任务完成                      | 136-140 行：`if Final Answer: return` |
| `tools → agent` 回环边 | 执行完，回模型继续推理                          | `for step in range(...)` 的下一轮     |

**心智模型**： **状态在 State 里，逻辑在节点里，路由在边上**，三者分离

- **State** 就是一个 TypedDict，定义图里有哪些字段在节点间流动：

```python
from typing import TypedDict
class AgentState(TypedDict):
    messages: list   # 对话历史
    step: int        # 走到第几步
    done: bool       # 是否结束
```

- **节点**就是一个函数：接收 state、干活、返回"更新"：

```python
def agent_node(state: AgentState) -> dict:
    msgs = state["messages"]             # 读
    reply = model.invoke(msgs)           # 干活
    return {"messages": msgs + [reply]}  # 返回更新
```

**关键点：**

1. **节点返回的是「更新」不是完整 state**--只写这次要改的字段，没改的字段原样保留。
2. **图自动 merge**：把返回值合并回 state，下一个节点拿到的就是新 state。
3. **为什么能支撑回环边**：state 在循环**外面**。每次回到 agent 节点，它拿到的 state 已含上一轮 tools 节点写回的结果。循环不是"重新执行"，而是"**带着累积的状态再走一圈**"。

**reducer**：

- **字段的合并策略，LangGraph 的默认行为是覆盖；加了 reducer 就按 reducer 的规则合并（如追加）。**
- 对应手写Agent的`messages.append(...)` 

```python
# 写法 A：只返回新增的一条
def tools_node(state):
    result = call_tool(...)
    return {"messages": [result]}                       # 只放新消息

# 写法 B：手动拼整个列表
def tools_node(state):
    result = call_tool(...)
    return {"messages": state["messages"] + [result]}   # 新旧一起返回
```

- **没 reducer** 时，写法 A 会让 messages 只剩这一条新消息，**历史全丢**；写法 B 能对，但每个节点都要手动拼，累且容易写错。
- **有 reducer** 时，写法 A 就够了--图会自动把 result 追加到原有 messages 末尾。

给字段加 reducer 的写法：

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

# `add_messages` 就是一个 reducer 函数，它告诉图：**"messages 这个字段，合并时不是覆盖，而是列表追加（并按 id 去重）"**
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]   # ← 关键：加 reducer
    step: int
    done: bool
```

**是否需要reducer**：字段更新是「和旧值合并」还是「直接覆盖旧值」？

| 字段                     | 合并语义                   | 类型 | 要 reducer？ |
| ------------------------ | -------------------------- | ---- | ------------ |
| `messages`               | 追加（新消息拼到旧消息后） | list | ✅ 要         |
| `step`                   | 覆盖（直接 set step=2）    | int  | ❌ 不要       |
| `done`                   | 覆盖（直接 set done=true） | bool | ❌ 不要       |
| `turn_count`（每步 +1）  | 累加                       | int  | ✅ 要         |
| `candidates`（整体替换） | 覆盖                       | list | ❌ 不要       |

- 替换型字段：不用 reducer（默认覆盖即可）

- 累积型字段：

  - **用 reducer**：节点只返回增量，图自动合并。适合 messages 这种"纯追加、每个节点都追加"的简单语义。

  - **不用 reducer**：节点自己读旧值、算好、返回完整新值。适合 retry_count 这种"有时累加有时重置"的混合语义。

    

**LangGraph 拼图就三件事：加节点、加边、设入口，最后编译**。

```python
from langgraph.graph import StateGraph, END

# 1. 建图，告诉它用哪个 State
graph = StateGraph(AgentState)

# 2. 加节点：名字 -> 函数
graph.add_node("agent", agent_node)   # "agent" 是节点名，agent_node 是函数
graph.add_node("tools", tools_node)

# 3. 加边：两种
#    a) 普通边（固定流转）：A 完了一定去 B
graph.add_edge("tools", "agent")      # tools 跑完一定回 agent ← 这就是回环边

#    b) 条件边（动态路由）：A 完了去哪，看 state
graph.add_conditional_edges(
    "agent",                          # 从哪个节点出发
    route_fn,                         # 路由函数：接收 state，返回字符串
    {"continue": "tools", "end": END} # 路由表：返回值 -> 目标节点
)

# 4. 设入口 + 编译
graph.set_entry_point("agent")
app = graph.compile()                 # 编译成可执行对象
```

**普通边 vs 条件边**：

|        | 普通边 `add_edge` | 条件边 `add_conditional_edges` |
| ------ | ----------------- | ------------------------------ |
| 流转   | 写死：A → B       | 动态：A → ?                    |
| 决定者 | 代码（你写死）    | state（路由函数读 state 决定） |
| 例子   | tools → agent     | agent → tools 或 END           |

**路由函数 `route_fn`**：

```python
def route_fn(state: AgentState) -> str:
    last_msg = state["messages"][-1]
    if last_msg.tool_calls:           # 模型要调工具
        return "continue"             # -> 路由表查到去 tools
    return "end"                      # 模型给最终答案了 -> 去 END
```

它就是：**接收 state、返回一个字符串**，图拿这个字符串去路由表里查下一步去哪。

> 这就是 `create_agent` 内部的"条件边路由"。你上一站一直在用这套机制，只是被 LangChain 包成了 `create_agent(模型, 工具)` 一行调用。现在壳拆了，你能看见每一根线。

**跑起来**：

```python
app.invoke({"messages": [{"role": "user", "content": "上海天气怎么样"}]})
```

流程：agent 调模型 → 模型要调工具 → 条件边路由到 tools → tools 执行 → 普通边回 agent → agent 再调模型 → 模型给答案 → 条件边路由到 END。**一个完整的 ReAct 循环。**



 **checkpointer** ：把 state 存盘，实现**会话接续**。

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
app = graph.compile(checkpointer=memory)   # 编译时传入

# 用 thread_id 标识"这是哪个会话"
config = {"configurable": {"thread_id": "user-001"}}

# 第一次：自我介绍
app.invoke({"messages": [{"role": "user", "content": "我叫小明"}]}, config)
# 第二次：只传新消息，不传历史
app.invoke({"messages": [{"role": "user", "content": "我叫什么？"}]}, config)
# -> 模型能答出"小明"--checkpointer 自动把上次的 state 取回来了
```

三个关键点：

1. **thread_id = 会话标识**。同一个 thread_id，state **跨 invoke 累积**；不同 thread_id 互不干扰（多用户隔离）。
2. **第二次 invoke 只传新消息**，checkpointer 自动取回上次 state、追加新消息、再跑图。
3. **每次节点执行后都存盘**--中途崩了，下次同 thread_id 能从最近 checkpoint 恢复。

**和 Agent 站 Chroma 长期记忆的区别（别混淆！）**

你大概率在想："这不就是 Agent 站的长期记忆吗？" **不是**，两者层次不同：

|          | LangGraph checkpointer      | Agent 站 Chroma 长期记忆       |
| -------- | --------------------------- | ------------------------------ |
| 存什么   | 完整 state（messages 全量） | 从对话提取的事实               |
| 怎么取   | 按 thread_id **精确取回**   | 按**语义相似度检索**           |
| 解决什么 | 会话接续（接着上次聊）      | 跨会话知识（记得用户去过上海） |

一句话：**checkpointer = 会话级持久化（把短期记忆存盘）；Chroma = 跨会话语义记忆（提取事实做检索）。**

**Human-in-the-loop**

 checkpointer 最酷的用法：：你的 Agent 要执行一个**危险工具**（删数据库），你不想让模型人工确认后才执行。

LangGraph 怎么做？编译时加一个参数：

```python
app = graph.compile(
    checkpointer=memory,
    interrupt_before=["tools"]   # ← 在进入 tools 节点前暂停
)

config = {"configurable": {"thread_id": "1"}}

# 第一次 invoke：图跑到 tools 节点前就停了
result = app.invoke({"messages": [{"role": "user", "content": "删掉用户表"}]}, config)
# state 存在 checkpointer 里，图"卡"在 tools 前面

# 人工看一眼：模型要调什么工具？
last = result["messages"][-1]
print(last.tool_calls)   # 看模型想干啥

# 确认没问题，让图继续跑（传 None = "接着上次停的地方跑"）
result = app.invoke(None, config)
```

**关键点：**

1. **`interrupt_before=["tools"]`** 告诉图"进入 tools 节点前先停一下"。也可以用 `interrupt_after`，或者在节点函数里用 `interrupt()` 函数动态中断。
2. **第一次 invoke 跑到 tools 前就停**，state 存在 checkpointer 里。**没有 checkpointer 这事做不到**--图停下来 state 不能丢。
3. **`invoke(None, config)`** 传 None 表示"不传新输入，接着上次停的地方跑"。人工确认后让它继续。

**价值**

| 场景               | 没检查点           | 有检查点 + interrupt           |
| ------------------ | ------------------ | ------------------------------ |
| 危险工具（删数据） | 模型一调用就执行了 | 停下等人确认                   |
| 审批流             | 做不到             | Agent 提方案 -> 人审 -> 才执行 |
| 纠偏               | 做不到             | 看到 Agent 走错路，停下来改    |

> 这呼应你 Agent 站讲的"护栏"：工具滥用不能光靠 prompt 规则约束（Rule 是最弱护栏），用 interrupt 在**执行前硬拦截**。Rule 是软约束，interrupt 是硬约束。

**HITL 和 Claude Code 的工具确认本质上是一个东西，同一个概念，不同实现层**

Claude Code 每次调工具前问你"允许执行这个 bash 吗？"，就是 HITL 的典型形态：**工具执行前暂停 -> 人确认 -> 才执行**。

|        | LangGraph 的 HITL                           | Claude Code 的 HITL         |
| ------ | ------------------------------------------- | --------------------------- |
| 实现层 | 图编排层                                    | harness 权限层              |
| 机制   | `interrupt_before=["tools"]` + checkpointer | permission mode（权限系统） |
| 谁用   | 你写图时调的 API                            | 用户用 Agent 时配的开关     |

**LangGraph 和 Claude Code 没有直接代码关联，但抽象高度同构。**

- Claude Code 是 Anthropic 官方的 Agent CLI，运行时是 Anthropic 自己实现的，**不是用 LangGraph 搭的**。
- 但它内部的 **Agent loop** 和 LangGraph 的图是**同一个抽象的不同实现**。

| LangGraph 概念           | Claude Code 里的对应                    |
| ------------------------ | --------------------------------------- |
| 回环边 `tools -> agent`  | Agent loop（模型 -> 工具 -> 模型 循环） |
| 条件边路由到 END         | 模型说"做完了"就停                      |
| tools 节点               | 调内置工具 / MCP 工具                   |
| State.messages 累积      | 对话 context                            |
| `interrupt_before`       | 权限确认弹窗                            |
| Checkpointer (thread_id) | `/resume` 续接会话                      |

而且不止 LangGraph--**你前几站学的概念，在 Claude Code 里都有产品级体现**：

| 你学过的         | Claude Code 里的体现                           |
| ---------------- | ---------------------------------------------- |
| Function Calling | 每次调工具就是 FC 决策                         |
| MCP              | Claude Code 是 Host，`.mcp.json` 装外部 Server |
| Skill            | Claude Code 的 Skill 系统（渐进式披露）        |
| Agent loop       | = LangGraph 的回环图                           |
| HITL             | = 权限确认                                     |

> 所以 **Claude Code 是一个生产级 Agent harness**，它把你学的 RAG/Prompt/FC/Agent/MCP/Skill/LangGraph 概念**全部产品化了**。你每天用它，就是在用这些概念的成品。这也是为什么这几站学得顺--你一直有个活样板在旁边跑着。





LangSmith是针对LangChain的应用进行测试、监控和分析的平台





## 多Agent / Subagent 

**定义：** 多个 Agent 协作完成任务，主 Agent 编排子 Agent 执行

**本质：**研究 **Agent 之间的协作架构**。它有三个核心问题要回答：

1. **什么时候该拆**：什么任务用一个 Agent，什么任务该拆成多个？
2. **怎么拆**：按什么维度拆？按职能（研究/编码/测试）？按角色？
3. **怎么协作**：拆完之后，Agent 之间怎么传递信息、谁指挥谁

**多 Agent ≠ SubAgent**，它们是两种不同的协作关系：

| 维度     | SubAgent（子代理）                                        | Multi-Agent（多代理）                    |
| -------- | --------------------------------------------------------- | ---------------------------------------- |
| 关系     | **层级**：主 Agent 调用子 Agent，类似函数调用             | **对等 / 协作**：多个 Agent 之间平等协作 |
| 比喻     | 你（主管）把一个子任务交给下属去做，下属做完汇报          | 一个团队里几个同事各自负责一块，互相沟通 |
| 控制权   | 主 Agent 全程掌控，子 Agent 只负责自己那一块              | 没有绝对主导者，靠协议/机制协调          |
| 典型实现 | Claude Code 的 Task 工具、OpenAI 的 function calling 嵌套 | CrewAI、AutoGen 的群聊                   |

多个 Agent怎么拆分取决于**"任务本质"（比如「写一篇技术博客文章」可分为调研、写作、校对）**

**多 Agent 协作模式**

**1、串行 / 流水线（Sequential Pipeline）**

```
调研Agent ──→ 写作Agent ──→ 校对Agent
```

前一个的输出，是后一个的输入。像工厂流水线。

- 特点：**顺序固定、单向、可控**
- 缺点：慢（必须一个接一个），且后置 Agent 完全依赖前置 Agent 的产出质量

**2、并行（Parallel）**

```
        ┌→ 调研Agent A（查LangGraph资料）─┐
调度者 ─┼→ 调研Agent B（查CrewAI资料）────┼→ 汇总Agent
        └→ 调研Agent C（查AutoGen资料）─┘
```

多个 Agent 同时干活，最后汇总。

- 特点：**快、能处理多源信息**
- 缺点：最后要"合并"，合并逻辑可能很复杂（三个 Agent 写出来的东西风格不一）

**并行搜集 + 串行加工** -- 混合模式（Hybrid）。真实世界里几乎没有"纯串行"或"纯并行"的多 Agent 系统，都是混合的。

**3、层级（Hierarchical）**

**层级模式 = 一个主 Agent 做总指挥 + 多个子 Agent（即子Agent） 干活**

「**调度者**」即主 Agent，被指挥的即 子Agent

- 把搜集任务**拆成几份**（拆几个源）
- **分派**给并行的子 Agent
- 等它们都回来后**汇总**
- 再把汇总结果传给下一站（写简报 Agent）

**4、网状 / 群聊（Network / Group Chat）**

```
AgentA <---> AgentB
  ^           ^
  |           |
  v           v
AgentC <---> AgentD
```

无固定指挥者，Agent 之间**自由对话**，谁该发言由某种协议决定（比如轮询、或一个"主持人"判断该轮到谁）。如AutoGen 的群聊

- 特点：**灵活、能涌现出协作**
- 缺点：**不可控、容易跑偏、token 烧得快**--几个 Agent 吵起来没完

**网状和并行模式的区别：**

| 维度             | 并行                       | 网状                     |
| ---------------- | -------------------------- | ------------------------ |
| Agent 间是否通信 | **不通信**，只对调度者汇报 | **互相通信**，自由对话   |
| 结构             | 星型（中心是调度者）       | 网状（任意两点可连）     |
| 协作深度         | 各干各的，最后合并         | 互相影响、动态迭代       |
| 控制权           | 有明确调度者               | 无固定指挥者，靠协议协调 |

**Send 动态扇出**

LangGraph 的 `Send` 就是解决这个的。它的作用：

> 分派节点不返回普通 state 更新，而是返回一个 **`Send` 列表**，每个 `Send` 代表"派发一个并行任务给某节点，带上这份任务数据"。

类比快递站调度员：看今天有几单（sources），就派几个快递员出去，每人的目的地不同。**调度员不需要提前知道有几单**，看列表现派。这就是"层级模式里调度者动态分派"的代码落地。

```python
# 假设输入 `sources = ["36kr", "huxiu", "techcrunch"]`，`topic = "AI"`：
dispatch_node 读 sources 列表，返回 3 个 Send：
    ├─ Send("collect", {"source":"36kr",        "topic":"AI"})
    ├─ Send("collect", {"source":"huxiu",       "topic":"AI"})   ──并行──> 3 个 collect_node 同时跑
    └─ Send("collect", {"source":"techcrunch",  "topic":"AI"})

每个 collect_node 各自返回 {"raw_news": [一条资讯]}
    │
    └─ reducer(operator.add) 把 3 个 list 拼接：
       raw_news = ["[36氪]AI赛道...", "[虎嗅]AI行业...", "[TC]Global AI summit..."]
```



**SubAgent 的核心：**

1. 把"派子 Agent"做成主 Agent 的**一个工具（@tool）**
2. 要不要派生子任务由主Agent决定

|        | 多 Agent           | SubAgent                     |
| ------ | ------------------ | ---------------------------- |
| 决策者 | 你（写图的人）     | 主 Agent（模型）             |
| 时机   | 编译时固定         | 运行时动态                   |
| 像什么 | 流水线（图纸画好） | 主管派活（现场看情况派给谁） |

**三层结构**：

```
① 子 Agent（调研员）= 一个标准 ReAct 图（复用你 demo 的模式），编译成 sub_app
② delegate_research 工具 = @tool，内部调用 sub_app.invoke → 把子 Agent 当工具用
③ 主 Agent（研究助手）= 另一个 ReAct 图，工具集只有 delegate_research
```

**SubAgent 的全部灵魂在第 ② 层**：主 Agent 收到任务，自己决定调不调它，需要就 `tool_call` 调用 `delegate_research`，工具内部启动一个子 Agent 去干活，干完把结果作为返回值回主 Agent，主 Agent 拿到继续往下走。

**SubAgent 示例：**

```
用户问："帮我研究一下 GLM-5.2 的能力边界，给个评估"

主 Agent（研究助手）
   │  判断：这题需要深入调研，我亲自搜会污染上下文，派个子 Agent 去
   │
   ├─ tool_call: delegate_research("GLM-5.2 能力边界")
   │
   │        子 Agent（调研员，独立 ReAct 循环）
   │           └─ 用自己的 search 工具：搜->看->再搜->...->总结
   │           └─ 返回调研结论（独立上下文，不污染主 Agent）
   │
   │  工具返回：调研结论
   │
   └─ 主 Agent 拿到结论，整合成最终评估给用户
```

这个场景体现 SubAgent 的两大价值：

1. **上下文隔离**：主 Agent 不被搜索垃圾塞满，保持清爽做决策
2. **专业分工**：子 Agent 有自己的 prompt + 工具，专精调研



## 工作流 / AI Workflow

**定义：** AI 应用中的多步骤自动化执行流程

**与 Agent 的区别：**

| Agent    | Workflow   |
| :------- | :--------- |
| 有自主性 | 固定流程   |
| 可决策   | 按步骤执行 |
| 动态     | 静态       |

**Prompt Caching（2026 关键优化技术）：**

- 利用 LLM 平台的 Prompt Cache 功能复用相同前缀
- 系统提示词 / 共享上下文只计一次 Token
- 可降低 Coding Agent 成本 50-90%
- LangChain Deep Agents 通过 PromptCacheMiddleware 内置支持
- **优化策略**：启用缓存 + 上下文瘦身 + 复用上下文 + Subagent 隔离
- 关联 [[Prompt Engineering]] / [[Context Engineering]] / [[AI Coding]]

**详细知识节点：** [[Prompt & Context/prompt-caching.md]]



## AI Security

**定义：** AI Agent 的安全防护工程体系

**三大方向（2026 Q2）：**
1. **Agent 代码执行安全**：WASM + QuickJS 实现进程内沙箱执行 Agent 生成的不可信代码
2. **Jailbreak 评估标准**：Anthropic + Amazon + Microsoft + Google 联合提出 Glasswing 框架
3. **模型安全栈**：GPT-5.6 Sol 分层防护体系（高风险过滤 + 压力测试 + 实战攻击加固）

**详细知识节点：** [[AI Security/agent-security.md]]



## Models & SDK（2026 最新模型）

**GPT-5.6 系列（2026-06-26）：**
- Sol（旗舰）→ 最强推理 + Ultra Mode Subagent 并行（$5/$30 per 1M tokens）
- Terra（均衡）→ 性能对标 GPT-5.5，价格 2x 便宜（$2.50/$15 per 1M tokens）
- Luna（低成本）→ 最强性价比（$1/$6 per 1M tokens）

**Prompt Caching 升级（GPT-5.6）：**
- 显式缓存断点（Cache Breakpoints）
- 30 分钟最低缓存生命期
- Cache Write 1.25x 输入价格，Cache Read 90% 折扣

**Cerebras 部署：** Sol 可达 750 tokens/秒

**核心趋势：** Agent 能力成为模型核心竞争力（Terminal-Bench 2.1 SOTA），模型定价 + 缓存机制优化正在降低 Agent 规模化部署成本

**GPT-Live（2026-07-14 新增）：** OpenAI 推出全双工语音模型，能同时听和说。架构亮点：交互层与推理层解耦分离——GPT-Live 处理持续交互，GPT-5.5 处理后台推理。参考：[[Models & SDK/gpt-live.md]]

**Programmatic Tool Calling（2026-07-14 新增）：** GPT-5.6 可通过 Responses API 编写并运行轻量级程序协调工具调用，减少 Token 消耗和模型往返。与 Deep Agents Dynamic Subagents 思路一致。参考：[[Models & SDK/gpt-5-6-sol.md]]

**详细知识节点：** [[Models & SDK/gpt-5-6-sol.md]]



## Evaluation

**定义：** 评估和测试 Agent / AI 应用的质量和效果

**2026 实践：**
- **LangSmith Engine**：分析 Agent Trace，自动化提取记忆和优化点
- **Harbor x LangChain**（2026-06-30）：统一 Agent 评估平台，标准化评测流程，自动红队测试
- **OOLONG Benchmark**：RLM 评估标准，测试长上下文推理和数据分析聚合能力
- **GeneBench-Pro**（OpenAI 2026-06-30）：合成数据 + 多步追踪 + 消融实验的严谨评估方法论
- **SWE-Bench Pro 审计**（OpenAI 2026-07-08）：约 30% 任务有缺陷，OpenAI 正式撤回推荐。启示：没有完美的 Benchmark，建立自己的评估集 + Agent 辅助审核才是正道
- **Glasswing 框架**（Anthropic+ 2026-06-30）：Jailbreak 严重性评分的行业标准
- **Verifier 设计模式**（LangChain × Harvey 2026-06-02）：用批量评分 + 低成本模型优化评估验证成本，DeepSeek V4 Flash 作验证器性价比最优
- **Coding Agent 成本优化**（LangChain 2026-07-02）：Prompt Caching + 上下文瘦身 + Subagent 隔离 + 模型分层

**三大评估层次：**
1. **Benchmark（基准测试）**——模型能力上限，如 Terminal-Bench、OOLONG
2. **Production Evaluation（生产评估）**——任务完成率、成本效率、延迟分布
3. **Safety Evaluation（安全评估）**——代码执行安全、Jailbreak 防御

**评估体系搭建原则：**
- 先建立评估，再优化 Agent（没有评估就没有改进方向）
- 追踪中间决策过程，不只关注最终结果
- 评估数据可 Feed 回 Agent 记忆系统形成改进闭环
- 每个 Agent 上线前通过：功能测试 → 安全评估 → 性能评估

**Agent 工程化模式更新：** Loop Engineering 提供了 Agent 开发的系统化成熟度模型。三层循环栈从基础执行到验证再到事件驱动，是 Agent 工程化的基础设计模式。参考：[[AI Agent/agent-architecture.md#7. Loop Engineering：三层循环设计模式]]



## Fine-tuning 微调

**定义：**将新知识通过**模型训练**的手段直接训到模型里去，需要判断是否值得微调（如降低推理成本的意义，是否要私有化部署

**特点：**微调后通用能力会下降，但是垂直领域的专有能力会增强





## Popular Tools

### Ponytail

**定义：** 开源的 AI Coding 技能插件（本质是 Skill），定位【AI Coding 质量约束层】--不给 Agent 新能力，而是叠加一层"最懒资深工程师"的思维约束，要求只写任务必需的代码，治 AI Coding 的"代码膨胀"病（LOC 剧增、乱装依赖、过度设计）。

**核心：七层决策阶梯**（理解问题后、动笔前依次爬升，停在第一个命中的档）：

```
1. 这东西需要存在吗？   -> 不需要就跳过（YAGNI）
2. 代码库里已经有了？   -> 复用，别重写
3. 标准库能做？         -> 用标准库
4. 原生平台特性能做？   -> 用原生（<input type=date>、<dialog>、IntersectionObserver）
5. 已安装的依赖能做？   -> 用已装依赖，别新增
6. 一行能搞定？         -> 一行
7. 最后才是：能工作的最小实现
```

**实现机制：hook 每轮注入。** 通过 `SessionStart` / `UserPromptSubmit` 等 hook **每轮对话重新注入**七层阶梯，纪律不随对话变长而稀释（对比写死 system prompt 一次会被稀释）。注入是 Harness（Claude Code）干的，不是模型--即 [[Skill]] 站"声明式 + Harness 实现"的产品级实物。七层阶梯本质是一组结构化 [[Rule]] 约束。

**命令：**

| 命令 | 作用 |
|---|---|
| `/ponytail [lite\|full\|ultra\|off]` | 设置强度或关闭，无参数返回当前等级 |
| `/ponytail-review` | 单文件/变更块过度设计冗余评审 |
| `/ponytail-audit` | 全仓库代码审计，输出待删冗余优先级清单 |
| `/ponytail-debt` | 提取注释里 `ponytail:` 前缀的技术债，汇总台账 |

`ponytail:` 注释前缀：Agent 做"有意简化"时标记（如 `// ponytail: 用原生 date 而非装 dayjs`），配合 `/ponytail-debt` 留可追溯痕迹。

**实测收益（我的实验，Vue2+ElementUI 后台 + Claude Code+GLM-5.2，每组 4 轮取均，新会话防干扰）：**

- 代码编写（简单+一般任务，保障正确性）：**LOC ↓33% / Token ↓30% / 耗时 ↓20%**，安全不降级
- 原生优先验证：进度条、Excel 导出等场景，Ponytail 用原生方法替代装依赖（七层阶梯第 4 档实战兑现）
- 代码审核（`/ponytail-audit`）：审核效率与建议采纳率均高于纯 AI Coding
- 官方 Benchmark（React+FastAPI，n=4）：LOC -54% / token -22% / cost -20% / time -27% / 安全 100%

**劣势/边界：**

1. 极简任务收益≈0（代码已够精简时无的放矢，已验证）
2. 复杂交互/已有严格组件规范的需求，收益明显收窄
3. 对模型有要求：小模型不生效；部分 reasoning 模型（GPT-5.6）反复 deliberating 反而更贵
4. 设计系统盲区：只看代码库有没有，不知项目实际组件库，可能破坏前端一致性

**同类质量约束层插件：**

| 插件 | 定位 | 治什么 | 与 Ponytail 差异 |
|---|---|---|---|
| Caveman | 压缩输出散文省 token | 输出啰嗦（管"说什么"） | 不改代码逻辑 |
| Karpathy Skills | Karpathy 四原则编码纪律 | 乱改/跑偏 | 偏行为纪律 + 工程化 enforcement |
| Ponytail | 七层阶梯约束代码量 | 代码多（管"写多少"） | 治本，约束代码本身 |
| tokless | 整合包一键装齐 | -- | 全家桶入口（装上面三个+其他） |

**连接已学：** Ponytail 没引入新概念，是已学概念的工程化组装--Skill（它本身是 Skill 插件）+ Prompt Rule（七层阶梯=结构化 Rule）+ Harness（hook 每轮注入=Harness 层能力）。归「工程实践补充」，非学习路线节点。详见 [[11-Ponytail]]。

**参考：** [GitHub](https://github.com/DietrichGebert/ponytail) / [官网 ponytail.dev](https://ponytail.dev) / 官方 benchmark writeup



### 应用层 Benchmark

**定义：** 标准化评测体系：输入测试集 → 评分规则 → 判定 AI 系统好坏。分**模型层**（测模型通用能力，供选型）与**应用层**（⭐测模型在特定业务链路的适用程度，供质量保障/回归测试/持续优化），工程重心在应用层。

**核心：界定 → 衡量 → 改进。** 界定=建黄金数据集（20–50 例输入↔预期输出，专家独立判断）；衡量=评分器对测试集打分；改进=数据飞轮（记录→抽样→专家审查→回填黄金集，越用越厚的数据资产）。四要素：**数据集、评分器、指标、框架（eval harness）**。

**评分器三型（内置逻辑都是断言）：** 代码型（确定性规则，可复现但只判形式不判语义）/ 模型型（LLM-as-a-Judge，能判语义但需人工校准）/ 人工型（专家判分，准但不可规模化）。准则：能编码→代码型；能用语言描述好坏→模型型；都不行→人工型。

**命令（Promptfoo，CLI+YAML，TDD for LLM）：**

| 命令 | 作用 |
|---|---|
| `promptfoo init` | 初始化生成配置（promptfooconfig.yaml） |
| `promptfoo generate dataset` | 合成测试集 |
| `promptfoo optimize` | 自动迭代优化 prompt |
| `promptfoo eval` | 运行评估（prompts×providers×tests 矩阵评测） |
| `promptfoo view` | 本地 Web UI 看结果 |

指标按评测对象分六套：Prompt（矩阵评测）/ RAG（检索生成分阶段：context-recall、factuality、faithfulness…）/ Agent（trajectory:goal-success、tool-used…）/ SKILL（skill-used / not-skill-used，只换 SKILL.md 做对照）/ LLM 链（unit vs end-to-end）/ 结构化输出（is-json 带 Schema）。差异化能力：红队 50+ 漏洞类型（Plugins×Strategies）+ CI/CD 集成。

**实测收益：** 调研阶段，无自建实测；后续真实场景落地时补黄金集 + 基线数据。

**劣势/边界：**

1. 框架只是工具，评估质量取决于任务和评分器本身
2. 评分器各有天花板：代码型脆弱、模型型会幻觉需校准、人工型不可规模化
3. 黄金集冷启动要专家投入，且需持续维护
4. 自动化评估可能脱离真实用法造成假信心，需配合生产监控/用户反馈

**同类（专用评测框架）：**

| 框架 | 定位 | 一句话 |
|---|---|---|
| Promptfoo | 通用评测 + 红队（50+ 漏洞，最强） | 通用首选 |
| DeepEval | Python/pytest 生态全家族指标 | Python 团队首选 |
| RAGAS | RAG 专项 reference-free 指标库 | RAG 专项 |
| mcp-eval | MCP 专项（真实 agent↔server + OTel 断言） | MCP 专项 |
| skill-up | SKILL.md 评测 + 演进 | Skill 专项 |
| Langfuse | 可观测性平台 + 在线评测 | 生产监控 |

观测+评测一体化平台：LangSmith（LangChain 生态）/ Langfuse（自托管）/ Arize Phoenix（OTel 原生）/ Braintrust（一站式商业）。选型从评测对象 + 是否需生产监控出发。

**连接已学：** 应用层 Benchmark 没引入新范式，是已学全链路的验收层——RAG 站手写 Hit@K/MRR 是代码型评分器的手写版；LLM-as-a-Judge 是 Prompt+FC 的反向应用（模型当裁判）；trajectory 指标量化 ReAct 轨迹；skill-used 断言测 Skill 站 description 触发正确性；数据飞轮≈长期记忆闭环的评测版；红队=阶段4护栏的自动化探测。前端老本行 TDD 的 LLM 重生。归「工程实践补充」，非学习路线节点。详见 [[12-应用层Benchmark评测]]。

**参考：** [Anthropic — Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) / [OpenAI — 评估框架](https://openai.com/zh-Hans-CN/index/evals-drive-next-chapter-of-ai/) / [Langfuse — LLM Evaluation Strategy](https://langfuse.com/resources/engineering/llm-evaluation-strategy)

