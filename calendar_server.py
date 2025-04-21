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

if __name__ == "__main__":
    asyncio.run(run())