# WorkBuddy 连接器（工程实践调研）

> 2026-09-16 调研完成。**非学习路线节点，是工作中实测的工具调研**，归入「工程实践补充」。
> 衔接 [[13-CLI]] / [[06-MCP]] / [[07-Skill]]：WorkBuddy 连接器是"AI 工具接口三形态（CLI/MCP/Skill）"在真实产品上的落地现场——两种官方接法正好是三形态的两两拼合。
> 关键词：WorkBuddy、连接器、MCP + Skill、CLI + Skill、SKILL.md、认证流程

---

## 核心认知
> **WorkBuddy（腾讯 AI 助手）连接器 = 把第三方能力接入 AI 助手的扩展接口，官方只给两条路：MCP + Skill（协议注册，推荐）和 CLI + Skill（读说明书），一个连接器只能选一种。**

---

## 一、问题：第三方服务怎么接进 AI 助手

AI 助手是封闭产品，第三方想让用户"用自然语言调用我的服务"，缺一个标准扩展点。WorkBuddy 的答案就是连接器市场：开发者提交一个符合规范的目录，审核通过后用户点安装，服务能力进入对话。

关键分野是**模型怎么知道这个能力**——两条路对应两种答案（13-CLI 站的判断框架，这里是官方实现）：

| 方案 | 模型怎么知道能力 | 适用 |
|---|---|---|
| MCP + Skill（推荐） | 协议注册（list_tools 的 schema 常驻） | 有 API 服务或能开发 MCP Server |
| CLI + Skill | 读说明书（SKILL.md 命令表，`--help` 按需） | 已有成熟跨平台 CLI |

🎯 **本质金句：连接器规范 = 分发格式 + 认证托管 + 生命周期调度三件事的工程约定，能力本体还是 MCP/CLI/Skill 老三样。**

## 二、原理：两种方案的结构与配置

### MCP + Skill 结构

```
your-connector/
├── connector-meta.json   # 元信息（必须）
├── mcp.json              # MCP Server 连接配置（必须）
├── icon.svg              # 市场图标（必须）
└── skills/{name}/SKILL.md  # AI 使用说明（MCP 可选，CLI 强烈推荐）
```

`mcp.json` 只能配 **一个** Server：远程用 HTTPS 的 `streamableHttp`/`sse`（含 `${VAR}` 凭证占位），本地用 `stdio`（`command`+`args`）。工具"名称、描述、参数、返回值要清晰稳定，便于 AI 正确选择"——就是 FC 站那句"工具 description = 给模型看的 Prompt"的官方复述。

MCP + Skill 里的 SKILL.md 定位：MCP schema 已声明"有什么工具"，Skill 补协议装不下的**使用策略**（何时用哪个、多步编排、错误恢复）。两者是互补不是重复。

### CLI + Skill 结构

```
your-cli-connector/
├── connector-meta.json   # type 必须为 cli
├── cli.json              # 安装与认证配置（必须）
├── icon.svg
└── skills/{name}/SKILL.md  # CLI 没有工具描述协议，AI 全靠它（强烈推荐）
```

`cli.json` 核心字段：`init.{darwin,linux,win32}` 三平台安装命令；有认证才需要 `auth`/`status`/`unAuth` + `statusMatch`；依赖 Node/Python 运行时声明 `runtime`（WorkBuddy 托管，不污染用户系统，npm/pip 装到管理目录）。

### connector-meta.json（两种方案通用）

注册与市场展示：`source`（kebab-case 全局唯一标识）、中英文名称/描述、`examples_zh/en`（用户真实会说的自然语言示例）、`type`（mcp/cli/skill-only）。

**版本门控机制**：配置字段带"最低版本"标注（如 cli.json 的 `runtime` Python 支持 = 5.0.0），用了就必须在 meta 里声明 `minWorkbuddyVersion`，低版本客户端不展示或置灰。这是渐进式披露思想在**配置分发层**的重现。

## 三、怎么跑的：WorkBuddy 的调度生命周期

MCP 版：安装连接器 → WorkBuddy 按 mcp.json 连 Server（stdio 拉子进程 / HTTP 发请求）→ 工具 schema 注册给模型 → 对话中模型自主决定调用。

CLI 版认证调度（文档约 70% 篇幅都在讲这个，是 CLI 方案真正的复杂度所在）：
1. 用户点「连接」→ 未安装先 `init`（5 分钟超时，必须非交互）
2. `status` 判断登录态（幂等无副作用，10 秒超时，退出码 0 + 输出匹配 `statusMatch` = 已登录）
3. 未登录执行 `auth`：**10 秒内**在 stdout/stderr 输出完整 https:// 认证 URL（前后需空白、不能被引号尖括号包裹、不得等 TTY 交互）→ WorkBuddy 提取 URL 后**立即杀掉 auth 子进程**并开浏览器
4. 每 3 秒轮询 status，最长 5 分钟 → `unAuth` 清理（未登录时也要正常返回）
5. WorkBuddy 重启只跑 status 恢复、不重跑 auth → **登录态必须跨进程重启有效**

认证三方案：后台 Daemon 接收回调（中）/ **Device Code Flow RFC 8628（推荐，无需本地回调）** / 服务端 Token 存储（中）。MCP 侧 OAuth 走 2.1 + PKCE 公共客户端，WorkBuddy 内置 OAuth 管理器，开发者只实现服务端端点；无 OAuth 只有 API Key 的用 `auth_mode: "token"` + `token-schema.json` 表单（`${VAR}` 占位符必须与表单 key 大小写一致）。

