from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.api_shared import clean_text, fetch_json, fetched_at_label, to_float, to_int
from app.settings import WeatherRequest, get_settings

FORECAST_TIMES = [2, 5, 8, 11, 14, 17, 20, 23]
WEATHER_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
WEATHER_NUM_OF_ROWS = 300

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


def _parse_amount(raw: str | None, empty_values: set[str], unit: str) -> float | None:
    cleaned = clean_text(raw)
    if cleaned is None:
        return None
    if cleaned in empty_values:
        return 0.0
    normalized = cleaned.replace(unit, "").replace(" ", "")
    if "~" in normalized:
        normalized = normalized.split("~", 1)[0]
    if normalized.endswith("이상"):
        normalized = normalized.removesuffix("이상")
    return to_float(normalized)


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

    @classmethod
    def from_categories(cls, fcst_date: str, fcst_time: str, categories: dict[str, str]) -> "WeatherForecastSlot":
        sky_code = to_int(categories.get("SKY"))
        precip_type_code = to_int(categories.get("PTY"))
        precip_mm = _parse_amount(categories.get("PCP"), {"강수없음", "없음"}, "mm")
        snow_cm = _parse_amount(categories.get("SNO"), {"적설없음", "없음"}, "cm")
        wind_speed = to_float(categories.get("WSD"))
        sky_text = PTY_MAP.get(precip_type_code) if precip_mm != 0 else SKY_MAP.get(sky_code)
        return cls(
            fcst_date=fcst_date,
            fcst_time=fcst_time,
            categories=categories,
            temp_c=to_float(categories.get("TMP")),
            min_temp_c=to_float(categories.get("TMN")),
            max_temp_c=to_float(categories.get("TMX")),
            humidity_pct=to_int(categories.get("REH")),
            rain_prob_pct=to_int(categories.get("POP")),
            sky_code=sky_code,
            sky_text=sky_text,
            precip_type_code=precip_type_code,
            precip_type_text=PTY_MAP.get(precip_type_code),
            precip_mm=precip_mm,
            precip_text=_precip_text(precip_mm),
            snow_cm=snow_cm,
            snow_text=_snow_text(snow_cm),
            wind_speed_ms=wind_speed,
            wind_text=_wind_text(wind_speed),
            wind_dir_deg=to_float(categories.get("VEC")),
            wind_uuu_ms=to_float(categories.get("UUU")),
            wind_vvv_ms=to_float(categories.get("VVV")),
            wave_m=to_float(categories.get("WAV")),
        )


@dataclass
class WeatherResponse:
    region: str
    base_date: str
    base_time: str
    fetched_at: str
    current: WeatherForecastSlot | None
    forecasts: list[WeatherForecastSlot]

    @classmethod
    def empty(cls, region: str, base_date: str, base_time: str, now: datetime) -> "WeatherResponse":
        return cls(
            region=region,
            base_date=base_date,
            base_time=base_time,
            fetched_at=fetched_at_label(now),
            current=None,
            forecasts=[],
        )


def _group_categories(items: list[dict]) -> dict[tuple[str, str], dict[str, str]]:
    grouped: dict[tuple[str, str], dict[str, str]] = {}
    for row in items:
        fcst_date = clean_text(row.get("fcstDate"))
        fcst_time = clean_text(row.get("fcstTime"))
        category = clean_text(row.get("category"))
        if fcst_date is None or fcst_time is None or category is None:
            continue
        grouped.setdefault((fcst_date, fcst_time), {})[category] = str(row.get("fcstValue", ""))
    return grouped


def _normalize_forecasts(items: list[dict]) -> list[WeatherForecastSlot]:
    grouped = _group_categories(items)
    return [
        WeatherForecastSlot.from_categories(fcst_date, fcst_time, grouped[(fcst_date, fcst_time)])
        for fcst_date, fcst_time in sorted(grouped.keys())
    ]


async def _fetch_weather_page(
    base_date: str,
    base_time: str,
    request: WeatherRequest,
    page_no: int,
) -> tuple[list[dict] | None, int | None]:
    settings = get_settings()
    payload = await fetch_json(
        url=WEATHER_URL,
        params={
            "serviceKey": settings.public_api_key,
            "pageNo": page_no,
            "numOfRows": WEATHER_NUM_OF_ROWS,
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": request.nx,
            "ny": request.ny,
        },
    )
    if payload is None:
        return None, None

    body = payload.get("response", {}).get("body", {})
    raw_total_count = body.get("totalCount")
    total_count = int(raw_total_count)
    items = body.get("items", {}).get("item", [])
    return (items if isinstance(items, list) else []), total_count


async def get_weather(now: datetime, request: WeatherRequest) -> WeatherResponse:
    base_date, base_time = _select_base(now)
    total_items: list[dict] = []
    total_count: int | None = None
    page_no = 1

    while True:
        items, total_count = await _fetch_weather_page(base_date, base_time, request, page_no)
        if items is None:
            break

        total_items.extend(items)

        if len(total_items) >= total_count:
            break

        page_no = page_no + 1


    forecasts = _normalize_forecasts(total_items)
    return WeatherResponse(
        region=request.region,
        base_date=base_date,
        base_time=base_time,
        fetched_at=fetched_at_label(now),
        current=forecasts[0] if forecasts else None,
        forecasts=forecasts,
    )
