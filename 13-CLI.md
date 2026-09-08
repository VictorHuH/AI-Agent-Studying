# 💻 CLI：AI 工具的通用接口（工程实践笔记）

> 学习日期：2026-09-07
> 定位：工程实践调研，非学习路线节点。**触发场景**：工作中第三方 AI 工具同时提供 MCP、CLI 两种形式，搞懂这是什么、怎么选。
> 路线位置：站在 MCP ✅ + Skill ✅ + Agent ✅ 之上——工具接口形态的补全拼图
> 关键词：进程契约、三形态（CLI/MCP/Skill）、Agent 四步循环、发现即集成

---

## 一、本质：CLI 是操作系统的原生 API

CLI = Command-Line Interface。`git commit`、`pip install`、`python xxx.py` 全是。本质契约只有三条：

| 契约 | 内容 | 类比 |
|---|---|---|
| **参数进** | 命令 + 参数，`--help` 是约定俗成的说明书 | 函数的形参 + 文档 |
| **文本出** | stdout = 干净数据（给管道下游用）/ stderr = 日志报错（给人看） | 返回值 vs 日志 |
| **退出码报成败** | 0 = 成功，非 0 = 失败，脚本/CI 不读文本就能分支 | 异常信号 |

**对比定位**：GUI 的契约只给人眼看（无法自动化）；HTTP API 契约强但要服务器+网络+鉴权；**CLI 契约刚好够自动化——进程级、零依赖、可组合**（`a --json | jq` 管道串联的基础就是 stdout/stderr 分离）。

**Agent 四步循环**（实证过，见第三节）：发现（`--help`）→ 学习（子命令 `--help`）→ 执行 → 验证。全程没人写一行工具定义，靠的只有 CLI 契约 + Bash 工具。

---

## 二、为什么 AI 工具厂商同时提供 MCP 和 CLI

同一个工具（如合同审查）两种形态，覆盖两类用户：

| | MCP 形态 | CLI 形态 |
|---|---|---|
| 谁调用 | MCP 宿主（Claude Desktop/Cursor/Claude Code） | 人、脚本、CI、任何有 shell 的 Agent |
| 怎么调用 | JSON-RPC 协议，`tools/list` 自动注册 | 直接跑命令 |
| 工具发现 | 宿主启动时自动握手，LLM 天生知道 | LLM 自己跑 `--help` 发现 |
| 参数 | JSON Schema + 类型校验 | 字符串拼命令，拼错运行时才炸 |
| 上下文成本 | **Schema 常驻上下文**（挂 10 个 server 光工具列表就吃不少 token） | **按需加载**（用时 `--help`，用完丢） |
| 权限 | 逐工具细粒度授权 | Bash = 全权限 shell（企业 IT 顾虑点） |
| 状态 | 常驻进程（连接池/缓存/会话） | 每次新进程，无状态 |
| 集成成本 | 厂商要写 MCP Server | **什么都不用做**，CLI 已存在 |

**核心取舍一句话**：MCP 是为 LLM 量身定制的结构化接口，CLI 是操作系统和人类已有的通用接口——而 **Agent 的 Bash 工具让 LLM"降级兼容"了后者**。所以厂商"顺手提供 CLI"= 免费获得 Agent 生态。

**选型直觉**：工具少、高频、深度集成 → MCP；工具多、低频、通用 → CLI 更省上下文。

**加上 Skill，接口三形态**（拼图完整版）：

| 形态 | 本质 | 给谁用 |
|---|---|---|
| **CLI** | 进程契约（参数进/文本出/退出码） | 人、脚本、CI |
| **MCP** | 结构化协议（Schema + 常驻进程） | MCP 宿主里的 LLM |
| **Skill** | markdown 说明书 + 脚本 | Claude 读了说明书自己决定怎么调 CLI/MCP |

Skill 是第三条路：不写代码接口，直接把使用说明喂给 LLM（"教 Agent 用工具"）。

---

## 三、实战实证：flashcard.py

20 行 argparse 写的学习卡片 CLI（`Code/flashcard.py`），验证了完整链路：

### 3.1 Agent 四步循环（盲测实录）

```
① 发现   → python flashcard.py --help        （"哦，有 add/list 两个子命令"）
② 学习   → python flashcard.py add --help    （"哦，要 question answer 两个参数"）
③ 执行   → python flashcard.py add "问题" "答案"
④ 验证   → python flashcard.py list           （确认写入成功）
```

零工具定义、零 MCP Server——CLI 契约 + Bash 工具 = 万能接口的实证。

### 3.2 盲测暴露的真实问题（比成功更有教育意义）

**问题 1：Windows 编码坑。** 首次 `--help` 中文全乱码（控制台默认 GBK）。对 Agent 来说乱码的帮助文档 = 工具不可用。修复：脚本开头 `sys.stdout.reconfigure(encoding="utf-8")`（stderr 同理）。

