"""Регистрация задач APScheduler."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.config import Settings
from backend.scheduler import jobs
from backend.services.broadcast_service import BroadcastQueue


def setup_scheduler(
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    broadcast_queue: BroadcastQueue,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tz)

    scheduler.add_job(
        jobs.job_confirm_visit_reminders,
        "cron",
        minute="*/5",
        kwargs={"bot": bot, "session_factory": session_factory, "settings": settings},
    )
    scheduler.add_job(
        jobs.job_unconfirmed_alerts,
        "cron",
        minute="*/5",
        kwargs={"bot": bot, "session_factory": session_factory, "settings": settings},
    )
    scheduler.add_job(
        jobs.job_repeat_reminders,
        "cron",
        minute="0",
        kwargs={"bot": bot, "session_factory": session_factory, "settings": settings},
    )
    scheduler.add_job(
        jobs.job_complete_appointments,
        "cron",
        minute="*/15",
        kwargs={"session_factory": session_factory, "settings": settings},
    )
    scheduler.add_job(
        jobs.job_waitlist_timeouts,
        "cron",
        minute="*",
        kwargs={"bot": bot, "session_factory": session_factory, "settings": settings},
    )
    scheduler.add_job(
        broadcast_queue.run_worker,
        "interval",
        seconds=1,
        kwargs={"bot": bot, "session_factory": session_factory},
        max_instances=1,
    )
    return scheduler
