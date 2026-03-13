from datetime import datetime, timedelta
from threading import Lock
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api import get_bus_arrivals
from settings import get_settings
from weather import WeatherForecastSlot, WeatherResponse, get_weather

import json

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="static/templates")


WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
KST = ZoneInfo("Asia/Seoul")
WEATHER_CACHE_TTL = timedelta(minutes=30)
BUS_CACHE_TTL = timedelta(minutes=1)
settings = get_settings()

_weather_cache_lock = Lock()
_weather_cache_value: WeatherResponse | None = None
_weather_cache_expires_at: datetime | None = None

_bus_cache_lock = Lock()
_bus_cache_value: list[dict] | None = None
_bus_cache_expires_at: datetime | None = None


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


def _build_daily_ui(slots: list, max_days: int = 8) -> list[dict]:
    grouped: dict[str, dict] = {}
    for slot in slots:
        key = slot.fcst_date
        day = grouped.setdefault(
            key,
            {
                "date": key,
                "min_temp": None,
                "max_temp": None,
                "sky_text": None,
            },
        )
        for value in [slot.temp_c, slot.min_temp_c]:
            if value is None:
                continue
            day["min_temp"] = value if day["min_temp"] is None else min(day["min_temp"], value)
        for value in [slot.temp_c, slot.max_temp_c]:
            if value is None:
                continue
            day["max_temp"] = value if day["max_temp"] is None else max(day["max_temp"], value)
        if day["sky_text"] is None and slot.sky_text:
            day["sky_text"] = slot.sky_text

    result = []
    for day in sorted(grouped.keys())[:max_days]:
        dt_value = datetime.strptime(day, "%Y%m%d")
        row = grouped[day]
        result.append(
            {
                "weekday": WEEKDAY_KO[dt_value.weekday()],
                "sky_text": row["sky_text"] or "맑음",
                "max_temp": None if row["max_temp"] is None else int(round(float(row["max_temp"]))),
                "min_temp": None if row["min_temp"] is None else int(round(float(row["min_temp"]))),
            }
        )
    return result



async def _get_weather_cached(now: datetime):
    global _weather_cache_value, _weather_cache_expires_at
    with _weather_cache_lock:
        if _weather_cache_value is not None and _weather_cache_expires_at is not None and now < _weather_cache_expires_at:
            return _weather_cache_value

    weather = await get_weather(now, settings.weather)

    with _weather_cache_lock:
        _weather_cache_value = weather
        _weather_cache_expires_at = now + WEATHER_CACHE_TTL

    return weather


async def _get_bus_arrivals_cached(now: datetime):
    global _bus_cache_value, _bus_cache_expires_at
    with _bus_cache_lock:
        if _bus_cache_value is not None and _bus_cache_expires_at is not None and now < _bus_cache_expires_at:
            return _bus_cache_value

    bus_arrivals = await get_bus_arrivals(request=settings.bus_arrival)

    with _bus_cache_lock:
        _bus_cache_value = bus_arrivals
        _bus_cache_expires_at = now + BUS_CACHE_TTL

    return bus_arrivals


@app.get("/")
def read_root():
    return {}


@app.get("/home")
async def get_home(request: Request, accessKey: str | None = None):
    if settings.access_key != "" and accessKey != settings.access_key:
        raise HTTPException(status_code=404, detail="Not Found")

    now = datetime.now(KST)
    weather = await _get_weather_cached(now)
    bus_stops = await _get_bus_arrivals_cached(now)
    hourly_series = _build_hourly_series(weather.forecasts, max_items=24)
    now_label = f"({WEEKDAY_KO[now.weekday()]}요일) {now.strftime('%p').replace('AM', 'AM').replace('PM', 'PM')} {now.strftime('%I:%M').lstrip('0')}"
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "bus_stops": bus_stops,
            "weather": weather,
            "hourly_series": json.dumps(hourly_series, ensure_ascii=False),
            "now_label": now_label,
        },
    )
