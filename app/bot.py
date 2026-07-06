import asyncio
import logging
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def webapp_keyboard(url: str, ref: str | None = None) -> InlineKeyboardMarkup:
    full_url = f"{url}?startapp={ref}" if ref else url
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌱 Открыть сад", web_app=WebAppInfo(url=full_url))]
        ]
    )


async def main() -> None:
    settings = get_settings()
    if not settings.bot_token:
        logger.error("BOT_TOKEN is required")
        sys.exit(1)

    session = None
    if settings.telegram_proxy:
        from aiogram.client.session.aiohttp import AiohttpSession

        session = AiohttpSession(proxy=settings.telegram_proxy)
        logger.info("Using Telegram proxy: %s", settings.telegram_proxy)

    bot = Bot(token=settings.bot_token, session=session)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def cmd_start(message: types.Message) -> None:
        ref: str | None = None
        if message.text and len(message.text.split()) > 1:
            arg = message.text.split(maxsplit=1)[1]
            if arg.startswith("ref_"):
                ref = arg

        text = (
            "🌱 <b>Сад семечек</b>\n\n"
            "Выращивай семечки в растения редкой силы!\n"
            "Зови друзей — они помогут полить твой сад и ускорят рост.\n\n"
        )
        if ref:
            text += "Ты перешёл по реферальной ссылке — открой сад для бонуса!\n"

        await message.answer(
            text,
            reply_markup=webapp_keyboard(settings.webapp_url, ref),
            parse_mode="HTML",
        )

    @dp.message(Command("garden"))
    async def cmd_garden(message: types.Message) -> None:
        await message.answer(
            "Открой мини-приложение:",
            reply_markup=webapp_keyboard(settings.webapp_url),
        )

    logger.info("Bot started (mode=%s)", settings.mode)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
