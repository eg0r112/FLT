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
    vid = int(variant_id)
    if vid >= 101:
        return 1.0
    idx = _PRICE_INDEX.get(vid, 0)
    return 1.0 + idx * (0.45 / max(1, len(PRICE_ORDER) - 1))


def roll_variant_for_rarity(rarity: str) -> int:
    pool = VARIANT_BY_RARITY.get(rarity, VARIANT_BY_RARITY["common"])
    return random.choice(pool)


def rarity_for_variant(variant_id: int) -> str:
    vid = int(variant_id)
    if vid >= 101:
        for rarity, ids in SPACE_VARIANT_BY_RARITY.items():
            if vid in ids:
                return rarity
        return "common"
    return VARIANT_RARITY.get(vid, "common")


# Инопланетные растения (Flower_space) — id 101..106 ↔ картинки space/1..6
# Порядок ценности: 1,5 (common) · 2 (uncommon) · 6 (rare) · 4 (epic) · 3 (legendary)
SPACE_VARIANT_IDS: tuple[int, ...] = (101, 102, 103, 104, 105, 106)

SPACE_VARIANT_BY_RARITY: dict[str, tuple[int, ...]] = {
    "common": (101, 105),
    "uncommon": (102,),
    "rare": (106,),
    "epic": (104,),
    "legendary": (103,),
}

# Для цены: редкость сдвигается на ступень вверх
SPACE_PRICE_RARITY: dict[str, str] = {
    "common": "uncommon",
    "uncommon": "rare",
    "rare": "epic",
    "epic": "legendary",
    "legendary": "legendary",
}

SPACE_LEGENDARY_PRICE_MULT = 1.5


def space_market_rarity(rarity: str) -> str:
    return SPACE_PRICE_RARITY.get(rarity, rarity)


def space_price_extra_mult(rarity: str, variant_id: int | None) -> float:
    if not is_space_variant(variant_id):
        return 1.0
    if rarity == "legendary":
        return SPACE_LEGENDARY_PRICE_MULT
    return 1.0


def is_space_variant(variant_id: int | None) -> bool:
    return bool(variant_id and int(variant_id) >= 101)


def roll_space_variant_for_rarity(rarity: str) -> int:
    pool = SPACE_VARIANT_BY_RARITY.get(rarity, SPACE_VARIANT_BY_RARITY["common"])
    return random.choice(pool)
