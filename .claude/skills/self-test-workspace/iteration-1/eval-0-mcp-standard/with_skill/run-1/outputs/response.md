# MCP 自测 · 6 道题（覆盖 06-MCP.md 全部考点）

范围：`06-MCP.md` 全部七节（本质 / 架构 / 三大原语 / Server 实战 / Client 实战 / MCP 与 FC 的关系 / 进化位置）。
配比：记忆 1 + 理解 2 + 应用 2 + 分析 1。逐题作答即可，答完我逐题判分讲解。

---

**第 1 题【记忆】三大原语**

MCP Server 能暴露的三类原语（Primitives）是什么？它们分别对应你之前学过的哪三大范式？各举一个例子。

---

**第 2 题【理解】M×N → M+N**

为什么说 MCP 把工具接入成本从 M×N 降到了 M+N？请解释 M、N 各指什么、M×N 的痛点在哪，以及 MCP 用什么办法把它变成 M+N（用"USB-C 接口"的类比说明 MCP 到底标准化了什么）。

---

**第 3 题【理解】解耦的本质**

在你的 Client demo 里，连接 Server 只需要 `StdioServerParameters(command=..., args=[...])`，**完全不 import Server 的代码**。为什么这样就够了？这个设计带来了什么好处（提示：跨进程、跨语言）？

---

**第 4 题【应用】新场景迁移**

假设你想把之前 RAG 站做的"简历知识库"暴露成一个 MCP Server，接到 Claude Desktop 上让模型按需查询。你会用三大原语中的哪一个？为什么？Claude Desktop 这边还需要你写 Client 代码吗？

---

**第 5 题【应用】FastMCP 实战**

把 FC demo 的 `get_weather` 用 FastMCP 重写成 MCP Server 后：

1. `@mcp.tool()` 装饰器下，给模型看的 JSON Schema 和 description 分别从哪来？（对比 FC demo 手写 `TOOLS_SCHEMA` + `TOOL_REGISTRY` 的做法）
2. 如果你直接在终端跑 `python test_mcp_server.py`，发现没有任何输出——这是代码坏了吗？为什么？

---

**第 6 题【分析】MCP 和 FC 的关系**

有人说："MCP 出来之后，Function Calling 迟早会被淘汰。"你同意吗？请说明 FC 和 MCP 各自解决什么层面的问题，并描述一个真实 Agent 里两者如何配合工作（谁决策、谁执行）。

---

答题方式：直接按题号写下你的回答即可（不用翻笔记，凭记忆答，答不全也没关系）。答完我逐题判分，错的题会讲清思路和对应笔记的小节。
