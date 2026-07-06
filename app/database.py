import aiosqlite
from pathlib import Path

from app.config import get_settings

_db: aiosqlite.Connection | None = None

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-8000;
PRAGMA temp_store=MEMORY;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    referrer_id INTEGER REFERENCES users(id),
    coins INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id);

CREATE TABLE IF NOT EXISTS plants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'growing',
    rarity TEXT,
    background_id INTEGER,
    planted_at INTEGER NOT NULL,
    ready_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plants_user ON plants(user_id);
CREATE INDEX IF NOT EXISTS idx_plants_status ON plants(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_growing ON plants(user_id) WHERE status = 'growing';

CREATE TABLE IF NOT EXISTS waterings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_id INTEGER NOT NULL REFERENCES plants(id),
    waterer_id INTEGER NOT NULL REFERENCES users(id),
    watered_at INTEGER NOT NULL,
    UNIQUE(plant_id, waterer_id, watered_at)
);
CREATE INDEX IF NOT EXISTS idx_waterings_plant ON waterings(plant_id);
CREATE INDEX IF NOT EXISTS idx_waterings_waterer ON waterings(waterer_id, watered_at);

CREATE TABLE IF NOT EXISTS self_waterings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_id INTEGER NOT NULL REFERENCES plants(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    watered_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_self_water_user ON self_waterings(user_id, watered_at);
"""


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        settings = get_settings()
        Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
        _db = await aiosqlite.connect(settings.db_path)
        _db.row_factory = aiosqlite.Row
        await _db.executescript(SCHEMA)
        await _db.commit()
        for sql in (
            "ALTER TABLE users ADD COLUMN display_name TEXT",
        ):
            try:
                await _db.execute(sql)
                await _db.commit()
            except Exception:
                pass
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None
