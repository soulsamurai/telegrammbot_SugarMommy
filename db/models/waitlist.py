"""Лист ожидания на занятые слоты."""

from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base
from db.models.enums import WaitlistStatus


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    __table_args__ = (
        Index(
            "ix_waitlist_queue",
            "master_id",
            "service_id",
            "preferred_date",
            "preferred_time_start",
            "position",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    master_id: Mapped[int] = mapped_column(ForeignKey("masters.id", ondelete="CASCADE"))
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"))
    preferred_date: Mapped[date] = mapped_column(Date, nullable=False)
    preferred_time_start: Mapped[time] = mapped_column(Time, nullable=False)
    preferred_time_end: Mapped[time] = mapped_column(Time, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[WaitlistStatus] = mapped_column(
        Enum(WaitlistStatus, name="waitlist_status"),
        nullable=False,
        default=WaitlistStatus.waiting,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    offered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped["User"] = relationship("User", back_populates="waitlist_entries")
    master: Mapped["Master"] = relationship("Master", back_populates="waitlist_entries")
    service: Mapped["Service"] = relationship("Service")
