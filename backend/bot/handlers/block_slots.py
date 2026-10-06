"""FSM блокировки слотов мастера (кабинет / админ)."""

from datetime import date, datetime, time, timedelta

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from backend.bot.filters.roles import RoleFilter
from backend.bot.handlers.master import cabinet_menu
from backend.bot.states.admin import BlockSlotStates
from backend.config import Settings
from backend.services.slot_service import SlotService, _add_minutes
from db.models.blocked_slot import BlockedSlot
from db.models.user import User
from db.repositories.appointment_repo import AppointmentRepository
from db.repositories.blocked_repo import BlockedSlotRepository
from db.repositories.master_repo import MasterRepository
from db.repositories.schedule_repo import ScheduleRepository
from db.repositories.service_repo import ServiceRepository

router = Router(name="block_slots")
router.callback_query.filter(RoleFilter("master", "admin"))
router.message.filter(RoleFilter("master", "admin"))


def _masters_keyboard(masters: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=m.name, callback_data=f"blk:mst:{m.id}")]
        for m in masters
    ]
    rows.append([InlineKeyboardButton(text=_("btn_main_menu"), callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _dates_keyboard(days: list[date], *, admin_flow: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i, d in enumerate(days, start=1):
        row.append(
            InlineKeyboardButton(
                text=d.strftime("%d.%m"),
                callback_data=f"blk:date:{d.isoformat()}",
            )
        )
        if i % 4 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    back_data = "blk:back:mst" if admin_flow else "menu:cabinet"
    rows.append([InlineKeyboardButton(text=_("btn_back"), callback_data=back_data)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _slots_keyboard(
    day: date,
    slots: list[time],
    selected: set[str],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i, slot in enumerate(slots, start=1):
        key = slot.strftime("%H:%M")
        mark = "✓ " if key in selected else ""
        row.append(
            InlineKeyboardButton(
                text=f"{mark}{key}",
                callback_data=f"blk:tog:{day.isoformat()}:{key}",
            )
        )
        if i % 4 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [
            InlineKeyboardButton(text=_("btn_confirm"), callback_data="blk:done"),
            InlineKeyboardButton(text=_("btn_cancel"), callback_data="menu:main"),
        ]
    )
    rows.append([InlineKeyboardButton(text=_("btn_back"), callback_data="blk:back:date")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _slot_step_min(session: AsyncSession) -> int:
    services = await ServiceRepository(session).list_all()
    active = [s.duration_min for s in services if s.is_active]
    return min(active) if active else 60


async def _working_dates(
    session: AsyncSession, settings: Settings, master_id: int
) -> list[date]:
    sched_repo = ScheduleRepository(session)
    today = date.today()
    days: list[date] = []
    for i in range(settings.calendar_days_ahead):
        d = today + timedelta(days=i)
        sch = await sched_repo.get_day(master_id, d.weekday())
        if sch is not None and sch.is_working:
            days.append(d)
    return days


async def _begin_block_flow(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    role: str,
    settings: Settings,
) -> None:
    await state.clear()
    if role == "admin":
        masters = await MasterRepository(session).list_active()
        if not masters:
            await query.answer("Нет активных мастеров", show_alert=True)
            return
        if len(masters) == 1:
            await state.update_data(master_id=masters[0].id)
            await state.set_state(BlockSlotStates.select_date)
            days = await _working_dates(session, settings, masters[0].id)
            if not days:
                await query.message.edit_text(
                    "Нет рабочих дней в календаре.", reply_markup=cabinet_menu()
                )
                await state.clear()
                return
            await query.message.edit_text(
                "Выберите дату для блокировки:",
                reply_markup=_dates_keyboard(days, admin_flow=True),
            )
            return
        await state.set_state(BlockSlotStates.select_master)
        await query.message.edit_text(
            "Выберите мастера:",
            reply_markup=_masters_keyboard(masters),
        )
        return

    master = await MasterRepository(session).get_by_user_id(db_user.id)
    if master is None:
        await query.answer("Профиль мастера не найден", show_alert=True)
        return
    await state.update_data(master_id=master.id)
    await state.set_state(BlockSlotStates.select_date)
    days = await _working_dates(session, settings, master.id)
    if not days:
        await query.message.edit_text(
            "Нет рабочих дней в календаре.", reply_markup=cabinet_menu()
        )
        await state.clear()
        return
    await query.message.edit_text(
        "Выберите дату для блокировки:",
        reply_markup=_dates_keyboard(days, admin_flow=False),
    )


@router.callback_query(F.data.in_({"cab:block", "adm:block"}))
async def start_block(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    role: str,
    settings: Settings,
) -> None:
    await _begin_block_flow(query, state, session, db_user, role, settings)
    await query.answer()


@router.callback_query(
    F.data.startswith("blk:mst:"), StateFilter(BlockSlotStates.select_master)
)
async def block_pick_master(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    master_id = int(query.data.split(":")[-1])
    await state.update_data(master_id=master_id)
    await state.set_state(BlockSlotStates.select_date)
    days = await _working_dates(session, settings, master_id)
    if not days:
        await query.message.edit_text(
            "Нет рабочих дней в календаре.", reply_markup=cabinet_menu()
        )
        await state.clear()
        await query.answer()
        return
    await query.message.edit_text(
        "Выберите дату для блокировки:",
        reply_markup=_dates_keyboard(days, admin_flow=True),
    )
    await query.answer()


@router.callback_query(F.data == "blk:back:mst")
async def block_back_master(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    role: str,
) -> None:
    if role != "admin":
        await query.answer()
        return
    masters = await MasterRepository(session).list_active()
    await state.set_state(BlockSlotStates.select_master)
    await query.message.edit_text(
        "Выберите мастера:",
        reply_markup=_masters_keyboard(masters),
    )
    await query.answer()


@router.callback_query(
    F.data.startswith("blk:date:"), StateFilter(BlockSlotStates.select_date)
)
async def block_pick_date(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    day = date.fromisoformat(query.data.split(":")[-1])
    data = await state.get_data()
    master_id = int(data["master_id"])
    step = await _slot_step_min(session)
    slots = await SlotService(session, settings).get_all_slot_starts(
        master_id, day, step
    )
    if not slots:
        await query.answer("Нет слотов на этот день", show_alert=True)
        return
    await state.update_data(block_date=day.isoformat(), slot_step=step, selected_slots=[])
    await state.set_state(BlockSlotStates.select_slots)
    await query.message.edit_text(
        f"Дата {day.strftime('%d.%m.%Y')}: отметьте слоты для блокировки, затем «Подтвердить».",
        reply_markup=_slots_keyboard(day, slots, set()),
    )
    await query.answer()


@router.callback_query(F.data == "blk:back:date")
async def block_back_date(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    role: str,
) -> None:
    data = await state.get_data()
    master_id = int(data["master_id"])
    await state.set_state(BlockSlotStates.select_date)
    days = await _working_dates(session, settings, master_id)
    await query.message.edit_text(
        "Выберите дату для блокировки:",
        reply_markup=_dates_keyboard(days, admin_flow=role == "admin"),
    )
    await query.answer()


@router.callback_query(
    F.data.startswith("blk:tog:"), StateFilter(BlockSlotStates.select_slots)
)
async def block_toggle_slot(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    parts = query.data.split(":")
    day = date.fromisoformat(parts[2])
    slot_key = parts[3]
    data = await state.get_data()
    master_id = int(data["master_id"])
    step = int(data["slot_step"])
    selected = set(data.get("selected_slots") or [])
    if slot_key in selected:
        selected.remove(slot_key)
    else:
        selected.add(slot_key)
    await state.update_data(selected_slots=sorted(selected))
    slots = await SlotService(session, settings).get_all_slot_starts(
        master_id, day, step
    )
    await query.message.edit_text(
        f"Дата {day.strftime('%d.%m.%Y')}: отметьте слоты для блокировки, затем «Подтвердить».",
        reply_markup=_slots_keyboard(day, slots, selected),
    )
    await query.answer()


@router.callback_query(F.data == "blk:done", StateFilter(BlockSlotStates.select_slots))
async def block_confirm_prompt(
    query: CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    selected = data.get("selected_slots") or []
    if not selected:
        await query.answer("Выберите хотя бы один слот", show_alert=True)
        return
    day = date.fromisoformat(data["block_date"])
    lines = ", ".join(sorted(selected))
    await state.set_state(BlockSlotStates.confirm)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=_("btn_confirm"), callback_data="blk:save"),
                InlineKeyboardButton(text=_("btn_cancel"), callback_data="menu:main"),
            ],
            [InlineKeyboardButton(text=_("btn_back"), callback_data="blk:back:slots")],
        ]
    )
    await query.message.edit_text(
        f"Заблокировать {day.strftime('%d.%m.%Y')} в {lines}?",
        reply_markup=kb,
    )
    await query.answer()


@router.callback_query(F.data == "blk:back:slots")
async def block_back_slots(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    data = await state.get_data()
    day = date.fromisoformat(data["block_date"])
    master_id = int(data["master_id"])
    step = int(data["slot_step"])
    selected = set(data.get("selected_slots") or [])
    await state.set_state(BlockSlotStates.select_slots)
    slots = await SlotService(session, settings).get_all_slot_starts(
        master_id, day, step
    )
    await query.message.edit_text(
        f"Дата {day.strftime('%d.%m.%Y')}: отметьте слоты для блокировки, затем «Подтвердить».",
        reply_markup=_slots_keyboard(day, slots, selected),
    )
    await query.answer()


@router.callback_query(F.data == "blk:save", StateFilter(BlockSlotStates.confirm))
async def block_save(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    master_id = int(data["master_id"])
    day = date.fromisoformat(data["block_date"])
    step = int(data["slot_step"])
    selected: list[str] = data.get("selected_slots") or []

    appt_repo = AppointmentRepository(session)
    blocked_repo = BlockedSlotRepository(session)
    appointments = await appt_repo.list_for_master_on_date(master_id, day)

    created = 0
    skipped_busy = 0
    skipped_dup = 0

    for slot_key in sorted(selected):
        start = datetime.strptime(slot_key, "%H:%M").time()
        end = _add_minutes(start, step)
        busy = any(
            appt.start_time < end and appt.end_time > start for appt in appointments
        )
        if busy:
            skipped_busy += 1
            continue
        if await blocked_repo.overlaps(master_id, day, start, end):
            skipped_dup += 1
            continue
        await blocked_repo.add(
            BlockedSlot(
                master_id=master_id,
                date=day,
                start_time=start,
                end_time=end,
                reason=None,
            )
        )
        created += 1

    await state.clear()
    parts = [f"Заблокировано интервалов: {created}."]
    if skipped_busy:
        parts.append(f"Пропущено (есть запись): {skipped_busy}.")
    if skipped_dup:
        parts.append(f"Уже заблокировано: {skipped_dup}.")
    await query.message.edit_text("\n".join(parts), reply_markup=cabinet_menu())
    await query.answer()
