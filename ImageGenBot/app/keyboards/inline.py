from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.config import settings


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Генерировать", callback_data="start_generation")],
        [InlineKeyboardButton(text="💰 Купить токены", callback_data="buy_menu")],
        [InlineKeyboardButton(text="💎 Баланс", callback_data="profile")],
        [InlineKeyboardButton(text="🔗 Пригласить друзей", callback_data="referral_info")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])
    return keyboard


def buy_tokens_keyboard() -> InlineKeyboardMarkup:
    """Buy tokens menu keyboard"""
    buttons = []
    
    buttons.append([InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="buy_stars_alt_menu")])
    buttons.append([InlineKeyboardButton(text="💎 Оплата криптой", callback_data="buy_crypto_menu")])
    buttons.append([InlineKeyboardButton(text="💳 Оплата картой", callback_data="buy_card_menu")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def card_payment_keyboard() -> InlineKeyboardMarkup:
    """Card payment menu keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Российская карта", callback_data="card_ru")],
        [InlineKeyboardButton(text="🌍 Международная карта", callback_data="card_intl")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="buy_menu")]
    ])
    return keyboard


def crypto_payment_keyboard() -> InlineKeyboardMarkup:
    """Crypto payment menu keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 USDT", callback_data="crypto_currency_usdt")],
        [InlineKeyboardButton(text="💎 TON", callback_data="crypto_currency_ton")],
        [InlineKeyboardButton(text="₿ BTC", callback_data="crypto_currency_btc")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="buy_menu")]
    ])
    return keyboard


def admin_keyboard() -> InlineKeyboardMarkup:
    """Admin panel keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 Транзакции", callback_data="admin_transactions")],
        [InlineKeyboardButton(text="👨‍💼 Управление админами", callback_data="admin_manage")],
        [InlineKeyboardButton(text="💳 Заявки на оплату", callback_data="admin_payment_requests")],
        [InlineKeyboardButton(text="⚙️ Настройки оплаты", callback_data="admin_payment_settings")],
        [InlineKeyboardButton(text="📞 Настройки поддержки", callback_data="admin_support_settings")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])
    return keyboard


def generation_styles_keyboard() -> InlineKeyboardMarkup:
    """Generation styles selection keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👗 Стиль 1", callback_data="style_1")],
        [InlineKeyboardButton(text="💃 Стиль 2", callback_data="style_2")],
        [InlineKeyboardButton(text="👙 Стиль 3", callback_data="style_3")],
        [InlineKeyboardButton(text="🔥 Стиль 4", callback_data="style_4")],
        [InlineKeyboardButton(text="✨ Стиль 5", callback_data="style_5")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])
    return keyboard


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    """Back to main menu keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")]
    ])
    return keyboard


def video_models_keyboard() -> InlineKeyboardMarkup:
    """Video animation models selection keyboard"""
    models = [
        ("💋 Blowjob", "M0d1IGEkCkeys3z"),
        ("🍒 Bouncy tits", "egncvJ0CJemcUX5"),
        ("👣 Footjob", "qJ9KByOKlNrnD7X"),
        ("💦 Squirt", "MgP3RMTMxrQ4xn1"),
        ("❤️ Hand heart", "9IoEyMGTQNBUlSW"),
        ("💏 Lesbian Kiss", "3Fj2x7hzDreTCp6x817DU"),
        ("😛 Ahegao", "tgPcSA8laTd0yv4"),
        ("✊ Masturbation", "D99MLg6R0gi9hJd"),
        ("🛏 Missionary", "FRt2l4RDDHu979d"),
        ("👆 Fingering", "50tZbquENp3P97K"),
        ("🔮 Witch Spell", "J_I-rb2LVwgshO47iEX-W"),
        ("🐕 Doggy style", "t39EDWrEckcwwmA"),
        ("🍑 Twerk", "eMYnaGciQuqm7wi"),
        ("✨ Poof!", "VRYrEWtdZmZzP9avklJup"),
        ("🍑 Ass Spanks", "wCLrc7XPsqOui6Z"),
        ("🏇 Reverse Cowgirl", "DKvEpidXcX6NfLX"),
        ("👙 Shows tits", "Tsl6UFbtiYmJhiA"),
    ]
    
    buttons = []
    for i in range(0, len(models), 2):
        row = []
        row.append(InlineKeyboardButton(text=models[i][0], callback_data=f"video_model_{models[i][1]}"))
        if i + 1 < len(models):
            row.append(InlineKeyboardButton(text=models[i+1][0], callback_data=f"video_model_{models[i+1][1]}"))
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
