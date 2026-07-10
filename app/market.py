"""Рыночная цена растений (как в static/app.js)."""

RARITY_MARKET: dict[str, dict[str, float | int]] = {
    "common": {"weight": 60, "base": 18},
    "uncommon": {"weight": 25, "base": 45},
    "rare": {"weight": 10, "base": 120},
    "epic": {"weight": 4, "base": 340},
    "legendary": {"weight": 1, "base": 1200},
}

COSMIC_BACKGROUND_ID = 11

BACKGROUND_MARKET: dict[int, dict[str, float | int]] = {
    1: {"weight": 22, "mult": 1.0},
    2: {"weight": 18, "mult": 1.08},
    3: {"weight": 15, "mult": 1.15},
    4: {"weight": 11, "mult": 1.28},
    5: {"weight": 10, "mult": 1.42},
    6: {"weight": 8, "mult": 1.6},
    7: {"weight": 6, "mult": 1.9},
    8: {"weight": 4, "mult": 2.4},
    9: {"weight": 3, "mult": 3.0},
    10: {"weight": 2, "mult": 3.8},
    11: {"weight": 1, "mult": 8.0},
}


def plant_market_price(
    rarity: str | None,
    background_id: int | None,
    variant_id: int | None = None,
) -> int:
    from app.plants import (
        is_space_variant,
        space_market_rarity,
        space_price_extra_mult,
        variant_price_mult,
    )

    eff_rarity = rarity or "common"
    if is_space_variant(variant_id):
        eff_rarity = space_market_rarity(eff_rarity)
    r = RARITY_MARKET.get(eff_rarity, RARITY_MARKET["common"])
    bg = BACKGROUND_MARKET.get(int(background_id or 1), BACKGROUND_MARKET[1])
    rarity_scarcity = 60 / float(r["weight"])
    bg_scarcity = 22 / float(bg["weight"])
    combo_boost = (rarity_scarcity * bg_scarcity) ** 0.38
    return round(
        float(r["base"])
        * float(bg["mult"])
        * combo_boost
        * variant_price_mult(variant_id)
        * space_price_extra_mult(rarity or "common", variant_id)
    )
