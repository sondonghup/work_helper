import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from .applescript import (
    run_applescript_async,
    AppleScriptError,
    format_applescript_value,
    parse_applescript_record,
    parse_applescript_list
)

logger = logging.getLogger(__name__)

class CalendarModule:
    
    async def check_calendar_access(self) -> bool:

        try:
            script = """
            try
                tell apllication "Calendar"
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
            
    import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from .applescript import (
    run_applescript_async,
    AppleScriptError,
    format_applescript_value,
    parse_applescript_record,
    parse_applescript_list
)

logger = logging.getLogger(__name__)

class CalendarModule:
    
    async def check_calendar_access(self) -> bool:

        try:
            script = """
            try
                tell apllication "Calendar"
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
        
        # AppleScript 입력값 안전 처리
        safe_title = format_applescript_value(title)
        safe_location = format_applescript_value(location) if location else "missing"
        safe_notes = format_applescript_value(notes) if notes else "missing"
        safe_calendar_name = format_applescript_value(calendar_name) if calendar_name else "missing"
        
        # 이벤트 속성 구성
        properties = [
            f"summary:{safe_title}",
            f"start date:(date \"{start_date}\")",
            f"end date:(date \"{end_date}\")"
        ]
        if location:
            properties.append(f"location:{safe_location}")
        if notes:
            properties.append(f"description:{safe_notes}")
        properties_str = ", ".join(properties)

        script = f"""
        tell application "Calendar"
            try
                -- 캘린더 목록 가져오기
                set calendarList to every calendar
                set targetCalendar to missing value
                set defaultCalendar to missing value
                
                -- calendar_name으로 캘린더 찾기
                if "{safe_calendar_name}" is not "missing" then
                    repeat with cal in calendarList
                        if name of cal is "{calendar_name}" then
                            set targetCalendar to cal
                            exit repeat
                        end if
                    end repeat
                end if
                
                -- 캘린더 없으면 기본 캘린더 사용
                if targetCalendar is missing value then
                    set defaultCalendar to first calendar whose writable is true
                    set targetCalendar to defaultCalendar
                end if
                
                -- 이벤트 생성
                tell targetCalendar
                    make new event at end with properties {{{properties_str}}}
                    return "SUCCESS:Event created successfully in calendar " & name of targetCalendar
                end tell
            on error errMsg
                return "ERROR:" & errMsg
            end try
        end tell
        """

        try:
            result = await run_applescript_async(script)
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