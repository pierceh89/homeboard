from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, YamlConfigSettingsSource


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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_file_path = "settings.yaml"

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
