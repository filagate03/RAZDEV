from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.database import async_session_maker
from app.repositories import UserRepository, GenerationTaskRepository, TransactionRepository
from app.services.image_api import ImageGenerationAPI
from app.keyboards.inline import back_to_main_keyboard, buy_tokens_keyboard, generation_styles_keyboard, video_models_keyboard
from app.keyboards.reply import BUTTON_PHOTO, BUTTON_VIDEO
from app.states import GenerationStates, CardPaymentStates
import uuid
import os
import logging
from app.config import settings

logger = logging.getLogger(__name__)
router = Router()


def _normalize_host(value: str) -> str:
    value = value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value.rstrip("/")
    return f"https://{value.lstrip('/').rstrip('/')}"


def resolve_public_webhook_base() -> str:
    """
    Try to determine public base URL for image generation webhooks.
    Priority:
    1. Explicit WEBHOOK_HOST from settings/.env
    2. REPLIT_DOMAINS / REPLIT_DEV_DOMAIN / REPL_SLUG combo
    3. Local fallback http://localhost:8080
    """
    if settings.WEBHOOK_HOST:
        return _normalize_host(settings.WEBHOOK_HOST)

    # Check Replit environment variables
    repl_domains = os.getenv("REPLIT_DOMAINS")
    if repl_domains:
        domain = repl_domains.split(",")[0].strip()
        if domain:
            return _normalize_host(domain)

    repl_dev_domain = os.getenv("REPLIT_DEV_DOMAIN")
    if repl_dev_domain:
        return _normalize_host(repl_dev_domain)

    # Try REPL_SLUG and REPL_OWNER combo
    slug = os.getenv("REPL_SLUG")
    owner = os.getenv("REPL_OWNER")
    if slug and owner:
        return _normalize_host(f"{slug}.{owner}.repl.co")

    # Local fallback for development
    return "http://localhost:8080"


@router.message(F.text == BUTTON_PHOTO)
async def start_photo_generation(message: Message, state: FSMContext):
    """Handle photo generation button from reply keyboard"""
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_chat_id(message.from_user.id)
        
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы. Используйте /start для начала работы с ботом."
            )
            await state.clear()
            return
    
    await state.clear()
    await state.update_data(content_type="photo")
    
    text = (
        "📸 Генерация фото\n\n"
        "Выберите стиль, затем отправьте фото\n"
        "💰 Стоимость: 1 токен = 1 генерация\n\n"
        "Выберите стиль:"
    )
    
    await message.answer(text, reply_markup=generation_styles_keyboard())


@router.message(F.text == BUTTON_VIDEO)
async def start_video_generation(message: Message, state: FSMContext):
    """Handle video generation button - generates VIDEO from PHOTO"""
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_chat_id(message.from_user.id)
        
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы. Используйте /start для начала работы с ботом."
            )
            await state.clear()
            return
    
    await state.clear()
    await state.update_data(content_type="video")
    
    text = (
        "🎬 Генерация видео из фото\n\n"
        "📸 Выберите анимацию, затем отправьте ФОТО\n"
        "🎥 На выходе получите видео с анимацией\n\n"
        "💰 Стоимость: 1 токен = 1 генерация\n"
        "⏱ Обработка занимает 60-120 секунд\n\n"
        "Выберите тип анимации:"
    )
    
    await message.answer(text, reply_markup=video_models_keyboard())


@router.callback_query(F.data.startswith("style_"))
async def select_style(callback: CallbackQuery, state: FSMContext):
    """Select photo undress style"""
    style = callback.data.split("_")[1]
    await state.update_data(style=style, generation_type="photo")
    await state.set_state(GenerationStates.waiting_for_photo)
    
    style_names = {
        "1": "👗 Стиль 1",
        "2": "💃 Стиль 2",
        "3": "👙 Стиль 3",
        "4": "🔥 Стиль 4",
        "5": "✨ Стиль 5"
    }
    
    text = (
        f"✅ Выбран стиль: {style_names.get(style, 'Стиль ' + style)}\n\n"
        "📸 Теперь отправьте фото для обработки\n\n"
        "💰 Стоимость: 1 токен"
    )
    
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await callback.answer("Стиль выбран! Отправьте фото")


