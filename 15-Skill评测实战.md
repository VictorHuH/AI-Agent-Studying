# Skill 评测实战（执行质量 × 触发质量 双维评测）

> 2026-09-27 实战完成并录入。**学习路线阶段4「评估 Evaluation」的实战篇**（非独立站点）：把 12 号的评测理论落到 07 站自己写的 self-test Skill 上。
> 衔接 [[12-应用层Benchmark评测]] / [[07-Skill]]：12 回答"为什么评、评什么（数据集/评分器/指标/框架）"，本篇回答"具体到一个 Claude Code Skill 怎么评"——执行质量两轮迭代 + 触发质量一轮，26 次对照运行 + 6 次独立判分全链路走通，官方 skill-creator 方法论完整跑了一遍。
> 关键词：Skill 评测、skill-creator、promptfoo、skill-up、消融对照、触发质量、执行质量、口号≠机制、not-skill-used、基线污染

---

## 核心认知

> **Skill 评测 = 两个独立维度分开评：执行质量（触发了以后做得好不好，看 SKILL.md 正文）+ 触发质量（该不该用时会不会被想起，看 description）。两者失败模式与优化手段完全不同，混在一起测说不清 Δ 来自哪里。**

---

## 一、评什么：两维度 × 各自的测法

| 维度 | 评测对象 | 失败表现 | 测法 |
|---|---|---|---|
| **执行质量** | SKILL.md 正文指令 | 触发了但做出来的结果不行：编造、越界、重复、泄答案 | 测试集 × 消融对照（带 skill vs 无 skill/旧版）→ 独立 grader 判断言 |
| **触发质量** | frontmatter 的 description | 该用没用（漏触发）/ 不该用抢着用（误触发）/ 抢了别的 skill 的活（串台） | 用户原话 query × subagent 自然响应，检查有没有真的调 Skill 工具 |

**交互式 skill 的处理**：只测单阶段（如"出题阶段"），用 prompt 预确认短路中间的等待环节——一次实验只隔离一个变量。

**对照组随问题切换**（这是设计精髓）：
- 证明"skill 有没有用" → baseline = **无 skill**
- 证明"改动有没有效" → baseline = **旧版 skill 快照**
- 两次消融回答两个不同的问题，不能混用

---

## 二、用什么评：工具生态地图

### 2.1 生态内（唯一原生路径）

被测对象是"harness 里装了 skill 的完整 agent 会话"，不是一次 API 调用——外部平台默认构造不出来，生态内工具有两件：

| 工具 | 定位 | 机制要点 |
|---|---|---|
| **`claude plugin eval`**（官方 CLI） | skill 随 plugin 发布后的无人值守评测 / CI 门禁 | 声明式 case（prompt.md + graders/）；隔离子会话自动跑 WITH/W/OUT 消融；判分器单元化（确定性断言 / LLM judge / **`tool_used: Skill`** 测触发）；低于阈值 exit non-zero 卡 CI；子会话只继承环境变量白名单 |
| **skill-creator 插件**（官方） | 会话内交互式迭代单个 skill | 循环：草稿 → 同轮并行 spawn 带 skill + baseline subagent → 运行期间起草断言 → 独立 grader 判分（text/passed/evidence）→ `aggregate_benchmark.py` 汇总 → 分析师环节 → 评审页面（Outputs 人工反馈 + Benchmark 定量，带上一轮对比）→ 读 feedback 改 skill → 下一轮。进阶件：盲比较（匿名输出给独立 judge）、description 优化循环（`run_loop.py`：20 条 should/shouldn't query、60/40 切 train/test、每条跑 3 次、按 held-out 分数选最优防过拟合） |

### 2.2 外部平台的边界与桥

**通用规律：评测平台的边界不在"能测什么"，而在"被测系统能否被程序化调用"。** Skill 的运行时是 Claude Code harness，但 `claude -p`（headless 模式）就是桥——把"跑一次带 skill 的完整会话"当作一次"模型调用"：

