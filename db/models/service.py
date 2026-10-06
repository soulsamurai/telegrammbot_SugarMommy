"""Услуги салона."""

from sqlalchemy import Boolean, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.associations import master_services
from db.models.base import Base


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name_i18n: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    description_i18n: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    reminder_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    masters: Mapped[list["Master"]] = relationship(
        "Master", secondary=master_services, back_populates="services"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="service"
    )
