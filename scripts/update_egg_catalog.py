import json
from pathlib import Path

entries = [
    (9, 56.6, 61.1, 112),
    (10, 57.3, 60, 128),
    (12, 54.6, 58.4, 40),
    (13, 58.2, 60.1, 60),
    (14, 61.6, 58.1, 48),
    (15, 52.4, 54.9, 48),
    (16, 62.9, 62.7, 48),
    (17, 55.6, 59.5, 64),
    (18, 53.2, 62.6, 48),
    (19, 58.6, 60.1, 60),
    (21, 57.3, 3.5, 80),
    (22, 58.8, 60.1, 48),
    (23, 58.8, 59.6, 60),
    (24, 60.5, 60.2, 64),
    (25, 55.5, 62.6, 24),
    (26, 55, 60.7, 48),
    (27, 53.9, 59.8, 64),
    (28, 61.4, 59.5, 80),
    (29, 53.8, 58.9, 112),
    (30, 58.4, 57.3, 128),
    (31, 53.9, 58.5, 48),
    (32, 56.7, 59.8, 96),
    (33, 54.5, 58.9, 56),
    (34, 55.8, 59.8, 88),
    (36, 62, 59.1, 64),
    (37, 54, 57.6, 36),
]

p = Path(__file__).resolve().parent.parent / "static/images/easter/catalog.json"
catalog = json.loads(p.read_text(encoding="utf-8"))
by_id = {e["id"]: e for e in catalog}

for eid, left, top, size in entries:
    by_id[eid].update({"left": left, "top": top, "size": size})
    by_id[eid].pop("animation", None)
    by_id[eid].pop("effect", None)

by_id[11].update(
    {
        "left": -10,
        "top": 20.8,
        "size": 52,
        "animation": {
            "type": "path",
            "loop": False,
            "hideAfter": True,
            "segments": [
                {
                    "durationMin": 30,
                    "durationMax": 40,
                    "to": {"left": 112, "top": 3.7},
                },
            ],
        },
    }
)

by_id[20].update(
    {
        "left": 70.2,
        "top": 2.1,
        "size": 48,
        "animation": {
            "type": "path",
            "loop": True,
            "segments": [
                {"duration": 8, "to": {"left": 30.3, "top": 13.7}},
                {"duration": 8, "to": {"left": 67.7, "top": 11.6}},
                {"duration": 8, "to": {"left": 70.2, "top": 2.1}},
            ],
            "clickEscape": {"top": -14, "duration": 2},
        },
    }
)

by_id[35].update(
    {
        "left": 58.8,
        "top": 59.6,
        "size": 112,
        "effect": "smoke",
    }
)

out = [by_id[i] for i in range(1, 38)]
p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("updated", len(out), "eggs")
