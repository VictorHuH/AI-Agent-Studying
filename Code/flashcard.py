"""学习卡片管理 CLI。

用法:
    python flashcard.py add <question> <answer>   添加一张卡片
    python flashcard.py list [--tag 关键字]       列出卡片
"""
import argparse
import json
import sys
from pathlib import Path

# ponytail: Windows 控制台默认 GBK，不强制 UTF-8 会导致中文乱码
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

DB = Path(__file__).parent / "flashcards.json"


def load():
    return json.loads(DB.read_text(encoding="utf-8")) if DB.exists() else []


def save(cards):
    DB.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description="学习卡片管理：添加、列出、搜索卡片")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="添加一张卡片")
    a.add_argument("question", help="卡片正面：问题")
    a.add_argument("answer", help="卡片背面：答案")

    l = sub.add_parser("list", help="列出所有卡片")
    l.add_argument("--tag", help="只显示问题中包含该关键字的卡片")

    args = p.parse_args()
    cards = load()

    if args.cmd == "add":
        cards.append({"question": args.question, "answer": args.answer})
        save(cards)
        print(f"已添加第 {len(cards)} 张卡片")
    else:
        matched = [c for c in cards if args.tag in c["question"] or args.tag in c["answer"]] if args.tag else cards
        if not matched:
            print("没有找到卡片", file=sys.stderr)
            sys.exit(1)
        for c in matched:
            print(f"Q: {c['question']}\nA: {c['answer']}\n")
        print(f"共 {len(matched)} 张卡片", file=sys.stderr)


if __name__ == "__main__":
    main()
