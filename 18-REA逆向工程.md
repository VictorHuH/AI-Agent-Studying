# REA 逆向工程（工程实践调研）

> 2026-10-17 调研完成。**非学习路线节点，是工作中实测的工具调研**，归入「工程实践补充」。
> 衔接 [[06-MCP]] / [[07-Skill]] / [[13-CLI]]：【MCP + Skill + CLI 三形态同时出现，且三者的成本差被实测量化】
> 关键词：Evidence 契约 · authority/confidence · limitations · token 感知 IO · 建库/查库分离 · MCP 常驻成本

---

## 核心认知

> **REA 不输出「结论」，它输出「证据 + 索引」，结论由 Agent 自己下。**
>
> 它的价值不在"给你源码"（源码你本来就能拿到），在**"给你一张精确到列、且标注了可信度的地图"**。

---

## 一、问题：Agent 遇到"没有源码的东西"就瞎猜

给 Agent 看一个 App、一个网站、一个二进制，它只有两条路：

| 路 | 症状 | 根因 |
|---|---|---|
| **猜** | 说"这个功能大概是这么实现的"，说得头头是道 | 模型在补全，不是在观测 |
| **人肉翻** | DevTools 手点、`curl` 抓 HTML | SPA 空壳（37KB HTML 全靠 JS 渲染）、278 个 chunk 人工翻不现实、微前端运行时才注入 |

两条路都缺同一个东西：**可核验的证据**。模型说 `main.js:9` 写了文件，你怎么知道对不对？

🎯 **本质：逆向工程缺的不是"能不能看出来"，是"看出来的东西凭什么可信"。**

REA 的回答是——**把不确定性做成一等公民**。

---

## 二、原理：Evidence 三件套

REA 的每个结论都挂三个标签。这是它和"让 GPT 猜代码"的本质区别。

### 2.1 `authority` —— 我是怎么知道的

| 取值 | 含义 |
|---|---|
| `ast-static-analysis` | 直接从 AST 读到的（最硬） |
| `artifact-bytes` | 从文件字节读到的 |
| `static-relationship-inference` | **推断**出来的（跨文件关系） |
| `unknown` | **明说不知道** |

### 2.2 `confidence` —— 我有多确定

`exact` / `high` / `medium` / `low` / `unknown`

G HUB 实测分布（4674 条推断 vs 3419 条直读 vs 1513 条 unknown）—— **它敢标 unknown**。

### 2.3 `limitations` —— 我的边界在哪

一次 G HUB 分析吐出 **11 条限制**，克制到近乎冷酷。摘几条：

- **"Graph coverage is incomplete; unavailable facts remain explicit and must not be read as absence."**
  → 直接写「查不到 ≠ 不存在」给模型看，**这是写给 LLM 的反幻觉护栏**
- "Dynamic IPC channel expressions remain unresolved and are **never paired by textual similarity**."
  → 明确拒绝模糊匹配（宁可漏，不可猜）
- "JavaScript and HTML were parsed as inert text; bundle bootstrap code was never executed."
- **"app.min.js: ... Owned JavaScript worker exhausted its heap while analyzing app.min.js"**
  → **它把一个真实的分析失败如实写进了 limitations，而不是静默返回部分结果假装成功**

> 🔗 **呼应已学**：这套东西和你 RAG 里写的「不编造」Rule 是同一个病——**但 REA 不是靠喊口号，是把"我为什么不确定"做成了结构化字段**。
> 对比 [[15-Skill评测实战]] 的教训「口号≠机制」：REA 把"别过度断言"从口号变成了可机读的数据。

### 2.4 一个结论长什么样

```yaml
kind: ipc-channel
identity:
  strategy: artifact-local-key
  stability: artifact-version        # 身份绑产物哈希，换版本 ID 就变
  namespace: electron-inferred-ipc-channel   # 注意 "inferred"
  key: "literal:OPEN_DIALOG"
observations[1]:
  - label: OPEN_DIALOG
    properties:
      side: main            # main 进程
      operation: handle     # ipcMain.handle
      channel: OPEN_DIALOG
      resolution: literal   # 字面量，不是动态拼的
    evidence:
      authority: static-relationship-inference
      state: inferred       # 明说是推断
      confidence: high
      location:
        source: main.js
        start: { line: 25, column: 419265 }   # 精确到列
      coverage: { status: partial }           # 自认覆盖不全
```

---

## 三、怎么跑的：静态分析，全程不执行

**解压 + 读 AST + 模式匹配。三步，全程不运行目标程序。**

