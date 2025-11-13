import asyncio
import errno
import logging
import os
import sys
from typing import Optional
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import aiohttp
from app.config import settings
from app.database import init_db, async_session_maker
from app.repositories import GenerationTaskRepository


def _normalize_base_url(value: str) -> str:
    """Return https url no trailing slash for provided host or url."""
    value = value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value.rstrip("/")
    return f"https://{value.lstrip('/').rstrip('/')}"


def resolve_public_base_url() -> Optional[str]:
    """
    Determine public base URL for webhooks.
    Priority:
    1. Explicit WEBHOOK_HOST from settings
    2. Replit-specific environment variables (REPLIT_DOMAINS, REPLIT_DEV_DOMAIN, REPL_SLUG/REPL_OWNER)
    """
    if settings.WEBHOOK_HOST:
        return _normalize_base_url(settings.WEBHOOK_HOST)

    candidates = [
        os.getenv("REPLIT_DOMAINS"),
        os.getenv("REPLIT_DEV_DOMAIN"),
    ]

    if not candidates[0]:
        slug = os.getenv("REPL_SLUG")
        owner = os.getenv("REPL_OWNER")
        if slug and owner:
            candidates.append(f"{slug}.{owner}.repl.co")

    for candidate in candidates:
        if not candidate:
            continue
        domain = candidate.split(',')[0].strip()
        if domain:
            return _normalize_base_url(domain)

    return None


def build_webhook_url(base_url: str, path: str) -> str:
    """Join base URL with a path ensuring single slash between them."""
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base_url}{path}"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)


async def send_generation_result(bot: Bot, task_id: str, user_chat_id: int, result_url: Optional[str] = None, error: Optional[str] = None):
    """Send generation result to user"""
    try:
        if result_url:
            is_video = result_url.endswith(('.mp4', '.avi', '.mov', '.webm'))
            
            if is_video:
                video_file = FSInputFile(result_url)
                await bot.send_video(
                    chat_id=user_chat_id,
                    video=video_file,
                    caption="✅ Генерация видео завершена!\n\nОтправьте еще фото или видео для новой генерации."
                )
            else:
                photo_file = FSInputFile(result_url)
                await bot.send_photo(
                    chat_id=user_chat_id,
                    photo=photo_file,
                    caption="✅ Генерация завершена!\n\nОтправьте еще фото или видео для новой генерации."
                )
        elif error:
            await bot.send_message(
                chat_id=user_chat_id,
                text=f"❌ Ошибка генерации:\n{error}\n\nТокен возвращен на баланс."
            )
        else:
            await bot.send_message(
                chat_id=user_chat_id,
                text="❌ Неизвестная ошибка генерации\n\nТокен возвращен на баланс."
            )
    except Exception as e:
        logger.error(f"Failed to send result to user {user_chat_id}: {e}")


async def on_startup(bot: Bot):
    """Execute on bot startup"""
    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    
    if settings.USE_WEBHOOK:
        try:
            current_webhook = await bot.get_webhook_info()
            current_url = current_webhook.url
            production_url = "https://image-gen-bot.replit.app/webhook/telegram"

            if current_url == production_url:
                logger.info(f"✅ Webhook уже на production: {production_url}")
                logger.info(f"📋 Webhook info: {current_webhook}")
            else:
                base_url = resolve_public_base_url()

                if base_url:
                    webhook_url = build_webhook_url(base_url, settings.WEBHOOK_PATH)

                    await bot.delete_webhook(drop_pending_updates=True)
                    logger.info("🗑️ Old webhook deleted")

                    await bot.set_webhook(
                        url=webhook_url,
                        secret_token=settings.WEBHOOK_SECRET,
                        drop_pending_updates=True
                    )
                    logger.info(f"✅ Webhook set: {webhook_url}")

                    webhook_info = await bot.get_webhook_info()
                    logger.info(f"📋 Webhook info: {webhook_info}")
                else:
                    logger.warning("⚠️ Не найден публичный домен. Укажите WEBHOOK_HOST или переменные REPLIT_* для автоконфигурации.")
        except Exception as e:
            logger.error(f"Failed to manage webhook: {e}", exc_info=True)
    else:
        logger.info("Webhook mode disabled")


async def on_shutdown(bot: Bot):
    """Execute on bot shutdown"""
    await bot.delete_webhook()
    logger.info("Bot stopped")


