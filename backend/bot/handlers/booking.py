"""FSM записи на услугу."""

from datetime import date, time

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from backend.bot.keyboards.booking import (
    booking_confirm_keyboard,
    dates_keyboard,
    masters_keyboard,
    services_keyboard,
    times_keyboard,
    waitlist_keyboard,
)
from backend.bot.keyboards.common import main_menu_keyboard
from backend.bot.states.booking import BookingStates
from backend.config import Settings
from backend.services.appointment_service import AppointmentService
from backend.services.i18n_helpers import service_name
from backend.services.notifications import notify_master_new_booking
from backend.services.slot_service import SlotService, _add_minutes
from db.models.user import User
from db.repositories.master_repo import MasterRepository
from db.repositories.service_repo import ServiceRepository

router = Router(name="booking")


@router.callback_query(F.data == "menu:book")
async def start_booking(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    locale: str,
) -> None:
    await state.clear()
    await state.set_state(BookingStates.choosing_service)
    await state.update_data(service_page=0)
    await _show_services(query, session, state, settings, locale)
    await query.answer()


async def _show_services(
    query: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    settings: Settings,
    locale: str,
) -> None:
    data = await state.get_data()
    page = int(data.get("service_page", 0))
    repo = ServiceRepository(session)
    services, total = await repo.list_active_paginated(
        page * settings.services_per_page, settings.services_per_page
    )
    await query.message.edit_text(
        _("choose_service"),
        reply_markup=services_keyboard(
            services, page, total, settings.services_per_page, locale
        ),
    )


@router.callback_query(
    F.data.startswith("book:svc_page:"), StateFilter(BookingStates.choosing_service)
)
async def services_page(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    locale: str,
) -> None:
    page = int(query.data.split(":")[-1])
    await state.update_data(service_page=page)
    await _show_services(query, session, state, settings, locale)
    await query.answer()


@router.callback_query(
    F.data.startswith("book:svc:"), StateFilter(BookingStates.choosing_service)
)
async def pick_service(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    locale: str,
) -> None:
    service_id = int(query.data.split(":")[-1])
    masters = await MasterRepository(session).list_for_service(service_id)
    if not masters:
        await query.answer("Нет мастеров для услуги", show_alert=True)
        return
    await state.update_data(service_id=service_id)
    await state.set_state(BookingStates.choosing_master)
    await query.message.edit_text(_("choose_master"), reply_markup=masters_keyboard(masters))
    await query.answer()


@router.callback_query(F.data == "book:back:svc", StateFilter(BookingStates.choosing_master))
async def back_to_services(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    locale: str,
) -> None:
    await state.set_state(BookingStates.choosing_service)
    await _show_services(query, session, state, settings, locale)
    await query.answer()


