"""Общие inline-клавиатуры."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from backend.bot.i18n import SUPPORTED_LOCALES


def language_keyboard() -> InlineKeyboardMarkup:
    labels = {"ru": "🇷🇺 Русский", "uz": "🇺🇿 O'zbek", "en": "🇬🇧 English"}
    rows = [
        [InlineKeyboardButton(text=labels[loc], callback_data=f"lang:{loc}")]
        for loc in SUPPORTED_LOCALES
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu_keyboard(role: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=_("menu_book"), callback_data="menu:book")],
        [InlineKeyboardButton(text=_("menu_appointments"), callback_data="menu:appts")],
        [InlineKeyboardButton(text=_("menu_language"), callback_data="menu:lang")],
    ]
    if role in ("master", "admin"):
        rows.append(
            [InlineKeyboardButton(text=_("menu_cabinet"), callback_data="menu:cabinet")]
        )
    if role == "admin":
        rows.append(
            [InlineKeyboardButton(text=_("menu_admin"), callback_data="menu:admin")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("btn_main_menu"), callback_data="menu:main")]
        ]
    )


def confirm_cancel_keyboard(confirm_data: str, cancel_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=_("btn_confirm"), callback_data=confirm_data),
                InlineKeyboardButton(text=_("btn_cancel"), callback_data=cancel_data),
            ]
        ]
    )
