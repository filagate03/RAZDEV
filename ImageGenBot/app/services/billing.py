from app.config import settings
from typing import Optional, Dict


class BillingService:
    """Service for price calculations and token packages"""
    
    @staticmethod
    def get_stars_package(tokens: int) -> Optional[Dict]:
        """Get Stars package info by token amount"""
        packages = settings.stars_packs_list
        for pack in packages:
            if pack.get("tokens") == tokens:
                return pack
        return None
    
    @staticmethod
    def get_all_packages() -> list:
        """Get all available Stars packages"""
        return settings.stars_packs_list
    
    @staticmethod
    def calculate_discount(tokens: int) -> int:
        """Calculate discount percentage for token amount"""
        pack = BillingService.get_stars_package(tokens)
        return pack.get("discount", 0) if pack else 0
    
    @staticmethod
    def calculate_referral_bonus(amount: int) -> int:
        """Calculate referral commission from purchase"""
        return int(amount * settings.referral_commission / 100)
