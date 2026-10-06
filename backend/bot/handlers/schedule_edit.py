"""FSM редактирования недельного графика мастера."""

import re
from datetime import time

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from backend.bot.filters.roles import RoleFilter
from backend.bot.handlers.master import cabinet_menu
from backend.bot.states.admin import ScheduleStates
from db.models.user import User
from db.repositories.master_repo import MasterRepository
from db.repositories.schedule_repo import ScheduleRepository

router = Router(name="schedule_edit")
router.callback_query.filter(RoleFilter("master", "admin"))
router.message.filter(RoleFilter("master", "admin"))

_DOW_LABELS = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)

_HOURS_RE = re.compile(
    r"^(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})$",
    re.IGNORECASE,
)


def _masters_keyboard(masters: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=m.name, callback_data=f"sch:mst:{m.id}")]
        for m in masters
    ]
    rows.append([InlineKeyboardButton(text=_("btn_main_menu"), callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _days_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=_DOW_LABELS[dow][:3],
                callback_data=f"sch:dow:{dow}",
            )
        ]
        for dow in range(7)
    ]
    rows.append([InlineKeyboardButton(text=_("btn_back"), callback_data="sch:back:mst")])
    rows.append([InlineKeyboardButton(text=_("btn_main_menu"), callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _begin_schedule_flow(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    role: str,
) -> None:
    await state.clear()
    if role == "admin":
        masters = await MasterRepository(session).list_active()
        if not masters:
            await query.answer("Нет активных мастеров", show_alert=True)
            return
        if len(masters) == 1:
            await state.update_data(master_id=masters[0].id)
            await state.set_state(ScheduleStates.select_day)
            await query.message.edit_text(
                f"График: {masters[0].name}\nВыберите день недели:",
                reply_markup=_days_keyboard(),
            )
            return
        await state.set_state(ScheduleStates.select_master)
        await query.message.edit_text(
            "Выберите мастера для настройки графика:",
            reply_markup=_masters_keyboard(masters),
        )
        return

    master = await MasterRepository(session).get_by_user_id(db_user.id)
    if master is None:
        await query.answer("Профиль мастера не найден", show_alert=True)
        return
    await state.update_data(master_id=master.id)
    await state.set_state(ScheduleStates.select_day)
    await query.message.edit_text(
        "Выберите день недели:",
        reply_markup=_days_keyboard(),
    )


@router.callback_query(F.data.in_({"cab:schedule", "adm:schedule"}))
async def start_schedule(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    role: str,
) -> None:
    await _begin_schedule_flow(query, state, session, db_user, role)
    await query.answer()


@router.callback_query(
    F.data.startswith("sch:mst:"), StateFilter(ScheduleStates.select_master)
)
async def schedule_pick_master(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    master_id = int(query.data.split(":")[-1])
    master = await MasterRepository(session).get_by_id(master_id)
    await state.update_data(master_id=master_id)
    await state.set_state(ScheduleStates.select_day)
    name = master.name if master else f"#{master_id}"
    await query.message.edit_text(
        f"График: {name}\nВыберите день недели:",
        reply_markup=_days_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == "sch:back:mst")
async def schedule_back_master(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    role: str,
) -> None:
    if role != "admin":
        await query.answer()
        return
    masters = await MasterRepository(session).list_active()
    await state.set_state(ScheduleStates.select_master)
    await query.message.edit_text(
        "Выберите мастера для настройки графика:",
        reply_markup=_masters_keyboard(masters),
    )
    await query.answer()


@router.callback_query(
    F.data.startswith("sch:dow:"), StateFilter(ScheduleStates.select_day)
)
async def schedule_pick_day(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    dow = int(query.data.split(":")[-1])
    data = await state.get_data()
    master_id = int(data["master_id"])
    row = await ScheduleRepository(session).get_day(master_id, dow)
    if row is None or not row.is_working:
        current = "выходной (график не задан)"
    else:
        current = (
            f"{row.start_time.strftime('%H:%M')}–{row.end_time.strftime('%H:%M')} (рабочий)"
        )
    await state.update_data(day_of_week=dow)
    await state.set_state(ScheduleStates.set_hours)
    await query.message.edit_text(
        f"{_DOW_LABELS[dow]}\nТекущий режим: {current}\n\n"
        "Введите интервал `ЧЧ:ММ-ЧЧ:ММ` или слово «выходной».",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=_("btn_back"), callback_data="sch:back:day")]
            ]
        ),
    )
    await query.answer()


@router.callback_query(F.data == "sch:back:day")
async def schedule_back_day(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ScheduleStates.select_day)
    await query.message.edit_text(
        "Выберите день недели:",
        reply_markup=_days_keyboard(),
    )
    await query.answer()


@router.message(StateFilter(ScheduleStates.set_hours))
async def schedule_set_hours(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    text = (message.text or "").strip()
    data = await state.get_data()
    master_id = int(data["master_id"])
    dow = int(data["day_of_week"])
    repo = ScheduleRepository(session)

    if text.lower() in ("выходной", "off", "выходной день", "закрыто"):
        await repo.upsert_day(
            master_id,
            dow,
            start_time=time(9, 0),
            end_time=time(18, 0),
            is_working=False,
        )
        await state.set_state(ScheduleStates.select_day)
        await message.answer(
            f"{_DOW_LABELS[dow]}: выходной сохранён.\nВыберите следующий день:",
            reply_markup=_days_keyboard(),
        )
        return

    match = _HOURS_RE.match(text)
    if not match:
        await message.answer(
            "Формат: 09:00-18:00 или «выходной». Пример: 10:00–19:30"
        )
        return

    h1, m1, h2, m2 = (int(match.group(i)) for i in range(1, 5))
    start = time(h1, m1)
    end = time(h2, m2)
    if start >= end:
        await message.answer("Время начала должно быть раньше окончания.")
        return

    await repo.upsert_day(master_id, dow, start, end, True)
    await state.set_state(ScheduleStates.select_day)
    await message.answer(
        f"{_DOW_LABELS[dow]}: {start.strftime('%H:%M')}–{end.strftime('%H:%M')} сохранено.\n"
        "Выберите следующий день или вернитесь в меню:",
        reply_markup=_days_keyboard(),
    )
