"""Репозиторий заблокированных слотов."""

from datetime import date, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.blocked_slot import BlockedSlot


class BlockedSlotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_master_date(self, master_id: int, day: date) -> list[BlockedSlot]:
        result = await self._session.execute(
            select(BlockedSlot)
            .where(BlockedSlot.master_id == master_id, BlockedSlot.date == day)
            .order_by(BlockedSlot.start_time)
        )
        return list(result.scalars().all())

    async def add(self, slot: BlockedSlot) -> BlockedSlot:
        self._session.add(slot)
        await self._session.flush()
        return slot

    async def delete(self, slot_id: int) -> None:
        slot = await self._session.get(BlockedSlot, slot_id)
        if slot:
            await self._session.delete(slot)

    async def overlaps(
        self, master_id: int, day: date, start: time, end: time
    ) -> bool:
        result = await self._session.execute(
            select(BlockedSlot).where(
                BlockedSlot.master_id == master_id,
                BlockedSlot.date == day,
                BlockedSlot.start_time < end,
                BlockedSlot.end_time > start,
            )
        )
        return result.scalar_one_or_none() is not None
