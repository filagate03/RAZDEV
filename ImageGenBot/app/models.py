from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    balance = Column(Integer, default=0)
    is_admin = Column(Boolean, default=False, index=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    referrals = relationship("Referral", foreign_keys="Referral.referrer_id", back_populates="referrer")
    generation_tasks = relationship("GenerationTask", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer)
    reason = Column(String)
    payment_method = Column(String, nullable=True)
    external_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="transactions")


class Referral(Base):
    __tablename__ = "referrals"
    
    id = Column(Integer, primary_key=True)
    referrer_id = Column(Integer, ForeignKey("users.id"))
    referee_id = Column(Integer, ForeignKey("users.id"))
    total_earned = Column(Integer, default=0)
    first_purchase_bonus_given = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="referrals")


class GenerationTask(Base):
    __tablename__ = "generation_tasks"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(String, unique=True, index=True)
    status = Column(String, default="processing")
    photo_telegram_id = Column(String)
    style = Column(String, nullable=True)
    result_url = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="generation_tasks")


class CardPaymentRequest(Base):
    __tablename__ = "card_payment_requests"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    package_name = Column(String)
    tokens_amount = Column(Integer)
    price_rub = Column(Integer, nullable=True)
    price_usd = Column(Integer, nullable=True)
    card_type = Column(String)
    status = Column(String, default="pending")
    receipt_file_id = Column(String, nullable=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    admin_response = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class CardPaymentInstruction(Base):
    __tablename__ = "card_payment_instructions"
    
    id = Column(Integer, primary_key=True)
    card_type = Column(String, unique=True, nullable=False)
    instruction_text = Column(String, nullable=False)
    requisites = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BotSettings(Base):
    __tablename__ = "bot_settings"
    
    id = Column(Integer, primary_key=True)
    support_contact = Column(String, default="@your_support")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CryptoInvoice(Base):
    __tablename__ = "crypto_invoices"
    
    id = Column(Integer, primary_key=True)
    user_chat_id = Column(BigInteger, nullable=False, index=True)
    invoice_id = Column(String, unique=True, nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)
    tokens_amount = Column(Integer, nullable=False)
    pay_url = Column(String, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
