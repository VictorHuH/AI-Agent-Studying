# 📄 用 Python 对简历 PDF 做 RAG（实战笔记）

> 学习日期：2026-07-08
> 目标：跑通一个能"和简历对话"的最小 RAG 应用

## 一、环境准备

```bash
pip install openai pypdf numpy

# 设置 API Key
# Windows PowerShell:
$env:OPENAI_API_KEY="sk-你的key"
# Windows CMD:
set OPENAI_API_KEY=sk-你的key
```

国内无 OpenAI key 时见末尾「国内模型替换方案」。

## 二、完整代码（rag_resume.py）

```python
"""
和你的简历对话：一个最小 RAG 应用
对应 RAG 三步：索引 → 检索 → 生成
"""
import os
import numpy as np
from pypdf import PdfReader
from openai import OpenAI

# ===== 0. 初始化客户端 =====
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    # base_url="https://api.deepseek.com",   # 用 DeepSeek 时取消注释
)

EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL  = "gpt-4o-mini"


# ===== 1. 读取 PDF =====
def load_pdf(path: str) -> str:
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    import re
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


# ===== 2. 切块（带重叠）=====
def chunk_text(text: str, size: int = 300, overlap: int = 50) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return [c for c in chunks if c.strip()]


# ===== 3. Embedding =====
def embed(text: str) -> np.ndarray:
    res = client.embeddings.create(model=EMBED_MODEL, input=text)
    return np.array(res.data[0].embedding, dtype=np.float32)


# ===== 4. 检索 Top-K（批量余弦相似度）=====
def retrieve(question: str, chunks: list[str], doc_vecs: np.ndarray, k: int = 3):
    qv = embed(question)
    dots = doc_vecs @ qv
    scores = dots / (np.linalg.norm(doc_vecs, axis=1) * np.linalg.norm(qv) + 1e-8)
    top_idx = np.argsort(scores)[::-1][:k]
    return [chunks[i] for i in top_idx], [float(scores[i]) for i in top_idx]


# ===== 5. 生成 =====
def answer(question: str, context_chunks: list[str]) -> str:
    context = "\n---\n".join(context_chunks)
    res = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content":
             f"你是简历主人的助手，只根据以下简历内容回答问题。"
             f"简历中未提及的信息就说\"简历中未提及\"。\n\n简历内容:\n{context}"},
            {"role": "user", "content": question},
        ],
    )
    return res.choices[0].message.content


# ===== 主流程 =====
if __name__ == "__main__":
    pdf_path = "resume.pdf"            # ← 改成你的简历路径

    # 索引阶段
    text = load_pdf(pdf_path)
    chunks = chunk_text(text)
    print(f"✅ 简历切成 {len(chunks)} 块")

    doc_vecs = np.array([embed(c) for c in chunks])
    print("✅ 向量化完成，开始提问\n" + "=" * 40)

    # 检索 + 生成
    while True:
        q = input("\n💬 问点关于简历的（q 退出）: ").strip()
        if q.lower() == "q":
            break
        tops, scores = retrieve(q, chunks, doc_vecs, k=3)
        print(f"🔍 命中相似度: {[f'{s:.3f}' for s in scores]}")
        print("🤖 " + answer(q, tops))
```

## 三、运行

```bash
python rag_resume.py
```

示例提问：
- "这份简历的主人有哪些工作经历？"
- "他用过哪些技术栈？"
- "他的最高学历是什么？"

## 四、代码对应 RAG 三步

| RAG 阶段 | 代码函数 | 做了什么 |
|---------|---------|---------|
| 索引 | `load_pdf` + `chunk_text` + `embed` | 读 PDF → 切块 → 向量化 → 存进 `doc_vecs` |
| 检索 | `retrieve` | 问题向量化 → 算余弦相似度 → 取 Top-3 |
| 生成 | `answer` | 把 Top-3 块拼进 system prompt → 调大模型 |

`doc_vecs` 这个 numpy 数组就是"向量数据库"。真实项目换成 Chroma / Milvus / pgvector，逻辑一样。

## 五、国内模型替换方案

兼容 OpenAI SDK 格式，改 `base_url`、`api_key`、模型名即可：

```python
# 智谱 GLM（推荐，有 Embedding）
client = OpenAI(
    api_key=os.getenv("ZHIPU_API_KEY"),
    base_url="https://open.bigmodel.cn/api/paas/v4/",
)
EMBED_MODEL = "embedding-3"
CHAT_MODEL  = "glm-4-flash"

# 通义千问
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
EMBED_MODEL = "text-embedding-v3"
CHAT_MODEL  = "qwen-plus"
```

⚠️ DeepSeek 没有 Embedding 接口，用 DeepSeek 做对话时 Embedding 仍需智谱/通义/OpenAI。新手建议直接用智谱或通义，一套搞定。

## 六、常见坑

| 问题 | 解决 |
|------|------|
| `extract_text()` 返回空 | 扫描件 PDF（图片），改用 OCR：`pytesseract` 或换 `PyMuPDF` |
| API 报 401 | API Key 没设对，检查环境变量 |
| 相似度都很低 | 简历太短切块太碎，调大 `size`（如 500）和 `k` |
| 中文切块 | 按字符数切没问题；按 token 切用 `tiktoken` |

## 七、核心收获

跑通这个 demo 后就拥有了 RAG 的最小骨架。后续进阶（Re-ranking、Hybrid Search、多轮对话、换向量数据库）都是在这个骨架上迭代。