@router.callback_query(F.data.startswith("video_model_"))
async def select_video_model(callback: CallbackQuery, state: FSMContext):
    """Select video animation model"""
    model_id = callback.data.replace("video_model_", "")
    await state.update_data(video_model=model_id, generation_type="video")
    await state.set_state(GenerationStates.waiting_for_photo)
    
    text = (
        f"✅ Анимация выбрана!\n\n"
        "📸 Теперь отправьте ФОТО человека\n"
        "🎥 На выходе получите видео с анимацией\n\n"
        "💰 Стоимость: 1 токен"
    )
    
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await callback.answer("Модель выбрана! Отправьте фото")


@router.message(GenerationStates.waiting_for_photo, F.photo)
async def handle_photo_with_style(message: Message, state: FSMContext):
    """Handle photo - for both photo undress and video generation"""
    data = await state.get_data()
    generation_type = data.get("generation_type", "photo")
    style = data.get("style", "1")
    video_model = data.get("video_model")
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_chat_id(message.from_user.id)
        
        if not user:
            await message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
            await state.clear()
            return
        
        if user.balance < 1:
            await message.answer(
                "❌ Недостаточно токенов!\n\n"
                f"💰 Ваш баланс: {user.balance} токенов\n"
                "💵 Стоимость генерации: 1 токен\n\n"
                "Купите токены через меню /start",
                reply_markup=buy_tokens_keyboard()
            )
            await state.clear()
            return
        
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        file_data = await message.bot.download_file(file.file_path)
        photo_bytes = file_data.getvalue()
        
        gen_id = f"gen_{uuid.uuid4().hex[:12]}"
        base_url = resolve_public_webhook_base()
        webhook_url = f"{base_url}/webhook/image_generation"
        
        if generation_type == "video" and video_model:
            progress_msg = await message.answer("🎬 Создаю видео из фото...")
            result = await ImageGenerationAPI.generate_video(
                image_file_data=photo_bytes,
                webhook_url=webhook_url,
                gen_id=gen_id,
                model_id=video_model
            )
            task_desc = f"Генерация видео"
            result_time = "60-120 секунд"
        else:
            progress_msg = await message.answer("⏳ Обрабатываю фото...")
            result = await ImageGenerationAPI.generate_image(
                photo_file_data=photo_bytes,
                webhook_url=webhook_url,
                gen_id=gen_id,
                style=style
            )
            task_desc = f"Генерация изображения (Стиль {style})"
            result_time = "30-90 секунд"
        
        if result:
            task_repo = GenerationTaskRepository(session)
            await task_repo.create(
                user_id=user.id,
                task_id=gen_id,
                photo_id=photo.file_id
            )
            
            await user_repo.update_balance(message.from_user.id, -1)
            
            tx_repo = TransactionRepository(session)
            await tx_repo.create(
                user_id=user.id,
                amount=-1,
                reason=task_desc
            )
            
            await progress_msg.edit_text(
                "✅ Задача создана!\n\n"
                f"⏱ Результат придет через {result_time}\n"
                f"💰 Списано 1 токен\n"
                f"💵 Новый баланс: {user.balance - 1} токенов"
            )
            
            logger.info(f"{task_desc} task created: {gen_id} by user {message.from_user.id}")
        else:
            await progress_msg.edit_text(
                "❌ Ошибка API при создании задачи\n\n"
                "Попробуйте позже или обратитесь в поддержку"
            )
        
        await state.clear()


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    """Handle photo for AI generation"""
    current_state = await state.get_state()
    if current_state == CardPaymentStates.waiting_receipt:
        return
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_chat_id(message.from_user.id)
        
        if not user:
            await message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
            return
        
        if user.balance < 1:
            await message.answer(
                "❌ Недостаточно токенов!\n\n"
                f"💰 Ваш баланс: {user.balance} токенов\n"
                "💵 Стоимость генерации: 1 токен\n\n"
                "Купите токены через меню /start",
                reply_markup=buy_tokens_keyboard()
            )
            return
        
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        file_data = await message.bot.download_file(file.file_path)
        
        gen_id = f"gen_{uuid.uuid4().hex[:12]}"
        
        # Используем правильную функцию для получения базового URL
        base_url = resolve_public_webhook_base()
        webhook_url = f"{base_url}/webhook/image_generation"
        
        progress_msg = await message.answer("⏳ Обрабатываю фото...")
        
        result = await ImageGenerationAPI.generate_image(
            photo_file_data=file_data.read(),
            webhook_url=webhook_url,
            gen_id=gen_id
        )
        
        if result:
            task_repo = GenerationTaskRepository(session)
            await task_repo.create(
                user_id=user.id,
                task_id=gen_id,
                photo_id=photo.file_id
            )
            
            await user_repo.update_balance(message.from_user.id, -1)
            
            tx_repo = TransactionRepository(session)
            await tx_repo.create(
                user_id=user.id,
                amount=-1,
                reason="Генерация изображения"
            )
            
            await progress_msg.edit_text(
                "✅ Задача создана!\n\n"
                "⏱ Результат придет через 30-90 секунд\n"
                f"💰 Списано 1 токен\n"
                f"💵 Новый баланс: {user.balance - 1} токенов"
            )
            
            logger.info(f"Генерация изображения task created: {gen_id} by user {message.from_user.id}")
        else:
            await progress_msg.edit_text(
                "❌ Ошибка API при создании задачи\n\n"
                "Попробуйте позже или обратитесь в поддержку"
            )
        
        await state.clear()

