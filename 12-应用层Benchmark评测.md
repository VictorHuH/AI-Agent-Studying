# 应用层 Benchmark 评测（工程实践调研）

> 2026-07-28 调研完成，2026-09-03 录入。**非学习路线节点，是工作中的工程调研**，归入「工程实践补充」。
> 衔接 [[11-Ponytail]] / [[09-LangGraph]] / [[07-Skill]]：已学的 Prompt / RAG / Agent / MCP / Skill 每一站在工程上都要回答"改了到底有没有变好"，Benchmark 就是给整条已学链路装上量化回归测试。
> 关键词：Benchmark、评估驱动开发、LLM-as-a-Judge、黄金数据集、eval harness

---

## 核心认知

> **Benchmark = 标准化评测体系：输入测试集 → 评分规则 → 判定系统好坏。应用层 Benchmark 衡量"模型在特定业务链路的适用程度"，是 LLM 应用的质量保障 + 回归测试 + 持续优化基础设施。**

---

## 一、问题：LLM 应用的"改了不知道变好还是变坏"病

**症状表：**

| 症状 | 表现 |
|---|---|
| 拍脑袋迭代 | 改一版 prompt / 换个模型 / 调 RAG 分块参数，效果全靠肉眼抽样"感觉不错" |
| 悄悄退化 | 上线后某次改动让某类问题变差，没人发现，直到用户投诉 |
| 选型错位 | 按公开榜单选了模型（模型层能力），落到自己业务场景表现对不上 |
| 无法回归 | 每次迭代都是全新一轮人工验收，测过的东西没法自动重测 |

**根因：** ① 模型层榜单测的是"通用能力"，不等于在具体业务链路的表现；② LLM 输出非确定性，传统单元测试的 equals 思路直接失效；③ 没有把"什么算好"沉淀为可执行判据。

**🎯 本质一句话：评估驱动开发（eval-driven development）——先建评估定义能力，再迭代。没有评估的迭代是盲飞。**

---

## 二、原理：两层分类 + 界定→衡量→改进

### 2.1 Benchmark 两层分类

| 层次 | 定义 | 评测对象 | 应用场景 | 价值 |
|---|---|---|---|---|
| **模型层 Benchmark** | 模型整体综合能力 | 底层大模型本身（GPT、Qwen、DeepSeek…） | 了解模型基础能力 | 模型选型、采购决策 |
| **应用层 Benchmark** ⭐ | 模型在特定应用的适用程度 | Prompt、RAG、Agent 等业务链路 | 基于公司真实场景构造测试集，评估系统是否真正解决业务问题 | 质量保障、回归测试、持续优化 |

> 分类是被广泛实践的企业评测分层。来源：
> （1）OpenAI《评估框架如何推动企业进入 AI 新篇章》——前言评估框架 / **情境评估框架**（"企业领导者需要学习如何设计符合自身组织需求和运营环境的情境评估框架"）
> （2）Arize《Model Evals vs Task Evals》——**Model evaluations / Task evaluations**（模型评估看"整体性能"，任务评估衡量"在特定应用中的适用程度"）

**重心在应用层**：针对具体业务场景用真实数据集评估，获得基准数据和回归测试结果，最终优化 LLM 应用效果。

### 2.2 整体评测流程：界定 → 衡量 → 改进

| 阶段 | 做什么 |
|---|---|
| **界定** | 专业成员识别关键决策点，建立**黄金数据集**（渐进式生成，初始少量即可） |
| **衡量** | 真实条件下设立评分标准，评估框架通过评分器对测试集测量 |
| **改进** | **数据飞轮**：记录输入/输出/结果 → 定期抽样日志 → 专家审查典型案例 → 更新 prompt/工具/模型。每次迭代在前一次基础上累积，最终形成**数据集资产** |

### 2.3 四要素

**（1）数据集（黄金数据集）**
把早期工作流每一步的成功标准（正例）和需避免的情况（反例），形成 **20–50 个输入与预期输出的映射（人类专家独立判断结论）**。
（"20–50 simple tasks drawn from real failures is a great start" —— Anthropic《Demystifying evals for AI agents》）
- 衡量阶段：真实输出与期望输出比对，看偏差
- 改进阶段：eval 揭示的错误案例经专家审查后**回填黄金集**，越用越厚越准

**（2）评分器**（内置逻辑都是**断言**）

