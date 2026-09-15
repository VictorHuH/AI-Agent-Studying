"""学习卡片管理 CLI（WorkBuddy flashcards-cli 连接器）。

用法:
    flashcards add <front> <back> [--tag TAG]   添加一张卡片
    flashcards list [--tag TAG]                 列出卡片（可按标签过滤）
    flashcards random                            随机抽一张（只出问题）
    flashcards reveal <id>                       查看指定卡片的答案

业务结果输出 JSON 到 stdout，错误信息输出到 stderr 并以非 0 退出码结束。
"""
import argparse
import json
import random
import sys
from pathlib import Path

# ponytail: Windows 控制台默认 GBK，不强制 UTF-8 会导致中文乱码
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

DB = Path.home() / ".workbuddy-flashcards.json"


def load():
    return json.loads(DB.read_text(encoding="utf-8")) if DB.exists() else []


def save(cards):
    DB.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")


def die(msg):
    print(f"错误: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="学习卡片管理：添加、列出、抽卡自测")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="添加一张卡片")
    a.add_argument("front", help="卡片正面：问题")
    a.add_argument("back", help="卡片背面：答案")
    a.add_argument("--tag", default="", help="标签，用于分类（如 RAG）")

    l = sub.add_parser("list", help="列出所有卡片")
    l.add_argument("--tag", default="", help="只显示该标签的卡片")

    sub.add_parser("random", help="随机抽一张卡片（只返回问题）")

    r = sub.add_parser("reveal", help="查看指定卡片的答案")
    r.add_argument("id", type=int, help="卡片编号")

    args = p.parse_args()
    cards = load()

    if args.cmd == "add":
        cards.append({"id": len(cards) + 1, "front": args.front,
                      "back": args.back, "tag": args.tag})
        save(cards)
        print(json.dumps({"ok": True, "id": len(cards), "total": len(cards)},
                         ensure_ascii=False))
    elif args.cmd == "list":
        matched = [c for c in cards if not args.tag or c["tag"] == args.tag]
        if not matched:
            die(args.tag and f"没有标签为「{args.tag}」的卡片" or "卡片库为空")
        print(json.dumps(matched, ensure_ascii=False, indent=2))
    elif args.cmd == "random":
        if not cards:
            die("卡片库为空，请先添加卡片")
        c = random.choice(cards)
        print(json.dumps({"id": c["id"], "front": c["front"]}, ensure_ascii=False))
    elif args.cmd == "reveal":
        c = next((x for x in cards if x["id"] == args.id), None)
        if not c:
            die(f"不存在编号为 {args.id} 的卡片")
        print(json.dumps(c, ensure_ascii=False))


if __name__ == "__main__":
    main()
