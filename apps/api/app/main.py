from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import api, pages


APP_DIR = Path(__file__).resolve().parent
SERVICE_DIR = APP_DIR.parent
STATIC_DIR = SERVICE_DIR / "static"

app = FastAPI()

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(pages.router)
app.include_router(api.router)


@app.get("/")
def read_root():
    return {}
