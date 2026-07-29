import os
import sys
import time
import chromadb
from pypdf import PdfReader
from openai import OpenAI

# ===== 0. 初始化客户端 =====
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
)

EMBED_MODEL = "doubao-embedding-vision"   # Embedding 模型
CHAT_MODEL  = "glm-5.2"                   # 对话模型

# ===== 0.5 初始化向量数据库 Chroma（持久化到磁盘）=====
chroma_client = chromadb.PersistentClient(path="./chroma_db")
COLLECTION_NAME = "resume"

def get_collection():
    """创建/获取 collection（类似数据库里的"表"），用余弦距离"""
    return chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# ===== 1. 读取 PDF + 清洗 =====
def dedup_adjacent_lines(text: str) -> str:
    """去掉相邻的完全重复行（PDF 提取常见毛病：每行被提取两次）"""
    lines = text.split("\n")
    result = []
    for line in lines:
        if not result or result[-1] != line:
            result.append(line)
    return "\n".join(result)


def load_pdf(path: str) -> str:
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    import re
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = dedup_adjacent_lines(text)    # 去掉 PDF 提取产生的重复行
    return text.strip()


# ===== 2. 切块（递归切分：尊重结构 + 小块合并 + 清洗去重）=====
def chunk_text(text: str, size: int = 300, overlap: int = 50) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    buffer = ""                            # 攒相邻短段落，合并到 size 为止
    for para in paragraphs:
        if len(para) < 2:                  # 清洗：跳过单字/空块等脏数据
            continue
        candidate = (buffer + "\n" + para) if buffer else para
        if len(candidate) <= size:
            buffer = candidate             # 还没满，继续攒
        else:
            if buffer:
                chunks.append(buffer)
            if len(para) > size:
                start = 0
                while start < len(para):
                    chunks.append(para[start:start + size])
                    start += size - overlap
                buffer = ""
            else:
                buffer = para
    if buffer:
        chunks.append(buffer)
    seen = set()
    chunks = [c for c in chunks if not (c in seen or seen.add(c))]
    return chunks


def print_chunks(chunks: list[str]):
    """打印切块明细，用于观察切成了什么样（调试 RAG 的必备习惯）"""
    print(f"\n📋 切块明细（共 {len(chunks)} 块）:")
    for i, c in enumerate(chunks):
        preview = c.replace("\n", " ")[:70]
        print(f"  [{i}] ({len(c)}字) {preview}{'...' if len(c) > 70 else ''}")
    print()


# ===== 3. Embedding：文本 -> 向量 =====
def embed(text: str) -> list[float]:
    res = client.embeddings.create(model=EMBED_MODEL, input=text)
    return res.data[0].embedding


# ===== 4. 检索：用 Chroma 查最相似的 Top-K 块 =====
def retrieve(question: str, collection, k: int = 3):
    qv = embed(question)
    res = collection.query(query_embeddings=[qv], n_results=k)
    ids   = res["ids"][0]              # ["3","1",...] 块编号，评估时要对账
    docs  = res["documents"][0]
    dists = res["distances"][0]        # 余弦距离 = 1 - 相似度，越小越相似
    sims  = [1 - d for d in dists]     # 转回相似度
    return ids, docs, sims


# ===== 4.5 重排序（Re-ranking）：用 LLM 对粗排结果精排 =====
def rerank(question: str, cand_ids: list[str], cand_docs: list[str], top_n: int = 3):
    candidates_text = "\n\n".join(f"[{i}] {c[:200]}" for i, c in enumerate(cand_docs))
    prompt = (
        f"你是检索结果重排器。下面是一个问题和若干候选文档块。\n"
        f"请选出与问题最相关的 {top_n} 个块，按相关度从高到低返回它们的编号。\n"
        f"只输出编号，逗号分隔，不要任何其他文字。\n\n"
        f"问题：{question}\n\n候选块：\n{candidates_text}\n\n最相关的{top_n}个编号："
    )
    res = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,                # 重排要稳定，不要随机
    )
    import re
    nums = [int(x) for x in re.findall(r"\d+", res.choices[0].message.content)]
    seen, picked = set(), []
    for n in nums:                    # 取 LLM 选出的有效编号
        if 0 <= n < len(cand_docs) and n not in seen:
            seen.add(n)
            picked.append(n)
        if len(picked) >= top_n:
            break
    for i in range(len(cand_docs)):  # LLM 返回不足时按原顺序补齐
        if len(picked) >= top_n:
            break
        if i not in seen:
            seen.add(i)
            picked.append(i)
    return [cand_ids[i] for i in picked], [cand_docs[i] for i in picked]


