"""Сборка бота и dispatcher."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from backend.bot.handlers import (
    admin,
    appointments,
    block_slots,
    booking,
    errors,
    master,
    schedule_edit,
    start,
    visit,
    waitlist,
)
from backend.bot.middlewares.context import AppContextMiddleware
from backend.bot.middlewares.db import DbSessionMiddleware
from backend.bot.middlewares.locale import LocaleMiddleware
from backend.bot.middlewares.logging_mw import LoggingMiddleware
from backend.bot.middlewares.throttling import ThrottlingMiddleware
from backend.bot.middlewares.user_role import UserRoleMiddleware
from backend.config import Settings
from backend.services.broadcast_service import BroadcastQueue
from db.session import async_sessionmaker, AsyncSession


def create_dispatcher(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    broadcast_queue: BroadcastQueue,
) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(AppContextMiddleware(settings, broadcast_queue))
    dp.update.middleware(DbSessionMiddleware(session_factory))
    dp.update.middleware(UserRoleMiddleware(settings))
    dp.update.middleware(LocaleMiddleware())
    dp.update.middleware(ThrottlingMiddleware())

    dp["settings"] = settings
    dp["broadcast_queue"] = broadcast_queue

    dp.include_router(errors.router)
    dp.include_router(start.router)
    dp.include_router(booking.router)
    dp.include_router(appointments.router)
    dp.include_router(waitlist.router)
    dp.include_router(visit.router)
    dp.include_router(master.router)
    dp.include_router(block_slots.router)
    dp.include_router(schedule_edit.router)
    dp.include_router(admin.router)
    return dp


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
