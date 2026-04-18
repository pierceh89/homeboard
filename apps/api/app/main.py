from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
import asyncio
import json
import traceback
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Request, Response
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.air import AirConditionResponse
from app.api import BusArrivalStop
from app.cache_layer import (
    get_air_condition_cached,
    get_bus_arrivals_cached,
    get_mid_forecast_cached,
    get_weather_cached,
)
from app.discord import send_discord
from app.mid_forecast import MidForecastResponse
from app.settings import get_settings
from app.weather import WeatherForecastSlot, WeatherResponse
from app.naver_calendar import get_naver_today_events

APP_DIR = Path(__file__).resolve().parent
SERVICE_DIR = APP_DIR.parent
STATIC_DIR = SERVICE_DIR / "static"
TEMPLATES_DIR = STATIC_DIR / "templates"
KINDLE_IMAGE_RENDER_RETRY_COUNT = 3
KINDLE_IMAGE_RENDER_RETRY_DELAY_SECONDS = 1.0

app = FastAPI()

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
KST = ZoneInfo("Asia/Seoul")
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


def _slot_dt(slot) -> datetime | None:
    try:
        return datetime.strptime(f"{slot.fcst_date}{slot.fcst_time}", "%Y%m%d%H%M")
    except ValueError:
        return None


def _hour_label(dt_value: datetime) -> str:
    hour = dt_value.hour
    ampm = "AM" if hour < 12 else "PM"
    view_hour = hour % 12 or 12
    return f"{ampm} {view_hour}시"


def _convert_png_to_8bit_grayscale(image_bytes: bytes) -> bytes:
    try:
        from PIL import Image
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="Pillow is not installed") from exc

    with Image.open(BytesIO(image_bytes)) as image:
        output = BytesIO()
        # Kindle endpoint returns an 8-bit grayscale PNG to reduce output depth.
        image.convert("L").save(output, format="PNG")
        return output.getvalue()


def _build_hourly_series(slots: list[WeatherForecastSlot], max_items: int = 12) -> list[dict]:
    picked = slots[:max_items]
    result = []
    for slot in picked:
        dt_value = _slot_dt(slot)
        result.append(
            {
                "label": _hour_label(dt_value) if dt_value else slot.fcst_time,
                "temp": None if slot.temp_c is None else float(slot.temp_c),
                "rain": None if slot.rain_prob_pct is None else float(slot.rain_prob_pct),
                "wind": None if slot.wind_speed_ms is None else float(slot.wind_speed_ms),
            }
        )
    return result


def _format_mid_sky(text: str | None) -> str | None:
    if text is None:
        return None
    compact = text.replace(" ", "")
    if "비" in compact:
        return "비"
    if "눈" in compact:
        return "눈"
    if "흐" in compact:
        return "흐림"
    if "구름" in compact:
        return "구름많음"
    if "맑" in compact:
        return "맑음"
    return text


def _build_weekly_outlook(now: datetime, weather: WeatherResponse, mid: MidForecastResponse | None) -> list[dict]:
    base_date = now.date()
    by_date: dict[str, dict] = {}

    for slot in weather.forecasts:
        dt_value = _slot_dt(slot)
        if dt_value is None:
            continue
        date_key = dt_value.strftime("%Y-%m-%d")
        day = by_date.setdefault(
            date_key,
            {
                "min_temp": None,
                "max_temp": None,
                "sky_text": None,
                "rainy": False,
            },
        )

        if slot.temp_c is not None:
            temp_int = int(round(slot.temp_c))
            day["min_temp"] = temp_int if day["min_temp"] is None else min(day["min_temp"], temp_int)
            day["max_temp"] = temp_int if day["max_temp"] is None else max(day["max_temp"], temp_int)

        if slot.precip_type_text and slot.precip_type_text != "없음":
            day["rainy"] = True
            day["sky_text"] = slot.precip_type_text
        elif day["sky_text"] is None and slot.sky_text:
            day["sky_text"] = slot.sky_text

    weekly: list[dict] = []
    mid_by_offset = {d.day_offset: d for d in (mid.daily if mid is not None else [])}

    for offset in range(0, 8):
        target_date = base_date + timedelta(days=offset)
        date_key = target_date.strftime("%Y-%m-%d")
        weekday = WEEKDAY_KO[target_date.weekday()]

        short = by_date.get(date_key)
        min_temp = short.get("min_temp") if short else None
        max_temp = short.get("max_temp") if short else None
        sky_text = short.get("sky_text") if short else None

        if offset >= 4:
            mid_day = mid_by_offset.get(offset)
            if mid_day is not None:
                if min_temp is None:
                    min_temp = mid_day.min_temp
                if max_temp is None:
                    max_temp = mid_day.max_temp
                if sky_text is None:
                    sky_text = _format_mid_sky(mid_day.afternoon_sky or mid_day.sky or mid_day.morning_sky)

        if sky_text is None:
            sky_text = "-"

        weekly.append(
            {
                "date": date_key,
                "weekday": weekday,
                "sky_text": sky_text,
                "max_temp": max_temp,
                "min_temp": min_temp,
            }
        )

    return weekly


def _require_access_key(access_key: str | None):
    if settings.access_key != "" and access_key != settings.access_key:
        raise HTTPException(status_code=404, detail="Not Found")


def _build_page_error_log(page_name: str, request: Request, exc: Exception) -> str:
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S %Z")
    client_host = request.client.host if request.client else "-"
    user_agent = request.headers.get("user-agent", "-")
    trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    prefix = (
        "[Homeboard Render Error]\n"
        f"time: {now}\n"
        f"page: {page_name}\n"
        f"path: {request.url.path}\n"
        f"client: {client_host}\n"
        f"user-agent: {user_agent}\n"
        f"error: {type(exc).__name__}: {exc}\n"
        "traceback:\n```"
    )
    suffix = "```"
    max_trace_length = 2000 - len(prefix) - len(suffix)
    if max_trace_length < 0:
        return prefix[:1997] + "..."
    if len(trace) > max_trace_length:
        trace = "..." + trace[-max(0, max_trace_length - 3) :]
    return f"{prefix}{trace}{suffix}"


