# import schedule
import time
import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

from gather_data.gmail_obsidian_main import get_megastudy_emails
from gather_data.jira_obsidian_main import main as jira_obsidian_main
from gather_data.slack_obsidian_main import main as slack_obsidian_main
from client import run as client_run

async def run_all_tasks():
    print(f"캘린더를 생성합니다!")
    print(f"=== GMAIL 동기화 중 ... ===")
    get_megastudy_emails()
    print(f"=== JIRA 동기화 중 ... ===")
    jira_obsidian_main()
    print(f"=== SLACK 동기화 중 ... ===")
    slack_obsidian_main()
    print(f"=== 클라이언트 동기화 중 ... ===")
    await client_run()

def schedule_job():
    with ThreadPoolExecutor() as executor:
        executor.submit(lambda: asyncio.run(run_all_tasks()))

if __name__ == "__main__":
    # 매일 오전 7시에 실행
    # schedule.every().day.at("21:08").do(schedule_job)
    
    # print("스케줄러가 실행 중입니다...")
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)  # 1분마다 체크


    schedule_job()
