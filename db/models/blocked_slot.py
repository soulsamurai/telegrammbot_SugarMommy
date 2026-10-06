"""Заблокированные мастером интервалы."""

from datetime import date, time

from sqlalchemy import Date, ForeignKey, Index, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base


class BlockedSlot(Base):
    __tablename__ = "blocked_slots"
    __table_args__ = (Index("ix_blocked_master_date", "master_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    master_id: Mapped[int] = mapped_column(ForeignKey("masters.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True)

    master: Mapped["Master"] = relationship("Master", back_populates="blocked_slots")
