import hashlib
import hmac
import json
import random
import time
import urllib.parse
from functools import lru_cache
from typing import Any

from app.config import get_settings
from app.database import get_db
from app.market import COSMIC_BACKGROUND_ID, plant_market_price
from app.plants import (
    ALL_VARIANT_IDS,
    rarity_for_variant,
    roll_space_variant_for_rarity,
    roll_variant_for_rarity,
)

NOW = lambda: int(time.time())

PLOT_PRICE = 200
PLOT_MAX = 10
SPEED_PRICES = (100, 200)
SPEED_MAX = 2
WATER_CAN_PRICES = (50, 100, 150)
WATER_CAN_MAX = 3


@lru_cache(maxsize=1)
def _rarity_tables() -> tuple[tuple[str, ...], tuple[int, ...]]:
    weights = get_settings().parsed_rarity_weights()
    names, values = zip(*weights)
    return names, values


def validate_init_data(init_data: str, bot_token: str) -> dict[str, Any] | None:
    """Validate Telegram WebApp initData."""
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None

    auth_date = int(parsed.get("auth_date", 0))
    if NOW() - auth_date > 86400:
        return None

    user_raw = parsed.get("user")
    if not user_raw:
        return None
    return json.loads(user_raw)


def roll_rarity() -> str:
    names, weights = _rarity_tables()
    return random.choices(names, weights=weights, k=1)[0]


def roll_background(*, in_portal: bool = False) -> int:
    if in_portal and random.random() < 0.05:
        return COSMIC_BACKGROUND_ID
    return random.randint(1, get_settings().background_count)


GLOBAL_GROWN_KEY = "global_grown_total"


async def _upsert_setting(key: str, value: str) -> None:
    db = await get_db()
    await db.execute(
        "INSERT INTO app_settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    await db.commit()


async def get_app_setting(key: str) -> str | None:
    db = await get_db()
    cur = await db.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
    row = await cur.fetchone()
    if not row:
        return None
    return row["value"] if isinstance(row, dict) else row[0]


async def get_global_grown_total() -> int:
    raw = await get_app_setting(GLOBAL_GROWN_KEY)
    if raw is not None:
        return max(0, int(raw))
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) AS c FROM plants WHERE status = 'ready'")
    row = await cur.fetchone()
    return int(row["c"] if isinstance(row, dict) else row[0])


async def set_global_grown_total(total: int) -> int:
    total = max(0, int(total))
    await _upsert_setting(GLOBAL_GROWN_KEY, str(total))
    return total


async def increment_global_grown(count: int = 1) -> int:
    total = await get_global_grown_total()
    total += max(0, int(count))
    await _upsert_setting(GLOBAL_GROWN_KEY, str(total))
    return total