| 平台 | 桥的程度 | 形态 |
|---|---|---|
| **promptfoo** | 桥已产品化 | 六类断言体系里有 **SKILL** 一类（含控制变量对照、`not-skill-used` 防误触发）+ 声明式 YAML + CI + 红队，SKILL 支持最原生 |
| **DeepEval** | 桥自己搭 | pytest 风格，subprocess 调 `claude -p` 当 fixture，之后 LLM-as-judge 指标库 / pass@k / 回归报告白捡 |
| **LangSmith / Langfuse** | 不是跑评测，是采数据 | Claude Code 的 OTel trace 导出 → 真实使用轨迹沉淀成数据集 → 离线回放评分。解决"测试集是拍脑袋写的而非从真实使用长出来的"问题 |

**何时值得迁**：case 上几十条、要反复跑、要进 CI、要团队共享报告、或要真实数据回流——首选 promptfoo。当前量级（十几个 case、两三轮迭代）生态内工具够用，迁移成本（搭桥 + 每次评测都是完整 agent 会话的 token 账单）大于收益。

---

## 三、实战一：执行质量两轮迭代（对象：self-test）

### 3.1 设计四决策

1. **对象界定**：只测出题阶段（prompt 里预答"考全部、出6道"，短路确认环节）
2. **测试集 3 条**：MCP（标准）/ Agent（换触发语）/ Benchmark（口语"Benchmark 评测" vs 笔记标题"应用层Benchmark评测"，考匹配）
3. **断言 6 条**：正好6道题 / 基于正确笔记 / 可溯源无编造 / 考点不重复 / 认知层次混合 / 不泄答案
4. **判分独立**：grader subagent 只读落盘文件（response.md + 笔记原文），不采信运行 agent 自述——防运动员兼裁判

### 3.2 Iteration-1：skill 有没有用（baseline = 无 skill）

**结果**：with 94.4%（17/18）vs without 83.3%（15/18），Δ +11pp；token +8%。

**Δ 拆解（比总分重要）**：
- 6 条断言里 **4 条双方全过（非区分性）**——强模型原生就能做到题量/正确笔记/层次混合/不泄答案
- **全部增量来自"锚定指定笔记"一条**：无 skill 时两次把笔记外内容混进题目（其他笔记的内容、模型自带知识如 pass^k 细节）——对"对照笔记复习"的用途是致命的，这就是 skill 的核心价值
- **with-skill 自己栽了一条**：考点重复（"命门"被拆进两道题）——护栏写在 SKILL.md 里却没被遵守
- 意外收获：暴露 `extract_topics.py` 在 Windows GBK 控制台下 print emoji 标题**必崩**的确定性 bug（3 次运行 2 次触发）

### 3.3 三处改动（评测结论 → 修复）

| 改动 | 类型 | 对应发现 |
|---|---|---|
| 脚本加 `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` | bug 修复 | GBK 必崩 |
| 新增步骤「考点查重」：出完逐题标注对应小节、同考点合并/换题 | **口号→机制** | 断言 4 失败 |
| 两处护栏补 why（超范围=没法对照笔记复习；重复=虚假覆盖感） | 解释动机 | 心法：解释 why > 堆 MUST |

### 3.4 Iteration-2：改动有没有效（baseline = 旧版快照）

**结果**：新版 **100%（18/18）** vs 旧版 94.4%；**耗时 186s→139s（−25%，来自消灭 GBK 重试循环）**；token 持平（+1.4%）。

**行为层 A/B（比分数硬）**：GBK 修复 6:0（旧版 3/3 崩、新版 3/3 直接过）；查重机制新版 3/3 执行（旧版累计 4 次运行挂 2 次断言 4、换了地方挂——同一缺陷随机冒头，说明无机制时靠运气）。

**🎯 本篇最值钱的教训：口号 ≠ 机制。** 写进 SKILL.md 的质量要求如果只是口号（"一个考点最多一道题"）而没有"怎么做"的步骤，模型不会自动遵守；一旦变成可执行步骤（逐题标注小节 + 同节合并），失败消失。**skill 里每条质量要求都该配一个怎么做。**

---

## 四、实战二：触发质量（14 条 query）

### 4.1 设计

