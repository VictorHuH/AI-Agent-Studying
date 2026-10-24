# Multica（AI Native 平台：Agent 团队工作区）

> 2026-10-24 调研完成。**非学习路线节点，是工作中实测的工具调研**，归入「工程实践补充」。
> 衔接 [[05-Agent]] / [[09-LangGraph]] / [[10-多Agent与SubAgent]] / [[13-CLI]]：Multica 是这些概念的**产品级组装**——把 Agent 执行外包给 Claude Code 等 Harness，自己在外面补调度、治理、沉淀三层。
> 关键词：AI Native 平台 / 任务即工作单元 / 运行时 Runtime / 小队 Squad / Webhook / Plugin SDK

---

## 核心认知

> **Multica 不自带模型。它把 Claude Code、Codex、Cursor 等 Agent CLI 当成可插拔的执行器，自己在外面补 Harness 不管的三件事：调度、治理、沉淀。**
>
> 它的工作单元不是「一次对话」，而是「一个任务」——需求、讨论、运行记录、产出、状态、成本全挂在任务下，会话关了也不丢。

---

## 一、问题：多智能体时代的「会话孤岛」病

README 开头就是病历：

> 你手上已经同时开着 Claude Code、Codex，还有另外三个智能体。每一个都关在自己的终端标签页里，会话一关就什么都不记得，同一段上下文你今天已经讲到第四遍。结果是智能体越加越多，你越忙。

症状与根因：

| 症状 | 根因 |
|---|---|
| 上下文反复重讲 | 状态活在会话里，会话结束即销毁 |
| 多开标签页管理不过来 | 人肉充当调度器 |
| 不知道谁在干什么 | 没有任务级状态，只有终端输出 |
| 出问题查不到 | 执行日志随终端滚走 |
| 成本失控 | 只有月底账单，没有按任务归因 |
| 做完不敢直接上线 | 没有验收卡点，只能人肉盯 diff |

🎯 **本质：Agent 的执行能力已经不是瓶颈，围绕执行的「调度 + 治理 + 沉淀」才是。** AI Native 平台卖的不是模型，是这三层。

---

## 二、原理：平台 = 执行插槽 + 三层外挂

```
┌──────────────────────────────────────────┐
│ 调度层：任务队列 / 分配 / 并发 / 重试      │  ← 平台
├──────────────────────────────────────────┤
│ 治理层：权限 / 审计 / 人在环 / 验收        │  ← 平台
├──────────────────────────────────────────┤
│ 沉淀层：记忆 / 知识 / Skill / 评估         │  ← 平台
├──────────────────────────────────────────┤
│ 执行层：Claude Code / Codex / Cursor …    │  ← 插槽（不自带模型）
└──────────────────────────────────────────┘
```

关键判断：**执行层是插槽，不是平台自己实现的部分。** 官方原话：

> Multica 不自带模型。它驱动的是你本来就装好、登录好的那些智能体 CLI——目前支持 26 种——所以换提供方就是切个下拉框，谈不上迁移。

这直接决定了它的能力边界：**平台不提升单次执行质量，只提升执行的吞吐、可追溯和治理。** 和 [[08-LangChain]] 那句「框架是放大器，不是能力来源」同构。

---

## 三、怎么跑的：一次执行的完整链路

官方定义的五步：

1. **任务提供上下文。** 任务保存工作说明、讨论和负责人；分配给智能体后，系统使用该智能体的指令、模型、Skill 和运行时配置。
2. **Multica 创建运行。** 运行进入队列；没有在线运行时时，它在队列中等待。
3. **运行时领取。** 连接电脑上的在线运行时领取后，调用智能体配置的 AI 编程工具。
4. **AI 编程工具在本地执行。** 读取工作目录、运行命令、生成结果。
5. **结果写回任务。** 进度、评论和结果显示在任务的时间线与执行日志中。

```
建任务 → 派给智能体/小队 → 运行入队 → 运行时领取 → 本地 CLI 执行 → 结果写回任务时间线
```

