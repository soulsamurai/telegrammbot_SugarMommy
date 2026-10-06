"""Фильтры ролей."""

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject


class RoleFilter(BaseFilter):
    def __init__(self, *roles: str) -> None:
        self.roles = roles

    async def __call__(self, event: TelegramObject, role: str | None = None) -> bool:
        return role in self.roles
