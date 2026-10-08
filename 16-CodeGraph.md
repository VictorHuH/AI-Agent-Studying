# CodeGraph（工程实践调研）

> 2026-10-08 调研完成。**非学习路线节点，是工作中实测的工具调研**，归入「工程实践补充」。
> 衔接 [[14-WorkBuddy连接器]] / [[06-MCP]] / [[01-RAG入门教程]]：CodeGraph 是 RAG（预建索引精准取上下文）+ MCP（stdio Server 暴露工具）+ Agent（Claude Code 当 Host 查图）三个已学概念的产品级汇合点。
> 关键词：代码知识图谱、tree-sitter、MCP Server、图检索、关系型查询

---

## 核心认知

> **把代码库预先解析成知识图谱（节点=符号、边=调用/继承/导入关系）存本地 SQLite，AI 助手经 MCP 直接查图，替代每次对话 grep/glob/read 暴力爬文件**——治 AI 编程助手在陌生大仓库里"迷路"（重复探索烧 token）的病。

- 项目：colbymchenry/codegraph，MIT，GitHub 7 万+ star（2026 年爆火）
- 官方数据（7 个真实代码库）：工具调用 ↓71% / token ↓57% / 速度 ↑46% / 成本 ↓35%

---

## 一、问题：Agent 在陌生代码库里"迷路"

让 Claude Code"改一下 UserService 的登录逻辑"，它的第一步是**暴力探索**：grep 搜关键词 → glob 找文件 → read 读文件 → 发现还要看被调函数 → 再 read……每个新对话都从零重爬一遍。

这本质是 [[01-RAG入门教程]] 讲过的同一个问题的变体：**怎么让 LLM 高效拿到相关上下文，而不是塞整个知识库**。向量 RAG 擅长"语义相似"，但对代码理解的核心——**关系型查询**——是盲区：

- 这个函数**被谁调用**（call graph）
- 这个类**继承/实现**了谁
- 改这个函数，**波及**哪些下游（blast radius）

Embedding 算的是文本向量相似度，"谁调用谁"这种结构关系在向量空间里根本不构成"相似"。**向量检索找"长得像的"，图遍历找"有关系的"——代码理解要的是后者。**

> 🎯 本质金句：关系型查询是向量 RAG 的盲区，代码理解的重心恰恰全是关系。

## 二、原理：四阶段流水线

把"代码理解"从**运行时**（AI 对话中）挪到**预构建时**（init 一次）：

| 阶段 | 做什么 | 关键点 |
|---|---|---|
| ① 提取 Extraction | tree-sitter 解析源码成 AST，抽**节点**（函数/类/方法/路由/组件）和**边**（调用/导入/继承/实现/引用） | **确定性解析**，不是 LLM 写摘要——AST 不会幻觉，`login() calls verifyJWT()` 是语法树里的 ground truth |
| ② 存储 Storage | 全部存入项目根目录 `.codegraph/codegraph.db`，SQLite + FTS5 全文索引 | 查询模式浅（1~3 跳遍历），关系表够用，**不需要 Neo4j**；100% 本地，代码不出机器（公司敢用于私有仓库的原因） |
| ③ 解析 Resolution | 把引用解析到定义：调用→定义、导入→源文件、URL 路由→handler；支持跨语言（TS 前端↔后端路由、RN↔原生模块） | 提取只知道"有个调用叫 verifyJWT"，解析才知道它定义在哪 |
| ④ 自动同步 Auto-Sync | OS 原生文件事件（Windows=ReadDirectoryChangesW）监控项目，2 秒防抖增量更新 | 图谱**永不 stale**，改代码即更新，无需手动重建 |

## 三、怎么跑的：MCP 接口（呼应已学）

`codegraph serve --mcp` 启动一个 stdio MCP Server（[[06-MCP]] 站那套），Claude Code 等 Host 启动时拉起子进程。**配置分两个时刻，容易混**：

1. **`npm i -g @colbymchenry/codegraph` 时**——安装器扫描本机 agent，把 MCP Server 注册写进 agent 配置（Claude Code 的 `~/.claude.json` 的 `mcpServers` 段）。**MCP 配置在这一步完成，与项目无关。**
2. **`codegraph init -i` 时**——只做项目级的事：生成 `.codegraph/` 索引库，不改 MCP 配置。
3. Agent 启动时 Server 挂着，但**只有当前目录存在 `.codegraph/` 才真正干活**——配置=枪，索引=子弹。

新版工具设计趋势：默认只暴露 **`codegraph_explore` 一个工具**（旧版 8~10 个），输入符号名/自然语言问题，一次返回相关源码+调用路径+影响半径。理由：一个工具减少 agent 选错工具的概率（对比别的同类工具暴露 14~17 个）。另有 7 个细粒度工具（`codegraph_search/callers/callees/impact/node/files/status`）默认不列出，输出已内联在 explore 响应里。

图查询语义速记：`callers`=反向边遍历、`callees`=正向边遍历、`impact`=**反向可达性**（从 X 出发沿 calls 边反向走传递闭包，所有能到达 X 的节点=爆炸半径）。注意"下游"一词在调用链里有歧义——改 X 影响的是**调用 X 的人**（上游消费者），不是 X 调用的人。

