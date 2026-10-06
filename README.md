# Sugar Mommy — Telegram-бот салона красоты (MVP)

Python 3.11+, aiogram 3, SQLAlchemy 2 async, Alembic, APScheduler, i18n (ru/uz/en).

## Структура

- `db/` — модели, репозитории, Alembic
- `backend/` — бот, сервисы, планировщик
- `locales/` — gettext `.po` / `.mo`
- `docs/ARCHITECTURE.md` — модули, FSM, scheduler, план **Фазы 2**

## Быстрый старт (локально)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# BOT_TOKEN, ADMIN_IDS=1977440418,6725003474, MASTER_IDS=<Gulnaz>
python scripts/compile_locales.py
alembic -c db/alembic.ini upgrade head
python scripts/seed.py
python backend/main.py
```

SQLite (без Docker): в `.env` задайте  
`DB_URL=sqlite+aiosqlite:///./data/sugar_mommy.db`

## Docker

```bash
copy .env.example .env
docker compose run --rm migrate
docker compose run --rm bot python scripts/seed.py
docker compose up -d bot
```

## Render (деплой в один клик)

1. Репозиторий на GitHub (без `.env`).
2. [Render](https://render.com) → **New** → **Blueprint** → выберите репо → **Apply**.
3. Введите **BOT_TOKEN** и **MASTER_IDS** при запросе.

Подробно: [`docs/DEPLOY_RENDER.md`](docs/DEPLOY_RENDER.md). Конфиг: [`render.yaml`](render.yaml).

## Роли

| Telegram ID | Роль |
|-------------|------|
| 1977440418 | Администратор (Рената) |
| 6725003474 | Администратор (Ангелина) |
| `MASTER_IDS` в `.env` | Мастер (Гульназ) |

## MVP vs Фаза 2

Реализовано в коде: запись, лист ожидания, anti-no-show, рассылки, экспорт, админ-обзор.  
FSM блокировки слотов (`cab:block`, `adm:block`) и редактирования графика (`cab:schedule`, `adm:schedule`) — handlers `block_slots.py`, `schedule_edit.py`.  
**Фаза 2** (спящие клиенты, горящие окна, сегментация) — только архитектура в `docs/ARCHITECTURE.md`, код по вашему сигналу.

## Пример i18n в handler

```python
from aiogram.utils.i18n import gettext as _

await message.answer(_("welcome"), reply_markup=language_keyboard())
```

Язык берётся из `User.language_code` через `LocaleMiddleware`.
