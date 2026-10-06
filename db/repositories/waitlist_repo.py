"""Репозиторий листа ожидания."""

from datetime import date, datetime, time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models.enums import WaitlistStatus
from db.models.waitlist import WaitlistEntry


class WaitlistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_position(
        self,
        master_id: int,
        service_id: int,
        preferred_date: date,
        preferred_time_start: time,
    ) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(WaitlistEntry.position), 0)).where(
                WaitlistEntry.master_id == master_id,
                WaitlistEntry.service_id == service_id,
                WaitlistEntry.preferred_date == preferred_date,
                WaitlistEntry.preferred_time_start == preferred_time_start,
                WaitlistEntry.status == WaitlistStatus.waiting,
            )
        )
        return int(result.scalar_one()) + 1

    async def add(self, entry: WaitlistEntry) -> WaitlistEntry:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def get_by_id(self, entry_id: int) -> WaitlistEntry | None:
        result = await self._session.execute(
            select(WaitlistEntry)
            .where(WaitlistEntry.id == entry_id)
            .options(
                selectinload(WaitlistEntry.client),
                selectinload(WaitlistEntry.service),
                selectinload(WaitlistEntry.master),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_client(self, client_id: int) -> list[WaitlistEntry]:
        result = await self._session.execute(
            select(WaitlistEntry)
            .where(
                WaitlistEntry.client_id == client_id,
                WaitlistEntry.status.in_(
                    (WaitlistStatus.waiting, WaitlistStatus.offered)
                ),
            )
            .order_by(WaitlistEntry.created_at)
        )
        return list(result.scalars().all())

    async def first_waiting(
        self,
        master_id: int,
        service_id: int,
        preferred_date: date,
        preferred_time_start: time,
        preferred_time_end: time,
    ) -> WaitlistEntry | None:
        result = await self._session.execute(
            select(WaitlistEntry)
            .where(
                WaitlistEntry.master_id == master_id,
                WaitlistEntry.service_id == service_id,
                WaitlistEntry.preferred_date == preferred_date,
                WaitlistEntry.preferred_time_start == preferred_time_start,
                WaitlistEntry.preferred_time_end == preferred_time_end,
                WaitlistEntry.status == WaitlistStatus.waiting,
            )
            .order_by(WaitlistEntry.position)
            .limit(1)
            .options(selectinload(WaitlistEntry.client))
        )
        return result.scalar_one_or_none()

    async def list_all_active(self) -> list[WaitlistEntry]:
        result = await self._session.execute(
            select(WaitlistEntry)
            .where(
                WaitlistEntry.status.in_(
                    (WaitlistStatus.waiting, WaitlistStatus.offered)
                )
            )
            .options(
                selectinload(WaitlistEntry.client),
                selectinload(WaitlistEntry.master),
                selectinload(WaitlistEntry.service),
            )
            .order_by(
                WaitlistEntry.preferred_date,
                WaitlistEntry.preferred_time_start,
                WaitlistEntry.position,
            )
        )
        return list(result.scalars().all())

    async def expired_offers(self, before: datetime) -> list[WaitlistEntry]:
        result = await self._session.execute(
            select(WaitlistEntry)
            .where(
                WaitlistEntry.status == WaitlistStatus.offered,
                WaitlistEntry.offered_at.is_not(None),
                WaitlistEntry.offered_at < before,
            )
            .options(selectinload(WaitlistEntry.client))
        )
        return list(result.scalars().all())
