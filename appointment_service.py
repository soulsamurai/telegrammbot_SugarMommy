"""Бизнес-логика записей: создание, отмена, перенос."""

from datetime import date, datetime, timedelta, time

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from backend.services.slot_service import SlotService, _add_minutes
from db.models.appointment import Appointment
from db.models.enums import AppointmentStatus, ReminderStatus, ReminderType
from db.models.reminder import Reminder
from db.repositories.appointment_repo import AppointmentRepository
from db.repositories.reminder_repo import ReminderRepository
from db.repositories.service_repo import ServiceRepository


class AppointmentPolicyError(Exception):
    """Нарушение правил отмены/переноса."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AppointmentService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = AppointmentRepository(session)
        self._services = ServiceRepository(session)
        self._reminders = ReminderRepository(session)
        self._slots = SlotService(session, settings)

    def _appointment_start(self, appt: Appointment) -> datetime:
        return datetime.combine(
            appt.date, appt.start_time, tzinfo=self._settings.tz
        )

    def ensure_can_modify(self, appt: Appointment, now: datetime | None = None) -> None:
        now = now or datetime.now(self._settings.tz)
        start = self._appointment_start(appt)
        min_delta = timedelta(hours=self._settings.cancel_min_hours)
        if start - now < min_delta:
            raise AppointmentPolicyError("too_late")

    async def create(
        self,
        client_id: int,
        master_id: int,
        service_id: int,
        day: date,
        start: time,
    ) -> Appointment:
        service = await self._services.get_by_id(service_id)
        if service is None:
            raise ValueError("service_not_found")
        end = _add_minutes(start, service.duration_min)

        if await self._repo.overlaps(master_id, day, start, end):
            raise ValueError("slot_taken")

        free = await self._slots.get_free_slots(master_id, day, service.duration_min)
        if start not in free:
            raise ValueError("slot_unavailable")

        appt = Appointment(
            client_id=client_id,
            master_id=master_id,
            service_id=service_id,
            date=day,
            start_time=start,
            end_time=end,
            status=AppointmentStatus.confirmed,
        )
        appt = await self._repo.create(appt)
        await self._session.flush()
        await self._schedule_confirm_reminder(appt)
        return appt

    async def _schedule_confirm_reminder(self, appt: Appointment) -> None:
        start = self._appointment_start(appt)
        scheduled = start - timedelta(hours=self._settings.confirm_visit_hours)
        await self._reminders.add(
            Reminder(
                appointment_id=appt.id,
                type=ReminderType.confirm_visit,
                scheduled_at=scheduled,
                status=ReminderStatus.pending,
            )
        )

    async def cancel_by_client(self, appt: Appointment) -> Appointment:
        self.ensure_can_modify(appt)
        appt.status = AppointmentStatus.cancelled_by_client
        await self._reminders.cancel_for_appointment(appt.id)
        await self._session.flush()
        return appt

    async def cancel_by_master(self, appt: Appointment) -> Appointment:
        appt.status = AppointmentStatus.cancelled_by_master
        await self._reminders.cancel_for_appointment(appt.id)
        await self._session.flush()
        return appt

    async def reschedule(
        self, appt: Appointment, new_day: date, new_start: time
    ) -> Appointment:
        self.ensure_can_modify(appt)
        service = await self._services.get_by_id(appt.service_id)
        if service is None:
            raise ValueError("service_not_found")
        new_end = _add_minutes(new_start, service.duration_min)
        if await self._repo.overlaps(
            appt.master_id, new_day, new_start, new_end, exclude_id=appt.id
        ):
            raise ValueError("slot_taken")

        appt.status = AppointmentStatus.rescheduled
        old_id = appt.id
        await self._reminders.cancel_for_appointment(old_id)

        new_appt = Appointment(
            client_id=appt.client_id,
            master_id=appt.master_id,
            service_id=appt.service_id,
            date=new_day,
            start_time=new_start,
            end_time=new_end,
            status=AppointmentStatus.confirmed,
        )
        await self._repo.create(new_appt)
        await self._schedule_confirm_reminder(new_appt)
        return new_appt

    async def mark_completed(self, appt: Appointment) -> None:
        appt.status = AppointmentStatus.completed
        service = appt.service
        if service and service.reminder_days > 0:
            scheduled = datetime.now(self._settings.tz) + timedelta(
                days=service.reminder_days
            )
            await self._reminders.add(
                Reminder(
                    appointment_id=None,
                    client_id=appt.client_id,
                    service_id=appt.service_id,
                    type=ReminderType.repeat_visit,
                    scheduled_at=scheduled,
                    status=ReminderStatus.pending,
                )
            )
        await self._session.flush()

    async def confirm_visit(self, appt: Appointment) -> None:
        appt.visit_confirmed_at = datetime.now(self._settings.tz)
        await self._session.flush()