@router.callback_query(F.data.startswith("book:mst:"), StateFilter(BookingStates.choosing_master))
async def pick_master(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    master_id = int(query.data.split(":")[-1])
    data = await state.get_data()
    service = await ServiceRepository(session).get_by_id(int(data["service_id"]))
    if service is None:
        await query.answer("Услуга не найдена", show_alert=True)
        return
    slots_svc = SlotService(session, settings)
    dates = await slots_svc.iter_available_dates(master_id, service.duration_min)
    if not dates:
        await query.answer("Нет доступных дат", show_alert=True)
        return
    await state.update_data(master_id=master_id)
    await state.set_state(BookingStates.choosing_date)
    await query.message.edit_text(_("choose_date"), reply_markup=dates_keyboard(dates))
    await query.answer()


@router.callback_query(F.data == "book:back:mst", StateFilter(BookingStates.choosing_date))
async def back_to_master(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    masters = await MasterRepository(session).list_for_service(int(data["service_id"]))
    await state.set_state(BookingStates.choosing_master)
    await query.message.edit_text(_("choose_master"), reply_markup=masters_keyboard(masters))
    await query.answer()


@router.callback_query(F.data.startswith("book:date:"), StateFilter(BookingStates.choosing_date))
async def pick_date(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    day = date.fromisoformat(query.data.split(":")[-1])
    data = await state.get_data()
    service = await ServiceRepository(session).get_by_id(int(data["service_id"]))
    master_id = int(data["master_id"])
    slots_svc = SlotService(session, settings)
    free = await slots_svc.get_free_slots(master_id, day, service.duration_min)
    await state.update_data(booking_date=day.isoformat())
    if not free:
        all_starts = await slots_svc.get_all_slot_starts(
            master_id, day, service.duration_min
        )
        await state.set_state(BookingStates.waitlist_offer)
        await state.update_data(booking_date=day.isoformat())
        if all_starts:
            await query.message.edit_text(
                _("no_slots") + "\n" + _("choose_time"),
                reply_markup=times_keyboard(all_starts, day),
            )
        else:
            await query.message.edit_text(_("no_slots"))
        await query.answer()
        return
    await state.set_state(BookingStates.choosing_time)
    await query.message.edit_text(_("choose_time"), reply_markup=times_keyboard(free, day))
    await query.answer()


@router.callback_query(
    F.data == "book:back:date",
    StateFilter(BookingStates.choosing_time, BookingStates.waitlist_offer),
)
async def back_to_date(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    data = await state.get_data()
    service = await ServiceRepository(session).get_by_id(int(data["service_id"]))
    master_id = int(data["master_id"])
    dates = await SlotService(session, settings).iter_available_dates(
        master_id, service.duration_min
    )
    await state.set_state(BookingStates.choosing_date)
    await query.message.edit_text(_("choose_date"), reply_markup=dates_keyboard(dates))
    await query.answer()


@router.callback_query(
    F.data.startswith("book:time:"), StateFilter(BookingStates.waitlist_offer)
)
async def waitlist_pick_time(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    locale: str,
) -> None:
    _, _, day_str, time_str = query.data.split(":", 3)
    day = date.fromisoformat(day_str)
    start = time.fromisoformat(time_str)
    data = await state.get_data()
    service = await ServiceRepository(session).get_by_id(int(data["service_id"]))
    master_id = int(data["master_id"])
    end = _add_minutes(start, service.duration_min)
    free = await SlotService(session, settings).get_free_slots(
        master_id, day, service.duration_min
    )
    if start in free:
        await state.update_data(booking_date=day_str, booking_time=time_str)
        await state.set_state(BookingStates.confirming)
        master = await MasterRepository(session).get_by_id(master_id)
        text = _("confirm_booking").format(
            service=service_name(service, locale),
            master=master.name if master else "",
            date=day.strftime("%d.%m.%Y"),
            time=start.strftime("%H:%M"),
            price=service.price,
        )
        text = f"{text}\n\n{_('cancel_policy')}"
        await query.message.edit_text(text, reply_markup=booking_confirm_keyboard())
        await query.answer()
        return
    await state.update_data(
        booking_date=day_str,
        booking_time=time_str,
        waitlist_end=end.isoformat(),
    )
    await query.message.edit_text(
        _("waitlist_offer").format(date=day.strftime("%d.%m"), time=start.strftime("%H:%M")),
        reply_markup=waitlist_keyboard(
            day, start, master_id, int(data["service_id"])
        ),
    )
    await query.answer()


@router.callback_query(F.data.startswith("book:time:"), StateFilter(BookingStates.choosing_time))
async def pick_time(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    locale: str,
) -> None:
    _, _, day_str, time_str = query.data.split(":", 3)
    await state.update_data(booking_date=day_str, booking_time=time_str)
    data = await state.get_data()
    service = await ServiceRepository(session).get_by_id(int(data["service_id"]))
    master = await MasterRepository(session).get_by_id(int(data["master_id"]))
    day = date.fromisoformat(day_str)
    start = time.fromisoformat(time_str)
    text = _("confirm_booking").format(
        service=service_name(service, locale),
        master=master.name if master else "",
        date=day.strftime("%d.%m.%Y"),
        time=start.strftime("%H:%M"),
        price=service.price,
    )
    text = f"{text}\n\n{_('cancel_policy')}"
    await state.set_state(BookingStates.confirming)
    await query.message.edit_text(text, reply_markup=booking_confirm_keyboard())
    await query.answer()


@router.callback_query(F.data == "book:confirm", StateFilter(BookingStates.confirming))
async def confirm_booking(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    db_user: User,
    role: str,
) -> None:
    data = await state.get_data()
    svc = AppointmentService(session, settings)
    day = date.fromisoformat(data["booking_date"])
    start = time.fromisoformat(data["booking_time"])
    try:
        appt = await svc.create(
            client_id=db_user.id,
            master_id=int(data["master_id"]),
            service_id=int(data["service_id"]),
            day=day,
            start=start,
        )
    except ValueError:
        await query.answer("Слот уже занят", show_alert=True)
        return
    await session.refresh(appt, attribute_names=["master", "service", "client"])
    if appt.master:
        await notify_master_new_booking(query.bot, appt.master, appt)
    await state.clear()
    await query.message.edit_text(
        _("booking_created").format(
            date=day.strftime("%d.%m"), time=start.strftime("%H:%M")
        )
    )
    await query.message.answer(_("menu_book"), reply_markup=main_menu_keyboard(role))
    await query.answer()
