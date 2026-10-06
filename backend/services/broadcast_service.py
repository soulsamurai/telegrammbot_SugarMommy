"""Очередь массовой и экстренной рассылки с rate limit."""

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import date

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from db.models.broadcast_log import BroadcastLog
from db.models.enums import BroadcastType
from db.repositories.user_repo import UserRepository

logger = structlog.get_logger(__name__)


@dataclass
class BroadcastJob:
    admin_user_id: int | None
    broadcast_type: BroadcastType
    target_date: date | None
    text: str
    media_file_id: str | None
    telegram_ids: list[int]
    reply_markup: InlineKeyboardMarkup | None = None


class BroadcastQueue:
    """In-memory очередь с ограничением сообщений в секунду."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._queue: deque[BroadcastJob] = deque()
        self._running = False

    def enqueue(self, job: BroadcastJob) -> None:
        self._queue.append(job)

    async def run_worker(self, bot: Bot, session_factory) -> None:
        if self._running:
            return
        self._running = True
        while True:
            if not self._queue:
                await asyncio.sleep(0.5)
                continue
            job = self._queue.popleft()
            await self._process_job(bot, session_factory, job)

    async def _process_job(self, bot: Bot, session_factory, job: BroadcastJob) -> None:
        sent = 0
        failed = 0
        interval = 1.0 / max(1, self._settings.broadcast_rate_limit)
        for tg_id in job.telegram_ids:
            try:
                if job.media_file_id:
                    await bot.send_photo(
                        tg_id,
                        job.media_file_id,
                        caption=job.text,
                        reply_markup=job.reply_markup,
                    )
                else:
                    await bot.send_message(
                        tg_id, job.text, reply_markup=job.reply_markup
                    )
                sent += 1
                logger.info("broadcast_sent", telegram_id=tg_id)
            except TelegramForbiddenError:
                failed += 1
                async with session_factory() as session:
                    repo = UserRepository(session)
                    user = await repo.get_by_telegram_id(tg_id)
                    if user:
                        user.is_active = False
                    await session.commit()
                logger.warning("broadcast_blocked", telegram_id=tg_id)
            except TelegramRetryAfter as exc:
                await asyncio.sleep(exc.retry_after)
                continue
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.exception("broadcast_error", telegram_id=tg_id, error=str(exc))
            await asyncio.sleep(interval)

        async with session_factory() as session:
            log = BroadcastLog(
                admin_id=job.admin_user_id,
                type=job.broadcast_type,
                target_date=job.target_date,
                text=job.text,
                media_file_id=job.media_file_id,
                total_sent=sent,
                total_failed=failed,
            )
            session.add(log)
            await session.commit()
        logger.info(
            "broadcast_finished",
            type=job.broadcast_type.value,
            sent=sent,
            failed=failed,
        )
