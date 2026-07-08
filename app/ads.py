import time
from typing import Any

from app.config import Settings, get_settings
from app.database import get_db
from app.services import get_user_by_id, get_user_by_telegram

NOW = lambda: int(time.time())


def is_admin(telegram_id: int, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return telegram_id == settings.admin_telegram_id


async def _admin_user_id() -> int | None:
    settings = get_settings()
    user = await get_user_by_telegram(settings.admin_telegram_id)
    return int(user["id"]) if user else None


async def get_or_create_conversation(user_id: int) -> dict:
    db = await get_db()
    cur = await db.execute(
        "SELECT id, user_id, blocked, created_at, updated_at, admin_last_read_at "
        "FROM ad_conversations WHERE user_id = ?",
        (user_id,),
    )
    row = await cur.fetchone()
    if row:
        return dict(row)

    now = NOW()
    cur = await db.execute(
        "INSERT INTO ad_conversations (user_id, blocked, created_at, updated_at, admin_last_read_at) "
        "VALUES (?, 0, ?, ?, 0)",
        (user_id, now, now),
    )
    await db.commit()
    conv_id = cur.lastrowid
    return {
        "id": conv_id,
        "user_id": user_id,
        "blocked": 0,
        "created_at": now,
        "updated_at": now,
        "admin_last_read_at": 0,
    }


async def count_admin_unread() -> int:
    admin_id = await _admin_user_id()
    if not admin_id:
        return 0
    db = await get_db()
    cur = await db.execute(
        """
        SELECT COUNT(*) AS c FROM ad_messages m
        JOIN ad_conversations c ON c.id = m.conversation_id
        WHERE m.from_user_id != ?
          AND m.created_at > c.admin_last_read_at
        """,
        (admin_id,),
    )
    row = await cur.fetchone()
    return int(row["c"] if isinstance(row, dict) else row[0])


async def list_admin_inbox() -> list[dict]:
    admin_id = await _admin_user_id()
    db = await get_db()
    if admin_id:
        cur = await db.execute(
            """
            SELECT c.id, c.user_id, c.blocked, c.updated_at, c.admin_last_read_at,
                   u.display_name, u.username,
                   (
                     SELECT body FROM ad_messages
                     WHERE conversation_id = c.id
                     ORDER BY created_at DESC, id DESC LIMIT 1
                   ) AS last_body,
                   (
                     SELECT created_at FROM ad_messages
                     WHERE conversation_id = c.id
                     ORDER BY created_at DESC, id DESC LIMIT 1
                   ) AS last_at,
                   (
                     SELECT COUNT(*) FROM ad_messages m
                     WHERE m.conversation_id = c.id
                       AND m.from_user_id = c.user_id
                       AND m.created_at > c.admin_last_read_at
                   ) AS unread
            FROM ad_conversations c
            JOIN users u ON u.id = c.user_id
            WHERE c.user_id != ?
            ORDER BY c.updated_at DESC
            """,
            (admin_id,),
        )
    else:
        cur = await db.execute(
            """
            SELECT c.id, c.user_id, c.blocked, c.updated_at, c.admin_last_read_at,
                   u.display_name, u.username,
                   (
                     SELECT body FROM ad_messages
                     WHERE conversation_id = c.id
                     ORDER BY created_at DESC, id DESC LIMIT 1
                   ) AS last_body,
                   (
                     SELECT created_at FROM ad_messages
                     WHERE conversation_id = c.id
                     ORDER BY created_at DESC, id DESC LIMIT 1
                   ) AS last_at,
                   (
                     SELECT COUNT(*) FROM ad_messages m
                     WHERE m.conversation_id = c.id
                       AND m.from_user_id = c.user_id
                       AND m.created_at > c.admin_last_read_at
                   ) AS unread
            FROM ad_conversations c
            JOIN users u ON u.id = c.user_id
            ORDER BY c.updated_at DESC
            """
        )
    rows = await cur.fetchall()
    result: list[dict] = []
    for row in rows:
        item = dict(row)
        item["blocked"] = bool(item.get("blocked"))
        item["unread"] = int(item.get("unread") or 0)
        result.append(item)
    return result


async def get_user_inbox(user_id: int) -> dict:
    conv = await get_or_create_conversation(user_id)
    messages = await get_messages(conv["id"], user_id, admin=False)
    return {"conversation": conv, "messages": messages}


async def get_messages(
    conversation_id: int, viewer_user_id: int, admin: bool
) -> list[dict]:
    db = await get_db()
    cur = await db.execute(
        "SELECT id, user_id, blocked FROM ad_conversations WHERE id = ?",
        (conversation_id,),
    )
    conv = await cur.fetchone()
    if not conv:
        return []
    conv = dict(conv)
    if not admin and conv["user_id"] != viewer_user_id:
        return []

    if admin:
        await db.execute(
            "UPDATE ad_conversations SET admin_last_read_at = ? WHERE id = ?",
            (NOW(), conversation_id),
        )
        await db.commit()

    cur = await db.execute(
        """
        SELECT m.id, m.from_user_id, m.body, m.created_at,
               u.display_name, u.username
        FROM ad_messages m
        JOIN users u ON u.id = m.from_user_id
        WHERE m.conversation_id = ?
        ORDER BY m.created_at ASC, m.id ASC
        """,
        (conversation_id,),
    )
    rows = await cur.fetchall()
    admin_id = await _admin_user_id()
    out: list[dict] = []
    for row in rows:
        item = dict(row)
        item["is_mine"] = item["from_user_id"] == viewer_user_id
        item["is_admin"] = admin_id is not None and item["from_user_id"] == admin_id
        out.append(item)
    return out


async def send_message(
    from_user_id: int,
    text: str,
    *,
    is_admin_user: bool,
    conversation_id: int | None = None,
) -> dict[str, Any]:
    body = (text or "").strip()
    if not body or len(body) > 2000:
        return {"ok": False, "error": "invalid_message"}

    db = await get_db()
    admin_id = await _admin_user_id()

    if is_admin_user:
        if not conversation_id:
            return {"ok": False, "error": "conversation_required"}
        cur = await db.execute(
            "SELECT id, user_id, blocked FROM ad_conversations WHERE id = ?",
            (conversation_id,),
        )
        conv = await cur.fetchone()
        if not conv:
            return {"ok": False, "error": "not_found"}
        conv = dict(conv)
        sender_id = admin_id or from_user_id
    else:
        conv = await get_or_create_conversation(from_user_id)
        if int(conv.get("blocked") or 0):
            return {"ok": False, "error": "blocked"}
        conversation_id = int(conv["id"])
        sender_id = from_user_id

    now = NOW()
    cur = await db.execute(
        "INSERT INTO ad_messages (conversation_id, from_user_id, body, created_at) "
        "VALUES (?, ?, ?, ?)",
        (conversation_id, sender_id, body, now),
    )
    await db.execute(
        "UPDATE ad_conversations SET updated_at = ? WHERE id = ?",
        (now, conversation_id),
    )
    await db.commit()

    return {
        "ok": True,
        "message": {
            "id": cur.lastrowid,
            "from_user_id": sender_id,
            "body": body,
            "created_at": now,
            "is_mine": sender_id == from_user_id,
            "is_admin": admin_id is not None and sender_id == admin_id,
        },
    }


async def set_blocked(conversation_id: int, blocked: bool) -> dict[str, Any]:
    db = await get_db()
    cur = await db.execute(
        "UPDATE ad_conversations SET blocked = ? WHERE id = ?",
        (1 if blocked else 0, conversation_id),
    )
    await db.commit()
    if not cur.lastrowid and cur.lastrowid != 0:
        pass
    cur = await db.execute(
        "SELECT id, user_id, blocked FROM ad_conversations WHERE id = ?",
        (conversation_id,),
    )
    row = await cur.fetchone()
    if not row:
        return {"ok": False, "error": "not_found"}
    user = await get_user_by_id(row["user_id"])
    return {
        "ok": True,
        "conversation_id": conversation_id,
        "blocked": bool(row["blocked"]),
        "display_name": (user or {}).get("display_name"),
    }
