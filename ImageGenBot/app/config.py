import os
from pydantic_settings import BaseSettings
from typing import List, Optional
import json


class Settings(BaseSettings):
    BOT_TOKEN: str
    ALT_BOT_TOKEN: str
    ADMINS: str
    IMAGE_API_TOKEN: str
    IMAGE_API_URL: str
    CRYPTO_BOT_TOKEN: str
    SQLITE_DATABASE_URL: Optional[str] = None
    USE_WEBHOOK: bool = True
    WEBHOOK_HOST: str = ""
    WEBHOOK_PATH: str = "/webhook/telegram"
    WEBHOOK_SECRET: str = ""
    PRICE_SELL_RUB: str = "35"
    STARS_PACKS: str = '[{"tokens":10,"stars":194,"discount":0},{"tokens":25,"stars":486,"discount":10},{"tokens":50,"stars":972,"discount":15},{"tokens":100,"stars":1944,"discount":20},{"tokens":200,"stars":3889,"discount":25}]'
    REFERRAL_BONUS_TOKENS: str = "2"
    REFERRAL_COMMISSION_PERCENT: str = "10"
    
    @property
    def database_url(self) -> str:
        """Get database URL, prefer SQLITE_DATABASE_URL over DATABASE_URL"""
        if self.SQLITE_DATABASE_URL:
            return self.SQLITE_DATABASE_URL
        return "sqlite+aiosqlite:///./bot.db"
    
    @property
    def admin_ids(self) -> List[int]:
        return [int(x.strip()) for x in self.ADMINS.split(",") if x.strip()]
    
    @property
    def stars_packs_list(self) -> List[dict]:
        try:
            return json.loads(self.STARS_PACKS)
        except:
            return [{"tokens": 10, "stars": 194, "discount": 0}]
    
    @property
    def referral_bonus(self) -> int:
        return int(self.REFERRAL_BONUS_TOKENS)
    
    @property
    def referral_commission(self) -> int:
        return int(self.REFERRAL_COMMISSION_PERCENT)
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
