"""Определение роли пользователя и синхронизация staff из конфига."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from db.models.enums import MasterRole
from db.models.user import User
from db.repositories.master_repo import MasterRepository
from db.repositories.user_repo import UserRepository


class RoleService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)
        self._masters = MasterRepository(session)

    async def ensure_staff_profiles(self) -> None:
        """Создаёт User/Master для ADMIN_IDS и MASTER_IDS из .env."""
        for tg_id in self._settings.admin_ids:
            user = await self._users.upsert(tg_id, username=None)
            master = await self._masters.get_by_user_id(user.id)
            if master is None:
                await self._masters.create(
                    user_id=user.id,
                    name=f"Admin {tg_id}",
                    role=MasterRole.admin,
                )
            else:
                master.role = MasterRole.admin
                master.is_active = True

        for tg_id in self._settings.master_ids:
            if tg_id in self._settings.admin_ids:
                continue
            user = await self._users.upsert(tg_id, username=None)
            master = await self._masters.get_by_user_id(user.id)
            if master is None:
                await self._masters.create(
                    user_id=user.id,
                    name=f"Master {tg_id}",
                    role=MasterRole.master,
                )

    def resolve_role(self, user: User) -> str:
        """client | master | admin."""
        master = user.master_profile
        if master and master.is_active:
            if master.role == MasterRole.admin:
                return "admin"
            return "master"
        if user.telegram_id in self._settings.admin_ids:
            return "admin"
        if user.telegram_id in self._settings.master_ids:
            return "master"
        return "client"
