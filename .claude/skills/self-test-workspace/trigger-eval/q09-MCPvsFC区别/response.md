这个问题你的笔记里其实已经埋好答案了（`06-MCP.md` 第六节"关键认知"），正好用它检验你那一站有没有真正吃透。我先讲核心这一段，你确认理解了我们再往下挖。

**一句话先给结论：FC 和 MCP 不是竞争/替代关系，是两个层面的分工（分层）。**

| | FC（Function Calling） | MCP（Model Context Protocol） |
|---|---|---|
| 解决什么 | 模型怎么**表达**"我要调工具"（决策层） | 工具怎么被**发现和调用**（跨进程标准，协议层） |
| 谁在工作 | 模型：输出 `tool_call(get_weather, {city:"上海"})` | Client：通过 JSON-RPC 连 Server 调 `get_weather` |
| 你写过的代码 | `Code/test_function_calling.py` | `Code/test_mcp_server.py` + `test_mcp_client.py` |

用你自己的两个 demo 对照最直观：

- **FC demo**：模型决策完，是谁执行的？你的 Python 代码，靠手写的 `TOOL_REGISTRY` 派发表，函数和 schema 都写在同一个文件里——**工具绑死在这一个应用里**。换个 Host（Cursor、Claude Desktop）想用？schema 和函数再抄一遍，M×N 问题。
- **MCP demo**：Client 连 Server 连 `import` 都不 import，只拉起一个子进程靠 JSON-RPC（`tools/list` 发现、`tools/call` 调用）通信——**工具被解耦成独立服务**，任何 Host 都能连，M+N。

所以两者根本不在同一条赛道上：**FC 回答"调哪个、参数填什么"，MCP 回答"工具从哪来、怎么跨进程调到"**。你笔记里那句类比就是标准答案：FC 是"嘴"（说要调啥），MCP 是"手"的标准化接口（怎么调到）。真实工业 Agent 是两层叠着用的：**FC 出决策 → MCP 执行**。

再补一个最容易混的点收尾：MCP Server 暴露的 Tool，最终喂给模型时**还是要变成 FC 的 `tools` 参数**（schema + description）——模型那一层的机制一点没变。MCP 改变的是两件事：schema 从哪来（`tools/list` 自动发现，不用手抄）和执行在哪发生（跨进程，`import` 都不要）。

——

理解确认（答一下再继续）：

1. 用一句话向你的前端同事解释 MCP 干的事（他们懂 HTTP 的价值），你会怎么类比你笔记里现成的那个？
2. 在你的 MCP Client demo 里，"调哪个工具"是谁决定的？为什么说它跳过了 FC 那一层？