### 数据与执行的边界（做开发前必须内化）

| Multica 服务器 | 你的电脑 |
|---|---|
| 工作区、任务、评论和状态 | AI 编程工具及其凭据 |
| 智能体配置与 Skill | 代码目录和本地文件 |
| 运行状态、执行记录和结果 | 实际的文件修改与命令执行 |

⚠️ **例外**：智能体的 `custom_env` 和 MCP 配置保存在服务器侧，执行时下发。**「本地执行」≠「所有 secret 都只在本机」**，不要把不愿离开电脑的密钥写进 `custom_env`。

---

## 四、核心概念

| 概念 | 官方定义 | 一句话理解 |
|---|---|---|
| **工作区** | 团队共同工作的独立范围 | 租户边界 |
| **任务** | 一项要完成的工作及围绕它的描述、讨论、状态和历史 | **日常工作的基本单位** |
| **项目** | 把相关任务组织在一个目标下，可绑定仓库/目录等资源 | 任务分组 + 执行资源 |
| **智能体** | 一份可复用的配置：名称、指令、模型、Skill、Access、运行时 | **身份，不是常驻进程** |
| **Skill** | 可复用的能力包；指令定义「是谁」，Skill 说明「这类工作怎么做」 | 跨智能体复用的方法库 |
| **运行时** | 执行实际发生的地方：一台电脑 + 一款 AI 编程工具 | **可被调度的地址** |
| **运行** | 智能体的一次具体执行记录 | **执行尝试，不是任务本身** |
| **小队** | 一名 leader 智能体 + 若干成员（人/智能体） | **组织内路由，不是调用栈** |
| **对话** | 不依附任务的交流，每条消息触发一轮执行 | 轻量入口 |
| **收件箱** | 成员的通知中心；智能体不使用 | 人机边界 |
| **自动化** | 按时间表或外部事件触发执行 | cron / webhook |

### 三个最容易被忽略的性质

**① 任务 1 : 运行 N**

> 一个任务可以先后产生多次运行；**运行结束不等于任务完成**。

任务 = 工单，运行 = 师傅上门一次。师傅中途下班（运行时离线），工单还在；换个人再来，就是新的一条运行。

**② 智能体不是进程**

> 智能体本身不是一个持续运行的进程。它是一套可以反复使用的身份和配置，只有收到工作时才会产生具体的运行。

四种触发：分配任务 / 评论中 `@` / 直接对话 / 自动化。**事件唤醒身份，不是进程常驻。**

**③ 运行时是数据，守护进程是进程**

| | 守护进程 | 运行时 |
|---|---|---|
| 是什么 | 一台电脑上的后台**进程** | 服务器上的一条**记录** |
| 数量 | 一机一个 | 一台电脑 × 一款工具 × 一个工作区 = 一条 |
| 关系 | 1 个守护进程 → N 个运行时 | 运行时本身不执行任何东西 |
| 死了会怎样 | 它注册的运行时变**离线** | 记录还在，重启后恢复，不新建 |

官方例子：一台电脑装 Claude Code + Codex、连两个工作区 → **1 个守护进程，4 条运行时**。

---

## 五、小队 vs 多 Agent vs SubAgent（最容易混的三兄弟）

| | 多 Agent（[[09-LangGraph]]） | SubAgent（[[10-多Agent与SubAgent]]） | 小队 Squad |
|---|---|---|---|
| **协调介质** | 图里的 State | 函数返回值 | **任务时间线（数据库）** |
| **交接方式** | 边 / Send | tool call | **评论里 `mention://` → 触发新 run** |
| **有进程在等吗** | 有（同一张图） | **有**（父等子） | **没有** |
| **生命周期** | 一次 invoke | 父调用期间 | 多条独立 run，可跨天 |
| **失败单位** | 整张图 | 整条调用链 | **一条 run** |
| **状态在哪** | State / Checkpointer | 父进程内存 | **持久化任务时间线** |
| **成员能是人吗** | 不能（要 HITL 中断） | 不能 | **能，人类是正式成员** |
| **谁决定派给谁** | 写死的边 | 写死的 tool 描述 | **leader 运行时读任务决定** |

