好，考你 MCP 这章。我按 06-MCP.md 的考点清单出的题，覆盖六个不同考点，从记忆到分析都有，不全是背的题。答完我再逐题判分讲思路。

**第 1 题（理解）**
FC demo 里 `get_weather` 的问题不在于"难写"，笔记说在于"绑死"。请用自己的话说说：MCP 是怎么把 M×N 的问题变成 M+N 的？"USB-C 接口"这个类比里，USB-C 对应 MCP 的什么？

**第 2 题（理解）**
MCP 架构三角里，Host、Client、Server 各自的职责是什么？Client 和 Server 是什么数量关系？协议层用什么、传输层有哪两种，分别适合什么场景？

**第 3 题（记忆+理解）**
Server 能暴露的三大原语分别是什么？它们各自对应你已经学过的哪三大范式？请各举一个例子。

**第 4 题（应用）**
场景题：你同事写了一个 MCP Server（`test_mcp_server.py`，stdio 传输），他直接运行 `python test_mcp_server.py`，发现啥也没输出，以为代码坏了。他错在哪了？另外，`@mcp.tool()` 相比 FC demo 手写 `TOOLS_SCHEMA` + `TOOL_REGISTRY`，省掉了哪几件事？

**第 5 题（应用/分析）**
写 MCP Client 时，为什么只需要 `StdioServerParameters(command=..., args=[...])`，而不需要 import Server 的代码？这个设计的本质是什么？（提示：这和跨语言有什么关系？）

**第 6 题（分析）**
MCP 和 Function Calling 是不是替代关系？在一个真实的工业版 Agent 里，两者各负责什么、怎么接起来？你现在用的 Claude Code 在这个架构里扮演什么角色？

逐题答，不确定的也把你的想法说出来，模糊的地方我会追问，不会直接判对错。