## 四、命令与模式

```bash
npm i -g @colbymchenry/codegraph   # 安装+写 MCP 配置；或 npx 零安装
cd your-project && codegraph init -i   # 建索引，生成 .codegraph/
```

| 命令 | 作用 |
|---|---|
| `codegraph init -i` | 交互式初始化，建索引 |
| `codegraph status` | 看索引统计（符号数/边数/同步状态） |
| `codegraph sync` | 手动增量更新（平时不需要，auto-sync 兜底） |
| `codegraph query <关键词>` | 按名称搜索符号 |
| `codegraph callers <符号>` | 谁调用了它 |
| `codegraph callees <符号>` | 它调用了谁 |
| `codegraph impact <符号>` | 变更影响分析（反向可达性） |
| `codegraph affected` | 受改动影响的测试文件（CI 场景） |
| `codegraph uninstall` | 从所有 agent 移除配置+卸载 |

**提问模式决定图谱用不用得上**（Agent 看 MCP 工具 description 决定调不调，"像不像关系型查询"是关键）：

| ❌ 形容词式（诱导 grep） | ✅ 点名符号+点名关系（诱导查图） |
|---|---|
| "看看登录相关的代码" | "`login()` 的完整调用链是什么？" |
| "帮我改一下订单逻辑" | "修改 `OrderService.createOrder()` 会影响哪些模块？" |
| "这个项目怎么组织的" | "从 Controller 入口到数据库访问的路径是什么？" |

**团队工程细节**：`.codegraph/` 进 `.gitignore`（本地索引是衍生物，提交会污染 diff）；README setup 步骤写明"clone 后先 `codegraph init -i`"，否则新人拿到的是没子弹的枪。

## 五、实测：fastapi 上的 A/B 对照

前提：`git clone --depth 1 fastapi`（中型、结构规整的开源库）；CLI `callers` 结果先经**人工 grep 验证为 ground truth**（建立对索引的信任）；同一问题分别让 Claude Code 用/禁用 codegraph 跑一遍。

| 组 | 工具调用 | 明细 |
|---|---|---|
| 用 codegraph | **5 次** | 3× `codegraph_explore` + 1× Grep + 1× Read |
| 不用（baseline） | **7 次** | Grep×2 → Read×3+Grep×1 → Read×1（分 3 个并行批次） |

- 调用次数 ↓约 29%，仍保留少量 Grep/Read 属正常——图谱负责**定位**，确认周边细节偶尔仍要读文件。
- baseline 只 2 次 Grep 就命中且会分批并行——说明 **fastapi 结构太规整，grep 本来就不迷路**；官方降幅最大的场景是 grep 要试错很多轮的混乱大仓库。**baseline 越烂，图谱收益越大。**
- 样本=1 个问题，单次实验方差大，只当定性参考。

## 六、对比官方 Benchmark（[[12-应用层Benchmark评测]] 的批判框架应用）

官方：7 个代码库，工具调用 ↓71%、token ↓57%、速度 ↑46%、成本 ↓35%。我的实测 ↓29%。差异分析用四问框架：

1. **在什么任务上测的？**——关系型查询（找调用者/追路径/架构理解）恰是图谱主场，有选择偏差；"把这个按钮改成红色"图谱帮不上忙。
2. **对照组是什么？**——无索引裸 agent；裸 agent 本身可能是弱 baseline。
3. **省 token 的代价是什么？**——少读 71% 文件有没有漏上下文改错代码？**任务成功率有没有掉**是最常被省略的指标；成功率 90%→75% 就是赔本买卖。
4. **谁测的？**——官方自测有动机偏差；要第三方在自己技术栈/规模上的复现，或自己半天跑 A/B。

> 🎯 **效率指标（token/速度/调用数）必须和效果指标（任务成功率）成对出现，单看效率数字没有意义。** 评审任何 Agent 工具宣传数据的通用框架。

## 七、劣势与边界

1. **只有语法边，没有语义边**：tree-sitter 给 `A calls B` 的语法事实，给不了"B 是 A 的缓存失效器"的语义关系（需 LLM 抽取或人工标注，都没做）。查"谁调用 X"满分，问"这段代码为什么这么设计"零分。
2. **动态派发追不全**：大量反射、鸭子类型的运行时调用关系，语法层看不到。
3. **小项目不值得**：几千行 grep 三下完事，建图高射炮打蚊子。
4. **绿地项目不值得**：代码是 agent 刚写的，它自己"记得"。
5. **收益依赖 baseline 混乱度**：仓库越规整、agent 越会并行探索，收益越收窄（我的实测验证）。

> 🎯 判断要点：值得装的信号 = 5 万行以上 + 10+ 模块 + 多人协作 + 任务以理解存量代码为主 + 语言在解析名单内。

## 八、类似工具对比

**同赛道（本地+MCP）的分化轴 = 收尾那条原则**（确定性抽取 → LLM 抽取 → 向量，没有全赢方案）：