@router.message(F.video)
async def handle_video(message: Message, state: FSMContext):
    """Handle video for AI generation"""
    current_state = await state.get_state()
    if current_state == CardPaymentStates.waiting_receipt:
        return
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_chat_id(message.from_user.id)
        
        if not user:
            await message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
            return
        
        if user.balance < 1:
            await message.answer(
                "❌ Недостаточно токенов!\n\n"
                f"💰 Ваш баланс: {user.balance} токенов\n"
                "💵 Стоимость генерации: 1 токен\n\n"
                "Купите токены через меню /start",
                reply_markup=buy_tokens_keyboard()
            )
            return
        
        video = message.video
        file = await message.bot.get_file(video.file_id)
        file_data = await message.bot.download_file(file.file_path)
        
        gen_id = f"gen_{uuid.uuid4().hex[:12]}"
        
        replit_domain = os.getenv("REPLIT_DEV_DOMAIN")
        if not replit_domain:
            replit_slug = os.getenv("REPL_SLUG")
            replit_owner = os.getenv("REPL_OWNER")
            if replit_slug and replit_owner:
                replit_domain = f"{replit_slug}.{replit_owner}.repl.co"
            else:
                replit_domain = "localhost:8080"
        
        webhook_url = f"https://{replit_domain}/webhook/image_generation"
        
        progress_msg = await message.answer("⏳ Обрабатываю видео...")
        
        result = await ImageGenerationAPI.generate_video(
            video_file_data=file_data.read(),
            webhook_url=webhook_url,
            gen_id=gen_id
        )
        
        if result:
            task_repo = GenerationTaskRepository(session)
            await task_repo.create(
                user_id=user.id,
                task_id=gen_id,
                photo_id=video.file_id
            )
            
            await user_repo.update_balance(message.from_user.id, -1)
            
            tx_repo = TransactionRepository(session)
            await tx_repo.create(
                user_id=user.id,
                amount=-1,
                reason="Генерация видео"
            )
            
            await progress_msg.edit_text(
                "✅ Задача создана!\n\n"
                "⏱ Результат придет через 60-120 секунд\n"
                f"💰 Списано 1 токен\n"
                f"💵 Новый баланс: {user.balance - 1} токенов"
            )
            
            logger.info(f"Video generation task created: {gen_id} by user {message.from_user.id}")
        else:
            await progress_msg.edit_text(
                "❌ Ошибка API при создании задачи\n\n"
                "Попробуйте позже или обратитесь в поддержку"
            )
