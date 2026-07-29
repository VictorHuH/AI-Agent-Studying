"""
父子块 Small-to-Big 演示
核心思想：检索用小块（精准定位），返回用大块（上下文完整）
对比：普通检索（命中小块返回小块） vs Small-to-Big（命中小块返回所属大块）
"""
import os
import chromadb
from pypdf import PdfReader
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
)
EMBED_MODEL = "doubao-embedding-vision"
CHAT_MODEL  = "glm-5.2"
PDF_PATH = r"C:\Users\Administrator\Desktop\Personal\本科毕业找工作\胡天鸿的简历.pdf"


# ---- 基础工具（和 test.py 一致）----
def dedup_adjacent_lines(text: str) -> str:
    lines = text.split("\n")
    out = []
    for l in lines:
        if not out or out[-1] != l:
            out.append(l)
    return "\n".join(out)


def load_pdf(path: str) -> str:
    reader = PdfReader(path)
    import re
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return dedup_adjacent_lines(text).strip()


def chunk_text(text: str, size: int = 300, overlap: int = 50) -> list[str]:
    """递归切分（同 test.py）：尊重结构 + 小块合并 + 去重"""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks, buffer = [], ""
    for para in paragraphs:
        if len(para) < 2:
            continue
        cand = (buffer + "\n" + para) if buffer else para
        if len(cand) <= size:
            buffer = cand
        else:
            if buffer:
                chunks.append(buffer)
            if len(para) > size:
                s = 0
                while s < len(para):
                    chunks.append(para[s:s + size])
                    s += size - overlap
                buffer = ""
            else:
                buffer = para
    if buffer:
        chunks.append(buffer)
    seen = set()
    return [c for c in chunks if not (c in seen or seen.add(c))]


def embed(text: str) -> list[float]:
    return client.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding


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


# ---- 父子块切分 ----
def build_parent_child(text: str, parent_size: int = 600, child_size: int = 150, child_overlap: int = 30):
    """先切父块（大），每个父块再切子块（小）。返回 [(子块, 父块), ...]"""
    parents = chunk_text(text, size=parent_size, overlap=0)   # 父块不重叠，边界清晰
    pairs = []
    for parent in parents:
        children = chunk_text(parent, size=child_size, overlap=child_overlap)
        for child in children:
            pairs.append((child, parent))
    return pairs


# ---- 索引：子块做 embedding，父块文本存 metadata ----
def build_collection(pairs):
    cclient = chromadb.PersistentClient(path="./chroma_stb")   # 单独目录，不污染 test.py 的库
    coll = cclient.get_or_create_collection(name="resume_stb", metadata={"hnsw:space": "cosine"})
    if coll.count() > 0:
        print(f"⚡ 复用已有 {coll.count()} 个子块向量")
    else:
        coll.add(
            ids=[f"c{i}" for i in range(len(pairs))],
            embeddings=[embed(c) for c, _ in pairs],            # 只对子块算 embedding
            documents=[c for c, _ in pairs],                    # 子块文本（普通检索返回它）
            metadatas=[{"parent": p} for _, p in pairs],        # 父块文本（STB 返回它）
        )
    return coll


# ---- 两种检索 ----
def retrieve_normal(question: str, coll, k: int = 3) -> list[str]:
    """普通检索：命中子块，返回子块（信息可能不全）"""
    res = coll.query(query_embeddings=[embed(question)], n_results=k)
    return res["documents"][0]


def retrieve_stb(question: str, coll, k: int = 3) -> list[str]:
    """Small-to-Big：命中子块，返回去重后的父块（上下文完整）"""
    res = coll.query(query_embeddings=[embed(question)], n_results=k * 3)  # 多召回子块，去重父块后取k
    parents, seen = [], set()
    for m in res["metadatas"][0]:
        p = m["parent"]
        if p not in seen:                                       # 多个子块可能同属一个父块，去重
            seen.add(p)
            parents.append(p)
    return parents[:k]


# ---- 主流程：对比两种模式 ----
if __name__ == "__main__":
    text = load_pdf(PDF_PATH)
    pairs = build_parent_child(text)
    n_parents = len(set(p for _, p in pairs))
    print(f"✅ 切出 {n_parents} 个父块，{len(pairs)} 个子块")
    coll = build_collection(pairs)
    print("✅ 索引完成（子块做 embedding，父块存 metadata）\n" + "=" * 40)

    while True:
        q = input("\n💬 问点关于简历的（q 退出）: ").strip()
        if q.lower() == "q":
            break

        print("\n── 普通检索（返回小块）──")
        normal = retrieve_normal(q, coll, k=3)
        print(f"返回 {len(normal)} 个子块，总字数 {sum(len(c) for c in normal)}")
        print("🤖 " + answer(q, normal))

        print("\n── Small-to-Big（返回大块）──")
        stb = retrieve_stb(q, coll, k=3)
        print(f"返回 {len(stb)} 个父块，总字数 {sum(len(c) for c in stb)}")
        print("🤖 " + answer(q, stb))
