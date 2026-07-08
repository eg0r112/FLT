"""Готовый фон карточки в стиле TG Gifts: градиент + редкий watermark."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(
    r"C:\Users\Sasha\.cursor\projects\c-Users-Sasha-Desktop-FLT\assets"
)
OUT = ROOT / "static" / "images" / "bg"

CARD_W = 400
CARD_H = 520
ICON_SIZE = 30
ICON_ALPHA = 0.13

# Редкая сетка — много пустого места между иконками
ICON_POSITIONS = [
    (0.12, 0.10),
    (0.48, 0.07),
    (0.82, 0.14),
    (0.22, 0.28),
    (0.68, 0.24),
    (0.08, 0.46),
    (0.42, 0.42),
    (0.78, 0.40),
    (0.28, 0.58),
    (0.62, 0.55),
    (0.88, 0.62),
    (0.15, 0.74),
    (0.52, 0.72),
    (0.76, 0.80),
    (0.35, 0.90),
    (0.65, 0.92),
]

SOURCES = [
    ("c__Users_Sasha_AppData_Roaming_Cursor_User_workspaceStorage_60881873690c70cde651f6904c1c35a2_images_image-fbf4a93e-d9ec-4a33-9e38-da16ecc1d779.png", 1, "Алмаз"),
    ("c__Users_Sasha_AppData_Roaming_Cursor_User_workspaceStorage_60881873690c70cde651f6904c1c35a2_images_image-6e9393b6-331f-4f55-9c1f-52322e89202a.png", 2, "Лапка"),
    ("c__Users_Sasha_AppData_Roaming_Cursor_User_workspaceStorage_60881873690c70cde651f6904c1c35a2_images_image-0a3446fd-1df1-4ab0-94d5-cec5a0235e2b.png", 3, "Зверь"),
    ("c__Users_Sasha_AppData_Roaming_Cursor_User_workspaceStorage_60881873690c70cde651f6904c1c35a2_images_image-6d275f16-9142-4005-84cd-8aa3c5e683c8.png", 4, "Горшок"),
    ("c__Users_Sasha_AppData_Roaming_Cursor_User_workspaceStorage_60881873690c70cde651f6904c1c35a2_images_image-ad54f65e-08f9-4662-9bb4-2e5a4db2d1ff.png", 5, "Сердце"),
    ("c__Users_Sasha_AppData_Roaming_Cursor_User_workspaceStorage_60881873690c70cde651f6904c1c35a2_images_image-c4068205-dc8c-4dd1-b486-ac33fd0e14be.png", 6, "Лист"),
    ("c__Users_Sasha_AppData_Roaming_Cursor_User_workspaceStorage_60881873690c70cde651f6904c1c35a2_images_image-cee21446-702a-4efc-969b-5a73420d1174.png", 7, "Бабочка"),
    ("c__Users_Sasha_AppData_Roaming_Cursor_User_workspaceStorage_60881873690c70cde651f6904c1c35a2_images_image-bdfb0932-3c7c-4198-a3b1-28def39c6085.png", 8, "Инь-ян"),
    ("c__Users_Sasha_AppData_Roaming_Cursor_User_workspaceStorage_60881873690c70cde651f6904c1c35a2_images_image-ce95f21d-c085-4b0a-bc04-4050a9280306.png", 9, "Кубок"),
    ("c__Users_Sasha_AppData_Roaming_Cursor_User_workspaceStorage_60881873690c70cde651f6904c1c35a2_images_image-c7ef03c5-6199-4275-81d7-76cd3b17b8c6.png", 10, "Лилия"),
]

WEIGHTS = {
    1: (22, 1.0),
    2: (18, 1.08),
    3: (15, 1.15),
    4: (11, 1.28),
    5: (10, 1.42),
    6: (8, 1.6),
    7: (6, 1.9),
    8: (4, 2.4),
    9: (3, 3.0),
    10: (2, 3.8),
}


def _hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _bg_color(im: Image.Image) -> tuple[int, int, int]:
    w, h = im.size
    pts = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    rs, gs, bs = [], [], []
    for x, y in pts:
        p = im.getpixel((x, y))
        if len(p) == 4:
            p = p[:3]
        rs.append(p[0])
        gs.append(p[1])
        bs.append(p[2])
    return int(sum(rs) / 4), int(sum(gs) / 4), int(sum(bs) / 4)


def _lighten(rgb: tuple[int, int, int], factor: float = 1.18) -> tuple[int, int, int]:
    return tuple(min(255, int(c * factor)) for c in rgb)


def _darken(rgb: tuple[int, int, int], factor: float = 0.55) -> tuple[int, int, int]:
    return tuple(max(0, int(c * factor)) for c in rgb)


def _gradient(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (CARD_W, CARD_H))
    draw = ImageDraw.Draw(img)
    for y in range(CARD_H):
        t = y / max(1, CARD_H - 1)
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line([(0, y), (CARD_W, y)], fill=color)
    return img.convert("RGBA")


def _icon_stamp(src: Image.Image) -> Image.Image:
    icon = src.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
    r, g, b, a = icon.split()
    a = a.point(lambda p: int(p * ICON_ALPHA))
    return Image.merge("RGBA", (r, g, b, a))


def make_card_bg(src: Path, dst: Path) -> tuple[str, str]:
    im = Image.open(src).convert("RGBA")
    base = _bg_color(im)
    top = _lighten(base)
    bottom = _darken(base)

    card = _gradient(top, bottom)
    stamp = _icon_stamp(im)

    for fx, fy in ICON_POSITIONS:
        x = int(fx * CARD_W - ICON_SIZE / 2)
        y = int(fy * CARD_H - ICON_SIZE / 2)
        card.paste(stamp, (x, y), stamp)

    card.save(dst, "PNG", optimize=True)
    return _hex(top), _hex(bottom)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    meta: dict[str, dict] = {}
    for fname, num, name in SOURCES:
        src = ASSETS / fname
        if not src.exists():
            raise FileNotFoundError(src)
        c1, c2 = make_card_bg(src, OUT / f"{num}.png")
        w, m = WEIGHTS[num]
        meta[str(num)] = {
            "name": name,
            "weight": w,
            "mult": m,
            "color": c1,
            "colorDark": c2,
            "image": f"{num}.png",
        }
        print(f"OK {num} {name}")

    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
