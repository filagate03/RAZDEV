from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from app.database import async_session_maker
from app.repositories import UserRepository
from app.keyboards.inline import back_to_main_keyboard
from app.keyboards.reply import main_menu_keyboard, BUTTON_BALANCE, BUTTON_HELP
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = Router()


def is_admin(chat_id: int) -> bool:
    """Check if user is admin"""
    admin_ids = [int(admin_id) for admin_id in settings.ADMINS.split(",") if admin_id.strip()]
    return chat_id in admin_ids


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command"""
    try:
        logger.info(f"=== START command from user {message.from_user.id} ===")
        args = message.text.split()
        referrer_chat_id = None
        
        if len(args) > 1 and args[1].startswith("ref_"):
            try:
                referrer_chat_id = int(args[1].split("_")[1])
                logger.info(f"Referrer: {referrer_chat_id}")
            except Exception as e:
                logger.error(f"Failed to parse referrer: {e}")
        
        logger.info("Creating database session...")
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            logger.info("Getting or creating user...")
            user = await user_repo.get_or_create(
                chat_id=message.from_user.id,
                username=message.from_user.username,
                referrer_chat_id=referrer_chat_id
            )
            logger.info(f"User loaded: {user.chat_id}, balance: {user.balance}")
        
        logger.info("Building welcome text...")
        welcome_text = (
            f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
            "🎨 Я бот для AI-генерации изображений\n\n"
            "💡 Как использовать:\n"
            "1️⃣ Отправьте мне фото\n"
            "2️ Я обработаю его через AI\n"
            "3️⃣ Получите результат через 30-90 секунд\n\n"
            f"💰 Ваш баланс: {user.balance} токенов\n"
            "💵 Стоимость: 1 токен = 1 генерация\n\n"
            "Используйте меню ниже для покупки токенов или просмотра профиля 👇"
        )
        
        if referrer_chat_id:
            welcome_text += f"\n\n🎁 Вы зарегистрированы по реферальной ссылке! Получите +{settings.referral_bonus} токенов при первой покупке!"
        
        logger.info(f"Checking admin status for {message.from_user.id}...")
        admin_status = is_admin(message.from_user.id)
        logger.info(f"Admin status: {admin_status}")
        
        logger.info("Building keyboard...")
        keyboard = main_menu_keyboard(is_admin=admin_status)
        logger.info(f"Keyboard created: {keyboard}")
        
        logger.info(f"Sending message to {message.from_user.id}...")
        await message.answer(welcome_text, reply_markup=keyboard)
        logger.info(f"=== Message sent successfully to {message.from_user.id} ===")
    except Exception as e:
        logger.error(f"!!! ERROR in cmd_start: {e} !!!", exc_info=True)
        try:
            await message.answer("Произошла ошибка. Попробуйте позже.")
        except:
            pass


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    """Show main menu (callback from inline buttons)"""
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_chat_id(callback.from_user.id)
    
    text = (
        "📱 Главное меню\n\n"
        f"💰 Баланс: {user.balance if user else 0} токенов\n\n"
        "Используйте кнопки меню ниже ⬇️"
    )
    
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "start_generation")
async def start_generation_menu(callback: CallbackQuery):
    """Show generation start menu"""
    from app.keyboards.inline import generation_styles_keyboard
    
    text = (
        "🎨 Генерация изображений\n\n"
        "📸 Выберите стиль, затем отправьте фото\n"
        "💰 Стоимость: 1 токен = 1 генерация\n\n"
        "Выберите стиль:"
    )
    
    await callback.message.edit_text(text, reply_markup=generation_styles_keyboard())
    await callback.answer()


@router.message(F.text == BUTTON_BALANCE)
async def show_profile_message(message: Message):
    """Show user profile (from reply keyboard button)"""
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_chat_id(message.from_user.id)
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return
    
    text = (
        "💎 Ваш профиль\n\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"👤 Имя: {message.from_user.full_name}\n"
        f"💰 Баланс: {user.balance} токенов\n"
        f"📅 Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}\n"
    )
    
    await message.answer(text)


@router.callback_query(F.data == "profile")
async def show_profile_callback(callback: CallbackQuery):
    """Show user profile (from inline button - legacy)"""
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_chat_id(callback.from_user.id)
    
    if not user:
        await callback.answer("Ошибка: пользователь не найден", show_alert=True)
        return
    
    text = (
        "👤 Ваш профиль\n\n"
        f"🆔 ID: {callback.from_user.id}\n"
        f"👤 Имя: {callback.from_user.full_name}\n"
        f"💰 Баланс: {user.balance} токенов\n"
        f"📅 Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}\n"
    )
    
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await callback.answer()


@router.message(F.text == BUTTON_HELP)
async def show_help_message(message: Message):
    """Show help information (from reply keyboard button)"""
    from app.repositories import BotSettingsRepository
    
    async with async_session_maker() as session:
        settings_repo = BotSettingsRepository(session)
        bot_settings = await settings_repo.get_or_create()
    
    text = (
        "ℹ️ Помощь\n\n"
        "🎨 Как генерировать изображения:\n"
        "1. Нажмите '🎨 Генерация'\n"
        "2. Выберите стиль\n"
        "3. Отправьте фото\n"
        "4. Результат придет через 30-90 секунд\n\n"
        "💰 Стоимость:\n"
        "• 1 генерация = 1 токен\n"
        "• Токены покупаются пакетами\n\n"
        "💳 Способы оплаты:\n"
        "• Telegram Stars (⭐️)\n"
        "• Криптовалюта (USDT, TON, BTC)\n"
        "• Банковская карта (RU/INTL)\n\n"
        "🔗 Реферальная программа:\n"
        "• Приглашайте друзей\n"
        f"• Получайте {settings.referral_commission}% с их покупок\n"
        f"• Ваши рефералы получают +{settings.referral_bonus} токенов\n\n"
        f"📞 Поддержка: {bot_settings.support_contact}"
    )
    
    await message.answer(text)


@router.callback_query(F.data == "help")
async def show_help_callback(callback: CallbackQuery):
    """Show help information (from inline button - legacy)"""
    from app.repositories import BotSettingsRepository
    
    async with async_session_maker() as session:
        settings_repo = BotSettingsRepository(session)
        bot_settings = await settings_repo.get_or_create()
    
    text = (
        "ℹ️ Помощь\n\n"
        "🎨 Как генерировать изображения:\n"
        "1. Отправьте боту любое фото\n"
        "2. Бот обработает его через AI\n"
        "3. Результат придет через 30-90 секунд\n\n"
        "💰 Стоимость:\n"
        "• 1 генерация = 1 токен\n"
        "• Токены покупаются пакетами\n\n"
        "💳 Способы оплаты:\n"
        "• Telegram Stars (⭐️)\n"
        "• Криптовалюта (USDT, TON, BTC)\n\n"
        "🔗 Реферальная программа:\n"
        "• Приглашайте друзей\n"
        f"• Получайте {settings.referral_commission}% с их покупок\n"
        f"• Ваши рефералы получают +{settings.referral_bonus} токенов\n\n"
        f"📞 Поддержка: {bot_settings.support_contact}"
    )
    
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await callback.answer()
