# Деплой на Render (Blueprint, один клик)

## Что создаётся автоматически

| Ресурс | Назначение |
|--------|------------|
| **PostgreSQL** `sugar-mommy-db` | База данных |
| **Background Worker** `sugar-mommy-bot` | Telegram-бот (polling + scheduler) |

Файл конфигурации: [`render.yaml`](../render.yaml) в корне репозитория.

## Шаги

1. Залейте проект на **GitHub** (репозиторий **private** рекомендуется).  
   Не коммитьте `.env` — он в `.gitignore`.

2. Зайдите на [render.com](https://render.com) → **New** → **Blueprint**.

3. Подключите GitHub-репозиторий → **Apply Blueprint**.

4. Render попросит значения для секретов:
   - **BOT_TOKEN** — токен от [@BotFather](https://t.me/BotFather)
   - **MASTER_IDS** — Telegram ID мастера (можно оставить пустым и добавить позже в Environment)

5. Дождитесь первого деплоя. Автоматически выполняются:
   - сборка Docker-образа
   - `alembic upgrade head` (перед каждым деплоем)
   - `python scripts/seed.py` (один раз после первого успешного деплоя)

6. **Logs** у сервиса `sugar-mommy-bot` — убедитесь, что нет ошибок. В Telegram: `/start`.

## Обновления

Push в ветку, с которой связан Blueprint (обычно `main`) → Render пересоберёт worker.

## Важно

- Держите **numInstances: 1** — два worker’а с одним ботом ломают polling.
- **SQLite на Render не использовать** — только Postgres из Blueprint.
- Тариф **starter** у worker и **free** у БД можно сменить в Dashboard (для 24/7 часто нужен платный worker).
- Регион **singapore** у БД и worker должен совпадать (уже так в `render.yaml`).

## Ручной seed (если нужно повторить)

Worker → **Shell**:

```bash
python scripts/seed.py
```

## Локальная разработка

Как в [README](../README.md): `DB_URL` с SQLite или Postgres, без `render.yaml`.
