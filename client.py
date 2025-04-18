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
from google import genai
from dotenv import load_dotenv
import subprocess
import time

# .env 파일 로드
load_dotenv()

# pytz 설치 필요: pip install pytz

# Gemini API 설정
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 .env 파일에 설정되어 있지 않습니다.")

server_params = StdioServerParameters(
    command="/private/var/folders/9m/8c8yxc_55fd8czwpk611j6080000gn/T/AppTranslocation/3E61EC49-B551-4875-BD8D-C32E0E862F7D/d/iMCP.app/Contents/MacOS/imcp-server",  # Executable
)

# 한국 시간대 설정
korea_tz = pytz.timezone('Asia/Seoul')
today = datetime.now(korea_tz)
one_week_ago = today - timedelta(days=7)

# 일주일 동안의 모든 날짜 생성
dates = [(one_week_ago + timedelta(days=x)) for x in range(8)]  # 8일 = 일주일 전부터 오늘까지
date_paths = []

# Jira와 Slack 경로 생성
for date in dates:
    date_str = date.strftime("%Y-%m-%d")
    date_paths.extend([
        f"/Users/sondonghyeob/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report/Jira/{date_str}",
        f"/Users/sondonghyeob/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report/Slack/{date_str}"
    ])

# 실제 존재하는 디렉토리만 필터링
existing_paths = []
for path in date_paths:
    if os.path.exists(path):
        existing_paths.append(path)

# Dailyplan 디렉토리 경로
dailyplan_path = "/Users/sondonghyeob/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report/Dailyplan"
if os.path.exists(dailyplan_path):
    existing_paths.append(dailyplan_path)

# 최소한 하나의 허용 디렉토리가 필요하므로, 존재하는 디렉토리가 없으면 기본 디렉토리 추가
if not existing_paths:
    base_path = "/Users/sondonghyeob/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report"
    if os.path.exists(base_path):
        existing_paths.append(base_path)
    else:
        existing_paths.append(".")  # 현재 디렉토리를 기본으로 사용

file_server_params = StdioServerParameters(
    command="npx",
    args=[
        "-y",
        "@modelcontextprotocol/server-filesystem",
        existing_paths[0],  # 첫 번째 디렉토리를 허용 디렉토리로 지정
        *existing_paths[1:]  # 나머지 디렉토리들을 추가 디렉토리로 지정
    ]
)

CONFIG = {
    'response_mime_type': 'application/json',
    'response_schema': {
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                '시작시간': {
                    'type': 'string',
                    'description': '일정의 시작 시간 (HH:MM 형식)'
                },
                '종료시간': {
                    'type': 'string',
                    'description': '일정의 종료 시간 (HH:MM 형식)'
                },
                '내용': {
                    'type': 'array',
                    'items': {
                        'type': 'string'
                    },
                    'description': '해당 시간대에 해야 할 일들의 목록'
                }
            },
            'required': ['시작시간', '종료시간', '내용']
        }
    }
}

# 내일 날짜 계산
korea_tz = pytz.timezone('Asia/Seoul')
tomorrow = datetime.now(korea_tz) + timedelta(days=1)
tomorrow_str = tomorrow.strftime("%Y년 %m월 %d일")

