from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from app.database import async_session_maker
from app.repositories import UserRepository, TransactionRepository
from app.services.crypto_payment import CryptoPaymentService
from app.services.billing import BillingService
from app.services.referral import ReferralService
from app.keyboards.inline import buy_tokens_keyboard, crypto_payment_keyboard, back_to_main_keyboard
from app.keyboards.reply import BUTTON_BUY_TOKENS
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == BUTTON_BUY_TOKENS)
async def show_buy_menu_message(message: Message):
    """Show buy tokens menu (from reply keyboard button)"""
    text = (
        "💰 Покупка токенов\n\n"
        "Выберите пакет:\n"
    )
    
    packages = BillingService.get_all_packages()
    for pack in packages:
        discount_text = f" (-{pack['discount']}%)" if pack.get('discount', 0) > 0 else ""
        text += f"• {pack['tokens']} токенов = {pack['stars']} Stars{discount_text}\n"
    
    text += "\n💎 Также доступна оплата криптовалютой и картой"
    
    await message.answer(text, reply_markup=buy_tokens_keyboard())


@router.message(Command("buy"))
@router.callback_query(F.data == "buy_menu")
async def show_buy_menu(event):
    """Show buy tokens menu"""
    text = (
        "💰 Покупка токенов\n\n"
        "Выберите пакет:\n"
    )
    
    packages = BillingService.get_all_packages()
    for pack in packages:
        discount_text = f" (-{pack['discount']}%)" if pack.get('discount', 0) > 0 else ""
        text += f"• {pack['tokens']} токенов = {pack['stars']} Stars{discount_text}\n"
    
    text += "\n💎 Также доступна оплата криптовалютой"
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=buy_tokens_keyboard())
    else:
        await event.message.edit_text(text, reply_markup=buy_tokens_keyboard())
        await event.answer()




@router.callback_query(F.data == "buy_crypto_menu")
async def show_crypto_menu(callback: CallbackQuery):
    """Show crypto payment menu - choose currency"""
    text = (
        "💎 Оплата криптовалютой\n\n"
        "Выберите валюту для оплаты:"
    )
    
    await callback.message.edit_text(text, reply_markup=crypto_payment_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("crypto_currency_"))
