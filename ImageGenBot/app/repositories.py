from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, Transaction, Referral, GenerationTask, CardPaymentRequest, CardPaymentInstruction
from app.config import settings
from datetime import datetime
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_or_create(self, chat_id: int, username: Optional[str] = None, referrer_chat_id: Optional[int] = None) -> User:
        """Get existing user or create new one"""
        result = await self.session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()
        
        if not user:
            is_admin = chat_id in [int(x) for x in str(settings.ADMINS).split(",") if x.strip()]
            
            referrer_id = None
            if referrer_chat_id:
                ref_result = await self.session.execute(
                    select(User).where(User.chat_id == referrer_chat_id)
                )
                referrer = ref_result.scalar_one_or_none()
                if referrer:
                    referrer_id = referrer.id
            
            user = User(
                chat_id=chat_id,
                username=username,
                is_admin=is_admin,
                referrer_id=referrer_id
            )
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
            logger.info(f"New user created: {chat_id}")
        
        return user
    
    async def get_by_chat_id(self, chat_id: int) -> Optional[User]:
        """Get user by chat_id"""
        result = await self.session.execute(select(User).where(User.chat_id == chat_id))
        return result.scalar_one_or_none()
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by internal ID"""
        return await self.session.get(User, user_id)
    
    async def update_balance(self, chat_id: int, amount: int) -> bool:
        """Update user balance"""
        result = await self.session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()
        
        if user:
            user.balance += amount
            user.updated_at = datetime.utcnow()
            await self.session.commit()
            logger.info(f"User {chat_id} balance updated: {amount} (new balance: {user.balance})")
            return True
        return False
    
    async def get_all_users(self) -> List[User]:
        """Get all users"""
        result = await self.session.execute(select(User))
        return result.scalars().all()
    
    async def set_admin(self, chat_id: int, is_admin: bool) -> bool:
        """Set admin status for user"""
        result = await self.session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()
        
        if user:
            user.is_admin = is_admin
            user.updated_at = datetime.utcnow()
            await self.session.commit()
            logger.info(f"User {chat_id} admin status set to: {is_admin}")
            return True
        return False
    
    async def get_all_admins(self) -> List[User]:
        """Get all admin users"""
        result = await self.session.execute(select(User).where(User.is_admin == True))
        return result.scalars().all()


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        user_id: int,
        amount: int,
        reason: str,
        payment_method: Optional[str] = None,
        external_id: Optional[str] = None
    ) -> Transaction:
        """Create new transaction"""
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            reason=reason,
            payment_method=payment_method,
            external_id=external_id
        )
        self.session.add(transaction)
        await self.session.commit()
        await self.session.refresh(transaction)
        logger.info(f"Transaction created: user_id={user_id}, amount={amount}, reason={reason}")
        return transaction
    
    async def get_user_transactions(self, user_id: int) -> List[Transaction]:
        """Get all transactions for user"""
        result = await self.session.execute(
            select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.created_at.desc())
        )
        return result.scalars().all()


class ReferralRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, referrer_id: int, referee_id: int) -> Referral:
        """Create referral relationship"""
        referral = Referral(referrer_id=referrer_id, referee_id=referee_id)
        self.session.add(referral)
        await self.session.commit()
        await self.session.refresh(referral)
        logger.info(f"Referral created: referrer={referrer_id}, referee={referee_id}")
        return referral
    
    async def get_by_referrer(self, referrer_id: int) -> List[Referral]:
        """Get all referrals for referrer"""
        result = await self.session.execute(
            select(Referral).where(Referral.referrer_id == referrer_id)
        )
        return result.scalars().all()
    
    async def update_earned(self, referral_id: int, amount: int) -> bool:
        """Update total earned for referral"""
        result = await self.session.execute(
            select(Referral).where(Referral.id == referral_id)
        )
        referral = result.scalar_one_or_none()
        
        if referral:
            referral.total_earned += amount
            await self.session.commit()
            return True
        return False


class GenerationTaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, user_id: int, task_id: str, photo_id: str) -> GenerationTask:
        """Create new generation task"""
        task = GenerationTask(
            user_id=user_id,
            task_id=task_id,
            photo_telegram_id=photo_id
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        logger.info(f"Generation task created: {task_id}")
        return task
    
    async def get_by_task_id(self, task_id: str) -> Optional[GenerationTask]:
        """Get task by task_id"""
        result = await self.session.execute(
            select(GenerationTask).where(GenerationTask.task_id == task_id)
        )
        return result.scalar_one_or_none()
    
    async def update_status(
        self,
        task_id: str,
        status: str,
        result_url: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update task status"""
        result = await self.session.execute(
            select(GenerationTask).where(GenerationTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if task:
            task.status = status
            if result_url:
                task.result_url = result_url
            if error_message:
                task.error_message = error_message
            if status in ["completed", "failed"]:
                task.completed_at = datetime.utcnow()
            await self.session.commit()
            logger.info(f"Task {task_id} updated: status={status}")
            return True
        return False


class CardPaymentRequestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        user_id: int,
        package_name: str,
        tokens_amount: int,
        card_type: str,
        price_rub: Optional[int] = None,
        price_usd: Optional[int] = None
    ) -> CardPaymentRequest:
        """Create new card payment request"""
        request = CardPaymentRequest(
            user_id=user_id,
            package_name=package_name,
            tokens_amount=tokens_amount,
            card_type=card_type,
            price_rub=price_rub,
            price_usd=price_usd
        )
        self.session.add(request)
        await self.session.commit()
        await self.session.refresh(request)
        logger.info(f"Card payment request created: user_id={user_id}, amount={tokens_amount}")
        return request
    
    async def get_by_id(self, request_id: int) -> Optional[CardPaymentRequest]:
        """Get request by ID"""
        result = await self.session.execute(
            select(CardPaymentRequest).where(CardPaymentRequest.id == request_id)
        )
        return result.scalar_one_or_none()
    
    async def get_pending(self) -> List[CardPaymentRequest]:
        """Get all pending payment requests"""
        result = await self.session.execute(
            select(CardPaymentRequest).where(CardPaymentRequest.status == "pending").order_by(CardPaymentRequest.created_at.desc())
        )
        return result.scalars().all()
    
    async def update_status(self, request_id: int, status: str, admin_response: Optional[str] = None) -> bool:
        """Update request status"""
        result = await self.session.execute(
            select(CardPaymentRequest).where(CardPaymentRequest.id == request_id)
        )
        request = result.scalar_one_or_none()
        
        if request:
            request.status = status
            if admin_response:
                request.admin_response = admin_response
            if status in ["completed", "rejected"]:
                request.completed_at = datetime.utcnow()
            await self.session.commit()
            logger.info(f"Card payment request {request_id} updated: status={status}")
            return True
        return False
    
    async def update_receipt(self, request_id: int, receipt_file_id: str, admin_id: Optional[int] = None) -> bool:
        """Update receipt file_id and admin_id"""
        result = await self.session.execute(
            select(CardPaymentRequest).where(CardPaymentRequest.id == request_id)
        )
        request = result.scalar_one_or_none()
        
        if request:
            request.receipt_file_id = receipt_file_id
            if admin_id:
                request.admin_id = admin_id
            await self.session.commit()
            logger.info(f"Card payment request {request_id} receipt updated")
            return True
        return False


class CardPaymentInstructionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_or_create(self, card_type: str, default_text: str = "", default_requisites: str = "") -> CardPaymentInstruction:
        """Get instruction by card type or create default"""
        result = await self.session.execute(
            select(CardPaymentInstruction).where(CardPaymentInstruction.card_type == card_type)
        )
        instruction = result.scalar_one_or_none()
        
        if not instruction:
            instruction = CardPaymentInstruction(
                card_type=card_type,
                instruction_text=default_text,
                requisites=default_requisites
            )
            self.session.add(instruction)
            await self.session.commit()
            await self.session.refresh(instruction)
            logger.info(f"Card payment instruction created: {card_type}")
        
        return instruction
    
    async def update(self, card_type: str, instruction_text: Optional[str] = None, requisites: Optional[str] = None) -> bool:
        """Update instruction"""
        result = await self.session.execute(
            select(CardPaymentInstruction).where(CardPaymentInstruction.card_type == card_type)
        )
        instruction = result.scalar_one_or_none()
        
        if instruction:
            if instruction_text is not None:
                instruction.instruction_text = instruction_text
            if requisites is not None:
                instruction.requisites = requisites
            instruction.updated_at = datetime.utcnow()
            await self.session.commit()
            logger.info(f"Card payment instruction updated: {card_type}")
            return True
        return False
    
    async def get_all(self) -> List[CardPaymentInstruction]:
        """Get all instructions"""
        result = await self.session.execute(select(CardPaymentInstruction))
        return result.scalars().all()


class BotSettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_or_create(self) -> "BotSettings":
        """Get bot settings or create default"""
        from app.models import BotSettings
        
        result = await self.session.execute(select(BotSettings))
        settings = result.scalar_one_or_none()
        
        if not settings:
            settings = BotSettings(support_contact="@your_support")
            self.session.add(settings)
            await self.session.commit()
            await self.session.refresh(settings)
            logger.info("Bot settings created with defaults")
        
        return settings
    
    async def update_support_contact(self, support_contact: str) -> bool:
        """Update support contact"""
        from app.models import BotSettings
        
        result = await self.session.execute(select(BotSettings))
        settings = result.scalar_one_or_none()
        
        if settings:
            settings.support_contact = support_contact
            settings.updated_at = datetime.utcnow()
            await self.session.commit()
            logger.info(f"Support contact updated: {support_contact}")
            return True
        return False


class CryptoInvoiceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        user_chat_id: int,
        invoice_id: str,
        amount_cents: int,
        currency: str,
        tokens_amount: int,
        pay_url: str
    ) -> "CryptoInvoice":
        """Create crypto invoice"""
        from app.models import CryptoInvoice
        
        invoice = CryptoInvoice(
            user_chat_id=user_chat_id,
            invoice_id=invoice_id,
            amount=amount_cents,
            currency=currency,
            tokens_amount=tokens_amount,
            pay_url=pay_url,
            status="pending"
        )
        self.session.add(invoice)
        await self.session.commit()
        await self.session.refresh(invoice)
        logger.info(f"Crypto invoice created: {invoice_id} for user {user_chat_id}, amount=${amount_cents/100:.2f}")
        return invoice
    
    async def get_by_invoice_id(self, invoice_id: str) -> Optional["CryptoInvoice"]:
        """Get invoice by invoice_id"""
        from app.models import CryptoInvoice
        
        result = await self.session.execute(
            select(CryptoInvoice).where(CryptoInvoice.invoice_id == str(invoice_id))
        )
        return result.scalar_one_or_none()
    
    async def update_status(self, invoice_id: str, status: str) -> bool:
        """Update invoice status"""
        from app.models import CryptoInvoice
        
        result = await self.session.execute(
            select(CryptoInvoice).where(CryptoInvoice.invoice_id == str(invoice_id))
        )
        invoice = result.scalar_one_or_none()
        
        if invoice:
            invoice.status = status
            if status == "paid":
                invoice.paid_at = datetime.utcnow()
            await self.session.commit()
            logger.info(f"Crypto invoice {invoice_id} status updated: {status}")
            return True
        return False
