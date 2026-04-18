from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.api_shared import clean_text, fetch_json, fetched_at_label, to_int
from app.settings import get_settings

MID_FORECAST_BASE_URL = "https://apis.data.go.kr/1360000/MidFcstInfoService"


def _select_tmfc(now: datetime) -> str:
    if now.hour >= 18:
        base = now.replace(hour=18, minute=0, second=0, microsecond=0)
    elif now.hour >= 6:
        base = now.replace(hour=6, minute=0, second=0, microsecond=0)
    else:
        previous_day = now - timedelta(days=1)
        base = previous_day.replace(hour=18, minute=0, second=0, microsecond=0)
    return base.strftime("%Y%m%d%H%M")


def _extract_item(payload: dict | None) -> tuple[str | None, str | None, dict | None]:
    if payload is None:
        return None, None, None

    response = payload.get("response", {})
    header = response.get("header", {})
    body = response.get("body", {})
    raw_items = body.get("items", {}).get("item", [])
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    if not isinstance(raw_items, list) or not raw_items:
        return clean_text(header.get("resultCode")), clean_text(header.get("resultMsg")), None

    item = raw_items[0]
    if not isinstance(item, dict):
        return clean_text(header.get("resultCode")), clean_text(header.get("resultMsg")), None

    return clean_text(header.get("resultCode")), clean_text(header.get("resultMsg")), item


def _forecast_date(tmfc: str, day_offset: int) -> str | None:
    try:
        forecast_dt = datetime.strptime(tmfc[:8], "%Y%m%d") + timedelta(days=day_offset)
    except ValueError:
        return None
    return forecast_dt.strftime("%Y-%m-%d")


@dataclass
class MidForecastOverview:
    stn_id: str
    wf_sv: str | None

    @classmethod
    def from_api(cls, stn_id: str, item: dict) -> "MidForecastOverview":
        return cls(
            stn_id=stn_id,
            wf_sv=clean_text(item.get("wfSv")),
        )


@dataclass
class MidLandForecast:
    reg_id: str
    forecast: dict[str, str | int | None]

    @classmethod
    def from_api(cls, reg_id: str, item: dict) -> "MidLandForecast":
        forecast: dict[str, str | int | None] = {}
        for day in range(4, 8):
            forecast[f"rnSt{day}Am"] = to_int(item.get(f"rnSt{day}Am"))
            forecast[f"rnSt{day}Pm"] = to_int(item.get(f"rnSt{day}Pm"))
            forecast[f"wf{day}Am"] = clean_text(item.get(f"wf{day}Am"))
            forecast[f"wf{day}Pm"] = clean_text(item.get(f"wf{day}Pm"))
        for day in range(8, 11):
            forecast[f"rnSt{day}"] = to_int(item.get(f"rnSt{day}"))
            forecast[f"wf{day}"] = clean_text(item.get(f"wf{day}"))
        return cls(reg_id=reg_id, forecast=forecast)


@dataclass
class MidTemperatureForecast:
    reg_id: str
    forecast: dict[str, int | None]

    @classmethod
    def from_api(cls, reg_id: str, item: dict) -> "MidTemperatureForecast":
        forecast: dict[str, int | None] = {}
        for day in range(4, 11):
            for prefix in ("taMin", "taMinLow", "taMinHigh", "taMax", "taMaxLow", "taMaxHigh"):
                forecast[f"{prefix}{day}"] = to_int(item.get(f"{prefix}{day}"))
        return cls(reg_id=reg_id, forecast=forecast)


@dataclass
class MidForecastDay:
    day_offset: int
    date: str | None
    morning_sky: str | None
    afternoon_sky: str | None
    sky: str | None
    morning_rain_prob: int | None
    afternoon_rain_prob: int | None
    rain_prob: int | None
    min_temp: int | None
    min_temp_low: int | None
    min_temp_high: int | None
    max_temp: int | None
    max_temp_low: int | None
    max_temp_high: int | None


@dataclass
class MidForecastResponse:
    tm_fc: str
    fetched_at: str
    result_code: str | None
    result_msg: str | None
    stn_id: str | None
    land_reg_id: str
    temp_reg_id: str
    overview: MidForecastOverview | None
    land: MidLandForecast | None
    temperature: MidTemperatureForecast | None
    daily: list[MidForecastDay]

    @classmethod
    def empty(
        cls,
        now: datetime,
        tm_fc: str,
        land_reg_id: str,
        temp_reg_id: str,
        stn_id: str | None,
    ) -> "MidForecastResponse":
        return cls(
            tm_fc=tm_fc,
            fetched_at=fetched_at_label(now),
            result_code=None,
            result_msg=None,
            stn_id=stn_id,
            land_reg_id=land_reg_id,
            temp_reg_id=temp_reg_id,
            overview=None,
            land=None,
            temperature=None,
            daily=[],
        )


