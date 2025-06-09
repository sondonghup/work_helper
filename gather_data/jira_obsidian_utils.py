#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Jira 알림을 Obsidian에 동기화하는 유틸리티 모듈
"""

import os
import datetime
from pathlib import Path
from collections import defaultdict
from jira import JIRA
import json

def connect_to_jira(jira_server, jira_email, jira_api_token):
    """Jira에 연결"""
    try:
        jira = JIRA(server=jira_server, basic_auth=(jira_email, jira_api_token))
        return jira
    except Exception as e:
        print(f"Jira 연결 실패: {e}")
        return None

def get_last_check_time(last_check_file):
    """마지막 확인 시간 가져오기"""
    if os.path.exists(last_check_file):
        with open(last_check_file, 'r') as f:
            return f.read().strip()
    # 기본값: 24시간 전
    return (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

def save_last_check_time(last_check_file):
    """현재 시간을 마지막 확인 시간으로 저장"""
    with open(last_check_file, 'w') as f:
        f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

def get_my_notifications(jira, last_check_time, project_keys=None, days=7):
    """나와 관련된 이슈만 가져오기"""
    notifications = {
        'assigned': [],     # 나에게 할당된 이슈
        'mentioned': [],    # 댓글에서 멘션된 이슈
        'commented': [],    # 내가 댓글을 단 이슈
        'created': [],      # 내가 생성한 이슈
        'watching': [],     # 내가 지켜보는 이슈
        'in_progress': []   # 내가 담당자인 진행 중인 이슈
    }
    
    # 마지막 검색 시간 또는 지정된 일수 중 더 오래된 기준 사용
    time_limit = last_check_time
    days_ago = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    
    # 마지막 체크 시간이 지정된 일수보다 최근인 경우, 일수 기준 사용
    last_check_date = datetime.datetime.strptime(last_check_time, "%Y-%m-%d %H:%M")
    days_ago_date = datetime.datetime.strptime(days_ago, "%Y-%m-%d %H:%M")
    if days_ago_date < last_check_date:
        time_limit = days_ago
    
    # 프로젝트 필터 적용
    project_filter = ""
    if project_keys:
        projects = ", ".join(f'"{key}"' for key in project_keys)
        project_filter = f" AND project in ({projects})"
    
    try:
        # 1. 나에게 할당된 이슈 (최근에 업데이트된 것)
        assigned_jql = f'assignee = currentUser() AND updated >= "{time_limit}"{project_filter} ORDER BY updated DESC'
        notifications['assigned'] = jira.search_issues(assigned_jql, maxResults=50)
        
        # 2. 댓글에서 멘션된 이슈
        mentioned_jql = f'comment ~ currentUser() AND updated >= "{time_limit}"{project_filter} ORDER BY updated DESC'
        notifications['mentioned'] = jira.search_issues(mentioned_jql, maxResults=50)
        
        # 3. 내가 댓글을 단 이슈
        try:
            commented_jql = f'issueFunction in commented("by currentUser()") AND updated >= "{time_limit}"{project_filter} ORDER BY updated DESC'
            notifications['commented'] = jira.search_issues(commented_jql, maxResults=50)
        except:
            # issueFunction이 지원되지 않는 경우 빈 리스트 유지
            print("댓글 함수 검색이 지원되지 않습니다. 수동으로 확인해 주세요.")
        
        # 4. 내가 생성한 이슈
        created_jql = f'reporter = currentUser() AND updated >= "{time_limit}"{project_filter} ORDER BY updated DESC'
        notifications['created'] = jira.search_issues(created_jql, maxResults=50)
        
        # 5. 내가 지켜보는 이슈
        watching_jql = f'watcher = currentUser() AND updated >= "{time_limit}"{project_filter} ORDER BY updated DESC'
        notifications['watching'] = jira.search_issues(watching_jql, maxResults=50)
        
        # 6. 내가 담당자인 진행 중인 이슈
        in_progress_jql = f'assignee = currentUser() AND status = "In Progress"{project_filter} ORDER BY updated DESC'
        notifications['in_progress'] = jira.search_issues(in_progress_jql, maxResults=50)
        
        return notifications
    except Exception as e:
        print(f"알림 검색 실패: {e}")
        return notifications

def get_issue_comments(jira, issue_key, last_check_time=None):
    """이슈의 모든 댓글 가져오기 (last_check_time이 None이면 모든 댓글, 아니면 최근 댓글만)"""
    try:
        issue = jira.issue(issue_key)
        all_comments = []
        
        for comment in issue.fields.comment.comments:
            comment_date = datetime.datetime.strptime(
                comment.created.split('.')[0], 
                "%Y-%m-%dT%H:%M:%S"
            )
            
            # last_check_time이 None이거나, 최근 댓글이면 추가
            if last_check_time is None or (
                last_check_time and comment_date > datetime.datetime.strptime(
                    last_check_time, "%Y-%m-%d %H:%M"
                )
            ):
                all_comments.append({
                    'author': comment.author.displayName,
                    'body': comment.body,
                    'created': comment.created.split('T')[0] + ' ' + comment.created.split('T')[1].split('.')[0],
                    'created_date': comment_date
                })
        
        # 날짜순으로 정렬 (오래된 것부터)
        return sorted(all_comments, key=lambda x: x['created_date'])
    except Exception as e:
        print(f"댓글 가져오기 실패 ({issue_key}): {e}")
        return []

def issue_to_markdown(issue, comments=None, jira_server=""):
    """Jira 이슈를 Markdown 형식으로 변환"""
    fields = issue.fields
    
    # 기본 정보
    markdown = f"# [{issue.key}] {fields.summary}\n\n"
    markdown += f"**Status**: {fields.status.name}  \n"
    markdown += f"**Type**: {fields.issuetype.name}  \n"
    markdown += f"**Project**: {fields.project.name} ({fields.project.key})  \n"
    
    if hasattr(fields, 'priority') and fields.priority:
        markdown += f"**Priority**: {fields.priority.name}  \n"
    
    if hasattr(fields, 'assignee') and fields.assignee:
        markdown += f"**Assignee**: {fields.assignee.displayName}  \n"
    
    if hasattr(fields, 'reporter') and fields.reporter:
        markdown += f"**Reporter**: {fields.reporter.displayName}  \n"
    
    markdown += f"**Created**: {fields.created.split('T')[0]}  \n"
    markdown += f"**Updated**: {fields.updated.split('T')[0]}  \n\n"
    
    # 설명
    if fields.description:
        markdown += f"## Description\n\n{fields.description}\n\n"
    
    # 모든 댓글 (전체 내용)
    if comments and len(comments) > 0:
        markdown += f"## Comments ({len(comments)})\n\n"
        for comment in comments:
            markdown += f"### {comment['author']} - {comment['created']}\n\n"
            markdown += f"{comment['body']}\n\n"
    
    # Jira 링크
    markdown += f"---\n[View in Jira]({jira_server}/browse/{issue.key})"
    
    return markdown

def save_to_obsidian(issue, markdown_content, obsidian_vault_path, jira_base_folder):
    """Markdown 콘텐츠를 Obsidian 볼트에 저장 (프로젝트별 폴더 구조)"""
    # 프로젝트 키로 폴더 생성
    project_key = issue.fields.project.key
    project_path = os.path.join(obsidian_vault_path, jira_base_folder, project_key)
    Path(project_path).mkdir(parents=True, exist_ok=True)
    
    # 파일명 생성 (이슈 키 + 제목의 일부)
    sanitized_summary = issue.fields.summary[:30].replace('/', '-').replace('\\', '-').replace(':', '-')
    file_name = f"{issue.key} - {sanitized_summary}.md"
    file_path = os.path.join(project_path, file_name)
    
    # 메타데이터 추가 (Obsidian 프론트매터)
    update_date = datetime.datetime.strptime(
        issue.fields.updated.split('.')[0], 
        "%Y-%m-%dT%H:%M:%S"
    )
    
    front_matter = f"""---
