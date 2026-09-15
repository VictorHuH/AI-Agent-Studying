"""学习卡片 MCP Server（stdio）

WorkBuddy 连接器 flashcards 的 MCP 实现。
三个工具：add_card / list_cards / random_card，JSON 文件持久化。
"""

import json
import os
import random
import sys

from mcp.server.fastmcp import FastMCP

# Windows GBK 防乱码
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

DB_PATH = os.path.join(os.path.expanduser("~"), ".workbuddy-flashcards.json")


def _load():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def _save(cards):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)


mcp = FastMCP("flashcards")


@mcp.tool()
def add_card(front: str, back: str, tag: str = "") -> str:
    """添加一张学习卡片。

    Args:
        front: 卡片正面，即问题（如 "RAG 的三个步骤？"）
        back: 卡片背面，即答案
        tag: 可选标签，用于分类（如 "RAG"、"Agent"）
    """
    cards = _load()
    cards.append({"id": len(cards) + 1, "front": front, "back": back, "tag": tag})
    _save(cards)
    return f"已添加第 {len(cards)} 张卡片：{front}"


@mcp.tool()
def list_cards(tag: str = "") -> str:
    """列出学习卡片。可按标签过滤，不传标签列出全部。"""
    cards = _load()
    if tag:
        cards = [c for c in cards if c["tag"] == tag]
    if not cards:
        return tag and f"没有标签为「{tag}」的卡片" or "卡片库为空"
    return "\n".join(
        f'{c["id"]}. [{c["tag"] or "未分类"}] {c["front"]} -> {c["back"]}'
        for c in cards
    )


@mcp.tool()
def random_card() -> str:
    """随机抽一张卡片用于自测。只返回正面，用户答完再由 AI 对照卡片库评判。"""
    cards = _load()
    if not cards:
        return "卡片库为空，先让我添加几张卡片吧"
    c = random.choice(cards)
    return f'抽到第 {c["id"]} 张：{c["front"]}（想好了再说，我来对答案）'


if __name__ == "__main__":
    mcp.run()
