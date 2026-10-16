# 基于 REA 的海康威视 AI 开放平台站点分析

> **分析对象**：`https://ai.hikvision.com/`（标题「海康威视AI开放平台」）
> **分析日期**：2026-10-17
> **分析方法**：REA 被动观测（CDP）+ curl/openssl 响应层实测
> **关键词**：REA · 被动观测 · Module Federation 2.0 · 微前端 · CORS · CSP · 无障碍 · 供应链

---

## 第一章 REA 应用过程

这一章记录**怎么做的**，不是**发现了什么**。分析结论从第二章开始。

### 1.1 为什么选 REA

普通「看网站」有两条路：View Source / DevTools 手翻，或者 `curl` 抓 HTML 解析。

这两条路对这个站点都失效：

| 障碍 | 说明 |
|---|---|
| **SPA 空壳** | `curl` 拿到的 HTML 只有 37KB，`<body>` 里几乎没内容，全靠 JS 渲染 |
| **分块加载** | 278 个 `chunk-*.js`，人工翻不现实 |
| **微前端** | 远程模块运行时才注入，静态抓取看不到拓扑 |
| **体量** | 单次加载 653 个请求 |

REA 的价值在于：**通过 CDP 被动观测一个已经在跑的浏览器**，拿到渲染后的 DOM、可访问性树、脚本清单、资源清单，同时对 JS 做静态解析（不执行），产出路由表、端点、联邦拓扑。

关键约束——**REA 不执行页面 JS**。它读的是「已经渲染出来的结果」和「静态解析出的结构」，不是运行时行为。这一点决定了后面所有结论的性质。

### 1.2 环境准备：CDP 端口

REA 的浏览器工具全部走 **CDP（Chrome DevTools Protocol）**，需要一个开着调试端口的浏览器。第一次尝试直接连 `127.0.0.1:9222`，**失败**：

```json
{
  "error": {
    "code": "provider_unavailable",
    "message": "list_browser_targets could not reach the selected loopback debugging endpoint.",
    "details": { "reason": "endpoint_unreachable" }
  }
}
```

原因：用户日常开的 Chrome **默认不监听调试端口**。确认了一下，Chrome 在跑，但 9222/9223/9229 全部未监听。

两条路：

| 方案 | 做法 | 取舍 |
|---|---|---|
| A. 接管用户浏览器 | 关掉 Chrome，带 `--remote-debugging-port=9222` 重启 | 干扰用户，且要清空 profile 锁 |
| **B. REA 自起浏览器** | `capture_browser_scenario` 的 `mode: "launch"` | ✅ 不动用户的 Chrome |

选了 B，但更进一步——为了用上 REA 的**全套被动工具**（`inspect_web_page` / `analyze_web_bundle` 等，这些需要 `target_id`，而 `capture_browser_scenario` 一次性抓完就关），我改成**自己用命令行起一个带调试端口的 headless Chrome**，再让 REA 连上去：

```bash
"C:/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless=new \
  --remote-debugging-port=9222 \
  --user-data-dir=".../rea/chrome-profile" \
  --no-first-run --no-default-browser-check --disable-gpu \
  "https://ai.hikvision.com/"
```

这样浏览器常驻，REA 可以反复观测同一个 target。**这是本次分析的关键操作。**

> 注：`--user-data-dir` 必须独立，否则会和用户正在跑的 Chrome 抢 profile 锁。

### 1.3 实际调用序列

全程只用了 **1 个 MCP 服务：`rea`**（`npx -y rea-agents@6.5.0 mcp`）。

| # | 工具 | 关键参数 | 产出 |
|---|---|---|---|
| 1 | `list_browser_targets` | `9222` | ❌ 端点不可达 |
| 2 | `capture_browser_scenario` | `mode: launch`，8s 等待 | 侦察：站点性质、技术栈线索、1968 事件 |
| 3 | `list_browser_targets` | `9222`（自起浏览器） | ✅ `target_id = E5E7…`，标题「海康威视AI开放平台」 |
| 4 | `inspect_web_page` | a11y + console + storage + json/ws shapes | DOM 2514 节点、a11y 737 节点、脚本 38、资源 81 |
| 5 | `capture_browser_scenario` | 全新 profile，8s | 653 请求全量清单 → **定位 `mf-manifest.json`** |
| 6 | `analyze_web_bundle` | 同 target | 38 脚本静态解析，**499 万 AST 节点** → 45 条路由、2 个端点 |

辅助 CLI（REA 之外的补充）：

| 命令 | 用途 |
|---|---|
| `curl -D -` | 响应头、TLS、压缩协商、CORS 行为 |
| `openssl s_client -alpn` | ALPN 协议协商（确认 HTTP/2） |
| `curl -w "%{size_download}"` | 逐文件实测传输体积 |
| `node -e` | 解析 REA 落盘的大 JSON |

### 1.4 踩到的四个坑

**坑 1：调试端口没开。** 见 1.2。REA 报的是 `endpoint_unreachable`，不是配置错误——先分辨清楚再动手，别急着跑 `doctor` 修配置。

