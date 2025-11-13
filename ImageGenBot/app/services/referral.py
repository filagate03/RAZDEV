from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import UserRepository, ReferralRepository, TransactionRepository
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class ReferralService:
    """Service for referral system management"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.ref_repo = ReferralRepository(session)
        self.tx_repo = TransactionRepository(session)
    
    async def process_referral_signup(self, referee_chat_id: int, referrer_chat_id: int):
        """Process new user signup via referral link"""
        referee = await self.user_repo.get_by_chat_id(referee_chat_id)
        referrer = await self.user_repo.get_by_chat_id(referrer_chat_id)
        
        if referee and referrer and referee.id != referrer.id:
            await self.ref_repo.create(
                referrer_id=referrer.id,
                referee_id=referee.id
            )
            logger.info(f"Referral relationship created: {referrer_chat_id} -> {referee_chat_id}")
    
    async def process_first_purchase(self, buyer_chat_id: int, amount: int):
        """Process first purchase bonus for referee and commission for referrer"""
        buyer = await self.user_repo.get_by_chat_id(buyer_chat_id)
        if not buyer or not buyer.referrer_id:
            return
        
        referrals = await self.ref_repo.get_by_referrer(buyer.referrer_id)
        buyer_referral = None
        for ref in referrals:
            if ref.referee_id == buyer.id:
                buyer_referral = ref
                break
        
        if not buyer_referral or buyer_referral.first_purchase_bonus_given:
            return
        
        bonus_tokens = settings.referral_bonus
        await self.user_repo.update_balance(buyer_chat_id, bonus_tokens)
        await self.tx_repo.create(
            user_id=buyer.id,
            amount=bonus_tokens,
            reason="Бонус за первую покупку по реферальной программе"
        )
        
        commission = int(amount * settings.referral_commission / 100)
        referrer = await self.session.get(User, buyer.referrer_id)
        if referrer:
            await self.user_repo.update_balance(referrer.chat_id, commission)
            await self.tx_repo.create(
                user_id=referrer.id,
                amount=commission,
                reason=f"Комиссия с реферала (первая покупка)"
            )
            await self.ref_repo.update_earned(buyer_referral.id, commission)
        
        buyer_referral.first_purchase_bonus_given = True
        await self.session.commit()
        
        logger.info(f"First purchase processed: buyer={buyer_chat_id}, bonus={bonus_tokens}, commission={commission}")


from app.models import User
