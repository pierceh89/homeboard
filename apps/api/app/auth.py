from fastapi import HTTPException

from app.settings import get_settings


settings = get_settings()


def require_access_key(access_key: str | None):
    if settings.access_key != "" and access_key != settings.access_key:
        raise HTTPException(status_code=404, detail="Not Found")