async def _notify_page_render_error(page_name: str, request: Request, exc: Exception) -> None:
    try:
        await send_discord(_build_page_error_log(page_name, request, exc), username="Homeboard")
    except Exception:
        pass


@app.get("/")
def read_root():
    return {}


@app.get("/home")
async def get_home(request: Request, accessKey: str | None = None):
    _require_access_key(accessKey)

    try:
        now = datetime.now(KST)
        weather = await get_weather_cached(now)
        bus_stops = await get_bus_arrivals_cached(now)
        air = await get_air_condition_cached(now)
        mid = await get_mid_forecast_cached(now)
        hourly_series = _build_hourly_series(weather.forecasts, max_items=24)
        weekly_outlook = _build_weekly_outlook(now, weather, mid)
        now_label = f"({WEEKDAY_KO[now.weekday()]}요일) {now.strftime('%p').replace('AM', 'AM').replace('PM', 'PM')} {now.strftime('%I:%M').lstrip('0')}"
        return templates.TemplateResponse(
            request=request,
            name="home.html",
            context={
                "bus_stops": bus_stops,
                "weather": weather,
                "air": air,
                "hourly_series": json.dumps(hourly_series, ensure_ascii=False),
                "weekly_outlook": weekly_outlook,
                "now_label": now_label,
            },
        )
    except Exception as exc:
        await _notify_page_render_error("/home", request, exc)
        raise


@app.get("/kindle")
async def get_kindle_home(request: Request, accessKey: str | None = None):
    _require_access_key(accessKey)

    try:
        now = datetime.now(KST)
        weather = await get_weather_cached(now)
        air = await get_air_condition_cached(now)
        mid = await get_mid_forecast_cached(now)
        hourly_series = _build_hourly_series(weather.forecasts, max_items=24)
        weekly_outlook = _build_weekly_outlook(now, weather, mid)
        date_label = f"{now.strftime('%m.%d')}"
        now_label = (
            f"({WEEKDAY_KO[now.weekday()]}요일) "
            f"{now.strftime('%p').replace('AM', 'AM').replace('PM', 'PM')} "
            f"{now.strftime('%I:%M').lstrip('0')}"
        )
        return templates.TemplateResponse(
            request=request,
            name="kindle_home.html",
            context={
                "weather": weather,
                "air": air,
                "hourly_series": json.dumps(hourly_series, ensure_ascii=False),
                "weekly_outlook": weekly_outlook,
                "now_label": now_label,
                "date_label": date_label,
            },
        )
    except Exception as exc:
        await _notify_page_render_error("/kindle", request, exc)
        raise


@app.get("/kindle-image")
async def get_kindle_home_image(request: Request, accessKey: str | None = None):
    _require_access_key(accessKey)

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="playwright is not installed") from exc

    target_url = str(request.url_for("get_kindle_home"))
    target_url = f"{target_url}?accessKey={accessKey}"

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(
                    viewport={"width": 600, "height": 800},
                    device_scale_factor=1,
                )
                last_status_code = None
                for attempt in range(1, KINDLE_IMAGE_RENDER_RETRY_COUNT + 1):
                    page_response = await page.goto(target_url, wait_until="networkidle")
                    last_status_code = page_response.status if page_response is not None else None
                    if last_status_code == 200:
                        break
                    if attempt < KINDLE_IMAGE_RENDER_RETRY_COUNT:
                        await asyncio.sleep(KINDLE_IMAGE_RENDER_RETRY_DELAY_SECONDS)
                else:
                    raise RuntimeError(f"target page returned status code {last_status_code}")

                image_bytes = await page.screenshot(type="png", full_page=False)
                image_bytes = _convert_png_to_8bit_grayscale(image_bytes)
            finally:
                await browser.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to capture kindle image: {exc}") from exc

    return Response(content=image_bytes, media_type="image/png")


@app.get("/api/calendar/naver/today", response_model=TodayScheduleResponse)
async def get_naver_calendar_today(accessKey: str | None = None):
    _require_access_key(accessKey)

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


@app.get("/api/weather/short-term", response_model=WeatherResponse)
async def get_short_term_forecast(accessKey: str | None = None, force_reload: bool = Query(default=False)):
    _require_access_key(accessKey)

    now = datetime.now(KST)
    weather = await get_weather_cached(now, force_reload=force_reload)

    return weather


@app.get("/api/weather/mid-term", response_model=MidForecastResponse)
async def get_mid_term_forecast(accessKey: str | None = None, force_reload: bool = Query(default=False)):
    _require_access_key(accessKey)
    
    now = datetime.now(KST)
    mid_forecast = await get_mid_forecast_cached(now, force_reload=force_reload)

    return mid_forecast


@app.get("/api/weather/air", response_model=AirConditionResponse)
async def get_air(accessKey: str | None = None, force_reload: bool = Query(default=False)):
    _require_access_key(accessKey)

    now = datetime.now(KST)
    air_condition = await get_air_condition_cached(now, force_reload=force_reload)

    return air_condition


@app.get("/api/bus-arrivals", response_model=list[BusArrivalStop])
async def get_bus_arrivals_api(
    accessKey: str | None = None,
    force_reload: bool = Query(default=False),
):
    _require_access_key(accessKey)

    now = datetime.now(KST)
    return await get_bus_arrivals_cached(now, force_reload=force_reload)
