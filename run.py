"""Запуск API. На Amvera бот работает через webhook в app.main."""
import logging
from pathlib import Path

import uvicorn

from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)

    logger.info("API on %s:%s | WEBAPP_URL=%s", settings.host, settings.port, settings.webapp_url)

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
