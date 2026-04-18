from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.api_shared import clean_text, fetch_json, fetched_at_label, to_float, to_int
from app.settings import get_settings

GRADE_LABELS = {
    1: "좋음",
    2: "보통",
    3: "나쁨",
    4: "매우나쁨",
}

AIR_CONDITION_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"


def _grade_label(value: int | None) -> str | None:
    if value is None:
        return None
    return GRADE_LABELS.get(value)


@dataclass
class AirMeasurement:
    data_time: str | None = None
    station_name: str | None = None
    station_code: str | None = None
    mang_name: str | None = None
    so2_value: float | None = None
    co_value: float | None = None
    o3_value: float | None = None
    no2_value: float | None = None
    pm10_value: int | None = None
    pm10_value24: int | None = None
    pm25_value: int | None = None
    pm25_value24: int | None = None
    khai_value: int | None = None
    khai_grade: int | None = None
    khai_grade_label: str | None = None
    so2_grade: int | None = None
    co_grade: int | None = None
    o3_grade: int | None = None
    no2_grade: int | None = None
    pm10_grade: int | None = None
    pm10_grade_label: str | None = None
    pm25_grade: int | None = None
    pm25_grade_label: str | None = None
    pm10_grade1h: int | None = None
    pm10_grade1h_label: str | None = None
    pm25_grade1h: int | None = None
    pm25_grade1h_label: str | None = None
    so2_flag: str | None = None
    co_flag: str | None = None
    o3_flag: str | None = None
    no2_flag: str | None = None
    pm10_flag: str | None = None
    pm25_flag: str | None = None

    @classmethod
    def from_api(cls, item: dict) -> "AirMeasurement":
        khai_grade = to_int(item.get("khaiGrade"))
        pm10_grade = to_int(item.get("pm10Grade"))
        pm25_grade = to_int(item.get("pm25Grade"))
        pm10_grade1h = to_int(item.get("pm10Grade1h"))
        pm25_grade1h = to_int(item.get("pm25Grade1h"))
        return cls(
            data_time=clean_text(item.get("dataTime")),
            station_name=clean_text(item.get("stationName")),
            station_code=clean_text(item.get("stationCode")),
            mang_name=clean_text(item.get("mangName")),
            so2_value=to_float(item.get("so2Value")),
            co_value=to_float(item.get("coValue")),
            o3_value=to_float(item.get("o3Value")),
            no2_value=to_float(item.get("no2Value")),
            pm10_value=to_int(item.get("pm10Value")),
            pm10_value24=to_int(item.get("pm10Value24")),
            pm25_value=to_int(item.get("pm25Value")),
            pm25_value24=to_int(item.get("pm25Value24")),
            khai_value=to_int(item.get("khaiValue")),
            khai_grade=khai_grade,
            khai_grade_label=_grade_label(khai_grade),
            so2_grade=to_int(item.get("so2Grade")),
            co_grade=to_int(item.get("coGrade")),
            o3_grade=to_int(item.get("o3Grade")),
            no2_grade=to_int(item.get("no2Grade")),
            pm10_grade=pm10_grade,
            pm10_grade_label=_grade_label(pm10_grade),
            pm25_grade=pm25_grade,
            pm25_grade_label=_grade_label(pm25_grade),
            pm10_grade1h=pm10_grade1h,
            pm10_grade1h_label=_grade_label(pm10_grade1h),
            pm25_grade1h=pm25_grade1h,
            pm25_grade1h_label=_grade_label(pm25_grade1h),
            so2_flag=clean_text(item.get("so2Flag")),
            co_flag=clean_text(item.get("coFlag")),
            o3_flag=clean_text(item.get("o3Flag")),
            no2_flag=clean_text(item.get("no2Flag")),
            pm10_flag=clean_text(item.get("pm10Flag")),
            pm25_flag=clean_text(item.get("pm25Flag")),
        )


@dataclass
class AirConditionResponse:
    station: str
    fetched_at: str
    result_code: str | None
    result_msg: str | None
    num_of_rows: int | None
    page_no: int | None
    total_count: int | None
    items: list[AirMeasurement]
    current: AirMeasurement | None

    @classmethod
    def empty(cls, station: str, now: datetime) -> "AirConditionResponse":
        return cls(
            station=station,
            fetched_at=fetched_at_label(now),
            result_code=None,
            result_msg=None,
            num_of_rows=None,
            page_no=None,
            total_count=None,
            items=[],
            current=None,
        )


def _parse_air_items(body: dict) -> list[AirMeasurement]:
    raw_items = body.get("items", [])
    if isinstance(raw_items, dict):
        raw_items = raw_items.get("item", [])
    if not isinstance(raw_items, list):
        return []
    return [AirMeasurement.from_api(item) for item in raw_items if isinstance(item, dict)]


async def get_air_condition(now: datetime) -> AirConditionResponse:
    settings = get_settings()
    station = settings.air.station
    payload = await fetch_json(
        url=AIR_CONDITION_URL,
        params={
            "serviceKey": settings.public_api_key,
            "returnType": "json",
            "numOfRows": 100,
            "pageNo": 1,
            "stationName": station,
            "dataTerm": "DAILY",
            "ver": "1.0",
        },
    )
    if payload is None:
        return AirConditionResponse.empty(station=station, now=now)

    response = payload.get("response", {})
    header = response.get("header", {})
    body = response.get("body", {})
    items = _parse_air_items(body)
    return AirConditionResponse(
        station=station,
        fetched_at=fetched_at_label(now),
        result_code=clean_text(header.get("resultCode")),
        result_msg=clean_text(header.get("resultMsg")),
        num_of_rows=to_int(body.get("numOfRows")),
        page_no=to_int(body.get("pageNo")),
        total_count=to_int(body.get("totalCount")),
        items=items,
        current=items[0] if items else None,
    )