- **正例 7 条**（应触发）：覆盖口语化变体——"考我 RAG"（标准）到"掌握没掌握，考考我"（长口语无关键词）到"你来提问我来答"（说法完全换掉）
- **负例 7 条**（近似失误，共享关键词但需要别的）：总结章节 / 概念问答 / record-tool 地盘（"整理进笔记"）/ git-upload 地盘（"同步 GitHub"）/ 讲解某节 / **"写个单元测试"（"测试"字眼撞车）** / 更新路线进度
- **方法**：subagent 只收用户原话，skill 仅以列表项存在；先跑 1 条哨兵验证链路再放量；负例涉及写文件/git 的加"只读不落盘"护栏（触发决策发生在执行之前，不影响测量）
- **判据**：subagent 自报 `SKILL_USED` + 回复行为佐证（先问范围/跑 extract_topics/先问后判 = 真触发了）

### 4.2 结果：14/14 全对

- **漏触发 0/7、误触发 0/7、技能路由 2/2**（该给 record-tool/git-upload 的没被 self-test 抢——三 skill 并存零串台）
- 正例里最刁钻的"你来提问我来答"正确触发，还主动追问是否连带考多Agent篇；"写个单元测试"没被"考我"的 description 带偏，合理反问要代码

**结论：description 的"推式"写法（"不可跳过"+触发语枚举）被验证安全**——枚举触发词足够覆盖口语变体，语义边界（出题 ≠ 总结/问答/讲解/录入）防住全部近似失误。12 号笔记里 Promptfoo 的 `not-skill-used` 断言，就是这套东西的产品化形态。

---

## 五、方法论骨架（可复用）

```
① 界定评测对象和维度（执行 or 触发，一次一个变量）
② 设计测试集（真实 prompt + 刻意的近似失误）
③ 断言要预判区分力（非区分性断言让总分虚高）
④ 对照组随问题切换（证有用→无skill；证有效→旧版本）
⑤ 判分独立（grader 只看落盘文件）
⑥ Δ 拆解归因，别只看 pass_rate
⑦ 把失败变成机制化的修复，再跑一轮验证
⑧ 边界照实写：样本量、单次波动、没测什么
```

---

## 六、坑与边界清单

**坑：**
- **Windows GBK 三连**：skill 脚本 print emoji 必崩（`sys.stdout.reconfigure` 修）；官方 `aggregate_benchmark.py` 同样不带 encoding 读 UTF-8 中文就炸（`PYTHONUTF8=1` 绕过）；目录结构不符脚本预期时静默输出空 benchmark（它要 `eval-*/配置/run-N/` 三层 + grading.json 里带 summary 块）
- **单次运行的分数不可过度解读**：旧版 4 次运行挂 2 次断言 4、换了地方挂；5/6 vs 6/6 的翻转完全可能是波动。要看收敛的行为证据（机制是否被执行、失败是否消失），不要只看 pass_rate
- **评测基础设施自身的噪音会污染数据**（分类器超时导致重试→耗时虚高）

**边界（诚实清单）：**
- 样本量小：执行 3 prompt × 1 run × 2 配置 × 2 轮；触发 14 × 1。100% ≠ 无 bug
- 判分环节（交互后半段）从未测过
- 触发未测"练习 vs 自测"语义边界（"出两道题练练手"）和跨会话稳定性

---

## 七、收尾 + 连接已学

- **12 号的落地**：四要素全部现身——数据集（evals.json 测试集）、评分器（脚本判 + LLM-as-judge grader + 人工评审页面）、指标（pass_rate/tokens/duration 三角）、框架（skill-creator 编排）。「界定→衡量→改进」数据飞轮 = 本篇的 iteration 循环
- **07 号的延伸**：Skill 站学的"description 决定被想起概率"从设计原则变成了被测指标；"渐进式披露"解释了为什么执行评测要让 skill 以列表项存在而非塞进 prompt
- **02 号的呼应**：Hit@K/MRR 是手写评测前身，本篇的断言判分是它的 Skill 版
- **通用判断力**：评测平台选型看"被测系统能否被程序化调用"；每条质量要求配一个怎么做；Δ 必须拆解归因

## 八、promptfoo 落地实战（外部平台桥接，2026-10-06）

