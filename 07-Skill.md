# 🧰 Skill 教程（阶段3笔记）

> 学习日期：2026-07-22
> 定位：阶段 3 框架与工具链。**工具体系进化链的顶层** -- 把"完成一类任务所需的一切"打包成按需加载的能力包。
> 路线位置：RAG ✅ -> Prompt ✅ -> FC ✅ -> Agent ✅ -> MCP ✅ -> **Skill** ✅ -> LangChain
> 关键词：能力封装包、渐进式披露、声明式触发

---

## 一、本质：为什么工具够用了还需要 Skill（三痛点）

MCP 站已经会把工具解耦成独立服务了。但 Agent 越来越能干，工具挂几十个上去，三个痛点一起冒出来：

**① 工具是"原子"的，但真实任务是"成套"的。**
用户说"帮我做一份销售数据图表分析报告"--单个工具不够，得查数据 -> 清洗 -> 算汇总 -> 画图 -> 排版，一整套配合。工具给的是螺丝刀、扳手，用户要的是"换轮胎"这个完整动作。原子工具之间怎么配合、什么顺序、什么参数，光靠工具的 description 讲不清。

**② 全塞进 system prompt 会爆。**
几十个工具 + 详细用法 + 模板 + 注意事项，全塞 system prompt，每轮带着 -- token 烧钱，模型注意力被稀释（一堆工具说明抢着被"看见"，反而选不对）。比 messages 膨胀更占地方。

**③ 知识和资源没地方放。**
完成某些任务不只靠"调函数"，还靠"参考文档""模板文件""示例脚本"。MCP 的 Tool 塞不进去（只暴露函数签名），塞 system prompt 又太大。

**Skill 解这三件事。** 一句话定义：

> 🎯 **一句话**：Skill = 把"完成某类任务所需的一切"打包成一个按需加载的能力包 = 指令（Prompt：怎么用）+ 工具（Tool：能做什么）+ 资源（Resource：参考文件/模板/脚本）。平时躺文件系统不占上下文，请求匹配到职责时才加载，且先加载说明书封面、需要细节再翻具体章节。

---

## 二、进化链顶层：Skill 站在 MCP 肩膀上

| 进化链 | 类比 | 解决的问题 | 状态 |
|---|---|---|---|
| **Function**（FC） | 一把螺丝刀 | 单点原子能力，模型决定调不调 | ✅ |
| **Tool / MCP** | 一套标准化的工具箱（统一接口） | 工具怎么跨进程、跨应用复用 | ✅ |
| **Skill** | "换轮胎技能包"（千斤顶+螺丝刀+操作手册+安全清单，整套打包） | 完成一类任务需要工具+知识+资源配合，且按需加载省上下文 | ✅ 本站 |

**Skill 和 MCP 是叠加不是替代。** Skill 是消费者/编排者，MCP 是供给者：

```
Skill（能力包：打包"做这类活"需要的工具+指令+资源，按需加载）
  └─ 里面调用的工具，很可能就是 MCP 工具
       └─ MCP（标准化供给工具，跨进程的手）
            └─ 工具被调用这件事，靠 FC 来决策（嘴）
```

Skill 里那个"查数据"的工具，背后完全可能就是 `test_mcp_server.py` 暴露的 MCP 工具。Skill 不取代 MCP，它站在 MCP 肩膀上，再加一层"知识+资源+用法"的打包，并管"什么时候才把这些加载进上下文"。

> 🔗 **MCP 站钩子兑现**：MCP 笔记结尾留的"Tool 是一把螺丝刀，Skill 是组装技能卡（告诉你用哪几把螺丝刀、按什么顺序）"--本站兑现。

---

## 三、Skill 长什么样：文件夹结构 + SKILL.md

**Skill 的物理形态就是一个文件夹**。标准结构：

```
my-skill/
├── SKILL.md            # 必需。说明书：封面 + 目录 + 操作手册
├── scripts/            # 可选。可执行脚本（Python）
│   └── convert.py
├── templates/          # 可选。模板文件
│   └── report.md
├── references/         # 可选。大块参考文档（按需读，平时不加载）
│   └── api_docs.md
└── assets/             # 可选。其他资源
```