async def show_crypto_packages(callback: CallbackQuery):
    """Show packages for selected crypto currency"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    parts = callback.data.split("_")
    currency = parts[2].upper()
    
    currency_names = {
        "USDT": "💵 USDT (TRC-20)",
        "TON": "💎 TON",
        "BTC": "₿ Bitcoin"
    }
    
    text = (
        f"💎 Оплата через {currency_names.get(currency, currency)}\n\n"
        "Выберите пакет токенов:\n"
    )
    
    packages = BillingService.get_all_packages()
    buttons = []
    
    for pack in packages:
        tokens = pack["tokens"]
        stars = pack["stars"]
        price_usd = round(stars * 0.015, 2)
        discount = pack.get("discount", 0)
        
        btn_text = f"💎 {tokens} токенов (${price_usd:.2f}"
        if discount > 0:
            btn_text += f", -{discount}%"
        btn_text += ")"
        
        buttons.append([InlineKeyboardButton(
            text=btn_text,
            callback_data=f"crypto_buy_{currency}_{tokens}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="buy_crypto_menu"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("crypto_buy_"))
async def create_crypto_invoice(callback: CallbackQuery):
    """Create crypto payment invoice"""
    try:
        parts = callback.data.split("_")
        currency = parts[2]
        tokens = int(parts[3])
        
        package = BillingService.get_stars_package(tokens)
        if not package:
            await callback.answer("Пакет не найден", show_alert=True)
            return
        
        price_usd = round(package["stars"] * 0.015, 2)
        amount_cents = int(price_usd * 100)
        
        crypto_service = CryptoPaymentService()
        invoice_data = await crypto_service.create_invoice(
            amount=price_usd,
            currency=currency,
            description=f"Покупка {tokens} токенов для AI-генерации"
        )
        
        if not invoice_data:
            await callback.message.edit_text(
                "❌ Ошибка API при создании задачи\n\n"
                "Попробуйте позже или обратитесь в поддержку",
                reply_markup=back_to_main_keyboard()
            )
            await callback.answer("Ошибка создания платежа", show_alert=True)
            return
        
        async with async_session_maker() as session:
            from app.repositories import CryptoInvoiceRepository
            invoice_repo = CryptoInvoiceRepository(session)
            await invoice_repo.create(
                user_chat_id=callback.from_user.id,
                invoice_id=invoice_data["invoice_id"],
                amount_cents=amount_cents,
                currency=currency,
                tokens_amount=tokens,
                pay_url=invoice_data["pay_url"]
            )
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить ${price_usd}", url=invoice_data["pay_url"])],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="buy_crypto_menu")]
        ])
        
        currency_symbols = {"USDT": "💵 USDT", "TON": "💎 TON", "BTC": "₿ BTC"}
        
        await callback.message.edit_text(
            f"{currency_symbols.get(currency, currency)} Оплата криптовалютой\n\n"
            f"📦 Пакет: {tokens} токенов\n"
            f"💰 Сумма: ${price_usd}\n"
            f"💳 Валюта: {currency}\n\n"
            f"Нажмите кнопку ниже для оплаты.\n"
            f"После оплаты токены будут начислены автоматически.",
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error creating crypto invoice: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "buy_stars_alt_menu")
async def show_stars_alt_menu(callback: CallbackQuery):
    """Show alternative Stars payment menu"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    text = (
        "⭐ Оплата Telegram Stars\n\n"
        "Выберите пакет токенов для оплаты через альтернативный бот:\n"
    )
    
    packages = BillingService.get_all_packages()
    buttons = []
    
    for pack in packages:
        tokens = pack["tokens"]
        stars = pack["stars"]
        discount = pack.get("discount", 0)
        
        btn_text = f"⭐️ {tokens} токенов ({stars} Stars"
        if discount > 0:
            btn_text += f", -{discount}%"
        btn_text += ")"
        
        buttons.append([InlineKeyboardButton(
            text=btn_text,
            callback_data=f"buy_stars_alt_{tokens}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="buy_menu"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("buy_stars_alt_"))
async def buy_stars_alt_package(callback: CallbackQuery):
    """Create invoice link using alternative bot for Stars payment"""
    try:
        tokens = int(callback.data.split("_")[3])
        package = BillingService.get_stars_package(tokens)
        
        if not package:
            await callback.answer("Пакет не найден", show_alert=True)
            return
        
        stars = package["stars"]
        
        # Create invoice link using ALTERNATIVE bot (ALT_BOT_TOKEN)
        import aiohttp
        from app.config import settings
        
        bot_token = settings.ALT_BOT_TOKEN
        
        invoice_data = {
            "title": f"Покупка {tokens} токенов",
            "description": f"Пакет токенов для AI-генерации изображений и видео",
            "payload": f"tokens_{tokens}_{callback.from_user.id}",
            "provider_token": "",
            "currency": "XTR",
            "prices": [{"label": f"{tokens} токенов", "amount": stars}]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api.telegram.org/bot{bot_token}/createInvoiceLink",
                json=invoice_data
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("ok"):
                        invoice_link = data["result"]
                        
                        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="⭐ Оплатить Stars", url=invoice_link)],
                            [InlineKeyboardButton(text="◀️ Назад", callback_data="buy_stars_alt_menu")]
                        ])
                        
                        await callback.message.edit_text(
                            f"⭐ Оплата {tokens} токенов\n\n"
                            f"💰 Стоимость: {stars} Stars\n\n"
                            "Нажмите кнопку ниже для оплаты:",
                            reply_markup=keyboard
                        )
                        await callback.answer()
                    else:
                        logger.error(f"Failed to create invoice link: {data}")
                        await callback.answer("Ошибка создания ссылки на оплату", show_alert=True)
                else:
                    logger.error(f"API error creating invoice link: {resp.status}")
                    await callback.answer("Ошибка API", show_alert=True)
                    
    except Exception as e:
        logger.error(f"Error creating alternative invoice: {e}", exc_info=True)
        await callback.answer("Ошибка создания счета", show_alert=True)
