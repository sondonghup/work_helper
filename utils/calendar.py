import logging
from typing import Dict, Any, Optional, List
from dateutil import parser
import datetime
from .applescript import (
    run_applescript_async,
    format_applescript_value,
)

logger = logging.getLogger(__name__)

class CalendarModule:
    
    async def check_calendar_access(self) -> bool:
        try:
            script = """
            try
                tell application 'Calendar'
                    get name
                    return true
                end tell
            on error
                return false
            end try
            """
            result = await run_applescript_async(script)
            return result.lower().strip() == "true"
        except Exception as e:
            logger.error(f"cannot access calendar: {e}")
            return False
            
    async def create_event(
        self,
        title: str,
        start_date: str,
        end_date: str,
        location: Optional[str] = None,
        notes: Optional[str] = None,
        calendar_name: Optional[str] = None
    ) -> Dict[str, Any]:

        logger.info(f"start_date: {start_date}")
        logger.info(f"end_date: {end_date}")

        try:
            # AppleScript-safe 문자열
            safe_title = format_applescript_value(title)
            
            # 시작 날짜와 끝 날짜를 설정하는 AppleScript 코드
            date_setup_script = self._create_date_setup_script(start_date, end_date)

            # 추가 속성 설정
            properties = f"{{summary:{safe_title}, start date:theStartDate, end date:theEndDate"
            
            # location이 제공된 경우 추가
            if location:
                safe_location = format_applescript_value(location)
                properties += f", location:{safe_location}"
            
            # notes가 제공된 경우 추가
            if notes:
                safe_notes = format_applescript_value(notes)
                properties += f", description:{safe_notes}"
            
            # 속성 닫기
            properties += "}"
            
            if calendar_name:
                logger.info(f"Calendar name: {calendar_name}")
                safe_cal_name = format_applescript_value(calendar_name)
                script = f"""
                {date_setup_script}
                
                tell application "Calendar"
                    try
                        set foundCalendar to missing value
                        set allCalendars to every calendar
                        
                        repeat with c in allCalendars
                            set calName to name of c as string
                            set targetName to {safe_cal_name} as string
                            
                            if calName is equal to targetName then
                                set foundCalendar to c
                                exit repeat
                            end if
                        end repeat
                        
                        if foundCalendar is missing value then
                            set foundCalendar to first calendar whose writable is true
                        end if
                        
                        tell foundCalendar
                            make new event at end with properties {properties}
                            return "SUCCESS:Event created successfully in calendar " & name of foundCalendar
                        end tell
                    on error errMsg
                        return "ERROR:" & errMsg
                    end try
                end tell
                """
            else:
                script = f"""
                {date_setup_script}
                
                tell application "Calendar"
                    try
                        set defaultCalendar to first calendar whose writable is true
                        
                        tell defaultCalendar
                            make new event at end with properties {properties}
                            return "SUCCESS:Event created successfully in default calendar " & name of defaultCalendar
                        end tell
                    on error errMsg
                        return "ERROR:" & errMsg
                    end try
                end tell
                """

            logger.debug(f"Executing AppleScript:\n{script}")
            result = await run_applescript_async(script)
            logger.info(f"AppleScript result: {result}")
            success = result.startswith("SUCCESS:")
            return {
                "success": success,
                "message": result.replace("SUCCESS:", "").replace("ERROR:", "")
            }
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return {
                "success": False,
                "message": str(e)
            }
    
    def _create_date_setup_script(self, start_date: str, end_date: str) -> str:
        """
        ISO 형식의 시작 및 종료 날짜 문자열을 AppleScript의 날짜 설정 코드로 변환합니다.
        """
        try:
            # 시작 날짜 파싱
            start_dt = parser.parse(start_date)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)
            start_dt = start_dt.astimezone()  # 로컬 시간대로 변환
            
            # 종료 날짜 파싱
            end_dt = parser.parse(end_date)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=datetime.timezone.utc)
            end_dt = end_dt.astimezone()  # 로컬 시간대로 변환
            
            # 날짜 차이 계산 (현재 날짜로부터 얼마나 떨어져 있는지)
            now = datetime.datetime.now().astimezone()
            days_diff = (start_dt.date() - now.date()).days
            
            # AppleScript 날짜 설정 코드 생성
            script = f"""
            set theStartDate to (current date)
            """
            
            # 날짜 조정
            if days_diff != 0:
                script += f"set theStartDate to theStartDate + ({days_diff} * days)\n"
            
            # 시간, 분, 초 설정
            script += f"""
            set hours of theStartDate to {start_dt.hour}
            set minutes of theStartDate to {start_dt.minute}
            set seconds of theStartDate to {start_dt.second}
            """
            
            # 이벤트 기간 계산 (시간 단위)
            duration_hours = (end_dt - start_dt).total_seconds() / 3600
            script += f"""
            set theEndDate to theStartDate + ({duration_hours} * hours)
            """
            
            return script
        except Exception as e:
            logger.error(f"Error creating date setup script: {e}")
            # 문제가 있을 경우, 원래 문자열 포맷 사용
            return f"""
            set theStartDate to date "{start_date}"
            set theEndDate to date "{end_date}"
            """