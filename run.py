"""Запуск: both (по умолчанию), api (масштабирование), bot (отдельный инстанс)."""
import asyncio
import logging
import sys
from pathlib import Path

import uvicorn

from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _run_api() -> None:
    settings = get_settings()
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    logger.info(
        "API %s:%s workers=%s mode=%s",
        settings.host,
        settings.port,
        settings.workers,
        settings.run_mode,
    )
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers if settings.run_mode == "api" else 1,
        log_level="warning",
    )


def _run_bot() -> None:
    from app.bot import main as bot_main

    asyncio.run(bot_main())


def main() -> None:
    settings = get_settings()
    mode = settings.run_mode

    if mode == "bot":
        _run_bot()
    elif mode == "api":
        if settings.workers > 1 and settings.bot_token:
            logger.warning("workers>1: бот не запускается, вынеси RUN_MODE=bot в отдельный проект")
        _run_api()
    else:
        if settings.workers > 1:
            logger.error("RUN_MODE=both не совместим с workers>1. Используй RUN_MODE=api + отдельный bot")
            sys.exit(1)
        _run_api()


if __name__ == "__main__":
    main()
