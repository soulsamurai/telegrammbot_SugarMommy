"""Подстановка locale пользователя для gettext."""

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from backend.bot.i18n import i18n
from db.models.user import User


class LocaleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("db_user")
        locale = (user.language_code if user and user.language_code else None) or data.get(
            "locale", "ru"
        )
        data["locale"] = locale
        with i18n.use_locale(locale):
            return await handler(event, data)
