"""
LangChain 第一站：最小 LCEL 链
用 LangChain 重写 test_agent.py 里"拼 prompt -> 调模型 -> 解析"这一段。

对比 test_agent.py 手写版（建议开着 test_agent.py 对照读）：
  手写：messages = [system, user] -> client.create(messages) -> resp.choices[0].message.content
  LangChain：prompt | model | parser  三个组件用 | 拼起来，chain.invoke({...}) 传字典

核心看三件事（跑完对着输出看）：
  1. 三个组件分别对应手写代码的哪部分
  2. | 管道怎么把上一个组件的输出喂给下一个
  3. invoke 怎么传参、返回什么

用法：
  cd Code
  python test_langchain.py
"""
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ===== 1. 模型组件（对应手写 test_agent.py 28-33 行：客户端初始化）=====
# 手写：client = OpenAI(api_key=..., base_url=...)，调用时再传 model
# LangChain：ChatOpenAI 把 api_key/base_url/model 全封进一个组件。
# 【可替换性体现】换模型供应商只改这一处，其余不动。
model = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
    model="glm-5.2",
)

# ===== 2. Prompt 模板组件（对应手写 60-97 行 SYSTEM_PROMPT + 109-112 拼 messages）=====
# 手写：SYSTEM_PROMPT 是写死的字符串，工具说明焊在里面，换工具要改整个字符串。
# LangChain：ChatPromptTemplate 把 prompt 参数化，{tool_desc}/{question} 是占位符，运行时注入。
# 【可替换性体现】换工具只改 invoke 传入的 tool_desc，prompt 模板不动。
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个会使用工具的智能助手。{tool_desc}"),
    ("user", "{question}"),
])

# ===== 3. 解析器组件（对应手写 101-103 行 _RE_THOUGHT 等正则解析）=====
# 手写：用 re.search 从模型文本里抠 Thought/Action。
# 这里先用最简的 StrOutputParser：直接拿模型 content 字符串。
# 后面到 Agent 段会换成结构化解析器（Pydantic），这里先看最小链子。
parser = StrOutputParser()

# ===== 4. 用 LCEL 拼起来（对应手写 run_agent 里"拼 messages -> 调模型 -> 拿 content"）=====
# | 是管道符重载：prompt 的输出喂给 model，model 的输出喂给 parser。
# 手写要三步显式调用；LangChain 一行声明 + 一个 invoke。
chain = prompt | model | parser

# ===== 5. 调用（对应手写 client.chat.completions.create）=====
# invoke 传字典，key 对应模板里的占位符 {tool_desc}、{question}。
# 这条 query 选 test_agent.py 里注释掉的"闲聊"用例（不触发工具，直接答）。
result = chain.invoke({
    "tool_desc": "可用工具：get_weather（查某城市当前天气）。",
    "question": "你好，你是谁？能帮我做什么？",
})
print(result)