def create_app():
    """Create and configure the application"""
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Create alternative bot and dispatcher for Stars payments
    from aiogram import Bot as AltBot, Dispatcher as AltDp, F
    from aiogram.types import PreCheckoutQuery, Message as AltMessage
    from app.repositories import UserRepository, TransactionRepository
    
    alt_bot = AltBot(
        token=settings.ALT_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    alt_dp = AltDp()
    
    @alt_dp.pre_checkout_query()
    async def alt_pre_checkout(pre_checkout: PreCheckoutQuery):
        await pre_checkout.answer(ok=True)
    
    @alt_dp.message(F.successful_payment)
    async def alt_successful_payment(message: AltMessage):
        payment = message.successful_payment
        new_balance = 0
        try:
            payload_parts = payment.invoice_payload.split("_")
            tokens = int(payload_parts[1])
            user_id = int(payload_parts[2])
            
            async with async_session_maker() as session:
                user_repo = UserRepository(session)
                await user_repo.update_balance(user_id, tokens)
                
                user = await user_repo.get_by_chat_id(user_id)
                if user:
                    tx_repo = TransactionRepository(session)
                    await tx_repo.create(
                        user_id=int(user.id),
                        amount=tokens,
                        reason=f"Покупка через Telegram Stars",
                        payment_method="stars",
                        external_id=payment.telegram_payment_charge_id
                    )
                    
                    from app.services.referral import ReferralService
                    ref_service = ReferralService(session)
                    await ref_service.process_first_purchase(user_id, tokens)
                    
                    new_balance = user.balance
            
            await message.answer(
                f"✅ Оплата успешна!\n\n"
                f"💰 Начислено: {tokens} токенов\n"
                f"💵 Новый баланс: {new_balance} токенов\n\n"
                "Теперь вы можете отправить фото для генерации в основном боте!"
            )
            
            logger.info(f"✅ Stars payment: user={user_id}, tokens={tokens}")
            
        except Exception as e:
            logger.error(f"Error processing Stars payment: {e}")
            await message.answer("Ошибка обработки платежа. Обратитесь в поддержку.")
    
    from app.handlers import start, admin, payment, generate, referral, card_payment
    dp.include_router(start.router)
    dp.include_router(generate.router)
    dp.include_router(admin.router)
    dp.include_router(payment.router)
    dp.include_router(card_payment.router)
    dp.include_router(referral.router)
    
    # Fallback router with lowest priority - runs AFTER all other routers
    from aiogram import Router, F
    from aiogram.types import Message
    fallback_router = Router()
    
    @fallback_router.message()
    async def catch_all_messages(message: Message):
        """Catch all unhandled messages to prevent 'not handled' errors"""
        user_id = message.from_user.id if message.from_user else 0
        logger.info(f"⚠️ Unhandled message from {user_id}: {message.text or message.content_type}")
    
    @fallback_router.callback_query()
    async def catch_all_callbacks(callback):
        """Catch all unhandled callbacks"""
        logger.info(f"⚠️ Unhandled callback from {callback.from_user.id}: {callback.data}")
        await callback.answer()
    
    # Include fallback router LAST with lowest priority
    dp.include_router(fallback_router)
    
    from app.middlewares.admin import AdminMiddleware
    dp.update.middleware(AdminMiddleware())
    
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    app = web.Application()
    
    async def telegram_webhook_wrapper(request):
        """Wrapper for telegram webhook with logging"""
        logger.info(f"📥 Incoming webhook request from {request.remote}")
        logger.info(f"Headers: {dict(request.headers)}")
        body = await request.read()
        logger.info(f"Body size: {len(body)} bytes")

        # Rewind request body for downstream handler
        request._read_bytes = body  # type: ignore[attr-defined]

        # Call the original handler
        webhook_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=settings.WEBHOOK_SECRET
        )
        return await webhook_handler.handle(request)
    
    app.router.add_post(settings.WEBHOOK_PATH, telegram_webhook_wrapper)
    

    async def image_webhook(request):
        """Handle image generation webhook from external API"""
        try:
            logger.info(f"🎨 Image webhook received from {request.remote}")
            logger.info(f"Content-Type: {request.content_type}")

            gen_id = None
            error = None
            content_type = None
            media_entries = []
            selected_media = None

            if request.content_type and 'multipart/form-data' in request.content_type:
                reader = await request.multipart()
                async for field in reader:
                    field_name = field.name
                    logger.info(f"Field: {field_name}")

                    if field_name in ['undressingId', 'id_gen', 'id']:
                        gen_id = await field.text()
                        logger.info(f"Generation ID: {gen_id}")
                    elif field_name in ['image', 'video', 'result_pv']:
                        payload = await field.read()
                        field_content_type = field.headers.get('Content-Type')
                        entry = {
                            "bytes": payload,
                            "content_type": field_content_type,
                            "field": field_name,
                            "filename": getattr(field, 'filename', None)
                        }
                        media_entries.append(entry)
                        logger.info(
                            f"Media chunk received: field={field_name} size={len(payload)} type={field_content_type} filename={entry['filename']}"
                        )
                    elif field_name == 'error':
                        error = await field.text()
                        logger.error(f"API Error: {error}")
                    elif field_name == 'webhook':
                        webhook_url = await field.text()
                        logger.info(f"Webhook URL: {webhook_url}")
            elif request.content_type and 'application/json' in request.content_type:
                body = await request.read()
                import json
                data = json.loads(body)
                logger.info(f"JSON data: {data}")
                gen_id = data.get('id_gen') or data.get('undressingId') or data.get('id')
                error = data.get('error')

                candidate_urls = []
                for key in ['video_url', 'video', 'image_url', 'image']:
                    value = data.get(key)
                    if isinstance(value, str) and value.startswith('http'):
                        candidate_urls.append(value)

                result_list = data.get('result_pv')
                if isinstance(result_list, list):
                    for item in result_list:
                        if isinstance(item, str) and item.startswith('http'):
                            candidate_urls.append(item)

                for url in candidate_urls:
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url) as resp:
                                if resp.status == 200:
                                    payload = await resp.read()
                                    entry = {
                                        "bytes": payload,
                                        "content_type": resp.headers.get('Content-Type'),
                                        "field": 'json',
                                        "filename": url.split('/')[-1]
                                    }
                                    media_entries.append(entry)
                                    logger.info(f"Fetched media from URL: {url}")
                                    break
                    except Exception as fetch_err:
                        logger.error(f"Failed to fetch media from {url}: {fetch_err}")

            if media_entries:
                preferred = [
                    entry for entry in media_entries
                    if (entry.get('field') == 'video')
                    or ((entry.get('content_type') or '').lower().startswith('video'))
                    or ((entry.get('filename') or '').lower().endswith(('.mp4', '.mov', '.avi', '.webm')))
                ]
                selected_media = preferred[0] if preferred else media_entries[0]
                content_type = selected_media.get('content_type')
                if not content_type:
                    filename = (selected_media.get('filename') or '').lower()
                    if filename.endswith(('.mp4', '.mov', '.avi', '.webm')) or selected_media.get('field') == 'video':
                        content_type = 'video/mp4'
                    elif filename.endswith('.png'):
                        content_type = 'image/png'
                    else:
                        content_type = 'image/jpeg'

            logger.info(f"✅ Parsed: gen_id={gen_id}, has_media={bool(selected_media)}, error={error}")

            if gen_id:
                async with async_session_maker() as session:
                    task_repo = GenerationTaskRepository(session)
                    task = await task_repo.get_by_task_id(gen_id)

                    if task:
                        if selected_media:
                            media_bytes = selected_media.get('bytes')
                            filename = selected_media.get('filename') or ''
                            if content_type and 'video' in content_type:
                                file_ext = '.mp4'
                            elif filename:
                                _, ext = os.path.splitext(filename)
                                file_ext = ext or '.jpg'
                            elif content_type and 'png' in content_type:
                                file_ext = '.png'
                            else:
                                file_ext = '.jpg'

                            # 使用适合Windows的临时目录
                            if os.name == 'nt':  # Windows
                                temp_dir = os.path.join(os.environ.get('TEMP', 'C:\\temp'), 'imagegenbot')
                            else:  # Unix-like systems
                                temp_dir = '/tmp'
                            
                            # 确保临时目录存在
                            os.makedirs(temp_dir, exist_ok=True)
                            
                            file_path = os.path.join(temp_dir, f"{gen_id}{file_ext}")
                            with open(file_path, 'wb') as f:
                                f.write(media_bytes)

                            await task_repo.update_status(
                                task_id=gen_id,
                                status="completed",
                                result_url=file_path
                            )

                            from app.repositories import UserRepository
                            user_repo = UserRepository(session)
                            user = await session.get(User, task.user_id)

                            if user:
                                await send_generation_result(
                                    bot=bot,
                                    task_id=gen_id,
                                    user_chat_id=int(user.chat_id),
                                    result_url=file_path
                                )

                            logger.info(f"✅ Generation completed: {gen_id}")
                        elif error:
                            await task_repo.update_status(
                                task_id=gen_id,
                                status="failed",
                                error_message=error
                            )

                            from app.repositories import UserRepository
                            user_repo = UserRepository(session)
                            user = await session.get(User, task.user_id)

                            if user:
                                await user_repo.update_balance(int(user.chat_id), 1)

                                await send_generation_result(
                                    bot=bot,
                                    task_id=gen_id,
                                    user_chat_id=int(user.chat_id),
                                    error=error
                                )

                            logger.error(f"❌ Generation failed: {gen_id} - {error}")

            return web.Response(status=200, text="OK")

        except Exception as e:
            logger.error(f"Webhook error: {e}", exc_info=True)
            return web.Response(status=500, text=str(e))

    async def health(request):
        """Health check endpoint"""
        return web.Response(text="OK", status=200)
    
    async def index(request):
        """Index page"""
        return web.Response(
            text="🤖 Telegram AI Image Generation Bot is running",
            status=200
        )
    
    async def keep_alive_task():
        """Keep-alive task for deployment"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                logger.info("💓 Keep-alive heartbeat")
            except asyncio.CancelledError:
                logger.info("Keep-alive task cancelled")
                break
            except Exception as e:
                logger.error(f"Keep-alive error: {e}")
    
    async def setup_alt_bot_webhook():
        """Setup webhook for alternative Stars bot"""
        from aiogram import Bot as AltBot
        
        alt_bot = AltBot(
            token=settings.ALT_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        try:
            # Check current webhook
            current_webhook = await alt_bot.get_webhook_info()
            production_url = "https://image-gen-bot.replit.app/webhook/telegram_alt"
            
            if current_webhook.url == production_url:
                logger.info(f"✅ Alt bot webhook уже на production: {production_url}")
            else:
                base_url = resolve_public_base_url()

                if base_url:
                    alt_webhook_url = build_webhook_url(base_url, "/webhook/telegram_alt")
                    await alt_bot.delete_webhook(drop_pending_updates=True)
                    await alt_bot.set_webhook(
                        url=alt_webhook_url,
                        secret_token=settings.WEBHOOK_SECRET,
                        drop_pending_updates=True
                    )
                    logger.info(f"✅ Alt bot webhook set: {alt_webhook_url}")
                else:
                    logger.warning("⚠️ Alt bot: публичный домен не найден, webhook не установлен")
        except Exception as e:
            logger.error(f"Failed to setup alt bot webhook: {e}")
        finally:
            await alt_bot.session.close()


    async def log_crypto_webhook_url():
        """Log CryptoBot webhook URL for manual configuration"""
        try:
            base_url = resolve_public_base_url()

            if base_url:
                crypto_webhook_url = build_webhook_url(base_url, "/webhook/crypto")
                logger.info(f"💸 CryptoBot webhook URL: {crypto_webhook_url}")
                logger.info("ℹ️ Configure webhook manually in @CryptoBot -> Crypto Pay -> My Apps -> Webhooks")
            else:
                logger.warning("⚠️ Crypto webhook URL не может быть сформирован без публичного домена")
        except Exception as e:
            logger.error(f"Error logging crypto webhook URL: {e}")


    async def start_background_tasks(app):
        """Start background tasks"""
        app['keep_alive'] = asyncio.create_task(keep_alive_task())
        # Setup alt bot webhook instead of polling
        await setup_alt_bot_webhook()
        # Log CryptoBot webhook URL for manual configuration
        await log_crypto_webhook_url()
    
    async def cleanup_background_tasks(app):
        """Cleanup background tasks"""
        if 'keep_alive' in app:
            app['keep_alive'].cancel()
            try:
                await app['keep_alive']
            except asyncio.CancelledError:
                pass
    
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    async def crypto_webhook(request):
        """Handle CryptoBot webhook for payment notifications"""
        try:
            logger.info(f"💰 CryptoBot webhook received from {request.remote}")
            
            body = await request.json()
            logger.info(f"Crypto webhook data: {body}")
            
            update_type = body.get("update_type")
            payload = body.get("payload")
            
            if update_type == "invoice_paid":
                invoice_id = payload.get("invoice_id")
                logger.info(f"Invoice paid notification: {invoice_id}")
                
                from app.services.crypto_payment import CryptoPaymentService
                crypto_service = CryptoPaymentService()
                
                is_verified = await crypto_service.check_invoice(invoice_id)
                if not is_verified:
                    logger.warning(f"Invoice {invoice_id} verification failed - not paid or doesn't exist")
                    return web.Response(text="Invoice not verified", status=400)
                
                logger.info(f"✅ Invoice {invoice_id} verified as paid")
                
                async with async_session_maker() as session:
                    try:
                        from app.repositories import CryptoInvoiceRepository, UserRepository, TransactionRepository
                        
                        invoice_repo = CryptoInvoiceRepository(session)
                        invoice = await invoice_repo.get_by_invoice_id(str(invoice_id))
                        
                        if not invoice:
                            logger.warning(f"Invoice {invoice_id} not found in database")
                            return web.Response(text="Invoice not found", status=404)
                        
                        if invoice.status == "paid":
                            logger.info(f"Invoice {invoice_id} already processed - preventing double credit")
                            return web.Response(text="OK")
                        
                        user_repo = UserRepository(session)
                        user = await user_repo.get_by_chat_id(invoice.user_chat_id)
                        
                        if not user:
                            logger.error(f"User {invoice.user_chat_id} not found")
                            return web.Response(text="User not found", status=404)
                        
                        await user_repo.update_balance(invoice.user_chat_id, invoice.tokens_amount)
                        logger.info(f"✅ Balance updated: user={invoice.user_chat_id}, tokens={invoice.tokens_amount}")
                        
                        trans_repo = TransactionRepository(session)
                        await trans_repo.create(
                            user_id=user.id,
                            amount=invoice.tokens_amount,
                            reason=f"Покупка через {invoice.currency}",
                            payment_method=f"crypto_{invoice.currency.lower()}",
                            external_id=str(invoice_id)
                        )
                        
                        from app.services.referral import ReferralService
                        ref_service = ReferralService(session)
                        await ref_service.process_first_purchase(user.id, invoice.tokens_amount)
                        logger.info(f"✅ Referral bonuses processed")
                        
                        await invoice_repo.update_status(str(invoice_id), "paid")
                        logger.info(f"✅ Invoice {invoice_id} marked as paid after successful credit")
                        
                        user = await user_repo.get_by_chat_id(invoice.user_chat_id)
                        
                    except Exception as e:
                        logger.error(f"Error processing crypto payment for invoice {invoice_id}: {e}", exc_info=True)
                        await session.rollback()
                        return web.Response(text="Error processing payment", status=500)
                    
                    try:
                        await bot.send_message(
                            invoice.user_chat_id,
                            f"✅ Оплата успешна!\n\n"
                            f"💰 Начислено: {invoice.tokens_amount} токенов\n"
                            f"💵 Новый баланс: {user.balance} токенов\n\n"
                            f"Теперь вы можете отправить фото для генерации!"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user {invoice.user_chat_id}: {e}")
                    
                    logger.info(f"✅ Crypto payment processed: user={invoice.user_chat_id}, tokens={invoice.tokens_amount}")
            
            return web.Response(text="OK")
            
        except Exception as e:
            logger.error(f"Error processing crypto webhook: {e}", exc_info=True)
            return web.Response(text="Error", status=500)
    
    app.router.add_post("/webhook/image_generation", image_webhook)
    app.router.add_post("/webhook/crypto", crypto_webhook)
    app.router.add_get("/health", health)
    app.router.add_get("/", index)
    
    # Setup main bot webhook
    setup_application(app, dp, bot=bot)
    
    # Setup alternative bot webhook on different path
    alt_webhook_handler = SimpleRequestHandler(
        dispatcher=alt_dp,
        bot=alt_bot,
        secret_token=settings.WEBHOOK_SECRET
    )
    alt_webhook_handler.register(app, path="/webhook/telegram_alt")
    
    return app


from app.models import User


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"🚀 Starting bot on port {port}")
    app = create_app()
    reuse_port = sys.platform != "win32"
    try:
        web.run_app(app, host="0.0.0.0", port=port, print=None, reuse_port=reuse_port)
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            logger.error(
                f"❌ Порт {port} уже занят. Остановите процесс, который его использует, "
                f"или задайте свободный порт через переменную окружения PORT."
            )
        else:
            raise

