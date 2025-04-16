#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
슬랙의 특정 채널에서 메시지와 댓글을 가져와 Obsidian에 날짜별로 저장하는 스크립트
"""

import os
import time
import datetime
from pathlib import Path
from collections import defaultdict
import slack_sdk
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

# 환경 변수에서 설정 가져오기
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
CHANNEL_NAME = os.getenv("SLACK_CHANNEL_NAME", "llm-app")  # 기본값 설정
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH")
SLACK_BASE_FOLDER = os.getenv("SLACK_BASE_FOLDER", "Slack")  # 기본값 설정
OLDEST_TIMESTAMP = os.getenv("OLDEST_TIMESTAMP")  # 2024년 4월 1일 타임스탬프 또는 그 이후

def initialize_slack_client():
    """슬랙 클라이언트 초기화"""
    if not SLACK_TOKEN:
        print("오류: SLACK_TOKEN 환경 변수가 설정되지 않았습니다.")
        return None
    
    client = slack_sdk.WebClient(token=SLACK_TOKEN)
    try:
        # 연결 테스트
        client.auth_test()
        return client
    except SlackApiError as e:
        print(f"슬랙 연결 오류: {e}")
        return None

def get_channel_id(client, channel_name):
    """채널 이름으로 채널 ID 가져오기"""
    try:
        result = client.conversations_list()
        for channel in result["channels"]:
            if channel["name"] == channel_name:
                return channel["id"]
        
        print(f"채널을 찾을 수 없음: {channel_name}")
        return None
    except SlackApiError as e:
        print(f"채널 목록 조회 오류: {e}")
        return None

def timestamp_to_date(ts):
    """슬랙 타임스탬프를 datetime 객체로 변환"""
    return datetime.datetime.fromtimestamp(float(ts))

def get_channel_messages(client, channel_id, oldest=None):
    """채널의 메시지 가져오기"""
    messages = []
    cursor = None
    
    while True:
        try:
            # 요청 파라미터 구성
            params = {
                "channel": channel_id,
                "limit": 100  # 한 번에 가져올 최대 메시지 수
            }
            
            if oldest:
                params["oldest"] = oldest
                
            if cursor:
                params["cursor"] = cursor
            
            # 메시지 가져오기
            response = client.conversations_history(**params)
            messages.extend(response["messages"])
            
            # 다음 페이지가 있는지 확인
            if response["has_more"]:
                cursor = response["response_metadata"]["next_cursor"]
            else:
                break
            
            # API 속도 제한 방지
            time.sleep(1)
            
        except SlackApiError as e:
            print(f"메시지 조회 오류: {e}")
            break
    
    return messages

def get_message_replies(client, channel_id, thread_ts):
    """메시지 스레드의 댓글 가져오기"""
    replies = []
    cursor = None
    
    while True:
        try:
            # 요청 파라미터 구성
            params = {
                "channel": channel_id,
                "ts": thread_ts,
                "limit": 100  # 한 번에 가져올 최대 댓글 수
            }
            
            if cursor:
                params["cursor"] = cursor
            
            # 댓글 가져오기
            response = client.conversations_replies(**params)
            
            # 첫 번째 메시지는 원본 메시지이므로 제외
            if len(replies) == 0 and len(response["messages"]) > 0:
                replies.extend(response["messages"][1:])
            else:
                replies.extend(response["messages"])
            
            # 다음 페이지가 있는지 확인
            if response["has_more"]:
                cursor = response["response_metadata"]["next_cursor"]
            else:
                break
            
            # API 속도 제한 방지
            time.sleep(0.5)
            
        except SlackApiError as e:
            print(f"댓글 조회 오류: {e}")
            break
    
    return replies

def get_user_info(client, user_id):
    """사용자 ID로 사용자 정보 가져오기"""
    try:
        response = client.users_info(user=user_id)
        user = response["user"]
        return {
            "id": user_id,
            "name": user.get("real_name", user.get("name", "Unknown")),
            "display_name": user.get("profile", {}).get("display_name", ""),
            "image": user.get("profile", {}).get("image_72", "")
        }
    except SlackApiError as e:
        print(f"사용자 정보 조회 오류: {e}")
        return {
            "id": user_id,
            "name": "Unknown User",
            "display_name": "",
            "image": ""
        }

def enrich_message_with_user_info(client, message):
    """메시지에 사용자 정보 추가"""
    if "user" in message:
        user_info = get_user_info(client, message["user"])
        message["user_info"] = user_info
    return message

def format_message_to_markdown(message, channel_name):
    """메시지를 마크다운 형식으로 변환"""
    # 사용자 정보 가져오기
    user_name = message.get("user_info", {}).get("name", "Unknown User")
    display_name = message.get("user_info", {}).get("display_name", "")
    
    # 사용자 표시 이름 결정 (display_name이 있으면 사용, 없으면 name 사용)
    user_display = display_name if display_name else user_name
    
    # 타임스탬프를 날짜와 시간으로 변환
    ts_date = timestamp_to_date(message["ts"])
    formatted_date = ts_date.strftime("%Y-%m-%d %H:%M:%S")
    
    # 메시지 텍스트 가져오기
    text = message.get("text", "")
    
    # 마크다운 형식으로 메시지 포맷팅
    markdown = f"## {user_display} - {formatted_date}\n\n"
    markdown += f"{text}\n\n"
    
    # 첨부 파일이 있는 경우
    if "files" in message:
        for file in message["files"]:
            file_name = file.get("name", "Unknown file")
            file_url = file.get("url_private", "")
            markdown += f"**첨부 파일:** [{file_name}]({file_url})\n"
        markdown += "\n"
    
    # 메시지 링크 추가
    message_link = f"https://{os.getenv('SLACK_WORKSPACE')}.slack.com/archives/{channel_name}/{message['ts'].replace('.', '')}"
    markdown += f"[슬랙에서 보기]({message_link})\n\n"
    
    # 구분선 추가
    markdown += "---\n\n"
    
    return markdown

def format_replies_to_markdown(replies):
    """댓글을 마크다운 형식으로 변환"""
    if not replies:
        return ""
    
    markdown = "### 댓글\n\n"
    
    for reply in replies:
        # 사용자 정보 가져오기
        user_name = reply.get("user_info", {}).get("name", "Unknown User")
        display_name = reply.get("user_info", {}).get("display_name", "")
        
        # 사용자 표시 이름 결정
        user_display = display_name if display_name else user_name
        
        # 타임스탬프를 날짜와 시간으로 변환
        ts_date = timestamp_to_date(reply["ts"])
        formatted_date = ts_date.strftime("%Y-%m-%d %H:%M:%S")
        
        # 댓글 텍스트 가져오기
        text = reply.get("text", "")
        
        # 마크다운 형식으로 댓글 포맷팅
        markdown += f"#### {user_display} - {formatted_date}\n\n"
        markdown += f"{text}\n\n"
        
        # 첨부 파일이 있는 경우
        if "files" in reply:
            for file in reply["files"]:
                file_name = file.get("name", "Unknown file")
                file_url = file.get("url_private", "")
                markdown += f"**첨부 파일:** [{file_name}]({file_url})\n"
            markdown += "\n"
    
    return markdown

def save_to_obsidian(messages_by_date, channel_name, obsidian_vault_path, slack_base_folder):
    """날짜별로 메시지를 Obsidian에 저장"""
    saved_files = []
    
    for date_str, messages in messages_by_date.items():
        # 날짜별 폴더 생성
        date_path = os.path.join(obsidian_vault_path, slack_base_folder, channel_name, date_str)
        Path(date_path).mkdir(parents=True, exist_ok=True)
        
        # 파일명 생성
        file_name = f"{date_str}.md"
        file_path = os.path.join(date_path, file_name)
        
        # 메타데이터 준비
        front_matter = f"""---
