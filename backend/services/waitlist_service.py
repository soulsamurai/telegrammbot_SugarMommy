"""Лист ожидания: постановка в очередь и оффер слота."""

from datetime import date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from backend.services.appointment_service import AppointmentService
from db.models.enums import WaitlistStatus
from db.models.waitlist import WaitlistEntry
from db.repositories.waitlist_repo import WaitlistRepository


class WaitlistService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = WaitlistRepository(session)
        self._appointments = AppointmentService(session, settings)

    async def join(
        self,
        client_id: int,
        master_id: int,
        service_id: int,
        preferred_date: date,
        preferred_time_start: time,
        preferred_time_end: time,
    ) -> WaitlistEntry:
        position = await self._repo.next_position(
            master_id, service_id, preferred_date, preferred_time_start
        )
        entry = WaitlistEntry(
            client_id=client_id,
            master_id=master_id,
            service_id=service_id,
            preferred_date=preferred_date,
            preferred_time_start=preferred_time_start,
            preferred_time_end=preferred_time_end,
            position=position,
            status=WaitlistStatus.waiting,
        )
        return await self._repo.add(entry)

    async def cancel_entry(self, entry: WaitlistEntry) -> None:
        entry.status = WaitlistStatus.cancelled
        await self._session.flush()

    async def offer_next_for_slot(
        self,
        master_id: int,
        service_id: int,
        preferred_date: date,
        preferred_time_start: time,
        preferred_time_end: time,
    ) -> WaitlistEntry | None:
        entry = await self._repo.first_waiting(
            master_id,
            service_id,
            preferred_date,
            preferred_time_start,
            preferred_time_end,
        )
        if entry is None:
            return None
        entry.status = WaitlistStatus.offered
        entry.offered_at = datetime.now(self._settings.tz)
        await self._session.flush()
        return entry

    async def accept_offer(self, entry: WaitlistEntry) -> int:
        """Создаёт запись из оффера листа ожидания. Возвращает appointment_id."""
        if entry.status != WaitlistStatus.offered:
            raise ValueError("not_offered")
        appt = await self._appointments.create(
            client_id=entry.client_id,
            master_id=entry.master_id,
            service_id=entry.service_id,
            day=entry.preferred_date,
            start=entry.preferred_time_start,
        )
        entry.status = WaitlistStatus.expired  # использован
        await self._session.flush()
        return appt.id

    async def decline_or_expire(self, entry: WaitlistEntry) -> None:
        entry.status = WaitlistStatus.expired
        await self._session.flush()

    async def process_expired_offers(self) -> list[WaitlistEntry]:
        """Истекают офферы старше 15 мин и возвращает новые офферы для рассылки."""
        cutoff = datetime.now(self._settings.tz) - timedelta(
            minutes=self._settings.waitlist_offer_minutes
        )
        expired = await self._repo.expired_offers(cutoff)
        new_offers: list[WaitlistEntry] = []
        for entry in expired:
            entry.status = WaitlistStatus.expired
            nxt = await self.offer_next_for_slot(
                entry.master_id,
                entry.service_id,
                entry.preferred_date,
                entry.preferred_time_start,
                entry.preferred_time_end,
            )
            if nxt:
                new_offers.append(nxt)
        await self._session.flush()
        return new_offers

    async def notify_slot_freed(
        self,
        master_id: int,
        service_id: int,
        preferred_date: date,
        preferred_time_start: time,
        preferred_time_end: time,
    ) -> WaitlistEntry | None:
        return await self.offer_next_for_slot(
            master_id,
            service_id,
            preferred_date,
            preferred_time_start,
            preferred_time_end,
        )