async def get_user_by_telegram(telegram_id: int) -> dict | None:
    db = await get_db()
    cur = await db.execute(
        "SELECT id, telegram_id, username, display_name, referrer_id, coins, "
        "extra_plots, speed_level, water_can_level, portal_dimension, created_at "
        "FROM users WHERE telegram_id = ?",
        (telegram_id,),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def get_user_by_id(user_id: int) -> dict | None:
    db = await get_db()
    cur = await db.execute(
        "SELECT id, telegram_id, username, display_name, referrer_id, coins, "
        "extra_plots, speed_level, water_can_level, portal_dimension, created_at "
        "FROM users WHERE id = ?",
        (user_id,),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


def plot_count(user: dict) -> int:
    return min(PLOT_MAX, 1 + int(user.get("extra_plots") or 0))


def max_extra_plots() -> int:
    return PLOT_MAX - 1


def growth_duration_for_user(settings, user: dict) -> int:
    level = int(user.get("speed_level") or 0)
    base = settings.growth_duration
    return max(30, int(base * (1 - 0.15 * level)))


def self_water_seconds(settings, user: dict) -> int:
    base = settings.water_time_reduction
    bonus = int(user.get("water_can_level") or 0) * int(base * 0.1)
    return base + bonus


def self_water_percent(settings, user: dict) -> int:
    bonus = int(user.get("water_can_level") or 0) * 10
    return settings.self_water_reduction_percent + bonus


def build_upgrades_info(user: dict, settings) -> dict:
    speed_level = int(user.get("speed_level") or 0)
    water_level = int(user.get("water_can_level") or 0)
    extra = int(user.get("extra_plots") or 0)
    return {
        "extra_plots": extra,
        "plot_count": plot_count(user),
        "plot_max": PLOT_MAX,
        "speed_level": speed_level,
        "speed_max": SPEED_MAX,
        "water_can_level": water_level,
        "water_can_max": WATER_CAN_MAX,
        "growth_reduction_percent": speed_level * 15,
        "self_water_bonus_percent": water_level * 10,
        "self_water_total_percent": self_water_percent(settings, user),
        "self_water_seconds": self_water_seconds(settings, user),
        "growth_duration": growth_duration_for_user(settings, user),
    }


def build_shop_state(user: dict) -> dict:
    coins = int(user["coins"])
    extra = int(user.get("extra_plots") or 0)
    speed = int(user.get("speed_level") or 0)
    water = int(user.get("water_can_level") or 0)
    speed_price = SPEED_PRICES[speed] if speed < SPEED_MAX else None
    water_price = WATER_CAN_PRICES[water] if water < WATER_CAN_MAX else None
    return {
        "plot": {
            "price": PLOT_PRICE,
            "owned": extra,
            "max": max_extra_plots(),
            "can_buy": coins >= PLOT_PRICE and extra < max_extra_plots(),
        },
        "speed": {
            "level": speed,
            "max": SPEED_MAX,
            "price": speed_price,
            "can_buy": speed < SPEED_MAX and speed_price is not None and coins >= speed_price,
        },
        "water_can": {
            "level": water,
            "max": WATER_CAN_MAX,
            "price": water_price,
            "can_buy": water < WATER_CAN_MAX and water_price is not None and coins >= water_price,
        },
    }


async def buy_upgrade(user_id: int, upgrade_type: str) -> dict:
    user = await get_user_by_id(user_id)
    if not user:
        return {"ok": False, "error": "user_not_found"}

    db = await get_db()
    coins = int(user["coins"])

    if upgrade_type == "plot":
        if int(user.get("extra_plots") or 0) >= max_extra_plots():
            return {"ok": False, "error": "max_level"}
        if coins < PLOT_PRICE:
            return {"ok": False, "error": "not_enough_coins"}
        await db.execute(
            "UPDATE users SET coins = coins - ?, extra_plots = extra_plots + 1 WHERE id = ?",
            (PLOT_PRICE, user_id),
        )
    elif upgrade_type == "speed":
        level = int(user.get("speed_level") or 0)
        if level >= SPEED_MAX:
            return {"ok": False, "error": "max_level"}
        price = SPEED_PRICES[level]
        if coins < price:
            return {"ok": False, "error": "not_enough_coins"}
        await db.execute(
            "UPDATE users SET coins = coins - ?, speed_level = speed_level + 1 WHERE id = ?",
            (price, user_id),
        )
    elif upgrade_type == "water_can":
        level = int(user.get("water_can_level") or 0)
        if level >= WATER_CAN_MAX:
            return {"ok": False, "error": "max_level"}
        price = WATER_CAN_PRICES[level]
        if coins < price:
            return {"ok": False, "error": "not_enough_coins"}
        await db.execute(
            "UPDATE users SET coins = coins - ?, water_can_level = water_can_level + 1 WHERE id = ?",
            (price, user_id),
        )
    else:
        return {"ok": False, "error": "unknown_upgrade"}

    await db.commit()
    updated = await get_user_by_id(user_id)
    assert updated is not None
    settings = get_settings()
    return {
        "ok": True,
        "coins": updated["coins"],
        "upgrades": build_upgrades_info(updated, settings),
        "shop": build_shop_state(updated),
    }


def build_display_name(tg_user: dict) -> str:
    first = (tg_user.get("first_name") or "").strip()
    last = (tg_user.get("last_name") or "").strip()
    name = f"{first} {last}".strip()
    if name:
        return name
    uname = tg_user.get("username")
    if uname:
        return f"@{uname}"
    return f"Игрок {tg_user.get('id', '')}"


async def sync_user_profile(
    telegram_id: int,
    username: str | None,
    display_name: str,
) -> None:
    db = await get_db()
    cur = await db.execute(
        "SELECT username, display_name FROM users WHERE telegram_id = ?",
        (telegram_id,),
    )
    row = await cur.fetchone()
    if not row:
        return
    if row["username"] == username and row["display_name"] == display_name:
        return
    await db.execute(
        "UPDATE users SET username = ?, display_name = ? WHERE telegram_id = ?",
        (username, display_name, telegram_id),
    )
    await db.commit()


async def get_or_create_user(
    telegram_id: int,
    username: str | None,
    referrer_telegram_id: int | None = None,
    display_name: str | None = None,
) -> tuple[dict, bool]:
    """Returns (user, is_new)."""
    existing = await get_user_by_telegram(telegram_id)
    if existing:
        if display_name:
            await sync_user_profile(telegram_id, username, display_name)
            existing["username"] = username
            existing["display_name"] = display_name
        return existing, False

    db = await get_db()
    settings = get_settings()
    referrer_db_id: int | None = None
    bonus_coins = 0

    if referrer_telegram_id and referrer_telegram_id != telegram_id:
        ref = await get_user_by_telegram(referrer_telegram_id)
        if ref:
            referrer_db_id = ref["id"]
            bonus_coins = settings.new_user_bonus
            await db.execute(
                "UPDATE users SET coins = coins + ? WHERE id = ?",
                (settings.referrer_bonus, referrer_db_id),
            )

    cur = await db.execute(
        "INSERT INTO users (telegram_id, username, display_name, referrer_id, coins, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (telegram_id, username, display_name or username, referrer_db_id, bonus_coins, NOW()),
    )
    user_id = cur.lastrowid
    await db.commit()

    user = await get_user_by_telegram(telegram_id)
    assert user is not None
    return user, True


async def get_growing_plants(user_id: int) -> list[dict]:
    db = await get_db()
    cur = await db.execute(
        "SELECT id, user_id, status, rarity, background_id, plant_variant_id, "
        "planted_in_portal, planted_at, ready_at, plot_slot "
        "FROM plants WHERE user_id = ? AND status = 'growing' ORDER BY plot_slot",
        (user_id,),
    )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_growing_plant(user_id: int) -> dict | None:
    plants = await get_growing_plants(user_id)
    return plants[0] if plants else None


async def get_growing_plant_by_id(user_id: int, plant_id: int) -> dict | None:
    db = await get_db()
    cur = await db.execute(
        "SELECT id, user_id, status, rarity, background_id, plant_variant_id, "
        "planted_in_portal, planted_at, ready_at, plot_slot "
        "FROM plants WHERE user_id = ? AND id = ? AND status = 'growing'",
        (user_id, plant_id),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def get_ready_plants(user_id: int) -> list[dict]:
    db = await get_db()
    cur = await db.execute(
        "SELECT id, user_id, status, rarity, background_id, plant_variant_id, "
        "planted_in_portal, planted_at, ready_at, plot_slot "
        "FROM plants WHERE user_id = ? AND status = 'ready' ORDER BY ready_at DESC",
        (user_id,),
    )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def plant_seed(user_id: int, plot_slot: int = 1) -> dict | None:
    """Plant a seed on a plot slot if it's free."""
    user = await get_user_by_id(user_id)
    if not user:
        return None
    if plot_slot < 1 or plot_slot > plot_count(user):
        return None

    db = await get_db()
    cur = await db.execute(
        "SELECT id FROM plants WHERE user_id = ? AND plot_slot = ? AND status = 'growing'",
        (user_id, plot_slot),
    )
    if await cur.fetchone():
        return None

    settings = get_settings()
    now = NOW()
    ready_at = now + growth_duration_for_user(settings, user)

    planted_in_portal = int(user.get("portal_dimension") or 0)
    cur = await db.execute(
        "INSERT INTO plants (user_id, status, planted_at, ready_at, plot_slot, "
        "planted_in_portal) VALUES (?, 'growing', ?, ?, ?, ?)",
        (user_id, now, ready_at, plot_slot, planted_in_portal),
    )
    await db.commit()
    return {
        "id": cur.lastrowid,
        "user_id": user_id,
        "status": "growing",
        "rarity": None,
        "background_id": None,
        "plant_variant_id": None,
        "planted_in_portal": planted_in_portal,
        "planted_at": now,
        "ready_at": ready_at,
        "plot_slot": plot_slot,
    }


async def finalize_ready_plants(user_id: int) -> list[dict]:
    """Finalize all growing plants whose time has elapsed."""
    db = await get_db()
    now = NOW()
    cur = await db.execute(
        "SELECT id, user_id, status, rarity, background_id, plant_variant_id, "
        "planted_in_portal, planted_at, ready_at, plot_slot "
        "FROM plants WHERE user_id = ? AND status = 'growing' AND ready_at <= ?",
        (user_id, now),
    )
    plants = [dict(r) for r in await cur.fetchall()]
    if not plants:
        return []

    for plant in plants:
        rarity = roll_rarity()
        in_portal = bool(int(plant.get("planted_in_portal") or 0))
        if in_portal:
            variant_id = roll_space_variant_for_rarity(rarity)
            bg = roll_background(in_portal=True)
        else:
            variant_id = roll_variant_for_rarity(rarity)
            bg = roll_background(in_portal=False)
        await db.execute(
            "UPDATE plants SET status = 'ready', rarity = ?, background_id = ?, "
            "plant_variant_id = ? WHERE id = ?",
            (rarity, bg, variant_id, plant["id"]),
        )
        plant["status"] = "ready"
        plant["rarity"] = rarity
        plant["background_id"] = bg
        plant["plant_variant_id"] = variant_id
    await increment_global_grown(len(plants))
    await db.commit()
    return plants


async def get_friend_growing_plant(owner_telegram_id: int) -> dict | None:
    owner = await get_user_by_telegram(owner_telegram_id)
    if not owner:
        return None
    plant = await get_growing_plant(owner["id"])
    if not plant:
        return None
    plant["owner_telegram_id"] = owner_telegram_id
    plant["owner_username"] = owner.get("username")
    plant["owner_display_name"] = owner.get("display_name") or owner.get("username")
    return plant


async def can_water_friend_plant(waterer_id: int, plant_id: int) -> tuple[bool, int]:
    """Once per day per friend's plant."""
    db = await get_db()
    settings = get_settings()
    cur = await db.execute(
        "SELECT watered_at FROM waterings WHERE waterer_id = ? AND plant_id = ? "
        "ORDER BY watered_at DESC LIMIT 1",
        (waterer_id, plant_id),
    )
    row = await cur.fetchone()
    if not row:
        return True, 0
    last = row["watered_at"] if isinstance(row, dict) else row[0]
    elapsed = NOW() - int(last)
    if elapsed < settings.water_cooldown:
        return False, settings.water_cooldown - elapsed
    return True, 0


async def get_self_water_status(user_id: int) -> dict:
    settings = get_settings()
    db = await get_db()
    cur = await db.execute(
        "SELECT MAX(watered_at) as last FROM self_waterings WHERE user_id = ?",
        (user_id,),
    )
    row = await cur.fetchone()
    last = row["last"] if row and row["last"] else 0
    elapsed = NOW() - last
    cooldown = settings.self_water_cooldown
    if elapsed < cooldown:
        return {"can_water": False, "wait_seconds": cooldown - elapsed}
    return {"can_water": True, "wait_seconds": 0}


async def water_own_plant(user_id: int, plant_id: int) -> dict:
    settings = get_settings()
    user = await get_user_by_id(user_id)
    if not user:
        return {"ok": False, "error": "user_not_found"}

    plant = await get_growing_plant_by_id(user_id, plant_id)
    if not plant:
        return {"ok": False, "error": "plant_not_found"}

    status = await get_self_water_status(user_id)
    if not status["can_water"]:
        return {
            "ok": False,
            "error": "cooldown",
            "wait_seconds": status["wait_seconds"],
        }

    now = NOW()
    remaining_sec = max(0, plant["ready_at"] - now)
    if remaining_sec <= 0:
        return {"ok": False, "error": "already_ready"}

    saved = min(remaining_sec, self_water_seconds(settings, user))
    new_ready = max(now, plant["ready_at"] - saved)

    db = await get_db()
    await db.execute(
        "INSERT INTO self_waterings (plant_id, user_id, watered_at) VALUES (?, ?, ?)",
        (plant_id, user_id, now),
    )
    await db.execute(
        "UPDATE plants SET ready_at = ? WHERE id = ?",
        (new_ready, plant_id),
    )
    await db.commit()

    return {
        "ok": True,
        "new_ready_at": new_ready,
        "time_saved": saved,
        "reduction_seconds": saved,
    }


async def water_plant(
    waterer_id: int,
    plant_id: int,
    owner_user_id: int,
) -> dict:
    """Water a friend's plant. Returns result dict."""
    settings = get_settings()

    if waterer_id == owner_user_id:
        return {"ok": False, "error": "cannot_water_own"}

    plant = await get_growing_plant_by_id(owner_user_id, plant_id)
    if not plant:
        return {"ok": False, "error": "plant_not_found"}

    can, wait = await can_water_friend_plant(waterer_id, plant_id)
    if not can:
        return {"ok": False, "error": "cooldown", "wait_seconds": wait}

    db = await get_db()
    now = NOW()
    new_ready = max(now, plant["ready_at"] - settings.water_time_reduction)

    await db.execute(
        "INSERT INTO waterings (plant_id, waterer_id, watered_at) VALUES (?, ?, ?)",
        (plant_id, waterer_id, now),
    )
    await db.execute(
        "UPDATE plants SET ready_at = ? WHERE id = ?",
        (new_ready, plant_id),
    )
    await db.commit()

    return {
        "ok": True,
        "new_ready_at": new_ready,
        "time_saved": settings.water_time_reduction,
    }


async def get_user_stats(user_id: int) -> dict:
    db = await get_db()
    cur = await db.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM users WHERE referrer_id = ?) AS referrals,
            (SELECT COUNT(*) FROM waterings WHERE waterer_id = ?) AS waterings
        """,
        (user_id, user_id),
    )
    row = await cur.fetchone()
    return {"referrals": row["referrals"], "waterings": row["waterings"]}


async def get_global_growth_window(now_ts: int | None = None) -> dict:
    """Totals for smooth local interpolation on the client."""
    now_ts = now_ts or NOW()
    current_hour = now_ts - (now_ts % 3600)
    next_hour = current_hour + 3600
    total = await get_global_grown_total()
    return {
        "window_start": current_hour,
        "window_end": next_hour,
        "from_count": total,
        "to_count": total,
    }


LEADERBOARD_HOUR_KEY = "leaderboard_hour"
LEADERBOARD_JSON_KEY = "leaderboard_json"


async def _compute_leaderboard_top10() -> list[dict]:
    db = await get_db()
    cur = await db.execute(
        "SELECT user_id, rarity, background_id, plant_variant_id FROM plants WHERE status = 'ready'"
    )
    rows = await cur.fetchall()
    values: dict[int, int] = {}
    counts: dict[int, int] = {}
    for row in rows:
        uid = int(row["user_id"])
        price = plant_market_price(
            row.get("rarity"),
            row.get("background_id"),
            row.get("plant_variant_id"),
        )
        values[uid] = values.get(uid, 0) + price
        counts[uid] = counts.get(uid, 0) + 1

    ranked = sorted(values.items(), key=lambda x: x[1], reverse=True)[:10]
    entries: list[dict] = []
    for rank, (uid, garden_value) in enumerate(ranked, start=1):
        user = await get_user_by_id(uid)
        if not user:
            continue
        entries.append(
            {
                "rank": rank,
                "display_name": user.get("display_name") or "Садовник",
                "username": user.get("username"),
                "garden_value": garden_value,
                "plant_count": counts.get(uid, 0),
            }
        )
    return entries


async def get_leaderboard(now_ts: int | None = None) -> dict:
    now_ts = now_ts or NOW()
    hour_start = now_ts - (now_ts % 3600)
    next_update = hour_start + 3600

    cached_hour = await get_app_setting(LEADERBOARD_HOUR_KEY)
    if cached_hour == str(hour_start):
        raw = await get_app_setting(LEADERBOARD_JSON_KEY)
        if raw:
            return {
                "updated_at": hour_start,
                "next_update_at": next_update,
                "entries": json.loads(raw),
            }

    entries = await _compute_leaderboard_top10()
    await _upsert_setting(LEADERBOARD_HOUR_KEY, str(hour_start))
    await _upsert_setting(LEADERBOARD_JSON_KEY, json.dumps(entries, ensure_ascii=False))
    return {
        "updated_at": hour_start,
        "next_update_at": next_update,
        "entries": entries,
    }


async def admin_grant_all_plants(telegram_id: int) -> tuple[int, str | None]:
    """Admin: выдать по одному экземпляру каждого из 13 растений."""
    user = await get_user_by_telegram(telegram_id)
    if not user:
        return 0, "no_user"

    db = await get_db()
    now = NOW()
    for variant_id in ALL_VARIANT_IDS:
        rarity = rarity_for_variant(variant_id)
        bg = roll_background()
        await db.execute(
            "INSERT INTO plants (user_id, status, rarity, background_id, "
            "plant_variant_id, planted_at, ready_at, plot_slot) "
            "VALUES (?, 'ready', ?, ?, ?, ?, ?, 0)",
            (user["id"], rarity, bg, variant_id, now, now),
        )
    await db.commit()
    return len(ALL_VARIANT_IDS), None


async def toggle_portal_dimension(user_id: int) -> bool:
    db = await get_db()
    cur = await db.execute(
        "SELECT portal_dimension FROM users WHERE id = ?",
        (user_id,),
    )
    row = await cur.fetchone()
    if not row:
        return False
    current = int(
        row["portal_dimension"] if isinstance(row, dict) else row[0] or 0
    )
    new_val = 0 if current else 1
    await db.execute(
        "UPDATE users SET portal_dimension = ? WHERE id = ?",
        (new_val, user_id),
    )
    await db.commit()
    return bool(new_val)
