# 🔌 MCP 教程（阶段3笔记）

> 学习日期：2026-07-19
> 定位：阶段 3 框架与工具链。**工具体系进化链的关键一环** -- 把"工具"从 Agent 代码里解耦成标准服务。
> 路线位置：RAG ✅ -> Prompt ✅ -> FC ✅ -> Agent ✅ -> **MCP** ✅ -> Skill -> LangChain
> 协议版本：本机验证为 `2025-11-25`（最新稳定版，2024-11 初版，2025-06 第二版，2025-11 第三版）

---

## 一、本质：为什么需要 MCP（M×N → M+N）

回看 FC demo（`test_function_calling.py`）：工具是怎么接进来的？

```
手写 TOOLS_SCHEMA（JSON Schema，给模型看）
手写 TOOL_REGISTRY（函数派发表，给代码用）
两个都得自己维护，schema 和函数实现散在两处
```

这套写法的问题不在"难写"，在**绑死**：`get_weather` 这个工具写死在 FC demo 这一个应用里。换个应用（Cursor、Claude Desktop、另一个 Agent）想用它？**得把 schema 和函数再抄一遍**。

放大看：**M 个 Host（宿主应用）× N 个工具 = M×N 份适配代码**。每出一个新工具，要给每个 Host 重写一遍接入。

MCP（Model Context Protocol，Anthropic 2024-11 推出）解的就是这个：

```
Host 不再自己接工具，而是通过统一的 Client 协议去连"工具服务"。
工具实现成独立的 Server，任何 Host 都能用同一套协议发现并调用。
```

- M 个 Host：各实现一次 Client（接入协议）→ M 份
- N 个工具：各实现一次 Server（暴露能力）→ N 份
- 总成本：**M + N**，不是 M×N

> 🎯 **一句话**：MCP 是 AI 工具的"USB-C 接口"。USB-C 不关心你插的是硬盘还是显示器，只规定"插上就能被识别"。MCP 不关心工具内部怎么实现，只规定"工具怎么被发现、怎么被调用"。HTTP 标准化了 Web 通信，MCP 标准化了 AI 调工具。

### 和已学知识的钩子兑现

Agent 站埋的钩子今天兑现第一半：

| 钩子（Agent 站留的） | 今天兑现 |
|---|---|
| "Agent 的工具是手写 Python 函数" | MCP 把工具从代码里**解耦**成独立进程/服务 |
| "Function -> Tool -> Skill 进化链" | 本站走完 **Function → Tool** 这一段；Skill 是下一站 |

FC demo 的 `get_weather` 是 **Function**（函数 + 手写 schema，绑死在应用里）。本站把它升级成 **Tool**（MCP Server，标准化、可复用）。下一站 Skill 再包一层"怎么用"。

---

## 二、架构：Host / Client / Server 三角

```
┌─────────────────────────────┐
│  Host（宿主应用）            │   跑 LLM、做决策的应用
│  ┌─────────┐  ┌─────────┐  │   例子：Claude Desktop、Cursor、
│  │ Client  │  │ Client  │  │         Claude Code、你自己的 Agent
│  └────┬────┘  └────┬────┘  │
└───────┼────────────┼──────┘
        │ JSON-RPC   │ JSON-RPC     统一协议，每个 Client 1:1 连一个 Server
        ▼            ▼
   ┌─────────┐  ┌─────────┐
   │ Server  │  │ Server  │       独立进程，暴露工具/资源/提示词
   │ 天气     │  │ 数据库   │       例子：天气 Server、GitHub Server、你的 RAG
   └─────────┘  └─────────┘
```

三个角色：

| 角色 | 是什么 | 你已见的例子 |
|---|---|---|
| **Host** | 跑 LLM 的应用，装着若干 Client | Claude Desktop、Claude Code、你的 Agent |
| **Client** | Host 内部 1:1 连一个 Server 的连接器 | 本站 `ClientSession` |
| **Server** | 暴露能力的独立进程 | 本站 `test_mcp_server.py` |

通信两层：

- **协议层：JSON-RPC 2.0**。请求-响应模型，方法名如 `tools/list`、`tools/call`。和 FC 的 `tools` 参数完全不同维度：FC 是"模型怎么表达要调工具"，MCP 是"工具怎么跨进程被发现和调用"。
- **传输层：stdio / Streamable HTTP**。
  - **stdio**：本地子进程，server 通过标准输入/输出收发 JSON-RPC。**教学首选，最简**。
  - **Streamable HTTP**：远程，2025-03 起取代旧版 SSE（SSE 已废弃）。一次 HTTP 请求即可升级成流式，适合生产远程场景。

---

## 三、三大原语（Primitives）-- 三大范式在这里重逢

