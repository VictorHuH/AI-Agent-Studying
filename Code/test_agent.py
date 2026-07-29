"""
Agent 实战 demo（ReAct 模式）
演示 Agent 的核心：自主规划 + 推理循环（Thought -> Action -> Observation）

核心认知（带着读代码）：
  1. Agent = Function Calling + 自主规划 + 显式推理(ReAct) + 停止判断。
     FC 是"单步执行"，Agent 是"给个目标，自己拆步骤、调工具、判断何时停"。
  2. ReAct = Reasoning + Acting 交替。模型先"想"(Thought)再"做"(Action)，
     看完结果(Observation)再想下一步，直到信息够给 Final Answer。
  3. 本文件用"纯 Prompt ReAct"（论文原版）：不用 FC 的 tools 参数，
     靠 system prompt 约束输出格式，自己解析文本。
     - 好处：Thought 是模型显式输出的文本，肉眼可见推理过程（教学最清晰）。
     - 代价：解析脆弱（模型格式飘了就出错）-> 工业上多用 FC 结构化版（LangChain 阶段用）。

对比 Code/test_function_calling.py：
  - FC 版：模型输出结构化 tool_call（Action 被结构化），Thought 藏模型内部（content 常为空）。
  - ReAct 版（本文件）：模型输出文本 Thought/Action/Observation，推理白盒可见。

用法：
  cd Code
  python test_agent.py
"""
import json
import os
import re
from openai import OpenAI

# ===== 0. 客户端（复用豆包配置，和 test_function_calling.py 一致）=====
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
)
CHAT_MODEL = "glm-5.2"


# ===== 1. 工具实现（复用 Function Calling 的两个工具）=====
def get_weather(city: str) -> str:
    """模拟天气查询（同 FC demo）。"""
    fake = {"上海": "32℃，晴", "北京": "30℃，多云", "广州": "35℃，雷阵雨"}
    return fake.get(city, f"{city}：28℃，晴")


def calculate(expression: str) -> str:
    """精确计算（同 FC demo，受限 eval）。生产环境别用 eval。"""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算失败: {e}"


# 工具派发表（同 FC demo：模型只说名字，代码靠这张表路由到真正函数）
TOOL_REGISTRY = {"get_weather": get_weather, "calculate": calculate}


# ===== 2. ReAct 的系统提示词（Agent 的"大脑"）=====
# 关键认知：纯 Prompt ReAct 不用 FC 的 tools 参数，而是把工具说明写进 prompt，
# 靠"格式约定 + few-shot 例子"让模型输出可解析的 Thought/Action/Action Input 文本。
# 这份 prompt 的质量直接决定 Agent 行不行——它就是 Agent 的"大脑"。
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


# 解析正则：兼容中英文冒号（模型可能输出 "Action:" 或 "Action："）
_RE_THOUGHT = re.compile(r"Thought[：:]\s*(.+?)(?=\nAction[：:])", re.DOTALL)
_RE_ACTION = re.compile(r"Action[：:]\s*(.+)")
_RE_INPUT = re.compile(r"Action Input[：:]\s*(.+)", re.DOTALL)


# ===== 3. ReAct 循环（Agent 的心脏）=====
def run_agent(user_query: str, max_steps: int = 10):
    """一次 Agent 运行：Thought->Action->Observation 循环，直到 Final Answer 或达上限。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]
    print(f"\n{'#'*60}\n# 用户: {user_query}\n{'#'*60}")

    for step in range(1, max_steps + 1):
        print(f"\n--- 第 {step} 步 ---")
        # 不带 tools 参数！纯文本对话，靠 system prompt 约束输出格式
        resp = client.chat.completions.create(model=CHAT_MODEL, messages=messages)
        text = resp.choices[0].message.content.strip()
        # 模型这一步的输出必须记回 messages，否则它不知道自己上步说过啥（短期记忆）
        messages.append({"role": "assistant", "content": text})

        # ① 打印 Thought（ReAct 的精髓：让推理过程白盒可见）
        m_thought = _RE_THOUGHT.search(text)
        if m_thought:
            print(f"💭 Thought: {m_thought.group(1).strip()}")

        # ② 解析 Action
        m_action = _RE_ACTION.search(text)
        if not m_action:
            print(f"⚠️ 没解析到 Action，原始输出：\n{text}")
            break
        action = m_action.group(1).strip()

        # ③ 停止判断：Final Answer -> 任务完成
        if action.lower().startswith("final answer"):
            m_input = _RE_INPUT.search(text)
            final = m_input.group(1).strip() if m_input else text
            print(f"✅ 最终答案: {final}")
            return final

        # ④ 执行工具
        m_input = _RE_INPUT.search(text)
        if not m_input:
            print(f"⚠️ 缺 Action Input，原始输出：\n{text}")
            break
        raw_input = m_input.group(1).strip()
        try:
            args = json.loads(raw_input)
        except json.JSONDecodeError:
            # 纯 Prompt ReAct 的脆弱点：模型格式飘了就解析失败。
            # 工业版用 FC 的 tools 参数规避（结构化输出，不靠解析文本）。
            observation = f"参数不是合法 JSON：{raw_input}，请严格输出 JSON。"
        else:
            print(f"🔧 Action: {action}({args})")
            fn = TOOL_REGISTRY.get(action)
            if not fn:
                observation = f"未知工具 '{action}'，可用：{list(TOOL_REGISTRY)}"
            else:
                observation = fn(**args)
        print(f"👁️ Observation: {observation}")

        # ⑤ 把 Observation 拼回 messages（用 user 角色模拟"环境反馈"）
        # API 没有 observation 角色，惯例用 user 塞 "Observation: ..." 让模型看到工具结果
        messages.append({"role": "user", "content": f"Observation: {observation}"})

    print("⚠️ 达到最大步数仍未给出最终答案（可能陷入循环或格式持续出错）")


if __name__ == "__main__":
    # 任务：多步规划——查三城天气，找最热，算与最冷的差值。
    # 对比 FC：FC 可能一轮并行查3城（被动响应）；ReAct 是推理驱动、逐步行动（主动规划）。
    # 跑起来你会看到模型一步步 Thought/Action/Observation，最后 Final Answer。
    run_agent(
        "我想去中国最热的城市旅游，候选是上海、北京、广州。"
        "帮我查这三个城市的天气，找出最热的，并算出它比最冷的高多少度。"
    )

    # 想测"不需要工具时直接 Final Answer"的停止判断，取消注释：
    # run_agent("你好，你是谁？能帮我做什么？")
