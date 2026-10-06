"""Отправка уведомлений мастерам, клиентам, админам."""

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from backend.bot.i18n import i18n as app_i18n
from backend.services.i18n_helpers import service_name
from db.models.appointment import Appointment
from db.models.master import Master
from db.models.user import User


def _with_locale(user: User, coro_factory):
    """Контекст gettext для языка пользователя."""
    locale = user.language_code or "ru"
    with app_i18n.use_locale(locale):
        return coro_factory()


async def notify_master_new_booking(bot: Bot, master: Master, appt: Appointment) -> None:
    tg_id = master.user.telegram_id
    client_label = appt.client.username or str(appt.client.telegram_id)
    locale = master.user.language_code or "ru"
    with app_i18n.use_locale(locale):
        text = _("master_new_booking").format(
            client=f"@{client_label}" if appt.client.username else client_label,
            service=service_name(appt.service, locale),
            date=appt.date.strftime("%d.%m"),
            time=appt.start_time.strftime("%H:%M"),
        )
    await bot.send_message(tg_id, text)


async def notify_master_reschedule(
    bot: Bot, old: Appointment, new: Appointment
) -> None:
    master = new.master
    if master is None:
        return
    locale = master.user.language_code or "ru"
    client_label = new.client.username or str(new.client.telegram_id)
    with app_i18n.use_locale(locale):
        text = _("master_reschedule").format(
            client=f"@{client_label}" if new.client.username else client_label,
            old_date=old.date.strftime("%d.%m"),
            old_time=old.start_time.strftime("%H:%M"),
            new_date=new.date.strftime("%d.%m"),
            new_time=new.start_time.strftime("%H:%M"),
        )
    await bot.send_message(master.user.telegram_id, text)


async def notify_master_cancel(bot: Bot, master: Master, appt: Appointment) -> None:
    locale = master.user.language_code or "ru"
    client_label = appt.client.username or str(appt.client.telegram_id)
    with app_i18n.use_locale(locale):
        text = _("master_cancel").format(
            client=f"@{client_label}" if appt.client.username else client_label,
            date=appt.date.strftime("%d.%m"),
            time=appt.start_time.strftime("%H:%M"),
        )
    await bot.send_message(master.user.telegram_id, text)


async def notify_client_cancelled_by_master(bot: Bot, appt: Appointment) -> None:
    locale = appt.client.language_code or "ru"
    with app_i18n.use_locale(locale):
        text = _("client_cancel_by_master").format(
            date=appt.date.strftime("%d.%m"),
            time=appt.start_time.strftime("%H:%M"),
        )
    await bot.send_message(appt.client.telegram_id, text)


async def send_confirm_visit_prompt(bot: Bot, appt: Appointment) -> None:
    locale = appt.client.language_code or "ru"
    with app_i18n.use_locale(locale):
        text = _("confirm_visit_prompt").format(
            date=appt.date.strftime("%d.%m"),
            time=appt.start_time.strftime("%H:%M"),
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=_("confirm_visit_yes"),
                        callback_data=f"visit:yes:{appt.id}",
                    ),
                    InlineKeyboardButton(
                        text=_("confirm_visit_no"),
                        callback_data=f"visit:no:{appt.id}",
                    ),
                ]
            ]
        )
    await bot.send_message(appt.client.telegram_id, text, reply_markup=kb)


async def send_waitlist_offer(bot: Bot, client: User, date_str: str, time_str: str, entry_id: int) -> None:
    locale = client.language_code or "ru"
    with app_i18n.use_locale(locale):
        text = _("waitlist_freed").format(date=date_str, time=time_str)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=_("btn_take_slot"), callback_data=f"waitlist:take:{entry_id}"
                    ),
                    InlineKeyboardButton(
                        text=_("btn_decline_slot"), callback_data=f"waitlist:decline:{entry_id}"
                    ),
                ]
            ]
        )
    await bot.send_message(client.telegram_id, text, reply_markup=kb)


async def alert_admins_unconfirmed(bot: Bot, admin_ids: list[int], appt: Appointment) -> None:
    client_label = appt.client.username or str(appt.client.telegram_id)
    text = (
        f"Запись #{appt.id} ({client_label}, "
        f"{appt.date.strftime('%d.%m')} {appt.start_time.strftime('%H:%M')}) "
        "не подтверждена. Свяжитесь с клиентом."
    )
    for admin_tg in admin_ids:
        await bot.send_message(admin_tg, text)