async def _fetch_mid_forecast(endpoint: str, extra_params: dict[str, str]) -> tuple[str | None, str | None, dict | None]:
    settings = get_settings()
    payload = await fetch_json(
        url=f"{MID_FORECAST_BASE_URL}/{endpoint}",
        params={
            "serviceKey": settings.public_api_key,
            "pageNo": 1,
            "numOfRows": 10,
            "dataType": "JSON",
            **extra_params,
        },
    )
    return _extract_item(payload)


def _build_daily_forecasts(
    tm_fc: str,
    land: MidLandForecast | None,
    temperature: MidTemperatureForecast | None,
) -> list[MidForecastDay]:
    daily: list[MidForecastDay] = []
    land_forecast = land.forecast if land is not None else {}
    temp_forecast = temperature.forecast if temperature is not None else {}

    for day in range(4, 11):
        daily.append(
            MidForecastDay(
                day_offset=day,
                date=_forecast_date(tm_fc, day),
                morning_sky=clean_text(land_forecast.get(f"wf{day}Am")),
                afternoon_sky=clean_text(land_forecast.get(f"wf{day}Pm")),
                sky=clean_text(land_forecast.get(f"wf{day}")),
                morning_rain_prob=to_int(land_forecast.get(f"rnSt{day}Am")),
                afternoon_rain_prob=to_int(land_forecast.get(f"rnSt{day}Pm")),
                rain_prob=to_int(land_forecast.get(f"rnSt{day}")),
                min_temp=to_int(temp_forecast.get(f"taMin{day}")),
                min_temp_low=to_int(temp_forecast.get(f"taMinLow{day}")),
                min_temp_high=to_int(temp_forecast.get(f"taMinHigh{day}")),
                max_temp=to_int(temp_forecast.get(f"taMax{day}")),
                max_temp_low=to_int(temp_forecast.get(f"taMaxLow{day}")),
                max_temp_high=to_int(temp_forecast.get(f"taMaxHigh{day}")),
            )
        )

    return daily


async def get_mid_forecast(
    now: datetime,
    land_reg_id: str,
    temp_reg_id: str,
    stn_id: str | None = None,
    tm_fc: str | None = None,
) -> MidForecastResponse:
    selected_tm_fc = tm_fc or _select_tmfc(now)

    land_result_code, land_result_msg, land_item = await _fetch_mid_forecast(
        endpoint="getMidLandFcst",
        extra_params={
            "regId": land_reg_id,
            "tmFc": selected_tm_fc,
        },
    )
    temp_result_code, temp_result_msg, temp_item = await _fetch_mid_forecast(
        endpoint="getMidTa",
        extra_params={
            "regId": temp_reg_id,
            "tmFc": selected_tm_fc,
        },
    )

    overview_result_code = None
    overview_result_msg = None
    overview_item = None
    if stn_id:
        overview_result_code, overview_result_msg, overview_item = await _fetch_mid_forecast(
            endpoint="getMidFcst",
            extra_params={
                "stnId": stn_id,
                "tmFc": selected_tm_fc,
            },
        )

    if land_item is None and temp_item is None and overview_item is None:
        return MidForecastResponse.empty(
            now=now,
            tm_fc=selected_tm_fc,
            land_reg_id=land_reg_id,
            temp_reg_id=temp_reg_id,
            stn_id=stn_id,
        )

    overview = MidForecastOverview.from_api(stn_id, overview_item) if stn_id and overview_item is not None else None
    land = MidLandForecast.from_api(land_reg_id, land_item) if land_item is not None else None
    temperature = MidTemperatureForecast.from_api(temp_reg_id, temp_item) if temp_item is not None else None

    return MidForecastResponse(
        tm_fc=selected_tm_fc,
        fetched_at=fetched_at_label(now),
        result_code=land_result_code or temp_result_code or overview_result_code,
        result_msg=land_result_msg or temp_result_msg or overview_result_msg,
        stn_id=stn_id,
        land_reg_id=land_reg_id,
        temp_reg_id=temp_reg_id,
        overview=overview,
        land=land,
        temperature=temperature,
        daily=_build_daily_forecasts(selected_tm_fc, land=land, temperature=temperature),
    )
