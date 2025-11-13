from aiogram.fsm.state import State, StatesGroup


class GenerationStates(StatesGroup):
    choosing_style = State()
    waiting_for_photo = State()


class CardPaymentStates(StatesGroup):
    selecting_card_type = State()
    selecting_package = State()
    waiting_receipt = State()
