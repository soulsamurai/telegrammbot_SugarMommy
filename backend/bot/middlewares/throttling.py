"""Простой throttling для callback и сообщений."""

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 0.4) -> None:
        self._rate_limit = rate_limit
        self._last: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            user_id = event.from_user.id
        if user_id is not None:
            now = time.monotonic()
            prev = self._last.get(user_id, 0.0)
            if now - prev < self._rate_limit:
                if isinstance(event, CallbackQuery):
                    await event.answer("…", show_alert=False)
                return None
            self._last[user_id] = now
        return await handler(event, data)
