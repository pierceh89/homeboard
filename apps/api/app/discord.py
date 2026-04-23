from __future__ import annotations

from typing import Any

import httpx

from app.settings import get_settings

DISCORD_MESSAGE_LIMIT = 2000


class DiscordWebhookNotConfiguredError(RuntimeError):
    pass


async def send_discord(
    message: str,
    *,
    username: str | None = None,
    avatar_url: str | None = None,
    webhook_url: str | None = None,
    timeout: float = 10.0,
) -> None:
    content = message.strip()
    if not content:
        raise ValueError("Discord message must not be empty")
    if len(content) > DISCORD_MESSAGE_LIMIT:
        raise ValueError(f"Discord message must be {DISCORD_MESSAGE_LIMIT} characters or fewer")

    target_webhook_url = webhook_url or get_settings().discord_webhook_url
    if not target_webhook_url:
        raise DiscordWebhookNotConfiguredError("DISCORD_WEBHOOK_URL is not configured")

    payload: dict[str, Any] = {"content": content}
    if username is not None:
        payload["username"] = username
    if avatar_url is not None:
        payload["avatar_url"] = avatar_url

    async with httpx.AsyncClient() as client:
        response = await client.post(target_webhook_url, json=payload, timeout=timeout)
        response.raise_for_status()


async def main():
    await send_discord("hello discord")



if __name__ == '__main__':
    import asyncio
    asyncio.run(main())