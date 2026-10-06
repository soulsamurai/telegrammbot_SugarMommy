"""FSM записи клиента."""

from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    choosing_service = State()
    choosing_master = State()
    choosing_date = State()
    choosing_time = State()
    waitlist_offer = State()
    confirming = State()


class RescheduleStates(StatesGroup):
    select_appointment = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()


class LanguageStates(StatesGroup):
    choosing = State()
