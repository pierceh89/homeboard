from __future__ import annotations

from dataclasses import dataclass

from api_shared import clean_text, fetch_json, to_int
from settings import BusArrivalRequest, BusStop, get_settings

STATE_CD = {
    0: "교차로통과",
    1: "정류소 도착",
    2: "정류소 출발",
}

CROWDED_CD = {
    1: "여유",
    2: "보통",
    3: "혼잡",
    4: "매우혼잡",
}

FLAG_CD = {
    "RUN": "운행중",
    "PASS": "운행중",
    "STOP": "운행종료",
    "WAIT": "회차지대기",
}

LOW_PLATE_CD = {
    0: "일반버스",
    1: "저상버스",
    2: "2층버스",
    5: "전세버스",
    6: "예약버스",
    7: "트롤리",
}

TAGLESS_CD = {
    0: "일반차량",
    1: "태그리스차량",
}

ROUTE_TYPE_CD = {
    11: "직행좌석형시내버스",
    12: "좌석형시내버스",
    13: "일반형시내버스",
    14: "광역급행형시내버스",
    15: "따복형시내버스",
    16: "경기순환버스",
    21: "직행좌석형농어촌버스",
    22: "좌석형농어촌버스",
    23: "일반형농어촌버스",
    30: "마을버스",
    41: "고속형시외버스",
    42: "좌석형시외버스",
    43: "일반형시외버스",
    51: "리무진공항버스",
    52: "좌석형공항버스",
    53: "일반형공항버스",
}

BUS_ARRIVAL_URL = "https://apis.data.go.kr/6410000/busarrivalservice/v2/getBusArrivalListv2"


@dataclass
class BusVehicleArrival:
    vehId: int | None
    plateNo: str | None
    predictTime: int | None
    predictTimeSec: int | None
    locationNo: int | None
    stationNm: str | None
    stateCd: int | None
    stateName: str | None
    crowded: int | None
    crowdedName: str | None
    remainSeatCnt: int | None
    lowPlate: int | None
    lowPlateName: str | None
    taglessCd: int | None
    taglessName: str | None

    @classmethod
    def from_api(cls, row: dict, suffix: str) -> "BusVehicleArrival":
        state_cd = to_int(row.get(f"stateCd{suffix}"))
        crowded = to_int(row.get(f"crowded{suffix}"))
        low_plate = to_int(row.get(f"lowPlate{suffix}"))
        tagless = to_int(row.get(f"taglessCd{suffix}"))
        return cls(
            vehId=to_int(row.get(f"vehId{suffix}")),
            plateNo=clean_text(row.get(f"plateNo{suffix}")),
            predictTime=to_int(row.get(f"predictTime{suffix}")),
            predictTimeSec=to_int(row.get(f"predictTimeSec{suffix}")),
            locationNo=to_int(row.get(f"locationNo{suffix}")),
            stationNm=clean_text(row.get(f"stationNm{suffix}")),
            stateCd=state_cd,
            stateName=STATE_CD.get(state_cd),
            crowded=crowded,
            crowdedName=CROWDED_CD.get(crowded),
            remainSeatCnt=to_int(row.get(f"remainSeatCnt{suffix}")),
            lowPlate=low_plate,
            lowPlateName=LOW_PLATE_CD.get(low_plate),
            taglessCd=tagless,
            taglessName=TAGLESS_CD.get(tagless),
        )


@dataclass
class BusArrival:
    routeId: int | None
    routeName: str | None
    routeTypeCd: int | None
    routeTypeName: str | None
    routeDestId: int | None
    routeDestName: str | None
    stationId: int | None
    staOrder: int | None
    turnSeq: int | None
    flag: str | None
    flagName: str | None
    firstVehicle: BusVehicleArrival
    secondVehicle: BusVehicleArrival

    @classmethod
    def from_api(cls, row: dict) -> "BusArrival":
        route_type = to_int(row.get("routeTypeCd"))
        flag = clean_text(row.get("flag"))
        return cls(
            routeId=to_int(row.get("routeId")),
            routeName=clean_text(row.get("routeName")),
            routeTypeCd=route_type,
            routeTypeName=ROUTE_TYPE_CD.get(route_type),
            routeDestId=to_int(row.get("routeDestId")),
            routeDestName=clean_text(row.get("routeDestName")),
            stationId=to_int(row.get("stationId")),
            staOrder=to_int(row.get("staOrder")),
            turnSeq=to_int(row.get("turnSeq")),
            flag=flag,
            flagName=FLAG_CD.get(flag),
            firstVehicle=BusVehicleArrival.from_api(row, "1"),
            secondVehicle=BusVehicleArrival.from_api(row, "2"),
        )


@dataclass
class BusArrivalStop:
    stationId: str
    stationName: str
    arrivals: list[BusArrival]

    @classmethod
    def empty(cls, stop: BusStop) -> "BusArrivalStop":
        return cls(
            stationId=stop.no,
            stationName=stop.name,
            arrivals=[],
        )


def _filter_arrivals(rows: list[dict], bus_stop: BusStop) -> list[BusArrival]:
    allowed_routes = set(bus_stop.filter)
    arrivals: list[BusArrival] = []
    for row in rows:
        route_name = clean_text(row.get("routeName"))
        if route_name not in allowed_routes:
            continue
        arrivals.append(BusArrival.from_api(row))
    return arrivals


async def get_bus_arrivals(request: BusArrivalRequest) -> list[BusArrivalStop]:
    settings = get_settings()
    result: list[BusArrivalStop] = []

    for bus_stop in request.busstops:
        payload = await fetch_json(
            url=BUS_ARRIVAL_URL,
            params={
                "serviceKey": settings.public_api_key,
                "stationId": bus_stop.id,
                "format": "json",
            },
        )
        if payload is None:
            result.append(BusArrivalStop.empty(bus_stop))
            continue

        raw_arrivals = payload.get("response", {}).get("msgBody", {}).get("busArrivalList", [])
        if not isinstance(raw_arrivals, list):
            raw_arrivals = []

        result.append(
            BusArrivalStop(
                stationId=bus_stop.no,
                stationName=bus_stop.name,
                arrivals=_filter_arrivals(raw_arrivals, bus_stop),
            )
        )

    return result