**坑 2：结果超出 token 上限，被 harness 落盘。** `analyze_web_bundle` 返回 182,593 字符，`capture_browser_scenario` 返回 1,033,240 字符，都超过单次响应上限，被 Claude Code 自动存到：

```
.claude/projects/.../tool-results/mcp-rea-<tool>-<ts>.txt
```

这不是 REA 的导出机制，是**传输层截断的副作用**。处理办法：用 `node -e` 读文件做结构化查询（只取需要的字段），不要试图整份读进上下文。

**坑 3：`jq` 没装。** 落盘提示推荐用 `jq` 查询，但这台机器 `jq: command not found`。改用 `node -e` + `JSON.parse`。**注意 shell 转义**——在 bash 双引号里写正则的 `$`、`{}` 会被吃掉，第一次提取路由时正则匹配到 0 条就是这个原因，改用 `includes()` / `endsWith()` 才成功。

**坑 4：`detail: "summary"` 不落盘。** `analyze_javascript_application` 用 summary 模式时，完整 Evidence **只存在 REA 进程内存**（key 是 `ev_9d1c7908…`），磁盘上没有。要留档必须显式调 `export_evidence_bundle`。本次没导，所以那份 Evidence 随会话结束就没了——**这是个教训**。

### 1.5 观测边界（贯穿全文）

必须说清楚这份报告**没做什么**：

- ❌ **未执行任何页面 JS** —— REA 全程被动，所有「行为」结论都是静态推断
- ❌ **未登录、未点击、未提交表单**
- ❌ **未抓脚本源码** —— `script_sources` 需显式授权，且 278 个 chunk 体积过大
- ❌ **未做认证绕过 / 注入 / 越权测试** —— 安全部分只做了「发一个带 `Origin` 头的普通请求读响应头」这种非侵入检查
- ❌ **未分析控制台内部页面** —— `/intellisense/*` 需登录，只分析了公开首页
- ⚠️ **首轮网络明细为 0** —— REA 在页面加载完成后才 attach，之前的流量不可回溯；网络数据来自第二轮从零启动的捕获

**性能数字的性质**：核心 7 个文件是**精确实测**；278 个路由 chunk 是 **24 个抽样外推**，误差可能 ±30%。**不是** LCP/TTI 等真实用户指标。

---

## 第二章 站点概览

**这是一个营销落地页，不是控制台本体。**

页面结构是「产品介绍 + 行业案例 + 数据背书 + 页脚协议」，**没有登录表单、没有侧边菜单、没有数据表格**。真正的控制台在 `/home`、`/intellisense/*` 等路径下，首页只负责引流。

页脚可见的合规信息：

| 项 | 值 |
|---|---|
| 标题 | 海康威视AI开放平台 |
| 备案 | 浙ICP备05007700号 |
| 公安备案 | 浙公网安备 33010802004037号 |
| 版权 | ©2026 杭州海康威视数字技术股份有限公司 |

**首页文案要点**（从可访问性树抽取）：

- 主标语：「基于海康观澜大模型，开发场景化的智能算法，支持云边端多种部署方式。」
- 双 Tab：**算法生产** / **设备开放平台**
- 三大能力：
  - **开放能力** —— 典型应用模型覆盖 9 大行业、上传图片即可在线验证效果
  - **一站式训练平台** —— 一站式/零门槛/高精度、覆盖图片视频音频、10 类模型（物体检测/混合/图像分类/OCR/图像比对/检索比对/分割/音频分类/关键词识别/视频分类）
  - **算法应用编排平台** —— 0 代码可视化算法编排
- 行业覆盖 8 个：数字能源、医疗卫生、数字乡村、智慧金融、智慧交通、工商企业、住宅建筑
- 数据背书：**120** 落地行业 · **75000** 落地项目 · **46000** 注册用户

---

## 第三章 技术栈

| 层 | 结论 | 置信度 | 依据 |
|---|---|---|---|
| 框架 | **Vue 2.7.16** | ✅ 确证 | `mf-manifest.json` 的 `shared` 字段显式声明 `vue@2.7.16` |
| 构建 | **Webpack**（Vue CLI 风格） | 观测 | `chunk-vendors.*.js` + 278 个 `chunk-<hash>.*.js` |
| 微前端 | **Module Federation 2.0** | 观测 | 入口是 `mf-manifest.json` 而非 `remoteEntry.js` → `@module-federation/enhanced` |
| UI 库 | HUI（海康自研）+ `aiop-ui@1.2.20` | ✅ 确证 | `/huiRewrite.css`；manifest 声明 |
| 错误监控 | Sentry 7.114.0 | 观测 | `sentry.javascript.vue/7.114.0` |
| 媒体 | 阿里云 OSS 杭州 | 观测 | `oss-cn-hangzhou.aliyuncs.com` |
| 视频 | WASM 播放器 + bideo.js | 观测 | `wasmplayer.min.js` version `0801000D` buildDate `20260513` |
| 服务端 | openresty | 观测 | `Server: openresty` |

**关于 Vue 版本**：第一轮我从 `__ob__` 观察者标记和 Sentry 的 vue 集成**推断**是 Vue 2。第二轮拿到 `mf-manifest.json` 后**确证**为 `2.7.16` —— 2.7 是 Vue 2 的最后一个特性版本（backport 了 Composition API）。

