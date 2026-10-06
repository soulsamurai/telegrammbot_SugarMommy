"""Панель мастера (без админ-прав)."""

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from backend.bot.filters.roles import RoleFilter
from backend.services.i18n_helpers import service_name
from db.models.user import User
from db.repositories.appointment_repo import AppointmentRepository
from db.repositories.master_repo import MasterRepository

router = Router(name="master_panel")
router.callback_query.filter(RoleFilter("master", "admin"))


def cabinet_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Мои записи", callback_data="cab:appts")],
            [InlineKeyboardButton(text="Мой график", callback_data="cab:schedule")],
            [InlineKeyboardButton(text="Блокировка слотов", callback_data="cab:block")],
            [InlineKeyboardButton(text=_("btn_main_menu"), callback_data="menu:main")],
        ]
    )


@router.callback_query(F.data == "menu:cabinet")
async def open_cabinet(query: CallbackQuery, role: str) -> None:
    if role == "admin":
        await query.message.edit_text(
            "Администратор: используйте «Админ-панель» или выберите действие мастера.",
            reply_markup=cabinet_menu(),
        )
    else:
        await query.message.edit_text(_("menu_cabinet"), reply_markup=cabinet_menu())
    await query.answer()


@router.callback_query(F.data == "cab:appts")
async def cabinet_appts(
    query: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    locale: str,
    role: str,
) -> None:
    master = await MasterRepository(session).get_by_user_id(db_user.id)
    if master is None and role != "admin":
        await query.answer("Профиль мастера не найден", show_alert=True)
        return
    if master is None:
        await query.answer("Выберите мастера в админ-панели", show_alert=True)
        return
    from datetime import date, timedelta

    items = await AppointmentRepository(session).list_between(
        date.today(), date.today() + timedelta(days=14), master.id
    )
    lines = [
        f"#{a.id} {a.date.strftime('%d.%m')} {a.start_time.strftime('%H:%M')} "
        f"{service_name(a.service, locale)}"
        for a in items
    ]
    await query.message.edit_text("\n".join(lines) or "Нет записей", reply_markup=cabinet_menu())
    await query.answer()


