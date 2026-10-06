"""Расчёт свободных слотов мастера."""

from datetime import date, datetime, timedelta, time

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from db.repositories.appointment_repo import AppointmentRepository
from db.repositories.blocked_repo import BlockedSlotRepository
from db.repositories.schedule_repo import ScheduleRepository


def _add_minutes(t: time, minutes: int) -> time:
    dt = datetime.combine(date.today(), t) + timedelta(minutes=minutes)
    return dt.time()


def _time_ranges_overlap(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    return a_start < b_end and a_end > b_start


class SlotService:
    """Сервис доступных временных слотов с учётом графика, записей и блокировок."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._schedules = ScheduleRepository(session)
        self._appointments = AppointmentRepository(session)
        self._blocked = BlockedSlotRepository(session)

    async def date_has_availability(
        self, master_id: int, day: date, duration_min: int
    ) -> bool:
        slots = await self.get_free_slots(master_id, day, duration_min)
        return len(slots) > 0

    async def get_free_slots(
        self, master_id: int, day: date, duration_min: int
    ) -> list[time]:
        dow = day.weekday()
        schedule = await self._schedules.get_day(master_id, dow)
        if schedule is None or not schedule.is_working:
            return []

        appointments = await self._appointments.list_for_master_on_date(master_id, day)
        blocked = await self._blocked.list_for_master_date(master_id, day)

        slots: list[time] = []
        cursor = schedule.start_time
        while True:
            slot_end = _add_minutes(cursor, duration_min)
            if slot_end > schedule.end_time:
                break

            busy = False
            for appt in appointments:
                if _time_ranges_overlap(cursor, slot_end, appt.start_time, appt.end_time):
                    busy = True
                    break
            if not busy:
                for blk in blocked:
                    if _time_ranges_overlap(cursor, slot_end, blk.start_time, blk.end_time):
                        busy = True
                        break

            if not busy:
                # Не показываем прошедшие слоты на сегодня
                if day == date.today():
                    now_t = datetime.now(self._settings.tz).time()
                    if cursor <= now_t:
                        cursor = _add_minutes(cursor, duration_min)
                        continue
                slots.append(cursor)

            cursor = _add_minutes(cursor, duration_min)

        return slots

    async def get_all_slot_starts(
        self, master_id: int, day: date, duration_min: int
    ) -> list[time]:
        """Все старты слотов по графику (включая занятые) — для листа ожидания."""
        dow = day.weekday()
        schedule = await self._schedules.get_day(master_id, dow)
        if schedule is None or not schedule.is_working:
            return []
        slots: list[time] = []
        cursor = schedule.start_time
        while True:
            slot_end = _add_minutes(cursor, duration_min)
            if slot_end > schedule.end_time:
                break
            if day == date.today():
                now_t = datetime.now(self._settings.tz).time()
                if cursor <= now_t:
                    cursor = _add_minutes(cursor, duration_min)
                    continue
            slots.append(cursor)
            cursor = _add_minutes(cursor, duration_min)
        return slots

    async def iter_available_dates(
        self, master_id: int, duration_min: int, days_ahead: int | None = None
    ) -> list[date]:
        ahead = days_ahead or self._settings.calendar_days_ahead
        today = date.today()
        available: list[date] = []
        for i in range(ahead):
            day = today + timedelta(days=i)
            if await self.date_has_availability(master_id, day, duration_min):
                available.append(day)
        return available