jira_key: {issue.key}
project: {project_key}
status: {issue.fields.status.name}
created: {issue.fields.created.split('T')[0]}
updated: {issue.fields.updated.split('T')[0]}
update_year: {update_date.year}
update_month: {update_date.month}
update_day: {update_date.day}
tags: [jira, {project_key.lower()}]
---

"""
    
    # 파일 저장
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(front_matter + markdown_content)
    
    return file_path

def create_notification_summary(issue, notification_type, comments=None, 
                               jira_server="", obsidian_vault_path="", jira_base_folder=""):
    """알림 요약 생성"""
    fields = issue.fields
    
    # 기본 정보
    summary = f"## [{issue.key}] {fields.summary}\n\n"
    
    # 알림 유형에 따른 메시지
    type_msg = ""
    if notification_type == "assigned":
        type_msg = "🔔 **이슈가 나에게 할당되었습니다.**"
    elif notification_type == "mentioned":
        type_msg = "💬 **댓글에서 내가 멘션되었습니다.**"
    elif notification_type == "commented":
        type_msg = "📝 **내가 댓글을 단 이슈가 업데이트되었습니다.**"
    elif notification_type == "created":
        type_msg = "✅ **내가 생성한 이슈가 업데이트되었습니다.**"
    elif notification_type == "watching":
        type_msg = "👁️ **내가 지켜보는 이슈가 업데이트되었습니다.**"
    
    summary += f"{type_msg}\n\n"
    
    # 주요 정보
    summary += f"- **상태**: {fields.status.name}\n"
    summary += f"- **프로젝트**: {fields.project.name} ({fields.project.key})\n"
    
    if hasattr(fields, 'assignee') and fields.assignee:
        summary += f"- **담당자**: {fields.assignee.displayName}\n"
    
    # 업데이트 날짜/시간
    update_time = datetime.datetime.strptime(
        fields.updated.split('.')[0], 
        "%Y-%m-%dT%H:%M:%S"
    )
    summary += f"- **업데이트**: {update_time.strftime('%Y-%m-%d %H:%M')}\n\n"
    
    # 최근 댓글 요약 (있는 경우)
    if comments and len(comments) > 0:
        for comment in sorted(comments, key=lambda x: x['created_date'], reverse=True)[:1]:  # 최신 댓글 1개만
            summary += f"**최근 댓글** ({comment['author']}):\n> {comment['body'][:150]}{'...' if len(comment['body']) > 150 else ''}\n\n"
    
    # 링크 추가
    summary_clean = fields.summary[:30].replace('/', '-').replace('\\', '-').replace(':', '-')
    file_path = f"{jira_base_folder}/{fields.project.key}/{issue.key} - {summary_clean}"
    summary += f"[이슈 상세 보기](obsidian://open?vault={os.path.basename(obsidian_vault_path)}&file={file_path})\n"
    summary += f"[Jira에서 보기]({jira_server}/browse/{issue.key})\n\n"
    
    summary += "---\n\n"  # 구분선
    
    return summary

def create_daily_note(date, daily_notifications, vault_path, jira_base_folder):
    """일일 노트 생성"""
    # 날짜 폴더 생성
    date_folder = os.path.join(vault_path, jira_base_folder, date.strftime("%Y-%m-%d"))
    os.makedirs(date_folder, exist_ok=True)
    
    # 일일 노트 파일 경로
    note_path = os.path.join(date_folder, f"{date.strftime('%Y-%m-%d')}.md")
    
    with open(note_path, 'w', encoding='utf-8') as f:
        f.write(f"# {date.strftime('%Y년 %m월 %d일')} Jira 알림\n\n")
        
        # 문자열인 경우 JSON으로 파싱
        if isinstance(daily_notifications, str):
            try:
                daily_notifications = json.loads(daily_notifications)
            except json.JSONDecodeError:
                print("JSON 파싱 실패")
                return note_path
        
        # 작업 내용 섹션 추가
        f.write("## 오늘의 작업\n\n")
        f.write("### 완료한 작업\n")
        f.write("- [ ] \n\n")
        f.write("### 진행 중인 작업\n")
        
        # 진행 중인 작업 목록 추가
        if 'in_progress' in daily_notifications and daily_notifications['in_progress']:
            for issue, _ in daily_notifications['in_progress']:
                due_date = issue.fields.duedate if hasattr(issue.fields, 'duedate') and issue.fields.duedate else "마감일 없음"
                f.write(f"- [ ] {issue.key}: {issue.fields.summary} (마감일: {due_date})\n")
        else:
            f.write("- [ ] \n")
        
        f.write("\n### 내일 할 작업\n")
        f.write("- [ ] \n\n")
        
        f.write("## Jira 알림\n\n")
        for notification in daily_notifications:
            if isinstance(notification, str):
                try:
                    notification = json.loads(notification)
                except json.JSONDecodeError:
                    continue
            
            f.write(f"### {notification['issue']['key']}: {notification['issue']['fields']['summary']}\n\n")
            f.write(f"- 상태: {notification['issue']['fields']['status']['name']}\n")
            f.write(f"- 담당자: {notification['issue']['fields']['assignee']['displayName']}\n")
            f.write(f"- 우선순위: {notification['issue']['fields']['priority']['name']}\n")
            f.write(f"- 마감일: {notification['issue']['fields']['duedate']}\n\n")
            
            if 'comment' in notification:
                f.write("#### 댓글\n")
                f.write(f"- 작성자: {notification['comment']['author']['displayName']}\n")
                f.write(f"- 내용: {notification['comment']['body']}\n\n")
            
            f.write("---\n\n")
    
    return note_path

def create_weekly_note(start_date, daily_notifications, vault_path, jira_base_folder):
    """주간 노트 생성"""
    # 주간 노트는 해당 주의 월요일 폴더에 저장
    date_folder = os.path.join(vault_path, jira_base_folder, start_date.strftime('%Y-%m-%d'))
    os.makedirs(date_folder, exist_ok=True)
    
    end_date = start_date + datetime.timedelta(days=6)
    note_path = os.path.join(date_folder, f"{start_date.strftime('%Y-%m-%d')}_weekly.md")
    
    with open(note_path, 'w', encoding='utf-8') as f:
        f.write(f"# {start_date.strftime('%Y년 %m월 %d일')} ~ {end_date.strftime('%Y년 %m월 %d일')} 주간 Jira 알림\n\n")
        
        for date in sorted(daily_notifications.keys()):
            if start_date <= date <= end_date:
                f.write(f"## {date.strftime('%Y년 %m월 %d일')}\n\n")
                for notification_type, issues in daily_notifications[date].items():
                    if issues:
                        f.write(f"### {notification_type}\n\n")
                        for issue, _ in issues:
                            f.write(f"- {issue.key}: {issue.fields.summary}\n")
                        f.write("\n")
    
    return note_path

def create_monthly_note(month_date, daily_notifications, vault_path, jira_base_folder):
    """월간 노트 생성"""
    # 월간 노트는 해당 월의 첫 날 폴더에 저장
    date_folder = os.path.join(vault_path, jira_base_folder, month_date.strftime('%Y-%m-%d'))
    os.makedirs(date_folder, exist_ok=True)
    
    note_path = os.path.join(date_folder, f"{month_date.strftime('%Y-%m')}_monthly.md")
    
    with open(note_path, 'w', encoding='utf-8') as f:
        f.write(f"# {month_date.strftime('%Y년 %m월')} Jira 알림\n\n")
        
        for date in sorted(daily_notifications.keys()):
            if date.year == month_date.year and date.month == month_date.month:
                f.write(f"## {date.strftime('%Y년 %m월 %d일')}\n\n")
                for notification_type, issues in daily_notifications[date].items():
                    if issues:
                        f.write(f"### {notification_type}\n\n")
                        for issue, _ in issues:
                            f.write(f"- {issue.key}: {issue.fields.summary}\n")
                        f.write("\n")
    
    return note_path

def create_notification_index(vault_path, jira_base_folder):
    """알림 인덱스 페이지 생성"""
    index_folder = os.path.join(vault_path, jira_base_folder)
    os.makedirs(index_folder, exist_ok=True)
    
    index_path = os.path.join(index_folder, "index.md")
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write("# Jira 알림 인덱스\n\n")
        f.write("## 월별 알림\n\n")
        
        # 월별 노트 링크 생성
        current_date = datetime.date.today()
        for i in range(12):
            month_date = current_date.replace(day=1) - datetime.timedelta(days=30*i)
            f.write(f"- [[{month_date.strftime('%Y-%m-%d')}/{month_date.strftime('%Y-%m')}_monthly|{month_date.strftime('%Y년 %m월')}]]\n")
        
        f.write("\n## 주간 알림\n\n")
        
        # 주간 노트 링크 생성
        for i in range(4):
            week_start = current_date - datetime.timedelta(days=7*i)
            f.write(f"- [[{week_start.strftime('%Y-%m-%d')}/{week_start.strftime('%Y-%m-%d')}_weekly|{week_start.strftime('%Y년 %m월 %d일')} 주간]]\n")
        
        f.write("\n## 일별 알림\n\n")
        
        # 일별 노트 링크 생성
        for i in range(7):
            day = current_date - datetime.timedelta(days=i)
            f.write(f"- [[{day.strftime('%Y-%m-%d')}/{day.strftime('%Y-%m-%d')}|{day.strftime('%Y년 %m월 %d일')}]]\n")
    
    return index_path

def remove_duplicates(issues_list):
    """중복 이슈 제거"""
    seen = set()
    unique_issues = []
    
    for issue in issues_list:
        if issue.key not in seen:
            seen.add(issue.key)
            unique_issues.append(issue)
    
    return unique_issues