date: {date_str}
channel: {channel_name}
messages_count: {len(messages)}
tags: [slack, {channel_name.lower()}, daily]
---

# {channel_name} - {date_str}

이 문서는 {channel_name} 채널의 {date_str} 날짜 메시지를 포함합니다.

"""
        
        # 본문 내용 생성
        content = front_matter
        
        # 메시지 추가
        for message_data in messages:
            message = message_data["message"]
            replies = message_data["replies"]
            
            # 메시지와 댓글을 마크다운으로 변환
            message_markdown = format_message_to_markdown(message, channel_name)
            replies_markdown = format_replies_to_markdown(replies)
            
            content += message_markdown + replies_markdown
        
        # 파일 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        saved_files.append(file_path)
        print(f"저장됨: {file_path} (메시지 {len(messages)}개)")
    
    return saved_files

def create_index_file(dates, channel_name, obsidian_vault_path, slack_base_folder):
    """인덱스 파일 생성"""
    # 폴더 생성
    index_path = os.path.join(obsidian_vault_path, slack_base_folder, channel_name)
    Path(index_path).mkdir(parents=True, exist_ok=True)
    
    # 파일명 생성
    file_name = "index.md"
    file_path = os.path.join(index_path, file_name)
    
    # 현재 날짜
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 메타데이터 준비
    front_matter = f"""---
