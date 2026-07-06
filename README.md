# 🌱 Сад семечек — Telegram Mini App

Мини-приложение для Telegram: выращивай семечки, получай растения случайной редкости, зови друзей поливать сад.

## Механика

| Действие | Тест | Продакшен |
|----------|------|-----------|
| Рост семечка | 5 мин | 10 ч |
| Полив (кулдаун) | 1 мин | 24 ч |
| Ускорение за полив | −10 мин | −10 мин |

- **Редкость растения**: common → legendary (взвешенный рандом)
- **Фон**: 1 из 10 случайных (номер сохраняется, картинки добавите позже)
- **Реферал**: новый пользователь + автор ссылки получают бонус монет
- **Полив друга**: поливший получает +5 🪙, время роста уменьшается

## Стек (оптимизирован под слабый сервер)

- **Python 3.11** + FastAPI + aiogram 3 — один процесс (`run.py`)
- **SQLite** (WAL mode) — без отдельной БД
- **Vanilla JS** — без React/Vue, ~8 KB фронтенд
- Статика отдаётся через FastAPI StaticFiles

## Быстрый старт (локально)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # заполните BOT_TOKEN, BOT_USERNAME, WEBAPP_URL
python run.py
```

1. Создайте бота через [@BotFather](https://t.me/BotFather)
2. В BotFather: `/setmenubutton` → укажите URL вашего WebApp
3. `WEBAPP_URL` — публичный HTTPS URL (для локалки используйте ngrok)

## Деплой на Amvera

1. Залейте репозиторий на Amvera (Git push)
2. В настройках приложения задайте переменные окружения:
   - `BOT_TOKEN`
   - `BOT_USERNAME` (без @)
   - `WEBAPP_URL` (https://ваш-проект.amvera.ru)
   - `MODE=test` или `MODE=prod`
3. БД сохраняется в `/data/garden.db` (persistent volume)

Файл `amvera.yml` уже настроен.

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/me?ref=ID` | Профиль, растение, бонусы |
| POST | `/api/plant` | Посадить семечко |
| GET | `/api/friend/{telegram_id}` | Растение друга |
| POST | `/api/water/{plant_id}?owner_id=ID` | Полить растение друга |

Все запросы требуют заголовок `X-Telegram-Init-Data`.

## Структура

```
FLT/
├── app/
│   ├── main.py       # FastAPI + API
│   ├── bot.py        # Бот (отдельный запуск)
│   ├── services.py   # Бизнес-логика
│   ├── database.py   # SQLite
│   └── config.py     # Настройки из .env
├── static/           # WebApp UI
├── run.py            # API + бот в одном процессе
├── amvera.yml
└── requirements.txt
```

## Добавление картинок позже

В `static/images/` положите:
- `plants/{rarity}.png`
- `backgrounds/{id}.png`

В `app.js` замените emoji на `<img src="/static/images/...">` по `rarity` и `background_id` из API.
