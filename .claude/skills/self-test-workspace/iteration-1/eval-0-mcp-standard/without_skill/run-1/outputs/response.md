好，MCP 全量自测，6 道题。范围覆盖 06-MCP.md 的全部内容（本质、架构、三大原语、Server/Client 实战、FC 分层关系），最后一题延伸到你在 WorkBuddy 连接器里的真实落地。难度从回忆到应用递进。

**第 1 题（本质：为什么需要 MCP）**
你在 FC 站手写了 `TOOLS_SCHEMA` 和 `TOOL_REGISTRY`。请说明这套写法的核心问题是什么，MCP 是怎么解决的？要求说出 M×N → M+N 的具体含义：M、N 各指什么，M×N 份什么成本，M+N 后各是谁实现的。

**第 2 题（架构 + 通信）**
画出或描述 MCP 的三角架构：Host、Client、Server 各是什么角色？Client 和 Server 的数量关系是怎样的？再回答两点：
- a) 协议层用什么？举两个具体的方法名。
- b) 传输层有哪两种方式？各适用什么场景？其中哪种取代了哪种旧方案？

**第 3 题（三大原语）**
MCP Server 能暴露哪三类东西？请把每一类和你前面学过的范式一一对应起来，并各举一个例子。另外说明：MCP 把"给模型加能力"拆成三个标准维度，这个设计和你已学的三大范式是什么关系？

**第 4 题（实战代码：写 Server）**
用 FastMCP 写出一个 MCP Server 的核心代码：定义一个 `get_weather(city)` 工具并启动 stdio 服务。要求：
- a) 写出 `@mcp.tool()` 装饰器用法；
- b) 说明 schema、description 分别从哪里自动生成——对比 FC demo 里这两样东西是怎么来的；
- c) 解释为什么不能直接 `python test_mcp_server.py` 看到输出。

**第 5 题（实战代码：写 Client + 关键认知）**
写 MCP Client 拉起一个 stdio Server 并调用工具，完整协议流程是哪四步（写出关键函数名）？然后回答三个"为什么"：
- a) Client 为什么不需要 import Server 的代码？这体现了什么本质？
- b) "FC 出决策 → MCP 执行"——这两层分别解决什么问题？是替代关系吗？
- c) 你正在用的 Claude Code 在这个架构里是什么角色？"装一个 MCP Server = 零代码改动加新能力"是怎么做到的？

**第 6 题（综合应用：WorkBuddy 落地）**
你在 WorkBuddy 连接器里真实交付过 `flashcards-mcp`。假设现在要把它接入 WorkBuddy：
- a) mcp.json 里能配几个 Server？远程和本地各怎么配？
- b) MCP + Skill 方案里，MCP 的 schema 已经声明了"有什么工具"，那 SKILL.md 还负责什么？两者为什么是互补不是重复？
- c) "工具名称、描述、参数要清晰稳定，便于 AI 正确选择"——这句话印证了你在 FC 站学到的哪条原则？

---

作答方式随意：一次性全答，或者一题一题来都行。答完我按笔记逐题判分 + 补漏。
