from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


BUTTON_PHOTO = "📸 Фото"
BUTTON_VIDEO = "🎬 Видео"
BUTTON_BUY_TOKENS = "💰 Пополнить токены"
BUTTON_BALANCE = "💎 Баланс"
BUTTON_REFERRALS = "👥 Рефералы"
BUTTON_HELP = "ℹ️ Помощь"
BUTTON_ADMIN = "👨‍💼 Админ-панель"


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    Main menu keyboard (persistent at bottom of screen)
    
    Args:
        is_admin: Whether user is admin (shows admin panel button)
    """
    buttons = [
        [KeyboardButton(text=BUTTON_PHOTO), KeyboardButton(text=BUTTON_VIDEO)],
        [KeyboardButton(text=BUTTON_BUY_TOKENS)],
        [KeyboardButton(text=BUTTON_BALANCE), KeyboardButton(text=BUTTON_REFERRALS)],
        [KeyboardButton(text=BUTTON_HELP)]
    ]
    
    if is_admin:
        buttons.append([KeyboardButton(text=BUTTON_ADMIN)])
    
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите действие..."
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    """Remove reply keyboard"""
    return ReplyKeyboardRemove()
