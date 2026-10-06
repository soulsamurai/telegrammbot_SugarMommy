"""Anti-no-show: подтверждение визита."""

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from backend.bot.keyboards.common import main_menu_keyboard
from backend.config import Settings
from backend.services.appointment_service import AppointmentPolicyError, AppointmentService
from backend.services.waitlist_service import WaitlistService
from db.repositories.appointment_repo import AppointmentRepository

router = Router(name="visit")


@router.callback_query(F.data.startswith("visit:yes:"))
async def confirm_visit(
    query: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    role: str,
) -> None:
    appt_id = int(query.data.split(":")[-1])
    appt = await AppointmentRepository(session).get_by_id(appt_id)
    if appt is None:
        await query.answer("Не найдено", show_alert=True)
        return
    await AppointmentService(session, settings).confirm_visit(appt)
    await query.message.edit_text(_("confirm_visit_yes") + " ✓")
    await query.message.answer(_("menu_book"), reply_markup=main_menu_keyboard(role))
    await query.answer()


@router.callback_query(F.data.startswith("visit:no:"))
async def cancel_from_visit_prompt(
    query: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    role: str,
) -> None:
    appt_id = int(query.data.split(":")[-1])
    appt = await AppointmentRepository(session).get_by_id(appt_id)
    if appt is None:
        await query.answer("Не найдено", show_alert=True)
        return
    svc = AppointmentService(session, settings)
    try:
        await svc.cancel_by_client(appt)
    except AppointmentPolicyError:
        await query.answer(_("cancel_too_late"), show_alert=True)
        return
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
