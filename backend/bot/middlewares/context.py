"""DI: settings и очередь рассылок в data."""

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from backend.config import Settings
from backend.services.broadcast_service import BroadcastQueue


class AppContextMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings, broadcast_queue: BroadcastQueue) -> None:
        self._settings = settings
        self._broadcast_queue = broadcast_queue

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["settings"] = self._settings
        data["broadcast_queue"] = self._broadcast_queue
        return await handler(event, data)
