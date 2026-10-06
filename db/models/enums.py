"""Перечисления доменной модели."""

import enum


class MasterRole(str, enum.Enum):
    admin = "admin"
    master = "master"


class AppointmentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled_by_client = "cancelled_by_client"
    cancelled_by_master = "cancelled_by_master"
    completed = "completed"
    rescheduled = "rescheduled"
    no_show = "no_show"


class WaitlistStatus(str, enum.Enum):
    waiting = "waiting"
    offered = "offered"
    expired = "expired"
    cancelled = "cancelled"


class ReminderType(str, enum.Enum):
    repeat_visit = "repeat_visit"
    confirm_visit = "confirm_visit"
    follow_up = "follow_up"


class ReminderStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    cancelled = "cancelled"


class BroadcastType(str, enum.Enum):
    emergency = "emergency"
    mass = "mass"
