"""Старт, выбор языка, главное меню."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from backend.bot.i18n import SUPPORTED_LOCALES
from backend.bot.keyboards.common import language_keyboard, main_menu_keyboard
from backend.bot.states.booking import LanguageStates
from db.models.user import User
from db.repositories.user_repo import UserRepository

router = Router(name="start")


async def show_main(message: Message, role: str) -> None:
    await message.answer(_("menu_book"), reply_markup=main_menu_keyboard(role))


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    session: AsyncSession,
    db_user: User,
    role: str,
    state: FSMContext,
) -> None:
    await state.clear()
    if db_user.language_code not in SUPPORTED_LOCALES:
        await message.answer(_("welcome"), reply_markup=language_keyboard())
        await state.set_state(LanguageStates.choosing)
        return
    await show_main(message, role)


@router.callback_query(F.data.startswith("lang:"))
async def set_language(
    query: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    role: str,
    state: FSMContext,
) -> None:
    locale = query.data.split(":")[1]
    if locale not in SUPPORTED_LOCALES:
        await query.answer()
        return
    repo = UserRepository(session)
    await repo.set_language(db_user, locale)
    db_user.language_code = locale
    await state.clear()
    await query.message.edit_text(_("welcome"))
    await query.message.answer(_("menu_book"), reply_markup=main_menu_keyboard(role))
    await query.answer()


@router.callback_query(F.data == "menu:main")
async def menu_main(query: CallbackQuery, role: str, state: FSMContext) -> None:
    await state.clear()
    await query.message.edit_text(_("menu_book"))
    await query.message.answer(_("menu_book"), reply_markup=main_menu_keyboard(role))
    await query.answer()


@router.callback_query(F.data == "menu:lang")
async def menu_language(query: CallbackQuery, state: FSMContext) -> None:
    await query.message.edit_text(_("welcome"), reply_markup=language_keyboard())
    await state.set_state(LanguageStates.choosing)
    await query.answer()