---

## 第四章 微前端架构（联邦拓扑）

这是本次分析**最有价值**的部分。

### 4.1 入口不是 remoteEntry.js

按 MF1 的惯例探测 `remoteEntry.js`，四个路径全 404。从宿主 bundle（605KB）里搜 `remoteEntry` / `remotes` / `__federation`，**零命中**。

最后是在**从 t=0 抓的全量请求清单**里找到的：

```
/ai-layout/static/aiop-base-tmp/aiop-base@1.0.0/mf-manifest.json?t=1792171829192
/ai-layout/static/aiop-intelligent-assistant/aiop-intelligent-assistant@1.0.0/mf-manifest.json?t=1792171827608
```

**`mf-manifest.json` 是 Module Federation 2.0 的标志。** 这条线索只有在「从头抓全量请求」时才看得见 —— 这正是 1.2 里坚持自起浏览器的回报。

### 4.2 完整拓扑

```
https://ai.hikvision.com/ai-layout/static/
├── aiop-base-tmp/aiop-base@1.0.0/
│     ├── mf-manifest.json                       ← 联邦清单
│     └── static/js/baseProvider.073b3273.js     ← remoteEntry (type: global)
│
└── aiop-intelligent-assistant/aiop-intelligent-assistant@1.0.0/
      ├── mf-manifest.json
      └── static/js/intelligentAssistantProvider.0197ec07.js
```

**`aiop-base`** — 基础能力层，`id: baseProvider`，暴露 **43 个模块**：

| 类别 | 模块 |
|---|---|
| **UI 组件（33）** | AiopCard · AiopTabs · AiopTag · AiopTagFilter / MultiLevel / TwoLevel · AiopMenu · AiopPopover · AiopPrompt · AiopLoading · AiopMark · AiopEmpty · AiopTransfer · AiopScrollbar · AiopSlicksort · AiopCascadeSelect · AiopCheckboxButton · AiopCheckMask · AiopDataTimeGroup · AiopDefaultProcess · AiopFilterGroup · AiopFreeDialog · AiopHangButton · AiopLayout · AiopRadioButton · AiopTips · AiopBread · AiopBatchButton · AiopAudio · AiopAdaptCardManage · AiopLayoutGraphGenerator · AiopSearchGroup |
| **基础设施（8）** | `Api` · `Axios` · `TaskManager` · `UploadTask` · `DownloadTask` · `LunchClient` · `APiCodeEnum` · `LayoutGraphGeneratorFun` |
| **异常（2）** | `NoAuthority` · `ErrorPage` |

**`aiop-intelligent-assistant`** — AI 助手层，`id: intelligentAssistantProvider`，暴露 **11 个模块**：

```
IntelligentAssistantSideBar            侧边栏形态
IntelligentAssistantChatArea           对话区
IntelligentAssistantChat               对话核心
IntelligentAssistantDialog             弹窗形态
IntelligentAssistantPage               整页形态
IntelligentAssistantLayoutCard         编排卡片
IntelligentAssistantLayoutCardHiklink  编排卡片（海康链接变体）
IntelligentAssistantPdfExcelPreview    PDF/Excel 预览
HikIntelligentAssistantPage
QuestionSourcesList                    引用来源列表
FeedbackDialogPage                     反馈弹窗
```

**解读**：这个 AI 助手不是「一个聊天框」，而是**完整的对话产品**——三种挂载形态（侧边栏/整页/弹窗）、引用来源展示（RAG 特征）、文档预览、反馈收集。而且它**独立部署**，主站发版不带它。

### 4.3 ⚠️ 联邦配置缺陷：`aiop-ui` 重复加载

对比两个模块的 `shared` 声明：

| 模块 | 声明的 shared |
|---|---|
| `aiop-base` | `aiop-ui@1.2.20`、`vue@2.7.16` |
| `aiop-intelligent-assistant` | **只有 `vue@2.7.16`** |

助手模块**没有把 `aiop-ui` 声明为共享**，于是自己打包了一份。实测确认：

```
aiop-base/static/js/async/aiop-ui.ae9e33e2.js           2,805 KB (gzip)  / 5,365 KB (raw)
aiop-assistant/static/js/aiop-ui.1a2a1284.js             2,706 KB (gzip)  / 5,093 KB (raw)
                                                        ─────────────
                                          同一套 UI 库传了两遍 ≈ 5.5 MB
```

`vue` 是配对成功的（两边都声明 2.7.16，只加载一份）—— 说明团队**知道**要配 shared，只是 `aiop-ui` 漏了。

**这是本次分析里最具体、最可修的一个问题。**

### 4.4 冗余请求

`aiop-base` 的 manifest 在 12 秒内被请求 **5 次**，每次带不同时间戳绕缓存：

```
?t=1792171829192
?t=1792171829193      ← 只差 1ms
?t=1792171829194
?t=1792171829339
?t=1792171829452
```

时间戳只差 1ms 说明是**并发重复拉取**——多个消费者同时初始化，没做去重。文件本身小，但属于初始化竞态。

