from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update
from app.config import settings


class AdminMiddleware(BaseMiddleware):
    """Middleware to check admin rights"""
    
    def _is_admin(self, chat_id: int) -> bool:
        """Check if user is admin"""
        try:
            admin_ids = [int(admin_id) for admin_id in settings.ADMINS.split(",") if admin_id.strip()]
            return chat_id in admin_ids
        except:
            return False
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if user:
            data["is_admin"] = self._is_admin(user.id)
        else:
            data["is_admin"] = False
        
        return await handler(event, data)
