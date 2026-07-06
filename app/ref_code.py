"""Кодирование telegram_id для реферальных ссылок (без явного id)."""

from app.config import get_settings


def encode_ref(telegram_id: int) -> int:
    s = get_settings()
    return telegram_id * s.ref_mult + s.ref_add


def decode_ref(code: int) -> int | None:
    s = get_settings()
    if code < s.ref_add:
        return None
    n = code - s.ref_add
    if n % s.ref_mult != 0:
        return None
    tid = n // s.ref_mult
    return tid if tid > 0 else None


def resolve_ref(code: int) -> int | None:
    decoded = decode_ref(code)
    if decoded is not None:
        return decoded
    if get_settings().dev_mode and 0 < code < 10_000_000:
        return code
    return None


def make_ref_param(telegram_id: int) -> str:
    return f"ref_{encode_ref(telegram_id)}"
