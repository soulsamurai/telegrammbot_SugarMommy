"""Репозиторий графика работы."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.schedule import Schedule


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_master(self, master_id: int) -> list[Schedule]:
        result = await self._session.execute(
            select(Schedule).where(Schedule.master_id == master_id).order_by(Schedule.day_of_week)
        )
        return list(result.scalars().all())

    async def get_day(self, master_id: int, day_of_week: int) -> Schedule | None:
        result = await self._session.execute(
            select(Schedule).where(
                Schedule.master_id == master_id,
                Schedule.day_of_week == day_of_week,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_day(
        self,
        master_id: int,
        day_of_week: int,
        start_time,
        end_time,
        is_working: bool,
    ) -> Schedule:
        row = await self.get_day(master_id, day_of_week)
        if row is None:
            row = Schedule(
                master_id=master_id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                is_working=is_working,
            )
            self._session.add(row)
        else:
            row.start_time = start_time
            row.end_time = end_time
            row.is_working = is_working
        await self._session.flush()
        return row
