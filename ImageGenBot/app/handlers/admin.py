from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.database import async_session_maker
from app.repositories import UserRepository, TransactionRepository, CardPaymentRequestRepository, CardPaymentInstructionRepository, BotSettingsRepository
from app.keyboards.inline import admin_keyboard, back_to_main_keyboard
from app.keyboards.reply import BUTTON_ADMIN
from app.config import settings
from sqlalchemy import func, select
from app.models import User, Transaction
import logging

logger = logging.getLogger(__name__)
router = Router()


def is_admin(chat_id: int) -> bool:
    """Check if user is admin"""
    admin_ids = [int(admin_id) for admin_id in settings.ADMINS.split(",") if admin_id.strip()]
    return chat_id in admin_ids


@router.message(F.text == BUTTON_ADMIN)
async def show_admin_panel_message(message: Message):
    """Show admin panel (from reply keyboard button)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели")
        return
    
    text = (
        "⚙️ Админ-панель\n\n"
        "Выберите действие:"
    )
    
    await message.answer(text, reply_markup=admin_keyboard())


class AdminStates(StatesGroup):
    waiting_for_admin_id = State()
    waiting_for_payment_response = State()
    waiting_for_instruction_text = State()
    waiting_for_requisites = State()
    waiting_for_support_contact = State()


def is_admin_filter():
    """Filter to check if user is admin"""
    async def _filter(message: Message, is_admin: bool):
        return is_admin
    return _filter


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Admin panel command"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели")
        return
    
    text = (
        "⚙️ Админ-панель\n\n"
        "Выберите действие:"
    )
    
    await message.answer(text, reply_markup=admin_keyboard())


@router.callback_query(F.data == "admin_stats")
async def show_admin_stats(callback: CallbackQuery):
    """Show admin statistics"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    async with async_session_maker() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        
        total_balance = await session.scalar(select(func.sum(User.balance))) or 0
        
        total_transactions = await session.scalar(select(func.count(Transaction.id)))
        
        total_earned = await session.scalar(
            select(func.sum(Transaction.amount)).where(Transaction.amount > 0)
        ) or 0
        
        total_spent = await session.scalar(
            select(func.sum(Transaction.amount)).where(Transaction.amount < 0)
        ) or 0
    
    text = (
        "📊 Статистика бота\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"💰 Суммарный баланс: {total_balance} токенов\n"
        f"💳 Всего транзакций: {total_transactions}\n"
        f"📈 Куплено токенов: {total_earned}\n"
        f"📉 Потрачено токенов: {abs(total_spent)}\n"
        f"💵 Прибыль: {total_earned + total_spent} токенов\n"
    )
    
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_users")
async def show_admin_users(callback: CallbackQuery):
    """Show users list"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        users = await user_repo.get_all_users()
        
        users_sorted = sorted(users, key=lambda u: u.balance, reverse=True)[:10]
    
    text = "👥 Топ-10 пользователей по балансу:\n\n"
    
    for i, user in enumerate(users_sorted, 1):
        username = f"@{user.username}" if user.username else f"ID: {user.chat_id}"
        text += f"{i}. {username} - {user.balance} токенов\n"
    
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_transactions")
async def show_admin_transactions(callback: CallbackQuery):
    """Show recent transactions"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(Transaction).order_by(Transaction.created_at.desc()).limit(10)
        )
        transactions = result.scalars().all()
    
    text = "💰 Последние 10 транзакций:\n\n"
    
    for tx in transactions:
        sign = "+" if tx.amount > 0 else ""
        text += f"{sign}{tx.amount} токенов - {tx.reason}\n"
        text += f"  {tx.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_manage")
async def show_admin_manage(callback: CallbackQuery):
    """Show admin management"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        admins = await user_repo.get_all_admins()
    
    text = "👨‍💼 Управление админами\n\n"
    text += "Текущие админы:\n"
    
    for admin in admins:
        username = f"@{admin.username}" if admin.username else f"ID: {admin.chat_id}"
        text += f"• {username} ({admin.chat_id})\n"
    
    text += "\n📝 Для добавления админа используйте:\n/add_admin [ID пользователя]\n\n"
    text += "❌ Для удаления админа используйте:\n/remove_admin [ID пользователя]"
    
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await callback.answer()


@router.message(Command("add_admin"))
async def cmd_add_admin(message: Message):
    """Add new admin"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /add_admin <chat_id>")
        return
    
    try:
        new_admin_id = int(args[1])
    except ValueError:
        await message.answer("❌ Неверный формат ID")
        return
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_chat_id(new_admin_id)
        
        if not user:
            await message.answer("❌ Пользователь не найден. Он должен сначала запустить бота.")
            return
        
        if user.is_admin:
            await message.answer("⚠️ Этот пользователь уже админ")
            return
        
        await user_repo.set_admin(new_admin_id, True)
    
    await message.answer(f"✅ Пользователь {new_admin_id} теперь админ!")


