"""
LangChain 第三站：Retriever 收尾
用 LangChain 重写 test.py 的 RAG（检索 -> 生成），接你已有的 ./chroma_db 简历库。

对比 test.py 手写版（建议开着 test.py 对照读）：
  手写：retrieve(q, collection) -> (ids, docs, sims)；再 answer(q, docs)。两步手动调。
  LangChain：retriever | format_docs | prompt | model | parser  一条链。

核心看三件事：
  1. retriever 怎么从 vectorstore.as_retriever() 变出来（检索变 Runnable）
  2. RAG chain 的数据流：query -> 检索 -> 拼字符串 -> prompt -> model
  3. 对比手写：检索和生成从"两步"变成"一条链"

用法：
  cd Code
  python test_langchain_rag.py
"""
import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# ===== 0. 模型 + Embedding（对应手写 test.py 9-15 行）=====
# 手写：一个 OpenAI client 既调 chat 又调 embedding
# LangChain：拆成 ChatOpenAI（对话）+ OpenAIEmbeddings（向量化）两个组件
# 【可替换性】换模型 / 换 embedding 各改各的，互不影响（A/B 类分离的体现）
model = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
    model="glm-5.2",
)
embeddings = OpenAIEmbeddings(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
    model="doubao-embedding-vision",   # 同 test.py 的 EMBED_MODEL
    # 【坑】check_embedding_ctx_length 默认 True：会用 tiktoken 把文本先分词成 token id 数组再传。
    # OpenAI 官方端点吃 token id；火山豆包端点只吃字符串，报 400 "expected a string, got [43511...]"。
    # 关掉它，直接传字符串。这是"OpenAI 兼容=部分兼容"的典型坑。
    check_embedding_ctx_length=False,
)

# ===== 1. 向量库 + Retriever（对应手写 test.py 18-26、95-102 行）=====
# 手写：chromadb.PersistentClient + get_collection + retrieve 函数（独立调用）
# LangChain：Chroma 封装 + as_retriever() 把向量库变成 Runnable
# 【这一站的魔法】as_retriever()：把"查向量库"这个动作变成"链的一环"
vectorstore = Chroma(
    collection_name="resume",          # 同 test.py COLLECTION_NAME
    embedding_function=embeddings,
    persist_directory="./chroma_db",   # 同 test.py，复用已有数据，不重建
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})   # 对应 retrieve 的 k=3


# ===== 2. 把 Document 列表拼成字符串 =====
# 手写 test.py 没单独这步，散在 answer() 里：context = "\\n---\\n".join(context_chunks)
# LangChain：检索输出 Document 列表，要拼成字符串才能塞进 prompt
def format_docs(docs):
    return "\n---\n".join(d.page_content for d in docs)


# ===== 3. Prompt（对应手写 test.py 143-147 行 answer 的 messages）=====
# 手写：messages 里直接 f-string 拼 context
# LangChain：ChatPromptTemplate 模板化，{context}/{question} 占位符运行时注入
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是简历主人的助手，只根据以下简历内容回答问题。"
               "简历中未提及的信息就说\"简历中未提及\"。\n\n简历内容:\n{context}"),
    ("user", "{question}"),
])

# ===== 4. 拼成 RAG chain（对应手写 test.py 主流程的 retrieve -> answer 两步）=====
# 这是这一站的核心：retriever 接进链，跟 prompt/model 平起平坐。
# 数据流见下方"数据流图"。
chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt | model | StrOutputParser()
)

# ===== 5. 调用（用 test.py 评估集里的同一问题，对比手写版）=====
# 这个问题 test.py TESTSET 标注 relevant={3,7}（跨块问题，你父子块那站验证过）
if __name__ == "__main__":
    q = "他用过什么部署技术？"
    print(f"问题：{q}\n")
    print("回答：")
    print(chain.invoke(q))
