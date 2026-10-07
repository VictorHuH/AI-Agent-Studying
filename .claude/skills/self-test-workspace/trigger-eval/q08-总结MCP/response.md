你 MCP 这章（06-MCP.md，2026-07-19）学的核心内容，可以收拢成五件事：

**1. 为什么需要 MCP：M×N → M+N**
- 回看 FC demo 的痛点：工具 schema + 函数派发表手写两份，且绑死在单个应用里——M 个 Host × N 个工具就要 M×N 份适配代码
- MCP 把工具解耦成独立 Server，任何 Host 用统一协议连接，总成本降为 M+N
- 一句话：**MCP 是 AI 工具的 USB-C 接口**

**2. 三角架构**
- **Host**（跑 LLM 的应用，如 Claude Desktop / Cursor / Claude Code）→ 内含 **Client**（1:1 连接器）→ **Server**（暴露能力的独立进程）
- 协议层 JSON-RPC 2.0（`tools/list`、`tools/call`），传输层 stdio（本地，教学首选）/ Streamable HTTP（远程，已取代 SSE）

**3. 三大原语 = 已学三范式重逢**
- Tools ↔ FC、Resources ↔ RAG、Prompts ↔ Prompt Engineering。本章实战聚焦 Tools

**4. 两个实战（都跑通了 ✅）**
- **Server**（`test_mcp_server.py`）：`@mcp.tool()` 装饰器，函数即工具，schema 从类型注解自动生成、docstring 即 description——对比 FC 手写 schema 是质的提升
- **Client**（`test_mcp_client.py`）：四步协议流程（stdio_client 拉起子进程 → initialize 握手 → list_tools 发现 → call_tool 调用）。关键认知：**Client 不 import Server 代码**，这就是解耦的本质
- 顺手踩平了 Windows 工程坑：`sys.executable`、UTF-8 编码、FastMCP 日志

**5. 两个关系认知**
- **MCP 和 FC 是分层不是替代**：FC 是嘴（模型决策调啥），MCP 是手的标准化接口（怎么调到）。完整形态 = FC 出决策 + MCP 执行
- **Claude Code 本身就是 MCP 的 Host**：装一个 Server 就能零代码加新能力，这是 M+N 的现实样子

进化链上你走完了 **Function → Tool** 这一段，给 Skill 站留的钩子是"再包一层怎么用的说明书（prompt + 资源）"。

要把哪一块展开讲讲，还是直接进 Skill 那章？