### 一句话记

> **SubAgent 是调用栈，多 Agent 是图，小队是组织架构。**
>
> 调用栈里，调用者必须知道被调用者是谁（tool 名写死）；
> 组织架构里，领导看着花名册和任务现场，临时决定派给谁。

### 三个必须纠正的直觉

1. **小队不是并行。** 官方明说：「不会自动提高并发」。它解决的是「把工作交给谁」，不是「同时干」。
2. **队长不干活。** 「派完活，队长不亲自动手。」只做路由和评估，把活写进任务 activity 时间线。
3. **人类是正式成员。** `@` 智能体触发新运行，`@` 人则进收件箱。做人机协作不需要像 LangGraph 那样专门写 `interrupt_before`。

### 为什么它更抗故障

小队的状态不在进程里，**在持久化的任务时间线里**。所以：

- 任何进程都可以死掉重启，工作不丢
- 现在执行的 run 失败了，任务本身不失败，可重试/换人/换机器
- 没有「父进程在等子进程」这种跨进程阻塞

**准确说法：持久化的事件日志 + 事件驱动的调度。** 前者保证「进程死了还在」，后者保证「没人等谁」。

---

## 六、四个开发者插槽

「在上面做开发」不是一条路，是四条。官方说的「界面上能点的，CLI 和 API 里都能调」只覆盖了前三面。

| # | 面 | 方向 | 凭证 | 用途 |
|---|---|---|---|---|
| 1 | **UI**（Web/Desktop/Mobile） | 人 → 平台 | 浏览器 cookie | 看、点、拖、验收 |
| 2 | **CLI** (`multica`) | 脚本 → 平台 | `mul_` PAT | 终端、CI、批量操作、本地守护进程 |
| 3 | **内部 HTTP API** `/api` | 服务 → 平台 | `mul_` PAT | 长期集成、高频、细粒度控制 |
| 4 | **Webhook** | 外部事件 → 平台 | URL 里的 `awt_` | GitHub/CI/告警驱动 |
| 5 | **Plugin API v1 + SDK** | 平台内嵌 → 你的代码 | `mpi_` / `mpc_` | 在界面里加自己的面板 |
| 6 | **Skill / MCP / 自定义运行时** | 能力扩展 | 平台配置 | 给智能体加「怎么做 / 用什么」 |

### CLI 与 API 的关系

**CLI 是 API 的客户端，外加一个本地职责。**

```
你的脚本 ──> CLI ──> /api/*（PAT）
你的服务 ─────────> /api/*（PAT）
CLI 额外管 ──────> 本机守护进程（API 管不了）
```

功能上 **API ⊇ CLI**；CLI 多出来的是 `daemon start/status/logs` 这类本机操作。

选型：终端/一次性/CI → CLI；长期服务/高频/需要分页重试并发 → 内部 API。

### 凭证谱系（值得抄的设计）

| 前缀 | 谁用 | 范围 | 生命周期 |
|---|---|---|---|
| `mul_` | 你 / CLI / 脚本 | 你有权访问的全部工作区和 API | 30d/90d/1y/永久，自动续期 |
| `mat_` | 智能体运行时 | 绑定 **用户 + 工作区 + 智能体 + 运行** | 最长 24h，运行结束清理 |
| `mpi_` / `mpc_` | 插件 | 安装身份 + manifest scopes | 安装/回调 |
| `mcn_` / `mdt_` | 平台内部 | 内部协议 | 不用管 |

🎯 **最值得抄的一条**：智能体永远拿不到你的 PAT。守护进程领活后，服务端发一个 `mat_` 临时令牌，绑定到这次运行，24h 过期，行为记在智能体名下，也调不动 owner 级敏感操作。**Least privilege 落到执行边界。**