---

## 第五章 路由与控制台路径

从 499 万 AST 节点中静态提取出 **45 条唯一路由**。

### 控制台本体

```
/home                       控制台首页
/intellisense/ai-layout/    AI 算法编排   ← 对应 aiop-base 的 LayoutGraphGenerator
/intellisense/ai-training/  AI 模型训练
```

`/intellisense/*` 就是首页「算法生产」Tab 背后的真实模块。

### 业务模块

```
开放能力   /open-ability
          /open-ability/multimodal-batch-verify[/create|/result]   多模态批量验证
          /open-ability/domain-case-detail/:id

资源中心   /resource-center/document-center
          /resource-center/document-detail/:uuid
          /resource-center/document-platform/:uuid?
          /resource-center/document-search
          /resource-center/download-center
          /resource-center/video-center

行业方案   /vertical/customer-case-search
          /vertical/customer-case/:uuid
          /vertical/resolution-search
          /vertical/resolution-detail/:uuid

合作伙伴   /partner/list · /partner/detail/:uuid · /partner/join/:status · /partner/success
          /partner-consultation/ · /provider-submit/

商城      /ai-market/ · /goods-list/ · /goods-detail/ · /shop-detail/

其他      /aiPilot/ · /labpilotAi/ · /heop · /duty/ · /demo-try · /hefei · /service-agreement
错误      /error/403 · /error/404 · /error/:type
```

`/aiPilot/`、`/labpilotAi/`、`/heop` 看起来是**其他产品线**挂载在同一 SPA 下。

### API 基址

从脚本中提取到的编排平台 API 根：

```
/api/saas/ai-layout/saas-algorithm-layout/v1/algorithm/applications
```

即 `/api/saas/ai-layout/saas-algorithm-layout/v1/` 是编排平台的服务端入口。

---

## 第六章 页面与组件结构

### DOM 规模

| 指标 | 值 |
|---|---|
| DOM 节点 | 2514 |
| 元素节点 | 1912 |
| **Vue scoped 作用域** | **19 个**（≈19 个组件） |
| 可访问性节点 | 737 |
| 标签分布 | `div` 970 · `link` 536 · `span` 183 · `img` 79 · `button` 25 · `h1` 5 |

`div` 占绝对多数，典型的 Vue SPA + scoped CSS 布局。

### 组件区块

| 作用域 | 节点数 | 对应区块 |
|---|---|---|
| `data-v-64f28d36` | 347 | 主容器/布局 |
| `data-v-45ac55d2` | 309 | 主容器/布局 |
| `data-v-13baf33a` | 141 | 行业应用 |
| `data-v-5372c12c` | 130 | 一站式训练平台 |
| `data-v-8bff4d94` | 71 | 开放能力（4 张能力卡） |
| `data-v-6cdebb14` | 46 | 顶部导航 |
| `data-v-6b161a9f` | 35 | 算法生产 / 设备开放平台 切换 |
| `data-v-1afce936` | 18 | 合作伙伴 logo 墙 |

### DOM 骨架

```
body
└─ #app (data-v-2f99d6b9)
   ├─ 顶栏 (data-v-6cdebb14)   logo + 5 项导航 + 咨询入口
   ├─ 主区 (data-v-b6824382)
   │   ├─ Tab 切换 (data-v-6b161a9f)   算法生产 | 设备开放平台
   │   ├─ 开放能力 (data-v-8bff4d94)   4 张卡片
   │   ├─ 训练平台 (data-v-5372c12c)
   │   ├─ 行业应用 (data-v-13baf33a)   8 个行业 + 3 个数据指标
   │   ├─ 合作伙伴 (data-v-1afce936)   6 个 logo
   │   └─ 底部 CTA (data-v-cda37288 / data-v-b73bfa92)
   └─ 页脚 (data-v-568943e7)
```

**特殊元素**：
- `VIDEO ×2`（`autoplay muted loop`）—— 背景视频，`SOURCE` 指向 OSS 上的 `.webm`
- `OBJECT ×1`（`aria-hidden`）—— WASM 播放器挂载点

---

## 第七章 数据流与接口

### 配置驱动的门户

首页内容**全部由后端配置驱动**：

```
POST /api/ai-portal/portal/v1/config-management/system-config/query     ← 系统配置
POST /api/ai-portal/portal/v1/config-management/menu-config/query       ← 菜单结构
POST /api/ai-portal/portal/v1/config-management/home-page-config/query  ← 首页布局
POST /api/ai-portal/portal/v1/config-module/query                       ← 模块清单
POST /api/ai-portal/portal/v1/operate/buried-point                      ← 埋点上报
GET  /configfiles/json/aiop-console/intelligent/{ability,training}      ← 静态 JSON
GET  /configfiles/json/aiop-console/default/web.sample-image
GET  /static/i18n/zh_CN/index.json                                      ← 国际化
```

前四个返回 **200**，**无需登录**。

**这套模式的意义**：首页没有硬编码内容。换一批行业案例、调一次数据指标，改后端配置即可，不用发前端版本。这是企业级门户的标准做法。

### 客户端存储

