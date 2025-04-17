from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from datetime import datetime, timedelta
import pytz
import asyncio
import anyio
from contextlib import asynccontextmanager
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# pytz 설치 필요: pip install pytz

# Gemini API 설정
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 .env 파일에 설정되어 있지 않습니다.")

genai.configure(api_key=GEMINI_API_KEY)

server_params = StdioServerParameters(
    command="/private/var/folders/9m/8c8yxc_55fd8czwpk611j6080000gn/T/AppTranslocation/3E61EC49-B551-4875-BD8D-C32E0E862F7D/d/iMCP.app/Contents/MacOS/imcp-server",  # Executable
)

file_server_params = StdioServerParameters(
    command="npx",
    args=[        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/sondonghyeob/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report/Daily Jira Notes/",
        "/Users/sondonghyeob/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report/Slack/llm-app",
        "/Users/sondonghyeob/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report/Dailyplan"]
)

# 내일 날짜 계산
korea_tz = pytz.timezone('Asia/Seoul')
tomorrow = datetime.now(korea_tz) + timedelta(days=1)
tomorrow_str = tomorrow.strftime("%Y년 %m월 %d일")

PROMPT = f"""해당 내용들을 읽고 {tomorrow_str}에 해야 하는 일을 시간대별로 정리해주세요.
시간대는 아침 9시부터 밤 12시까지 1시간 간격으로 정리해주세요.
각 시간대는 다음과 같은 형식으로 작성해주세요:

[09:00 ~ 10:00]
- 할 일 1
- 할 일 2

[10:00 ~ 11:00]
- 할 일 1
- 할 일 2

...

[23:00 ~ 00:00]
- 할 일 1
- 할 일 2

각 시간대별로 해야 하는 일을 구체적으로 작성해주세요."""



@asynccontextmanager
async def create_server_session(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session

async def ask_gemini(question):
    model = genai.GenerativeModel('gemini-1.5-pro')
    response = model.generate_content(question)
    return response.text

async def run():
    try:
        # Gemini API로 날씨 질문

        # iMCP 서버 초기화 및 이벤트 생성
        async with create_server_session(server_params) as imcp_session:
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
            result = await imcp_session.call_tool("createEvent", {
                "title": "손동협",
                "startDate": start_iso,
                "endDate": end_iso,
                "notes": "손동협 일정",
                "availability": "busy"
            })
            print(f"이벤트 생성 결과: {result}")

            # 생성된 이벤트 확인
            events = await imcp_session.call_tool("fetchEvents", {
                "startDate": start_iso,
                "endDate": end_iso
            })
            print(f"생성된 이벤트: {events}")

        # File 서버 초기화 및 경로 설정
        async with create_server_session(file_server_params) as file_session:
            print("File 서버 초기화 완료")
            
            tools_response = await file_session.list_tools()
            tool_names = [tool.name for tool in tools_response.tools]
            print("도구:", ", ".join(tool_names)) 

            extensions = ['.txt', '.md', '.py', '.json', '.csv', '.log']

            allowed_response = await file_session.call_tool("list_allowed_directories")
            allowed_text = allowed_response.content[0].text
            
            directories = [line.strip() for line in allowed_text.split('\n') if line.strip()]
            if not directories:
                directories = ['.']
                
            print(f"디렉토리: {', '.join(directories)}")
        
            contents = ""

            for directory in directories[:-1]:
                print(f"\n--- {directory} ---")
                
                dir_response = await file_session.call_tool("list_directory", {"path": directory})
                dir_text = dir_response.content[0].text
                
                text_files = [line.replace('[FILE]', '').strip() for line in dir_text.split('\n') 
                            if line.startswith('[FILE]') and any(line.endswith(ext) for ext in extensions)]
                
                print(f"{len(text_files)}개 파일: {', '.join(text_files[:3])}" + 
                    ("..." if len(text_files) > 3 else ""))
                
                for filename in text_files:  # 최대 2개 파일만 읽기
                    try:
                        file_path = os.path.join(directory, filename)
                        file_response = await file_session.call_tool("read_file", {"path": file_path})
                        content = file_response.content[0].text
                        contents += content
                        lines = content.split('\n')
                        
                        print(f"\n> {filename}:")
                        for i in range(min(3, len(lines))):
                            print(f"  {lines[i]}")
                        
                        if len(lines) > 3:
                            print("  ...")
                    except:
                        print(f"오류: {filename} 읽기 실패")

            gemini_response = await ask_gemini(PROMPT + "\n\n" + contents)
            print("\nGemini API 응답:")
            print(gemini_response)
            print("\n" + "="*50 + "\n")

            
            
            # 현재 설정 확인
            



    except Exception as e:
        print(f"에러 발생: {e}")
        print("에러 상세 정보:", str(e))

if __name__ == "__main__":
    asyncio.run(run())