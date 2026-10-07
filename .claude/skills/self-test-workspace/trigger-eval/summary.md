# self-test 触发质量评测 · 结果汇总

日期：2026-09-24 · 方法：subagent 只收用户原话，skill 仅以列表项存在，自报 SKILL_USED + 回复行为佐证 · 每条 1 次运行

## 正例组（应触发 self-test）— 7/7

| # | Query | 结果 |
|---|-------|------|
| 1 | 考我 RAG | ✅ self-test（发现两篇 RAG 笔记，先问考哪篇） |
| 2 | 自测一下 LangGraph | ✅ self-test |
| 3 | 出几道题检验 Prompt Engineering | ✅ self-test |
| 4 | 我 MCP 这章掌握没掌握，出6道题考考我（长口语无关键词） | ✅ self-test |
| 5 | 复习一下 Agent，你来提问我来答（完全换说法） | ✅ self-test（还追问是否含多Agent篇） |
| 6 | 检验一下我学没学会 CLI，考全部 | ✅ self-test |
| 7 | 考我一下 WorkBuddy连接器呗（口语+儿化） | ✅ self-test |

## 负例组（self-test 不该触发）— 7/7

| # | Query | 实际 | 判定 |
|---|-------|------|------|
| 8 | 总结一下我 MCP 这章学了什么 | none | ✅ 直接总结 |
| 9 | MCP 和 Function Calling 有什么区别？ | none | ✅ 直接问答 |
| 10 | 把今天调研的 promptfoo 整理进笔记 | record-tool | ✅ 正确路由给 record-tool，且未编造素材、先要素材 |
| 11 | 把笔记同步到 GitHub | git-upload | ✅ 正确路由（评测环境仅只读 git，未实际推送） |
| 12 | 帮我把 05-Agent.md 里三层记忆那段讲清楚点 | none | ✅ 直接讲解 |
| 13 | 给这段代码写个单元测试（"测试"字眼撞车） | none | ✅ 反问要代码 |
| 14 | 学完新的一站了，更新一下学习路线进度 | none | ✅ 追问依据，不凭空改 |

## 指标

- 漏触发率：0/7
- 误触发率：0/7
- 技能路由（三 skill 并存时的正确分派）：2/2（Q10→record-tool，Q11→git-upload）

## 结论与边界

- description 的"推"式写法（"不可跳过"+触发语枚举）在正例覆盖充分，未观察到误触发代价
- 每条仅 1 次运行、n=14；SKILL_USED 为自报，但与回复行为（先问范围、跑 extract_topics、先问后判）一致，可信度较高
- 负例中未包含"出两道题练练手"这类"练习 vs 自测"的语义边界 case
- 测试期间平台分类器多次超时（基础设施噪音，非 skill 问题）