| 维度 | 代码型 | 模型型 | 人工型 |
|---|---|---|---|
| **判分依据** | 确定性规则（正则、单元测试、状态检查） | LLM 当裁判对输出评判 | 人的主观判断 |
| **确定性** | ✅ 完全可复现 | ❌ 非确定性，同次输出可能不同分 | ❌ 因人而异，需多标注者求共识 |
| **能处理** | 有客观正解的（代码能跑吗/测试过吗/状态对吗） | 开放式、多正确答案（语气/全面性） | 主观、模糊、需领域专家 |
| **劣势** | **脆弱**：合理变体不合预设模式就判错；只判**形式**判不了**语义** | **需校准**：LLM 裁判可能幻觉，必须和人工对照 | **不可规模化**：跑不了成百上千条 |
| **典型方法** | 字符串匹配、二值测试、静态分析 | rubric 评分表、自然语言断言、成对比较、多 judge 投票 | SME 专家评审、抽样、A/B、标注一致性 |

> **使用准则：能编码 → 代码型；不能编码但能用语言描述好坏 → 模型型；语言描述不清或模型也判不准 → 人工型**

**（3）评测指标**（评分器执行后的结果）
- 确定性指标：`equals`、`contains`、`regex`、`is-json`、`javascript` 函数验证等
- 模型辅助指标：`similar`、`classifier`、`llm-rubric`、`factuality` 等

**（4）评测框架（eval harness）**
把"AI 应该达到什么标准"变成"可衡量、可改进、可持续运行"的基础设施：跑任务（批量多次）/ 隔离环境（每次干净启动）/ 调度 agent / 采集轨迹（算 pass@k）/ 评分并汇总指标。

```
【输入层】  一个任务（task）的定义
   ├─ 任务描述
   ├─ 评分器 graders（code / model / human，带 rubric/assertions）
   └─ tracked_metrics：声明要采集哪些过程指标
        ↓
【运行层】  eval harness 在隔离环境启动 agent harness
   ├─ agent 跑一次任务 -> 产生 transcript（轨迹/输出）
   ├─ 采集过程数据（轮数、token、延迟）
   └─ 同一任务跑 k 次 -> k 个单次 pass/fail
        ↓
【判分层·单次】  评分器对这次 transcript 判分
   ├─ 代码型：字符串匹配/状态检查 -> pass/fail
   ├─ 模型型：rubric -> 0-8 分
   └─ 人工型：SME -> 分数
   多个 grader 按 weighted/binary/hybrid 合成 -> 本次 pass/fail
        ↓
【汇总层】  把 k 次结果聚合成指标
   ├─ 成功率：pass@k / pass^k
   ├─ 效率：平均 latency / token / cost
   └─ 过程：平均 n_turns / n_toolcalls
```

> **"框架只是工具，评估质量取决于你跑的任务和评分器本身"**

---

## 三、怎么跑的：以 Promptfoo 为例

Promptfoo = 开源 CLI + YAML 的 LLM 测试框架，目标是把 **TDD 理念引入 LLM 开发**。运行方式：CLI（主要）/ Node.js 库 / Python 包。

工作流：**定义测试用例 → 配置评估 → 运行评估 → 分析结果**，通过**断言**将 LLM 输出与期望值比较，自动化分析。

评测以断言体系组织，按评测对象分六类（均为评分器三型 + 两类指标的产品化落地）：

**（1）Prompt**：矩阵评测（`prompts × providers × tests`）横向对比不同 prompt 版本。指标=全部确定性指标 + 全部模型评分指标（如 `llm-rubric` 用自然语言 rubric 评判语义质量）。

**（2）RAG**：分检索/生成两阶段分别量化——

| 指标 | 类别 | 含义 |
|---|---|---|
| `contains-all` | 确定性 | 检索：召回结果含全部期望文档子串 |
| `context-recall` | 模型评分 | 检索：上下文召回率 |
| `context-relevance` | 模型评分 | 检索：上下文相关性 |
| `factuality` | 模型评分 | 生成：答案与参考事实的一致性 |
| `answer-relevance` | 模型评分 | 生成：答案对问题的相关性 |
| `similar` | 确定性 | 生成：与期望的 embedding 相似度 |
| `context-faithfulness` | 模型评分 | 生成：对上下文忠实度（0–1，threshold 0.8） |

**（3）Agent**："测系统不测模型"，三层分级（Tier 0 纯文本 / Tier 1 SDK / Tier 2 rich client）——