| 步骤 | 做法 |
|---|---|
| **1. 拿源码** | 不是破解，是解压/读取——`app.asar` 本身就是归档文件，里面本来就有打包后的 JS；网站脚本是**浏览器已经下载下来执行的**，通过 CDP 读出来 |
| **2. 解析成 AST** | Babel（证据里写着 `structural_fingerprint_algorithm: babel-ast-v2`） |
| **3. 找已知模式** | `import`/`require`/`__webpack_require__` → 模块边；`ipcMain.handle` ↔ `ipcRenderer.invoke` → 按**字面量名配对**；`contextBridge.exposeInMainWorld` → contextBridge 节点；`fetch` → endpoint 候选 |

**source map 是关键变量**：带 `.map` 就能顺着还原出**原始源码**（甚至 TypeScript）；没有就只能拿到 min 过的代码。

**因为不执行，所以有盲区** —— webpack 的 bootstrap 没跑过、动态拼接的通道名解析不了、运行时注册的东西看不到。**盲区全部变成 limitations 里的那些话。**

### 3.1 建库 vs 查库（最重要的一条设计）

```
analyze-*        →  建库   贵（G HUB 19MB 跑 1m52s）   跑一次
trace-* / inspect-* / search / compare  →  查库   便宜   反复跑
evidence-export  →  把库存成规范 JSON
```

而且查询接口分两代：

| | 吃什么 | 行为 |
|---|---|---|
| `search <path>` / `trace <path>` | **路径** | 内部重新分析 → 慢 |
| `trace-application-feature <inputJson>` / `inspect-analysis-view <inputJson>` | **Evidence JSON** | 不重跑 → 快 |

> 🎯 **如果你自己写 MCP server，这条必须抄：昂贵的计算和廉价的查询必须拆开。**
> 合成一个工具，Agent 每次追问都重跑一遍分析——一个会话问 10 个问题就是 17 分钟。

### 3.2 token 感知的 IO 契约

| flag | 作用 |
|---|---|
| `--token-count` | 只报输出多少 token，**不打印内容** |
| `--token-limit <n>` / `--token-offset <n>` | 按 token 分页，不是按行 |
| `--filter-output <keys>` | 按键路径投影（`foo,bar.baz,a[0,3]`） |
| `--llms` / `--llms-full` | 吐一份"给 LLM 看的清单" |
| `--schema` | 每个命令的 JSON Schema |
| `--format <toon\|json\|yaml\|md\|jsonl>` | `toon` 是给 LLM 的紧凑格式 |

**这组 flag 的存在本身就说明：REA 的 CLI 从第一天就是按"被 Agent 调用"设计的，不是给人敲的。**

---

## 四、命令与模式

### 4.1 安装（`npx rea-agents setup`）

交互式，会列出所有改动让你 approve。**多选菜单是 `Space toggle · Enter confirm`——直接回车 = 一个都不选。**

| 选了什么 | 装到哪 | 效果 |
|---|---|---|
| agents 选 `none` | `.agents/skills/reverse-engineer-anything/` | 只有 skill，**且是"for CLI use"那套**（给读 AGENTS.md 约定的 CLI 型 Agent） |
| agents 选 `Claude Code` | `.claude/skills/reverse-engineer-anything/` + `.claude.json` 的 `mcpServers.rea` | skill + MCP 都装，**且带配置备份 `.claude.json.rea.backup`** |

### 4.2 常用命令

| 命令 | 作用 |
|---|---|
| `rea doctor` | 体检：Node/宿主/分析引擎/注册状态/skill 身份 |
| `rea capabilities` | 列出 provider 能力和**副作用**（哪些会真的运行目标程序） |
| `rea analyze-javascript-application <asar\|dir>` | 建库：JS/Electron 静态重建 |
| `rea analyze-web-bundle <endpoint> <target>` | 建库：网站 bundle 静态解析 |
| `rea inspect-web-page <endpoint> <target>` | 被动观测已打开的页面 |
| `rea list-browser-targets <endpoint>` | 列出可 attach 的页面 |
| `rea evidence-export / -import` | 证据留档 / 导入 |
| `rea uninstall` | 全部移除（MCP 注册 + skill） |

### 4.3 网站逆向的姿势（和你想的不一样）

**它不爬网页，它 attach 到你自己开着的浏览器。**

