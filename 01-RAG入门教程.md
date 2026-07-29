# 📖 RAG 简易教程（入门笔记）

> 学习日期：2026-07-08
> 适用对象：前端工程师转型大模型应用开发

## 一、什么是 RAG？

**RAG = Retrieval-Augmented Generation（检索增强生成）**

一句话定义：**先检索，再生成**。让大模型在回答问题前，先去你的私有数据里"查资料"，然后基于查到的资料来回答。

> 🎯 **类比：开卷考试**
> 大模型是个聪明的学生，但没学过你公司的内部资料。RAG 就是考试时给它一本「参考书」，让它先翻到相关页码，再答题。

## 二、为什么需要 RAG？

大模型本身的硬伤：

| 问题 | 说明 |
|------|------|
| ⏰ 知识截止 | 训练数据有截止日期，不知道最新信息 |
| 🔒 不识私有数据 | 你的公司文档、个人笔记，它从没见过 |
| 🤥 会幻觉 | 不知道也硬编，说得头头是道 |
| 💰 微调成本高 | 更新知识要重新训练，又贵又慢 |

RAG 的优势：
- ✅ 数据随时更新（加文档就行，不用重训模型）
- ✅ 回答有依据（可溯源到原文）
- ✅ 数据私有（不用把数据喂给模型训练）

## 三、核心流程（经典三步）

```
1. 索引阶段（离线，一次性）
   文档 → 切块(Chunking) → 向量化(Embedding) → 存入向量库

2. 检索阶段（在线，每次提问）
   用户问题 → 向量化 → 在向量库中找最相似的 Top-K 块

3. 生成阶段（在线）
   [检索到的块 + 用户问题] → 拼成 Prompt → 大模型生成回答
```

## 四、4 个关键概念

### 1. Embedding（向量化）
把文本变成一串数字（向量），让计算机能计算**语义相似度**。
- "猫" 和 "小猫咪" → 向量距离很近 ✅
- "猫" 和 "汽车" → 向量距离很远 ❌

这是 RAG 能做**语义检索**（而非关键词匹配）的根本原因。用户问"年假"，能命中写"带薪休假"的文档。

### 2. Chunking（切块）
文档太长，模型一次吃不下，要切成小块。
- 块太大 → 检索不精准，浪费 token
- 块太小 → 丢失上下文
- 常见策略：按字符数切（如 500 字），带重叠（overlap 50 字，防止切断语义）

### 3. 向量数据库
专门存向量、做相似度搜索的数据库。
- 主流：Pinecone、Milvus、Chroma、Qdrant、Weaviate
- 也能用现有数据库：PostgreSQL + pgvector 插件

### 4. 相似度检索
用**余弦相似度（Cosine Similarity）**算两个向量的"方向"是否一致，越接近 1 越相似。

## 五、极简代码示例（TypeScript）

用 OpenAI SDK + 内存数组模拟向量库，理解本质。真实项目把内存数组换成向量数据库即可。

```typescript
import OpenAI from "openai";
const openai = new OpenAI();

// ===== 1. 索引阶段：把文档切块 + 向量化 =====
const docs = [
  "公司请假制度：年假每年15天，需提前3天申请。",
  "报销流程：填报销单附发票，提交部门经理审批。",
  "上班时间：周一至周五 9:00-18:00，午休1小时。",
];

async function embed(text: string): Promise<number[]> {
  const res = await openai.embeddings.create({
    model: "text-embedding-3-small",
    input: text,
  });
  return res.data[0].embedding;
}

const docVectors = await Promise.all(docs.map(embed));

// ===== 2. 检索阶段：问题向量化 + 找最相似的 Top-2 =====
const question = "年假有几天？";
const qVector = await embed(question);

function cosineSim(a: number[], b: number[]) {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] ** 2;
    nb += b[i] ** 2;
  }
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}

const topK = docVectors
  .map((v, i) => ({ doc: docs[i], score: cosineSim(v, qVector) }))
  .sort((a, b) => b.score - a.score)
  .slice(0, 2);

// ===== 3. 生成阶段：把检索结果拼进 Prompt，让模型回答 =====
const context = topK.map((t) => t.doc).join("\n");

const reply = await openai.chat.completions.create({
  model: "gpt-4o-mini",
  messages: [
    {
      role: "system",
      content: `根据以下资料回答问题，资料中没有就说"不知道"。\n\n资料:\n${context}`,
    },
    { role: "user", content: question },
  ],
});

console.log(reply.choices[0].message.content);
// ✅ 输出：年假每年15天。
```

RAG 的本质就这么简单——检索 + 拼接 + 生成。后面所有进阶都是在优化这三个环节。

## 六、前端工程师的切入点

1. **流式输出**：生成阶段用 SSE 流式返回，前端逐字渲染
2. **引用展示**：把检索到的来源展示给用户（可溯源），做高亮、跳转、折叠
3. **检索可视化**：显示命中了哪些文档块、相似度分数，做调试面板

## 七、进阶路线

- 📐 Chunking 优化：语义切分、父子块（Parent-Child）
- 🔁 Re-ranking：检索回一批后用模型重新排序，提升精度
- 🔍 Hybrid Search：向量 + 关键词（BM25）混合检索
- 💬 Multi-turn RAG：多轮对话带历史上下文
- 🕸️ GraphRAG：基于知识图谱的 RAG

## 八、一句话总结

> RAG = 给大模型一本「参考书」，让它先查再答。
> 核心三步：**索引（切块+向量化+入库）→ 检索（找相似）→ 生成（拼Prompt回答）**
