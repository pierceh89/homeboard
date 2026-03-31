from __future__ import annotations

from datetime import datetime

import httpx


def clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "-":
        return None
    return text


def to_int(value) -> int | None:
    cleaned = clean_text(value)
    if cleaned is None:
        return None
    try:
        return int(float(cleaned))
    except (TypeError, ValueError):
        return None


def to_float(value) -> float | None:
    cleaned = clean_text(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def fetched_at_label(now: datetime) -> str:
    return now.strftime("%Y-%m-%d %H:%M")


def should_propagate_http_error(exc: httpx.HTTPError) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return True
    return False


async def fetch_json(url: str, params: dict, timeout: float = 10.0) -> dict | None:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url=url, params=params, timeout=timeout)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        if should_propagate_http_error(exc):
            raise
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    return payload if isinstance(payload, dict) else None