### Plugin SDK（前端背景的最优插槽）

`@multica/plugin-sdk`：一块运行在沙箱 iframe 里的界面，和宿主通信：

```js
import { multica } from "@multica/plugin-sdk";

const ctx   = await multica.context.get();      // 谁在看、在哪个任务
const issue = await multica.issue.get();        // 读任务
await multica.issue.comment({ body: "hello" }); // 以用户身份发评论
const note  = await multica.storage.user.get("note");
multica.ui.resize(320);
```

Public API v1 只有 5 个路径：

```
/context
/issues/{issue_ref}
/issues/{issue_ref}/comments
/storage/{scope}
/storage/{scope}/{key}
```

三条硬约束：

1. **双重权限**：插件能力 = 管理员授予的 scope ∩ 当前用户本来就能做的事（不提权）。
2. **评论不触发 `@` 派活**：面板不能靠发文字偷偷拉起智能体。
3. **沙箱**：`sandbox="allow-scripts"`、无同源、无 localStorage/cookie、CSP 由平台生成；访问网络必须声明 `net:` scope。

发布：manifest + 文件打 zip → Settings → Plugins。版本不可变，升级要管理员确认；开发用 `MULTICA_PLUGIN_DIR` 从磁盘直发。

---

## 七、命令与模式

### 安装与连接

```bash
# Windows PowerShell
irm https://raw.githubusercontent.com/multica-ai/multica/main/scripts/install.ps1 | iex

multica version
multica setup            # 连接 Cloud，打开浏览器登录，启动守护进程
multica auth status
multica daemon status
multica runtime list
multica workspace list
```

### 任务与运行

```bash
multica issue list --limit 5 --output json
multica issue create --title "修复登录失败" --assignee "Engineer" --output json
multica issue runs MARS-9 --output json          # 一个任务的全部运行
multica issue run-messages <task-id> --issue MARS-9
multica issue cancel-task <task-id> --issue MARS-9
multica issue rerun MARS-9
```

### 智能体 / Skill / 小队

```bash
multica agent list
multica agent create --name "Reviewer" --runtime-id <id> --model <model>
multica agent skills add <agent-id> --skill-ids <skill-id>
multica skill import --url <skill-url>
multica squad create --name "Product Delivery" --leader <agent>
multica squad member add <squad-id> --member-id <agent-or-member> --type agent
```

### 自动化与 Webhook

```bash
multica autopilot create \
  --title "Webhook 试验" \
  --agent "Engineer" \
  --mode create_issue \
  --issue-title-template "外部事件触发 {{date}}" \
  --description "收到外部事件后，回复一句话确认。"

multica autopilot trigger-add <autopilot-id> --kind webhook --label "manual test"
multica autopilot trigger-add <autopilot-id> --kind schedule --cron "0 9 * * *"
multica autopilot runs <autopilot-id>
```

---

## 八、实测：Webhook 全链路

### 实验步骤

1. 建自动化（`create_issue` 模式，负责人 Engineer）
2. 挂 webhook 触发器，拿到 URL
3. `curl` 发一次 POST
4. 观察返回、任务、运行、评论

### 结果

```bash
curl -X POST "https://multica.ai/api/webhooks/autopilots/awt_..." \
  -H "Content-Type: application/json" \
  -d '{"hello":"world","source":"cli-test"}'
```

返回（**立即**，不等执行）：

```json
{
  "autopilot_id": "8989dcd6-...",
  "delivery_id": "01a16baf-1130-...",
  "run_id": "01a16baf-1139-...",
  "status": "accepted",
  "trigger_id": "adee13a9-..."
}
```

异步继续：

```
MARS-13 建出 → 派给 Engineer → 45 秒后 completed → 评论确认 → 状态 in_review
```

### 观察到的四个事实

