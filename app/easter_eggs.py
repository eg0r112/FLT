"""Каталог пасхалок на полянке (37 шт). Позиции — % экрана (viewport)."""

from __future__ import annotations

import json
from pathlib import Path

EGG_COUNT = 37
_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent / "static" / "images" / "easter" / "catalog.json"
)


def _load_catalog() -> list[dict]:
    data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    if len(data) != EGG_COUNT:
        raise RuntimeError(f"Expected {EGG_COUNT} eggs in catalog.json, got {len(data)}")
    return data


EGG_CATALOG: list[dict] = _load_catalog()
EGG_BY_ID: dict[int, dict] = {e["id"]: e for e in EGG_CATALOG}
ALL_EGG_IDS: tuple[int, ...] = tuple(e["id"] for e in EGG_CATALOG)


def get_egg(egg_id: int) -> dict | None:
    return EGG_BY_ID.get(int(egg_id))
