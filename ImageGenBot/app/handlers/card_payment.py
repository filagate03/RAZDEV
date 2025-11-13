from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from app.database import async_session_maker
from app.repositories import UserRepository, CardPaymentRequestRepository, CardPaymentInstructionRepository, TransactionRepository
from app.keyboards.inline import card_payment_keyboard, back_to_main_keyboard
from app.keyboards.reply import BUTTON_PHOTO, BUTTON_VIDEO
from app.config import settings
from app.states import CardPaymentStates
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "buy_card_menu")
async def show_card_menu(callback: CallbackQuery, state: FSMContext):
    """Show card payment menu"""
    await state.clear()
    
    text = (
        "💳 Оплата картой\n\n"
        "Выберите тип карты:"
    )
    
    await callback.message.edit_text(text, reply_markup=card_payment_keyboard())
    await callback.answer()


@router.callback_query(F.data.in_(["card_ru", "card_intl"]))
async def select_card_type(callback: CallbackQuery, state: FSMContext):
    """Select card type and show packages"""
    card_type = "ru" if callback.data == "card_ru" else "intl"
    await state.update_data(card_type=card_type)
    await state.set_state(CardPaymentStates.selecting_package)
    
    card_name = "Российская" if card_type == "ru" else "Международная"
    
    packages = settings.stars_packs_list
    text = f"💳 {card_name} карта\n\nВыберите пакет токенов:\n\n"
    
    keyboard_buttons = []
    for pack in packages:
        tokens = pack["tokens"]
        stars = pack["stars"]
        price_rub = int(stars * 1.5)
        keyboard_buttons.append([InlineKeyboardButton(
            text=f"⭐️ {tokens} токенов ({price_rub} ₽)",
            callback_data=f"card_pack_{tokens}_{card_type}"
        )])
    
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="buy_card_menu")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("card_pack_"), CardPaymentStates.selecting_package)
async def process_card_package_selection(callback: CallbackQuery, state: FSMContext):
    """Show payment instructions after package selection"""
    try:
        parts = callback.data.split("_")
        tokens = int(parts[2])
        card_type = parts[3]
        
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_chat_id(callback.from_user.id)
            
            if not user:
                await state.clear()
                await callback.answer("Ошибка: пользователь не найден", show_alert=True)
                return
            
            package = next((p for p in settings.stars_packs_list if p["tokens"] == tokens), None)
            if not package:
                await state.clear()
                await callback.answer("Ошибка: пакет не найден", show_alert=True)
                return
            
            price_rub = int(package["stars"] * 1.5)
            
            payment_repo = CardPaymentRequestRepository(session)
            request = await payment_repo.create(
                user_id=user.id,
                package_name=f"{tokens} токенов",
                tokens_amount=tokens,
                card_type=card_type,
                price_rub=price_rub if card_type == "ru" else None,
                price_usd=int(price_rub / 90) if card_type == "intl" else None
            )
            
            instr_repo = CardPaymentInstructionRepository(session)
            instruction = await instr_repo.get_or_create(
                card_type=card_type,
                default_text="Переведите указанную сумму на реквизиты ниже и отправьте скриншот чека.",
                default_requisites="2200 0000 2200 0000" if card_type == "ru" else "4111 1111 1111 1111"
            )
        
        card_name = "Российская" if card_type == "ru" else "Международная"
        price = f"{price_rub} ₽" if card_type == "ru" else f"${int(price_rub / 90)}"
        
        text = (
            f"💳 Оплата картой ({card_name})\n\n"
            f"📦 Пакет: {tokens} токенов\n"
            f"💰 Сумма: {price}\n\n"
            f"📝 {instruction.instruction_text}\n\n"
            f"💳 Реквизиты:\n<code>{instruction.requisites}</code>\n\n"
            f"После оплаты отправьте скриншот чека боту."
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отменить", callback_data="buy_card_menu")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer("Ожидаем скриншот чека")
        
        await state.update_data(request_id=request.id, tokens=tokens, price=price, card_name=card_name)
        await state.set_state(CardPaymentStates.waiting_receipt)
    
    except Exception as e:
        logger.error(f"Error in process_card_package_selection: {e}", exc_info=True)
        await state.clear()
        await callback.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)


@router.message(CardPaymentStates.waiting_receipt, F.photo)
async def receive_receipt_photo(message: Message, state: FSMContext):
    """Receive receipt photo from user"""
    try:
        data = await state.get_data()
        request_id = data.get("request_id")
        tokens = data.get("tokens")
        price = data.get("price")
        card_name = data.get("card_name")
        
        if not request_id:
            await message.answer("❌ Ошибка: заявка не найдена. Начните заново через /start")
            await state.clear()
            return
        
        photo = message.photo[-1]
        file_id = photo.file_id
        
        async with async_session_maker() as session:
            payment_repo = CardPaymentRequestRepository(session)
            await payment_repo.update_receipt(request_id, file_id)
            
            user_repo = UserRepository(session)
            admins = await user_repo.get_all_admins()
            
            for admin in admins:
                try:
                    admin_text = (
                        f"🆕 Новая заявка на оплату картой!\n\n"
                        f"👤 Пользователь: {message.from_user.full_name}\n"
                        f"🆔 ID: {message.from_user.id}\n"
                        f"📦 Пакет: {tokens} токенов\n"
                        f"💳 Тип карты: {card_name}\n"
                        f"💰 Сумма: {price}\n\n"
                        f"📸 Чек от пользователя:"
                    )
                    
                    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_card_{request_id}")],
                        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_card_{request_id}")]
                    ])
                    
                    await message.bot.send_photo(
                        admin.chat_id,
                        file_id,
                        caption=admin_text,
                        reply_markup=admin_keyboard
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin.chat_id}: {e}")
        
        await message.answer(
            "✅ Чек получен!\n\n"
            "Ваша заявка отправлена администратору на проверку.\n"
            "Ожидайте подтверждения оплаты.",
            reply_markup=back_to_main_keyboard()
        )
        
        await state.clear()
    
    except Exception as e:
        logger.error(f"Error receiving receipt: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте снова или обратитесь к администратору.")
        await state.clear()


