"""Middleware: пользователь, роль, locale hook."""

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from backend.config import Settings
from backend.services.role_service import RoleService
from db.models.master import Master
from db.models.user import User
from db.repositories.user_repo import UserRepository


class UserRoleMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = None
        if isinstance(event, Message):
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            tg_user = event.from_user

        if tg_user is None:
            return await handler(event, data)

        session: AsyncSession = data["session"]
        repo = UserRepository(session)
        user = await repo.upsert(tg_user.id, tg_user.username)
        # подгружаем master_profile
        result = await session.execute(
            select(User)
            .where(User.id == user.id)
            .options(selectinload(User.master_profile).selectinload(Master.services))
        )
        user = result.scalar_one()

        role_service = RoleService(session, self._settings)
        await role_service.ensure_staff_profiles()
        role = role_service.resolve_role(user)

        data["db_user"] = user
        data["role"] = role
        data["locale"] = user.language_code or "ru"
        return await handler(event, data)
