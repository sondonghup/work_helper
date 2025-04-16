import os
import json
import datetime
import requests
from jira import JIRA
from pathlib import Path
from collections import defaultdict


# 설정 (실제 사용 시 환경 변수 또는 설정 파일로 관리하는 것이 좋습니다)
JIRA_SERVER = "https://megastudyai.atlassian.net"
JIRA_EMAIL = "acer@megastudy.net"
JIRA_API_TOKEN = "ATATT3xFfGF0U_nSRcGXgk8ikcYmnyc8HTAOSlcF6f-0QFfpOSF0Ns8LxoMpkBYr6ygT11ubpLlWSCLqbMZhb4JK83H2DWfRDDH_P2h8TTcYb3vqxMX7w65kE-G8Q7BvQRwGWVW674voytg7Shp_FmjxKUXEF7UKy6wC5VlSacayqnOY3uHPkSk=F0943503"  # Atlassian 계정에서 생성한 API 토큰
OBSIDIAN_VAULT_PATH = "/Users/sondonghyeob/Documents/work helper/"  # Obsidian 볼트 경로
JIRA_BASE_FOLDER = "Jira"  # Obsidian 볼트 내 Jira 노트를 저장할 폴더
DAILY_NOTES_FOLDER = "Daily Jira Notes"  # 일별 알림을 저장할 폴더

# 최근 검색 시간을 저장할 파일
LAST_CHECK_FILE = os.path.join(OBSIDIAN_VAULT_PATH, ".jira_last_check")

# 프로젝트별로 추적할 프로젝트 키 목록 (비워두면 모든 프로젝트 추적)
# 예: ["PROJ1", "PROJ2", "DEV"]
PROJECT_KEYS = []  

def connect_to_jira():
    """Jira에 연결"""
    try:
        jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN))
        return jira
    except Exception as e:
        print(f"Jira 연결 실패: {e}")
        return None

