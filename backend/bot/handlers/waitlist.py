"""Лист ожидания."""

from datetime import date, time

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from backend.bot.keyboards.common import main_menu_keyboard
from backend.config import Settings
from backend.services.slot_service import _add_minutes
from backend.services.waitlist_service import WaitlistService
from db.models.user import User
from db.repositories.service_repo import ServiceRepository
from db.repositories.waitlist_repo import WaitlistRepository

router = Router(name="waitlist")


@router.callback_query(F.data.startswith("waitlist:join2:"))
async def join_waitlist_full(
    query: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    db_user: User,
    role: str,
) -> None:
    parts = query.data.split(":")
    master_id = int(parts[2])
    service_id = int(parts[3])
    day = date.fromisoformat(parts[4])
    time_str = parts[5]
    start = time.fromisoformat(time_str)
    service = await ServiceRepository(session).get_by_id(service_id)
    end = _add_minutes(start, service.duration_min)
    wl = WaitlistService(session, settings)
    await wl.join(db_user.id, master_id, service_id, day, start, end)
    await query.message.edit_text(_("btn_join_waitlist") + " ✓")
    await query.message.answer(_("menu_book"), reply_markup=main_menu_keyboard(role))
    await query.answer()


@router.callback_query(F.data.startswith("waitlist:take:"))
async def take_waitlist_slot(
    query: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    role: str,
) -> None:
    entry_id = int(query.data.split(":")[-1])
    repo = WaitlistRepository(session)
    entry = await repo.get_by_id(entry_id)
    if entry is None:
        await query.answer("Не найдено", show_alert=True)
        return
    wl = WaitlistService(session, settings)
    try:
        await wl.accept_offer(entry)
    except ValueError:
        await query.answer("Предложение недействительно", show_alert=True)
        return
    await query.message.edit_text(_("booking_created").format(
        date=entry.preferred_date.strftime("%d.%m"),
        time=entry.preferred_time_start.strftime("%H:%M"),
    ))
    await query.message.answer(_("menu_book"), reply_markup=main_menu_keyboard(role))
    await query.answer()


@router.callback_query(F.data.startswith("waitlist:decline:"))
async def decline_waitlist(
    query: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    entry_id = int(query.data.split(":")[-1])
    entry = await WaitlistRepository(session).get_by_id(entry_id)
    if entry is None:
        await query.answer()
        return
    wl = WaitlistService(session, settings)
    await wl.decline_or_expire(entry)
    nxt = await wl.notify_slot_freed(
        entry.master_id,
        entry.service_id,
        entry.preferred_date,
        entry.preferred_time_start,
        entry.preferred_time_end,
    )
    if nxt and nxt.client:
        from backend.services.notifications import send_waitlist_offer

        await send_waitlist_offer(
            query.bot,
            nxt.client,
            entry.preferred_date.strftime("%d.%m"),
            entry.preferred_time_start.strftime("%H:%M"),
            nxt.id,
        )
    await query.message.edit_text(_("btn_decline_slot"))
    await query.answer()


@router.callback_query(F.data.startswith("waitlist:leave:"))
async def leave_waitlist(
    query: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    role: str,
) -> None:
    entry_id = int(query.data.split(":")[-1])
    entry = await WaitlistRepository(session).get_by_id(entry_id)
    if entry:
        await WaitlistService(session, settings).cancel_entry(entry)
    await query.message.edit_text(_("btn_leave_waitlist"))
    await query.message.answer(_("menu_book"), reply_markup=main_menu_keyboard(role))
    await query.answer()
