import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_db_path() -> str:
    if os.environ.get("AMVERA"):
        return "/data/garden.db"
    return "data/garden.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = ""
    bot_username: str = ""
    webapp_url: str = "http://localhost:8000"
    telegram_proxy: str = ""  # socks5://127.0.0.1:1080 — если api.telegram.org не открывается
    cors_origins: str = "*"  # через запятую, напр. https://user.github.io
    secret_key: str = "change-me"

    # test | prod
    mode: str = "test"
    dev_mode: bool = False
    dev_user_id: int = 1001
    dev_username: str = "local"

    # seconds
    growth_duration_test: int = 300  # 5 min
    growth_duration_prod: int = 36000  # 10 h
    water_cooldown_test: int = 60  # 1 min
    water_cooldown_prod: int = 86400  # 24 h
    water_time_reduction: int = 600  # 10 min per friend water

    # self water (own plant)
    self_water_cooldown_test: int = 10
    self_water_cooldown_prod: int = 86400  # 24 h
    self_water_reduction_percent_test: int = 90
    self_water_reduction_percent_prod: int = 15

    # bonuses (coins)
    new_user_bonus: int = 100
    referrer_bonus: int = 50
    water_bonus: int = 5

    # plant rarities: name:weight pairs
    rarity_weights: str = "common:60,uncommon:25,rare:10,epic:4,legendary:1"
    background_count: int = 10

    ref_mult: int = 8371
    ref_add: int = 52849

    db_path: str = _default_db_path()
    database_url: str = ""  # postgresql://... — для 10k+ онлайн (отдельный проект PostgreSQL на Amvera)
    redis_url: str = ""  # redis://... — кэш /api/me
    run_mode: str = "both"  # both | api | bot — для масштабирования: api отдельно, bot отдельно
    workers: int = 1  # воркеры uvicorn (только run_mode=api или both с workers=1)
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def growth_duration(self) -> int:
        return (
            self.growth_duration_test
            if self.mode == "test"
            else self.growth_duration_prod
        )

    @property
    def water_cooldown(self) -> int:
        return (
            self.water_cooldown_test if self.mode == "test" else self.water_cooldown_prod
        )

    @property
    def self_water_cooldown(self) -> int:
        return (
            self.self_water_cooldown_test
            if self.mode == "test"
            else self.self_water_cooldown_prod
        )

    @property
    def self_water_reduction_percent(self) -> int:
        return (
            self.self_water_reduction_percent_test
            if self.mode == "test"
            else self.self_water_reduction_percent_prod
        )

    def parsed_rarity_weights(self) -> list[tuple[str, int]]:
        result: list[tuple[str, int]] = []
        for part in self.rarity_weights.split(","):
            name, weight = part.strip().split(":")
            result.append((name, int(weight)))
        return result


@lru_cache
def get_settings() -> Settings:
    return Settings()
