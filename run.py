"""Запуск API (основной процесс) + бот (фоновый)."""
import logging
import subprocess
import sys
from pathlib import Path

import uvicorn

from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)

    bot_proc = subprocess.Popen([sys.executable, "-m", "app.bot"])
    logger.info("API on %s:%s | WEBAPP_URL=%s", settings.host, settings.port, settings.webapp_url)

    try:
        uvicorn.run(
            "app.main:app",
            host=settings.host,
            port=settings.port,
            log_level="warning",
        )
    finally:
        if bot_proc.poll() is None:
            bot_proc.terminate()
            try:
                bot_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                bot_proc.kill()


if __name__ == "__main__":
    main()
