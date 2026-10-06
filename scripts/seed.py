"""Начальные данные: услуги, график, админы/мастера."""

import asyncio
import sys
from datetime import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import get_settings
from backend.services.role_service import RoleService
from db.models.enums import MasterRole
from db.models.schedule import Schedule
from db.models.service import Service
from db.repositories.master_repo import MasterRepository
from db.repositories.schedule_repo import ScheduleRepository
from db.repositories.service_repo import ServiceRepository
from db.repositories.user_repo import UserRepository
from db.session import init_db


async def run() -> None:
    settings = get_settings()
    factory = init_db(settings.db_url)
    async with factory() as session:
        role_svc = RoleService(session, settings)
        await role_svc.ensure_staff_profiles()

        svc_repo = ServiceRepository(session)
        existing = await svc_repo.list_all()
        if not existing:
            services = [
                Service(
                    name_i18n={
                        "ru": "Шугаринг",
                        "uz": "Shugaring",
                        "en": "Sugaring",
                    },
                    description_i18n={"ru": "", "uz": "", "en": ""},
                    duration_min=60,
                    price=150000,
                    reminder_days=21,
                ),
                Service(
                    name_i18n={
                        "ru": "Маникюр",
                        "uz": "Manikyur",
                        "en": "Manicure",
                    },
                    description_i18n={"ru": "", "uz": "", "en": ""},
                    duration_min=90,
                    price=120000,
                    reminder_days=14,
                ),
            ]
            for s in services:
                session.add(s)
            await session.flush()

        masters = await MasterRepository(session).list_active()
        all_services = await svc_repo.list_all()
        sched_repo = ScheduleRepository(session)
        for master in masters:
            if not master.services and all_services:
                master.services = all_services
            for dow in range(5):  # Пн–Пт
                await sched_repo.upsert_day(
                    master.id,
                    dow,
                    time(9, 0),
                    time(18, 0),
                    True,
                )
            for dow in (5, 6):
                await sched_repo.upsert_day(
                    master.id,
                    dow,
                    time(9, 0),
                    time(18, 0),
                    False,
                )

        # Имена админов
        user_repo = UserRepository(session)
        names = {
            1977440418: ("Рената", MasterRole.admin),
            6725003474: ("Ангелина", MasterRole.admin),
        }
        for tg_id, (name, role) in names.items():
            user = await user_repo.get_by_telegram_id(tg_id)
            if user:
                m = await MasterRepository(session).get_by_user_id(user.id)
                if m:
                    m.name = name
                    m.role = role

        await session.commit()
    print("Seed OK")


if __name__ == "__main__":
    asyncio.run(run())
