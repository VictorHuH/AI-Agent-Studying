# Windows 下使用 OpenClaw + GBrain + 豆包 Embedding 搭建个人第二大脑

## 前言

GBrain 并不是传统的 RAG，也不是一个简单的知识库，而是一个为 AI Agent 提供长期记忆的系统。本文记录我在 **Windows** 环境下使用 **OpenClaw + GBrain + 火山引擎 Doubao Embedding** 的安装过程，全程无需使用官方推荐的 ZeroEntropy。

------

## 环境

- Windows 11
- OpenClaw（已安装）
- Bun
- GBrain 0.42.x
- DeepSeek V4 Flash
- Doubao Embedding Vision 251215（火山引擎 ARK）

整体架构如下：

```text
OpenClaw
    │
    ▼
 GBrain
    │
    ▼
OpenAI Compatible 接口
    │
    ▼
Doubao Embedding（ARK）
```

------

## 安装 GBrain

由于已经安装了 OpenClaw，因此可以直接让 Agent 自动安装 GBrain。

在 OpenClaw 中输入：

```text
Retrieve and follow the installation instructions at:

https://raw.githubusercontent.com/garrytan/gbrain/master/INSTALL_FOR_AGENTS.md

Please execute the installation step by step.
```

安装完成后，可执行：

```powershell
gbrain --version
gbrain doctor
```

如果能看到版本号，并且 `gbrain doctor` 正常运行，则说明安装成功。

------

## 配置 Embedding

官方默认推荐使用 **ZeroEntropy**，但国内使用并不方便，因此我改用了 **火山引擎 Doubao Embedding**。

由于 GBrain 当前仅支持 OpenAI Compatible Embedding，因此增加了一个本地代理：

```text
GBrain
    ↓
ark-proxy
    ↓
Doubao Embedding
```

代理负责把 OpenAI Embedding 请求转换为火山 ARK 接口，并将返回的向量维度调整为 GBrain 所需的 1536 维。

------

## 启动方式

每次使用前先启动代理：

```powershell
set ARK_API_KEY=你的ARK_API_KEY
node C:\Users\Administrator\.openclaw\workspace\ark-proxy.mjs
```

然后配置 GBrain：

```powershell
set OPENAI_API_KEY=你的ARK_API_KEY
set OPENAI_BASE_URL=http://localhost:11435
```

也可以使用 `setx` 将环境变量永久保存。

------

## 导入知识

导入 Markdown：

```powershell
gbrain import ./你的笔记目录
```

生成向量：

```powershell
gbrain embed --stale
```

开始查询：

```powershell
gbrain ask "Transformer 是什么？"
```

如果能够返回导入笔记中的内容，则说明整个知识库已经正常工作。

------

## 总结

至此，一套完整的个人知识脑已经搭建完成：

- **OpenClaw**：负责推理和 Agent 能力
- **GBrain**：负责长期知识管理
- **Doubao Embedding**：负责向量检索
- **Markdown**：作为知识的唯一事实来源（Source of Truth）

后续只需要持续维护 Markdown 笔记，并定期执行：

```powershell
gbrain embed --stale
```

即可让 GBrain 持续更新自己的知识库，实现真正意义上的 AI 长期记忆。