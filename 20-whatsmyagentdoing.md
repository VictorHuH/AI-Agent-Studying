# whatsmyagentdoing（本地 Agent 可视化看板）

> 2026-11-01 调研完成。**非学习路线节点，是工作中实测的工具调研**，归入「工程实践补充」。
> 衔接 [[05-Agent]] / [[07-Skill]] / [[13-CLI]] / [[19-Multica]]：它是「Harness 的日志 → 状态机 → 实时推送」这条可观测性骨架的最小产品级实现。
> 关键词：Agent 可观测性 / 日志 tail / 状态归约 / SSE / Skill 包装 CLI

---

## 核心认知

> **不插桩、不挂钩子、不要 API key——因为每个 Agent CLI 本来就把完整会话写进了磁盘。它只读地 tail 那些 JSONL，把「最后一条有意义的日志行」翻译成一个状态，再推给浏览器画成一个办公室。**

它治的不是"Agent 不会干活"，是"**同时开着好几个 Agent 时，你不知道谁在干活、谁在等你、谁卡住了**"。

---

## 一、问题：多开的 Agent 没有统一视图

| 症状 | 根因 |
|---|---|
| 开了 4 个终端标签页，来回切换才知道谁在动 | 状态活在各自的终端里，没有跨会话聚合 |
| 某个 Agent 卡了 20 分钟，你才想起来看它 | 终端只在输出时才有信息，静默 = 无信号 |
| 想知道"刚才那个任务跑完没" | 滚屏历史找不回来 |
| 每家客户端日志格式不一样 | 没有公共 API，格式还是私有的 |

🎯 **本质：Agent 的可观测性不需要插桩，需要的是一个"日志 → 状态"的归约层。** 而日志已经免费存在了——这是整个工具唯一真正的洞察。

---

## 二、原理：五段流水线

```
磁盘 JSONL ──scan──> 候选文件 ──stat/增量读──> 新行 ──parser──> 统一 session
                                                                   │
浏览器办公室 <──SSE── 快照 JSON <──view() 时钟修正 <──状态归约 ──────┘
```

| 段 | 位置 | 做什么 |
|---|---|---|
| **扫描** | `watcher.tick()` | 每 **5 秒**重扫目录，每 **1 秒**对已知文件 stat |
| **增量读** | `watcher.track()` | 文件变大 → 只读 `offset → size`；文件变小 → 判定被重写，重开 |
| **解析** | `parsers.applyXxx()` | 每家一个适配器，归约到同一个 `session` 结构 |
| **推进** | `server.push()` | 去掉 `now` 字段比较整包 JSON，没变就不推 |
| **修正** | `server.view()` | 用**时钟**补日志里根本没有的状态 |

四个值得记住的决策：

**1. 轮询而不是 `fs.watch`。** 理由写在源码注释里：轮询在 macOS/Linux/Windows 行为完全一致，1 秒一次 stat 几百个文件很便宜。跨平台一致性 > 事件驱动的优雅。

**2. 大文件只读头尾。** `HEAD_BYTES = 128KB`（拿 cwd / title / model）、`TAIL_BYTES = 768KB`（拿当前状态）。中间的对话内容对"现在在干嘛"没有信息量。

**3. 每家一个 parser，但只维护一份状态机。** 差异被吃在 `applyClaude` / `applyCodex` / `applyGemini` / `applyOMP` … 这些适配层里，往上是统一的 `thinking / tool / typing / waiting / done / error / idle` 七态。这是「M×N 适配 → M+N」的老办法：**日志格式是 M 种，下游消费者只有 1 种。**

