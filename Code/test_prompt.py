"""
Prompt Engineering 实战 demo
对比 bad / good prompt 的输出差异，演示 6 个核心技巧：
  1. 角色设定 Role
  2. 结构化指令 Structured Instruction
  3. Few-shot 少样本
  4. CoT 思维链
  5. 结构化输出 JSON
  6. Rule 规则约束

用法：
  python test_prompt.py            # 跑全部
  python test_prompt.py role       # 只跑角色设定
  python test_prompt.py struct     # 只跑结构化指令
  python test_prompt.py fewshot    # 只跑 Few-shot
  python test_prompt.py cot        # 只跑 CoT
  python test_prompt.py json       # 只跑结构化输出
  python test_prompt.py rule       # 只跑 Rule
"""
import sys
import json
import os
from openai import OpenAI

# ===== 0. 初始化客户端（复用豆包配置，和 test.py 一致）=====
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
)
CHAT_MODEL = "glm-5.2"


def chat(prompt: str, temperature: float = 0.3) -> str:
    """封装一次对话调用，返回模型回复文本。temperature 低一点，让 bad/good 对比更稳定可复现。"""
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


def show(title: str, prompt: str, output: str):
    """打印一组 prompt + output，方便肉眼对比。"""
    print(f"\n{'='*60}")
    print(f"【{title}】")
    print(f"{'-'*60}")
    print(f"Prompt:\n{prompt}")
    print(f"{'-'*60}")
    print(f"输出:\n{output}")
    print(f"{'='*60}")


# ===== 1. 技巧1：角色设定 Role =====
def demo_role():
    """同一件事：介绍 React。无角色 vs 给角色（专家 + 受众）。"""
    print("\n\n########## 技巧1：角色设定 Role ##########")

    bad = "帮我写一段介绍 React 的文字。"
    show("Bad 无角色", bad, chat(bad))

    good = (
        "你是一位有 10 年经验的前端技术专家。"
        "请向一个刚学完 JavaScript 的初学者介绍 React，"
        "重点讲\"为什么要用 React\"，用生活化的比喻，避免堆术语。"
    )
    show("Good 有角色 + 受众", good, chat(good))


# ===== 2. 技巧2：结构化指令 =====
def demo_structured():
    """分析用户评论。揉成一团 vs 分层结构化。"""
    print("\n\n########## 技巧2：结构化指令 ##########")
    comment = "耳机音质还行，但戴了半小时耳朵就疼，客服回复也很慢。"

    bad = f"分析一下这条评论，告诉我情绪和提到的问题：\"{comment}\""
    show("Bad 揉成一团", bad, chat(bad))

    good = f"""【任务】分析用户评论，输出情绪类别和具体问题。
【输入】"{comment}"
【输出格式】
  - 情绪：正面/负面/中性
  - 问题：逐条列出，没有则写"无"
【约束】只基于评论内容判断，不要脑补。"""
    show("Good 分层结构化", good, chat(good))


# ===== 3. 技巧3：Few-shot 少样本 =====
def demo_fewshot():
    """情感分类。只讲规则（Zero-shot）vs 给例子（Few-shot）。
    故意选一条混合情绪的评论，看哪种写法更稳。"""
    print("\n\n########## 技巧3：Few-shot 少样本 ##########")
    comment = "包装挺好看，就是价格有点贵。"

    bad = f"判断下面评论的情感，输出 正面/负面/中性：\n\"{comment}\""
    show("Bad Zero-shot 只讲规则", bad, chat(bad))

    good = f"""判断评论的情感，输出 正面/负面/中性。

评论：这个耳机音质绝了，戴一天也不累。
情感：正面

评论：用了两天就坏了，客服还不理人。
情感：负面

评论：今天到的货，还没拆。
情感：中性

评论：{comment}
情感："""
    show("Good Few-shot 给例子", good, chat(good))


# ===== 4. 技巧4：CoT 思维链 =====
def demo_cot():
    """经典推理题。直接答（容易凭直觉答错）vs 一步一步思考。
    正确答案是 5 分钟：1 台机器 5 分钟做 1 个零件，100 台并行也是 5 分钟做 100 个。"""
    print("\n\n########## 技巧4：CoT 思维链 ##########")
    question = "如果 5 台机器 5 分钟能做 5 个零件，那么 100 台机器做 100 个零件需要几分钟？"

    bad = question
    show("Bad 直接答（凭直觉容易答 100）", bad, chat(bad))

    good = f"{question}\n\n让我们一步一步思考。"
    show("Good CoT（一步一步思考）", good, chat(good))


# ===== 5. 技巧5：结构化输出（JSON）=====
def _strip_json(text: str) -> str:
    """模型有时爱用 ```json ... ``` 包裹，剥掉再解析。"""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    return text.strip()


def demo_json():
    """从评论抽取信息。自由文本（无法解析）vs JSON（可被程序解析）。"""
    print("\n\n########## 技巧5：结构化输出 ##########")
    comment = "我上周在你们上海旗舰店买的蓝牙耳机，型号 AirPro 3，用了三天左耳就没声音了，要求换货。"

    bad = f"请分析这条用户评论：\n\"{comment}\""
    show("Bad 自由文本（无法解析）", bad, chat(bad))

    good = f"""从用户评论中抽取信息，输出 JSON。
【输入】"{comment}"
【输出格式】只输出 JSON，不要 markdown 代码块，不要任何解释：
{{"产品": "", "型号": "", "购买地点": "", "问题": "", "诉求": ""}}"""
    output = chat(good)
    show("Good JSON（可解析）", good, output)

    # 验证：能否被程序解析--这才是结构化输出的目的
    try:
        data = json.loads(_strip_json(output))
        print(f"\n  ✅ json.loads 解析成功，程序可直接使用：")
        for k, v in data.items():
            print(f"     {k}: {v}")
    except Exception as e:
        print(f"\n  ❌ 解析失败：{e}（这就是为什么解析必须兜底）")


# ===== 6. 技巧6：Rule 规则约束 =====
def demo_rule():
    """客服回复。无规则（可能超长/乱承诺）vs 有硬约束。"""
    print("\n\n########## 技巧6：Rule 规则约束 ##########")
    complaint = "我花 899 买的耳机用了三天就坏了，你们什么垃圾质量！必须给我退款！"

    bad = f"你是客服，请回复这位投诉的用户：\n\"{complaint}\""
    show("Bad 无规则（可能超长/乱承诺）", bad, chat(bad))

    good = f"""你是客服，回复这位投诉的用户。
【输入】"{complaint}"
【规则】
- 必须先道歉，再给方案。
- 回复不超过 50 字。
- 禁止承诺退款（只能承诺核实后处理）。
- 禁止使用 markdown 格式。
【回复】"""
    show("Good 有 Rule（硬约束）", good, chat(good))


# ===== 7. 入口 =====
def main():
    demos = {
        "role": demo_role,
        "struct": demo_structured,
        "fewshot": demo_fewshot,
        "cot": demo_cot,
        "json": demo_json,
        "rule": demo_rule,
    }
    if len(sys.argv) > 1:
        key = sys.argv[1]
        if key == "all" or key not in demos:
            for d in demos.values():
                d()
        else:
            demos[key]()
    else:
        for d in demos.values():
            d()


if __name__ == "__main__":
    main()