> 用 promptfoo 把上述手动评测**独立复现**一遍，验证桥接结论：**被测系统只要能被程序化调用，就能进评测平台**——桥就是 Claude Agent SDK（`anthropic:claude-agent-sdk` provider）。

### 8.1 手动版 → promptfoo 版的映射

| 要素 | 手动版 | promptfoo 版 |
|------|--------|-------------|
| 被测单元 | subagent + prompt 里塞 skill 路径 | provider `anthropic:claude-agent-sdk`，`working_dir` 指向 fixture |
| 对照组 | 编排两批 subagent | 两个 provider **唯一差异 `working_dir: fixtures/v1 \| v2`**（swap-only 的声明式表达） |
| skill 注入 | 给路径 + 要求遵循 | `setting_sources: ['project']` 扫 `.claude/skills/` + `skills: ['self-test']` 白名单（自动 allow Skill 工具） |
| 触发证据 | subagent 自报 `SKILL_USED` + 行为佐证 | `skill-used` 断言读 **tool call 元数据**（一等公民证据） |
| 判分 | grader subagent | 基础断言（JS 计数/not-contains）+ `llm-rubric`（LLM-as-judge） |
| 笔记喂 judge | grader 自己读笔记 | `vars.note: file://./fixtures/06-MCP.md` + `{{note}}` 模板注入 rubric |

### 8.2 四道坎（每道都是通用教训）

1. **Not logged in**：promptfoo 起的 SDK 子进程继承不到 `~/.claude/settings.json` env 块的认证（Ark 网关+token）。桥的本质 = 环境变量显式传递（`apiKeyRequired: false` + `ANTHROPIC_BASE_URL/AUTH_TOKEN/MODEL`）。
2. **GBK 乱码吞掉 set 命令**：.cmd 里写中文注释 → cmd.exe 按 GBK 读 UTF-8 → 乱码行把 `set ANTHROPIC_BASE_URL` 吞了 → token 敲错门（403）。**.cmd 必须纯 ASCII**。GBK 坑第三次应验（extract_topics.py → aggregate_benchmark.py → run-eval.cmd）。
3. **非区分性断言**：第一版 3 条断言两版全过（skill-used/6题/不泄答案）——手动版 iteration-1 教训的 promptfoo 复现。但输出有真差异：v2 自述"已做考点查重（6 题落在 6 个不同小节）"——**SKILL.md 的改动在产出里留下可见痕迹**（"prove the skill changed the work, not just the routing trace"）。
4. **单次方差**：升级 5 条断言（+考点不重复/可溯源两条 llm-rubric，judge 判词逐题溯源到笔记小节）后 v1 仍全过——历史失败率 ~50%（4 挂 2），单次撞上好日子。**要真 Δ 需多轮跑失败率**。

### 8.3 结果与成本

| 轮次 | 断言 | 结果 | 耗时 | tokens |
|------|------|------|------|--------|
| 1 | 基础 3 条 | 2/2 过（无区分性） | 28s | 74.8k |
| 2 | 5 条（含 2 judge） | 2/2 过（v1 好日子） | 57s | 91k（judge 16.1k） |

- SDK 直跑会话 23~27s vs 手动 subagent 120~180s：SDK 会话不带 plugin/MCP/技能列表，轻一个量级
- judge 判分模型：`openai:chat` 打 Ark coding v3 端点（沿用历史验证过的配置），`apiKeyEnvar` 取 token
- 评测历史存 `~/.promptfoo/promptfoo.db`（SQLite，可直接查）

### 8.4 判断力沉淀

- promptfoo 的 SKILL 断言体系（skill-used / not-skill-used / trajectory）+ 声明式 fixture = "claude -p 桥"的产品化
- 评测平台价值排序：证据等级（tool call 元数据 > 模型自报）> 可移植（一份配置多 harness）> 规模化（CI/矩阵）
- **断言设计先于跑评测**：先问"这条断言能不能把好坏分开"，否则全绿报告是安慰剂
- 全绿之后看两样：输出里有无版本差异痕迹（有→改动有效）；要不要多轮跑失败率（单次 100% 不置信）

---

