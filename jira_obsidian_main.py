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

import jira_obsidian_utils as utils

# .env 파일에서 환경 변수 로드
load_dotenv()

# 환경 변수에서 설정 가져오기
JIRA_SERVER = os.getenv("JIRA_SERVER")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH")
JIRA_BASE_FOLDER = os.getenv("JIRA_BASE_FOLDER", "Jira")  # 기본값 설정
DAILY_NOTES_FOLDER = os.getenv("DAILY_NOTES_FOLDER", "Daily Jira Notes")  # 기본값 설정

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
    
    # 모든 관련 이슈를 하나의 목록으로 합치기 (중복 제거)
    all_issues = []
    for issue_type, issues in notifications.items():
        all_issues.extend(issues)
    
    # 중복 제거
    all_issues = utils.remove_duplicates(all_issues)
    print(f"총 알림 이슈 (중복 제거): {len(all_issues)}개")
    
    # 프로젝트별로 이슈 분류 및 저장
    projects = {}
    saved_files = []
    
    for issue in all_issues:
        project_key = issue.fields.project.key
        if project_key not in projects:
            projects[project_key] = []
        projects[project_key].append(issue)
        
        # 모든 댓글 가져오기 (last_check_time을 None으로 설정하여 모든 댓글 가져오기)
        comments = utils.get_issue_comments(jira, issue.key, None)
        
        # Markdown 변환
        markdown = utils.issue_to_markdown(issue, comments, JIRA_SERVER)
        
        # Obsidian에 저장
        file_path = utils.save_to_obsidian(issue, markdown, OBSIDIAN_VAULT_PATH, JIRA_BASE_FOLDER)
        saved_files.append(file_path)
        
        print(f"저장됨: {file_path} (댓글 {len(comments)}개 포함)")
    
    # 날짜별 알림 생성
    daily_notifications = defaultdict(list)
    
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
            
            # 알림 요약 생성
            summary = utils.create_notification_summary(
                issue, notification_type, comments, JIRA_SERVER, 
                OBSIDIAN_VAULT_PATH, JIRA_BASE_FOLDER
            )
            
            # 날짜별로 알림 추가 (중복 방지)
            issue_already_added = False
            for existing_notif in daily_notifications[update_date]:
                if existing_notif['issue'].key == issue.key:
                    issue_already_added = True
                    break
            
            if not issue_already_added:
                daily_notifications[update_date].append({
                    'issue': issue,
                    'type': notification_type,
                    'summary': summary
                })
    
    # 일별 노트 생성
    created_daily_notes = {}
    for date, notifications_list in daily_notifications.items():
        note_path = utils.create_daily_note(date, notifications_list, OBSIDIAN_VAULT_PATH, DAILY_NOTES_FOLDER)
        created_daily_notes[date.strftime('%Y-%m-%d')] = len(notifications_list)
        print(f"일별 알림 생성: {note_path} ({len(notifications_list)}건)")
    
    # 주간 노트 생성
    created_weekly_notes = {}
    
    # 해당 알림들의 날짜 범위에서 각 주의 월요일 찾기
    all_dates = list(daily_notifications.keys())
    if all_dates:
        min_date = min(all_dates)
        max_date = max(all_dates)
        
        # 첫 주의 월요일 찾기
        days_since_monday = min_date.weekday()
        first_monday = min_date - datetime.timedelta(days=days_since_monday)
        
        # 마지막 주의 월요일 찾기
        days_since_last_monday = max_date.weekday()
        last_monday = max_date - datetime.timedelta(days=days_since_last_monday)
        
        # 각 주별로 주간 노트 생성
        current_monday = first_monday
        while current_monday <= last_monday:
            week_number = current_monday.strftime('%U')
            week_key = f"{current_monday.strftime('%Y')}-W{week_number}"
            
            # 이 주에 해당하는 일별 노트 찾기
            week_daily_notes = {}
            for i in range(7):
                day = current_monday + datetime.timedelta(days=i)
                day_str = day.strftime('%Y-%m-%d')
                if day_str in created_daily_notes:
                    week_daily_notes[day_str] = created_daily_notes[day_str]
            
            # 주간 노트 생성
            if week_daily_notes:
                note_path = utils.create_weekly_note(
                    current_monday, week_daily_notes, 
                    OBSIDIAN_VAULT_PATH, DAILY_NOTES_FOLDER
                )
                created_weekly_notes[week_key] = {
                    'start_date': current_monday.strftime('%Y-%m-%d'),
                    'end_date': (current_monday + datetime.timedelta(days=6)).strftime('%Y-%m-%d'),
                    'count': sum(week_daily_notes.values())
                }
                print(f"주간 알림 생성: {note_path}")
            
            # 다음 주 월요일
            current_monday += datetime.timedelta(days=7)
    
    # 월간 노트 생성
    if all_dates:
        # 월별로 그룹화
        months = set()
        for date in all_dates:
            months.add((date.year, date.month))
        
        for year, month in months:
            month_date = datetime.date(year, month, 1)
            note_path = utils.create_monthly_note(
                month_date, created_weekly_notes, 
                OBSIDIAN_VAULT_PATH, DAILY_NOTES_FOLDER
            )
            print(f"월간 알림 생성: {note_path}")
    
    # 알림 인덱스 생성
    index_path = utils.create_notification_index(OBSIDIAN_VAULT_PATH, DAILY_NOTES_FOLDER)
    print(f"알림 인덱스 생성: {index_path}")
    
    # 현재 시간을 마지막 확인 시간으로 저장
    utils.save_last_check_time(LAST_CHECK_FILE)
    
    print(f"총 {len(saved_files)}개의 이슈가 Obsidian에 동기화되었습니다.")
    print(f"총 {len(created_daily_notes)}일의 알림 노트가 생성되었습니다.")

if __name__ == "__main__":
    main()