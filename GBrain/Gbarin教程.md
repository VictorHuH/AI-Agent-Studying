好，我先看看 gbrain 的内置帮助和主要命令结构，给你整理一份实用的。以下是 **GBrain 简易使用教程** 🐱

---

## 1️⃣ 什么是 GBrain？

GBrain = 本地知识大脑。把所有文档、笔记、代码放进一个 AI 可搜索的数据库里，然后可以用自然语言问答、自动维护、跟 Claude Code 等 AI 工具对接。

当前版本：`v0.42.53.0`，默认 **PGLite**（本地 SQLite 风格，无需装 PostgreSQL）。

---

## 2️⃣ 快速开始

### 初始化（创建大脑）
```bash
# 本地轻量模式（默认，无需数据库服务器）
gbrain init --pglite

# 或者用 Supabase（云数据库）
gbrain init --supabase

# 或者用已有的 PostgreSQL
gbrain init --url postgresql://user:pass@host/db
```

**目前还没初始化**，建议先跑 `gbrain init --pglite` 试试。

### 健康检查
```bash
gbrain doctor
```
刚刚跑过，65/100 是因为空 brain + 没设 ZeroEntropy API key，属于正常状态。

---

## 3️⃣ 内容管理

### 写入页面
```bash
# 直接输入内容
gbrain put my-first-note <<< "# Hello GBrain\n这是我的第一条笔记"

# 从文件写入
cat note.md | gbrain put note-slug

# 指定类型、标签
gbrain put my-slug --type note --tag "ai,学习"
```

### 读取页面
```bash
gbrain get my-slug           # 查看内容
gbrain list                  # 列出所有页面
gbrain list --type note -n 20  # 只列笔记，最多20条
gbrain list --tag "ai"       # 按标签过滤
```

### 删除
```bash
gbrain delete my-slug
```

---

## 4️⃣ 搜索与问答

GBrain 是知识库的灵魂就在搜索：

```bash
# 关键词搜索（全文检索）
gbrain search "机器学习基础"

# 语义搜索（需要先跑 embedding）
gbrain query "transformer 和 RNN 有什么区别"

# 自然语言问答（推荐）
gbrain ask "我的笔记里关于 Docker 部署的内容有哪些？"
```

> ⚠️ **先跑嵌入**：搜索前需要 `gbrain embed --stale` 生成向量嵌入，不然语义搜索用不了。

---

## 5️⃣ 批量导入

把整个 Markdown 目录喂进大脑：

```bash
gbrain import ./my-notes/        # 导入目录，自动处理
gbrain import ./my-notes/ --no-embed  # 导入但不马上生成嵌入
```

跟 Git 仓库同步：
```bash
gbrain sync --repo ./docs-repo   # 增量同步
gbrain sync --watch              # 持续监听变化
```

---

## 6️⃣ 嵌入（Embedding）

嵌入是把文字变成向量的过程，搜得准不准靠它：

```bash
gbrain embed --stale        # 刷新所有未嵌入的内容
gbrain embed --all          # 强制全部重新嵌入
gbrain embed some-page      # 只嵌入单个页面
```

> 默认嵌入模型是 ZeroEntropy 的 `zembed-1`，需要设置 API key：
> ```bash
> export ZEROENTROPY_API_KEY="your-key-here"
> ```
> 或直接注册 zeroentropy.dev 免费获取。

---

## 7️⃣ 链接与图谱

像 Obsidian / Roam 一样的双向链接：

```bash
# 创建链接
gbrain link transformer-attention "Attention Is All You Need"

# 查看反向链接
gbrain backlinks attention-is-all-you-need

# 图谱遍历
gbrain graph attention-is-all-you-need --depth 3

# 标签
gbrain tag transformer-attention "deep-learning"
gbrain tags transformer-attention
```

---

## 8️⃣ 创意与思考

```bash
# 头脑风暴（bisociation 交叉联想）
gbrain brainstorm "如何结合区块链和 AI Agent？"

# LSD 模式（奖励反直觉想法）
gbrain lsd "未来十年的教育模式"
```

---

## 9️⃣ 对外服务（MCP）

让 Claude Code、Cline 等 AI 工具直接连上你的知识库：

```bash
# 启动 MCP 服务（stdio 模式，适合 Claude Code）
gbrain serve

# 启动 HTTP 服务（适合远程连接）
gbrain serve --http --port 8080

# 连接 Claude Code
gbrain connect http://localhost:8080 --token my-token --install
```

---

## 🔟 日常维护

```bash
gbrain doctor # 健康检查
gbrain stats # 数据统计
gbrain check-update # 检查更新
gbrain upgrade # 自动升级

# 自动维护 daemon
gbrain autopilot --interval 3600 # 每小时跑一次维护

# 一键夜间维护
gbrain dream # 嵌入、提取、整理一条龙
```

---

## 🎯 你的下一步推荐

| 步骤                 | 命令                             | 预计时间 |
| -------------------- | -------------------------------- | -------- |
| 1️⃣ 初始化大脑         | `gbrain init --pglite`           | 10秒     |
| 2️⃣ 导入笔记           | `gbrain import ./笔记目录/`      | 看量     |
| 3️⃣ 设 ZeroEntropy key | `export ZEROENTROPY_API_KEY=xxx` | 1分钟    |
| 4️⃣ 生成嵌入           | `gbrain embed --stale`           | 几分钟   |
| 5️⃣ 玩起来             | `gbrain ask "我写了什么"`        | 🎉        |

有具体想用的场景吗？比如导入 Obsidian 笔记库、连 Claude Code、或者当 RAG 知识库用——我可以给你更针对性的指导。