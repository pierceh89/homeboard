from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx

from settings import WeatherRequest, get_settings

FORECAST_TIMES = [2, 5, 8, 11, 14, 17, 20, 23]

SKY_MAP = {
    1: "맑음",
    3: "구름많음",
    4: "흐림",
}

PTY_MAP = {
    0: "없음",
    1: "비",
    2: "비/눈",
    3: "눈",
    4: "소나기",
}


@dataclass
class WeatherForecastSlot:
    fcst_date: str
    fcst_time: str
    categories: dict[str, str] = field(default_factory=dict)
    temp_c: float | None = None
    min_temp_c: float | None = None
    max_temp_c: float | None = None
    humidity_pct: int | None = None
    rain_prob_pct: int | None = None
    sky_code: int | None = None
    sky_text: str | None = None
    precip_type_code: int | None = None
    precip_type_text: str | None = None
    precip_mm: float | None = None
    precip_text: str | None = None
    snow_cm: float | None = None
    snow_text: str | None = None
    wind_speed_ms: float | None = None
    wind_text: str | None = None
    wind_dir_deg: float | None = None
    wind_uuu_ms: float | None = None
    wind_vvv_ms: float | None = None
    wave_m: float | None = None


@dataclass
class WeatherResponse:
    region: str
    base_date: str
    base_time: str
    fetched_at: str
    current: WeatherForecastSlot | None
    forecasts: list[WeatherForecastSlot]


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_precip_mm(raw: str | None) -> float | None:
    if not raw:
        return None
    if raw in {"강수없음", "없음"}:
        return 0.0
    cleaned = raw.replace("mm", "").replace(" ", "")
    if "~" in cleaned:
        start = cleaned.split("~", 1)[0]
        return _to_float(start)
    if cleaned.endswith("이상"):
        cleaned = cleaned.removesuffix("이상")
    return _to_float(cleaned)


def _parse_snow_cm(raw: str | None) -> float | None:
    if not raw:
        return None
    if raw in {"적설없음", "없음"}:
        return 0.0
    cleaned = raw.replace("cm", "").replace(" ", "")
    if "~" in cleaned:
        start = cleaned.split("~", 1)[0]
        return _to_float(start)
    if cleaned.endswith("이상"):
        cleaned = cleaned.removesuffix("이상")
    return _to_float(cleaned)


def _precip_text(mm: float | None) -> str | None:
    if mm is None:
        return None
    if mm == 0:
        return "강수 없음"
    if mm < 3:
        return "약한 비"
    if mm < 15:
        return "보통 비"
    return "강한 비"


def _snow_text(cm: float | None) -> str | None:
    if cm is None:
        return None
    if cm == 0:
        return "적설 없음"
    if cm < 1:
        return "보통 눈"
    return "많은 눈"


def _wind_text(speed: float | None) -> str | None:
    if speed is None:
        return None
    if speed < 4:
        return "약한 바람"
    if speed < 9:
        return "약간 강한 바람"
    return "강한 바람"


def _select_base(now: datetime) -> tuple[str, str]:
    for hour in reversed(FORECAST_TIMES):
        if now.hour >= hour:
            return now.strftime("%Y%m%d"), f"{hour:02}00"

    previous_day = now - timedelta(days=1)
    return previous_day.strftime("%Y%m%d"), "2300"


def _build_slot(fcst_date: str, fcst_time: str, categories: dict[str, str]) -> WeatherForecastSlot:
    sky_code = _to_int(categories.get("SKY"))
    pty_code = _to_int(categories.get("PTY"))
    precip_mm = _parse_precip_mm(categories.get("PCP"))
    snow_cm = _parse_snow_cm(categories.get("SNO"))
    wind_speed = _to_float(categories.get("WSD"))
    if precip_mm != 0:
        sky_text = PTY_MAP.get(pty_code)
    else:
        sky_text = SKY_MAP.get(sky_code)

    return WeatherForecastSlot(
        fcst_date=fcst_date,
        fcst_time=fcst_time,
        categories=categories,
        temp_c=_to_float(categories.get("TMP")),
        min_temp_c=_to_float(categories.get("TMN")),
        max_temp_c=_to_float(categories.get("TMX")),
        humidity_pct=_to_int(categories.get("REH")),
        rain_prob_pct=_to_int(categories.get("POP")),
        sky_code=sky_code,
        sky_text=sky_text,
        precip_type_code=pty_code,
        precip_type_text=PTY_MAP.get(pty_code),
        precip_mm=precip_mm,
        precip_text=_precip_text(precip_mm),
        snow_cm=snow_cm,
        snow_text=_snow_text(snow_cm),
        wind_speed_ms=wind_speed,
        wind_text=_wind_text(wind_speed),
        wind_dir_deg=_to_float(categories.get("VEC")),
        wind_uuu_ms=_to_float(categories.get("UUU")),
        wind_vvv_ms=_to_float(categories.get("VVV")),
        wave_m=_to_float(categories.get("WAV")),
    )


def _normalize_forecasts(items: list[dict]) -> list[WeatherForecastSlot]:
    grouped: dict[tuple[str, str], dict[str, str]] = {}

    for row in items:
        fcst_date = str(row.get("fcstDate", ""))
        fcst_time = str(row.get("fcstTime", ""))
        category = str(row.get("category", ""))
        fcst_value = str(row.get("fcstValue", ""))

        if not fcst_date or not fcst_time or not category:
            continue

        key = (fcst_date, fcst_time)
        grouped.setdefault(key, {})[category] = fcst_value

    slots: list[WeatherForecastSlot] = []
    for fcst_date, fcst_time in sorted(grouped.keys()):
        slots.append(_build_slot(fcst_date, fcst_time, grouped[(fcst_date, fcst_time)]))

    return slots


def get_weather(
    now: datetime,
    request: WeatherRequest
) -> WeatherResponse:
    settings = get_settings()
    base_date, base_time = _select_base(now)

    page_no = 1
    total_items = []
    url = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

    while True:
        try:
            query_params = {
                "serviceKey": settings.public_api_key,
                "pageNo": page_no,
                "numOfRows": 300,
                "dataType": "JSON",
                "base_date": base_date,
                "base_time": base_time,
                "nx": request.nx,
                "ny": request.ny,
            }
            response = httpx.get(url=url, params=query_params, timeout=10.0)
            res_json = response.json()
            items = res_json.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            total_items.extend(items)
            total_count = res_json.get("response", {}).get("body", {}).get("totalCount", 0)
            page_no = page_no + 1
            if len(total_items) >= total_count:
                break
        except httpx.HTTPError:
            return WeatherResponse(
                region=request.region,
                base_date=base_date,
                base_time=base_time,
                fetched_at=now.strftime("%Y-%m-%d %H:%M"),
                current=None,
                forecasts=[],
            )
        if response.status_code != 200:
            return WeatherResponse(
                region=request.region,
                base_date=base_date,
                base_time=base_time,
                fetched_at=now.strftime("%Y-%m-%d %H:%M"),
                current=None,
                forecasts=[],
            )

    forecasts = _normalize_forecasts(total_items)
    current = forecasts[0] if forecasts else None

    return WeatherResponse(
        region=request.region,
        base_date=base_date,
        base_time=base_time,
        fetched_at=now.strftime("%Y-%m-%d %H:%M"),
        current=current,
        forecasts=forecasts,
    )
