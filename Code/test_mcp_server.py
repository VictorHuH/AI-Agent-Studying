"""
MCP Server 实战 demo
把 FC 阶段的两个工具（get_weather / calculate）改造成标准 MCP Server。

核心对比（务必带着这个对比读代码）：
  FC demo (test_function_calling.py)：
    - 手写 TOOLS_SCHEMA（JSON Schema，给模型看）
    - 手写 TOOL_REGISTRY（函数派发表，给代码用）
    - schema 和函数实现分散在两处，得手动保持一致
  MCP Server (本文件)：
    - @mcp.tool() 装饰器：函数本身就是工具，schema 从类型注解自动生成
    - docstring 就是给模型看的 description（和 FC 一样：给工具写 Prompt）
    - 工具独立成进程，任何 MCP Client（任何 Host）都能发现并调用
    - "写一次工具，到处可用" -- 这就是标准化的价值

运行方式：
  本文件不直接跑看输出，它是一个"被调用的服务"。
  由 test_mcp_client.py 通过 stdio 把它当子进程拉起，再调用它的工具。
  （也可用官方调试器：npx @modelcontextprotocol/inspector python test_mcp_server.py）
"""
from mcp.server.fastmcp import FastMCP

# 创建一个 MCP Server 实例。name 是给 Client/Host 看的服务名。
mcp = FastMCP("studying-mcp-server")


# ===== 工具 1：查天气（和 FC demo 同款假数据）=====
# 对比 FC：原来要手写一大段 JSON Schema 描述 city 参数。
# 现在 FastMCP 从函数签名（city: str）自动生成 schema，
# docstring 自动成为给模型看的 description（决定模型决策质量，和 FC 同理）。
@mcp.tool()
def get_weather(city: str) -> str:
    """获取指定城市的当前天气。用于查询实时天气信息。

    参数 city：城市名，如 '北京'、'上海'。
    """
    fake = {"上海": "32℃，晴", "北京": "30℃，多云", "广州": "35℃，雷阵雨"}
    return fake.get(city, f"{city}：28℃，晴")


# ===== 工具 2：精确计算（和 FC demo 同款，受限 eval）=====
@mcp.tool()
def calculate(expression: str) -> str:
    """精确计算数学表达式。用于大数乘除、复杂运算等模型可能算错的场景。

    简单加减法或两数比大小不需要调用，模型自己能判断。
    参数 expression：数学表达式，如 '1234*5678'、'(10+20)*3'。
    """
    try:
        # 限制 builtins，只允许纯数学运算。生产环境别用 eval，这里教学用。
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算失败: {e}"


if __name__ == "__main__":
    # stdio 传输：server 通过标准输入/输出和 client 通信（JSON-RPC over stdio）。
    # 本地最简传输，教学首选；远程用 Streamable HTTP：mcp.run(transport="streamable-http")
    mcp.run(transport="stdio")
