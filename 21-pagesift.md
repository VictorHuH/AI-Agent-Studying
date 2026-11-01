# pagesift（工程实践调研）

> 2026-11-01 调研完成。**非学习路线节点，是工作中实测的工具调研**，归入「工程实践补充」。
> 衔接 [[17-生产知识库实战]] / [[06-MCP]] / [[13-CLI]]：RAG 入库流水线最脏的第一段（抓取 → 解析 → 正文提取）被单独做成了服务，而且同一引擎同时供 CLI / HTTP / MCP 三种皮。
> 关键词：文档转 Markdown、Firecrawl 兼容、自托管、MCP、RAG 入库

---

## 核心认知

> **pagesift = 把「网页和各种文档洗成干净 Markdown」这条脏活独立成一个自托管引擎。** 一个 Rust 二进制，一套转换核心，外面套五层皮：CLI / Firecrawl 兼容 HTTP / Jina Reader 端点 / MCP Server / Python·Node SDK。它治的是 RAG 入库流水线里最难复用、最容易写崩的那一段。

---

## 一、问题：RAG 的第一公里全是脏活

| 症状 | 根因 |
|---|---|
| 网页抓回来一半是导航、广告、cookie 横幅 | HTML 没有"正文"这个概念，得靠启发式识别 |
| PDF 表格错行、页眉页脚混进正文、中文乱码 | PDF 只有排版指令，文字层要按结构树还原 |
| docx / xlsx / pptx / epub / csv 各写一套解析器 | 每种容器格式都要单独的库和边界处理 |
| 相对链接、发布日期、标题各站格式不同 | 元数据抽取没有统一标准 |
| 换个项目，上面全部重写一遍 | 这段代码和业务无关，却总被复制进业务代码 |

🎯 **本质：内容获取是「多格式异构 → 单一标准形态」的适配层，天然该独立成服务，不该长在业务代码里。** 这也是它同时提供 CLI / HTTP / MCP 的原因——写成服务之后，什么消费者都能接。

---

## 二、原理：一个转换核心，五层皮

| 皮 | 进程契约 | 谁在用 |
|---|---|---|
| CLI | 参数进、文本出、退出码报成败（[[13-CLI]] 三条契约） | 人、脚本、CI、Agent 的 Bash 工具 |
| HTTP（Firecrawl v1/v2） | `/v1` `/v2` 的 scrape / batch/scrape / crawl / map | 已有 Firecrawl 代码，改 `api_url` 即迁 |
| HTTP（Jina Reader） | `GET /r/<url>` 直接返回 Markdown | 只想"给我纯文本"的最短路径 |
| HTTP（文件） | `POST /v2/parse`，multipart 上传，≤50 MB | 本地 PDF / Office / EPUB / CSV |
| MCP | stdio 或 HTTP，5 个工具 | Claude Code 等 Host（[[06-MCP]]） |

五层皮共用同一套 Rust 核心：正文识别、Markdown 往返（标题/列表/表格/代码/公式）、发布日期抽取、`includeTags`/`excludeTags` 选择器。

**本地文档不走 MCP**：官方明确「MCP 不提供这个接口，文件不经 MCP 传」。原因是 MCP 工具的参数是 JSON，字节流塞不进去——这是协议形态的边界，不是功能缺失。所以文件类任务要么走 CLI（挂载目录），要么走 `/v2/parse`（上传）。**记住这条：MCP 管"我能访问到的资源"，管不了"我手里的文件"。**

---

## 三、怎么跑的：HTTP 优先，浏览器兜底

`engine: auto`（默认）先用纯 HTTP 抓，只有当 HTML 拿到的内容明显少于浏览器渲染结果时，才启动无头浏览器。Docker 镜像里自带 **lightpanda**（轻量无头浏览器），不用另装 Chrome。

其余工程约束：

