"""
每日科技简报生成器（多 Agent 版）
- 协作模式：并行搜集 + 串行加工（整体层级模式）
- 分派节点 = 真调度：用 LLM 根据 topic 从源池动态选源（不再是写死的输入）
- 搜集节点并行执行，结果用 reducer(operator.add) 累积
- 汇总 -> 写简报（串行）
"""
import os
import operator
from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool


# ===== 1. State：raw_news 用 reducer 累积，支持并行写入 =====
class BriefState(TypedDict):
    topic: str
    sources: List[str]
    raw_news: Annotated[List[str], operator.add]   # ★ 并行搜集结果累积，不覆盖
    summary: str
    brief: str


# ===== 2. 分派节点（真调度）+ 条件边路由：动态扇出 =====
# 候选源池（真实场景是所有可用资讯源）
SOURCE_POOL = ["36kr", "huxiu", "techcrunch", "机器之心", "量子位", "InfoQ"]


@tool
def select_sources(sources: List[str]) -> List[str]:
    """根据今日主题，从候选源池中选择 2-4 个最相关的资讯源。只能从候选池选。"""
    # 这个工具只是让 LLM 结构化输出选择，本身不做实事
    return sources


def dispatch_node(state: BriefState):
    """真调度：用 LLM 根据 topic 从源池动态选择要搜的源。
    从'假调度'升级而来：调度者本身是个会思考的 Agent，而非读写死的输入。"""
    prompt = f"""今日主题：{state["topic"]}

候选源池：{SOURCE_POOL}

请根据主题选择 2-4 个最相关的资讯源，调用 select_sources 工具返回你的选择（只能从候选池选）。"""
    try:
        reply = model.bind_tools([select_sources]).invoke(prompt)
        if reply.tool_calls:
            chosen = reply.tool_calls[0]["args"]["sources"]
            chosen = [s for s in chosen if s in SOURCE_POOL]   # 过滤 LLM 幻觉选的非法源
            if not chosen:
                chosen = SOURCE_POOL[:3]
        else:
            chosen = SOURCE_POOL[:3]
    except Exception as e:
        print(f"[warn] 调度 LLM 失败（{type(e).__name__}），用默认源")
        chosen = SOURCE_POOL[:3]
    print(f"[调度] 主题={state['topic']} -> LLM 选中源：{chosen}")
    return {"sources": chosen}


def route_dispatch(state: BriefState) -> list[Send]:
    """条件边路由：返回 Send 列表 = 动态扇出，每个 source 派一个并行搜集任务。
    ★ 这里一行都不用改：它只管读 sources 发 Send，不关心 sources 哪来的。
    调度决策（智能，在 dispatch_node）与扇出执行（机械，在这里）解耦。"""
    return [
        Send("collect", {"source": s, "topic": state["topic"]})
        for s in state["sources"]
    ]


# ===== 3. 搜集节点：每个并行实例处理一个源 =====
def collect_node(state: dict):
    """注意：这里参数是 dict 不是 BriefState。
    因为 Send 传进来的是子 payload {"source", "topic"}，不是完整主 state。"""
    source = state["source"]
    topic = state["topic"]
    # mock：对任意源返回一条模拟资讯（真实场景换爬虫 / 搜索 API）
    # 通用化：真调度后源由 LLM 选，无法预先写死每个源的 mock
    return {"raw_news": [f"[{source}] {topic}领域本周关键动态：头部玩家加速布局，多项新进展值得关注"]}


# 模型（复用 ReAct demo 的配置，写简报环节用）
model = ChatOpenAI(
    model="glm-5.2",
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
)


# ===== 4. 汇总节点（串行加工第一步）：拼合原始资讯 =====
def summary_node(state: BriefState):
    """把并行的原始资讯拼成一个文本块。真实场景可在此去重 / 分类 / 排序。"""
    joined = "\n".join(f"- {n}" for n in state["raw_news"])
    return {"summary": joined}


# ===== 5. 写简报节点（串行加工第二步）：调 LLM 成稿 =====
def brief_node(state: BriefState):
    prompt = f"""你是科技简报编辑。基于以下资讯生成每日简报，要求：
1. 一句话标题
2. 3-5 个要点（每点一行）
3. 一段总结（2-3 句）

资讯：
{state["summary"]}
"""
    try:
        reply = model.invoke(prompt)
        return {"brief": reply.content}
    except Exception as e:
        # 兜底：环境连不上 LLM 时用模板生成，保证多 Agent 架构可演示
        print(f"[warn] LLM 调用失败（{type(e).__name__}），启用模板兜底以演示架构闭环")
        lines = state["summary"].split("\n")
        bullets = "\n".join(lines)
        return {"brief": f"【每日 AI 简报（模板兜底）】\n\n今日要点：\n{bullets}\n\n总结：本日共收录 {len(lines)} 条 AI 相关资讯。"}


# ===== 6. 拼图：节点 + 边 =====
graph = StateGraph(BriefState)
graph.add_node("dispatch", dispatch_node)
graph.add_node("collect", collect_node)
graph.add_node("summary", summary_node)
graph.add_node("brief", brief_node)

graph.set_entry_point("dispatch")
# ★ dispatch -> collect 的扇出由条件边路由函数返回 Send 列表实现（动态，图结构里看不到这条边）
graph.add_conditional_edges("dispatch", route_dispatch)
graph.add_edge("collect", "summary")   # 多个并行 collect 汇聚到 summary（fan-in 屏障）
graph.add_edge("summary", "brief")     # 串行
graph.add_edge("brief", END)

app = graph.compile()


# ===== 7. 跑 =====
if __name__ == "__main__":
    try:
        result = app.invoke({
            "topic": "AI",      # ★ 只给主题，sources 由 dispatch 节点用 LLM 动态决定
            "raw_news": [],
        })

        print("\n===== 原始搜集 =====")
        for n in result["raw_news"]:
            print(n)
        print("\n===== 每日科技简报 =====")
        print(result["brief"])
    except Exception as e:
        print(f"[error] 运行失败：{type(e).__name__}: {e}")