# ===== 5. 生成：把检索结果拼进 Prompt，让大模型回答 =====
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


# ===== 6. 评估：用标注数据集量化检索质量（Hit@K, MRR）=====
# 测试集：每个问题人工标注"正确块编号"（对照 print_chunks 的 [0]-[7]）
# 这是评估的地基--没有标注，就没法算指标
TESTSET = [
    {"q": "他的论文研究什么？",        "relevant": {"6"}},
    {"q": "他做过哪个个人项目？",      "relevant": {"4"}},
    {"q": "他的籍贯是哪里？",          "relevant": {"0"}},
    {"q": "他用过什么部署技术？",      "relevant": {"3", "7"}},
    {"q": "他获得过什么奖？",          "relevant": {"5", "7"}},
    {"q": "项目1用了什么框架？",       "relevant": {"1", "2"}},
]

def evaluate(collection, use_rerank: bool = False, k: int = 3):
    """跑测试集，算 Hit@K（topK里有正确块的比例）和 MRR（正确块排名倒数的平均）"""
    hits, rr_sum = 0, 0
    mode = "精排(rerank)" if use_rerank else "粗排(无rerank)"
    print(f"\n📊 评估模式：{mode}  |  指标：Hit@{k}, MRR")
    print(f"{'问题':<20}{'命中块':<14}{'期望':<10}{'命中':<5}{'RR'}")
    print("-" * 60)
    for item in TESTSET:
        q, relevant = item["q"], item["relevant"]
        ids, docs, _ = retrieve(q, collection, k=10 if use_rerank else k)
        if use_rerank:
            ids, docs = rerank(q, ids, docs, top_n=k)
        hit = any(i in relevant for i in ids[:k])
        rr = 0.0
        for rank, i in enumerate(ids[:k], 1):
            if i in relevant:
                rr = 1 / rank
                break
        hits += int(hit)
        rr_sum += rr
        print(f"{q:<18}{','.join(ids[:k]):<14}{','.join(sorted(relevant)):<10}"
              f"{'✅' if hit else '❌':<4}{rr}")
    n = len(TESTSET)
    print("-" * 60)
    print(f"Hit@{k} = {hits}/{n} = {hits/n:.0%}   MRR = {rr_sum/n:.3f}\n")


# ===== 主流程 =====
if __name__ == "__main__":
    pdf_path = r"C:\Users\Administrator\Desktop\Personal\本科毕业找工作\胡天鸿的简历.pdf"
    collection = get_collection()

    # --rebuild：换切块策略后必须重建索引，否则 Chroma 里还是旧切块的数据
    if "--rebuild" in sys.argv:
        chroma_client.delete_collection(COLLECTION_NAME)
        collection = get_collection()
        print("🔄 已清空旧数据，准备用新策略重建索引...")

    # -- 索引阶段 --
    if collection.count() > 0:
        print(f"⚡ 检测到已有 {collection.count()} 块向量，跳过索引阶段")
        print("   （换切块策略后记得 --rebuild）")
    else:
        t0 = time.time()
        text = load_pdf(pdf_path)
        chunks = chunk_text(text)
        print(f"✅ 简历切成 {len(chunks)} 块")
        if "--show-chunks" in sys.argv:
            print_chunks(chunks)
        collection.add(
            ids=[str(i) for i in range(len(chunks))],
            embeddings=[embed(c) for c in chunks],
            documents=chunks,
        )
        print(f"✅ {len(chunks)} 块向量已存入 Chroma，索引耗时 {time.time()-t0:.2f}s")

    print("=" * 40)

    # 评估模式：跑测试集算指标，对比粗排 vs 精排
    if "--eval" in sys.argv:
        evaluate(collection, use_rerank=False, k=3)
        evaluate(collection, use_rerank=True,  k=3)
        sys.exit(0)

    # 交互问答模式
    use_rerank = "--rerank" in sys.argv
    print("🎯 Re-ranking 已开启（粗排10块 -> 精排3块）" if use_rerank
          else "检索模式：直接 top-3（加 --rerank 开启精排）")
    while True:
        q = input("\n💬 问点关于简历的（q 退出）: ").strip()
        if q.lower() == "q":
            break
        ids, tops, scores = retrieve(q, collection, k=10 if use_rerank else 3)
        if use_rerank:
            print(f"🔍 粗排召回 {len(tops)} 块，相似度: {[f'{s:.3f}' for s in scores]}")
            ids, tops = rerank(q, ids, tops, top_n=3)
            print(f"🎯 精排后取前 3 块（编号 {ids}）")
        else:
            print(f"🔍 命中块 {ids}，相似度: {[f'{s:.3f}' for s in scores]}")
        print("🤖 " + answer(q, tops))
