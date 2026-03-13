import httpx

from settings import BusArrivalRequest, get_settings

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


def _to_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_str(value):
    if value is None:
        return None
    return str(value)


def _normalize_arrival(row: dict) -> dict:
    route_type = _to_int(row.get("routeTypeCd"))
    state_cd1 = _to_int(row.get("stateCd1"))
    state_cd2 = _to_int(row.get("stateCd2"))
    crowded1 = _to_int(row.get("crowded1"))
    crowded2 = _to_int(row.get("crowded2"))
    low_plate1 = _to_int(row.get("lowPlate1"))
    low_plate2 = _to_int(row.get("lowPlate2"))
    tagless1 = _to_int(row.get("taglessCd1"))
    tagless2 = _to_int(row.get("taglessCd2"))
    flag = _to_str(row.get("flag"))

    return {
        "routeId": _to_int(row.get("routeId")),
        "routeName": _to_str(row.get("routeName")),
        "routeTypeCd": route_type,
        "routeTypeName": ROUTE_TYPE_CD.get(route_type),
        "routeDestId": _to_int(row.get("routeDestId")),
        "routeDestName": _to_str(row.get("routeDestName")),
        "stationId": _to_int(row.get("stationId")),
        "staOrder": _to_int(row.get("staOrder")),
        "turnSeq": _to_int(row.get("turnSeq")),
        "flag": flag,
        "flagName": FLAG_CD.get(flag),
        "firstVehicle": {
            "vehId": _to_int(row.get("vehId1")),
            "plateNo": _to_str(row.get("plateNo1")),
            "predictTime": _to_int(row.get("predictTime1")),
            "predictTimeSec": _to_int(row.get("predictTimeSec1")),
            "locationNo": _to_int(row.get("locationNo1")),
            "stationNm": _to_str(row.get("stationNm1")),
            "stateCd": state_cd1,
            "stateName": STATE_CD.get(state_cd1),
            "crowded": crowded1,
            "crowdedName": CROWDED_CD.get(crowded1),
            "remainSeatCnt": _to_int(row.get("remainSeatCnt1")),
            "lowPlate": low_plate1,
            "lowPlateName": LOW_PLATE_CD.get(low_plate1),
            "taglessCd": tagless1,
            "taglessName": TAGLESS_CD.get(tagless1),
        },
        "secondVehicle": {
            "vehId": _to_int(row.get("vehId2")),
            "plateNo": _to_str(row.get("plateNo2")),
            "predictTime": _to_int(row.get("predictTime2")),
            "predictTimeSec": _to_int(row.get("predictTimeSec2")),
            "locationNo": _to_int(row.get("locationNo2")),
            "stationNm": _to_str(row.get("stationNm2")),
            "stateCd": state_cd2,
            "stateName": STATE_CD.get(state_cd2),
            "crowded": crowded2,
            "crowdedName": CROWDED_CD.get(crowded2),
            "remainSeatCnt": _to_int(row.get("remainSeatCnt2")),
            "lowPlate": low_plate2,
            "lowPlateName": LOW_PLATE_CD.get(low_plate2),
            "taglessCd": tagless2,
            "taglessName": TAGLESS_CD.get(tagless2),
        },
    }


async def get_bus_arrivals(request: BusArrivalRequest) -> list:
    result = []
    settings = get_settings()

    for bus_stop in request.busstops:
        bus_stop_id = bus_stop.id
        bus_stop_name = bus_stop.name
        bus_stop_filter = bus_stop.filter
        query_params = {
            "serviceKey": settings.public_api_key,
            "stationId": bus_stop_id,
            "format": "json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url="https://apis.data.go.kr/6410000/busarrivalservice/v2/getBusArrivalListv2",
                    params=query_params,
                    timeout=10.0,
                )
        except httpx.HTTPError:
            result.append(
                {
                    "stationId": _to_int(bus_stop_id),
                    "stationName": bus_stop_name,
                    "arrivals": [],
                }
            )
            continue

        if response.status_code != 200:
            result.append(
                {
                    "stationId": _to_int(bus_stop_id),
                    "stationName": bus_stop_name,
                    "arrivals": [],
                }
            )
            continue

        res_json = response.json()
        raw_arrivals = res_json.get("response", {}).get("msgBody", {}).get("busArrivalList", [])
        normalized_arrivals = [_normalize_arrival(row) for row in raw_arrivals if str(row["routeName"]) in bus_stop_filter]

        result.append(
            {
                "stationId": bus_stop.no,
                "stationName": bus_stop_name,
                "arrivals": normalized_arrivals,
            }
        )

    return result
