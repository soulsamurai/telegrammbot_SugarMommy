"""Логирование входящих апдейтов."""

from typing import Any, Awaitable, Callable

import structlog
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            logger.info(
                "message",
                user=event.from_user.id if event.from_user else None,
                text=event.text,
            )
        elif isinstance(event, CallbackQuery):
            logger.info(
                "callback",
                user=event.from_user.id if event.from_user else None,
                data=event.data,
            )
        return await handler(event, data)
