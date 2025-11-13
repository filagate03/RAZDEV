from aiocryptopay import AioCryptoPay, Networks
from app.config import settings
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class CryptoPaymentService:
    """Service for CryptoBot payments"""
    
    def __init__(self):
        self.crypto = AioCryptoPay(
            token=settings.CRYPTO_BOT_TOKEN,
            network=Networks.MAIN_NET
        )
    
    async def create_invoice(
        self,
        amount: float,
        currency: str = "USDT",
        description: str = "Покупка токенов"
    ) -> Optional[Dict]:
        """
        Create payment invoice
        
        Args:
            amount: Payment amount
            currency: Cryptocurrency (USDT, TON, BTC, etc)
            description: Payment description
            
        Returns:
            Dict with invoice_id, pay_url, amount or None on error
        """
        try:
            invoice = await self.crypto.create_invoice(
                asset=currency,
                amount=amount,
                description=description
            )
            logger.info(f"Invoice created: {invoice.invoice_id} for {amount} {currency}")
            return {
                "invoice_id": invoice.invoice_id,
                "pay_url": invoice.bot_invoice_url,
                "amount": invoice.amount,
                "currency": currency
            }
        except Exception as e:
            logger.error(f"Failed to create invoice: {e}")
            return None
    
    async def check_invoice(self, invoice_id: int) -> bool:
        """
        Check if invoice is paid
        
        Args:
            invoice_id: Invoice ID to check
            
        Returns:
            True if paid, False otherwise
        """
        try:
            invoices = await self.crypto.get_invoices(invoice_ids=[invoice_id])
            if invoices and len(invoices) > 0:
                is_paid = invoices[0].status == "paid"
                logger.info(f"Invoice {invoice_id} status: {invoices[0].status}")
                return is_paid
            return False
        except Exception as e:
            logger.error(f"Failed to check invoice: {e}")
            return False
