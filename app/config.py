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
    telegram_proxy: str = ""
    cors_origins: str = "*"
    secret_key: str = "change-me"

    mode: str = "prod"
    dev_mode: bool = False
    dev_user_id: int = 1001
    dev_username: str = "local"

    admin_telegram_id: int = 5143241640
    reset_db: bool = False

    # seconds
    growth_duration_test: int = 300
    growth_duration_prod: int = 18000  # 5 h
    water_cooldown_test: int = 60
    water_cooldown_prod: int = 86400  # 1 раз в сутки на грядку друга
    water_time_reduction: int = 3600  # −1 ч за полив

    self_water_cooldown_test: int = 10
    self_water_cooldown_prod: int = 18000  # 5 h
    self_water_reduction_percent_test: int = 90
    self_water_reduction_percent_prod: int = 15  # база для бонуса лейки

    new_user_bonus: int = 100
    referrer_bonus: int = 50
    water_bonus: int = 0

    rarity_weights: str = "common:60,uncommon:25,rare:10,epic:4,legendary:1"
    background_count: int = 10

    ref_mult: int = 8371
    ref_add: int = 52849

    db_path: str = _default_db_path()
    database_url: str = ""
    redis_url: str = ""
    run_mode: str = "both"
    workers: int = 1
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
