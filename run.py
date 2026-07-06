"""Запуск API и Telegram-бота в отдельных процессах."""
import logging
import signal
import subprocess
import sys
import time
from pathlib import Path

from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)

    python = sys.executable
    api_cmd = [
        python,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        settings.host,
        "--port",
        str(settings.port),
        "--log-level",
        "warning",
    ]
    bot_cmd = [python, "-m", "app.bot"]

    logger.info("API: http://%s:%s", settings.host, settings.port)
    logger.info("WEBAPP_URL=%s", settings.webapp_url)

    api_proc = subprocess.Popen(api_cmd)
    bot_proc = subprocess.Popen(bot_cmd)
    stopping = False

    def stop(_signum=None, _frame=None) -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        for proc in (bot_proc, api_proc):
            if proc.poll() is None:
                proc.terminate()
        for proc in (bot_proc, api_proc):
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        while not stopping:
            if api_proc.poll() is not None:
                logger.error("API exited with code %s", api_proc.returncode)
                stop()
                sys.exit(api_proc.returncode or 1)

            if bot_proc.poll() is not None:
                logger.warning("Bot exited (code %s), restart in 5s...", bot_proc.returncode)
                time.sleep(5)
                if not stopping:
                    bot_proc = subprocess.Popen(bot_cmd)

            time.sleep(1)
    except KeyboardInterrupt:
        stop()


if __name__ == "__main__":
    main()