PROMPT = f"""해당 내용들을 읽고 {tomorrow_str}에 해야 하는 일을 시간대별로 정리해주세요.
만약 마감일이 있는 작업이라면 마감일 전까지 해야 하는 일을 적당히 분배 하여 정리해주세요.
시간대는 아침 9시부터 밤 12시까지 1시간 간격으로 정리해주세요.
회사는 09:00 ~ 18:00 근무입니다.
점심 시간은 12:00 ~ 13:00 입니다.
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

# 환경 변수에서 설정 가져오기
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH")
SLACK_BASE_FOLDER = os.getenv("SLACK_BASE_FOLDER", "Slack")
JIRA_BASE_FOLDER = os.getenv("JIRA_BASE_FOLDER", "Jira")

def open_obsidian_note(file_path):
    """Obsidian 노트 열기"""
    try:
        subprocess.run(["open", file_path])
    except Exception as e:
        print(f"파일 열기 실패: {e}")

def main():
    """메인 실행 함수"""
    # 오늘 날짜와 일주일 전 날짜 계산
    today = datetime.now(korea_tz).date()
    one_week_ago = today - timedelta(days=7)
    
    # 일주일 동안의 모든 날짜 생성
    dates = [(one_week_ago + timedelta(days=x)) for x in range(8)]  # 8일 = 일주일 전부터 오늘까지
    
    # 각 날짜별로 파일 열기
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        
        # Slack 노트 경로
        slack_note_path = os.path.join(
            OBSIDIAN_VAULT_PATH,
            SLACK_BASE_FOLDER,
            date_str,
            f"{date_str}.md"
        )
        
        # Jira 노트 경로
        jira_note_path = os.path.join(
            OBSIDIAN_VAULT_PATH,
            JIRA_BASE_FOLDER,
            date_str,
            f"{date_str}.md"
        )
        
        # 파일이 존재하는 경우에만 열기
        if os.path.exists(slack_note_path):
            print(f"Slack 노트 열기: {slack_note_path}")
            open_obsidian_note(slack_note_path)
            time.sleep(1)  # 파일이 열리는 시간을 기다림
        
        if os.path.exists(jira_note_path):
            print(f"Jira 노트 열기: {jira_note_path}")
            open_obsidian_note(jira_note_path)
            time.sleep(1)  # 파일이 열리는 시간을 기다림

@asynccontextmanager
async def create_server_session(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session

async def ask_gemini(question):
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model = 'gemini-1.5-pro',
        contents = question,
        config = CONFIG
    )
    return response.parsed

async def run():
    try:
        # Gemini API로 날씨 질문

        # File 서버 초기화 및 경로 설정
        async with create_server_session(file_server_params) as file_session:
            try:
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

                # 각 디렉토리에서 파일 읽기
                for directory in directories:
                    print(f"\n--- {directory} ---")
                    
                    dir_response = await file_session.call_tool("list_directory", {"path": directory})
                    dir_text = dir_response.content[0].text
                    
                    # .md 파일만 필터링
                    text_files = [line.replace('[FILE]', '').strip() for line in dir_text.split('\n') 
                                if line.startswith('[FILE]') and line.endswith('.md')]
                    
                    print(f"{len(text_files)}개 파일: {', '.join(text_files)}")
                    
                    # 모든 .md 파일 읽기
                    for filename in text_files:
                        try:
                            file_path = os.path.join(directory, filename)
                            file_response = await file_session.call_tool("read_file", {"path": file_path})
                            content = file_response.content[0].text
                            contents += f"\n\n=== {filename} ===\n\n"
                            contents += content
                            
                            print(f"파일 읽기 성공: {filename}")
                        except Exception as e:
                            print(f"오류: {filename} 읽기 실패 - {str(e)}")
                            print(f"에러 타입: {type(e).__name__}")
                            import traceback
                            print("상세 에러 스택:")
                            print(traceback.format_exc())

                gemini_response = await ask_gemini(PROMPT + "\n\n" + contents)
                print("\nGemini API 응답:")
                print(gemini_response)
                print("\n" + "="*50 + "\n")

                                # iMCP 서버 초기화 및 이벤트 생성
                async with create_server_session(server_params) as imcp_session:
                    try:
                        # 한국 시간대 설정
                        korea_tz = pytz.timezone('Asia/Seoul')

                        for schedule in gemini_response:
                            print(f"일정: {schedule}")
                            start_time = schedule['시작시간']
                            end_time = schedule['종료시간']
                            tasks = schedule['내용']
                        
                        # 현재 시간 기준으로 이벤트 생성
                            now = datetime.now(korea_tz)
                            start_hour, start_minute = map(int, start_time.split(':'))
                            start_time = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)

                            end_hour, end_minute = map(int, end_time.split(':'))
                            end_time = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)

                                                        # ISO 형식으로 변환 (더 단순한 형식)
                            start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%S%z")
                            end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S%z")


                        # 이벤트 생성
                            result = await imcp_session.call_tool("createEvent", {
                                "title": "업무",
                                "startDate": start_iso,
                                "endDate": end_iso,
                                "notes": f"{tasks}",
                                "availability": "busy",
                                "calendar": "primary"  # 기본 캘린더 사용
                            })
                            print(f"이벤트 생성 결과: {result}")

                        # 생성된 이벤트 확인
                            events = await imcp_session.call_tool("fetchEvents", {
                                "startDate": start_iso,
                                "endDate": end_iso
                            })
                            print(f"생성된 이벤트: {events}")

                    except Exception as e:
                        print(f"iMCP 서버 작업 중 에러 발생: {str(e)}")
                        print(f"에러 타입: {type(e).__name__}")
                        import traceback
                        print("상세 에러 스택:")
                        print(traceback.format_exc())

            except Exception as e:
                print(f"File 서버 작업 중 에러 발생: {str(e)}")
                print(f"에러 타입: {type(e).__name__}")
                import traceback
                print("상세 에러 스택:")
                print(traceback.format_exc())

    except Exception as e:
        print(f"전체 작업 중 에러 발생: {str(e)}")
        print(f"에러 타입: {type(e).__name__}")
        import traceback
        print("상세 에러 스택:")
        print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(run())