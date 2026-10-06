"""Экспорт статистики в CSV / XLSX."""

import csv
import io
from datetime import date

from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.i18n_helpers import service_name
from db.models.enums import AppointmentStatus
from db.repositories.appointment_repo import AppointmentRepository

COMPLETED_LIKE = (
    AppointmentStatus.confirmed,
    AppointmentStatus.completed,
    AppointmentStatus.pending,
)


class ExportService:
    def __init__(self, session: AsyncSession) -> None:
        self._appointments = AppointmentRepository(session)

    async def collect_rows(
        self, date_from: date, date_to: date, master_id: int | None, locale: str = "ru"
    ) -> list[dict[str, object]]:
        items = await self._appointments.list_between(date_from, date_to, master_id)
        rows: list[dict[str, object]] = []
        revenue = 0
        for appt in items:
            if appt.status in (
                AppointmentStatus.cancelled_by_client,
                AppointmentStatus.cancelled_by_master,
            ):
                continue
            price = appt.service.price if appt.service else 0
            if appt.status in COMPLETED_LIKE:
                revenue += price
            rows.append(
                {
                    "id": appt.id,
                    "date": appt.date.isoformat(),
                    "time": appt.start_time.strftime("%H:%M"),
                    "client": appt.client.username or appt.client.telegram_id,
                    "master": appt.master.name,
                    "service": service_name(appt.service, locale) if appt.service else "",
                    "price": price,
                    "status": appt.status.value,
                }
            )
        if rows:
            rows.append({"id": "TOTAL", "price": revenue})
        return rows

    def to_csv(self, rows: list[dict[str, object]]) -> bytes:
        if not rows:
            return b"id,date,time,client,master,service,price,status\n"
        buf = io.StringIO()
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return buf.getvalue().encode("utf-8-sig")

    def to_xlsx(self, rows: list[dict[str, object]]) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = "appointments"
        if not rows:
            ws.append(["id", "date", "time", "client", "master", "service", "price", "status"])
        else:
            headers = list(rows[0].keys())
            ws.append(headers)
            for row in rows:
                ws.append([row.get(h) for h in headers])
        bio = io.BytesIO()
        wb.save(bio)
        return bio.getvalue()
