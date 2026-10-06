"""Таблицы связей M2M."""

from sqlalchemy import Column, ForeignKey, Table

from db.models.base import Base

master_services = Table(
    "master_services",
    Base.metadata,
    Column("master_id", ForeignKey("masters.id", ondelete="CASCADE"), primary_key=True),
    Column("service_id", ForeignKey("services.id", ondelete="CASCADE"), primary_key=True),
)
