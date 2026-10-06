"""Админ-панель (полные права)."""

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from backend.bot.filters.roles import RoleFilter
from backend.bot.keyboards.common import back_main_keyboard
from backend.bot.states.admin import EmergencyBroadcastStates, MassBroadcastStates
from backend.config import Settings
from backend.services.appointment_service import AppointmentService
from backend.services.broadcast_service import BroadcastJob, BroadcastQueue
from backend.services.export_service import ExportService
from backend.services.i18n_helpers import service_name
from backend.services.notifications import notify_client_cancelled_by_master
from backend.services.waitlist_service import WaitlistService
from db.models.enums import BroadcastType
from db.models.user import User
from db.repositories.appointment_repo import AppointmentRepository
from db.repositories.user_repo import UserRepository

router = Router(name="admin")
router.message.filter(RoleFilter("admin"))
router.callback_query.filter(RoleFilter("admin"))


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Записи сегодня", callback_data="adm:appts:today")],
            [InlineKeyboardButton(text="Записи неделя", callback_data="adm:appts:week")],
            [InlineKeyboardButton(text="Статистика / экспорт", callback_data="adm:export")],
            [InlineKeyboardButton(text="Экстренная рассылка", callback_data="adm:bc:em")],
            [InlineKeyboardButton(text="Массовая рассылка", callback_data="adm:bc:mass")],
            [InlineKeyboardButton(text="Лист ожидания", callback_data="adm:waitlist")],
            [InlineKeyboardButton(text="Услуги", callback_data="adm:services")],
            [InlineKeyboardButton(text="Мастера", callback_data="adm:masters")],
            [InlineKeyboardButton(text="График мастеров", callback_data="adm:schedule")],
            [InlineKeyboardButton(text="Блокировка слотов", callback_data="adm:block")],
            [InlineKeyboardButton(text=_("btn_main_menu"), callback_data="menu:main")],
        ]
    )


@router.callback_query(F.data == "menu:admin")
async def open_admin(query: CallbackQuery) -> None:
    await query.message.edit_text(_("menu_admin"), reply_markup=admin_menu())
    await query.answer()


@router.callback_query(F.data == "adm:appts:today")
async def appts_today(query: CallbackQuery, session: AsyncSession, locale: str) -> None:
    today = date.today()
    items = await AppointmentRepository(session).list_between(today, today)
    if not items:
        text = "Нет записей на сегодня."
    else:
        lines = [
            f"#{a.id} {a.master.name} {a.start_time.strftime('%H:%M')} "
            f"{service_name(a.service, locale)} @{a.client.username or a.client.telegram_id}"
            for a in items
        ]
        text = "\n".join(lines)
    await query.message.edit_text(text, reply_markup=admin_menu())
    await query.answer()


@router.callback_query(F.data == "adm:appts:week")
async def appts_week(query: CallbackQuery, session: AsyncSession, locale: str) -> None:
    start = date.today()
    end = start + timedelta(days=7)
    items = await AppointmentRepository(session).list_between(start, end)
    text = f"Записей: {len(items)}" if items else "Нет записей на неделю."
    await query.message.edit_text(text, reply_markup=admin_menu())
    await query.answer()


@router.callback_query(F.data == "adm:export")
async def export_menu(query: CallbackQuery) -> None:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="CSV неделя", callback_data="adm:export:csv:week"),
                InlineKeyboardButton(text="XLSX неделя", callback_data="adm:export:xlsx:week"),
            ],
            [InlineKeyboardButton(text=_("btn_back"), callback_data="menu:admin")],
        ]
    )
    await query.message.edit_text("Экспорт отчёта:", reply_markup=kb)
    await query.answer()


@router.callback_query(F.data.startswith("adm:export:"))
async def do_export(query: CallbackQuery, session: AsyncSession, locale: str) -> None:
    _, _, fmt, period = query.data.split(":")
    start = date.today()
    end = start + timedelta(days=7 if period == "week" else 30)
    rows = await ExportService(session).collect_rows(start, end, None, locale)
    svc = ExportService(session)
    if fmt == "csv":
        content = svc.to_csv(rows)
        filename = "report.csv"
    else:
        content = svc.to_xlsx(rows)
        filename = "report.xlsx"
    await query.message.answer_document(
        BufferedInputFile(content, filename=filename),
    )
    await query.answer()


@router.callback_query(F.data == "adm:bc:em")
async def emergency_bc_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EmergencyBroadcastStates.select_date)
    await query.message.edit_text("Введите дату рассылки (YYYY-MM-DD):")
    await query.answer()


@router.message(StateFilter(EmergencyBroadcastStates.select_date))
async def emergency_bc_date(message: Message, state: FSMContext) -> None:
    try:
        day = date.fromisoformat(message.text.strip())
    except ValueError:
        await message.answer("Неверный формат даты.")
        return
    await state.update_data(bc_date=day.isoformat())
    await state.set_state(EmergencyBroadcastStates.enter_text)
    await message.answer("Текст сообщения для клиентов с записями на эту дату:")


