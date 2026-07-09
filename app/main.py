import asyncio
import json
import logging
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.version import BUILD
from app.config import get_settings
from app.database import close_db, get_db
from app.bot_setup import create_bot, create_dispatcher
from app.ref_code import encode_ref, make_ref_param, resolve_ref
from app.ads import (
    count_admin_unread,
    get_messages,
    get_user_inbox,
    is_admin,
    list_admin_inbox,
    send_message,
    set_blocked,
)
from app.easter import claim_easter_egg, get_active_easter_egg, get_found_egg_ids
from app.services import (
    build_display_name,
    build_shop_state,
    build_upgrades_info,
    buy_upgrade,
    finalize_ready_plants,
    get_friend_growing_plant,
    get_global_growth_window,
    get_leaderboard,
    get_growing_plant,
    get_growing_plants,
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

from pydantic import BaseModel


class AdMessageIn(BaseModel):
    text: str
    conversation_id: int | None = None


class AdBlockIn(BaseModel):
    conversation_id: int


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

    if settings.bot_token and settings.run_mode in ("bot", "both"):
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


_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate"}


@app.get("/")
async def index():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    html = html.replace(
        'href="/static/style.css"',
        f'href="/static/style.css?v={BUILD}"',
    )
    html = html.replace(
        'src="/static/app.js"',
        f'src="/static/app.js?v={BUILD}"',
    )
    return HTMLResponse(html, headers=_NO_CACHE)


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

    growing_plants = await get_growing_plants(db_user["id"])
    growing = growing_plants[0] if growing_plants else None
    ready = await get_ready_plants(db_user["id"])
    stats = await get_user_stats(db_user["id"])
    self_water = await get_self_water_status(db_user["id"])
    settings = get_settings()
    ref_code = encode_ref(telegram_id)
    upgrades = build_upgrades_info(db_user, settings)
    shop = build_shop_state(db_user)

    admin = is_admin(telegram_id, settings)
    ads_unread = await count_admin_unread() if admin else 0
    easter_egg = await get_active_easter_egg(
        db_user["id"], telegram_id, is_admin=admin
    )
    easter_found_count = len(await get_found_egg_ids(db_user["id"]))

    return {
        "user": {
            "telegram_id": db_user["telegram_id"],
            "username": db_user.get("username"),
            "display_name": db_user.get("display_name") or display_name,
            "ref_code": ref_code,
            "coins": db_user["coins"],
            "is_new": is_new,
            "is_admin": admin,
        },
        "growing": growing,
        "growing_plants": growing_plants,
        "ready_plants": ready,
        "stats": stats,
        "self_water": self_water,
        "upgrades": upgrades,
        "shop": shop,
        "config": {
            "growth_duration": upgrades["growth_duration"],
            "water_cooldown": settings.water_cooldown,
            "water_time_reduction": settings.water_time_reduction,
            "self_water_cooldown": settings.self_water_cooldown,
            "self_water_reduction_percent": upgrades["self_water_total_percent"],
            "self_water_seconds": upgrades["self_water_seconds"],
            "mode": settings.mode,
            "dev_mode": settings.dev_mode,
        },
        "referral_link": _referral_link(telegram_id, settings),
        "bot_username": _bot_username(settings),
        "ads_unread": ads_unread,
        "easter_egg": easter_egg,
        "easter_found": easter_found_count,
        "easter_total": 37,
    }


@app.post("/api/plant")
async def api_plant(
    tg_user: dict = Depends(get_tg_user),
    slot: int = Query(1, ge=1),
):
    user = await get_user_by_telegram(tg_user["id"])
    if not user:
        raise HTTPException(404, "User not found")

    plant = await plant_seed(user["id"], slot)
    if not plant:
        raise HTTPException(400, "Slot busy or invalid")
    return {"plant": plant}


@app.post("/api/buy/{upgrade_id}")
async def api_buy(upgrade_id: str, tg_user: dict = Depends(get_tg_user)):
    user = await get_user_by_telegram(tg_user["id"])
    if not user:
        raise HTTPException(404, "User not found")

    result = await buy_upgrade(user["id"], upgrade_id)
    if not result["ok"]:
        raise HTTPException(400, detail=result)
    return result


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


@app.get("/api/global-stats")
async def api_global_stats():
    return await get_global_growth_window()


@app.get("/api/leaderboard")
async def api_leaderboard():
    return await get_leaderboard()


@app.get("/api/ads/inbox")
async def api_ads_inbox(tg_user: dict = Depends(get_tg_user)):
    user = await get_user_by_telegram(tg_user["id"])
    if not user:
        raise HTTPException(404, "User not found")
    settings = get_settings()
    if is_admin(tg_user["id"], settings):
        return {
            "is_admin": True,
            "conversations": await list_admin_inbox(),
        }
    data = await get_user_inbox(user["id"])
    return {"is_admin": False, **data}


@app.get("/api/ads/messages/{conversation_id}")
async def api_ads_messages(
    conversation_id: int,
    tg_user: dict = Depends(get_tg_user),
):
    user = await get_user_by_telegram(tg_user["id"])
    if not user:
        raise HTTPException(404, "User not found")
    settings = get_settings()
    admin = is_admin(tg_user["id"], settings)
    if not admin:
        raise HTTPException(403, "Forbidden")
    messages = await get_messages(conversation_id, user["id"], admin=True)
    return {"messages": messages}


@app.post("/api/ads/messages")
async def api_ads_send(body: AdMessageIn, tg_user: dict = Depends(get_tg_user)):
    user = await get_user_by_telegram(tg_user["id"])
    if not user:
        raise HTTPException(404, "User not found")
    settings = get_settings()
    admin = is_admin(tg_user["id"], settings)
    result = await send_message(
        user["id"],
        body.text,
        is_admin_user=admin,
        conversation_id=body.conversation_id,
    )
    if not result["ok"]:
        raise HTTPException(400, detail=result)
    return result


@app.post("/api/ads/block")
async def api_ads_block(body: AdBlockIn, tg_user: dict = Depends(get_tg_user)):
    if not is_admin(tg_user["id"]):
        raise HTTPException(403, "Forbidden")
    result = await set_blocked(body.conversation_id, True)
    if not result["ok"]:
        raise HTTPException(400, detail=result)
    return result


@app.post("/api/ads/unblock")
async def api_ads_unblock(body: AdBlockIn, tg_user: dict = Depends(get_tg_user)):
    if not is_admin(tg_user["id"]):
        raise HTTPException(403, "Forbidden")
    result = await set_blocked(body.conversation_id, False)
    if not result["ok"]:
        raise HTTPException(400, detail=result)
    return result


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
async def api_water_self(
    tg_user: dict = Depends(get_tg_user),
    plant_id: int = Query(...),
):
    user = await get_user_by_telegram(tg_user["id"])
    if not user:
        raise HTTPException(404, "User not found")

    result = await water_own_plant(user["id"], plant_id)
    if not result["ok"]:
        raise HTTPException(400, detail=result)
    return result


@app.post("/api/easter-egg/claim")
async def api_easter_egg_claim(
    tg_user: dict = Depends(get_tg_user),
    egg_id: int = Query(..., ge=1, le=37),
):
    user = await get_user_by_telegram(tg_user["id"])
    if not user:
        raise HTTPException(404, "User not found")

    result = await claim_easter_egg(user["id"], egg_id)
    if not result["ok"]:
        raise HTTPException(400, detail=result)
    return result


@app.get("/health")
async def health():
    return {"status": "ok", "version": BUILD}
