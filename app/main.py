import asyncio
import json
import logging
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import close_db, get_db
from app.bot_setup import create_bot, create_dispatcher
from app.ref_code import encode_ref, make_ref_param, resolve_ref
from app.services import (
    build_display_name,
    finalize_ready_plants,
    get_friend_growing_plant,
    get_growing_plant,
    get_or_create_user,
    get_ready_plants,
    get_self_water_status,
    get_user_by_telegram,
    get_user_stats,
    plant_seed,
    validate_init_data,
    water_own_plant,
    water_plant,
)

logger = logging.getLogger(__name__)
STATIC = Path(__file__).resolve().parent.parent / "static"
_cached_bot_username: str | None = None
_polling_task: asyncio.Task | None = None


async def _run_polling(settings) -> None:
    while True:
        bot = None
        try:
            bot = create_bot(settings)
            await bot.delete_webhook(drop_pending_updates=False)
            dp = create_dispatcher(settings)
            logger.info("Bot polling started")
            await dp.start_polling(bot, handle_signals=False)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Bot polling error: %s — retry in 15s", e)
            await asyncio.sleep(15)
        finally:
            if bot:
                try:
                    await bot.session.close()
                except Exception:
                    pass


def _fetch_bot_username(token: str) -> str | None:
    try:
        with urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/getMe", timeout=15
        ) as resp:
            data = json.load(resp)
        return data.get("result", {}).get("username")
    except Exception as e:
        logger.warning("getMe failed: %s", e)
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cached_bot_username, _polling_task
    settings = get_settings()
    if settings.bot_token and not settings.bot_username:
        uname = await asyncio.to_thread(_fetch_bot_username, settings.bot_token)
        if uname:
            _cached_bot_username = uname
            logger.info("Bot username: @%s", uname)

    await get_db()

    if settings.bot_token:
        _polling_task = asyncio.create_task(_run_polling(settings))

    yield

    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass

    try:
        await close_db()
    except Exception:
        pass


app = FastAPI(title="Garden Mini App", lifespan=lifespan)

_settings = get_settings()
_origins = [o.strip() for o in _settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC), name="static")


def get_tg_user(
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    x_dev_user_id: int | None = Header(None, alias="X-Dev-User-Id"),
) -> dict:
    settings = get_settings()
    if settings.dev_mode:
        uid = x_dev_user_id if x_dev_user_id else settings.dev_user_id
        return {
            "id": uid,
            "username": f"player_{uid}",
            "first_name": "Игрок",
            "last_name": str(uid),
        }
    if not settings.bot_token:
        raise HTTPException(500, "Bot token not configured")
    if not x_telegram_init_data:
        raise HTTPException(401, "Invalid init data")
    user = validate_init_data(x_telegram_init_data, settings.bot_token)
    if not user:
        raise HTTPException(401, "Invalid init data")
    return user


def _bot_username(settings) -> str:
    global _cached_bot_username
    if settings.bot_username:
        return settings.bot_username
    if _cached_bot_username:
        return _cached_bot_username
    if settings.bot_token:
        uname = _fetch_bot_username(settings.bot_token)
        if uname:
            _cached_bot_username = uname
            return uname
    return "bot"


def _referral_link(telegram_id: int, settings) -> str:
    ref = make_ref_param(telegram_id)
    if settings.dev_mode:
        return f"{settings.webapp_url}/?startapp={ref}&as={telegram_id + 1}"
    return f"https://t.me/{_bot_username(settings)}?start={ref}"


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/me")
async def api_me(
    tg_user: dict = Depends(get_tg_user),
    ref: int | None = Query(None),
):
    telegram_id = tg_user["id"]
    username = tg_user.get("username")
    display_name = build_display_name(tg_user)

    referrer_id: int | None = None
    if ref is not None:
        referrer_id = resolve_ref(ref)

    db_user, is_new = await get_or_create_user(
        telegram_id, username, referrer_id, display_name
    )
    await finalize_ready_plants(db_user["id"])

    growing = await get_growing_plant(db_user["id"])
    ready = await get_ready_plants(db_user["id"])
    stats = await get_user_stats(db_user["id"])
    self_water = await get_self_water_status(db_user["id"])
    settings = get_settings()
    ref_code = encode_ref(telegram_id)

    return {
        "user": {
            "telegram_id": db_user["telegram_id"],
            "username": db_user.get("username"),
            "display_name": db_user.get("display_name") or display_name,
            "ref_code": ref_code,
            "coins": db_user["coins"],
            "is_new": is_new,
        },
        "growing": growing,
        "ready_plants": ready,
        "stats": stats,
        "self_water": self_water,
        "config": {
            "growth_duration": settings.growth_duration,
            "water_cooldown": settings.water_cooldown,
            "self_water_cooldown": settings.self_water_cooldown,
            "self_water_reduction_percent": settings.self_water_reduction_percent,
            "mode": settings.mode,
            "dev_mode": settings.dev_mode,
        },
        "referral_link": _referral_link(telegram_id, settings),
        "bot_username": _bot_username(settings),
    }


@app.post("/api/plant")
async def api_plant(tg_user: dict = Depends(get_tg_user)):
    user = await get_user_by_telegram(tg_user["id"])
    if not user:
        raise HTTPException(404, "User not found")

    plant = await plant_seed(user["id"])
    if not plant:
        raise HTTPException(400, "Already growing")
    return {"plant": plant}


@app.get("/api/friend/{ref_code}")
async def api_friend(
    ref_code: int,
    tg_user: dict = Depends(get_tg_user),
):
    owner_tid = resolve_ref(ref_code)
    if not owner_tid:
        raise HTTPException(400, "Invalid ref code")
    plant = await get_friend_growing_plant(owner_tid)
    if not plant:
        return {"plant": None}
    return {"plant": plant}


@app.post("/api/water/{plant_id}")
async def api_water(
    plant_id: int,
    owner_ref: int = Query(...),
    tg_user: dict = Depends(get_tg_user),
):
    user = await get_user_by_telegram(tg_user["id"])
    if not user:
        raise HTTPException(404, "User not found")

    owner_tid = resolve_ref(owner_ref)
    if not owner_tid:
        raise HTTPException(400, "Invalid ref code")
    owner = await get_user_by_telegram(owner_tid)
    if not owner:
        raise HTTPException(404, "Owner not found")

    result = await water_plant(user["id"], plant_id, owner["id"])
    if not result["ok"]:
        raise HTTPException(400, detail=result)
    return result


@app.post("/api/water-self")
async def api_water_self(tg_user: dict = Depends(get_tg_user)):
    user = await get_user_by_telegram(tg_user["id"])
    if not user:
        raise HTTPException(404, "User not found")

    plant = await get_growing_plant(user["id"])
    if not plant:
        raise HTTPException(400, "No growing plant")

    result = await water_own_plant(user["id"], plant["id"])
    if not result["ok"]:
        raise HTTPException(400, detail=result)
    return result


@app.get("/health")
async def health():
    return {"status": "ok"}