| 事实 | 证据 |
|---|---|
| **异步** | 返回 `accepted` 时智能体还没开始；15 秒后查仍在 `running`，45 秒后才 `completed` |
| **payload 透传** | 智能体评论里原样出现 `{"hello": "world"}` 和 `source: cli-test` |
| **智能体有写权限** | 它把 MARS-13 的标题改成了自己总结的版本，并把状态推到 `in_review` |
| **触发来源可审计** | `attribution.source = trigger_owner` |

### `attribution.source` 谱系（实测见过的三种）

| 值 | 含义 |
|---|---|
| `direct_human` | 人直接派的（MARS-12） |
| `delegation` | 队长派给成员的（MARS-9） |
| `trigger_owner` | 自动化 / webhook 触发的（MARS-13） |

一个字段就能回答「这活是谁发起的」——审计能力落到数据上的样子。

### 对照实验：同一脚本，不同负责人

`Code/multica_run.py` 做了「建任务 → 轮询 runs → 等终态 → 打印产出」。只换 `--assignee`：

| | MARS-12（派给智能体） | MARS-9（派给小队） |
|---|---|---|
| 负责人 | Engineer | AI新闻小队 |
| **运行数** | **1** | **5** |
| `kind` | `direct` | `direct` + `comment` |
| `attribution.source` | `direct_human` | `delegation` |
| `is_leader_task` | 无 | 3 条 `true` |
| 产出 | 一句话确认 | 新闻清单 + HTML |

**最干净的小队证明：换一个 `--assignee`，运行数从 1 变成 5。**

### 成本实测（MARS-12，一句话任务）

| 轮次 | 模型 | 输入 | 输出 | 缓存读 |
|---|---|---|---|---|
| 1 | `deepseek-v4.1-flash` | 352 | 250 | 640 |
| 2 | `deepseek-v4.1-flash[1M]` | **298,587** | **776** | 858,240 |

两件事：

1. **成本几乎全是 Harness 的固定上下文。** 任务是「回一句话」，产出 776 token，但第二轮输入接近 30 万 token。
2. **`provider` 和 `model` 是两个字段**：`provider: claude`（Harness）、`model: deepseek-...`（实际模型）。平台把「谁在跑」和「用什么跑」分开记账。

→ 工程含义：**碎任务按次跑不划算**；能合并就合并，或给轻任务换更轻的运行时/模型。

---

## 九、劣势与边界

| 边界 | 说明 |
|---|---|
| **不提升单次执行质量** | 底层还是你自己登录的 Claude Code；模型、工具、单次质量不变 |
| **有协调成本** | 建任务、配运行时、维护看板；一次性小任务直接开 Claude Code 更快 |
| **依赖本机 CLI** | 运行机器必须装好并登录至少一款受支持的 Agent CLI，平台不替你安装 |
| **运行时离线会断执行** | 正在执行的 run 会失败；排队中的等待；任务本身不失败 |
| **平台不保证即时远程停止** | 电脑离线时，服务端可撤销访问，但本地进程可能继续执行 |
| **Webhook 默认裸地址** | `has_signing_secret: false`，URL 泄露 = 别人能花你的 token |
| **重试可能重复触发** | 发送方超时重试会再 POST 一次，幂等要自己保证 |
| **Plugin 沙箱限制** | 无 localStorage/cookie；网络必须声明 `net:` scope；版本不可变 |
| **自托管有运维成本** | Docker Compose / Helm + PostgreSQL 17；iOS 客户端要自己编译 |
| **任务模型偏工程协作** | 非软件类工作未必适合用 issue/看板组织 |

🎯 **判断要点**：需要「回头看」或「多个 Agent/多个人并发」时，它才开始值钱。否则直接用 CLI 更快。

---

## 十、同类对比

