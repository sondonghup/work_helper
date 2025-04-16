# Jira to Obsidian 동기화 스크립트

이 스크립트는 Jira에서 나와 관련된 이슈와 알림을 가져와 Obsidian에 동기화합니다.

## 기능

- 나와 관련된 Jira 이슈만 가져오기 (할당된 이슈, 멘션된 이슈, 댓글 단 이슈, 생성한 이슈, 지켜보는 이슈)
- 각 이슈의 모든 댓글을 함께 가져오기
- 이슈와 댓글을 Markdown 형식으로 변환하여 Obsidian에 저장
- 날짜별/주별/월별 알림 노트 생성
- 프로젝트별로 이슈 구조화 및 저장

## 요구사항

- Python 3.6 이상
- python-jira
- python-dotenv

## 설치 방법

1. 필요한 패키지 설치:
```
pip install jira python-dotenv
```

2. 환경 변수 설정:
   - `.env-sample` 파일을 `.env`로 복사하고 필요한 정보를 입력합니다.
   ```
   cp .env-sample .env
   ```
   - `.env` 파일을 편집하여 Jira 서버, 계정 정보, Obsidian 볼트 경로 등을 입력합니다.

## 사용 방법

1. 스크립트 실행:
```
python jira_obsidian_main.py
```

2. 실행 결과:
   - 각 프로젝트별로 이슈가 Obsidian에 Markdown 파일로 저장됩니다.
   - 일별, 주별, 월별 알림 노트가 생성됩니다.
   - 알림 인덱스 페이지가 생성됩니다.

## 자동화 설정

### Windows에서 작업 스케줄러 설정
1. 작업 스케줄러 열기
2. "작업 만들기" 선택
3. 트리거 설정 (예: 매일 오전 9시)
4. 동작 설정: 프로그램 시작
   - 프로그램/스크립트: `python`
   - 인수 추가: `스크립트_경로\jira_obsidian_main.py`
   - 시작 위치: `스크립트_경로`

### Linux/Mac에서 crontab 설정
```bash
# 편집기 열기
crontab -e

# 매일 오전 9시에 실행
0 9 * * * cd /스크립트_경로 && python jira_obsidian_main.py
```

## 파일 구조

- `jira_obsidian_main.py`: 메인 실행 스크립트
- `jira_obsidian_utils.py`: 유틸리티 함수 모듈
- `.env`: 환경 변수 설정 파일

## 작동 방식

1. Jira API를 통해 나와 관련된 이슈 정보를 가져옵니다.
2. 각 이슈의 모든 댓글을 가져옵니다.
3. 이슈와 댓글을 Markdown 형식으로 변환합니다.
4. Obsidian 볼트에 프로젝트별로 구조화하여 저장합니다.
5. 날짜별로 알림을 정리하여 일별/주별/월별 노트를 생성합니다.
6. 마지막 확인 시간을 저장하여 다음 실행 시 새로운 업데이트만 가져옵니다.

## 주의 사항

- API 토큰은 Atlassian 계정 관리에서 생성할 수 있습니다.
- Obsidian 볼트 경로는 반드시 절대 경로로 입력해야 합니다.
- 큰 규모의 Jira 프로젝트의 경우 초기 실행 시 시간이 오래 걸릴 수 있습니다.