- **礼貌爬取**：默认守 robots.txt，同主机请求最小间隔 1 秒、并发 2，遇 429/503 退避
- **SSRF 防护**：默认拒绝私有网段与回环地址（`--allow-cidr` 放行），防 DNS 重绑定
- **内存有界**：容量按 cgroup 内存上限自动确定，768 MiB 容器内不 OOM
- **不静默失真**：结果残缺时给 `partial_content` / `pages_missing` / `output_truncated` 警告，而不是返回半截内容假装成功

🔗 呼应已学：这套"能力有边界就说出来"的做法，和 [[18-REA逆向工程]] 的 Evidence 契约是同一种设计——**把不确定性做成输出的一部分**。

---

## 四、命令与模式（Windows 实测可用形态）

### 4.1 一次性转换（最常用，不需要常驻服务）

```bash
cd "文件所在目录"

MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/work" \
  ghcr.io/yolow92/pagesift:0.81.5 scrape "/work/你的文件.pdf" > 输出.md
```

`MSYS_NO_PATHCONV=1` 不能省（Git Bash 会把 `/work/x.pdf` 改写成 Windows 路径，报 `SSRF_BLOCKED: scheme 'd'`）。日志走 stderr，stdout 只有 Markdown，`>` 重定向干净。

### 4.2 常驻 HTTP 服务

```bash
docker run -d --name pagesift -p 127.0.0.1:3002:3002 \
  -e PAGESIFT_API_KEYS=sk-test -v pagesift-data:/data \
  ghcr.io/yolow92/pagesift:0.81.5
```

```bash
# Jina Reader 风格
curl -s http://127.0.0.1:3002/r/https://example.com -H 'Authorization: Bearer sk-test'

# 本地文件上传（返回 {"success":true,"data":{markdown,metadata}}）
curl -s http://127.0.0.1:3002/v2/parse -H 'Authorization: Bearer sk-test' \
  -F 'file=@简历.pdf' -F 'options={"formats":["markdown"]}'
```

`formats` 可选：`markdown` / `html` / `rawHtml` / `links` / `images`（**没有 `metadata`**，metadata 永远附带）。PDF 可加 `"parsers":[{"type":"pdf","pages":true}]` 拿每页 Markdown。

### 4.3 迁移已有 Firecrawl 代码

```python
from firecrawl import FirecrawlApp
app = FirecrawlApp(api_url="http://localhost:3002", api_key="sk-test")   # 只改这一行
app.scrape_url("https://example.com", params={"formats": ["markdown"]})
```

### 4.4 MCP

```bash
claude mcp add --scope user pagesift -- docker run -i --rm ghcr.io/yolow92/pagesift:0.81.5 mcp
```

工具：`pagesift_scrape` / `pagesift_batch_scrape` / `pagesift_crawl` / `pagesift_crawl_status` / `pagesift_map`。**只接 URL，不接文件。**

### 4.5 Node SDK（npm 有 Windows 预编译）

```javascript
const { Scraper } = require('@pagesift/node')
const s = new Scraper({ requestIntervalMs: 1000 })
const p = await s.scrape('https://example.com', { formats: ['markdown'] })
console.log(p.metadata.title, p.markdown)
await s.close()
```

与官方 README 不一致的两处（0.81.5 实测）：**没有顶层 `scrape` 导出**，要用 `new Scraper()`；**`formats` 不接受 `"metadata"`**，传了直接抛 `UNSUPPORTED_OPTION`。纯本地 HTML 可用 `convert(htmlString)` 同步转换，不需要网络。

---

## 五、实测：Windows 上到底哪条路能走通

### 5.1 安装路径实测

| 路径 | 结果 | 原因 |
|---|---|---|
| `pip install pagesift` | ❌ 失败 | PyPI **只有 sdist，没有 Windows wheel**，pip 转去下 Rust 工具链现场编译 |
| GitHub Release 二进制 | ❌ 无 Windows 版 | 只有 linux / macOS 的 tar.gz |
| `cargo install pagesift` | ❌ 未验证 | 本机无 Rust 工具链 |
| npm `@pagesift/node` | ✅ 可用 | 有 `win32-x64-msvc` 预编译 addon |
| Docker 镜像 | ✅ 最完整 | 自带 lightpanda 浏览器，CLI/HTTP/MCP 全通 |

