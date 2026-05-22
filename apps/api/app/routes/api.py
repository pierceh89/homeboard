from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.air import AirConditionResponse
from app.api import BusArrivalStop
from app.auth import require_access_key
from app.cache_layer import (
    get_air_condition_cached,
    get_bus_arrivals_cached,
    get_mid_forecast_cached,
    get_weather_cached,
)
from app.constants import KST
from app.mid_forecast import MidForecastResponse
from app.naver_calendar import get_naver_today_events
from app.settings import get_settings
from app.weather import WeatherResponse


router = APIRouter()
settings = get_settings()


class TodayScheduleItem(BaseModel):
    uid: str | None
    summary: str
    start: str
    end: str
    is_all_day: bool


class TodayScheduleResponse(BaseModel):
    date: str
    timezone: str
    total: int
    schedules: list[TodayScheduleItem]


@router.get("/api/calendar/naver/today", response_model=TodayScheduleResponse)
async def get_naver_calendar_today(accessKey: str | None = None):
    require_access_key(accessKey)

    if not settings.naver_caldav_username or not settings.naver_caldav_password:
        raise HTTPException(status_code=500, detail="NAVER CalDAV credentials are not configured")

    try:
        events = get_naver_today_events(
            caldav_url=settings.naver_caldav_url,
            username=settings.naver_caldav_username,
            password=settings.naver_caldav_password,
            calendar_name=settings.naver_caldav_calendar_name or None,
            timezone=KST,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"failed to fetch NAVER Calendar events: {exc}") from exc

    now = datetime.now(KST)
    schedules = [
        TodayScheduleItem(
            uid=event.uid,
            summary=event.summary,
            start=event.start.isoformat(),
            end=event.end.isoformat(),
            is_all_day=event.is_all_day,
        )
        for event in events
    ]

    return TodayScheduleResponse(
        date=now.date().isoformat(),
        timezone=str(KST),
        total=len(schedules),
        schedules=schedules,
    )


@router.get("/api/weather/short-term", response_model=WeatherResponse)
async def get_short_term_forecast(accessKey: str | None = None, force_reload: bool = Query(default=False)):
    require_access_key(accessKey)

    now = datetime.now(KST)
    weather = await get_weather_cached(now, force_reload=force_reload)

    return weather


@router.get("/api/weather/mid-term", response_model=MidForecastResponse)
async def get_mid_term_forecast(accessKey: str | None = None, force_reload: bool = Query(default=False)):
    require_access_key(accessKey)

    now = datetime.now(KST)
    mid_forecast = await get_mid_forecast_cached(now, force_reload=force_reload)

    return mid_forecast


@router.get("/api/weather/air", response_model=AirConditionResponse)
async def get_air(accessKey: str | None = None, force_reload: bool = Query(default=False)):
    require_access_key(accessKey)

    now = datetime.now(KST)
    air_condition = await get_air_condition_cached(now, force_reload=force_reload)

    return air_condition


@router.get("/api/bus-arrivals", response_model=list[BusArrivalStop])
async def get_bus_arrivals_api(
    accessKey: str | None = None,
    force_reload: bool = Query(default=False),
):
    require_access_key(accessKey)

    now = datetime.now(KST)
    return await get_bus_arrivals_cached(now, force_reload=force_reload)
