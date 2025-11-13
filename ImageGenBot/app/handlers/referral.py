from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from app.database import async_session_maker
from app.repositories import UserRepository, ReferralRepository
from app.keyboards.inline import back_to_main_keyboard
from app.keyboards.reply import BUTTON_REFERRALS
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == BUTTON_REFERRALS)
async def show_referral_info_message(message: Message):
    """Show referral program information (from reply keyboard button)"""
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_chat_id(message.from_user.id)
        
        if not user:
            await message.answer("Ошибка: пользователь не найден. Используйте /start")
            return
        
        ref_repo = ReferralRepository(session)
        referrals = await ref_repo.get_by_referrer(user.id)
        
        total_earned = sum(ref.total_earned for ref in referrals)
        active_referrals = len(referrals)
    
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{message.from_user.id}"
    
    text = (
        "🔗 Реферальная программа\n\n"
        f"👥 Ваших рефералов: {active_referrals}\n"
        f"💰 Заработано всего: {total_earned} токенов\n\n"
        "📋 Условия:\n"
        f"• Ваши рефералы получают +{settings.referral_bonus} токенов при первой покупке\n"
        f"• Вы получаете {settings.referral_commission}% с каждой их покупки\n\n"
        f"🔗 Ваша реферальная ссылка:\n"
        f"`{ref_link}`\n\n"
        "Поделитесь ссылкой с друзьями и зарабатывайте!"
    )
    
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("ref"))
@router.callback_query(F.data == "referral_info")
async def show_referral_info(event):
    """Show referral program information"""
    user_id = event.from_user.id if isinstance(event, Message) else event.from_user.id
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_chat_id(user_id)
        
        if not user:
            text = "Ошибка: пользователь не найден. Используйте /start"
            if isinstance(event, Message):
                await event.answer(text)
            else:
                await event.answer(text, show_alert=True)
            return
        
        ref_repo = ReferralRepository(session)
        referrals = await ref_repo.get_by_referrer(user.id)
        
        total_earned = sum(ref.total_earned for ref in referrals)
        active_referrals = len(referrals)
    
    bot_info = await (event.bot if isinstance(event, Message) else event.message.bot).get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    
    text = (
        "🔗 Реферальная программа\n\n"
        f"👥 Ваших рефералов: {active_referrals}\n"
        f"💰 Заработано всего: {total_earned} токенов\n\n"
        "📋 Условия:\n"
        f"• Ваши рефералы получают +{settings.referral_bonus} токенов при первой покупке\n"
        f"• Вы получаете {settings.referral_commission}% с каждой их покупки\n\n"
        f"🔗 Ваша реферальная ссылка:\n"
        f"`{ref_link}`\n\n"
        "Поделитесь ссылкой с друзьями и зарабатывайте!"
    )
    
    keyboard = back_to_main_keyboard()
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await event.answer()
