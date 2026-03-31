from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock
from typing import Awaitable, Callable, TypeVar

import httpx

from air import AirConditionResponse, get_air_condition
from api import BusArrivalStop, get_bus_arrivals
from api_shared import should_propagate_http_error
from mid_forecast import MidForecastResponse, get_mid_forecast
from settings import get_settings
from weather import WeatherResponse, _select_base, get_weather

WEATHER_CACHE_TTL = timedelta(minutes=30)
BUS_CACHE_TTL = timedelta(minutes=1)
AIR_CACHE_TTL = timedelta(minutes=15)
MID_CACHE_TTL = timedelta(hours=6)

settings = get_settings()

_weather_cache_lock = Lock()
_weather_cache = {"value": None, "expires_at": None}

_bus_cache_lock = Lock()
_bus_cache = {"value": None, "expires_at": None}

_air_cache_lock = Lock()
_air_cache = {"value": None, "expires_at": None}

_mid_cache_lock = Lock()
_mid_cache = {"value": None, "expires_at": None}

CacheValue = TypeVar("CacheValue")


async def _get_cached_value(
    *,
    now: datetime,
    lock: Lock,
    cache: dict[str, object | None],
    ttl: timedelta,
    fetcher: Callable[[], Awaitable[CacheValue]],
    force_reload: bool = False,
) -> CacheValue:
    if not force_reload:
        with lock:
            cached_value = cache["value"]
            expires_at = cache["expires_at"]
            if cached_value is not None and isinstance(expires_at, datetime) and now < expires_at:
                return cached_value  # type: ignore[return-value]

    fresh_value = await fetcher()

    with lock:
        cache["value"] = fresh_value
        cache["expires_at"] = now + ttl

    return fresh_value


async def get_weather_cached(now: datetime, force_reload: bool = False):
    async def _fetch_weather():
        try:
            return await get_weather(now, settings.weather)
        except httpx.HTTPError as exc:
            if should_propagate_http_error(exc):
                raise
            base_date, base_time = _select_base(now)
            return WeatherResponse.empty(
                region=settings.weather.region,
                base_date=base_date,
                base_time=base_time,
                now=now,
            )
        except Exception:
            base_date, base_time = _select_base(now)
            return WeatherResponse.empty(
                region=settings.weather.region,
                base_date=base_date,
                base_time=base_time,
                now=now,
            )

    return await _get_cached_value(
        now=now,
        lock=_weather_cache_lock,
        cache=_weather_cache,
        ttl=WEATHER_CACHE_TTL,
        fetcher=_fetch_weather,
        force_reload=force_reload,
    )


async def get_bus_arrivals_cached(now: datetime, force_reload: bool = False):
    async def _fetch_bus_arrivals():
        try:
            return await get_bus_arrivals(request=settings.bus_arrival)
        except httpx.HTTPError as exc:
            if should_propagate_http_error(exc):
                raise
            return [BusArrivalStop.empty(bus_stop) for bus_stop in settings.bus_arrival.busstops]
        except Exception:
            return [BusArrivalStop.empty(bus_stop) for bus_stop in settings.bus_arrival.busstops]

    return await _get_cached_value(
        now=now,
        lock=_bus_cache_lock,
        cache=_bus_cache,
        ttl=BUS_CACHE_TTL,
        fetcher=_fetch_bus_arrivals,
        force_reload=force_reload,
    )


async def get_air_condition_cached(now: datetime, force_reload: bool = False):
    async def _fetch_air_condition():
        try:
            return await get_air_condition(now)
        except httpx.HTTPError as exc:
            if should_propagate_http_error(exc):
                raise
            return AirConditionResponse.empty(station=settings.air.station, now=now)
        except Exception:
            return AirConditionResponse.empty(station=settings.air.station, now=now)

    return await _get_cached_value(
        now=now,
        lock=_air_cache_lock,
        cache=_air_cache,
        ttl=AIR_CACHE_TTL,
        fetcher=_fetch_air_condition,
        force_reload=force_reload,
    )


async def get_mid_forecast_cached(now: datetime, force_reload: bool = False):
    async def _fetch_mid():
        try:
            return await get_mid_forecast(
                now=now,
                land_reg_id=settings.land_reg_id,
                temp_reg_id=settings.temp_reg_id,
            )
        except httpx.HTTPError as exc:
            if should_propagate_http_error(exc):
                raise
            return MidForecastResponse.empty(
                now=now,
                tm_fc=now.strftime("%Y%m%d%H%M"),
                land_reg_id=settings.land_reg_id,
                temp_reg_id=settings.temp_reg_id,
                stn_id=None,
            )
        except Exception:
            return MidForecastResponse.empty(
                now=now,
                tm_fc=now.strftime("%Y%m%d%H%M"),
                land_reg_id=settings.land_reg_id,
                temp_reg_id=settings.temp_reg_id,
                stn_id=None,
            )

    return await _get_cached_value(
        now=now,
        lock=_mid_cache_lock,
        cache=_mid_cache,
        ttl=MID_CACHE_TTL,
        fetcher=_fetch_mid,
        force_reload=force_reload,
    )
