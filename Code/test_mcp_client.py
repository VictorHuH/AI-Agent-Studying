"""
MCP Client 实战 demo
从代码连接 MCP Server，发现并调用它的工具 -- 不经过任何 LLM，纯协议演示。

核心认知（带着这三点读代码）：
  1. Client 只需要知道"怎么启动 Server"（command + args），不需要 import Server 的代码。
     这就是"解耦"：工具实现和工具调用彻底分开，跨进程、跨语言都行。
  2. 协议流程四步：启动子进程 -> initialize() 握手 -> list_tools() 发现 -> call_tool() 调用。
  3. 把这个 Client 换成 Claude Desktop / Cursor / 你的 Agent，Server 一行不用改就能用。
     这就是 MCP 标准化的价值：M 个 Host + N 个 Server = M+N，不是 M×N。

运行方式：
  python test_mcp_client.py
  它会自动用 stdio 把 test_mcp_server.py 拉起成子进程，并调用其工具。
"""
import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Server 脚本路径（和本文件同目录）
SERVER_SCRIPT = Path(__file__).parent / "test_mcp_server.py"


async def main():
    # ① 告诉 Client "怎么启动 Server"：跑 python test_mcp_server.py
    # 关键：Client 不 import Server 代码，只起子进程 -- 这是解耦的本质。
    # command 用 sys.executable（当前 Python 解释器完整路径），Windows 下比 "python" 稳。
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
    )

    print("=" * 60)
    print("① 启动 MCP Server（stdio 子进程）并建立会话...")
    print("=" * 60)

    # stdio_client：async context manager，负责拉起 server 子进程、接好 stdio 管道
    async with stdio_client(server_params) as (read, write):
        # ClientSession：负责讲 JSON-RPC 协议（封包/解包/请求响应配对）
        async with ClientSession(read, write) as session:
            # ② 握手：初始化会话，交换协议版本 + 能力（capabilities）
            init_result = await session.initialize()
            server_info = init_result.serverInfo
            print(f"✅ 会话已初始化。Server: {server_info.name}")
            print(f"   协议版本: {init_result.protocolVersion}\n")

            # ③ 发现工具：list_tools 返回 server 暴露的所有工具
            tools_resp = await session.list_tools()
            tools = tools_resp.tools
            print(f"② 发现 {len(tools)} 个工具（list_tools）：")
            for t in tools:
                # description 第一行做摘要打印
                desc = (t.description or "").strip().splitlines()[0]
                print(f"   - {t.name}({', '.join(t.inputSchema.get('properties', {}).keys())})")
                print(f"     {desc}")
            print()

            # ④ 调用工具：call_tool(工具名, 参数字典)
            # 不经过 LLM，直接由我们的代码指定调哪个、传什么参数。
            # 真实场景里这一步由 LLM 决策（FC 的 tool_call），本 demo 先纯协议验证。
            cases = [
                ("get_weather", {"city": "上海"}),
                ("get_weather", {"city": "广州"}),
                ("calculate", {"expression": "1234 * 5678"}),
            ]
            print("③ 调用工具（call_tool）：")
            for name, args in cases:
                result = await session.call_tool(name, args)
                # result.content 是一个 list，元素是 TextContent / ImageContent 等
                text = result.content[0].text if result.content else "(无返回)"
                print(f"   🔧 call_tool({name}, {args})")
                print(f"      -> {text}")
            print()
            print("=" * 60)
            print("✅ MCP 协议闭环跑通：Client 发现并调用了 Server 的工具。")
            print("   把本 Client 换成 Claude Desktop/你的 Agent，Server 无需改动即可复用。")
            print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