Server 能暴露三类东西，正好对上你已学的三大范式：

| 原语 | 是什么 | 对应已学 | 例子 |
|---|---|---|---|
| **Tools** | 模型可调用的函数 | **FC** 的 tools（`test_function_calling`） | `get_weather`、`calculate` |
| **Resources** | 可读的数据源（模型按需读） | **RAG** 的知识库 | 简历 PDF、数据库表、文件 |
| **Prompts** | 预定义提示词模板（用户触发） | **Prompt** Engineering 的模板 | "总结这份文档"模板 |

> 🎯 **一句话**：FC / RAG / Prompt 这三大范式，在 MCP 里以 Tools / Resources / Prompts 三大原语的形式重逢了。这不是巧合 -- MCP 就是把"给模型加能力"这件事拆成三个标准维度。

本站实战聚焦 **Tools**（最常用，和 FC 直接对应）。Resources / Prompts 思路一致，留给后续。

---

## 四、实战 1：写一个 MCP Server

见 `Code/test_mcp_server.py`。把 FC demo 的两个工具搬过来，但用 FastMCP 装饰器重写。

### 代码结构：2 个必懂点

**① `@mcp.tool()` -- 函数即工具，schema 自动生成**

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("studying-mcp-server")

@mcp.tool()
def get_weather(city: str) -> str:
    """获取指定城市的当前天气。用于查询实时天气信息。"""
    return fake.get(city, "...")
```

对比 FC demo 要手写的 `TOOLS_SCHEMA`（一大段 JSON）+ `TOOL_REGISTRY`（派发表）：

| | FC demo | MCP Server |
|---|---|---|
| schema | 手写 JSON Schema | 类型注解自动生成 |
| description | 写在 schema 里 | 函数 docstring 自动取用 |
| 派发 | 自己写 `TOOL_REGISTRY[fn](**args)` | 协议自动派发，代码不出现 |
| 复用 | 绑死在这个应用 | 任何 Host 都能连 |

**② `mcp.run(transport="stdio")` -- 启动服务**

stdio 传输：server 在自己的子进程里跑，靠标准输入/输出收发 JSON-RPC。所以 server 文件**不能直接 `python test_mcp_server.py` 看输出**（它没东西打印，只是在等 client 通过 stdin 发请求）--它是个"被调用的服务"。

---

## 五、实战 2：写一个 MCP Client

见 `Code/test_mcp_client.py`。不经过任何 LLM，纯协议验证：拉起 server 子进程 → 发现工具 → 调用工具。

### 协议流程四步

```python
# ① 告诉 Client "怎么启动 Server"（不 import server 代码！只起子进程）
server_params = StdioServerParameters(command=sys.executable, args=["test_mcp_server.py"])

async with stdio_client(server_params) as (read, write):       # 拉起子进程
    async with ClientSession(read, write) as session:         # 建会话
        await session.initialize()                             # ② 握手
        tools = (await session.list_tools()).tools             # ③ 发现
        result = await session.call_tool("get_weather",        # ④ 调用
                                         {"city": "上海"})
```

**关键认知**：Client 只需要"怎么启动 Server"（command + args），**不需要 import Server 的代码**。这就是解耦的本质 -- 工具实现和工具调用彻底分开，跨进程、跨语言都行（Server 用 Rust 写、Client 用 Python 连，照样通）。

### 真实运行结果（2026-07-19 跑通 ✅）

```
① 启动 MCP Server（stdio 子进程）并建立会话...
✅ 会话已初始化。Server: studying-mcp-server
   协议版本: 2025-11-25

② 发现 2 个工具（list_tools）：
   - get_weather(city)
     获取指定城市的当前天气。用于查询实时天气信息。
   - calculate(expression)
     精确计算数学表达式。用于大数乘除、复杂运算等模型可能算错的场景。

③ 调用工具（call_tool）：
   🔧 call_tool(get_weather, {'city': '上海'})  -> 32℃，晴
   🔧 call_tool(get_weather, {'city': '广州'})  -> 35℃，雷阵雨
   🔧 call_tool(calculate, {'expression': '1234 * 5678'})  -> 1234 * 5678 = 7006652

