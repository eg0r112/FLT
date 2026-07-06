import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.config import Settings

logger = logging.getLogger(__name__)


def webapp_keyboard(url: str, ref: str | None = None) -> InlineKeyboardMarkup:
    full_url = f"{url}?startapp={ref}" if ref else url
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌱 Открыть сад", web_app=WebAppInfo(url=full_url))]
        ]
    )


def create_bot(settings: Settings) -> Bot:
    if settings.telegram_proxy:
        from aiogram.client.session.aiohttp import AiohttpSession

        session = AiohttpSession(proxy=settings.telegram_proxy)
        logger.info("Using Telegram proxy: %s", settings.telegram_proxy)
        return Bot(token=settings.bot_token, session=session)
    return Bot(token=settings.bot_token)


def register_handlers(dp: Dispatcher, settings: Settings) -> None:
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


def create_dispatcher(settings: Settings) -> Dispatcher:
    dp = Dispatcher()
    register_handlers(dp, settings)
    return dp