| 指标 | 类别 | 含义 |
|---|---|---|
| `trajectory:goal-success` | 模型评分 | 基于 trace 用 LLM judge 判定是否真正完成任务 |
| `trajectory:step-count` | 模型评分 | 按 command / reasoning 统计步骤数 |
| `trajectory:tool-used` | 模型评分 | 断言使用了特定工具 |
| `trajectory:tool-sequence` | 模型评分 | 断言工具调用顺序符合预期 |
| `agent-rubric` | 模型评分 | 面向 agent 输出的 rubric 评分 |
| `is-json` / `contains-json` | 确定性 | 验证 output_schema 强制结构 |
| `javascript` | 确定性 | 检查漏洞数/bcrypt/是否跑 pytest 等业务逻辑 |
| `cost` / `latency` | 确定性 | 性能门禁 |

**（4）SKILL**：同一模型 + 同一 task 文件，仅替换 `SKILL.md` 做对照——

| 指标 | 类别 | 含义 |
|---|---|---|
| `skill-used` | 确定性 | 断言真的调用了指定 skill |
| `not-skill-used` | 确定性 | 断言未误调邻近 skill（路由正确性） |
| `trajectory:step-count`（带 pattern） | 模型评分 | 断言读过 SKILL.md 文件 |
| `javascript` | 确定性 | 计算 issue recall（hits / expected） |
| `max-score` | 模型评分 | weights 聚合多指标加权打分 |

**（5）LLM 链 / 工作流**：unit test（每步拆开单测）vs end-to-end（脚本包整条链）。`equals`/`contains`/`is-json` 校验中间与最终输出，`llm-rubric` 语义评判。

**（6）结构化生成输出**：`is-json`（带 Schema）+ `options.transform: JSON.parse` 预处理 + `javascript` 字段判断；另有 `is-sql`（可限 databaseType/allowedTables/allowedColumns）、`is-xml`/`is-html` 等。

**其他能力：**
- **红队测试（Red Teaming）**：核心差异化，覆盖 50+ 漏洞类型，架构 = Plugins（生成对抗输入）× Strategies（决定投递方式）
- **数据合成与优化**：`promptfoo generate dataset` 合成测试用例；`promptfoo optimize` 自动迭代优化 prompt 文本
- **CI/CD 集成**：官方 GitHub Action（`promptfoo/promptfoo-action@v1`）

---

## 四、命令与模式（Promptfoo）

| 命令 | 作用 |
|---|---|
| `promptfoo init` | 初始化，生成配置（`--example getting-started`） |
| `promptfoo generate dataset` | 基于 prompts/tests 合成更丰富的测试集 |
| `promptfoo optimize` | 针对 prompt+provider+测试自动迭代优化 prompt |
| `promptfoo eval` | 运行评估 |
| `promptfoo view` | 本地 Web UI 查看结果（也可导出 JSON/YAML/CSV） |

核心配置 `promptfooconfig.yaml`：`description` / `prompts`（prompt 列表）/ `providers`（含 id 与 config）/ `tests`（测试用例列表或外部文件）/ `assert`（断言列表）。

---

## 五、实测

本次为调研报告，无自建实测数据。⭐ 后续在公司真实场景落地时补：黄金集构造过程 + 基线跑分 + 迭代前后对比。

---

## 六、劣势与边界

1. **框架只是工具**：评估质量取决于你跑的任务和评分器本身，选再好的框架也救不了糟糕的测试集
2. **评分器三型各有天花板**（见 2.3 表）：代码型脆弱（判形式不判语义）、模型型需校准（LLM 裁判可能幻觉，必须和人工对照）、人工型不可规模化
3. **冷启动成本**：黄金数据集需人类专家独立判断结论，20–50 例起步也需投入；且需持续维护
4. **假信心风险**：自动化评估可能脱离真实用法；需配合生产监控/用户反馈校准
5. **应用层无现成榜单**：必须基于公司真实场景自建测试集，不能拿模型层榜单代替

---

## 七、类似工具对比

### 7.1 专用评测框架

