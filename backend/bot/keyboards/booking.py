"""Клавиатуры сценария записи."""

from datetime import date, time

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from backend.services.i18n_helpers import service_name
from db.models.master import Master
from db.models.service import Service


def services_keyboard(
    services: list[Service], page: int, total: int, per_page: int, locale: str
) -> InlineKeyboardMarkup:
    rows = []
    for svc in services:
        label = f"{service_name(svc, locale)} — {svc.price} / {svc.duration_min}m"
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"book:svc:{svc.id}")]
        )
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="◀", callback_data=f"book:svc_page:{page - 1}")
        )
    if (page + 1) * per_page < total:
        nav.append(
            InlineKeyboardButton(text="▶", callback_data=f"book:svc_page:{page + 1}")
        )
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text=_("btn_main_menu"), callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def masters_keyboard(masters: list[Master]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=m.name, callback_data=f"book:mst:{m.id}")]
        for m in masters
    ]
    rows.append([InlineKeyboardButton(text=_("btn_back"), callback_data="book:back:svc")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dates_keyboard(dates: list[date]) -> InlineKeyboardMarkup:
    rows = []
    row: list[InlineKeyboardButton] = []
    for i, d in enumerate(dates, start=1):
        row.append(
            InlineKeyboardButton(
                text=d.strftime("%d.%m"),
                callback_data=f"book:date:{d.isoformat()}",
            )
        )
        if i % 4 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=_("btn_back"), callback_data="book:back:mst")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def times_keyboard(slots: list[time], day: date) -> InlineKeyboardMarkup:
    rows = []
    row: list[InlineKeyboardButton] = []
    for i, slot in enumerate(slots, start=1):
        row.append(
            InlineKeyboardButton(
                text=slot.strftime("%H:%M"),
                callback_data=f"book:time:{day.isoformat()}:{slot.strftime('%H:%M')}",
            )
        )
        if i % 4 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=_("btn_back"), callback_data="book:back:date")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def waitlist_keyboard(
    day: date, slot: time, master_id: int, service_id: int
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_("btn_join_waitlist"),
                    callback_data=(
                        f"waitlist:join2:{master_id}:{service_id}:"
                        f"{day.isoformat()}:{slot.strftime('%H:%M')}"
                    ),
                )
            ],
            [InlineKeyboardButton(text=_("btn_main_menu"), callback_data="menu:main")],
        ]
    )


def booking_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=_("btn_confirm"), callback_data="book:confirm"),
                InlineKeyboardButton(text=_("btn_cancel"), callback_data="menu:main"),
            ]
        ]
    )
