import asyncio
import logging
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.bot_setup import create_bot, create_dispatcher
from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    if not settings.bot_token:
        logger.error("BOT_TOKEN is required")
        sys.exit(1)

    bot = create_bot(settings)
    dp = create_dispatcher(settings)

    logger.info("Bot polling (mode=%s)", settings.mode)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
