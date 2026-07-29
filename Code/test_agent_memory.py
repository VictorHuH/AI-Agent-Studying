"""
Agent 记忆实战 demo（三层记忆模型）
在 test_agent.py 的 ReAct Agent 上加记忆，演示完整的三层记忆 + 长期记忆闭环。

三层记忆：
  - 短期记忆：messages 跨轮复用（会话内，FC 阶段已学）。test_agent.py 的 run_agent 每次
    新建 messages = 无记忆；这里把 messages 提到外层跨轮复用，就有了短期记忆。
  - 工作记忆：ReAct 的 Thought/Action/Observation 序列（当前任务的草稿/scratchpad）。
    在 ReAct 里它是"免费的"--天然就在 messages 里，不用额外代码。这是 ReAct 相比纯 FC 的隐形好处。
  - 长期记忆：Chroma 存对话事实，跨会话。复用 RAG 那套（Chroma + 豆包 embedding），
    数据源从"简历 PDF"换成"对话事实"。

长期记忆闭环（每轮）：
  检索相关记忆 -> 塞进 system prompt -> ReAct 对话 -> 提取这轮值得记的事实 -> 存进 Chroma
  下次对话回到"检索"，形成闭环。

用法：
  cd Code
  python test_agent_memory.py        # 第1次运行：建立记忆，看短期记忆生效
  python test_agent_memory.py        # 第2次运行：从长期记忆记得"你要去上海旅游"（跨会话！）

依赖：chromadb（RAG 阶段已装）
"""
import json
import os
import re
import hashlib
import chromadb
from openai import OpenAI

# ===== 0. 客户端（复用豆包配置）=====
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
)
CHAT_MODEL = "glm-5.2"
EMBED_MODEL = "doubao-embedding-vision"


# ===== 1. 工具（复用 test_agent.py）=====
def get_weather(city: str) -> str:
    fake = {"上海": "32℃，晴", "北京": "30℃，多云", "广州": "35℃，雷阵雨"}
    return fake.get(city, f"{city}：28℃，晴")


def calculate(expression: str) -> str:
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算失败: {e}"


TOOL_REGISTRY = {"get_weather": get_weather, "calculate": calculate}


# ===== 2. ReAct 系统提示词（复用 test_agent.py，原样不动）=====
SYSTEM_PROMPT = """你是一个会使用工具的智能助手。面对用户的问题，你要通过"推理-行动-观察"的循环来解决。

【可用工具】
1. get_weather：查询某城市当前天气。参数：city（城市名，字符串）。
2. calculate：精确计算数学表达式。参数：expression（表达式字符串，如 "35-30"）。

【输出格式（必须严格遵守）】
每次只输出一个三元组，然后停下等结果：
Thought: <这一步的思考：我要做什么、为什么、接下来计划>
Action: <工具名：get_weather 或 calculate；若信息已足够回答，写 Final Answer>
Action Input: <工具参数的 JSON，如 {"city": "上海"}；若 Action 是 Final Answer，这里写最终答案>

工具执行后，你会收到一行 "Observation: <结果>"，然后你继续下一个 Thought/Action/Action Input，直到能给出 Final Answer。

【示例】
用户：上海比北京热几度？
Thought: 我需要上海和北京的天气才能比较。先查上海。
Action: get_weather
Action Input: {"city": "上海"}
Observation: 32℃，晴
Thought: 上海 32℃。现在查北京。
Action: get_weather
Action Input: {"city": "北京"}
Observation: 30℃，多云
Thought: 上海 32℃、北京 30℃，差 2 度。用 calculate 确认一下。
Action: calculate
Action Input: {"expression": "32-30"}
Observation: 32-30 = 2
Thought: 确认差 2 度，信息够了。
Action: Final Answer
Action Input: 上海比北京热 2 度（32℃ vs 30℃）。

【规则】
- 每次只输出一个 Thought/Action/Action Input，等 Observation 再继续，不要一次性把多步都输出。
- Action 只能是 get_weather、calculate 或 Final Answer。
- Action Input 必须是合法 JSON（Action 为 Final Answer 时除外）。
- 不要编造天气或计算结果，必须通过工具获取。
"""

_RE_THOUGHT = re.compile(r"Thought[：:]\s*(.+?)(?=\nAction[：:])", re.DOTALL)
_RE_ACTION = re.compile(r"Action[：:]\s*(.+)")
_RE_INPUT = re.compile(r"Action Input[：:]\s*(.+)", re.DOTALL)


# ===== 3. 长期记忆：Chroma 封装（复用 RAG 那套）=====
# 注意路径：用 ./chroma_memory，和 RAG 的 ./chroma_db 分开，避免污染简历库
chroma_client = chromadb.PersistentClient(path="./chroma_memory")
MEM_COLLECTION = "agent_memory"


def get_memory_collection():
    """长期记忆的"表"（同 RAG 的 collection，cosine 距离）。"""
    return chroma_client.get_or_create_collection(
        name=MEM_COLLECTION, metadata={"hnsw:space": "cosine"}
    )


def embed(text: str) -> list[float]:
    """文本 -> 向量（同 RAG 的 embed，豆包 embedding 模型）。"""
    res = client.embeddings.create(model=EMBED_MODEL, input=text)
    return res.data[0].embedding


def save_memory(text: str, collection):
    """存一条事实进长期记忆。

    id 用文本 md5：① 跨进程稳定（Python str hash 默认随机化，跨运行不一致，不能用）
                  ② 天然去重--相同事实 md5 相同，Chroma add 会 upsert 覆盖，不会重复存。
    """
    mid = hashlib.md5(text.encode()).hexdigest()[:16]
    collection.add(ids=[mid], embeddings=[embed(text)], documents=[text])