核心是 `SKILL.md`，分两部分：

**① frontmatter（封面/索引）-- 轻量，常驻可被扫到：**

```markdown
---
name: pdf-to-json
description: 把 PDF 文档转成结构化 JSON。当用户要求从 PDF 提取数据、或把 PDF 转成 JSON 时使用。
---
```

**② body（操作手册）-- 中等重量，触发后才加载：**

```markdown
# PDF 转 JSON
## 何时用
用户要把 PDF 转成 JSON / 从 PDF 提取结构化数据。
## 步骤
1. 运行 scripts/convert.py 转换，传入 PDF 路径
2. 字段缺失时按 references/field_mapping.md 补全
3. 用 templates/report.md 套版生成报告
## 注意
- 扫描件 PDF 先 OCR，否则字段会丢
```

### name vs description：触发判断只看 description，不看 name

这是容易踩的坑：

- **`name` = 标识符**。给代码/机器用，短、稳定、唯一、合法（kebab-case）。被引用的 key，如 `use_skill("self-test")`。是"身份证号"。
- **`description` = 语义招牌**。给模型读，鼓励写自然语言 + use-when 触发场景。模型靠它做语义匹配判断要不要加载。是"店招"。

> 🎯 **关键**：模型决定"要不要用这个 Skill"靠的是**读 description 做语义匹配**，不是匹配 name 字面。触发条件写进 name 是**写错地方** -- name 压根不参与触发判断。所以 description 要写成"当用户要求 X 时使用"这种带场景的自然语言，name 只管短而稳定。

**进化链上 name+description 二元一直都在**：FC 的 `TOOLS_SCHEMA`（`name: "get_weather"` + `description: "查询某城市天气"`）、MCP 工具、Skill frontmatter，同一个结构。区别只是 Skill 的 description 更"重"，要管"何时加载整个能力包"。本站对照 `test_function_calling.py` 的 `TOOLS_SCHEMA` 验证过。

---

## 四、核心设计：渐进式披露三层（Progressive Disclosure）

这是 Skill 最精巧的设计，也是它的命门：

| 层 | 何时加载 | 装什么 | 成本 |
|---|---|---|---|
| **L0**：frontmatter 的 `description` | 常驻，模型总扫得到 | 一句话：我是干啥的 | 极低 |
| **L1**：SKILL.md 的 body | 匹配到 Skill 后加载 | 步骤 + 何时用 + 注意事项 | 中 |
| **L2**：scripts / templates / references | body 指明要用时才 Read/运行 | 大块知识、模板、脚本 | 按需 |

body 步骤里**引用**而非**内联**资源是命门：
- 步骤写"运行 `scripts/extract_topics.py`"-- 但脚本代码不在 SKILL.md 里，执行时才加载。
- 步骤写"参考 `references/bloom_taxonomy.md`"-- 文件内容不在 SKILL.md 里，读取时才注入。

> 🎯 **一句话**：如果图省事把大块知识直接塞进 body（比如把布鲁姆 6 层全写进 SKILL.md），就破坏了渐进式披露 -- 本该按需的变成常驻，token 浪费、注意力稀释、可能撑爆上下文。和第一段那三痛点一模一样。

**和 RAG 的关系**：RAG 是"文档库太大塞不下，先放索引、用到再检索原文"；Skill 是"上下文装不下所有能力，先放 description 索引、用到再加载手册和资源"。同一个思想，一个作用在**外部知识**，一个作用在 **Agent 自身的能力** -- 上下文层的 RAG。

---

## 五、实战：第一个 Skill（self-test）

### 为什么选它
1. 学完 RAG/Prompt/FC/Agent/MCP 五座大山，正需要复习，立刻能用上；
2. 完整展示三层（指令 + 脚本 + 资源）；
3. 隐喻命中 Skill 本质：把"老师怎么出题、怎么判分"这套**方法论**打包成可复用包，而非临场发挥。

### 结构
见 `Skills/self-test/`：

