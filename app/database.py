from pathlib import Path
from typing import Any

import aiosqlite

from app.config import get_settings

_db: Any = None
_pool = None
_backend: str = "sqlite"

SCHEMA_VERSION = 2

SQLITE_SCHEMA = """
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
CREATE INDEX IF NOT EXISTS idx_plants_ready_at ON plants(ready_at);

CREATE TABLE IF NOT EXISTS waterings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_id INTEGER NOT NULL REFERENCES plants(id),
    waterer_id INTEGER NOT NULL REFERENCES users(id),
    watered_at INTEGER NOT NULL
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

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    referrer_id INTEGER REFERENCES users(id),
    coins INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id);

CREATE TABLE IF NOT EXISTS plants (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'growing',
    rarity TEXT,
    background_id INTEGER,
    planted_at INTEGER NOT NULL,
    ready_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plants_user ON plants(user_id);
CREATE INDEX IF NOT EXISTS idx_plants_status ON plants(status);
CREATE INDEX IF NOT EXISTS idx_plants_ready_at ON plants(ready_at);

CREATE TABLE IF NOT EXISTS waterings (
    id SERIAL PRIMARY KEY,
    plant_id INTEGER NOT NULL REFERENCES plants(id),
    waterer_id INTEGER NOT NULL REFERENCES users(id),
    watered_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_waterings_plant ON waterings(plant_id);
CREATE INDEX IF NOT EXISTS idx_waterings_waterer ON waterings(waterer_id, watered_at);

CREATE TABLE IF NOT EXISTS self_waterings (
    id SERIAL PRIMARY KEY,
    plant_id INTEGER NOT NULL REFERENCES plants(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    watered_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_self_water_user ON self_waterings(user_id, watered_at);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_MIGRATIONS = (
    "ALTER TABLE users ADD COLUMN display_name TEXT",
    "ALTER TABLE users ADD COLUMN extra_plots INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN speed_level INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN water_can_level INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE plants ADD COLUMN plot_slot INTEGER NOT NULL DEFAULT 1",
)


class CursorResult:
    def __init__(self, rows: list[Any], lastrowid: int | None = None):
        self._rows = rows
        self.lastrowid = lastrowid

    async def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    async def fetchall(self) -> list[Any]:
        return self._rows


class SqliteDatabase:
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def executescript(self, sql: str) -> None:
        await self._conn.executescript(sql)
        await self._conn.commit()

    async def execute(self, sql: str, params: tuple = ()) -> CursorResult:
        cur = await self._conn.execute(sql, params)
        if sql.strip().upper().startswith("SELECT"):
            rows = await cur.fetchall()
            return CursorResult(rows)
        return CursorResult([], cur.lastrowid)

    async def commit(self) -> None:
        await self._conn.commit()

    async def close(self) -> None:
        await self._conn.close()


class PostgresDatabase:
    def __init__(self, pool):
        self._pool = pool

    async def executescript(self, sql: str) -> None:
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        async with self._pool.acquire() as conn:
            for stmt in statements:
                await conn.execute(stmt)

    async def execute(self, sql: str, params: tuple = ()) -> CursorResult:
        pg_sql = _to_pg_sql(sql)
        upper = pg_sql.strip().upper()
        is_insert = upper.startswith("INSERT") and "RETURNING" not in upper
        if is_insert:
            pg_sql = pg_sql.rstrip().rstrip(";") + " RETURNING id"

        async with self._pool.acquire() as conn:
            if is_insert:
                row = await conn.fetchrow(pg_sql, *params)
                lastrowid = row["id"] if row else None
                return CursorResult([], lastrowid)
            if upper.startswith("SELECT") or " RETURNING " in upper:
                rows = await conn.fetch(pg_sql, *params)
                lastrowid = rows[0]["id"] if rows and "id" in rows[0] else None
                return CursorResult([dict(r) for r in rows], lastrowid)
            await conn.execute(pg_sql, *params)
            return CursorResult([])

    async def commit(self) -> None:
        return None

    async def close(self) -> None:
        await self._pool.close()


def _to_pg_sql(sql: str) -> str:
    out: list[str] = []
    idx = 0
    for ch in sql:
        if ch == "?":
            idx += 1
            out.append(f"${idx}")
        else:
            out.append(ch)
    return "".join(out)


def _normalize_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


async def _run_sqlite_migrations(db: SqliteDatabase) -> None:
    for sql in _MIGRATIONS:
        try:
            await db.execute(sql)
            await db.commit()
        except Exception:
            pass
    await db.execute("DROP INDEX IF EXISTS idx_one_growing")
    try:
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_one_growing_slot "
            "ON plants(user_id, plot_slot) WHERE status = 'growing'"
        )
    except Exception:
        pass
    await db.commit()


async def _ensure_app_settings(db: Any) -> None:
    if _backend == "sqlite":
        await db.execute(
            "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        await db.commit()


async def reset_all_data(db: Any) -> None:
    tables = ("self_waterings", "waterings", "plants", "users", "app_settings")
    if _backend == "postgres":
        async with db._pool.acquire() as conn:
            await conn.execute(
                "TRUNCATE self_waterings, waterings, plants, users, app_settings "
                "RESTART IDENTITY CASCADE"
            )
    else:
        for table in tables:
            await db.execute(f"DELETE FROM {table}")
        try:
            await db.execute(
                "DELETE FROM sqlite_sequence WHERE name IN ('users','plants','waterings','self_waterings')"
            )
        except Exception:
            pass
        await db.commit()


async def _maybe_migrate_schema(db: Any) -> None:
    settings = get_settings()
    await _ensure_app_settings(db)

    cur = await db.execute(
        "SELECT value FROM app_settings WHERE key = ?", ("schema_version",)
    )
    row = await cur.fetchone()
    current = int(row["value"]) if row else 0

    if settings.reset_db or current < SCHEMA_VERSION:
        await reset_all_data(db)
        await db.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        await db.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            ("global_grown_total", "0"),
        )
        await db.commit()


async def get_db() -> Any:
    global _db, _pool, _backend
    if _db is not None:
        return _db

    settings = get_settings()
    db_url = _normalize_url(settings.database_url.strip())

    if db_url.startswith("postgresql://"):
        import asyncpg

        _backend = "postgres"
        _pool = await asyncpg.create_pool(db_url, min_size=1, max_size=10)
        _db = PostgresDatabase(_pool)
        await _db.executescript(PG_SCHEMA)
        for sql in _MIGRATIONS:
            try:
                await _db.execute(sql.replace("INTEGER NOT NULL DEFAULT", "INTEGER DEFAULT"))
                await _db.commit()
            except Exception:
                pass
        try:
            await _db.execute("DROP INDEX IF EXISTS idx_one_growing")
            await _db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_one_growing_slot "
                "ON plants(user_id, plot_slot) WHERE status = 'growing'"
            )
        except Exception:
            pass
    else:
        _backend = "sqlite"
        Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(settings.db_path)
        conn.row_factory = aiosqlite.Row
        _db = SqliteDatabase(conn)
        await _db.executescript(SQLITE_SCHEMA)
        await _run_sqlite_migrations(_db)

    await _maybe_migrate_schema(_db)
    return _db


async def close_db() -> None:
    global _db, _pool, _backend
    if _db is not None:
        await _db.close()
        _db = None
        _pool = None
        _backend = "sqlite"
