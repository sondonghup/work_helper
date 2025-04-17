from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from datetime import datetime, timedelta
import pytz

# pytz 설치 필요: pip install pytz

server_params = StdioServerParameters(
    command="/private/var/folders/9m/8c8yxc_55fd8czwpk611j6080000gn/T/AppTranslocation/3E61EC49-B551-4875-BD8D-C32E0E862F7D/d/iMCP.app/Contents/MacOS/imcp-server",  # Executable
)

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            await session.initialize()

            # 한국 시간대 설정
            korea_tz = pytz.timezone('Asia/Seoul')
            
            # 현재 시간 기준으로 이벤트 생성
            now = datetime.now(korea_tz)
            start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)  # 오늘 오전 9시
            end_time = start_time + timedelta(hours=1)  # 1시간 동안

            # ISO 형식으로 변환 (더 단순한 형식)
            start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%S%z")
            end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S%z")

            print(f"시작 시간: {start_iso}")
            print(f"종료 시간: {end_iso}")

            # 이벤트 생성
            result = await session.call_tool("createEvent", {
                "title": "손동협",
                "startDate": start_iso,
                "endDate": end_iso,
                "notes": "손동협 일정",
                "availability": "busy"
            })
            print(f"이벤트 생성 결과: {result}")

            # 생성된 이벤트 확인
            events = await session.call_tool("fetchEvents", {
                "startDate": start_iso,
                "endDate": end_iso
            })
            print(f"생성된 이벤트: {events}")

if __name__ == "__main__":
    import asyncio

    asyncio.run(run())