```
Skills/self-test/
├── SKILL.md                      # 核心：说明书（指令层）
├── scripts/
│   └── extract_topics.py         # 从笔记 md 提取标题考点（工具层）
└── references/
    └── bloom_taxonomy.md         # 布鲁姆6层 + 出题示范 + 配比（资源层）
```

### SKILL.md 关键点（呼应已学）
- **frontmatter**：`name: self-test`（标识符）+ `description: ...当用户说"考我""自测"时使用`（语义招牌，带触发场景）-- name/description 机制实物。
- **body 分层**：何时用 / 前置 / 步骤 / 注意 = Prompt 站的"任务/输入/格式/约束"分层。
- **步骤引用资源**：步骤 1"运行 `scripts/extract_topics.py`"、步骤 3"参考 `references/bloom_taxonomy.md`"-- 渐进式披露 L2，body 不内联大块内容。
- **注意段 = Rule 护栏**："绝不先透露答案""笔记没有别编题"= Prompt 站 Rule（最弱护栏）；"不编题"= RAG 站"不编造"防幻觉 Rule 同款。

### 工具层 vs 资源层：两种本质不同的子目录

| | `scripts/` 工具层 | `references/` 资源层 |
|---|---|---|
| 是什么 | 可执行的确定性代码 | 只读的大块知识 |
| 怎么用 | 运行，拿 stdout 结果 | 阅读，注入上下文 |
| 干什么活 | LLM 不擅长的精确活（解析、计数） | LLM 需要参考但不常驻的活（规范、领域知识） |
| 呼应已学 | FC"工具补短板，不代替思考" | RAG"检索增强" |

`extract_topics.py` 用正则精确抠标题、数清楚有几个 -- 这种活让 LLM 干容易数错漏，交给代码最稳（同 FC 站 1234×5678 让 calculate 真算）。`bloom_taxonomy.md` 是出题方法论，6 层 + 配比 + 示范不小，全塞 SKILL.md 违反渐进式披露，单独成文件出题时才 Read。

> 🎯 **重逢**：MCP 三大原语 Tools / Resources / Prompts，在 Skill 子目录以 `scripts`（Tools）/ `references`（Resources）/ `SKILL.md body`（Prompts）的形式重逢。三大范式换个壳又见面了。

---

## 六、最后一公里：怎么被识别和触发

### 放哪
Skill 必须放到指定目录，Claude Code 才扫描到它（放在 `Skills/` 里只是一堆文件，模型看不见）：
- **用户级**：`~/.claude/skills/<name>/`（全局，所有项目可用）
- **项目级**：`<项目>/.claude/skills/<name>/`（只在该项目生效）

