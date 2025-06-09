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
    command="python",
    args=["apple_mcp.py"],
)

# 한국 시간대 설정
korea_tz = pytz.timezone('Asia/Seoul')
today = datetime.now(korea_tz)
one_week_ago = today - timedelta(days=7)

# 일주일 동안의 모든 날짜 생성
dates = [(one_week_ago + timedelta(days=x)) for x in range(8)]  # 8일 = 일주일 전부터 오늘까지
date_paths = []

# Jira, Slack, Diary 경로 생성
for date in dates:
    date_str = date.strftime("%Y-%m-%d")
    date_paths.extend([
        f"/Users/sondonghup/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report/Jira/{date_str}",
        f"/Users/sondonghup/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report/Slack/{date_str}",
        f"/Users/sondonghup/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report/Diary/{date_str}",
        f"/Users/sondonghyeob/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report/Gmail/{date_str}"
    ])

# 실제 존재하는 디렉토리만 필터링
existing_paths = []
for path in date_paths:
    if os.path.exists(path):
        existing_paths.append(path)

# Dailyplan 디렉토리 경로
dailyplan_path = "/Users/sondonghup/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report/Dailyplan"
if os.path.exists(dailyplan_path):
    existing_paths.append(dailyplan_path)

# 최소한 하나의 허용 디렉토리가 필요하므로, 존재하는 디렉토리가 없으면 기본 디렉토리 추가
if not existing_paths:
    base_path = "/Users/sondonghup/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report"
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
                '날짜': {
                    'type': 'string',
                    'description': '일정의 날짜 (YYYY-MM-DD 형식)'
                },
                '타이틀': {
                    'type': 'string',
                    'description': '일정의 카테고리 (업무, 휴식, 식사 등)',
                    'enum': ['업무', '휴식', '식사', '회의', '기타']
                },
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
            'required': ['날짜', '타이틀', '시작시간', '종료시간', '내용']
        }
    }
}

# 내일 날짜 계산
korea_tz = pytz.timezone('Asia/Seoul')
tomorrow = datetime.now(korea_tz) + timedelta(days=1)
tomorrow_str = tomorrow.strftime("%Y년 %m월 %d일")
tomorrow_weekday = tomorrow.strftime("%A")  # 요일 추가

# 오늘 날짜는 {datetime.now(korea_tz)} 입니다.

PROMPT = f"""
오늘 날짜는 2025년 5월 28일 입니다.
{tomorrow_str}({tomorrow_weekday})날 알어나거나 해야하는 일만 정리해주세요
다른 날짜의 일은 전부 제거해주세요

ex) === 아래는 날짜 : 2025-04-29 일의 내용 입니다. ===
내일 오후 4시에 우산을 사러가야 하고
오늘은 오후 2시에 쓰레기를 버려야해

위와 같이 되어 있다면 
2025년 4월 30일 오후 4시에 우산을 사러가는 스캐쥴을 잡아야 하고
2025년 4월 29일 오후 2시에 쓰레기를 버려야하는 스케쥴을 잡아야해


그리고 종료시간 또는 시작시간이 24:00 일떄는 24:00 말고 23:59으로 해줘

평일 업무 시간은 
오전 09:00 ~ 12:00 이고
오후 13:00 ~ 18:00 이고
점심 시간은 12:00 ~ 13:00 이고
저녁 시간은 19:00 ~ 20:00 입니다.

점심 저녁 시간도 같이 정리 해주세요
스스로 판단해서 사용자가 동시에 할 수 없는 일은 시작시간 종료시간이 안 겹치게 시간을 설정해주세요
"""

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

@asynccontextmanager
async def create_server_session(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session

async def ask_gemini(question):
    try:
        # API 키 설정 (함수 외부에서 한 번만 실행하는 것이 좋음)
        genai.configure(api_key=GEMINI_API_KEY)
        
        # 모델 생성
        model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
        
        # 콘텐츠 생성
        response = model.generate_content(
            contents=question,
            generation_config=CONFIG  # CONFIG가 있다면
        )
        
        return response.text
        
    except Exception as e:
        print(f"Gemini API 오류: {e}")
        return None

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
                            contents += f"\n\n=== 아래는 날짜 : {filename.split('.')[0]} 일의 내용 입니다. ===\n\n"
                            contents += content
                            
                            print(f"파일 읽기 성공: {filename}")
                        except Exception as e:
                            print(f"오류: {filename} 읽기 실패 - {str(e)}")
                            print(f"에러 타입: {type(e).__name__}")
                            import traceback
                            print("상세 에러 스택:")
                            print(traceback.format_exc())

                gemini_response = await ask_gemini(PROMPT + "\n\n내용:" + contents)

                print("\nGemini API 응답:")
                print(f"***************** : {contents}")
                print(gemini_response)
                print("\n" + "="*50 + "\n")

                                # iMCP 서버 초기화 및 이벤트 생성
                async with create_server_session(server_params) as imcp_session:
                    try:

                        for schedule in gemini_response:
                            print(f"일정: {schedule}")
                            start_time = schedule['시작시간']
                            end_time = schedule['종료시간']
                            tasks = schedule['내용']
                            title = schedule['타이틀']
                            date = schedule['날짜']
                                                        # ISO 형식으로 변환 (더 단순한 형식)
                            start_iso = f"{date} {start_time}"
                            end_iso = f"{date} {end_time}"

                            start_iso = datetime.strptime(start_iso, "%Y-%m-%d %H:%M")
                            end_iso = datetime.strptime(end_iso, "%Y-%m-%d %H:%M")

                            korean_timezone = pytz.timezone('Asia/Seoul')

                            start_iso = korean_timezone.localize(start_iso)
                            end_iso = korean_timezone.localize(end_iso)

                            start_iso = start_iso.isoformat()
                            end_iso = end_iso.isoformat()

                            print(f"시작 시간: {start_iso}")
                            print(f"종료 시간: {end_iso}")

                            # 이벤트 생성
                            result = await imcp_session.call_tool(
                                "create_event", 
                                arguments:={
                                    "event": {
                                        "title": title,
                                        "start_date": str(start_iso),
                                        "end_date": str(end_iso),
                                        "location": None,  # 선택적 필드
                                        "notes": "\n".join(tasks).replace("[", " ").replace("]", " "  ),
                                        "calendar_name": "스케쥴러"

                                    }
                                }
                            )
                            print(f"arguments : {arguments}")
                            print(f"이벤트 생성 결과: {result}")

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