```bash
# 自己起一个带调试端口的 Chrome（必须独立 profile）
chrome.exe --headless=new --remote-debugging-port=9222 \
  --user-data-dir=".../chrome-profile" "https://目标/"
# REA 连 http://127.0.0.1:9222
rea list-browser-targets http://127.0.0.1:9222
rea analyze-web-bundle  http://127.0.0.1:9222 <TARGET_ID>
rea inspect-web-page    http://127.0.0.1:9222 <TARGET_ID> --include-script-sources
```

**明确不是浏览器自动化**：不暴露通用 CDP、没有 `Runtime.evaluate`、**不能导航/输入/下载/关页面**，截图是唯一的像素接口。
**数据最小化是硬设计**：DOM 只留节点类型/属性名**不留文本**；cookie 和 authorization 头**永不保留**；storage 值永远脱敏。

---

## 五、实测

### 5.1 G HUB（本地 Electron，19 MB asar）

```bash
rea analyze-javascript-application "C:/Program Files/LGHUB/resources/app.asar"
```

| 指标 | 值 |
|---|---|
| 耗时 | **1 分 52 秒** |
| 输出 | **200 MB / 489 万行**（默认 YAML） |
| coverage | 1581 modules · 2336 图节点 · 2,206,638 AST 节点 · parse_failures: 0 |
| IPC | operations 132 · literal_channels 38 · **dynamic_channel_operations 94** · renderer_transmissions 67 · main_handlers 29 · **paired 0** · **unpaired_literal 3** |

**200 MB 里只有 32 行是给人看的**：

| 行号范围 | 内容 | 行数 | 占比 |
|---|---|---|---|
| 1–26 | Evidence 信封头 | 26 | ~0% |
| 27–391538 | `graph` 应用图（2336 节点） | 391,512 | 8% |
| **391539–391570** | **`summary` + `statistics` + `limitations`** | **32** | **~0%** |
| 391571–4894050 | `semantic_graph` 语义图 | 4,502,480 | **92%** |

**投影实测：**

```bash
rea analyze-javascript-application <asar> \
  --filter-output normalized_result.summary,normalized_result.statistics,normalized_result.limitations
# → 200 MB 变 4 KB（33 行）
```

⚠️ **但 `--filter-output` 只省上下文，不省时间** —— 实测照样跑满 1m52s，过滤发生在算完之后。

### 5.2 MCP 探针：207 个工具值不值

自己写了个 stdio 握手脚本探它的 tool 列表：

| 指标 | 值 |
|---|---|
| 工具数 | **207** |
| schema 总量 | **3,087,734 B（3.09 MB）** |
| 约合 token | **~858,000** |
| 中位数工具大小 | 10 KB |

**分布很平，砍不掉**：>50KB 只有 4 个，前 20 个只占 31.8%，就算删掉最胖的 20 个还剩 2.1 MB。
**`rea mcp` 只有 `add` 和 `doctor` 两个子命令，没有任何过滤/裁剪选项。**

**对比 skill 的体积**：`SKILL.md` 22 KB + `references/` 68 KB（按需加载）。

| 方案 | 常驻上下文 |
|---|---|
| skill + MCP | 3 MB（~858K token）+ 22 KB |
| **skill + CLI** | **22 KB**（references 68 KB 按需） |

**差 40 倍，能力一样** —— 因为 SKILL.md 第 68–79 行明确写了 CLI 兜底：

> A concrete CLI fallback for an operator-supplied JavaScript tree or ASAR is:
> `npx -y rea-agents@6.5.0 analyze-javascript-application /absolute/path/to/app --json`
> ...treat the resulting graph, limitations, and unknowns with **the same care as an MCP result**.

→ **结论：撤 MCP 注册，留 skill。这是官方支持的姿势，不是 hack。**

### 5.3 官方 notes 示例验证（交叉核对）

对 6 文件的官方示例跑 `analyze_javascript_application` + `trace_application_feature`，产出 renderer→preload→IPC→main 完整链路。**我逐条对着源码核了每一条 `file:line`，全部命中**（zip sha256 `646ec1ee…` 也对得上）。

| 声明 | 核对 |
|---|---|
| `index.html:15` 按钮 / `renderer.js:1-3` / `preload.js:3-4` / `main.js:8,9,10,16` / `csv.js:2,7` | ✅ 全对 |
| CSV 内容 `id,title\n1,"First note"\n`（手推） | ✅ 对 |
| `paired_renderer_transmissions: 1` / `unpaired: 0` | ✅ 静态可确定（通道名是 literal） |

**但要说清它证明了什么**：示例才 6 文件 50 行，Agent 本来就能直接读源码（它自己也写了"源码逐行核对"）。
→ **这验证了 REA「准」，没验证 REA「必要」。真正的考验是没有源码的时候。**