**问题 2：工具是黑盒，能力边界撞上才知道。** `--tag` 只搜问题字段不搜答案，明明答案里有 "Agent" 的卡片被漏掉。这就是 Agent 用 CLI 的常态：**工具不够聪明时，智能补在 Agent 侧**（降级策略：搜索扑空 → 全量拉取 → 自己过滤），代价是多一次调用多一点 token。根因修复一行：过滤条件加 `or args.tag in c["answer"]`。

**对比 MCP**：结构化 Schema 也解决不了搜索逻辑缺陷，但边界更早可见——这正是"发现即集成"和"契约质量 = Agent 使用体验"的含义。

### 3.3 给 AI 用的 CLI，验收清单（人工 5 分钟）

1. **代码走读**：数据写哪、有无危险操作、逻辑对不对
2. **三层 `--help`**：主命令/子命令/参数，输出可读（Agent 的唯一说明书）
3. **流分离**：`cmd 2>/dev/null` 只剩数据；`cmd 1>/dev/null` 只剩统计
4. **退出码**：失败路径 `echo $?` 非 0，成功为 0
5. **边界**：特殊字符（空格/引号）原样存入；空库 list 报错不崩溃

② 验输入契约、③④ 验输出契约、⑤ 验健壮性——清单就是三要素契约的镜像。

---

## 四、真实案例复盘：WorkBuddy 连接器（2026-09-08 补）

工作中遇到腾讯 CodeBuddy 的 WorkBuddy 文档，其"连接器"官方定义就是本笔记的三形态框架：

> 连接器是 WorkBuddy 与外部服务之间的桥梁，将外部能力引入 AI 工作流。技术形态分为：**MCP + CLI（标准化协议）** / **Skill + CLI（内置脚本）**。二者在数据收集和权限边界上遵循一致原则。

**翻译：** 两种形态的"+CLI"= 能力最终都由命令行程序执行（活谁来干，一样）；MCP vs Skill = 模型怎么学会用它（协议自动注册 vs 读说明书自学，不一样）。

| | MCP + CLI | Skill + CLI |
|---|---|---|
| 物理形态 | 一个 MCP Server 进程（WorkBuddy 当 Host 启动） | 一个技能包：SKILL.md 说明书 + scripts 内置脚本 |
| 模型怎么发现 | `tools/list` 自动注册进工具列表 | 平时不占上下文，任务匹配时读说明书 |
| 对应本仓库代码 | `Code/test_mcp_server.py` 那套写法 | `Code/flashcard.py` + Agent 四步循环的原始形态 |
| 谁在用 | 自定义连接器（装自定义 MCP 服务，"配置方式与 MCP 配置类似"） | 官方内置连接器（QQ 邮箱、腾讯文档等由厂商打包） |

**两处细节印证判断：**
- "自定义连接器的配置方式与 MCP 配置类似" → 反推自定义连接器走 MCP+CLI 形态（协议注册，无需说明书）
- "数据收集和权限边界遵循一致原则"（独立授权/不主动抓取/不超已有权限）→ 权限管控是**产品策略层**的东西，写在连接器管理层（Harness 职责），与技术形态正交

**判据沉淀：** 看到任何工具接入方案，问一句"**模型怎么知道这个能力——协议注册，还是读说明书？**"前者 MCP 系，后者 Skill 系，底层干活的多半都是 CLI。

---

## 五、连接已学

- **[[04-Function-Calling]]**：Agent 用 CLI 的机制就是 FC——LLM 决定调 `bash` 工具（参数=命令字符串），运行时执行，stdout 回填，循环
- **[[06-MCP]]**：MCP vs CLI 是同一工具的两种接口形态，MCP 为 LLM 优化（Schema/发现/细粒度授权），CLI 为操作系统和人类已有（零集成成本）
- **[[07-Skill]]**：三形态拼图的第三块——说明书直接喂给 LLM，"教 Agent 用工具"的声明式路线
- **[[05-Agent]]**：Agent 的降级自救（搜索扑空→全量拉取）= ReAct 循环里 Observation 驱动策略调整
- **Claude Code 本身就是双形态活案例**：交互时是 CLI，`claude -p "..." --output-format json` 时是被脚本调用的 CLI（CI 自动化 review 就这么用）
- 概念照进现实：Claude Code 的 Bash 工具 = "Agent 降级兼容一切 CLI"的产品化

**边界认知**：CLI 不引入新范式，是已学 FC/Agent/MCP 的接口形态补全——工具生态的最底层通用底座。

## 代码资产

- `Code/flashcard.py`（argparse CLI：add/list + --tag 搜索，含 UTF-8 修复）
