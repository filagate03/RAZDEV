import aiohttp
from typing import Optional, Dict
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class ImageGenerationAPI:
    """Service for working with Clothoff.net Image Generation API"""
    
    BASE_URL = settings.IMAGE_API_URL or "https://api.grtkniv.net"
    TOKEN = settings.IMAGE_API_TOKEN
    
    @classmethod
    def _headers(cls):
        return {"Authorization": cls.TOKEN}
    
    @classmethod
    async def generate_image(
        cls,
        photo_file_data: bytes,
        webhook_url: str,
        gen_id: str,
        style: str = "1"
    ) -> Optional[Dict]:
        """
        Send photo for AI generation
        
        Args:
            photo_file_data: Image bytes
            webhook_url: URL for webhook callback
            gen_id: Unique generation ID
            style: Generation style (1-5)
            
        Returns:
            API response dict or None on error
        """
        style_configs = {
            "1": {"bodyType": "skinny", "breastSize": "small", "buttSize": "small", "cloth": "Naked"},
            "2": {"bodyType": "normal", "breastSize": "normal", "buttSize": "normal", "cloth": "Naked"},
            "3": {"bodyType": "muscular", "breastSize": "normal", "buttSize": "normal", "cloth": "Naked"},
            "4": {"bodyType": "curvy", "breastSize": "big", "buttSize": "big", "cloth": "Naked"},
            "5": {"bodyType": "curvy", "breastSize": "big", "buttSize": "big", "cloth": "Naked"}
        }
        
        config = style_configs.get(style, style_configs["1"])
        
        form = aiohttp.FormData()
        form.add_field('image', photo_file_data, filename='photo.jpg', content_type='image/jpeg')
        form.add_field('webhook', webhook_url)
        form.add_field('id_gen', gen_id)
        form.add_field('postGeneration', 'upscale')
        form.add_field('agePeople', '18')
        form.add_field('bodyType', config['bodyType'])
        form.add_field('breastSize', config['breastSize'])
        form.add_field('buttSize', config['buttSize'])
        form.add_field('cloth', config['cloth'])
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{cls.BASE_URL}/api/imageGenerations/undress",
                    headers=cls._headers(),
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"Generation started successfully: {gen_id}")
                        return data
                    else:
                        error_text = await resp.text()
                        logger.error(f"API error {resp.status}: {error_text}")
                        return None
            except aiohttp.ClientError as e:
                logger.error(f"Generation request failed: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error during generation: {e}")
                return None
    
    @classmethod
    async def generate_video(
        cls,
        image_file_data: bytes,
        webhook_url: str,
        gen_id: str,
        model_id: str = "egncvJ0CJemcUX5"
    ) -> Optional[Dict]:
        """
        Generate video from photo using animation model
        
        Args:
            image_file_data: Photo bytes (not video!)
            webhook_url: URL for webhook callback
            gen_id: Unique generation ID
            model_id: Animation model ID from /api/videoGenerations/models
            
        Returns:
            API response dict or None on error
        """
        form = aiohttp.FormData()
        form.add_field('image', image_file_data, filename='photo.jpg', content_type='image/jpeg')
        form.add_field('id_gen', gen_id)
        form.add_field('name', model_id)
        form.add_field('webhook', webhook_url)
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{cls.BASE_URL}/api/videoGenerations/animate",
                    headers=cls._headers(),
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"Video generation started: {gen_id}, model: {model_id}")
                        return data
                    else:
                        error_text = await resp.text()
                        logger.error(f"Video API error {resp.status}: {error_text}")
                        return None
            except aiohttp.ClientError as e:
                logger.error(f"Video generation request failed: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error during video generation: {e}")
                return None
    
    @classmethod
    async def get_video_models(cls) -> Optional[list]:
        """Get available video animation models"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{cls.BASE_URL}/api/videoGenerations/models",
                    headers=cls._headers(),
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.error(f"Video models fetch error: {resp.status}")
                        return None
            except Exception as e:
                logger.error(f"Video models fetch failed: {e}")
                return None
    
    @classmethod
    async def get_collections(cls) -> Optional[Dict]:
        """Get available collections from API"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{cls.BASE_URL}/api/imageGenerations/collections",
                    headers=cls._headers(),
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.error(f"Collections fetch error: {resp.status}")
                        return None
            except Exception as e:
                logger.error(f"Collections fetch failed: {e}")
                return None
