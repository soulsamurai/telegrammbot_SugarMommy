"""Мастер / администратор."""

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.associations import master_services
from db.models.base import Base
from db.models.enums import MasterRole


class Master(Base):
    __tablename__ = "masters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[MasterRole] = mapped_column(
        Enum(MasterRole, name="master_role"), nullable=False, default=MasterRole.master
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="master_profile")
    services: Mapped[list["Service"]] = relationship(
        "Service", secondary=master_services, back_populates="masters"
    )
    schedules: Mapped[list["Schedule"]] = relationship("Schedule", back_populates="master")
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="master"
    )
    blocked_slots: Mapped[list["BlockedSlot"]] = relationship(
        "BlockedSlot", back_populates="master"
    )
    waitlist_entries: Mapped[list["WaitlistEntry"]] = relationship(
        "WaitlistEntry", back_populates="master"
    )
