import asyncio

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["apple_mcp.py"],
)

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(
            read, write) as session:

            await session.initialize()

            resources = await session.list_resources()
            print(resources)

            tools = await session.list_tools()
            print(tools)

            print(f"===========================================")

            result = await session.call_tool(
                "create_event",
                arguments={
                    "event": {  # event 객체 안에 모든 인자를 넣습니다
                        "title": "Test Event",
                        "start_date": "2025-04-22T09:00:00+0900",
                        "end_date": "2025-04-22T10:00:00+0900",
                        "location": None,  # 선택적 필드
                        "notes": None,     # 선택적 필드
                        "calendar_name": "스케쥴러"  # 선택적 필드
                    }
                }
            )
            print(result)

if __name__ == "__main__":
    asyncio.run(run())