## 九、skill-up 落地实战（评测+演进闭环工具，2026-10-07）

> 阿里巴巴开源的 Agent Skill 评测 CLI，卖点是"评测→诊断→修复→重跑"闭环 + Anthropic 格式原生兼容。本轮用它评测 self-test，跑通全链路，并撞出两个重要发现。

### 9.1 工具关系与用法

**两层架构**：`skill-up`（Go 二进制，执行引擎：起会话/判分/报告）+ `skill-upper`（Agent Skill，编排层：教 AI Agent 怎么调 CLI、读报告、诊断修复）。类比：skill-up≈pytest，skill-upper≈教 Agent 用 pytest 的作战手册——**一个用来评测 Skill 的 Skill**，07 站"Skill=打包一切"的元应用。

```bash
npx skills add .../skills/skill-upper -g -a claude-code -y   # 装编排层
skill-up import self-test/evals/evals.json                    # 吃掉存量 Anthropic 测试集（3 用例无损转换）
skill-up validate self-test/evals/eval.yaml                   # 预检
skill-up run     self-test/evals/eval.yaml                    # 运行；退出码 0/1 直接当 CI 门禁
```

### 9.2 评测配置（两个文件搞定）

```yaml
# eval.yaml 关键项
engine:
  name: claude_code          # 起真 claude CLI——零认证配置，自己读本机登录态
                            #（对比 promptfoo 要手工桥接三个环境变量）
cases:
  defaults: { max_turns: 20, timeout_seconds: 600 }  # 默认 10 轮不够 skill 流程用
benchmark:
  enabled: true             # 一键消融：每用例自动跑 with/without skill 两遍

# case.yaml 关键项
input.prompt       # 用户原话 + 预确认（短路 skill 的追问等待）
context.files      # 笔记副本进工作区（judge 溯源对照用）
expect.must_not_contain   # 确定性门槛（先脚本判，语义才上 judge）
judge:
  type: agent_judge       # LLM 判分
  criteria: [6 条断言]     # 断言写全在源 evals.json 的 expectations 字段（我们当年没写，import 后手工补）
```

**产物全本地化**（纯文件目录，对比 promptfoo 存 SQLite）：`<skill>-workspace/iteration-N/` 下 result.json / benchmark.json / report.html / 每 case 的 grading.json + agent 完整 transcript + judge 原始响应与重试记录，轮次自增历史全保留。

**agent_judge 证据质量三套方案最强**：判词带笔记行号引用（"第 214 行 PYTHONHASHSEED"）、交叉核对 transcript、甚至主动 grep 仓库验证越界内容不出现在任何笔记；judge 输出格式违规自动带纠错指引重试（本轮 3 次全自愈）。

### 9.3 两轮结果与两个发现

| 轮次 | 结果 | 性质 |
|------|------|------|
| 1（仓库内运行） | 6/6 全过，Δ=0 | **基线污染，无效** |
| 2（评测目录搬出仓库） | 4 过 2 挂 | 部分有效，出真发现 |

**发现 1：基线污染——消融对照的隐蔽失效**。"无 skill"基线 agent 自己在文件系统摸到仓库部署的真 skill（读 SKILL.md、跑它的脚本、输出里出现 v2 独有的"已做考点查重"措辞）——**对照组抄了作业，Δ=0 是假象**。搬出仓库也拦不住：机器全局配置授权 Desktop 读取（additionalDirectories + Read allow），绝对路径可达，3 个基线 1 干净 2 再污染。三层教训：
1. **消融效度 = 隔离强度**——对照组能接触实验组处理时 Δ 无意义，且失效方向隐蔽（被低估成"skill 没用"）
2. **隔离强度受限于运行环境授权面**——共享开发机上 `environment: none` 的 no-skill 基线必须真沙箱（docker/opensandbox）；带 skill vs 带旧版 skill 的对照（手动 it2 / promptfoo）不受此约束
3. **污染是随机的**——不查 transcript 看不出来，**读轨迹和读分数一样重要**

