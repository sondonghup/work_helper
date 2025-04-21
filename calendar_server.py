import asyncio

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from datetime import datetime, timedelta
import pytz

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

            start_date = datetime.now() + timedelta(days=2, hours=10)
            end_date = start_date + timedelta(hours=3)

            print(f"시작 시간: {start_date}")
            print(f"종료 시간: {end_date}")

            start_date = start_date.strftime("%Y-%m-%d %H:%M:%S")
            end_date = end_date.strftime("%Y-%m-%d %H:%M:%S")

            result = await session.call_tool(
                "create_event",
                arguments={
                    "event": {  # event 객체 안에 모든 인자를 넣습니다
                        "title": "Test Event",
                        "start_date": start_date,
                        "end_date": end_date,
                        "location": None,  # 선택적 필드
                        "notes": "hello",     # 선택적 필드
                        "calendar_name": "직장"  # 선택적 필드
                    }
                }
            )
            print(result)

if __name__ == "__main__":
    asyncio.run(run())