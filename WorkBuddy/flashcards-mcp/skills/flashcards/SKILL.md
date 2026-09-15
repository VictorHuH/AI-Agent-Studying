---
name: flashcards
description: 当用户想要添加学习卡片、复习卡片、随机抽卡自测时使用。触发词：记卡片、学习卡片、抽卡、考考我
description_zh: 管理学习卡片库——添加、按标签浏览、随机抽卡自测
description_en: Manage a study flashcard library with add, browse, and random draw for self-testing
category: productivity
version: 1.0.0
author: Victor
---

# 学习卡片使用说明

本连接器通过 MCP Server（stdio）提供 3 个工具，按用户意图选择调用。

## 工具说明

### add_card(front, back, tag="")
添加卡片。front=问题，back=答案，tag 可选（建议用主题如 RAG、Agent）。
用户说"帮我记一张卡片：XXX"时调用，把问题拆成 front、答案拆成 back。

### list_cards(tag="")
列出卡片。带 tag 只返回该标签，不带返回全部。
用户说"看看我记过哪些卡"或"列出 RAG 的卡片"时调用。

### random_card()
随机抽一张自测卡。只返回正面问题。
用户说"考考我""抽张卡"时调用。

## 使用流程（抽卡自测）

1. 调 random_card() 拿到问题，原样抛给用户，不给任何提示
2. 等用户回答后，调 list_cards() 找到对应卡片的 back，对照评判
3. 用户答错时给出正确答案和卡片原文；答对时确认并鼓励继续

## 约束

- 卡片内容只来自用户口述，不主动替用户编造卡片
- random_card() 之后不要立刻泄露答案
- 标签由用户指定，不要自行发明新标签
