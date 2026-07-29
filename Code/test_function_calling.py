"""
Function Calling 实战 demo
演示完整循环：模型决策 -> 代码执行 -> 结果回填 -> 模型生成最终答案

核心认知（务必带着这三点读代码）：
  1. 模型自己不执行任何函数，只输出"调用请求"(tool_call)。真正执行的是下面的 Python 函数。
  2. 模型不一定每次都调工具。调不调是模型自主判断的（tool_choice="auto"）。
  3. 这是一个循环：模型可能连续调多个工具，直到它觉得信息够了才输出最终答案。

工具：
  - get_weather(city):  查实时天气（模拟数据）。补"模型不知道的实时信息"。
  - calculate(expression): 精确计算（真用 Python 算）。补"模型容易算错的精确数值"。

用法：
  python test_function_calling.py
"""
import json
import os
from openai import OpenAI

# ===== 0. 客户端（复用豆包配置，和 test_prompt.py 一致）=====
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
)
CHAT_MODEL = "glm-5.2"


# ===== 1. 工具的真实实现（这些是"我们的代码"会真正执行的函数）=====
def get_weather(city: str) -> str:
    """模拟天气查询。真实场景这里调天气 API（如和风天气/OpenWeather）。"""
    # 假数据，够 demo 用
    fake = {"上海": "32℃，晴", "北京": "30℃，多云", "广州": "35℃，雷阵雨"}
    return fake.get(city, f"{city}：28℃，晴")


def calculate(expression: str) -> str:
    """精确计算。模型自己算大数容易错，交给 Python。
    注意：demo 用受限 eval，生产环境别用 eval（有注入风险），用 ast.literal_eval 或专用库。"""
    try:
        # 限制 builtins，只允许纯数学运算
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算失败: {e}"


# 工具派发表：模型决策出"调哪个工具"后，代码靠这张表找到对应函数去执行
TOOL_REGISTRY = {
    "get_weather": get_weather,
    "calculate": calculate,
}


# ===== 2. 工具说明书（给模型看的 JSON Schema）=====
# 关键：模型只看这份说明书决策，它看不见上面的函数实现。
# description 写清楚"什么场景该用/不该用"，直接影响模型决策质量（相当于给工具写 Prompt）。
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的当前天气。用于查询实时天气信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如'北京'、'上海'"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "精确计算数学表达式。用于大数乘除、复杂运算等模型可能算错的场景。"
                "简单的加减法或两个数比大小不需要调用，模型自己能判断。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '1234*5678'、'(10+20)*3'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]


# ===== 3. 核心循环（Function Calling 的心脏）=====
def run_conversation(user_query: str, max_rounds: int = 5):
    """一次完整对话：可能经历多轮工具调用，直到模型给出最终文本回答。"""
    messages = [{"role": "user", "content": user_query}]
    print(f"\n{'#'*60}")
    print(f"# 用户: {user_query}")
    print(f"{'#'*60}")

    for round_num in range(1, max_rounds + 1):
        print(f"\n--- 第 {round_num} 轮 ---")

        # ① 模型决策：带着完整对话历史 + 工具说明书，问模型"下一步干啥"
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",  # auto = 模型自己决定调不调工具
        )
        msg = resp.choices[0].message

        # 如果模型没输出 tool_calls，说明它决定直接回答 -> 循环结束
        if not msg.tool_calls:
            print(f"✅ 模型最终回答:\n{msg.content}")
            return msg.content

        # 关键易错点：模型这一轮的 tool_call 消息必须原样加回 messages，
        # 否则下一轮 API 会报错（tool 结果找不到对应的 tool_call）。
        messages.append(msg.model_dump(exclude_none=True))

        # ② 代码逐个执行模型请求的工具（可能一次多个 = 批量并行调用）
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            args = json.loads(tc.function.arguments)  # 模型给的是 JSON 字符串，解析成 dict
            print(f"🔧 模型决策: 调用 {fn_name}({args})")

            fn = TOOL_REGISTRY[fn_name]
            result = fn(**args)  # 真正执行！模型只负责说，这里才是做
            print(f"   代码执行结果: {result}")

            # ③ 结果回填：用 role=tool 把执行结果喂回模型，tool_call_id 标明是哪次调用的返回
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result),
            })
        # 回填完进入下一轮，模型会基于工具结果继续决策：调更多工具，或给出最终答案

    print("⚠️ 达到最大轮数仍未结束（可能模型陷入循环）")


def chat_multi_turn():
    """多轮对话 demo：messages 跨轮复用 = 短期记忆。

    对比 run_conversation：那个每次新建 messages = 无状态、无记忆。
    这里把 messages 提到外层、跨多轮用户输入复用，模型就能记住上文。

    关键认知：API 无状态，"记忆"不是额外功能，就是把 messages 历史一直带着传。
    但它只能记住"上下文窗口内"的对话，会话结束或超窗口就忘 -- 长期记忆见 Agent 阶段。
    """
    messages = []  # 跨轮复用 = 短期记忆的物理载体
    queries = [
        "上海和北京，哪个城市今天更热？",
        "那广州呢？比这两个都热吗？",  # "这两个"靠记忆指代上文的上海+北京
    ]
    for q in queries:
        print(f"\n{'#'*60}\n# 用户: {q}\n{'#'*60}")
        messages.append({"role": "user", "content": q})

        for _ in range(1, 6):  # 最多 5 轮工具调用，防死循环
            resp = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=messages,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
            )
            msg = resp.choices[0].message
            # 关键：模型每轮输出（工具调用 OR 最终回答）都要记回 messages，
            # 否则下一轮模型不知道自己上轮说过啥。这是多轮对话 vs 单次的本质区别。
            messages.append(msg.model_dump(exclude_none=True))

            if not msg.tool_calls:
                print(f"✅ 模型: {msg.content}")
                break

            for tc in msg.tool_calls:
                fn = TOOL_REGISTRY[tc.function.name]
                args = json.loads(tc.function.arguments)
                result = fn(**args)
                print(f"🔧 {tc.function.name}({args}) -> {result}")
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})


if __name__ == "__main__":
    # 多轮对话：演示"短期记忆" = messages 跨轮复用
    # 第二句里的"这两个"能被理解，全靠 messages 存着第一轮的上海/北京上下文
    chat_multi_turn()

    # 想看单次无记忆版做对比，取消下面注释：
    # run_conversation("上海和北京，哪个城市今天更热？")
    # run_conversation("帮我算一下 1234 乘以 5678 等于多少？")
    # run_conversation("你好，你是谁？能帮我做什么？")
