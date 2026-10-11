"""17-生产知识库实战 · 在线查询（RAG Query）

生产 RAG 的在线半边：问题 → embedding → 余弦相似度 top-k → 拼进 prompt
→ glm-5.2 生成 → 带引用出处的回答。检索过程全程打印，方便观察命中情况。
用法: python Code/ask_wiki.py
"""
import json
import os
from pathlib import Path

import numpy as np
from openai import OpenAI

INDEX_PATH = Path(__file__).resolve().parent / "wiki_index.json"
EMBED_MODEL = "doubao-embedding-vision"
CHAT_MODEL = "glm-5.2"
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
)


def retrieve(question: str, k: int = 5):
    """问题向量化 → 和索引里所有块算余弦 → top-k。这就是向量库内部干的事"""
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    vecs = np.array([c["vec"] for c in index["chunks"]])
    q = np.array(client.embeddings.create(model=EMBED_MODEL, input=[question]).data[0].embedding)
    scores = vecs @ q / (np.linalg.norm(vecs, axis=1) * np.linalg.norm(q))
    top = np.argsort(scores)[::-1][:k]
    return [(index["chunks"][i], float(scores[i])) for i in top]


def answer(question: str, hits) -> str:
    ctx = "\n\n".join(
        f"[{n}] 出处：{c['file']} · {c['heading']}\n{c['text']}"
        for n, (c, _) in enumerate(hits, 1))
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content":
                "你是学习笔记知识库助手。仅依据下方编号资料回答，引用时标注 [编号]，"
                "资料里没有的内容就明说不知道，不要编造。\n\n" + ctx},
            {"role": "user", "content": question},
        ])
    return resp.choices[0].message.content


if __name__ == "__main__":
    while True:
        q = input("\n💬 问点关于学习笔记的（q 退出）: ").strip()
        if q.lower() == "q":
            break
        hits = retrieve(q)
        print("🔍 检索命中：")
        for n, (c, s) in enumerate(hits, 1):
            print(f"   [{n}] {c['file']} · {c['heading']}（{s:.3f}）")
        print("\n🤖 " + answer(q, hits))
