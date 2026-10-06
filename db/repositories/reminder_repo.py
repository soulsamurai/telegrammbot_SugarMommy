"""Репозиторий напоминаний."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models.enums import ReminderStatus, ReminderType
from db.models.reminder import Reminder


class ReminderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, reminder: Reminder) -> Reminder:
        self._session.add(reminder)
        await self._session.flush()
        return reminder

    async def pending_due(self, now: datetime) -> list[Reminder]:
        result = await self._session.execute(
            select(Reminder)
            .where(
                Reminder.status == ReminderStatus.pending,
                Reminder.scheduled_at <= now,
            )
            .options(
                selectinload(Reminder.appointment).selectinload("client"),
                selectinload(Reminder.appointment).selectinload("service"),
            )
        )
        return list(result.scalars().all())

    async def cancel_for_appointment(self, appointment_id: int) -> None:
        result = await self._session.execute(
            select(Reminder).where(
                Reminder.appointment_id == appointment_id,
                Reminder.status == ReminderStatus.pending,
            )
        )
        for rem in result.scalars().all():
            rem.status = ReminderStatus.cancelled

    async def has_confirm_sent(self, appointment_id: int) -> bool:
        result = await self._session.execute(
            select(Reminder).where(
                Reminder.appointment_id == appointment_id,
                Reminder.type == ReminderType.confirm_visit,
                Reminder.status == ReminderStatus.sent,
            )
        )
        return result.scalar_one_or_none() is not None
