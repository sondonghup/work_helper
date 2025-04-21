#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Jira 알림을 Obsidian에 동기화하는 메인 스크립트
"""

import os
import datetime
from pathlib import Path
from collections import defaultdict
from jira import JIRA
from dotenv import load_dotenv

import make_obsidian.jira_obsidian_utils as utils

# .env 파일에서 환경 변수 로드
load_dotenv()

# 환경 변수에서 설정 가져오기
JIRA_SERVER = os.getenv("JIRA_SERVER")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH")
JIRA_BASE_FOLDER = os.getenv("JIRA_BASE_FOLDER", "Jira")  # 기본값 설정

# 최근 검색 시간을 저장할 파일
LAST_CHECK_FILE = os.path.join(OBSIDIAN_VAULT_PATH, ".jira_last_check")

# 프로젝트별로 추적할 프로젝트 키 목록 (비워두면 모든 프로젝트 추적)
# 예: ["PROJ1", "PROJ2", "DEV"]
PROJECT_KEYS = []

def main():
    """메인 실행 함수"""
    # Jira 연결
    jira = utils.connect_to_jira(JIRA_SERVER, JIRA_EMAIL, JIRA_API_TOKEN)
    if not jira:
        return
    
    # 마지막 확인 시간 가져오기
    last_check_time = utils.get_last_check_time(LAST_CHECK_FILE)
    print(f"마지막 확인 시간: {last_check_time}")
    
    # 나와 관련된 알림만 가져오기
    notifications = utils.get_my_notifications(jira, last_check_time, PROJECT_KEYS, days=7)
    
    print(f"내게 할당된 이슈: {len(notifications['assigned'])}개")
    print(f"멘션된 이슈: {len(notifications['mentioned'])}개")
    print(f"내가 댓글을 단 이슈: {len(notifications['commented'])}개")
    print(f"내가 생성한 이슈: {len(notifications['created'])}개")
    print(f"내가 지켜보는 이슈: {len(notifications['watching'])}개")
    
    # 날짜별 알림 정리
    daily_notifications = defaultdict(lambda: defaultdict(list))
    
    # 알림 타입별 처리
    for notification_type, issues in notifications.items():
        for issue in issues:
            # 업데이트 날짜 추출
            update_date = datetime.datetime.strptime(
                issue.fields.updated.split('.')[0], 
                "%Y-%m-%dT%H:%M:%S"
            ).date()
            
            # 최근 댓글 확인
            comments = utils.get_issue_comments(jira, issue.key, last_check_time)
            
            # 날짜별로 알림 정리
            daily_notifications[update_date][notification_type].append((issue, comments))
    
    # 날짜별 노트 생성
    for date, notifications_by_type in daily_notifications.items():
        # 날짜별 노트 생성
        daily_note_path = utils.create_daily_note(
            date,
            notifications_by_type,
            OBSIDIAN_VAULT_PATH,
            JIRA_BASE_FOLDER
        )
        print(f"생성됨: {daily_note_path}")
    
    # 주간 노트 생성 (최근 7일)
    week_start_date = datetime.date.today() - datetime.timedelta(days=7)
    weekly_note_path = utils.create_weekly_note(
        week_start_date,
        daily_notifications,
        OBSIDIAN_VAULT_PATH,
        JIRA_BASE_FOLDER
    )
    print(f"생성됨: {weekly_note_path}")
    
    # 월간 노트 생성 (이번 달)
    month_date = datetime.date.today().replace(day=1)
    monthly_note_path = utils.create_monthly_note(
        month_date,
        daily_notifications,
        OBSIDIAN_VAULT_PATH,
        JIRA_BASE_FOLDER
    )
    print(f"생성됨: {monthly_note_path}")
    
    # 인덱스 페이지 생성
    index_path = utils.create_notification_index(OBSIDIAN_VAULT_PATH, JIRA_BASE_FOLDER)
    print(f"생성됨: {index_path}")
    
    # 마지막 확인 시간 업데이트
    utils.save_last_check_time(LAST_CHECK_FILE)
    print("마지막 확인 시간이 업데이트되었습니다.")

if __name__ == "__main__":
    main()