| 位置 | 键 | 推测用途 |
|---|---|---|
| localStorage | `isCheck` | 协议勾选状态 |
| sessionStorage | `sentryReplaySession` | Sentry 会话回放 |
| sessionStorage | `actionInfo` | 行为埋点 |

**用量 0 字节**，无 IndexedDB、无 Cache Storage、无 Cookie。前端几乎不存业务数据。

---

## 第八章 性能分析

### 实测数据（冷启动，全新 profile）

| 指标 | 实测值 |
|---|---|
| 请求总数 | **653** |
| JS 文件 | **278 个 `chunk-*.js`** + 38 个联邦/入口脚本 |
| CSS | 11 |
| 图片 | 59 |
| 首屏 HTML | 37 KB → **7.7 KB**（gzip） |
| 观测时长 | 12 秒内完成 653 请求 |

### 体积明细（gzip 传输）

| 文件 | gzip | 未压缩 |
|---|---|---|
| `chunk-vendors.3dc6ac88.js` | **3,599 KB** | **7,646 KB** |
| `aiop-ui.ae9e33e2.js`（base） | 2,805 KB | 5,365 KB |
| `aiop-ui.1a2a1284.js`（assistant） | 2,706 KB | 5,093 KB |
| `vendors.2d156af1.js`（assistant） | 1,462 KB | 4,295 KB |
| `vendors.5a7c9944.js`（base） | 381 KB | 1,153 KB |
| `wasmplayer.min.js` | 388 KB | 2,024 KB |
| `index.e1ddf689.js` | 156 KB | 590 KB |
| **小计（7 个文件）** | **11.2 MB** | **26.1 MB** |
| 278 个路由 chunk（抽样外推） | ~2.5–4 MB | — |
| **首页估计总量** | **~14–15 MB** | **~28 MB+** |

### 问题清单

1. **`aiop-ui` 重复加载 5.5 MB** —— 见 4.3，联邦 `shared` 漏配。

2. **`chunk-vendors.js` 7.6 MB 未压缩** —— 全站最大单体文件。未拆分、未按需加载。**一个营销落地页不该拉 7.6MB 的 vendor 包。**

3. **278 个 chunk** —— 按路由切碎本身不是错，但**首页就触发 278 个 chunk 加载**说明 prefetch 策略过于激进。

4. **不支持 Brotli** —— 只开 gzip。实测发 `Accept-Encoding: br` 时服务端**返回未压缩内容**（605 KB 原样传）。Brotli 相比 gzip 通常再省 15–20%，对 7.6MB 的文件就是 1MB+ 的差距。

5. **HTTP/2 已启用**（ALPN 协商 `h2` 确认）—— ✅ 这条是好的，多路复用缓解了 653 请求的队头阻塞。但 TLS 只到 **1.2**，未开 1.3。

6. **`mf-manifest.json` 重复请求 5 次** —— 见 4.4。

7. **静态资源缓存策略正确** —— ✅ `Cache-Control: public, max-age=2592000`（30 天）+ ETag + 哈希文件名。

---

## 第九章 安全分析

### 🔴 9.1 CORS 反射任意 Origin + 允许凭证

实测（带外部 Origin 的普通 POST）：

```http
POST /api/ai-portal/portal/v1/config-module/query
Origin: https://evil.example.com

→ 200 OK
Access-Control-Allow-Origin: https://evil.example.com     ← 反射了任意源
Access-Control-Allow-Credentials: true                     ← 允许携带凭证
Access-Control-Allow-Methods: GET, POST, OPTIONS, HEAD, PUT, PATCH
Access-Control-Allow-Headers: Origin, x-csrftoken, API-Key, X-Requested-With,
                              Content-Type, accept, token, type
```

预检 `OPTIONS` 同样反射（204）。**同时缺少 `Vary: Origin`** —— 中间缓存可能把带错误 ACAO 的响应复用给其他源。

**实际影响要客观说**：

- 页面**没有任何 `Set-Cookie`**，且 `Allow-Headers` 里列的是 `token` —— 认证走的是 **Header Token，不是 Cookie**
- 这种情况下恶意站点无法自动携带受害者凭证（token 在 localStorage，受同源策略保护），**实际可利用性大幅降低**
- **但只要系统里任何一处改用 Cookie 会话，这条立刻变成完整的跨站账户接管**

**定性：这是一个必须修的配置缺陷，但当前不是已被利用的漏洞。**
修法：白名单校验 Origin，或直接去掉 `Allow-Credentials`（既然用 token 认证，本就不需要）。

### 🟠 9.2 完全缺失安全响应头

所有响应（HTML / JS / API）都**没有**：

| 缺失的头 | 后果 |
|---|---|
| `Strict-Transport-Security` | 无 HSTS，首次访问可被 SSL 剥离 |
| `Content-Security-Policy` | 无 XSS 缓解纵深；对一个加载 278 个脚本、含 3 个第三方域的 SPA 尤其危险 |
| `X-Frame-Options` / `frame-ancestors` | 可被任意站点 iframe 嵌套 → 点击劫持 |
| `X-Content-Type-Options: nosniff` | MIME 嗅探风险 |
| `Referrer-Policy` | Referrer 可能泄露到第三方 |
| `Permissions-Policy` | 摄像头/麦克风/地理位置权限无约束 |