## 四、交付与提交

- 打 zip 包（WorkBuddy 有专门的"解析失败"排查条目——格式错误会被拒收）
- 提交 WorkBuddy 团队审核，通过后进市场，更新重新提交，10~15 分钟生效
- 提交前检查表覆盖：source 唯一、单 Server、HTTPS、无硬编码凭证、Skill 能指导 AI 调用全部核心能力、图标/版本声明

## 五、实测：两套连接器 + 验收 harness

同一能力（学习卡片）用两种方案各实现一遍，共享同一份数据 `~/.workbuddy-flashcards.json`，代码在 `WorkBuddy/` 下：

| | flashcards-mcp | flashcards-cli |
|---|---|---|
| 结构 | meta + mcp.json + icon + skills + server.py | meta + cli.json + icon + skills + flashcards_cli.py |
| 模型侧 | FastMCP stdio，3 工具（add_card/list_cards/random_card） | argparse 4 命令（add/list/random/reveal），业务输出 JSON、错误走 stderr + 退出码 1 |
| 验证 | 真实 MCP Client 冒烟：initialize → list_tools → 三工具调用全通，落盘 UTF-8 无损 | 四步循环验收：--help 发现 → 执行 → 退出码 → 错误路径全通 |
| 认证 | 无（本地数据不涉隐私，最小权限） | 无（auth 按需字段，本地工具不填即免整套 OAuth 机制） |

**验收 harness `verify_skill.py`**（skill-used 断言的最小实现，Benchmark 站落地）：system prompt = SKILL.md 正文（模型看不到源码），一个 `run_command` FC 工具，任务"记卡 + 考考我"，断言命令序列 `add → random →(用户回答)→ reveal` 且 random 在 reveal 之前（不偷看）。**glm-5.2 实测 PASS**：5 项断言全过，且抽到旧卡时模型正确处理"答非所问"并主动翻出刚 add 的卡补充点评——说明书没写的边界靠模型上下文自救（Agent 站"智能补在 Agent 侧"）。改 SKILL.md 后重跑即回归测试。

## 六、对比官方 Benchmark

无官方 benchmark（产品接入规范非工具库），跳过。

## 七、劣势与边界

1. **demo 简化**：`pip install flashcards-cli` / 本地 server.py 相对路径——正式提交需发布 PyPI/npm 包或远程部署 HTTPS，stdio 分发方式文档未写死，需与团队确认
2. **市场依赖人工审核**：不像 npm/pip 即发即用，每次更新都要走 10~15 分钟同步
3. **版本门控是双刃剑**：新字段（如 runtime Python）绑定 5.0.0+，低版本客户端直接不可见，用新特性 = 放弃老用户
4. **CLI 方案的认证复杂度是固有税**：URL 提取 + 杀进程 + 轮询的时序约束很细，能走 MCP 就别走 CLI（文档自己也这么推荐）

## 八、方案对比（同类）

| 接法 | 模型知道能力的方式 | Schema 成本 | 认证复杂度 | 适用 |
|---|---|---|---|---|
| MCP + Skill | 协议注册，schema 常驻 | 高（写 Server） | OAuth/token 托管齐全 | 有 API、深度集成 |
| CLI + Skill | 读 SKILL.md，--help 按需 | 低（复用现有 CLI） | 全套自己实现（auth/status/unAuth） | 已有成熟 CLI |
| skill-only（type 第三值） | 纯说明书，无工具 | 零 | 无 | 纯知识/流程封装 |

判据（13-CLI 站的选型直觉被官方文档证实）：工具少高频深度集成 → MCP；工具多低频通用 → CLI 省上下文。

## 九、收尾 + 连接到已学

带走 5 件事：
1. 连接器 = 分发格式 + 认证托管 + 生命周期调度的工程约定，本体是 MCP/CLI/Skill 老三样
2. 一个连接器一种方案，MCP+Skill 是"协议注册 + 读说明书"两种能力告知方式的**拼合**而非替代
3. CLI 认证调度的时序约束（10 秒出 URL / 提取即杀 / 3 秒轮询 / 跨重启有效）是 CLI 方案的真实成本
4. 版本门控 = 配置分发层的渐进式披露
5. SKILL.md 效果要用"只读说明书的 AI"验证——skill-used 断言可回归

| 已学概念 | WorkBuddy 里的体现 |
|---|---|
| MCP（06 站） | mcp.json 单 Server、stdio/HTTP、`@mcp.tool()` 写 server.py 直接复用 |
| Skill（07 站） | skills/ 子目录、frontmatter+body、CLI 方案的必需品 |
| CLI 三形态（13 站） | 两种接法 = 三形态的两两拼合；选型判据被官方文档证实 |
| Benchmark skill-used（12 站） | verify_skill.py 最小实现，实测 PASS |
| Harness/调度（05 站） | WorkBuddy = Host，管安装/认证/轮询，模型只决策 |

🔗 **价值定位**：没引入新概念，是已学 MCP/Skill/CLI/Benchmark 的产品级组装现场，顺便把"AI 工具接口三形态"从调研判断升级成了动手实证。

---

## 参考资料
- [WorkBuddy 连接器开发指南](https://open.workbuddy.cn/docs/connector)
- [WorkBuddy 技能（SKILL）开发指南](https://open.workbuddy.cn/docs/skill)
- [MCP 协议规范](https://modelcontextprotocol.io/)
- 本仓库实物：`WorkBuddy/flashcards-mcp/`、`WorkBuddy/flashcards-cli/`（含 verify_skill.py）
