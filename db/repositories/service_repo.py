"""Репозиторий услуг."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.service import Service


class ServiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, service_id: int) -> Service | None:
        return await self._session.get(Service, service_id)

    async def list_active_paginated(self, offset: int, limit: int) -> tuple[list[Service], int]:
        count_q = await self._session.execute(
            select(func.count()).select_from(Service).where(Service.is_active.is_(True))
        )
        total = int(count_q.scalar_one())
        result = await self._session.execute(
            select(Service)
            .where(Service.is_active.is_(True))
            .order_by(Service.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_all(self) -> list[Service]:
        result = await self._session.execute(select(Service).order_by(Service.id))
        return list(result.scalars().all())

    async def create(self, **kwargs: object) -> Service:
        service = Service(**kwargs)  # type: ignore[arg-type]
        self._session.add(service)
        await self._session.flush()
        return service

    async def update(self, service: Service, **kwargs: object) -> Service:
        for key, value in kwargs.items():
            setattr(service, key, value)
        await self._session.flush()
        return service