**4. 日志没记的状态，用时间推。** 这是全项目最巧的一处（[`server.js` `view()`](whatsmyagentdoing/src/server.js#L40)）：

| 状态 | 沉默多久后改判 | 为什么 |
|---|---|---|
| `typing`（无生命周期标记） | 45 秒 → `done` | 回复块落盘后没有后续事件 = 这一轮结束了 |
| `typing`（有生命周期标记） | 15 分钟 → `idle` | 会话被关掉时停在半轮 |
| `thinking` | 15 分钟 → `idle` | 日志只按块写，长思考看起来就是沉默 |
| `tool` | 45 分钟 → `idle` | 工具跑飞了 |
| `waiting` / `error` | 2 小时 → `idle` | 陈旧的告警 |

另外还有 `stuck` 计数：工具挂了超过 10 分钟、思考超过 8 分钟，就在 UI 上标"卡住 N 分钟"。

🎯 **一句话：状态不是日志给的，是「日志 + 时钟」共同推出来的。** 只读日志你会得到一堆永远停在 `thinking` 的僵尸会话。

---

## 三、怎么跑的：Claude Code 的状态映射

Claude Code 把每一轮对话和每次工具调用追加到 `~/.claude/projects/<项目>/<session>.jsonl`，子 Agent 在 `subagents/` 下单独一份。`applyClaude` 就看最后一条有意义的记录：

| 日志里看到 | 归约为 |
|---|---|
| `tool_use` 但没看到对应的 `tool_result` | `tool`（`activity` 带上 `Bash: npm test` / `Edit app.ts` / `mcp__github__create_pr`） |
| 工具名是 `AskUserQuestion` / `ExitPlanMode` | `waiting` |
| 助手回复块 | `typing` |
| 一轮收尾 | `done` |
| 异常记录 | `error` |

工具名还会被翻译成人话（`describeClaudeTool`）：MCP 工具切成 `server · tool`，`Read/Edit/Write` 取文件名，`Agent/Task` 显示成 `Subagent: xxx`——**UI 上那句"正在干嘛"是给人看的，不是给机器看的**。

**Claude Code 唯一补不上的洞**：它不记录权限询问。所以等审批的工具会一直显示 `Running`，而不是 `Waiting for you`。作者给的办法是可选装一个 Notification hook（`--install-hook`）往磁盘写标记文件，watcher 再读——**用一个 hook 补一个日志没记的事件**，这个权衡很干净。

---

## 四、命令与模式

```bash
node bin/cli.js                 # 默认真实会话，起在 4545（被占就 +1）
node bin/cli.js --demo          # 假团队演示，截图/试玩用
node bin/cli.js --private       # 隐藏 prompt/回复/标题，只留状态（投屏安全）
node bin/cli.js --hours 4       # 只看最近 4 小时活跃的
node bin/cli.js --json          # 打一次快照就退出（可脚本化）
node bin/cli.js --stop          # 停掉后台面板
node bin/cli.js --scenes        # 列出 3D 场景
node bin/cli.js --install-hook  # 可选：让权限询问显示成 waiting
```

装成 Skill 后就是 `/myoffice`（`SKILL.md` 的 `name: myoffice`）。**注意：Skill 在这里只是一层触发器 + 用法说明书，真正干活的还是那个 CLI**——再次印证 [[13-CLI]] 的"CLI 是底座，Skill/MCP 只是模型怎么学会用它"。

| 视图 | 说明 |
|---|---|
| High (3D) | three.js + Kenney CC0 模型，~180KB gzip + 1.3MB 模型，**选 High 才加载** |
| Medium (2D) | 零依赖 canvas 手绘，含办公室猫 |
| List | 卡片分组：Needs you → Working → Finished，带本轮计时器和 `claude --resume` 复制按钮 |

---

## 五、实测：**没有实测，只有源码走读**

> ⚠️ 诚实标注：本次只做了 clone + 读码，没有运行。尝试后台起 demo 时被执行权限拦下（外部仓库代码），所以下面全部是**静态结论**，不是跑出来的数字。

| 项 | 数据 | 来源 |
|---|---|---|
| 仓库体积 | 20 MB（`docs/` 演示图 7.9MB、`assets/` 3D 模型 1.6MB） | `du -sh` |
| 真正的代码 | ~140 KB（`src/`），~4200 行 JS | `wc -l` |
| 运行时依赖 | **0**（`devDependencies` 只有 esbuild/playwright/three，仅打包和测试用） | `package.json` |
| 版本 | 0.6.0 | `package.json` |
| Node 要求 | ≥18（本机 v24.14.1 满足） | `package.json` |
| 支持的客户端 | Claude Code / Codex / Gemini CLI / Antigravity / Copilot / OMP / Kimi / DSH / Grok | `cli.js --help` + `watcher.js` |

---

## 六、官方 benchmark

**没有。** 作者没给任何性能/收益数字，README 也没跑分。对一个"看板"类工具这算合理——它没有可量化的任务指标。反而说明它没拿营销数据凑数。

---

## 七、劣势与边界

1. **日志是按块落盘，不是按 token。** "Writing reply" 表示一段回复已经写入磁盘、这一轮没结束，**不是实时逐字**。想要打字机效果，得改 Agent 本身。
2. **Claude Code 不记录权限询问。** 等你点同意的工具显示 `Running`，只有 Codex/Gemini 才是 `Waiting for you`（除非装 hook）。
3. **日志格式不是公开 API。** 上游一改，状态就可能退化。这是所有"读别人的私有日志"工具的宿命。
4. **收益取决于你并行开几个 Agent。** 单人单会话时，`/myoffice` 不如直接看终端——**这是它最大的落点，也是最大的局限**。
5. **绝大多数代码是玩具和渠道成本。** 3D 办公室、场景包下载、8 个客户端适配、9 种语言 i18n 吃掉 90% 代码，跟你真正想学的可观测性骨架无关。
6. **它只解决"看见"，不解决"控制"。** 没有暂停、没有 kill、没有重试——那是 [[19-Multica]] 那一层的事。

---

## 八、同类对比

| 工具 | 定位 | 与它的差异 |
|---|---|---|
| **Claude Code 自带 `/status`、各 CLI 的 resume 列表** | 单工具自省 | 只有自己的会话，不聚合 |
| **ccusage / 各家 token 看板** | 成本统计 | 看历史账单，不看当下在干嘛 |
| **LangSmith / Langfuse / Phoenix** | Agent 追踪与评测平台 | 要 SDK 插桩、要上报；它是零插桩读磁盘 |
| **OpenTelemetry GenAI 语义约定** | 追踪标准 | 需要应用自己埋点，管不到别人家 CLI 的私有日志 |
| **tmux / htop** | 进程级监控 | 看得到进程在跑，看不到"在干嘛" |
| **[[19-Multica]]** | 平台侧任务治理 | 状态在服务器记录里；它状态在**本机日志**里。两端互补：一个管"派活与验收"，一个管"此刻谁在动" |

---

## 九、收尾 + 连接到已学

**带走 4 件事：**

1. **可观测性可以零插桩**——只要目标系统本来就把状态写进了磁盘。先问"日志在不在"，再问"要不要埋点"。
2. **状态 = 日志 + 时钟。** 只按事件推进状态机，会留下一堆永远 `thinking` 的僵尸；沉默本身是信息。
3. **推送要先去重再比较。** 去掉时间戳后比较整包 JSON，比"每个字段写 diff"便宜得多，也比"定时无脑推"省带宽。
4. **本地 HTTP 服务别忘了两个洞**：`Host` 头校验（防 DNS rebinding，否则任意网页都能读你的 prompt）和自定义头（防 CSRF，网页跨站发不出自定义头）。

**连接已学：**

| 已学概念 | 在它身上的体现 |
|---|---|
| [[05-Agent]] Harness | 它监控的正是 Harness 的日志——**把 Harness 从"黑盒执行器"变成"可外部观测的进程"** |
| [[07-Skill]] | 整个工具被包成一个 Skill：`SKILL.md` 只负责触发和说明书，干活的是 CLI。渐进式披露的极简版 |
| [[13-CLI]] | 又一次印证"CLI 是底座"——`--json` 让它可被脚本/Agent 消费，页面只是可选前端 |
| [[12-应用层Benchmark评测]] | 它没有任何评测数据：**看板类工具没有 ground truth**，别硬套评测框架 |
| [[19-Multica]] | 同一条可观测性光谱的两端：Multica 在服务端持久化任务状态，它在本机 tail 日志 |

🎯 **价值定位：它没有引入任何新概念，是已学「Harness 日志 + 状态机 + SSE」的最小产品级组装。值得抄的只有 ~100 行核心（`watcher.tick` + `view` + `push`），不值得装、不值得学它的 UI。**

---

## 参考资料

- GitHub：https://github.com/Charonyuu/whatsmyagentdoing
- 本地副本：`whatsmyagentdoing/`（clone 自 main，v0.6.0）
- 核心文件：`src/watcher.js`（659 行）/ `src/parsers.js`（748 行）/ `src/server.js`（242 行）