### 🟠 9.3 速率限制配置对外暴露

```http
X-RateLimit-Remaining: 499
X-RateLimit-Requested-Tokens: 1
X-RateLimit-Burst-Capacity: 500
X-RateLimit-Replenish-Rate: 500
```

限流本身是好事（500 burst / 500 replenish），但把**容量和补充速率**完整回显，等于告诉攻击者可以打多快。应去掉这几个头。

### 🟡 9.4 生产环境残留调试日志

console 里 17 条 `log`，包括：

```
routes                     ← 打印了整个路由表
{userId: , userName: }     ← 用户对象
true 123456 true           ← 疑似硬编码测试值
整理数据
Report successfully
```

`true 123456 true` 尤其可疑 —— `123456` 出现在生产 console 里。虽然只在客户端、不构成漏洞，但属于该清理的。

### 🟡 9.5 Vue 运行时告警

```
[Vue warn]: Error in callback for immediate watcher "":
TypeError: Failed to execute 'removeChild' on 'Node': parameter 1 is not of type 'Node'.
```

`immediate` watcher 里操作了已被移除的 DOM 节点。典型的组件销毁时序问题 —— 异步回调回来时组件已卸载。

### 🟢 9.6 做得对的部分

- **TLS 证书有效**：GlobalSign OV，`CN=ai.hikvision.com`，验证通过
- **加密套件合理**：`ECDHE-RSA-AES128-GCM-SHA256`（前向保密）
- **无 Cookie 暴露**：公开页面零 `Set-Cookie`
- **存储极简**：只存协议勾选 + 监控/埋点状态
- **静态资源哈希命名 + 30 天缓存**，供应链完整性基本可控

### 汇总

| 严重度 | 问题 | 可修 |
|---|---|---|
| 🔴 高 | CORS 反射任意 Origin + `Allow-Credentials: true` | ✅ 加 Origin 白名单 |
| 🟠 中 | 缺全部安全响应头（HSTS/CSP/XFO/nosniff/Referrer） | ✅ 网关层统一加 |
| 🟠 中 | 限流参数对外暴露 | ✅ 去掉响应头 |
| 🟡 低 | 仅 TLS 1.2，未开 1.3 | ✅ |
| 🟡 低 | 生产 console 残留 `true 123456 true` | ✅ 清理 |
| 🟡 低 | Vue `removeChild` 运行时告警 | ✅ 修 watcher 时序 |

---

## 第十章 无障碍与语义结构分析 【补充】

> 本章为补充分析之一，数据来自 737 个可访问性节点。

### 10.1 做得好的地方

这个站点的语义化程度**高于同类营销页的平均水平**：

| 结构 | 观测 |
|---|---|
| Tab 组件 | `tablist` → `tab "算法生产" [selected]` / `tab "设备开放平台"` → `tabpanel "算法生产"` —— **ARIA 角色完整** |
| 导航 | `list` → `listitem` ×5，语义正确 |
| 内容图 | `image "安全帽佩戴识别"`、`image "物体检测模型"`、`image "煤矿安全管理算法包"` —— **有意义的 alt** |
| 页脚链接 | `link "浙ICP备05007700号"`、`link "浙公网安备 33010802004037号"` —— 备案号可访问 |
| 状态提示 | `role="status"` 用于动态状态 |

Tab 那块尤其值得肯定 —— 手写 tab 组件最容易漏 `role="tab"` / `aria-selected` / `tabpanel` 三件套，这里配齐了。

### 10.2 发现的问题

**问题 1：WASM 播放器对读屏完全隐藏**

```
OBJECT [aria-hidden]   ← 整块内容被无障碍树忽略
```

`OBJECT` 元素带 `aria-hidden`，无障碍树里直接跳过。如果这个播放器承载的是**内容**（演示视频）而不是纯装饰，读屏用户会完全不知道它的存在。需要判断：是装饰背景（`aria-hidden` 正确）还是内容（应该给替代文本）。

**问题 2：顶部导航 5 个按钮无可访问名称**

```
• list
  • listitem
    • button [focusable=true]     ← 没有 name
  • listitem
    • button [focusable=true]     ← 没有 name
  ...（共 5 个）
```

5 个导航按钮在无障碍树里**全部只有 `button` 角色、没有可访问名称**。读屏会读成「按钮 按钮 按钮 按钮 按钮」。这是**最严重的一处无障碍缺陷** —— 键盘/读屏用户无法知道每个按钮是什么。

**问题 3：装饰图使用描述性 alt**

`image "描述图标"` 反复出现多次。装饰性图片应该用 **`alt=""`**（空 alt，让读屏跳过），而不是填一个描述性文字 —— 否则读屏会反复播报「描述图标」，制造噪音。

**问题 4：数据指标数字与标签分离**

```
• generic
  • generic
    • StaticText "120"          ← 数字
  • generic
    • StaticText "落地行业"      ← 标签
```

