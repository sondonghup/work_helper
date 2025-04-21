from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from utils.calendar import CalendarModule

mcp = FastMCP(
    "APPLE MCP",
    dependencies=[
        "pydantic>=2.0.0",
        "httpx>=0.24.0"
    ]
)

caledar_module = CalendarModule()

class CalendarEvent(BaseModel):
    title: str
    start_date: str
    end_date: str
    location: Optional[str] = None
    notes: Optional[str] = None
    is_all_day: bool = False
    calendar_name: Optional[str] = None

@mcp.tool()
async def create_event(event: CalendarEvent) -> str:
    """캘린더 생성"""
    return await caledar_module.create_event(
        title=event.title,
        start_date=event.start_date,
        end_date=event.end_date,
        location=event.location,
        notes=event.notes,
        is_all_day=event.is_all_day,
        calendar_name=event.calendar_name
    )