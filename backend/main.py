"""Точка входа Telegram-бота Sugar Mommy."""

import asyncio
import sys
from pathlib import Path

# Корень проекта в PYTHONPATH при запуске python backend/main.py
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.bot.factory import create_bot, create_dispatcher
from backend.config import get_settings
from backend.logging_setup import setup_logging
from backend.scheduler.setup import setup_scheduler
from backend.services.broadcast_service import BroadcastQueue
from db.session import dispose_db, init_db


async def main() -> None:
    settings = get_settings()
    setup_logging(settings)
    session_factory = init_db(settings.db_url)
    broadcast_queue = BroadcastQueue(settings)
    bot = create_bot(settings)
    dp = create_dispatcher(settings, session_factory, broadcast_queue)

    scheduler = setup_scheduler(bot, settings, session_factory, broadcast_queue)
    scheduler.start()

    try:
        await dp.start_polling(bot, settings=settings, broadcast_queue=broadcast_queue)
    finally:
        scheduler.shutdown(wait=False)
        await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
