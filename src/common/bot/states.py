from aiogram.fsm.state import State, StatesGroup


class RegisterVpn(StatesGroup):
    chooising_devise = State()
    chooising_plan = State()
