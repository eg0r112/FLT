"""Каталог из 13 растений: редкость, порядок цены, картинки."""

from __future__ import annotations

import random

# Слева дешевле → справа дороже; группы — редкость.
PRICE_ORDER: tuple[int, ...] = (13, 3, 9, 10, 11, 8, 6, 5, 4, 2, 1, 12, 7)

VARIANT_BY_RARITY: dict[str, tuple[int, ...]] = {
    "common": (13, 3, 9, 10),
    "uncommon": (11, 8, 6),
    "rare": (5, 4),
    "epic": (2, 1),
    "legendary": (12, 7),
}

VARIANT_RARITY: dict[int, str] = {
    vid: rarity for rarity, ids in VARIANT_BY_RARITY.items() for vid in ids
}

ALL_VARIANT_IDS: tuple[int, ...] = PRICE_ORDER

_PRICE_INDEX = {vid: i for i, vid in enumerate(PRICE_ORDER)}


def variant_price_mult(variant_id: int | None) -> float:
    if not variant_id:
        return 1.0
    idx = _PRICE_INDEX.get(int(variant_id), 0)
    return 1.0 + idx * (0.45 / max(1, len(PRICE_ORDER) - 1))


def roll_variant_for_rarity(rarity: str) -> int:
    pool = VARIANT_BY_RARITY.get(rarity, VARIANT_BY_RARITY["common"])
    return random.choice(pool)


def rarity_for_variant(variant_id: int) -> str:
    return VARIANT_RARITY.get(int(variant_id), "common")