**最有价值的是两句边界声明**（limitations 传导成功的直接证据）：

```
app.getPath("downloads") 的实际返回值是运行时才确定的；上面给的 Windows 路径
是 Electron 的文档化行为，不是 REA 观测到的。
```
→ 没有这句，工具会自信地报"写到 C:\Users\Administrator\Downloads\notes.csv"（文档推断，不是观测）。

```
该 trace 只覆盖到 preload 侧的 ipcRenderer.invoke 表达式为止；main 侧的配对结论
来自应用图统计，不是同一条 trace 路径。
```
→ 把"trace 覆盖的"和"应用图统计推断的"**明确区分开**——两种不同的证据来源。

### 5.4 海康威视 AI 开放平台（网站逆向，详见 `rea/基于REA的海康威视AI开放平台站点分析.md`）

CDP 被动观测 + curl/openssl 响应层实测。**最有价值的发现是微前端联邦拓扑**：

```
/ai-layout/static/aiop-base-tmp/aiop-base@1.0.0/mf-manifest.json
/ai-layout/static/aiop-intelligent-assistant/.../mf-manifest.json
```

`mf-manifest.json` 而非 `remoteEntry.js` → **Module Federation 2.0**（`@module-federation/enhanced`）。
我在 manifest 原件里又捡到两个直接证据：`pluginVersion: "0.21.6"`（插件版本，可直接确证 MF2）、`prefetchInterface: false`。

**核心方法论（最有复用价值的一条）**：

> **从 t=0 抓全量请求，才能看见运行时注入的东西。**
> `mf-manifest.json` 在静态分析、宿主 bundle 搜索里**全部零命中**，只有全量请求清单里才现形。
> 所以「自己起浏览器 + 从零开始捕获」比「attach 到已加载的页面」信息量大一个数量级。

**我的复核（对着 manifest 原件）**：

| 报告的结论 | 复核结果 |
|---|---|
| `aiop-ui` 联邦 shared 漏配 | ✅ **确证**。base 声明 `aiop-ui@1.2.20 singleton:true`，assistant 的 shared 里**只有 vue** |
| 「vue 配对成功，只加载一份」 | ⚠️ **站不住**。两边是**两份不同 hash** 的 `lib-vue`，且 assistant 侧 `singleton: false`。版本号相同推不出只加载一份 |

---

## 六、对比官方 Benchmark

**无。** REA 没有官方 benchmark，也**不做效果宣称**——它的输出全是带可信度的证据，不报"准确率 X%"。

> 这反而是它最诚实的地方：**逆向工程没有 ground truth 数据集，任何"准确率"都是编的。**
> 对比 [[16-CodeGraph]] 的官方数据（调用 ↓71%/token ↓57%）——那是可量化的效率指标，REA 给不出同类的，因为它治的病不同。

---

## 七、劣势与边界

| # | 边界 | 说明 |
|---|---|---|
| 1 | **MCP 常驻成本极高** | 207 tools / 3.09 MB schema / ~858K token，无裁剪选项 |
| 2 | **不执行目标程序** | 动态通道、运行时注册、真实行为全看不到；性能指标（LCP/TTI）拿不到 |
| 3 | **需要分析引擎** | 原生二进制要 Hopper（付费，macOS）/ Ghidra（免费，Windows 支持 experimental）/ IDA（付费）；JS 和 .NET 静态分析不需要 |
| 4 | **大目标会失控** | 19 MB 已跑 1m52s / 200 MB 输出；187 MB 的 asar 不建议全量跑 |
| 5 | **`detail: "summary"` 不落盘** | 完整 Evidence 只在进程内存，要留档必须显式 `export_evidence_bundle` |
| 6 | **注册版本钉死** | `npx -y rea-agents@6.5.0 mcp`，不会自动升级；升级要重跑 setup |
| 7 | **年轻且活跃** | 半年 28.5 万 star / 1100+ open issues / 每 2–3 天发版 → 坑多但修得快 |

**坑清单（实测踩到的）**：

1. **多选菜单直接回车 = 一个都不选** → 只装了 skill，没装 MCP（第一次踩）
2. **skill 装哪个目录取决于有没有选中 agent**：`.agents/skills/`（CLI 用）vs `.claude/skills/`（Claude Code 用）
3. **`--filter-output` 不省时间**，只省上下文
4. **结果超 token 上限会被 harness 落盘**到 `.claude/projects/.../tool-results/`——**这是传输层截断的副作用，不是 REA 的导出机制**
5. **Windows 没装 `jq`** → 用 `node -e` 读落盘 JSON；**bash 双引号里正则的 `$` `{}` 会被吃掉**（改用 `includes()`/`endsWith()`）
6. **MCP 启动每次都要跑 npx** → 冷启动要下 238 MB，可能超时