**发现 2：评测挖出 skill 真缺陷（笔记匹配歧义）**。"自测一下 Agent"匹配到两篇笔记（05-Agent / 10-多Agent），agent 全都要，prompt 里的预确认把 skill 本该发出的"考哪篇？"追问短路了 → 挂范围锚定。对照触发评测 Q5（当时 agent 主动问了）——**询问才是正确行为**。改进项：**多笔记匹配必须先问，预确认不能替代歧义消解**。

**隔离轮有效结论**：干净基线（case-0）挂"越界"——考 OAuth/Sampling/Elicitation 等 MCP 官方知识，笔记里一个字没有（judge grep 验证）——skill"锚定笔记"的核心价值首次在工具评测中直接证实；但整体 Δ 因 2/3 基线污染不可算。

### 9.4 关键认知沉淀

- **测试集来源**：纯 skill-up 全人工；skill-upper 三种 AI 起草路径——种子扩展（人给意图 Agent 生成）/ 演进中自动补用例（覆盖缺口变回归保障）/ 观察转用例（真实使用→人工批准→回归 case，需 Codex/DSH 插件）。人握住的判断是"这条用例值得测吗"，不是 YAML 语法；红线是不许为通过而弱化断言
- **迭代闭环**：失败分性质修——Skill 行为错改 SKILL.md、覆盖不足补用例、断言错修断言（不许放水）；重跑生成新 iteration，历史可对比
- **评测集本身也是被演进的对象**——这是 skill-up 区别于"只跑评测"工具的本质

### 9.5 三套方案最终定位

| | skill-creator | promptfoo | skill-up |
|---|---|---|---|
| 本质 | 方法论（人肉编排） | 评测平台 | 评测 CLI + 演进闭环 |
| 最强项 | 会话内交互迭代 | 平台化（Web/矩阵/红队） | judge 证据质量 + Anthropic 兼容 + 一键消融 |
| 隔离 | 靠 prompt 指令 | fixture working_dir | none=纸糊，须上 sandbox |

一句话：**skill-up 把手动循环变成一条命令、judge 证据做到最强，但它的无沙箱消融被实测证明不可信——评测工具的隔离能力和判分能力一样重要。**

---

## 附：产出物

- 改进后的 skill（已生效）：`.claude/skills/self-test/`（GBK 修复 + 考点查重机制 + why 补充）
- 执行质量两轮数据：`.claude/skills/self-test-workspace/iteration-1|2/`（各 6 组 response/grading/timing + benchmark + review.html）
- 触发质量数据：`.claude/skills/self-test-workspace/trigger-eval/`（14 组 response + summary.md）
- promptfoo 复现实战：`SkillTest/promptfoo/`（promptfooconfig.yaml：2 providers + 5 断言；run-eval.cmd：认证桥；fixtures：v1/v2 + 06-MCP.md）
- skill-up 实战：`SkillTest/skill-up/`（self-test 副本 + evals 原生 YAML + 两轮 workspace 报告；隔离重跑目录 `Desktop/AI/skill-up-eval/`）

---

## 十、全程小结（收官）

### 总览

从一个问题出发——**"怎么对一个 SKILL 进行评测并优化？"**——走完了三套方案的完整实战，最终把它变成了"工程化·评估"环节的落地项目：

```
方法论框架（两维度）
   ↓
① skill-creator 手动实战：执行质量两轮迭代 + 触发质量一轮（26 次对照运行）
   ↓
② promptfoo 实战：外部平台桥接，swap-only 声明式对照 + LLM judge
   ↓
③ skill-up 实战：评测+演进闭环 CLI，撞出基线污染 + skill 真缺陷
   ↓
全部沉淀进 15-Skill评测实战.md（三套方案完整对照录）
```

### 一、方法论框架（一切的骨架）

**评测两维度，独立分开测，混测说不清 Δ 来源**：

| 维度 | 测什么 | 看哪 |
|------|--------|------|
| 执行质量 | 触发了做得好不好 | SKILL.md 正文 |
| 触发质量 | 该用时想不想得起、不该用抢不抢、抢不抢别人的活 | description |

### 二、手动实战（skill-creator 方法论）