def recall(query: str, collection, k: int = 3) -> list[str]:
    """检索与当前问题相关的长期记忆。空库时跳过（避免 Chroma 空查询报错）。"""
    if collection.count() == 0:
        return []
    res = collection.query(query_embeddings=[embed(query)], n_results=k)
    return res["documents"][0]


def extract_facts(user_query: str, agent_answer: str) -> list[str]:
    """用 LLM 从一轮对话提取"值得长期记住的事实"。

    不是所有对话都值得记（"你好"不用记）。让 LLM 当"记忆筛选器"：
    只提取用户偏好/个人信息/重要计划，闲聊返回空列表。
    记忆写入要有选择性，否则全是噪音--这是长期记忆质量的关键。
    """
    prompt = (
        '从下面这轮对话里提取"值得长期记住的事实"（用户偏好、个人信息、重要计划/决定等）。\n'
        "没有值得记的就返回空数组 []。每条事实一句话、客观陈述、不要编造。\n"
        '只输出 JSON 数组，如 ["用户打算下周去上海旅游"]，不要任何其他文字。\n\n'
        f"用户：{user_query}\n助手：{agent_answer}\n\n值得记住的事实（JSON 数组）："
    )
    res = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    try:
        facts = json.loads(res.choices[0].message.content)
        return facts if isinstance(facts, list) else []
    except json.JSONDecodeError:
        return []  # 模型没按格式输出就当没提取到，不存


# ===== 4. ReAct 循环（带短期记忆 messages + 长期记忆 memory_text）=====
def run_agent(user_query, messages, memory_text, max_steps=10):
    """ReAct 循环。messages 跨轮复用 = 短期记忆；memory_text 塞进 system = 长期记忆。"""
    # 长期记忆前置拼进 system（不破坏原 SYSTEM_PROMPT 里的 JSON 例子，避免 .format() 转义问题）
    system_content = SYSTEM_PROMPT
    if memory_text:
        system_content = (
            "【关于用户的长期记忆（来自过往对话，回答时可参考）】\n"
            f"{memory_text}\n\n" + SYSTEM_PROMPT
        )
    # 更新或插入 system：每轮 memory 可能变，要刷新 messages[0]
    if messages and messages[0]["role"] == "system":
        messages[0] = {"role": "system", "content": system_content}
    else:
        messages.insert(0, {"role": "system", "content": system_content})
    messages.append({"role": "user", "content": user_query})

    print(f"\n{'#'*60}\n# 用户: {user_query}\n{'#'*60}")
    for step in range(1, max_steps + 1):
        print(f"\n--- 第 {step} 步 ---")
        resp = client.chat.completions.create(model=CHAT_MODEL, messages=messages)
        text = resp.choices[0].message.content.strip()
        messages.append({"role": "assistant", "content": text})  # 短期+工作记忆：记回

        m_thought = _RE_THOUGHT.search(text)
        if m_thought:
            print(f"💭 Thought: {m_thought.group(1).strip()}")

        m_action = _RE_ACTION.search(text)
        if not m_action:
            print(f"⚠️ 没解析到 Action：\n{text}")
            return None, messages
        action = m_action.group(1).strip()

        if action.lower().startswith("final answer"):
            m_input = _RE_INPUT.search(text)
            final = m_input.group(1).strip() if m_input else text
            print(f"✅ 最终答案: {final}")
            return final, messages

        m_input = _RE_INPUT.search(text)
        if not m_input:
            print(f"⚠️ 缺 Action Input：\n{text}")
            return None, messages
        raw_input = m_input.group(1).strip()
        try:
            args = json.loads(raw_input)
        except json.JSONDecodeError:
            observation = f"参数不是合法 JSON：{raw_input}，请严格输出 JSON。"
        else:
            print(f"🔧 Action: {action}({args})")
            fn = TOOL_REGISTRY.get(action)
            observation = fn(**args) if fn else f"未知工具 '{action}'，可用：{list(TOOL_REGISTRY)}"
        print(f"👁️ Observation: {observation}")
        messages.append({"role": "user", "content": f"Observation: {observation}"})

    print("⚠️ 达到最大步数仍未结束")
    return None, messages


# ===== 5. 多轮对话 + 长期记忆闭环 =====
def chat_with_memory():
    collection = get_memory_collection()
    messages = []  # 短期记忆：跨轮复用（会话内）
    queries = [
        "我打算下周去上海旅游，帮我查下上海天气。",
        # 第二句测短期记忆："我刚才说要去哪"要靠 messages 里记着的上海；"那边天气"再查一次
        "我刚才说要去哪旅游来着？那边天气怎么样？",
    ]
    for q in queries:
        # ① 检索长期记忆
        mems = recall(q, collection)
        memory_text = "\n".join(f"- {m}" for m in mems) if mems else ""
        print(f"\n🧠 检索长期记忆: {mems if mems else '（空）'}")

        # ②③ ReAct 对话（短期 messages + 长期 memory_text）
        answer, messages = run_agent(q, messages, memory_text)

        # ④⑤ 提取这轮事实 -> 存长期记忆
        facts = extract_facts(q, answer) if answer else []
        for f in facts:
            save_memory(f, collection)
        print(f"💾 提取并存入长期记忆: {facts if facts else '（无）'}")

    print(f"\n📁 长期记忆库现有 {collection.count()} 条")
    print("💡 跨会话验证：再运行一次 python test_agent_memory.py，")
    print("   第一轮就能从长期记忆记得'用户要去上海旅游'--这就是跨会话长期记忆")
    print("   （短期记忆会话结束就没了，长期记忆不会）。")


if __name__ == "__main__":
    chat_with_memory()
