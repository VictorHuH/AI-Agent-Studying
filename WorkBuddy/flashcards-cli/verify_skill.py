"""SKILL.md 效果验收 harness（简版）。

原理：把 SKILL.md 正文当 system prompt，给模型一个 run_command 工具（FC），
模型只能靠"读说明书"学会用 flashcards CLI——和 WorkBuddy 里 AI 的处境一致。

断言（skill-used 式，只看命令序列，不评文本质量）：
  1. 先 add（参数含 front/back）
  2. 再 random（只出题），且 random 之后、用户回答之前不得 reveal
  3. 用户回答后 reveal（id 与 random 一致）
  4. 最终答案对照的是卡片 back 而非编造

用法: PYTHONUTF8=1 OPENAI_API_KEY=xxx python verify_skill.py
"""
import json
import os
import re
import subprocess
import sys
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")
CLI = os.path.join(os.path.dirname(__file__), "flashcards_cli.py")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
)
MODEL = "glm-5.2"

# system prompt = SKILL.md 正文（剥掉 frontmatter），模型看不见 CLI 源码
skill = open(os.path.join(os.path.dirname(__file__), "skills/flashcards/SKILL.md"),
             encoding="utf-8").read()
body = re.split(r"^---\s*$", skill, flags=re.M)[2].strip()

TOOLS = [{
    "type": "function",
    "function": {
        "name": "run_command",
        "description": "在用户机器上执行 flashcards 命令行工具并返回结果",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "完整命令，如 flashcards random"}},
            "required": ["command"],
        },
    },
}]


def execute(command: str) -> str:
    """把 'flashcards xxx' 翻译成本地 python 调用，其余原样返回错误。"""
    cmd = command.strip().replace("flashcards", f"{sys.executable} {CLI}", 1)
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8")
    return f"exit={r.returncode}\nstdout: {r.stdout.strip()}\nstderr: {r.stderr.strip()}"


def drive(messages):
    """FC 循环：模型出 tool_call -> 执行 -> 回填，直到输出最终文本。"""
    while True:
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto")
        m = resp.choices[0].message
        if m.tool_calls:
            for tc in m.tool_calls:
                result = execute(json.loads(tc.function.arguments)["command"])
                messages.append({"role": "assistant",
                                 "tool_calls": [{"id": tc.id, "type": "function",
                                                 "function": {"name": "run_command",
                                                              "arguments": tc.function.arguments}}]})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
            continue
        return m.content


# ===== 场景：记一张卡 + 抽卡考我 =====
messages = [
    {"role": "system", "content": body},
    {"role": "user", "content": "帮我记一张卡片：Skill 的物理形态是什么？答案是「一个文件夹：SKILL.md + scripts + references + templates」，标签 Skill。然后抽卡考考我。"},
]
final1 = drive(messages)

# 模拟用户回答（故意答半对，看 AI 能否对照卡片评判）
messages.append({"role": "user", "content": "我的回答：就是一个 SKILL.md 文件。"})
final2 = drive(messages)
print("=== 最终回复 ===")
print(final2)

# ===== 断言：从 tool 调用序列回放 =====
calls = [json.loads(m["tool_calls"][0]["function"]["arguments"])["command"]
         for m in messages if m.get("tool_calls")]
print("\n=== 命令序列 ===")
for c in calls:
    print(" ", c)

ok = True
def check(cond, msg):
    global ok
    print(("✅" if cond else "❌"), msg)
    ok &= bool(cond)

check(any("add" in c for c in calls), "调用了 add 添加卡片")
check(any("random" in c for c in calls), "调用了 random 出题")
ids = [re.search(r"reveal (\d+)", c) for c in calls]
check(any(ids), "调用了 reveal 对答案")
rand_idx = next((i for i, c in enumerate(calls) if "random" in c), 99)
rev_idx = next((i for i, c in enumerate(calls) if "reveal" in c), -1)
check(rand_idx < rev_idx, "先 random 出题、后 reveal 对答案（未偷看）")
check(final2 and "SKILL.md" in final2 and ("scripts" in final2 or "还" in final2),
      "最终回复基于卡片内容对照评判")
print("\n结论:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