**Iteration-1（证 skill 有用，对照=无 skill）**：94.4% vs 83.3%。Δ 拆解发现全部增量来自"锚定指定笔记"一条断言（4/6 断言非区分性）；with-skill 自己栽在"考点重复"——**口号 ≠ 机制**。

**三处改动**：GBK 脚本修复 / 新增"考点查重"可执行步骤（口号→机制）/ 护栏补 why。

**Iteration-2（证改动有效，对照=旧版快照）**：100% vs 94.4%，耗时 −25%，token 持平。**对照组随问题切换**是设计精髓。

**触发质量（14 条 query：正例口语变体 + 负例近似失误）**：14/14 全对——漏触发 0、误触发 0、技能路由 2/2（record-tool/git-upload 地盘没被抢）。description"推式"写法验证安全。

### 三、promptfoo 实战（外部平台桥接）

被测系统只要能被程序化调用就能进评测平台——桥 = Claude Agent SDK provider。**swap-only 声明式对照**（两个 provider 唯一差异 working_dir）、`skill-used` 断言拿**一等公民证据**（tool call 元数据）、`llm-rubric` + `file://` 变量把笔记喂给 judge。四道坎：SDK 认证桥接（环境变量显式传）、.cmd 纯 ASCII（GBK 第三次应验）、非区分性断言、单次方差。

### 四、skill-up 实战（评测+演进闭环）

两层架构（skill-upper 编排层 = 用 Skill 评测 Skill 的元应用；skill-up CLI 执行引擎）、import 无损吃掉存量 evals.json、`benchmark.enabled` 一键消融、**agent_judge 证据三套最强**（行号引用 + grep 验证 + transcript 交叉核对 + 格式自愈）、零认证配置。

**两个关键发现**：

1. **基线污染**——无 skill 基线 agent 从文件系统摸到仓库部署的真 skill 抄作业，Δ=0 是假象；搬出仓库也拦不住（全局配置授权 Desktop 读取）。三层教训：消融效度=隔离强度；共享机器 no-skill 基线必须真沙箱；**读轨迹和读分数一样重要**
2. **skill 真缺陷**——"考 Agent"匹配两篇笔记，预确认把"考哪篇"的追问短路 → 挂范围锚定。改进项：**多笔记匹配必须先问**。干净基线还实测挂了"越界"（考笔记外的 OAuth/Sampling）——skill 锚定价值首次被工具评测直接证实

### 五、三套方案最终定位

| | skill-creator | promptfoo | skill-up |
|---|---|---|---|
| 本质 | 方法论（人肉编排） | 评测平台 | 评测 CLI + 演进闭环 |
| 最强项 | 会话内交互迭代 | 平台化（Web/矩阵/红队/CI） | judge 证据 + Anthropic 兼容 + 一键消融 |
| 隔离 | 靠 prompt 指令 | fixture working_dir | none=纸糊，须沙箱 |

### 六、带走的判断力（十要点）

1. 两维度分开评 2. 测试集=真实 prompt+近似失误 3. 消融对照、baseline 随问题切换 4. 断言三层（脚本→judge→人工），**能脚本判的不用 judge** 5. **断言先问区分力**——全绿可能是安慰剂 6. 证据分级：tool call 元数据 > 行为佐证 > 模型自报 7. 指标三角（质量×成本×耗时） 8. **Δ 拆解归因**，别只看总分 9. **多轮看失败率**，单次 ≠ 结论 10. **口号≠机制**——每条质量要求配一个怎么做

外加三条工程级认知：**评测平台边界不在"能测什么"而在"被测系统能否被程序化调用"**；**消融效度=隔离强度**；**测试集该从真实使用长出来**（skill-up 的观察模式就是这个思路的产品化）。

### 七、遗留待办

1. **self-test 修"多笔记匹配歧义"**（改 SKILL.md + skill-up 跑回归，case-1 现成用例）
2. 隔离真 Δ：等真沙箱（docker/opensandbox）或干净配置 profile
3. 工程化剩余部分：流式输出 / FastAPI 部署 / 护栏

> 这条线走完，对"评测"的理解已从 12 号笔记的理论（四要素、界定→衡量→改进）落到三套工具的实操和坑里——**评估驱动开发，不再盲飞**。

