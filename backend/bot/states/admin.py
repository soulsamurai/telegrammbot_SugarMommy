"""FSM админ- и мастер-сценариев."""

from aiogram.fsm.state import State, StatesGroup


class BlockSlotStates(StatesGroup):
    select_master = State()
    select_date = State()
    select_slots = State()
    confirm = State()


class ScheduleStates(StatesGroup):
    select_master = State()
    select_day = State()
    set_hours = State()


class EmergencyBroadcastStates(StatesGroup):
    select_date = State()
    enter_text = State()
    confirm = State()


class MassBroadcastStates(StatesGroup):
    enter_text = State()
    enter_media = State()
    confirm = State()


class ServiceCrudStates(StatesGroup):
    menu = State()
    edit_field = State()


class MasterCrudStates(StatesGroup):
    menu = State()
    add_telegram_id = State()
    add_name = State()
