"""Репозиторий пользователей."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def upsert(
        self,
        telegram_id: int,
        username: str | None,
        language_code: str | None = None,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                language_code=language_code,
            )
            self._session.add(user)
        else:
            user.username = username
            if language_code is not None:
                user.language_code = language_code
        await self._session.flush()
        return user

    async def set_language(self, user: User, language_code: str) -> None:
        user.language_code = language_code
        await self._session.flush()

    async def list_active_telegram_ids(self) -> list[int]:
        result = await self._session.execute(
            select(User.telegram_id).where(User.is_active.is_(True))
        )
        return list(result.scalars().all())
