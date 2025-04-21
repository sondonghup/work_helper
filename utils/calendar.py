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
        
        script = f"""
            tell application "Calendar"
                try
                    tell application "Calendar"
                        tell (first calendar whose name is "Calendar")
                            make new event at end with properties {{summary: "{title}", start date: (date "{start_date}"),\
                                end date: (date "{end_date}")}}
                            return "SUCCESS:Event created successfully"
                        end tell
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