---

## 八、类似工具对比

| 工具 | 定位 | 和 REA 的差异 |
|---|---|---|
| **DevTools / View Source** | 人肉翻 | 无结构化证据、无 file:line、无可信度标注 |
| **curl / HTTP 层** | 看响应 | 只看到响应，看不到代码结构 |
| **Wappalyzer** | 技术栈识别 | 只识别"用了什么"，不回答"怎么实现的" |
| **Ghidra / IDA / Hopper** | 原生二进制反汇编/反编译引擎 | REA 是**编排层**——把它们和 Babel/CDP/JADX 的输出统一成同一套 Evidence 契约 |
| [[16-CodeGraph]] | 本地代码知识图谱（tree-sitter） | **CodeGraph 要源码，REA 治的是没有源码**。互补不重叠 |

> 关键区分：**CodeGraph 和 REA 都产出"图 + 精确位置"，但一个从源码建、一个从产物建。**
> 前者回答"我的代码里谁调用了谁"，后者回答"这个我拿不到源码的东西是怎么跑的"。

---

## 九、收尾 + 连接到已学

### 带走 6 件事

1. **Evidence 三件套**（authority + confidence + limitations）——把不确定性做成一等公民
2. **建库 / 查库分离**——昂贵的计算和廉价的查询必须拆开
3. **token 感知的 IO 契约**——消费者是 LLM 不是人，`--token-count/limit/offset` 是标配
4. **输出要"投影"不要"精简"**——200 MB 里 32 行给人看，不该读它该 SELECT 它
5. **装 MCP 前先数 tool 数量和 schema 体积**——207 tools = 858K token 常驻成本
6. **REA 的价值 = 一张精确到列、标注了可信度的地图**，不是"给你源码"

### 连接已学

| 已学概念 | REA 里的体现 |
|---|---|
| **MCP**（06站） | 一个 stdio Server 暴露 **207 个 tool**——"工具多"的极端反例，正好验证 13 站的选型判据 |
| **Skill**（07站） | 22 KB 说明书，**明写 CLI 兜底**，且要求把 CLI 结果与 MCP 结果同等对待——**MCP/Skill 可分离的活案例** |
| **CLI**（13站） | 双形态活案例；"工具多低频选 CLI 省上下文"被 858K token 实测证实 |
| **Agent**（05站） | 给 Agent 装"逆向的手"；skill 塑造它的调查习惯（安全侧观察是 Agent 自己读出来的，不是 REA 给的） |
| **Prompt Rule**（03站） | `limitations` 是"不编造"Rule 的**机制化版本**——不是喊口号，是结构化字段 |
| **Benchmark**（12站） | authority/confidence 分级 ≈ 评测里的可信度标注；**没有官方 benchmark 反而诚实**（逆向无 ground truth） |
| **RAG**（01站） | 建库/查库分离 ≈ 索引一次反复查询；Evidence 信封 ≈ 带元数据的检索单元 |
| [[15-Skill评测实战]] | 「口号≠机制」的又一例证：REA 把"别过度断言"做成了可机读数据 |
| [[16-CodeGraph]] | 同产出"图+精确位置"，但**一个从源码建、一个从产物建**，互补不重叠 |

> **价值定位**：没引入新范式，是已学 MCP(06站) + Skill(07站) + CLI(13站) + Agent(05站) 三形态的产品级组装。
> 归「工程实践补充」，非学习路线节点。

---

## 参考资料

- [REA GitHub](https://github.com/morluto/rea) · [官网](https://rea.tools/) · [Showcases](https://rea.tools/showcase/)
- [browser-observation.md](https://github.com/morluto/rea/blob/main/docs/browser-observation.md)（CDP 被动观测 + 数据最小化）
- [web-network-captures.md](https://github.com/morluto/rea/blob/main/docs/web-network-captures.md)（HAR/SAZ 离线分析）
- [mcp-contracts.md](https://github.com/morluto/rea/blob/main/docs/mcp-contracts.md)（工具契约 + 自动生成的 tool catalog）
- 本地实践产物：`rea/基于REA的海康威视AI开放平台站点分析.md`、`rea/manifests/`
- ⚠️ `rea/notes-example.zip` 等是从 `rea.tools` 下载的外部产物，**不要提交进 git**