「120」和「落地行业」是两个独立文本节点，中间没有语义关联。读屏会先读孤立的「120」，再读「落地行业」，**丢失了数字与标签的绑定关系**。正确做法是用 `aria-label="120 落地行业"` 或把两者放进同一语义单元。

**问题 5：空的文本节点**

页脚存在多个 `StaticText ""`（空内容）。虽然无害，但属于模板渲染残留。

### 10.3 无障碍缺陷汇总

| 严重度 | 问题 | 影响 |
|---|---|---|
| 🔴 高 | 导航 5 个按钮无可访问名称 | 读屏用户无法识别导航目标 |
| 🟠 中 | WASM 播放器 `aria-hidden` | 内容视频对读屏不可见 |
| 🟡 低 | 装饰图用「描述图标」而非 `alt=""` | 读屏噪音 |
| 🟡 低 | 数据数字与标签语义分离 | 读屏丢失绑定 |
| 🟡 低 | 空文本节点残留 | 无实际影响 |

**参照点**：同类企业官网里，Tab 的 ARIA 完整性属于中上水平，但**导航按钮无名**这种基础缺陷出现在生产站点上，说明**没有把无障碍纳入发布检查**。

---

## 第十一章 第三方依赖与信任边界 【补充】

> 本章为补充分析之二，梳理页面把信任交给了哪些外部方。

### 11.1 第三方域名清单

页面加载过程中触及的**非 hikvision.com 域名**：

| 域名 | 用途 | 信任级别 |
|---|---|---|
| `sentry.hpcbase.com` | 错误监控 + 会话回放 | ⚠️ 第三方 |
| `ff0be01e-hri-aiop-train-product.oss-cn-hangzhou.aliyuncs.com` | 图片/视频（生产） | 阿里云 OSS |
| `ff0be01e-hri-aiop-train-develop.oss-cn-hangzhou.aliyuncs.com` | 图片（**开发环境**） | ⚠️ 见 11.3 |

**注意 `hpcbase.com`** —— 监控域**不是** hikvision.com。这意味着：

- 用户行为数据（含会话回放）流向一个独立域
- 该域的可用性/安全性直接影响站点（脚本阻塞会拖慢加载）
- 需要在 CSP 里显式放行（但站点**根本没有 CSP**）

### 11.2 Sentry 的配置暴露

```
POST https://sentry.hpcbase.com/api/29/envelope/?
     sentry_key=6ec784713699242a776b0c72875b8fdf
     &sentry_version=7
     &sentry_client=sentry.javascript.vue%2F7.114.0
```

- `sentry_key` **明文写在 URL 里**（DSN 的标准做法，但意味着 key 完全公开）
- `sessionStorage.sentryReplaySession` 的存在说明**开启了 Session Replay** —— 会录制用户操作序列

Session Replay 对企业站点是双刃剑：排查问题有效，但**录制内容可能包含用户输入**。正规做法是配 `maskAllText` / `blockAllMedia`，并且必须在隐私政策里披露。

### 11.3 ⚠️ 生产页面加载开发环境资源

首页请求里出现了 **7 张来自 `-develop` bucket 的图片**：

```
ff0be01e-hri-aiop-train-develop.oss-cn-hangzhou.aliyuncs.com/img/736f27a80333464ca5a9a1ca4674321f.png
ff0be01e-hri-aiop-train-develop.oss-cn-hangzhou.aliyuncs.com/img/d336a61423e34627b09aac479ae6c8c4.png
ff0be01e-hri-aiop-train-develop.oss-cn-hangzhou.aliyuncs.com/img/d05e573da9e74df3b39a39636b55afff.png
ff0be01e-hri-aiop-train-develop.oss-cn-hangzhou.aliyuncs.com/img/65a384ad7e8d4840aa23b35010aeed41.png
ff0be01e-hri-aiop-train-develop.oss-cn-hangzhou.aliyuncs.com/img/99b91875adb14f48913824bfe5d86de3.png
ff0be01e-hri-aiop-train-develop.oss-cn-hangzhou.aliyuncs.com/img/72c9ee5faec541d4860fc7bc91284fae.png
ff0be01e-hri-aiop-train-develop.oss-cn-hangzhou.aliyuncs.com/img/3d35b857be7c4f73bf94e8291b27f151.png
```

**生产环境的首页，从开发 bucket 取图。** 结合第七章「首页由后端配置驱动」—— 说明**开发环境的图片 URL 被写进了生产环境的配置数据**。

风险：
- 开发 bucket 通常权限更松、生命周期策略更随意（可能被清理）
- 开发资源可能随时被替换/删除，导致生产页面图片 404
- 如果 develop bucket 的 ACL 是公开读，等于把开发素材暴露出去

### 11.4 信任边界总结

```
用户浏览器
  ├─ ai.hikvision.com          ← 主体
  │    ├─ /api/ai-portal/*     ← 第一方 API（token 认证）
  │    └─ /configfiles/*       ← 第一方静态配置
  ├─ hpcbase.com               ← 第三方：错误监控 + 会话回放
  ├─ aliyuncs.com (product)    ← 阿里云 OSS：媒体
  └─ aliyuncs.com (develop)    ← ⚠️ 开发环境资源混入生产
```

