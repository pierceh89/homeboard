from datetime import datetime, timedelta
import logging

from app.core.constants import KST, WEEKDAY_KO
from app.integrations.mid_forecast import MidForecastResponse
from app.integrations.naver_calendar import get_naver_today_events
from app.core.settings import get_settings
from app.integrations.weather import WeatherForecastSlot, WeatherResponse


logger = logging.getLogger("uvicorn")
settings = get_settings()


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


def build_hourly_series(slots: list[WeatherForecastSlot], max_items: int = 12) -> list[dict]:
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


def build_weekly_outlook(now: datetime, weather: WeatherResponse, mid: MidForecastResponse | None) -> list[dict]:
    base_date = now.date()
    by_date: dict[str, dict] = {}

    for slot in weather.forecasts:
        dt_value = _slot_dt(slot)
        if dt_value is None:
            continue
        date_key = dt_value.strftime("%m-%d")
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
        date_key = target_date.strftime("%m-%d")
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


def _format_kindle_calendar_time(dt_value: datetime) -> str:
    local_dt = dt_value.astimezone(KST)
    meridiem = "오전" if local_dt.hour < 12 else "오후"
    hour = local_dt.hour % 12 or 12
    return f"{meridiem} {hour}:{local_dt.minute:02d}"


def build_kindle_calendar_context(
    now: datetime,
    *,
    events: list | None,
    error: bool = False,
) -> dict:
    if error:
        return {
            "calendar_date_label": "일정 오류",
            "calendar_schedules": [],
            "calendar_error": True,
        }

    local_now = now.astimezone(KST)
    date_label = f"{local_now.month}. {local_now.day}. ({WEEKDAY_KO[local_now.weekday()]})"
    schedules = []
    for event in events or []:
        summary = (event.summary or "").strip() or "제목 없는 일정"
        if event.is_all_day:
            time_label = "하루 종일"
        else:
            time_label = (
                f"{_format_kindle_calendar_time(event.start)} - "
                f"{_format_kindle_calendar_time(event.end)}"
            )
        schedules.append(
            {
                "summary": summary,
                "time_label": time_label,
            }
        )

    return {
        "calendar_date_label": date_label,
        "calendar_schedules": schedules,
        "calendar_error": False,
    }


def get_kindle_calendar_context(now: datetime) -> dict:
    if not settings.naver_caldav_username or not settings.naver_caldav_password:
        return build_kindle_calendar_context(now, events=None, error=True)

    try:
        events = get_naver_today_events(
            caldav_url=settings.naver_caldav_url,
            username=settings.naver_caldav_username,
            password=settings.naver_caldav_password,
            calendar_name=settings.naver_caldav_calendar_name or None,
            timezone=KST,
            now=now,
        )
    except Exception:
        logger.warning("Failed to fetch NAVER Calendar events for /kindle", exc_info=True)
        return build_kindle_calendar_context(now, events=None, error=True)

    return build_kindle_calendar_context(now, events=events)
