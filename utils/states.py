from aiogram.fsm.state import StatesGroup, State


class RegisterVpn(StatesGroup):
    chooising_devise = State()
    chooising_plan = State()
