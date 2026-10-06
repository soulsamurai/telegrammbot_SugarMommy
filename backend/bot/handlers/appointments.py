"""Мои записи, отмена, перенос."""

from datetime import date, time

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from backend.bot.keyboards.booking import dates_keyboard, times_keyboard
from backend.bot.keyboards.common import main_menu_keyboard
from backend.bot.states.booking import RescheduleStates
from backend.config import Settings
from backend.services.appointment_service import AppointmentPolicyError, AppointmentService
from backend.services.i18n_helpers import service_name
from backend.services.notifications import notify_master_cancel
from backend.services.slot_service import SlotService
from backend.services.waitlist_service import WaitlistService
from db.models.user import User
from db.repositories.appointment_repo import AppointmentRepository
from db.repositories.service_repo import ServiceRepository

router = Router(name="appointments")


def _appt_keyboard(appt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_("btn_cancel"), callback_data=f"appt:cancel:{appt_id}"
                ),
                InlineKeyboardButton(
                    text=_("btn_reschedule"), callback_data=f"appt:resched:{appt_id}"
                ),
            ]
        ]
    )


@router.callback_query(F.data == "menu:appts")
async def list_appointments(
    query: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    locale: str,
    role: str,
) -> None:
    repo = AppointmentRepository(session)
    items = await repo.list_upcoming_for_client(db_user.id)
    if not items:
        await query.message.edit_text(_("menu_appointments"))
        await query.message.answer(_("menu_book"), reply_markup=main_menu_keyboard(role))
        await query.answer()
        return
    lines = []
    for appt in items:
        lines.append(
            f"#{appt.id} {service_name(appt.service, locale)} — "
            f"{appt.date.strftime('%d.%m')} {appt.start_time.strftime('%H:%M')}"
        )
    await query.message.edit_text("\n".join(lines))
    for appt in items:
        await query.message.answer(f"#{appt.id}", reply_markup=_appt_keyboard(appt.id))
    await query.answer()


@router.callback_query(F.data.startswith("appt:cancel:"))
async def cancel_appt(
    query: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    role: str,
) -> None:
    appt_id = int(query.data.split(":")[-1])
    repo = AppointmentRepository(session)
    appt = await repo.get_by_id(appt_id)
    if appt is None:
        await query.answer("Не найдено", show_alert=True)
        return
    svc = AppointmentService(session, settings)
    try:
        await svc.cancel_by_client(appt)
    except AppointmentPolicyError:
        await query.answer(_("cancel_too_late"), show_alert=True)
        return
    if appt.master:
        await notify_master_cancel(query.bot, appt.master, appt)
    wl = WaitlistService(session, settings)
    offered = await wl.notify_slot_freed(
        appt.master_id,
        appt.service_id,
        appt.date,
        appt.start_time,
        appt.end_time,
    )
    if offered and offered.client:
        from backend.services.notifications import send_waitlist_offer

        await send_waitlist_offer(
            query.bot,
            offered.client,
            appt.date.strftime("%d.%m"),
            appt.start_time.strftime("%H:%M"),
            offered.id,
        )
    await query.message.edit_text(_("booking_cancelled"))
    await query.message.answer(_("menu_book"), reply_markup=main_menu_keyboard(role))
    await query.answer()


@router.callback_query(F.data.startswith("appt:resched:"))
async def start_reschedule(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    appt_id = int(query.data.split(":")[-1])
    appt = await AppointmentRepository(session).get_by_id(appt_id)
    if appt is None:
        await query.answer("Не найдено", show_alert=True)
        return
    await state.set_state(RescheduleStates.choosing_date)
    await state.update_data(
        reschedule_appt_id=appt_id,
        service_id=appt.service_id,
        master_id=appt.master_id,
    )
    service = await ServiceRepository(session).get_by_id(appt.service_id)
    dates = await SlotService(session, settings).iter_available_dates(
        appt.master_id, service.duration_min
    )
    await query.message.edit_text(_("choose_date"), reply_markup=dates_keyboard(dates))
    await query.answer()


@router.callback_query(
    F.data.startswith("book:date:"),
    StateFilter(RescheduleStates.choosing_date),
)
async def reschedule_pick_date(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    day = date.fromisoformat(query.data.split(":")[-1])
    data = await state.get_data()
    service = await ServiceRepository(session).get_by_id(int(data["service_id"]))
    master_id = int(data["master_id"])
    free = await SlotService(session, settings).get_free_slots(
        master_id, day, service.duration_min
    )
    await state.update_data(booking_date=day.isoformat())
    await state.set_state(RescheduleStates.choosing_time)
    await query.message.edit_text(_("choose_time"), reply_markup=times_keyboard(free, day))
    await query.answer()


@router.callback_query(
    F.data.startswith("book:time:"),
    StateFilter(RescheduleStates.choosing_time),
)
async def reschedule_pick_time(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    role: str,
) -> None:
    _, _, day_str, time_str = query.data.split(":", 3)
    data = await state.get_data()
    appt_id = int(data["reschedule_appt_id"])
    appt = await AppointmentRepository(session).get_by_id(appt_id)
    if appt is None:
        await query.answer("Не найдено", show_alert=True)
        return
    svc = AppointmentService(session, settings)
    try:
        new_appt = await svc.reschedule(
            appt,
            date.fromisoformat(day_str),
            time.fromisoformat(time_str),
        )
    except AppointmentPolicyError:
        await query.answer(_("cancel_too_late"), show_alert=True)
        return
    except ValueError:
        await query.answer("Слот занят", show_alert=True)
        return
    await session.refresh(new_appt, ["master", "client"])
    if new_appt.master:
        from backend.services.notifications import notify_master_reschedule

        await notify_master_reschedule(query.bot, appt, new_appt)
    await state.clear()
    await query.message.edit_text(
        _("booking_created").format(
            date=new_appt.date.strftime("%d.%m"),
            time=new_appt.start_time.strftime("%H:%M"),
        )
    )
    await query.message.answer(_("menu_book"), reply_markup=main_menu_keyboard(role))
    await query.answer()