@router.message(StateFilter(EmergencyBroadcastStates.enter_text))
async def emergency_bc_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    broadcast_queue: BroadcastQueue,
) -> None:
    data = await state.get_data()
    day = date.fromisoformat(data["bc_date"])
    client_ids = await AppointmentRepository(session).clients_for_date(day)
    users = UserRepository(session)
    tg_ids: list[int] = []
    for cid in client_ids:
        u = await users.get_by_id(cid)
        if u and u.is_active:
            tg_ids.append(u.telegram_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("btn_reschedule"), callback_data="menu:book")],
            [InlineKeyboardButton(text="Связаться с админом", url="https://t.me/")],
        ]
    )
    broadcast_queue.enqueue(
        BroadcastJob(
            admin_user_id=db_user.id,
            broadcast_type=BroadcastType.emergency,
            target_date=day,
            text=message.text,
            media_file_id=None,
            telegram_ids=tg_ids,
            reply_markup=kb,
        )
    )
    await state.clear()
    await message.answer(f"Рассылка поставлена в очередь ({len(tg_ids)} получателей).")


@router.callback_query(F.data == "adm:bc:mass")
async def mass_bc_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MassBroadcastStates.enter_text)
    await query.message.edit_text("Текст массовой рассылки:")
    await query.answer()


@router.message(StateFilter(MassBroadcastStates.enter_text))
async def mass_bc_text(message: Message, state: FSMContext) -> None:
    await state.update_data(mass_text=message.text)
    await state.set_state(MassBroadcastStates.enter_media)
    await message.answer("Отправьте фото или /skip")


@router.message(StateFilter(MassBroadcastStates.enter_media))
async def mass_bc_media(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    broadcast_queue: BroadcastQueue,
) -> None:
    data = await state.get_data()
    media_id = None
    if message.text and message.text.strip() != "/skip":
        await message.answer("Используйте /skip или фото.")
        return
    if message.photo:
        media_id = message.photo[-1].file_id
    tg_ids = await UserRepository(session).list_active_telegram_ids()
    broadcast_queue.enqueue(
        BroadcastJob(
            admin_user_id=db_user.id,
            broadcast_type=BroadcastType.mass,
            target_date=None,
            text=data["mass_text"],
            media_file_id=media_id,
            telegram_ids=tg_ids,
        )
    )
    await state.clear()
    await message.answer(f"Массовая рассылка в очереди ({len(tg_ids)} пользователей).")


@router.callback_query(F.data == "adm:waitlist")
async def admin_waitlist(query: CallbackQuery, session: AsyncSession, locale: str) -> None:
    from db.repositories.waitlist_repo import WaitlistRepository

    entries = await WaitlistRepository(session).list_all_active()
    if not entries:
        text = "Лист ожидания пуст."
    else:
        lines = []
        for e in entries:
            lines.append(
                f"#{e.id} p{e.position} {e.master.name} "
                f"{service_name(e.service, locale)} {e.preferred_date} "
                f"{e.preferred_time_start.strftime('%H:%M')} — {e.status.value}"
            )
        text = "\n".join(lines)
    await query.message.edit_text(text, reply_markup=admin_menu())
    await query.answer()


@router.callback_query(F.data == "adm:services")
async def admin_services(query: CallbackQuery, session: AsyncSession, locale: str) -> None:
    from db.repositories.service_repo import ServiceRepository

    services = await ServiceRepository(session).list_all()
    lines = [
        f"#{s.id} {service_name(s, locale)} {s.price} / {s.duration_min}m / remind {s.reminder_days}d"
        for s in services
    ]
    await query.message.edit_text("\n".join(lines) or "Нет услуг", reply_markup=admin_menu())
    await query.answer()


@router.callback_query(F.data == "adm:masters")
async def admin_masters(query: CallbackQuery, session: AsyncSession) -> None:
    from db.repositories.master_repo import MasterRepository

    masters = await MasterRepository(session).list_active()
    lines = [f"#{m.id} {m.name} ({m.role.value}) tg={m.user.telegram_id}" for m in masters]
    await query.message.edit_text("\n".join(lines) or "Нет мастеров", reply_markup=admin_menu())
    await query.answer()


@router.callback_query(F.data.startswith("adm:cancel:"))
async def admin_cancel_appt(
    query: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    appt_id = int(query.data.split(":")[-1])
    appt = await AppointmentRepository(session).get_by_id(appt_id)
    if appt is None:
        await query.answer("Не найдено", show_alert=True)
        return
    await AppointmentService(session, settings).cancel_by_master(appt)
    await notify_client_cancelled_by_master(query.bot, appt)
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
    await query.answer("Запись отменена")