本站部署到 `c:\Users\Administrator\Desktop\AI\Studying\.claude\skills\self-test\`（项目级）。

### 触发机制（时间线）

```
① Claude Code 启动
   └─ 扫描 .claude/skills/*/SKILL.md
      └─ 只读 frontmatter（name + description）
         └─ description 进「可用 skill 列表」常驻          ← L0

② 用户发："考我 RAG"
   └─ 模型拿这句话，和所有 skill 的 description 做语义匹配
      └─ 命中 self-test（"考我""自测"对上了）
         └─ 加载这个 SKILL.md 的 body 进上下文            ← L1

③ body 步骤 1："运行 scripts/extract_topics.py"
   └─ 执行脚本，拿考点清单                                ← L2
   body 步骤 3："参考 references/bloom_taxonomy.md"
   └─ Read 这个文件，6 层知识注入上下文                    ← L2
```

### 两个收尾认知

**① 触发是「声明式」的，不是「命令式」的。**
- 命令式（Workflow）：代码写 `if 用户说"考我": 加载 skill` -- 写死，漏关键词就不触发。
- 声明式（Skill）：description 写"当用户说考我时使用"，**模型自己语义判断**。说"检验一下我学没学会"也能触发，哪怕原话没在 description 里 -- 语义像就行。

延伸 Agent 站 Workflow vs Agent 的区分：Skill 是声明式能力包，靠模型自主语义触发，不是写死流程。description 写得好不好，直接决定被想起的概率。

**② 「按需加载」是 Harness 干的，不是模型自己干的。**
模型只负责一件事：**判断要不要用这个 Skill**（读 description 语义匹配）。扫描目录、读 frontmatter、把 body 注入上下文、管 token -- **全是 Claude Code 这个 Harness（Agent 运行壳）在做**。模型自己没法"去文件系统翻一个 SKILL.md 进来"。呼应 MCP 站"Claude Code 即 Host + Agent"。

---

## 六.5 实战教训：声明式触发不可靠（实测）

部署 self-test 后实测：说"考我 RAG""出几道题复习"**都不自动触发**，只有 `/self-test` 斜杠命令才触发。这不是 bug，是声明式触发的固有特性：

- **模型会 rationalize 跳过**："出题这事我自己能干"，觉得不需要 skill，即使触发词就在消息里。
- **简单任务即使 description 完美匹配也不触发**：模型只对"超出自身基础能力、需专门知识/工具"的任务才主动调 skill。"考我 RAG"在模型看来是本来就会的。
- **呼应第五段钉子**：声明式=自主判断（含"判断不需要"）；命令式=强制可靠。`explicit beats implicit`--重要场景用斜杠命令。

**改进**：description 用"必须"式 + 理由（减少跳过空间）；写用户实际说的话（像搜索查询）；2 句以内。诊断工具：新对话问"你有哪些可用 skill？"确认在列表；`/doctor` 看为什么不触发。本站 description 已改成"必须"式，但自动触发是便利不是保证。

> 🔗 **补丁第五段**：第五段讲"触发是声明式"时太理想，只讲"灵活"的好处。实测补上代价--**不可靠**（模型可能跳过）。这是声明式 vs 命令式 trade-off 的另一半，缺了就不完整。

---

## 七、Skill 站总收尾

带走五件事：

1. **Skill = 能力封装包**：指令（Prompt）+ 工具（Tool）+ 资源（Resource）打包，按需加载。解决"工具原子但任务成套 / 全塞 prompt 爆 / 大块资源无处放"三痛点。
2. **物理形态是一个文件夹**：`SKILL.md`（name + description 的 frontmatter，和 何时用/前置/步骤/注意 的 body）+ `scripts/`（可执行）+ `references/`（只读大块知识）+ `templates/`（模板）。
3. **name vs description**：name 是标识符（代码用），description 是语义招牌（模型靠它做语义匹配判断触发）。触发条件写 description 不写 name。FC/MCP/Skill 三层同构。
4. **渐进式披露三层**：L0 description 常驻索引 / L1 body 触发后加载 / L2 scripts+references 按需执行或读。= 上下文层的 RAG。
5. **触发是声明式 + 加载是 Harness**：模型靠 description 语义自主判断要不要用（非 if-else 命令式）；扫描和注入 body 是 Harness（Claude Code）实现的，不是模型自己。

### 工具体系进化位置

```
Function Calling             ← 函数 + 手写 schema，绑死在应用 ✅
        │  解耦成独立服务 + 标准协议
        ▼
Tool / MCP                   ← 标准化工具服务，跨 Host 复用 ✅
        │  再包一层"怎么用"的说明书（prompt + 资源 + 工具）+ 按需加载
        ▼
Skill                        ← 能力封装包，渐进式披露 ✅（本站）
```

> 🔗 **下一站钩子（LangChain）**：
> - Skill 是"声明式 + 模型自主触发"的能力包；LangChain 是"把手写的 ReAct / Agent 循环工业化封装"成框架（AgentExecutor / LangGraph 节点）。
> - Agent 站你手写的 Thought/Action/Observation 循环、Skill 的按需加载，LangChain / LangGraph 都有对应抽象。先手写理解原理，再用框架省体力，是正确顺序。
> - 也可以先学 LangGraph（AI Workflow 编排，确定性 + 条件分支），再回 LangChain（Agent 封装）。
>
> Skill 站完成。下一站：**LangChain**（或 LangGraph）。
