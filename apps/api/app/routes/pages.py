from datetime import datetime
import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.templating import Jinja2Templates

from app.core.auth import require_access_key
from app.services.cache_layer import (
    get_air_condition_cached,
    get_bus_arrivals_cached,
    get_mid_forecast_cached,
    get_weather_cached,
)
from app.core.constants import KST, WEEKDAY_KO
from app.core.error_reporting import log_page_render_error, notify_page_render_error
from app.core.image_utils import convert_png_to_8bit_grayscale
from app.services.page_context import (
    build_hourly_series,
    build_weekly_outlook,
    get_kindle_calendar_context,
)


SERVICE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = SERVICE_DIR / "static" / "templates"
KINDLE_IMAGE_RENDER_RETRY_COUNT = 3
KINDLE_IMAGE_RENDER_RETRY_DELAY_SECONDS = 1.0
KINDLE_IMAGE_RENDER_SETTLE_SECONDS = 0.5

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/home")
async def get_home(request: Request, accessKey: str | None = None):
    require_access_key(accessKey)

    try:
        now = datetime.now(KST)
        weather = await get_weather_cached(now)
        bus_stops = await get_bus_arrivals_cached(now)
        air = await get_air_condition_cached(now)
        mid = await get_mid_forecast_cached(now)
        hourly_series = build_hourly_series(weather.forecasts, max_items=24)
        weekly_outlook = build_weekly_outlook(now, weather, mid)
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
        log_page_render_error("/home", request, exc)
        raise


@router.get("/kindle")
async def get_kindle_home(request: Request, accessKey: str | None = None):
    require_access_key(accessKey)

    try:
        now = datetime.now(KST)
        weather = await get_weather_cached(now)
        air = await get_air_condition_cached(now)
        mid = await get_mid_forecast_cached(now)
        hourly_series = build_hourly_series(weather.forecasts, max_items=24)
        weekly_outlook = build_weekly_outlook(now, weather, mid)
        calendar_context = get_kindle_calendar_context(now)
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
                **calendar_context,
            },
        )
    except Exception as exc:
        log_page_render_error("/kindle", request, exc)
        raise


@router.get("/kindle-image")
async def get_kindle_home_image(request: Request, accessKey: str | None = None):
    require_access_key(accessKey)

    try:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise HTTPException(status_code=500, detail="playwright is not installed") from exc

        target_url = str(request.url_for("get_kindle_home"))
        target_url = f"{target_url}?accessKey={accessKey}"

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(
                    viewport={"width": 600, "height": 800},
                    device_scale_factor=1,
                )
                last_status_code = None
                page_loaded = False
                for attempt in range(1, KINDLE_IMAGE_RENDER_RETRY_COUNT + 1):
                    page_response = await page.goto(target_url, wait_until="load")
                    last_status_code = page_response.status if page_response is not None else None
                    if page_response is not None and page_response.ok:
                        page_loaded = True
                        break
                    if attempt < KINDLE_IMAGE_RENDER_RETRY_COUNT:
                        await asyncio.sleep(KINDLE_IMAGE_RENDER_RETRY_DELAY_SECONDS)

                if not page_loaded:
                    status_description = (
                        str(last_status_code) if last_status_code is not None else "no response"
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=f"failed to load kindle page for image render: {status_description}",
                    )

                await asyncio.sleep(KINDLE_IMAGE_RENDER_SETTLE_SECONDS)
                image_bytes = await page.screenshot(type="png", full_page=False)
                image_bytes = convert_png_to_8bit_grayscale(image_bytes)
            finally:
                await browser.close()
    except HTTPException as exc:
        await notify_page_render_error("/kindle-image", request, exc)
        raise
    except Exception as exc:
        await notify_page_render_error("/kindle-image", request, exc)
        raise HTTPException(status_code=500, detail=f"failed to capture kindle image: {exc}") from exc

    return Response(content=image_bytes, media_type="image/png")
