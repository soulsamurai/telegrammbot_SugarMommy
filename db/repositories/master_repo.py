"""Репозиторий мастеров."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models.enums import MasterRole
from db.models.master import Master
from db.models.service import Service


class MasterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: int) -> Master | None:
        result = await self._session.execute(
            select(Master)
            .where(Master.user_id == user_id)
            .options(selectinload(Master.user), selectinload(Master.services))
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, master_id: int) -> Master | None:
        result = await self._session.execute(
            select(Master)
            .where(Master.id == master_id)
            .options(selectinload(Master.user), selectinload(Master.services))
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Master]:
        result = await self._session.execute(
            select(Master)
            .where(Master.is_active.is_(True))
            .options(selectinload(Master.services), selectinload(Master.user))
            .order_by(Master.name)
        )
        return list(result.scalars().all())

    async def list_for_service(self, service_id: int) -> list[Master]:
        result = await self._session.execute(
            select(Master)
            .join(Master.services)
            .where(Service.id == service_id, Master.is_active.is_(True))
            .options(selectinload(Master.user))
            .order_by(Master.name)
        )
        return list(result.unique().scalars().all())

    async def create(
        self,
        user_id: int,
        name: str,
        role: MasterRole,
        service_ids: list[int] | None = None,
    ) -> Master:
        master = Master(user_id=user_id, name=name, role=role)
        if service_ids:
            services = await self._session.execute(
                select(Service).where(Service.id.in_(service_ids))
            )
            master.services = list(services.scalars().all())
        self._session.add(master)
        await self._session.flush()
        return master
