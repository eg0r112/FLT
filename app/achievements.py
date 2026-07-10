"""Ачивки игрока."""

from __future__ import annotations

import time

from app.database import get_db
from app.easter import get_found_egg_ids
from app.easter_eggs import EGG_COUNT

NOW = lambda: int(time.time())

ACHIEVEMENTS: dict[str, dict] = {
    "easter_all": {
        "id": "easter_all",
        "title": "наконец то я собрал их всех",
        "emoji": "🏆",
        "desc": "Найти все пасхалки на полянке",
    },
}


async def get_unlocked_achievement_ids(user_id: int) -> set[str]:
    db = await get_db()
    cur = await db.execute(
        "SELECT achievement_id FROM user_achievements WHERE user_id = ?",
        (user_id,),
    )
    rows = await cur.fetchall()
    return {
        str(r["achievement_id"] if isinstance(r, dict) else r[0]) for r in rows
    }


async def get_user_achievements(user_id: int) -> list[dict]:
    unlocked = await get_unlocked_achievement_ids(user_id)
    out: list[dict] = []
    for aid, meta in ACHIEVEMENTS.items():
        out.append(
            {
                **meta,
                "unlocked": aid in unlocked,
            }
        )
    return out


async def try_unlock_achievement(user_id: int, achievement_id: str) -> dict | None:
    if achievement_id not in ACHIEVEMENTS:
        return None
    unlocked = await get_unlocked_achievement_ids(user_id)
    if achievement_id in unlocked:
        return None
    db = await get_db()
    now = NOW()
    await db.execute(
        "INSERT INTO user_achievements (user_id, achievement_id, unlocked_at) VALUES (?, ?, ?)",
        (user_id, achievement_id, now),
    )
    await db.commit()
    return {**ACHIEVEMENTS[achievement_id], "unlocked": True}


async def sync_easter_all_achievement(user_id: int) -> dict | None:
    found = await get_found_egg_ids(user_id)
    if len(found) < EGG_COUNT:
        return None
    return await try_unlock_achievement(user_id, "easter_all")
