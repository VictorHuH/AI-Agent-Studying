---
name: learning-summary
display_name: 学习小结生成器
display_name_en: Learning Summary Generator
description: 当用户想要复盘学习内容、总结学习笔记、生成费曼式知识小结时使用。触发词：学习小结、复盘笔记、总结今天学的内容
description_zh: 把学习笔记或对话内容提炼成结构化小结：核心概念、关键要点、费曼式一句话解释、待巩固清单
description_en: Turn study notes into a structured summary covering key concepts, bullet points, a one-line Feynman explanation, and a review checklist
category: writing
version: 1.0.0
author: Victor
---

# 学习小结生成器

当用户想要复盘学习内容、总结学习笔记时，按以下步骤执行：

## 步骤

1. **收集材料**：让用户提供笔记文件路径、粘贴的内容，或指定本次对话中讨论过的知识点。材料不足时先提问，不要凭空编造。
2. **提炼核心概念**：从材料中找出 3~5 个核心概念，每个用一句话概括「它是什么、解决什么问题」。
3. **生成小结**：按 @references/summary-template.md 的固定结构输出，包含四个部分：
   - 🎯 核心概念（每个概念一句话）
   - 🔑 关键要点（分条列出，控制在 7 条以内）
   - 💡 费曼检验（用一段大白话解释给外行听，不用术语）
   - 📌 待巩固（列出没吃透、需要下次复习的点）
4. **控制篇幅**：整个小结不超过 500 字，宁短勿长。
5. **输出建议**：结尾询问用户是否需要生成 Anki 卡片格式或思维导图大纲（不主动生成）。

## 约束

- 只基于用户提供的材料总结，不补充材料之外的知识点
- 费曼检验部分禁止使用任何专业术语
