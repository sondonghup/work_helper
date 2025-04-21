import imaplib
from dotenv import load_dotenv  
import os
import email
from email.header import decode_header
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import pytz

load_dotenv()

# Obsidian 설정
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "/Users/sondonghyeob/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report/")
GMAIL_FOLDER = "Gmail"

def save_emails_to_obsidian(emails):
    # Gmail 폴더 생성
    gmail_path = os.path.join(OBSIDIAN_VAULT_PATH, GMAIL_FOLDER)
    os.makedirs(gmail_path, exist_ok=True)
    
    # 이메일을 날짜별로 그룹화
    emails_by_date = {}
    for email in emails:
        date = email['date'].strftime('%Y-%m-%d')
        if date not in emails_by_date:
            emails_by_date[date] = []
        emails_by_date[date].append(email)
    
    # 각 날짜별로 파일 생성
    for date, date_emails in emails_by_date.items():
        # 날짜별 폴더 생성
        date_folder = os.path.join(gmail_path, date)
        os.makedirs(date_folder, exist_ok=True)
        
        # 각 이메일을 별도 파일로 저장
        for idx, email in enumerate(date_emails, 1):
            file_path = os.path.join(date_folder, f"{date}_{idx}.md")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# {email['subject']}\n\n")
                f.write(f"- **보낸 사람**: {email['from']}\n")
                f.write(f"- **시간**: {email['date'].strftime('%H:%M')}\n")
                f.write("\n**내용**:\n")
                f.write(f"{email['content']}\n")

def get_megastudy_emails():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")

    mail.login(os.getenv("GMAIL_ID"), os.getenv("GMAIL_PASSWORD"))

    mail.select("INBOX")

    # 일주일 전 날짜 계산
    one_week_ago = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
    
    # megastudy.net이 포함된 이메일 중 최근 일주일 것만 검색
    search_criteria = f'(FROM "@megastudy.net" SINCE "{one_week_ago}")'
    _, message_numbers = mail.search(None, search_criteria)

    emails = []

    # 각 이메일 처리
    for num in message_numbers[0].split():
        _, msg_data = mail.fetch(num, '(RFC822)')
        email_body = msg_data[0][1]
        email_message = email.message_from_bytes(email_body)
        
        # 이메일 정보 추출
        subject, encoding = decode_header(email_message["subject"])[0]
        if isinstance(subject, bytes):
            try:
                subject = subject.decode(encoding if encoding else 'utf-8')
            except:
                subject = subject.decode('utf-8', errors='replace')
            
        from_addr = email_message["from"]
        date = parsedate_to_datetime(email_message["date"])
        
        # 본문 내용 추출
        content = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        content = part.get_payload(decode=True).decode('utf-8')
                    except:
                        content = part.get_payload(decode=True).decode('utf-8', errors='replace')
                    break
        else:
            try:
                content = email_message.get_payload(decode=True).decode('utf-8')
            except:
                content = email_message.get_payload(decode=True).decode('utf-8', errors='replace')
        
        emails.append({
            "subject": subject,
            "from": from_addr,
            "date": date,
            "content": content
        })

    # 이메일을 Obsidian에 저장
    save_emails_to_obsidian(emails)
    
    # 연결 종료
    mail.close()
    mail.logout()

    return emails

# 사용 예시
if __name__ == "__main__":
    megastudy_emails = get_megastudy_emails()