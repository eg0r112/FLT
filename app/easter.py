"""Пасхалки: одна случайная за сессию, находки в БД, админ-оверрайд по номеру."""

from __future__ import annotations

import random
import time

from app.database import get_db
from app.easter_eggs import ALL_EGG_IDS, EGG_COUNT, get_egg
from app.services import get_app_setting, _upsert_setting

NOW = lambda: int(time.time())

_OVERRIDE_PREFIX = "easter_egg_override:"


def _override_key(telegram_id: int) -> str:
    return f"{_OVERRIDE_PREFIX}{telegram_id}"


async def set_admin_egg_override(telegram_id: int, egg_id: int) -> dict | None:
    egg = get_egg(egg_id)
    if not egg:
        return None
    await _upsert_setting(_override_key(telegram_id), str(egg_id))
    return egg


async def _pop_admin_override(telegram_id: int) -> int | None:
    key = _override_key(telegram_id)
    raw = await get_app_setting(key)
    if not raw:
        return None
    await _upsert_setting(key, "")
    try:
        egg_id = int(raw)
    except ValueError:
        return None
    if egg_id < 1 or egg_id > EGG_COUNT:
        return None
    return egg_id


async def get_found_egg_ids(user_id: int) -> set[int]:
    db = await get_db()
    cur = await db.execute(
        "SELECT egg_id FROM easter_egg_finds WHERE user_id = ?",
        (user_id,),
    )
    rows = await cur.fetchall()
    return {int(r["egg_id"] if isinstance(r, dict) else r[0]) for r in rows}


async def _get_stored_active(user_id: int) -> int | None:
    db = await get_db()
    cur = await db.execute(
        "SELECT egg_id FROM easter_egg_active WHERE user_id = ?",
        (user_id,),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return int(row["egg_id"] if isinstance(row, dict) else row[0])


async def _set_active(user_id: int, egg_id: int) -> None:
    db = await get_db()
    now = NOW()
    await db.execute(
        "INSERT INTO easter_egg_active (user_id, egg_id, assigned_at) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET egg_id = excluded.egg_id, "
        "assigned_at = excluded.assigned_at",
        (user_id, egg_id, now),
    )
    await db.commit()


async def _clear_active(user_id: int) -> None:
    db = await get_db()
    await db.execute("DELETE FROM easter_egg_active WHERE user_id = ?", (user_id,))
    await db.commit()


async def get_active_easter_egg(
    user_id: int,
    telegram_id: int,
    *,
    is_admin: bool = False,
    fresh_session: bool = False,
) -> dict | None:
    if is_admin:
        override_id = await _pop_admin_override(telegram_id)
        if override_id is not None:
            await _set_active(user_id, override_id)
            egg = get_egg(override_id)
            return dict(egg) if egg else None

    if fresh_session:
        picked = random.choice(list(ALL_EGG_IDS))
        await _set_active(user_id, picked)
        egg = get_egg(picked)
        return dict(egg) if egg else None

    active_id = await _get_stored_active(user_id)
    if active_id is not None:
        egg = get_egg(active_id)
        if egg:
            return dict(egg)
        await _clear_active(user_id)

    picked = random.choice(list(ALL_EGG_IDS))
    await _set_active(user_id, picked)
    egg = get_egg(picked)
    return dict(egg) if egg else None


async def claim_easter_egg(user_id: int, egg_id: int) -> dict:
    active_id = await _get_stored_active(user_id)
    if active_id is None or int(egg_id) != int(active_id):
        return {"ok": False, "error": "not_active"}

    egg = get_egg(egg_id)
    if not egg:
        return {"ok": False, "error": "unknown_egg"}

    found_before = await get_found_egg_ids(user_id)
    already_found = int(egg_id) in found_before

    if not already_found:
        db = await get_db()
        now = NOW()
        try:
            await db.execute(
                "INSERT INTO easter_egg_finds (user_id, egg_id, found_at) VALUES (?, ?, ?)",
                (user_id, egg_id, now),
            )
            await db.commit()
        except Exception:
            already_found = True

    found = await get_found_egg_ids(user_id)
    achievement_unlocked = None
    if len(found) >= EGG_COUNT:
        from app.achievements import sync_easter_all_achievement

        achievement_unlocked = await sync_easter_all_achievement(user_id)
    return {
        "ok": True,
        "egg": egg,
        "found_total": len(found),
        "total": EGG_COUNT,
        "already_found": already_found,
        "achievement_unlocked": achievement_unlocked,
    }