| 维度 | Promptfoo | DeepEval | RAGAS | skill-up | mcp-eval | Langfuse |
|---|---|---|---|---|---|---|
| **类型** | 评测 + 红队框架 | 评测框架 | RAG 评测库 | Skill 评测 + 演进框架 | MCP 评测框架 | 可观测性平台 + 评测 |
| **协议** | MIT | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 | MIT（核心）/ EE 商业 |
| **语言** | TypeScript | Python | Python | Go | Python | TypeScript |
| **GitHub Stars** | ~23.7k | ~17k | ~15k | ~107–226 ⚠️待核验 | ~31 ⚠️待核验 | ~31.7k |
| **评测对象** | Prompt / LLM 应用 / RAG / Agent | LLM 应用 / Agent / RAG / 多轮 / MCP / 多模态 | RAG 管道（+ Agent / SQL） | Agent Skill（SKILL.md） | MCP Server + Agent | 任意 LLM 应用（生产 trace） |
| **核心评测范式** | 矩阵评测 prompts×providers×tests | pytest 化断言 assert_test | reference-free 指标库 | expect + judge + 基线对比 | 真实 agent↔server + OTel 断言 | 在线/离线评分（Scores） |
| **LLM-as-Judge** | ✅（llm-rubric/factuality/select-best） | ✅（G-Eval/DAG/QAG） | ✅（多数指标） | ✅（agent_judge） | ✅（Expect.judge.llm） | ✅（主推） |
| **合成测试集** | ✅ generate dataset | ✅ Synthesizer（Evol-Instruct） | ✅ TestsetGenerator（进化生成 + KG） | ✅（对话生成） | ✅ mcp-eval generate | ✅ 从生产 trace 策展 |
| **红队测试** | ✅✅ 50+ 漏洞类型（最强） | ✅ RedTeamer / DeepTeam | ❌ | ❌ | 部分 | ❌ |
| **多轮 / Agent** | ✅ conversation / trajectory / simulated-user | ✅ ConversationalTestCase + Simulator | ✅ MultiTurnSample + Agent 指标 | ✅ turns + post_condition | 部分 | ✅ Session + Agent Graph |
| **MCP 专项** | ✅（provider 接入） | ✅（MCP 指标家族） | ❌ | ✅（real / mocked MCP） | ✅✅（专门） | ✅（MCP Server 集成） |
| **Skill 专项** | 部分（agent-rubric） | ❌ | ❌ | ✅✅（专门） | ❌ | 部分 |
| **可观测性 / Tracing** | ❌（纯评测） | 部分（@observe） | ❌（依赖外部） | ✅（OTLP） | ✅（OTel 单一事实源） | ✅✅（核心能力，10 种 observation 类型） |
| **Prompt 管理** | ❌ | 部分 | ❌ | ❌ | ❌ | ✅✅（版本 + label + A/B + Playground） |
| **生产监控 / 在线评测** | ❌（部署前为主） | 部分（via Confident AI） | ❌ | ❌ | ❌ | ✅✅（在线对生产 trace 评） |
| **CI/CD** | ✅（GH Action 等） | ✅（pytest 原生） | ✅（依赖 pytest/脚本） | ✅（GitHub Action） | ✅（GH Action/GitLab） | ✅（experiment-action + RegressionError） |
| **数据隐私** | ✅ 100% 本地 | ✅ 本地 Judge | ✅ 本地库 | ✅ 本地 | ✅ 本地 | ✅ 自托管 + 四区域 + 合规 |

> ⚠️ skill-up（~107–226）与 mcp-eval（~31）的 star 数为调研时点数据且来源存疑（报告原文标注"主候选"含义不明），选型引用前需重新核验。

**一句话选型：** 通用评测 + 红队 → **Promptfoo**；Python / pytest 生态 + 全家族指标 → **DeepEval**；RAG 专项 → **RAGAS**；MCP 专项 → **mcp-eval**；Skill 专项 → **skill-up**；可观测性平台 + 在线评测 → **Langfuse**。

### 7.2 可观测 + 评测一体化平台（离线评测 + 线上监控 + 人工标注全生命周期）

| 平台 | 特点 | 适合 |
|---|---|---|
| **LangSmith**（LangChain） | LangChain/LangGraph 生态首选；自动埋点、数据集管理、在线评测、标注工作流；按席位收费 | 已用 LangChain/LangGraph 的团队 |
| **Langfuse** | 开源 + 自托管可选 + 托管云 | 要自托管/合规敏感的团队 |
| **Arize Phoenix** | OpenTelemetry 原生、可自托管的 tracing + evals | 重视 OTel 标准、想自托管的团队 |
| **Braintrust** | 2026 年公认最完整的全生命周期商业平台（数据集→评分→生产监控→CI 发布门禁） | 要一站式商业方案的 AI SaaS 团队 |

**实际选型从评测对象 + 是否需要生产监控等真实需求出发。**

---

## 八、收尾 + 连接到已学

