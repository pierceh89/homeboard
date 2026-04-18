from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, YamlConfigSettingsSource

APP_DIR = Path(__file__).resolve().parent
SERVICE_DIR = APP_DIR.parent


class AirConditionRequest(BaseModel):
    station: str


class WeatherRequest(BaseModel):
    region: str
    nx: int
    ny: int


class BusStop(BaseModel):
    id: str
    name: str
    filter: list[str]
    no: str


class BusArrivalRequest(BaseModel):
    busstops: list[BusStop]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    access_key: str = Field(default="", validation_alias="ACCESS_KEY")
    public_api_key: str = Field(default="", validation_alias="PUBLIC_API_KEY")
    weather: WeatherRequest
    bus_arrival: BusArrivalRequest
    air: AirConditionRequest

    naver_caldav_url: str = Field(default="https://caldav.calendar.naver.com", validation_alias="NAVER_CALDAV_URL")
    naver_caldav_username: str = Field(default="", validation_alias="NAVER_CALDAV_USERNAME")
    naver_caldav_password: str = Field(default="", validation_alias="NAVER_CALDAV_PASSWORD")
    naver_caldav_calendar_name: str = Field(default="", validation_alias="NAVER_CALDAV_CALENDAR_NAME")

    discord_webhook_url: str = Field(default="", validation_alias="DISCORD_WEBHOOK_URL")

    land_reg_id: str = Field(default="11B00000", validation_alias="LAND_REG_ID")
    temp_reg_id: str = Field(default="11B20612", validation_alias="TEMP_REG_ID")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_file_path = SERVICE_DIR / "settings.yaml"

        yaml_source = YamlConfigSettingsSource(settings_cls, yaml_file=yaml_file_path)
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            yaml_source,
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