@router.message(CardPaymentStates.waiting_receipt, ~F.text.in_([BUTTON_PHOTO, BUTTON_VIDEO]))
async def waiting_receipt_other_content(message: Message):
    """Handle non-photo messages while waiting for receipt (except Фото/Видео buttons)"""
    await message.answer(
        "⚠️ Пожалуйста, отправьте скриншот чека (фото).\n\n"
        "Если хотите отменить, нажмите /start"
    )


@router.callback_query(F.data.startswith("confirm_card_"))
async def confirm_card_payment(callback: CallbackQuery):
    """Admin confirms card payment"""
    try:
        request_id = int(callback.data.split("_")[2])
        logger.info(f"Admin {callback.from_user.id} confirming payment request {request_id}")
        
        async with async_session_maker() as session:
            payment_repo = CardPaymentRequestRepository(session)
            request = await payment_repo.get_by_id(request_id)
            
            if not request:
                logger.error(f"Payment request {request_id} not found")
                await callback.answer("Заявка не найдена", show_alert=True)
                return
            
            logger.info(f"Request found: user_id={request.user_id}, status={request.status}, tokens={request.tokens_amount}")
            
            if request.status != "pending":
                await callback.answer(f"Заявка уже обработана: {request.status}", show_alert=True)
                return
            
            user_repo = UserRepository(session)
            user = await user_repo.get_by_id(request.user_id)
            
            if not user:
                logger.error(f"User with id={request.user_id} not found in database!")
                await callback.answer("Ошибка: пользователь не найден", show_alert=True)
                return
            
            logger.info(f"User found: id={user.id}, chat_id={user.chat_id}, balance={user.balance}")
            
            result = await user_repo.update_balance(user.chat_id, request.tokens_amount)
            
            if not result:
                await callback.answer("Ошибка обновления баланса", show_alert=True)
                return
            
            trans_repo = TransactionRepository(session)
            await trans_repo.create(
                user_id=request.user_id,
                amount=request.tokens_amount,
                reason=f"Пополнение картой: {request.package_name}",
                payment_method=f"card_{request.card_type}"
            )
            
            await payment_repo.update_status(request_id, "completed", f"Подтверждено {callback.from_user.full_name}")
            
            user = await user_repo.get_by_id(request.user_id)
            if user:
                try:
                    await callback.bot.send_message(
                        user.chat_id,
                        f"✅ Оплата подтверждена!\n\n"
                        f"📦 Начислено: {request.tokens_amount} токенов\n"
                        f"💰 Ваш баланс: {user.balance} токенов\n\n"
                        f"Спасибо за покупку!"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {user.chat_id}: {e}")
        
        await callback.message.edit_caption(
            caption=callback.message.caption + f"\n\n✅ Подтверждено {callback.from_user.full_name}",
            reply_markup=None
        )
        await callback.answer("Оплата подтверждена, токены начислены!")
    
    except Exception as e:
        logger.error(f"Error confirming payment: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("reject_card_"))
async def reject_card_payment(callback: CallbackQuery):
    """Admin rejects card payment"""
    try:
        request_id = int(callback.data.split("_")[2])
        
        async with async_session_maker() as session:
            payment_repo = CardPaymentRequestRepository(session)
            request = await payment_repo.get_by_id(request_id)
            
            if not request:
                await callback.answer("Заявка не найдена", show_alert=True)
                return
            
            if request.status != "pending":
                await callback.answer(f"Заявка уже обработана: {request.status}", show_alert=True)
                return
            
            await payment_repo.update_status(request_id, "rejected", f"Отклонено {callback.from_user.full_name}")
            
            user_repo = UserRepository(session)
            user = await user_repo.get_by_id(request.user_id)
            if user:
                try:
                    await callback.bot.send_message(
                        user.chat_id,
                        f"❌ Оплата отклонена\n\n"
                        f"Ваша заявка на {request.tokens_amount} токенов была отклонена администратором.\n"
                        f"Если у вас есть вопросы, свяжитесь с поддержкой."
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {user.chat_id}: {e}")
        
        await callback.message.edit_caption(
            caption=callback.message.caption + f"\n\n❌ Отклонено {callback.from_user.full_name}",
            reply_markup=None
        )
        await callback.answer("Заявка отклонена")
    
    except Exception as e:
        logger.error(f"Error rejecting payment: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)