**结论：Windows 上 Docker 是唯一"开箱可用"的形态**，Node SDK 是次选。

### 5.2 转换质量

| 用例 | 结果 |
|---|---|
| 2 页中文简历 PDF | ✅ 2309 字符 / 76 行，表格版式原样保留为 Markdown 表格 |
| `https://example.com` | ✅ 正文 + 多语言段落完整 |
| 本地 HTML 字符串（含 nav / script） | ✅ 导航和脚本被剔除，只留标题与正文 |

两个质量观察：

1. **表格式版面的简历会被还原成一张大表**——忠实，但对"喂给 LLM 做岗位匹配"不够友好。
2. **PDF 元数据标题会被推断错**（本例推成"项目经验"，实际是第一页的一个大标题）；页面里还有私用区字形（``，图标字体残留）。`metadata.titleSource: "inferred"` 能让你识别"这是推断不是原文"。

### 5.3 踩过的坑

| 坑 | 现象 | 解法 |
|---|---|---|
| Git Bash 路径改写 | `SSRF_BLOCKED: scheme 'd'` | 命令前加 `MSYS_NO_PATHCONV=1` |
| Windows Python 读 stdin | `JSONDecodeError`（中文被 GBK 解码） | `python -X utf8` 或 `PYTHONUTF8=1` |
| Node SDK 抓 HTTPS | `TLS_UNTRUSTED_ROOT: UnknownIssuer` | 本机有 TLS 中间人代理，rustls 不认系统证书库 → 改用 Docker |
| MCP 健康检查留残容器 | 多出一个 `--rm` 未清理的容器 | `docker rm -fv <名字>`；判据=无端口映射 + pagesift 镜像 |
| 本地文件走 MCP | 无此能力 | 走 CLI 挂载 或 `/v2/parse` 上传 |

---

## 六、对比官方 Benchmark（0.81，均为官方数据，我未复现）

| 任务 | 指标 | pagesift | 最强对手 | 差距 |
|---|---|---|---|---|
| PDF → Markdown（olmOCR-bench 1269 页，单线程） | 单页耗时 ↓ | 2.2 | pypdf 50.0 | ×22.3 |
| HTML → Markdown（600 篇） | 单页耗时 ↓ | 0.24 | Turndown 1.9 | ×8.2 |
| 网页正文（Firecrawl 597 页，单线程） | 中位耗时 ↓ | 1.0 | crw 7.4 | ×7.2 |
| Office / 电子书（81 份，单进程） | 吞吐 ↑ | 94.1 | Kreuzberg 19.5 | ×4.8 |
| RAG 分块（5 份语料 1.4MB） | 总耗时 ↓ | 11 | chonkie 35 | ×3.2 |
| RAG 查询过滤（472 题） | 答案召回 ↑ | 0.929 | Crawl4AI BM25 0.673 | +0.256 |
| 真实站点礼貌爬取（40 站×60 页） | 覆盖率 ↑ | 0.740 | Crawl4AI 0.529 | +0.211 |

**它自己也承认落后的三处**（这点比数字更值得记）：

- 回放吞吐 2.4 页/秒 vs spider 156.6 —— 差距主要来自**默认 1 秒同主机间隔**，不是引擎速度
- 快速模式 40 站×60 页 16.6 s vs spider 1.4 s —— 同上
- 扫描件完成率 0.112 vs Docling(GPU) 1.000 —— **它压根不做 OCR**，只读文本层

🎯 读 benchmark 的态度：**"最弱的那几行"比最强的几行信息量大**。官方肯把"我们不做 X、我们在 Y 上输一个数量级"写进首页，说明这几条是设计取舍而不是 bug。

---

## 七、劣势与边界

