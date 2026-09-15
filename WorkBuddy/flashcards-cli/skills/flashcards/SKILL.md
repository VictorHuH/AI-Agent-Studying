---
name: flashcards-cli
description: 当用户想要添加学习卡片、复习卡片、随机抽卡自测时使用 flashcards 命令行工具。触发词：记卡片、学习卡片、抽卡、考考我
description_zh: 通过 flashcards 命令行工具管理学习卡片库——添加、按标签浏览、随机抽卡自测
description_en: Manage a study flashcard library via the flashcards CLI with add, browse, and random draw for self-testing
category: productivity
version: 1.0.0
author: Victor
---

# flashcards CLI 使用说明

flashcards 是一个学习卡片命令行工具，所有业务命令输出 JSON 到 stdout，错误信息输出到 stderr 且退出码非 0。

## 命令说明

### `flashcards add <front> <back> [--tag TAG]`
添加卡片。front=问题，back=答案，--tag 可选（主题标签，如 RAG）。
用户说"帮我记一张卡片：XXX"时调用，问题拆给 front、答案拆给 back。
返回示例：`{"ok": true, "id": 2, "total": 2}`

### `flashcards list [--tag TAG]`
列出卡片。--tag 只返回该标签；不带参数返回全部。
返回 JSON 数组，每项含 `id`、`front`、`back`、`tag`。

### `flashcards random`
随机抽一张自测卡，只返回 `{"id": 1, "front": "..."}`，不含答案。
用户说"考考我""抽张卡"时调用。

### `flashcards reveal <id>`
查看指定编号卡片的完整内容（含答案）。抽卡自测的第三步用它对答案。

## 使用流程（抽卡自测）

1. 执行 `flashcards random`，把问题原样抛给用户，不给任何提示
2. 等用户回答后，执行 `flashcards reveal <id>`（id 来自上一步结果）
3. 对照答案评判：答错时给出正确答案和卡片原文；答对时确认并鼓励继续

## 错误场景与退出码

| 退出码 | 场景 | 处理方式 |
| --- | --- | --- |
| 1 + "卡片库为空" | random 时无卡片 | 引导用户先添加卡片 |
| 1 + "没有标签为..." | list 过滤无结果 | 去掉 --tag 重新 list 全部 |
| 1 + "不存在编号..." | reveal 的 id 无效 | 重新 random 获取有效 id |
| 2 | 参数格式错误 | 检查参数后重试 |

## 约束

- 卡片内容只来自用户口述，不主动替用户编造卡片
- random 之后、用户回答之前，不得执行 reveal 提前看答案
- 标签由用户指定，不要自行发明新标签
