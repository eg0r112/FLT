import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.types.error_event import ErrorEvent

from app.config import Settings
from app.services import get_global_grown_total, set_global_grown_total

logger = logging.getLogger(__name__)

_SEND_RETRIES = 3


async def safe_answer(message: types.Message, text: str, **kwargs) -> bool:
    """Ответ в чат с повторами при сетевых сбоях Amvera → Telegram."""
    for attempt in range(_SEND_RETRIES):
        try:
            await message.answer(text, **kwargs)
            return True
        except TelegramNetworkError as exc:
            if attempt + 1 >= _SEND_RETRIES:
                logger.error(
                    "Telegram send failed (chat %s) after %s tries: %s",
                    message.chat.id,
                    _SEND_RETRIES,
                    exc,
                )
                return False
            delay = 2 * (attempt + 1)
            logger.warning(
                "Telegram timeout, retry %s/%s in %ss",
                attempt + 1,
                _SEND_RETRIES,
                delay,
            )
            await asyncio.sleep(delay)
    return False


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

        session = AiohttpSession(
            proxy=settings.telegram_proxy,
            timeout=settings.telegram_timeout,
        )
        logger.info("Using Telegram proxy: %s", settings.telegram_proxy)
        return Bot(token=settings.bot_token, session=session)

    from aiogram.client.session.aiohttp import AiohttpSession

    session = AiohttpSession(timeout=settings.telegram_timeout)
    return Bot(token=settings.bot_token, session=session)


def register_handlers(dp: Dispatcher, settings: Settings) -> None:
    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        if isinstance(event.exception, TelegramNetworkError):
            logger.warning("Telegram network error: %s", event.exception)
            return True
        return False

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

        await safe_answer(
            message,
            text,
            reply_markup=webapp_keyboard(settings.webapp_url, ref),
            parse_mode="HTML",
        )

    @dp.message(Command("garden"))
    async def cmd_garden(message: types.Message) -> None:
        await safe_answer(
            message,
            "Открой мини-приложение:",
            reply_markup=webapp_keyboard(settings.webapp_url),
        )

    @dp.message(F.text)
    async def admin_text(message: types.Message) -> None:
        if not message.from_user or message.from_user.id != settings.admin_telegram_id:
            return
        text = (message.text or "").strip()
        low = text.lower()

        if low == "сколько":
            total = await get_global_grown_total()
            await safe_answer(
                message,
                f"🌍 Выращено в мире: {total:,}".replace(",", " "),
            )
            return

        m = re.match(r"редактировать\s+(\d+)", low)
        if m:
            total = await set_global_grown_total(int(m.group(1)))
            await safe_answer(
                message,
                f"✅ Счётчик установлен: {total:,}".replace(",", " "),
            )
            return


def create_dispatcher(settings: Settings) -> Dispatcher:
    dp = Dispatcher()
    register_handlers(dp, settings)
    return dp