def get_last_check_time():
    """마지막 확인 시간 가져오기"""
    if os.path.exists(LAST_CHECK_FILE):
        with open(LAST_CHECK_FILE, 'r') as f:
            return f.read().strip()
    # 기본값: 24시간 전
    return (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

def save_last_check_time():
    """현재 시간을 마지막 확인 시간으로 저장"""
    with open(LAST_CHECK_FILE, 'w') as f:
        f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

def get_my_notifications(jira, last_check_time, days=7):
    """나와 관련된 이슈만 가져오기"""
    notifications = {
        'assigned': [],     # 나에게 할당된 이슈
        'mentioned': [],    # 댓글에서 멘션된 이슈
        'commented': [],    # 내가 댓글을 단 이슈
        'created': [],      # 내가 생성한 이슈
        'watching': []      # 내가 지켜보는 이슈
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
    if PROJECT_KEYS:
        projects = ", ".join(f'"{key}"' for key in PROJECT_KEYS)
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
        
        return notifications
    except Exception as e:
        print(f"알림 검색 실패: {e}")
        return notifications

def get_issue_comments(jira, issue_key, last_check_time):
    """이슈의 최근 댓글 가져오기"""
    try:
        issue = jira.issue(issue_key)
        recent_comments = []
        
        for comment in issue.fields.comment.comments:
            comment_date = datetime.datetime.strptime(
                comment.created.split('.')[0], 
                "%Y-%m-%dT%H:%M:%S"
            )
            check_date = datetime.datetime.strptime(
                last_check_time, 
                "%Y-%m-%d %H:%M"
            )
            
            if comment_date > check_date:
                recent_comments.append({
                    'author': comment.author.displayName,
                    'body': comment.body,
                    'created': comment.created.split('T')[0] + ' ' + comment.created.split('T')[1].split('.')[0],
                    'created_date': comment_date
                })
        
        return recent_comments
    except Exception as e:
        print(f"댓글 가져오기 실패 ({issue_key}): {e}")
        return []

def issue_to_markdown(issue, comments=None):
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
    
    # 댓글
    if comments and len(comments) > 0:
        markdown += f"## Recent Comments\n\n"
        for comment in comments:
            markdown += f"### {comment['author']} - {comment['created']}\n\n"
            markdown += f"{comment['body']}\n\n"
    
    # Jira 링크
    markdown += f"---\n[View in Jira]({JIRA_SERVER}/browse/{issue.key})"
    
    return markdown

def save_to_obsidian(issue, markdown_content):
    """Markdown 콘텐츠를 Obsidian 볼트에 저장 (프로젝트별 폴더 구조)"""
    # 프로젝트 키로 폴더 생성
    project_key = issue.fields.project.key
    project_path = os.path.join(OBSIDIAN_VAULT_PATH, JIRA_BASE_FOLDER, project_key)
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

def create_notification_summary(issue, notification_type, comments=None):
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
    file_path = f"{JIRA_BASE_FOLDER}/{fields.project.key}/{issue.key} - {fields.summary[:30].replace('/', '-').replace('\\', '-').replace(':', '-')}"
    summary += f"[이슈 상세 보기](obsidian://open?vault={os.path.basename(OBSIDIAN_VAULT_PATH)}&file={file_path})\n"
    summary += f"[Jira에서 보기]({JIRA_SERVER}/browse/{issue.key})\n\n"
    
    summary += "---\n\n"  # 구분선
    
    return summary

def create_daily_note(date, notifications):
    """특정 날짜의 알림 노트 생성"""
    daily_path = os.path.join(OBSIDIAN_VAULT_PATH, DAILY_NOTES_FOLDER)
    Path(daily_path).mkdir(parents=True, exist_ok=True)
    
    # YYYY-MM-DD 형식의 파일명
    file_name = f"{date.strftime('%Y-%m-%d')}.md"
    file_path = os.path.join(daily_path, file_name)
    
    # 이미 파일이 존재하는 경우 내용 로드
    existing_content = ""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()
    
    # 프론트매터 준비
    front_matter = f"""---
date: {date.strftime('%Y-%m-%d')}
tags: [jira-daily, notifications]
---

"""
    
    # 본문 준비
    weekday_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    weekday = weekday_names[date.weekday()]
    title = f"# Jira 알림 - {date.strftime('%Y년 %m월 %d일')} ({weekday})\n\n"
    
    # 새로운 알림이 있는지 확인
    if notifications:
        content = f"오늘 발생한 Jira 알림 {len(notifications)}건을 확인하세요.\n\n"
        
        # 알림 유형별로 분류
        by_type = {
            "assigned": [],
            "mentioned": [],
            "commented": [],
            "created": [],
            "watching": []
        }
        
        for notif in notifications:
            by_type[notif['type']].append(notif)
        
        # 유형별로 알림 추가
        for type_name, type_label in [
            ("assigned", "📌 나에게 할당된 이슈"),
            ("mentioned", "💬 댓글에서 멘션됨"),
            ("commented", "🗨️ 내가 댓글을 단 이슈"),
            ("created", "✅ 내가 생성한 이슈"),
            ("watching", "👁️ 내가 지켜보는 이슈")
        ]:
            if by_type[type_name]:
                content += f"## {type_label} ({len(by_type[type_name])}건)\n\n"
                for notif in by_type[type_name]:
                    content += notif['summary']
        
        full_content = title + content
    else:
        # 새로운 알림이 없는 경우
        full_content = title + "오늘 새로운 Jira 알림이 없습니다.\n\n"
    
    # 파일 내용 생성 (새로 생성 또는 업데이트)
    if existing_content:
        # 기존 내용이 있으면, 프론트매터는 유지하고 내용만 업데이트
        if "---" in existing_content:
            parts = existing_content.split("---", 2)
            if len(parts) >= 3:
                # 프론트매터가 있는 경우
                updated_content = f"---{parts[1]}---\n\n{full_content}"
            else:
                # 프론트매터가 없는 경우
                updated_content = front_matter + full_content
        else:
            # 프론트매터가 없는 경우
            updated_content = front_matter + full_content
    else:
        # 새 파일 생성
        updated_content = front_matter + full_content
    
    # 파일 저장
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    return file_path

def create_weekly_note(week_start_date, daily_notes):
    """주간 알림 노트 생성"""
    weekly_path = os.path.join(OBSIDIAN_VAULT_PATH, DAILY_NOTES_FOLDER, "Weekly")
    Path(weekly_path).mkdir(parents=True, exist_ok=True)
    
    # 해당 주의 월요일 날짜로 파일명 생성
    week_number = week_start_date.strftime('%U')  # 연중 주차
    file_name = f"{week_start_date.strftime('%Y')}-W{week_number}.md"
    file_path = os.path.join(weekly_path, file_name)
    
    # 주 범위 계산 (월요일~일요일)
    week_end_date = week_start_date + datetime.timedelta(days=6)
    
    # 프론트매터
    front_matter = f"""---
week: {week_number}
start_date: {week_start_date.strftime('%Y-%m-%d')}
end_date: {week_end_date.strftime('%Y-%m-%d')}
tags: [jira-weekly, notifications]
---

"""
    
    # 본문
    title = f"# Jira 주간 알림 - {week_start_date.strftime('%Y년 %m월 %d일')} ~ {week_end_date.strftime('%Y년 %m월 %d일')}\n\n"
    
    content = f"이번 주에 발생한 Jira 활동 요약입니다.\n\n"
    
    # 일별 노트 링크
    content += "## 일별 알림\n\n"
    
    for day in range(7):
        date = week_start_date + datetime.timedelta(days=day)
        weekday_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        weekday = weekday_names[date.weekday()]
        
        date_str = date.strftime('%Y-%m-%d')
        if date_str in daily_notes:
            content += f"- [[{DAILY_NOTES_FOLDER}/{date_str}|{date.strftime('%Y년 %m월 %d일')} ({weekday})]] - {daily_notes[date_str]}건의 알림\n"
        else:
            content += f"- {date.strftime('%Y년 %m월 %d일')} ({weekday}) - 알림 없음\n"
    
    content += "\n"
    
    # 파일 저장
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(front_matter + title + content)
    
    return file_path

def create_monthly_note(month_date, weekly_notes):
    """월간 알림 노트 생성"""
    monthly_path = os.path.join(OBSIDIAN_VAULT_PATH, DAILY_NOTES_FOLDER, "Monthly")
    Path(monthly_path).mkdir(parents=True, exist_ok=True)
    
    # 해당 월의 첫째 날짜로 파일명 생성
    file_name = f"{month_date.strftime('%Y-%m')}.md"
    file_path = os.path.join(monthly_path, file_name)
    
    # 월의 마지막 날 계산
    if month_date.month == 12:
        next_month = datetime.date(month_date.year + 1, 1, 1)
    else:
        next_month = datetime.date(month_date.year, month_date.month + 1, 1)
    
    last_day = (next_month - datetime.timedelta(days=1)).day
    month_end_date = datetime.date(month_date.year, month_date.month, last_day)
    
    # 프론트매터
    front_matter = f"""---
year: {month_date.year}
month: {month_date.month}
start_date: {month_date.strftime('%Y-%m-%d')}
end_date: {month_end_date.strftime('%Y-%m-%d')}
tags: [jira-monthly, notifications]
---

"""
    
    # 본문
    title = f"# Jira 월간 알림 - {month_date.strftime('%Y년 %m월')}\n\n"
    
    content = f"{month_date.strftime('%Y년 %m월')}에 발생한 Jira 활동 요약입니다.\n\n"
    
    # 주간 노트 링크
    content += "## 주간 알림\n\n"
    
    # 해당 월의 주차 정보 정렬
    sorted_weeks = sorted(weekly_notes.keys())
    
    for week in sorted_weeks:
        week_start_date = datetime.datetime.strptime(weekly_notes[week]['start_date'], '%Y-%m-%d').date()
        week_end_date = datetime.datetime.strptime(weekly_notes[week]['end_date'], '%Y-%m-%d').date()
        
        # 이번 달에 해당하는 주차만 포함
        if (week_start_date.month == month_date.month or week_end_date.month == month_date.month) and \
           (week_start_date.year == month_date.year or week_end_date.year == month_date.year):
            content += f"- [[{DAILY_NOTES_FOLDER}/Weekly/{week}|{week_start_date.strftime('%Y년 %m월 %d일')} ~ {week_end_date.strftime('%Y년 %m월 %d일')}]] - {weekly_notes[week]['count']}건의 알림\n"
    
    content += "\n"
    
    # 파일 저장
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(front_matter + title + content)
    
    return file_path

def create_notification_index():
    """알림 인덱스 페이지 생성"""
    index_path = os.path.join(OBSIDIAN_VAULT_PATH, DAILY_NOTES_FOLDER, "알림 인덱스.md")
    
    # 오늘 날짜
    today = datetime.date.today()
    
    # 프론트매터
    front_matter = f"""---
created: {today.strftime('%Y-%m-%d')}
tags: [jira-index, notifications]
---

"""
    
    # 본문
    title = "# Jira 알림 인덱스\n\n"
    
    content = "Jira 알림을 날짜별, 주별, 월별로 확인할 수 있습니다.\n\n"
    
    # 최근 알림
    content += "## 최근 알림\n\n"
    
    # 최근 7일간 일자
    for days_ago in range(7):
        date = today - datetime.timedelta(days=days_ago)
        weekday_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        weekday = weekday_names[date.weekday()]
        
        date_str = date.strftime('%Y-%m-%d')
        date_file = os.path.join(DAILY_NOTES_FOLDER, date_str)
        if os.path.exists(os.path.join(OBSIDIAN_VAULT_PATH, f"{date_file}.md")):
            content += f"- [[{date_file}|{date.strftime('%Y년 %m월 %d일')} ({weekday})]]\n"
        else:
            content += f"- {date.strftime('%Y년 %m월 %d일')} ({weekday}) - 알림 없음\n"
    
    # 주간 알림
    content += "\n## 주간 알림\n\n"
    
    # 최근 4주
    for weeks_ago in range(4):
        # 이번 주 월요일 찾기
        days_since_monday = today.weekday()
        monday = today - datetime.timedelta(days=days_since_monday + 7*weeks_ago)
        sunday = monday + datetime.timedelta(days=6)
        
        week_number = monday.strftime('%U')
        week_str = f"{monday.strftime('%Y')}-W{week_number}"
        week_file = os.path.join(DAILY_NOTES_FOLDER, "Weekly", week_str)
        
        if os.path.exists(os.path.join(OBSIDIAN_VAULT_PATH, f"{week_file}.md")):
            content += f"- [[{week_file}|{monday.strftime('%Y년 %m월 %d일')} ~ {sunday.strftime('%Y년 %m월 %d일')}]]\n"
        else:
            content += f"- {monday.strftime('%Y년 %m월 %d일')} ~ {sunday.strftime('%Y년 %m월 %d일')}\n"
    
    # 월간 알림
    content += "\n## 월간 알림\n\n"
    
    # 최근 3개월
    for months_ago in range(3):
        # n개월 전 날짜 계산
        year = today.year
        month = today.month - months_ago
        
        # 월이 0 이하면 작년으로 조정
        while month <= 0:
            year -= 1
            month += 12
        
        month_date = datetime.date(year, month, 1)
        month_str = month_date.strftime('%Y-%m')
        month_file = os.path.join(DAILY_NOTES_FOLDER, "Monthly", month_str)
        
        if os.path.exists(os.path.join(OBSIDIAN_VAULT_PATH, f"{month_file}.md")):
            content += f"- [[{month_file}|{month_date.strftime('%Y년 %m월')}]]\n"
        else:
            content += f"- {month_date.strftime('%Y년 %m월')}\n"
    
    # 파일 저장
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(front_matter + title + content)
    
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

def main():
    """메인 실행 함수"""
    # Jira 연결
    jira = connect_to_jira()
    if not jira:
        return
    
    # 마지막 확인 시간 가져오기
    last_check_time = get_last_check_time()
    print(f"마지막 확인 시간: {last_check_time}")
    
    # 나와 관련된 알림만 가져오기
    notifications = get_my_notifications(jira, last_check_time, days=7)
    
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
    all_issues = remove_duplicates(all_issues)
    print(f"총 알림 이슈 (중복 제거): {len(all_issues)}개")
    
    # 프로젝트별로 이슈 분류 및 저장
    projects = {}
    saved_files = []
    
    for issue in all_issues:
        project_key = issue.fields.project.key
        if project_key not in projects:
            projects[project_key] = []
        projects[project_key].append(issue)
        
        # 최근 댓글 가져오기
        comments = get_issue_comments(jira, issue.key, last_check_time)
        
        # Markdown 변환
        markdown = issue_to_markdown(issue, comments)
        
        # Obsidian에 저장
        file_path = save_to_obsidian(issue, markdown)
        saved_files.append(file_path)
        
        print(f"저장됨: {file_path}")
    
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
            comments = get_issue_comments(jira, issue.key, last_check_time)
            
            # 알림 요약 생성
            summary = create_notification_summary(issue, notification_type, comments)
            
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
        note_path = create_daily_note(date, notifications_list)
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
                note_path = create_weekly_note(current_monday, week_daily_notes)
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
            note_path = create_monthly_note(month_date, created_weekly_notes)
            print(f"월간 알림 생성: {note_path}")
    
    # 알림 인덱스 생성
    index_path = create_notification_index()
    print(f"알림 인덱스 생성: {index_path}")
    
    # 현재 시간을 마지막 확인 시간으로 저장
    save_last_check_time()
    
    print(f"총 {len(saved_files)}개의 이슈가 Obsidian에 동기화되었습니다.")
    print(f"총 {len(created_daily_notes)}일의 알림 노트가 생성되었습니다.")

if __name__ == "__main__":
    main()