created: {today}
channel: {channel_name}
dates_count: {len(dates)}
tags: [slack, {channel_name.lower()}, index]
---

# {channel_name} 채널 메시지 인덱스

이 문서는 {channel_name} 채널의 날짜별 메시지 인덱스입니다.

마지막 업데이트: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

"""
    
    # 본문 내용 생성
    content = front_matter
    content += "## 날짜별 메시지\n\n"
    
    # 최신 날짜순으로 정렬
    sorted_dates = sorted(dates, reverse=True)
    
    for date_str in sorted_dates:
        content += f"- [[{slack_base_folder}/{channel_name}/{date_str}/{date_str}|{date_str}]] - {dates[date_str]}개 메시지\n"
    
    # 파일 저장
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"인덱스 생성: {file_path}")
    return file_path

def main():
    """메인 실행 함수"""
    # 필수 환경 변수 확인
    if not all([SLACK_TOKEN, OBSIDIAN_VAULT_PATH]):
        print("오류: 필수 환경 변수가 설정되지 않았습니다.")
        print("SLACK_TOKEN, OBSIDIAN_VAULT_PATH를 설정해주세요.")
        return
    
    # 슬랙 클라이언트 초기화
    client = initialize_slack_client()
    if not client:
        return
    
    # 채널 ID 가져오기
    channel_id = get_channel_id(client, CHANNEL_NAME)
    if not channel_id:
        return
    
    # 메시지 가져오기
    messages = get_channel_messages(client, channel_id, OLDEST_TIMESTAMP)
    print(f"총 {len(messages)}개의 메시지를 가져왔습니다.")
    
    # 메시지 정보 강화
    enriched_messages = []
    for msg in messages:
        # 사용자 정보 추가
        enriched_msg = enrich_message_with_user_info(client, msg)
        enriched_messages.append(enriched_msg)
    
    # 날짜별로 메시지 분류
    messages_by_date = defaultdict(list)
    
    for message in enriched_messages:
        # 타임스탬프를 날짜로 변환
        date = timestamp_to_date(message["ts"]).strftime("%Y-%m-%d")
        
        # 댓글이 있는 경우 댓글 가져오기
        replies = []
        if message.get("reply_count", 0) > 0:
            raw_replies = get_message_replies(client, channel_id, message["ts"])
            # 댓글에 사용자 정보 추가
            for reply in raw_replies:
                enriched_reply = enrich_message_with_user_info(client, reply)
                replies.append(enriched_reply)
        
        # 날짜별로 메시지와 댓글 저장
        messages_by_date[date].append({
            "message": message,
            "replies": replies
        })
    
    # Obsidian에 저장
    saved_files = save_to_obsidian(messages_by_date, CHANNEL_NAME, OBSIDIAN_VAULT_PATH, SLACK_BASE_FOLDER)
    
    # 인덱스 파일 생성
    dates_count = {date: len(messages) for date, messages in messages_by_date.items()}
    index_path = create_index_file(dates_count, CHANNEL_NAME, OBSIDIAN_VAULT_PATH, SLACK_BASE_FOLDER)
    
    print(f"총 {len(saved_files)}개의 날짜 파일이 Obsidian에 동기화되었습니다.")

if __name__ == "__main__":
    main()