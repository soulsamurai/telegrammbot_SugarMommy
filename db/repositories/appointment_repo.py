"""Репозиторий записей."""

from datetime import date, datetime, time

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models.appointment import Appointment
from db.models.enums import AppointmentStatus


ACTIVE_STATUSES = (
    AppointmentStatus.pending,
    AppointmentStatus.confirmed,
)


class AppointmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, appointment_id: int) -> Appointment | None:
        result = await self._session.execute(
            select(Appointment)
            .where(Appointment.id == appointment_id)
            .options(
                selectinload(Appointment.client),
                selectinload(Appointment.master).selectinload("user"),
                selectinload(Appointment.service),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, appointment: Appointment) -> Appointment:
        self._session.add(appointment)
        await self._session.flush()
        return appointment

    async def list_upcoming_for_client(self, client_id: int) -> list[Appointment]:
        today = date.today()
        result = await self._session.execute(
            select(Appointment)
            .where(
                Appointment.client_id == client_id,
                Appointment.status.in_(ACTIVE_STATUSES),
                or_(
                    Appointment.date > today,
                    and_(Appointment.date == today, Appointment.start_time >= datetime.now().time()),
                ),
            )
            .options(
                selectinload(Appointment.master),
                selectinload(Appointment.service),
            )
            .order_by(Appointment.date, Appointment.start_time)
        )
        return list(result.scalars().all())

    async def list_for_master_on_date(self, master_id: int, day: date) -> list[Appointment]:
        result = await self._session.execute(
            select(Appointment)
            .where(
                Appointment.master_id == master_id,
                Appointment.date == day,
                Appointment.status.in_(ACTIVE_STATUSES),
            )
            .order_by(Appointment.start_time)
        )
        return list(result.scalars().all())

    async def list_between(
        self,
        date_from: date,
        date_to: date,
        master_id: int | None = None,
    ) -> list[Appointment]:
        stmt = (
            select(Appointment)
            .where(Appointment.date >= date_from, Appointment.date <= date_to)
            .options(
                selectinload(Appointment.client),
                selectinload(Appointment.master),
                selectinload(Appointment.service),
            )
            .order_by(Appointment.date, Appointment.start_time)
        )
        if master_id is not None:
            stmt = stmt.where(Appointment.master_id == master_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active_on_master_date(
        self, master_id: int, day: date
    ) -> list[Appointment]:
        return await self.list_for_master_on_date(master_id, day)

    async def overlaps(
        self,
        master_id: int,
        day: date,
        start: time,
        end: time,
        exclude_id: int | None = None,
    ) -> bool:
        stmt = select(Appointment).where(
            Appointment.master_id == master_id,
            Appointment.date == day,
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.start_time < end,
            Appointment.end_time > start,
        )
        if exclude_id:
            stmt = stmt.where(Appointment.id != exclude_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def clients_for_date(self, day: date) -> list[int]:
        result = await self._session.execute(
            select(Appointment.client_id)
            .where(
                Appointment.date == day,
                Appointment.status.in_(ACTIVE_STATUSES),
            )
            .distinct()
        )
        return list(result.scalars().all())

    async def need_confirm_reminder(
        self, now: datetime, window_start: datetime, window_end: datetime
    ) -> list[Appointment]:
        """Записи, для которых пора отправить подтверждение визита (anti-no-show)."""
        result = await self._session.execute(
            select(Appointment)
            .where(
                Appointment.status.in_(ACTIVE_STATUSES),
                Appointment.visit_confirmed_at.is_(None),
            )
            .options(selectinload(Appointment.client), selectinload(Appointment.service))
        )
        appointments = list(result.scalars().all())
        matched: list[Appointment] = []
        for appt in appointments:
            start_dt = datetime.combine(appt.date, appt.start_time, tzinfo=now.tzinfo)
            if window_start <= start_dt <= window_end:
                matched.append(appt)
        return matched

    async def unconfirmed_before(
        self, now: datetime, hours_before: float
    ) -> list[Appointment]:
        result = await self._session.execute(
            select(Appointment)
            .where(
                Appointment.status.in_(ACTIVE_STATUSES),
                Appointment.visit_confirmed_at.is_(None),
            )
            .options(
                selectinload(Appointment.client),
                selectinload(Appointment.master).selectinload("user"),
            )
        )
        out: list[Appointment] = []
        for appt in result.scalars().all():
            start_dt = datetime.combine(appt.date, appt.start_time, tzinfo=now.tzinfo)
            delta_hours = (start_dt - now).total_seconds() / 3600
            if 0 < delta_hours <= hours_before:
                out.append(appt)
        return out

    async def past_active(self, now: datetime) -> list[Appointment]:
        today = now.date()
        now_time = now.time()
        result = await self._session.execute(
            select(Appointment)
            .where(Appointment.status.in_(ACTIVE_STATUSES))
            .options(selectinload(Appointment.client), selectinload(Appointment.service))
        )
        past: list[Appointment] = []
        for appt in result.scalars().all():
            if appt.date < today or (appt.date == today and appt.end_time <= now_time):
                past.append(appt)
        return past
