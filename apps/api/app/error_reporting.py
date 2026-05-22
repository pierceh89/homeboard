from datetime import datetime
import logging
import traceback

from fastapi import Request

from app.constants import KST
from app.discord import send_discord


logger = logging.getLogger("uvicorn")


def build_page_error_log(page_name: str, request: Request, exc: Exception) -> str:
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S %Z")
    client_host = request.client.host if request.client else "-"
    user_agent = request.headers.get("user-agent", "-")
    trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    prefix = (
        "[Homeboard Render Error]\n"
        f"time: {now}\n"
        f"page: {page_name}\n"
        f"path: {request.url.path}\n"
        f"client: {client_host}\n"
        f"user-agent: {user_agent}\n"
        f"error: {type(exc).__name__}: {exc}\n"
        "traceback:\n```"
    )
    suffix = "```"
    max_trace_length = 2000 - len(prefix) - len(suffix)
    if max_trace_length < 0:
        return prefix[:1997] + "..."
    if len(trace) > max_trace_length:
        trace = "..." + trace[-max(0, max_trace_length - 3) :]
    return f"{prefix}{trace}{suffix}"


async def notify_page_render_error(page_name: str, request: Request, exc: Exception) -> None:
    try:
        await send_discord(build_page_error_log(page_name, request, exc), username="Homeboard")
    except Exception:
        pass


def log_page_render_error(page_name: str, request: Request, exc: Exception) -> None:
    client_host = request.client.host if request.client else "-"
    user_agent = request.headers.get("user-agent", "-")
    logger.error(
        "Failed to render %s path=%s client=%s user_agent=%s",
        page_name,
        request.url.path,
        client_host,
        user_agent,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
