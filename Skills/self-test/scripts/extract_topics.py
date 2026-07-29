"""从 Markdown 学习笔记提取所有标题作为考点清单。

这是 Skill 的【工具层】：确定性代码，干 LLM 不擅长的精确活（解析、计数）。
LLM 负责出题的智能，脚本负责把笔记结构化成考点 -- 工具补短板，不代替思考。

用法:
    python extract_topics.py <笔记路径>
"""
import sys
import re


def extract_topics(md_text):
    """提取 markdown 标题行，返回 [(level, title), ...]。

    只认 ATX 风格标题（# 开头），不认 Setext 风格（下划线 ===）。
    大多数学习笔记都用 ATX，够用。
    """
    topics = []
    for line in md_text.splitlines():
        m = re.match(r'^(#{1,6})\s+(.+?)\s*$', line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            topics.append((level, title))
    return topics


def main():
    if len(sys.argv) < 2:
        print("用法: python extract_topics.py <笔记路径>")
        sys.exit(1)

    path = sys.argv[1]
    # Windows 中文环境，显式指定 utf-8，避免默认 gbk 报错
    with open(path, encoding='utf-8') as f:
        text = f.read()

    topics = extract_topics(text)
    if not topics:
        print("（该笔记没有标题，可能是纯文本。请直接出概念题。）")
        return

    print(f"考点清单（共 {len(topics)} 个标题）：\n")
    for level, title in topics:
        indent = "  " * (level - 1)
        print(f"{indent}H{level}  {title}")


if __name__ == "__main__":
    main()