| 工具 | 抽取/检索方式 | 一句话差异 |
|---|---|---|
| **Serena**（oraios/serena） | **真 LSP**（IDE 那套跳转定义/查找引用） | 编译器级精度天花板，40+ 语言；代价=每语言装 LSP、配置重 |
| **CodeGraph** | tree-sitter 确定性解析 | 零配置开箱即用，一个 explore 工具打天下 |
| **Graphify** | **LLM 抽取** | 泛化（文本/图片/PDF 都能入图）但关系可能错，非 ground truth |
| GitNexus / CodeGraphContext | Neo4j/Kuzu 图数据库 | 图查询表达力强，要自运维 DB |
| claude-context | BM25+向量（Milvus） | 检索上限高，要 embedding 调用+外部 DB |

**另一类（绑自家生态，不开放 MCP）**：Cursor codebase indexing（embedding 内置）/ Sourcegraph（SCIP **精确索引**=编译器输出的引用表，跨仓库，企业私有代码搜索事实标准）/ Augment（monorepo 级 context engine）/ GitHub Copilot 索引。与第一类的区别是商业模式：开源本地接任何 agent vs 护城河只在自家生态生效。

**最轻量路线（不建图）**：Aider repo map（tree-sitter 抽符号+PageRank 排重要性，一小段概览塞 prompt）/ repomix（整个代码库打包一个文件，小项目够用）/ Understand-Anything（LLM 生成 wiki，适合 onboarding 人看，不适合 agent 查询底座）。

**选型顺序**：主力语言有 LSP 且愿配置→Serena；要零配置多语言→CodeGraph；大 monorepo/企业合规→Sourcegraph；小项目→什么都不装，repomix 打包就够（**别给 3000 行项目上图谱**，本赛道最常见过度工程）。

## 九、收尾 + 连接到已学

带走 5 件事：

1. 向量 RAG 找"长得像的"，图遍历找"有关系的"——代码理解重心是关系
2. 四阶段流水线：tree-sitter 提取 → SQLite 存储 → 解析引用 → 文件事件自动同步
3. MCP 配置在 install 时，索引在 init 时；agent 见 `.codegraph/` 才干活
4. 评 benchmark 四问：任务选择偏差/baseline 强弱/成功率代价/谁测的
5. **数据有结构用确定性工具抽取，别用 LLM；数据没结构才轮到 LLM/向量**——用 LLM 抽 AST 就能抽的东西是最常见的浪费

与 GraphRAG 的对照（阶段5 按需深挖项的预备认知）：

| | GraphRAG（微软） | CodeGraph |
|---|---|---|
| 数据源 | 非结构化文本 | 结构化源代码 |
| 抽取方式 | LLM 抽取（文本没有现成结构，只能让模型"发明"） | 确定性解析（代码自带 ground truth） |
| 抽取成本/错误率 | 贵、有幻觉风险 | 便宜、不会错 |
| 共同点 | 预建图 → 图上检索 → 精准喂上下文 | 同左 |

连接已学表：

| 已学概念 | CodeGraph 里的体现 |
|---|---|
| [[01-RAG入门教程]] 预建索引 | 索引一次反复查询的极致版：图谱 vs 向量库，检索"关系" vs 检索"相似" |
| [[06-MCP]] stdio Server | Claude Code 的 `~/.claude.json mcpServers` 注册，install 时写入 |
| [[05-Agent]] Harness | Claude Code=Host+Agent：Host 拉 MCP 子进程，Agent 决策查什么 |
| [[04-Function-Calling]] 工具 description | 提问句式（点名符号+关系）决定 agent 会不会调 `codegraph_explore` |
| [[12-应用层Benchmark评测]] | 四问框架实战：我的 A/B（↓29%）vs 官方（↓71%）差异归因 |
| [[13-CLI]] 三形态 | codegraph 同时有 CLI（人/脚本用）+ MCP（agent 用）双形态 |

🔗 价值定位：没引入新范式，是已学 RAG（图检索变体）+ MCP（stdio Server）+ Agent（Harness 集成）的产品级组装，外加 Benchmark 批判框架的一次实战应用。归「工程实践补充」，非学习路线节点。

---

## 参考资料

- [GitHub - colbymchenry/codegraph](https://github.com/colbymchenry/codegraph)（官方 README + benchmark）
- [腾讯云：CodeGraph为什么突然这么火](https://cloud.tencent.com/developer/article/2713192)（四阶段流水线中文详解）
- [知乎：9 天狂揽3万+ Star！CodeGraph 让AI 代码助手效率翻倍](https://zhuanlan.zhihu.com/p/2045154422423023836)
- [Antão Almada: Knowledge Graph Tools for AI Code Agents](https://antaoalmada.dev/posts/Code-Agent-Knowledge-Graphs)（四工具对比：Graphify/GitNexus/codebase-memory-mcp/CodeGraph）
- [Sverklo: Best MCP Servers for Code Intelligence](https://sverklo.com/blog/practical-guide-mcp-code-intelligence)（12 个同类 MCP 代码智能工具对比）
- [Tokenade: CodeGraph Alternatives](https://tokenade.net/en/articles/codegraph-alternatives)（6 工具对比，含 Serena LSP 论述）
