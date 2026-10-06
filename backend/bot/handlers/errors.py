"""Глобальная обработка ошибок."""

import structlog
from aiogram import Router
from aiogram.types import ErrorEvent

logger = structlog.get_logger(__name__)

router = Router(name="errors")


@router.errors()
async def global_error_handler(event: ErrorEvent) -> bool:
    logger.exception("handler_error", error=str(event.exception))
    if event.update.callback_query:
        try:
            await event.update.callback_query.answer(
                "Произошла ошибка. Попробуйте позже.", show_alert=True
            )
        except Exception:  # noqa: BLE001
            pass
    elif event.update.message:
        try:
            await event.update.message.answer("Произошла ошибка. Попробуйте позже.")
        except Exception:  # noqa: BLE001
            pass
    return True