@router.message(Command("remove_admin"))
async def cmd_remove_admin(message: Message):
    """Remove admin"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /remove_admin <chat_id>")
        return
    
    try:
        admin_id = int(args[1])
    except ValueError:
        await message.answer("❌ Неверный формат ID")
        return
    
    if admin_id == message.from_user.id:
        await message.answer("❌ Вы не можете удалить себя из админов")
        return
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        await user_repo.set_admin(admin_id, False)
    
    await message.answer(f"✅ Админ {admin_id} удален")


@router.callback_query(F.data == "admin_payment_requests")
async def show_payment_requests(callback: CallbackQuery):
    """Show pending payment requests"""
    if not is_admin(message.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    async with async_session_maker() as session:
        payment_repo = CardPaymentRequestRepository(session)
        requests = await payment_repo.get_pending()
        
        if not requests:
            text = "💳 Нет активных заявок на оплату"
            await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
            await callback.answer()
            return
        
        text = "💳 Активные заявки на оплату:\n\n"
        
        buttons = []
        for req in requests[:10]:
            user_repo = UserRepository(session)
            user = await session.get(User, req.user_id)
            
            username = f"@{user.username}" if user and user.username else f"ID: {user.chat_id if user else 'N/A'}"
            card_type = "🇷🇺 RU" if req.card_type == "ru" else "🌍 INTL"
            price = f"{req.price_rub} ₽" if req.price_rub else f"${req.price_usd}"
            
            text += f"#{req.id} {username}\n"
            text += f"   {req.tokens_amount} токенов • {card_type} • {price}\n\n"
            
            buttons.append([InlineKeyboardButton(
                text=f"#{req.id} - {username}",
                callback_data=f"respond_{req.id}"
            )])
        
        buttons.append([InlineKeyboardButton(text="◀️ Админ меню", callback_data="admin_menu")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("respond_"))
async def respond_to_payment_request(callback: CallbackQuery, state: FSMContext):
    """Respond to payment request"""
    if not is_admin(message.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    request_id = int(callback.data.split("_")[1])
    
    async with async_session_maker() as session:
        payment_repo = CardPaymentRequestRepository(session)
        request = await payment_repo.get_by_id(request_id)
        
        if not request:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        
        user = await session.get(User, request.user_id)
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        card_type = "Российская" if request.card_type == "ru" else "Международная"
        price = f"{request.price_rub} ₽" if request.price_rub else f"${request.price_usd}"
        
        text = (
            f"💳 Заявка #{request.id}\n\n"
            f"👤 Пользователь: @{user.username if user.username else user.chat_id}\n"
            f"🆔 Chat ID: {user.chat_id}\n"
            f"📦 Пакет: {request.tokens_amount} токенов\n"
            f"💳 Тип карты: {card_type}\n"
            f"💰 Сумма: {price}\n\n"
            f"📝 Отправьте сообщение с реквизитами для оплаты.\n"
            f"Оно будет переслано пользователю."
        )
    
    await state.update_data(request_id=request_id, user_chat_id=user.chat_id)
    await state.set_state(AdminStates.waiting_for_payment_response)
    
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await callback.answer("Отправьте реквизиты")


@router.message(AdminStates.waiting_for_payment_response)
async def process_payment_response(message: Message, state: FSMContext):
    """Process admin response with payment details"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    request_id = data.get("request_id")
    user_chat_id = data.get("user_chat_id")
    
    if not request_id or not user_chat_id:
        await message.answer("❌ Ошибка: данные заявки не найдены")
        await state.clear()
        return
    
    response_text = message.text
    
    async with async_session_maker() as session:
        payment_repo = CardPaymentRequestRepository(session)
        await payment_repo.update_status(request_id, "processing", response_text)
    
    try:
        user_message = (
            f"💳 Ответ от администратора:\n\n"
            f"{response_text}\n\n"
            f"После оплаты отправьте чек в бот."
        )
        await message.bot.send_message(user_chat_id, user_message)
        await message.answer("✅ Ответ отправлен пользователю!")
    except Exception as e:
        logger.error(f"Failed to send message to user {user_chat_id}: {e}")
        await message.answer(f"❌ Ошибка отправки сообщения: {e}")
    
    await state.clear()