| 平台 | 定位 | 执行层 | 核心差异 |
|---|---|---|---|
| **Multica** | Agent 团队工作区（看板 + 任务） | 驱动本机 Agent CLI（26 种） | 任务即工作单元；自托管；人机混编小队 |
| **Pragma** (`pqpo/pragma`) | 跨 Harness 的 Agent 团队平台 | Runtime adapters（Claude Code/Codex/PI/…） | **方法即资产**：YAML DSL + `.pragma` 可移植包；Desktop/CLI/SDK 三入口；AGPL |
| **Dify / Coze / FastGPT** | 低代码 AI 应用平台 | 平台内置模型与工具 | 在平台里**搭应用**，不是管理 Agent CLI；不强调任务治理 |
| **n8n** | 工作流自动化 | 确定性节点 | 流程写死，无 Agent 自主决策 |
| **Claude Code** | 单个 Coding Agent | 自带 | 没有任务队列/看板/审计/多人协作；一次性会话 |
| **LangGraph** | Agent 编排框架 | 你的代码 | 是**库**不是平台；状态、调度、治理都要自己写 |

**一句话**：LangChain/LangGraph 给你零件，Dify/Coze 给你车间，Multica/Pragma 给你**团队的工作方式**。

---

## 十一、收尾 + 连接到已学

### 带走五件事

1. **AI Native 平台的分水岭不是「有没有 AI」，是「工作单元是不是任务」。** 会话 → 任务，才谈得上调度、审计、沉淀。
2. **执行层是可插拔的。** 不自带模型不是缺陷，是架构选择——它让平台不绑厂商，也让你换 Harness 零迁移。
3. **任务 1 : 运行 N。** 把「工作」和「尝试」分开，是重试、审计、成本归因的前提。
4. **小队 = 持久化事件日志 + 事件驱动调度。** 不是调用栈，所以没有进程在等谁，跨天、跨机器、跨人都成立。
5. **凭证要按执行边界切。** `mul_`（人）/ `mat_`（单次运行）/ `mpi_`（插件）——Agent 永远拿不到你的 PAT。

### 连接已学

| 已学概念 | 在 Multica 里的体现 |
|---|---|
| [[05-Agent]] ReAct 循环 | 外包给 Claude Code（Harness 变成插槽） |
| [[05-Agent]] 三层记忆 | 任务时间线持久化 + ContextStore/记忆沉淀 |
| [[06-MCP]] | 智能体配置里可挂 MCP |
| [[07-Skill]] | 一等公民；跨智能体复用；`skill import` |
| [[09-LangGraph]] Checkpointer | 升级为「任务本身持久化」，run 是挂在下面的尝试 |
| [[09-LangGraph]] HITL | 审核中 + 收件箱；人类是小队正式成员 |
| [[10-多Agent与SubAgent]] | 小队是第三种形态：组织路由 |
| [[12-应用层Benchmark评测]] 数据飞轮 | 运行产生证据 → 沉淀知识/Skill → 评估下一版 |
| [[13-CLI]] | 「界面能点的 CLI 都能调」；`--output json` 供脚本消费；CLI = API 客户端 + daemon 管理 |
| [[18-REA逆向工程]] | 同样的「不确定性/来源可审计」思路：`attribution.source` 落到数据 |

**价值定位**：没引入新范式，是已学 Agent/MCP/Skill/LangGraph/多Agent/CLI 的**产品级组装**。唯一真正的新概念是「Harness 从你手写的代码变成平台上的插槽」。归「工程实践补充」，非学习路线节点。

---

## 参考资料

- [Multica GitHub](https://github.com/multica-ai/multica) / [中文 README](https://github.com/multica-ai/multica/blob/main/README.zh.md)
- [官方文档（核心概念）](https://multica.ai/docs/zh/concepts) / [工作方式](https://multica.ai/docs/zh/how-multica-works) / [守护进程与运行时](https://multica.ai/docs/zh/daemon-runtimes)
- [CLI 文档](https://multica.ai/docs/zh/cli) / [认证与令牌](https://multica.ai/docs/zh/auth-tokens)
- 源码中的公共 API 契约：`server/pkg/publicapi/v1/openapi.yaml`
- 本地实践：`Code/multica_run.py`（建任务→轮询运行→打印产出，含 self-test）