**带走 6 件事：**
1. Benchmark 分**模型层**（选型决策）与**应用层**（质量保障）两层，工程重心在应用层
2. 评测流程 = **界定 → 衡量 → 改进**，改进阶段的**数据飞轮**让黄金集成为越用越厚的数据资产
3. 四要素 = **数据集、评分器、评测指标、评测框架**
4. 评分器三型（代码/模型/人工）按"**能编码→代码型；能描述→模型型；都不行→人工型**"选择
5. 评测框架五大功能 = **批量执行、隔离环境、调度 Agent、采集轨迹、汇总指标**
6. 框架分**纯评测**与**观测+评测一体化**两类，按需选型

**连接已学（评估不是新概念，是已学每一站的"验收层"）：**

| 已学概念 | 在本调研中的体现 |
|---|---|
| RAG 站手写 Hit@K / MRR | 代码型评分器的手写版；本站是工业化 + 全要素（数据集/评分器/框架分层） |
| RAG 站"标注陷阱（虚假满分）" | 黄金数据集质量决定评估上限——同一教训的产品级表述 |
| LLM-as-a-Judge | Prompt（03 站）+ FC（04 站）的反向应用：模型从"被测者"变"裁判"，但裁判本身会幻觉需人工校准 |
| Agent（05 站）ReAct 轨迹 | `trajectory:*` 指标 = Thought/Action/Observation 序列的量化断言 |
| Skill（07 站）description 触发 | `skill-used` / `not-skill-used` = 触发正确性的回归测试；只换 SKILL.md 做对照 = 控制变量实验 |
| LangGraph（09 站）Checkpointer | trace/trajectory 采集的基础设施相通 |
| 数据飞轮 | RAG 长期记忆闭环的评测版：错误案例回填黄金集 ≈ extract_facts 回填 Chroma |
| 红队（50+ 漏洞） | 阶段4"护栏 + AI Security"的自动化探测面 |
| 评估驱动开发 | TDD（前端老本行）在 LLM 时代的重生 |

**🔗 价值定位：** 应用层 Benchmark 没引入新范式，是已学全链路（Prompt/RAG/Agent/MCP/Skill）+ 前端工程测试思维的汇合点——"评估是 LLM 应用的单元测试 + 回归测试 + CI 门禁"。

---

## 参考资料

- [Anthropic — Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [OpenAI — 评估框架如何推动企业进入 AI 新篇章](https://openai.com/zh-Hans-CN/index/evals-drive-next-chapter-of-ai/)
- [Langfuse — LLM Evaluation Strategy](https://langfuse.com/resources/engineering/llm-evaluation-strategy)
- [LangSmith — Evaluation Concepts](https://docs.langchain.com/langsmith/evaluation-concepts)
- [Arize — Model Evals vs Task Evals](https://arize.com/blog/large-language-model-evaluations-vs-llm-task-evaluations-in-llm-application-development/)
- 原始调研报告：`AI Coding BenchMark 调研报告3.0.md`

### 附：相关概念备忘

**评测方法四件套：**

| 方法 | 是什么 | 优势 | 劣势 | 何时用 |
|---|---|---|---|---|
| 自动化评估 | 不带真实用户、程序化跑测试 | 快、可复现、每次提交都能跑 | 前期投入大、可能脱离真实用法造成假信心 | 上线前 + CI/CD，第一道防线 |
| 生产监控 | 线上系统追踪指标和错误 | 真实用户行为、真实表现真值 | 被动（问题已影响用户）、信号嘈杂 | 上线后，防分布漂移 |
| A/B 测试 | 真实流量对比两个变体 | 测真实用户结果、控制混淆变量 | 慢（数天到数周）、难解释"为什么" | 有足够流量时验证重大改动 |
| 用户反馈 | 点踩、bug 报告等显式信号 | 能发现没预见到的问题 | 稀疏且自选、偏严重问题 | 持续做，填补空白 |

有效团队会结合：自动化评估快速迭代 + 生产监控拿真实数据 + 定期人工审核校准。

**离线 vs 线上评测：**

| | 离线评测 | 线上评测 |
|---|---|---|
| 作用 | 发布前测试 | 生产监控 |
| 跑在什么上 | Dataset 的 Examples（带 reference output） | Tracing 的 Runs / Threads（无 reference） |
| 能做什么 | benchmark、回归测试、单元测试、回测 | 实时监控、异常检测、生产问题沉淀回数据集 |
| 关键能力 | 能对照"正确答案"判正确性 | 无 ground truth，靠启发式/安全检查/无参考评测 |

**两类评估：**
- **能力评估（Capability）**："这个智能体在哪些方面表现优异？"——通过率设定较低，针对难处理的任务
- **回归评估（Regression）**："是否仍能处理原先能处理的全部任务？"——通过率应接近 100%，防性能下降