@router.callback_query(F.data == "admin_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    """Back to admin menu"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    text = (
        "⚙️ Админ-панель\n\n"
        "Выберите действие:"
    )
    
    await callback.message.edit_text(text, reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_payment_settings")
async def show_payment_settings(callback: CallbackQuery):
    """Show payment settings menu"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    text = (
        "⚙️ Настройки оплаты\n\n"
        "Выберите тип карты для настройки реквизитов и инструкций:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Российские карты", callback_data="edit_payment_ru")],
        [InlineKeyboardButton(text="🌍 Международные карты", callback_data="edit_payment_intl")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.in_(["edit_payment_ru", "edit_payment_intl"]))
async def edit_payment_instructions(callback: CallbackQuery, state: FSMContext):
    """Edit payment instructions for specific card type"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    card_type = "ru" if callback.data == "edit_payment_ru" else "intl"
    card_name = "Российские" if card_type == "ru" else "Международные"
    
    async with async_session_maker() as session:
        instr_repo = CardPaymentInstructionRepository(session)
        instruction = await instr_repo.get_or_create(
            card_type=card_type,
            default_text="Переведите указанную сумму на реквизиты ниже и отправьте скриншот чека.",
            default_requisites="2200 0000 2200 0000" if card_type == "ru" else "4111 1111 1111 1111"
        )
    
    text = (
        f"💳 {card_name} карты\n\n"
        f"📝 Текущий текст инструкции:\n{instruction.instruction_text}\n\n"
        f"💳 Текущие реквизиты:\n<code>{instruction.requisites}</code>\n\n"
        "Что хотите изменить?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Изменить текст", callback_data=f"edit_text_{card_type}")],
        [InlineKeyboardButton(text="💳 Изменить реквизиты", callback_data=f"edit_req_{card_type}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_payment_settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("edit_text_"))
async def start_edit_text(callback: CallbackQuery, state: FSMContext):
    """Start editing instruction text"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    card_type = callback.data.split("_")[2]
    await state.update_data(card_type=card_type)
    await state.set_state(AdminStates.waiting_for_instruction_text)
    
    card_name = "российских" if card_type == "ru" else "международных"
    
    text = (
        f"📝 Введите новый текст инструкции для {card_name} карт:\n\n"
        "Этот текст будет показан пользователю после выбора пакета."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_payment_settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(AdminStates.waiting_for_instruction_text)
async def receive_instruction_text(message: Message, state: FSMContext):
    """Receive new instruction text"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    card_type = data.get("card_type")
    
    if not card_type:
        await message.answer("❌ Ошибка: тип карты не найден")
        await state.clear()
        return
    
    new_text = message.text
    
    async with async_session_maker() as session:
        instr_repo = CardPaymentInstructionRepository(session)
        await instr_repo.update(card_type, instruction_text=new_text)
    
    card_name = "российских" if card_type == "ru" else "международных"
    await message.answer(
        f"✅ Текст инструкции для {card_name} карт обновлен!\n\n"
        f"Новый текст:\n{new_text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Вернуться в настройки", callback_data="admin_payment_settings")]
        ])
    )
    
    await state.clear()


@router.callback_query(F.data.startswith("edit_req_"))
async def start_edit_requisites(callback: CallbackQuery, state: FSMContext):
    """Start editing requisites"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    card_type = callback.data.split("_")[2]
    await state.update_data(card_type=card_type)
    await state.set_state(AdminStates.waiting_for_requisites)
    
    card_name = "российских" if card_type == "ru" else "международных"
    
    text = (
        f"💳 Введите новые реквизиты для {card_name} карт:\n\n"
        "Например: 2200 0000 2200 0000\n"
        "Или: Счет Paypal: example@mail.com"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_payment_settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(AdminStates.waiting_for_requisites)
async def receive_requisites(message: Message, state: FSMContext):
    """Receive new requisites"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    card_type = data.get("card_type")
    
    if not card_type:
        await message.answer("❌ Ошибка: тип карты не найден")
        await state.clear()
        return
    
    new_requisites = message.text
    
    async with async_session_maker() as session:
        instr_repo = CardPaymentInstructionRepository(session)
        await instr_repo.update(card_type, requisites=new_requisites)
    
    card_name = "российских" if card_type == "ru" else "международных"
    await message.answer(
        f"✅ Реквизиты для {card_name} карт обновлены!\n\n"
        f"Новые реквизиты:\n<code>{new_requisites}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Вернуться в настройки", callback_data="admin_payment_settings")]
        ]),
        parse_mode="HTML"
    )
    
    await state.clear()


@router.callback_query(F.data == "admin_support_settings")
async def show_support_settings(callback: CallbackQuery):
    """Show support settings"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    async with async_session_maker() as session:
        settings_repo = BotSettingsRepository(session)
        bot_settings = await settings_repo.get_or_create()
    
    text = (
        "📞 Настройки поддержки\n\n"
        f"Текущий контакт: {bot_settings.support_contact}\n\n"
        "Этот контакт отображается в разделе помощи"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить контакт", callback_data="edit_support_contact")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "edit_support_contact")
async def start_edit_support_contact(callback: CallbackQuery, state: FSMContext):
    """Start editing support contact"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_support_contact)
    
    text = (
        "✏️ Введите новый контакт поддержки:\n\n"
        "Например: @support или @your_username\n"
        "Или с t.me: t.me/support"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_support_settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(AdminStates.waiting_for_support_contact)
async def receive_support_contact(message: Message, state: FSMContext):
    """Receive new support contact"""
    if not is_admin(message.from_user.id):
        return
    
    new_contact = message.text.strip()
    
    async with async_session_maker() as session:
        settings_repo = BotSettingsRepository(session)
        await settings_repo.update_support_contact(new_contact)
    
    await message.answer(
        f"✅ Контакт поддержки обновлен!\n\n"
        f"Новый контакт: {new_contact}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Вернуться в настройки", callback_data="admin_support_settings")]
        ])
    )
    
    await state.clear()