**一个健康的信任边界应该是**：第一方域名承载业务，第三方域名最小化且全部在 CSP 白名单里。这个站点的实际情况是：**第三方域存在、混入开发环境资源、且没有 CSP 来约束任何一方**。

---

## 第十二章 结论与可复用模式

### 12.1 这个站点的架构画像

一个**成熟的企业级 AI 平台门户**：Vue 2.7 SPA + Module Federation 2.0 微前端 + 配置驱动内容 + 独立部署的 AI 助手模块。架构选型是**对的**，工程质量在**中上**，但有明确的**性能与安全欠账**。

### 12.2 三个最该修的问题

| # | 问题 | 代价 | 修法 |
|---|---|---|---|
| 1 | `aiop-ui` 联邦 shared 漏配 | 每次访问多传 **5.5 MB** | 在助手模块的 `shared` 里加 `aiop-ui`，配 `singleton: true` |
| 2 | CORS 反射任意 Origin | 配置缺陷，当前 token 认证下未直接可利用 | Origin 白名单，或去掉 `Allow-Credentials` |
| 3 | 零安全响应头 | 无 XSS 纵深、可被 iframe | 网关层统一注入 CSP/HSTS/XFO/nosniff |

### 12.3 值得学的三个模式

**模式 1：AI 助手作为独立联邦模块**

助手暴露 11 个组件（侧边栏/整页/弹窗三种形态 + 引用来源 + 文档预览 + 反馈），独立部署。做 LLM 应用时，对话界面迭代频率远高于主站 —— 用微前端隔离，或至少独立路由 + 独立部署，避免每次调 prompt 都要全站发版。

**模式 2：配置驱动的门户**

菜单、首页布局、系统配置全走 `/query` 接口。运营能自己改首页，不用排前端需求。这是企业级平台的标配。

**模式 3：统一请求层显式 expose**

`Api` / `Axios` / `LunchClient` / `TaskManager` / `UploadTask` / `DownloadTask` 全部由基础层暴露给业务模块。多个微前端共用一套鉴权、重试、错误处理、任务管理，而不是各写各的。

**可以照抄的 RAG 对话组件清单**（来自 `aiop-intelligent-assistant` 的 exposes）：

```
SideBar / ChatArea / Chat / Dialog / Page      ← 多形态挂载
QuestionSourcesList                            ← 引用来源
PdfExcelPreview                                ← 文档预览
FeedbackDialogPage                             ← 反馈收集
```

这是一份完整的 RAG 对话产品模块划分，直接可以拿来当自己项目的组件设计起点。

### 12.4 REA 使用心得

**REA 适合什么**：已部署的 SPA/Electron/原生应用的**结构侦察** —— 拿不到源码时看清架构、路由、依赖、联邦拓扑。

**REA 不适合什么**：真实性能指标（LCP/TTI）、运行时行为（它不执行 JS）、需要认证的内部页面。

**这次最大的收获**：**从 t=0 抓全量请求**才能看见运行时注入的东西。`mf-manifest.json` 在静态分析、宿主 bundle 搜索里**全部零命中**，只有全量请求清单里才现形。所以做这类分析时，**「自己起浏览器 + 从零开始捕获」比「attach 到已加载的页面」信息量大一个数量级**。

**一个操作教训**：REA 的 `detail: "summary"` 模式**不落盘**，完整 Evidence 只在进程内存里。要留档必须显式 `export_evidence_bundle`。

---

## 附录 观测边界与未知

### 已确证（有直接证据）

- 联邦拓扑、manifest 内容、43+11 个 expose 列表、`vue@2.7.16` / `aiop-ui@1.2.20`
- 45 条路由、API 基址
- 文件体积、请求数、chunk 数
- 响应头、CORS 行为、TLS 协商、压缩协商
- DOM 规模、组件数、无障碍树结构

### 推断（有间接证据）

- 「营销落地页而非控制台」—— 基于页面结构判断
- 「`aiop-ui` 重复加载」—— 基于两个不同哈希文件 + manifest shared 声明差异
- 「生产配置混入开发资源」—— 基于 URL 中的 `-develop` 标识

### 未观测

- 控制台内部页面（`/intellisense/*` 需登录）
- 278 个 chunk 的业务逻辑
- 真实性能指标（LCP / TTI / TBT）
- API 请求/响应体结构
- 联邦 `remoteEntry` 的运行时加载时序
- CSP 的实际部署情况（站点没有，所以无法验证「如果有会是什么」）

### 数据可靠性说明

- **精确**：核心 7 个文件的体积（逐个 curl 实测）
- **外推**：278 个路由 chunk 的体积（24 个抽样，误差可能 ±30%）
- **单次观测**：所有数字来自单次冷启动，未做多次取均值

---

## 参考资料

- REA 官方文档：`https://github.com/morluto/rea`
- Module Federation 2.0：`https://module-federation.io/`
- 本地证据留存：`rea/manifests/aiop-base.json`、`rea/manifests/aiop-assistant.json`

---

*分析日期：2026-10-17 ｜ 方法：REA 被动观测 + curl/openssl 实测 ｜ 全程未执行目标页面 JS、未登录、未做侵入性测试*