✅ MCP 协议闭环跑通：Client 发现并调用了 Server 的工具。
```

三个看点印证：
1. **协议版本 `2025-11-25`**：握手时 client 和 server 协商出的最新稳定版。
2. **schema 自动生成**：`get_weather(city)` 的 `city` 参数是 FastMCP 从 `city: str` 注解推出来的，没手写一个字的 JSON Schema。
3. **`1234 * 5678 = 7006652`**：FC demo 里这个数被模型口述成"700万66652"（多 1 个 6），这里 Python 算对了。**工具补短板，不代替思考** -- 钩子再次兑现。

### Windows 工程坑（已踩平）

- **`command=sys.executable`**：Windows 下用 `"python"` 可能找不到（PATH/版本问题），用 `sys.executable`（当前解释器完整路径）最稳。
- **编码 UTF-8**：跑之前设 `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`，避免中文输出乱码（Python 3.14 默认 UTF-8，但 Windows 控制台不一定）。
- **FastMCP 的 INFO 日志**：默认会打 `Processing request of type ListToolsRequest`，是日志不是报错。生产可调日志级别关掉。

---

## 六、关键认知：MCP 和 FC 的关系 + 和 Claude Code 的关系

### MCP 不是 FC 的替代，是分层

容易混淆的点：MCP 和 FC 是一回事吗？不是，是**两个层面**：

| | 解决什么 | 例子 |
|---|---|---|
| **FC（Function Calling）** | 模型怎么**表达**"我要调工具" | 模型输出 `tool_call(get_weather, {city:"上海"})` |
| **MCP（Model Context Protocol）** | 工具怎么被**发现和调用**（跨进程标准） | Client 通过 JSON-RPC 连 Server 调 `get_weather` |

一个 Host 可以**同时用两者**：用 FC 让模型决策调哪个工具，用 MCP 去真正执行（连对应的 Server）。本站 Client demo 是"代码指定调哪个"（跳过 FC 决策）；真实 Agent 里这两层会接起来：**FC 出决策 → MCP 执行**。

> 🎯 **一句话**：FC 是"嘴"（说要调啥），MCP 是"手"的标准化接口（怎么调到）。FC + MCP = 模型决策 + 标准化执行，这才是工业版 Agent 的完整形态。Agent 站留的钩子"工业版用 FC 的 tools 参数"今天补全另一半。

### 你正在用的 Claude Code 就是 MCP 的 Host

正反馈来了 -- 你这两天的学习环境本身就在用 MCP：

- **Claude Code 是 Host + Agent**（Agent 站已学：Claude Code = Harness + Agent，Harness 不做决策只执行）。
- 它的每个内置工具（`Bash`、`Read`、`Edit`、`Grep`...）背后都是 tool（可以理解成内置 Server）。
- 配置文件（`.mcp.json` / `claude_desktop_config.json`）就是装外部 MCP Server 的入口。
- **装一个 MCP Server = 给 Claude Code 加新能力，零代码改动**。这就是 M+N 的现实样子。

> 试着搜一下"awesome mcp servers" -- 已经有几百个现成的 Server（GitHub、Slack、数据库、文件系统…）。这就是标准化的网络效应：写一次，到处可用。

---

## 七、MCP 站总收尾

带走五件事：

1. **MCP = AI 工具的 USB-C**。把工具从应用代码里解耦成独立服务，M+N 替代 M×N。
2. **三角架构**：Host（跑 LLM）/ Client（连接器）/ Server（暴露能力），JSON-RPC 2.0 通信，stdio（本地）/ Streamable HTTP（远程）传输。
3. **三大原语 = 三大范式重逢**：Tools（FC）/ Resources（RAG）/ Prompts（Prompt Engineering）。
4. **MCP 和 FC 是分层不是替代**：FC 是嘴（决策调啥），MCP 是手的标准化接口（怎么调到）。真实 Agent = FC 决策 + MCP 执行。
5. **`@mcp.tool()` 让函数即工具**：schema 从注解自动生成，docstring 就是给模型看的 description（和 FC 同理：给工具写 Prompt）。

### 工具体系进化位置

```
Function Calling             ← 函数 + 手写 schema，绑死在应用 ✅
        │  解耦成独立服务 + 标准协议
        ▼
Tool / MCP                   ← 标准化工具服务，跨 Host 复用 ✅（本站）
        │  再包一层"怎么用"的说明书（prompt + 资源）
        ▼
Skill                        ← 能力封装包，下一站
```

> 🔗 **下一站钩子（Skill）**：
> - MCP 的 Tool 是"一个动作"；Skill 是"一整套能力的封装包"-- 带 prompt（怎么用）、资源（依赖什么）、tools（能干啥）。
> - 类比：Tool 是一把螺丝刀，Skill 是"组装这台电脑"的技能卡（告诉你用哪几把螺丝刀、按什么顺序）。
> - 你正在用的 Claude Code 的 Skill（`/skill-name`）就是工业实现 -- 它能把多个 tool + 一段 prompt 打包成一个可复用技能。
> - Skill 也讲 SubAgent（一个 Agent 派生子 Agent 干特定任务）的关系 -- 暂留作后续。
>
> MCP 站完成。下一站：**Skill**（或先 LangChain 把 Agent + MCP 工程化封装）。