| 边界 | 说明 |
|---|---|
| **不做 OCR** | 扫描版 PDF / 图片只有文本层才读得到；扫描件请用 Docling / olmOCR |
| **不追求极限爬速** | 守 robots.txt + 同主机 1s 间隔 + 失败重试，比 spider 慢一个量级——这是"礼貌"的代价，不是缺陷 |
| **Windows 覆盖不全** | 无 CLI 二进制、无 Python wheel，只能 Docker 或 Node SDK |
| **MCP 不接文件** | 本地文档必须走 CLI / HTTP 上传 |
| **AGPL-3.0** | 商业闭源部署要么遵守 AGPL 要么买商业许可 |
| **无托管云服务** | 只能自托管 |
| **弱在"读得懂"** | 它保证"转得像"，不保证"转完能回答业务问题"——后者是切块与检索的事（[[17-生产知识库实战]]） |

---

## 八、同类工具对比

| 工具 | 定位 | 与 pagesift 差异 |
|---|---|---|
| Firecrawl | 商业抓取 API（也开源自托管） | pagesift 兼容其 v1/v2 协议，换 `api_url` 即迁；不按页付费 |
| Jina Reader | 托管 reader 服务 | pagesift 提供同形 `/r/` 端点，自托管 |
| Crawl4AI | Python 爬取/抽取框架 | 同生态内可编程性更强；覆盖率和召回指标低于 pagesift |
| trafilatura / Readability | 纯正文提取库 | 只处理 HTML，不碰 PDF/Office/爬站 |
| pymupdf4llm / pypdf | PDF → 文本 | 只做 PDF，且慢一个量级 |
| Kreuzberg | 多格式文档提取库 | 定位最接近；pagesift 吞吐更高、且带爬取能力 |
| Docling | 文档理解（含 OCR/版面） | **扫描件场景 pagesift 打不过，该换 Docling** |
| spider | 极快爬虫 | 快，但不限速；无 Markdown 清洗与多格式文档 |

---

## 九、收尾 + 连接到已学

**带走四件事：**

1. **一种能力、多种皮**是成熟开源工具的标配形态：核心一个，CLI / HTTP / MCP / SDK 各包一层。选哪层看消费者，不看功能。
2. **协议形态会砍掉能力**：MCP 参数是 JSON，所以文件传不进去——不是工具没做，是形态不许。选型时先问"我的输入是资源还是文件"。
3. **读 benchmark 先看输的那几行**：肯把弱点写进首页的工具，那几条是取舍；只贴赢的，才要警惕。
4. **Windows 上"有没有预编译"决定可行性**：源码能从 PyPI 下到 ≠ 能装上，sdist + 无 Rust 工具链 = 直接堵死。

| 已学概念 | 在 pagesift 里的体现 |
|---|---|
| [[01-RAG入门教程]] / [[17-生产知识库实战]] | 它就是 RAG 入库流水线的第一段（抓取+解析），被服务化 |
| [[06-MCP]] | 第五层皮；同时是"MCP 传不了文件"的边界实证 |
| [[13-CLI]] | 第一层皮，三条契约（参数进 / 文本出 / 退出码）逐条对上 |
| [[09-LangGraph]] 的 HITL 思路 | 无直接体现，但它"结果残缺要报警"是同一类"别让静默失败"的设计 |
| [[18-REA逆向工程]] | 同一种"把不确定性写进输出"（`partial_content` 警告 vs `limitations` 字段） |
| [[12-应用层Benchmark评测]] | 官方 benchmark 的"四问"（任务选择偏差 / baseline 强弱 / 成功率代价 / 谁测的）用在这里 |

**价值定位**：没引入新概念，是已学 RAG（入库段）+ MCP + CLI 三站的产品级组装。归「工程实践补充」，非学习路线节点。

---

## 参考资料

- [GitHub: YOLOW92/pagesift](https://github.com/YOLOW92/pagesift)
- [中文 README](https://github.com/YOLOW92/pagesift/blob/main/docs/README.zh-CN.md)
- [上传文件解析 API（/v2/parse）](https://github.com/YOLOW92/pagesift/blob/main/docs/parse-api.md)
- 官方 benchmarks：`docs/benchmarks/history/0.81/`
