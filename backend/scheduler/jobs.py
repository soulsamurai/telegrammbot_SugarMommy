"""Фоновые задачи APScheduler."""

from datetime import datetime, timedelta

import structlog
from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.config import Settings
from backend.services.appointment_service import AppointmentService
from backend.services.notifications import (
    alert_admins_unconfirmed,
    send_confirm_visit_prompt,
    send_waitlist_offer,
)
from backend.services.waitlist_service import WaitlistService
from db.models.enums import ReminderStatus, ReminderType
from db.repositories.appointment_repo import AppointmentRepository
from db.repositories.reminder_repo import ReminderRepository
from db.repositories.user_repo import UserRepository

logger = structlog.get_logger(__name__)


async def job_confirm_visit_reminders(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    now = datetime.now(settings.tz)
    window_end = now + timedelta(hours=settings.confirm_visit_hours)
    window_start = now + timedelta(hours=settings.confirm_visit_hours - 0.25)
    async with session_factory() as session:
        repo = AppointmentRepository(session)
        reminders = ReminderRepository(session)
        appts = await repo.need_confirm_reminder(now, window_start, window_end)
        for appt in appts:
            if await reminders.has_confirm_sent(appt.id):
                continue
            await send_confirm_visit_prompt(bot, appt)
            from db.models.reminder import Reminder

            await reminders.add(
                Reminder(
                    appointment_id=appt.id,
                    type=ReminderType.confirm_visit,
                    scheduled_at=now,
                    sent_at=now,
                    status=ReminderStatus.sent,
                )
            )
        await session.commit()


async def job_unconfirmed_alerts(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    now = datetime.now(settings.tz)
    async with session_factory() as session:
        appts = await AppointmentRepository(session).unconfirmed_before(
            now, settings.unconfirmed_alert_hours
        )
        for appt in appts:
            await alert_admins_unconfirmed(bot, settings.admin_ids, appt)
        await session.commit()


async def job_repeat_reminders(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from backend.bot.i18n import i18n
    from aiogram.utils.i18n import gettext as _
    from backend.services.i18n_helpers import service_name
    from db.models.service import Service

    now = datetime.now(settings.tz)
    async with session_factory() as session:
        reminders = await ReminderRepository(session).pending_due(now)
        users = UserRepository(session)
        for rem in reminders:
            if rem.type != ReminderType.repeat_visit or rem.client_id is None:
                continue
            user = await users.get_by_id(rem.client_id)
            service = await session.get(Service, rem.service_id) if rem.service_id else None
            if user is None or service is None:
                rem.status = ReminderStatus.cancelled
                continue
            locale = user.language_code or "ru"
            with i18n.use_locale(locale):
                text = _("repeat_visit").format(
                    days=service.reminder_days,
                    service=service_name(service, locale),
                )
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=_("menu_book"), callback_data="menu:book")]
                    ]
                )
            await bot.send_message(user.telegram_id, text, reply_markup=kb)
            rem.status = ReminderStatus.sent
            rem.sent_at = now
        await session.commit()


async def job_complete_appointments(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    now = datetime.now(settings.tz)
    async with session_factory() as session:
        appts = await AppointmentRepository(session).past_active(now)
        svc = AppointmentService(session, settings)
        for appt in appts:
            await svc.mark_completed(appt)
        await session.commit()


async def job_waitlist_timeouts(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as session:
        wl = WaitlistService(session, settings)
        new_offers = await wl.process_expired_offers()
        for entry in new_offers:
            if entry.client:
                await send_waitlist_offer(
                    bot,
                    entry.client,
                    entry.preferred_date.strftime("%d.%m"),
                    entry.preferred_time_start.strftime("%H:%M"),
                    entry.id,
                )
        await session.commit()
