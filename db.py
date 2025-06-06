import os
import asyncpg
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import (
    DECIMAL,
    TIMESTAMP,
    Boolean,
    Column,
    DateTime,
    Integer,
    BigInteger,
    Interval,
    Numeric,
    String,
    Date,
    ForeignKey,
    create_engine,
    func,
)
from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from dotenv import load_dotenv

load_dotenv(".env")

DATABASE_URL = os.getenv("DATABASE_URL")
Base = declarative_base()

# Создаем движок и сессию
if not os.getenv("ALEMBIC_RUNNING"):
    engine = create_async_engine(DATABASE_URL, echo=True)
    AsyncSessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )


class SubscriptionStatus(str, Enum):
    active = "active"
    expired = "expired"
    pending = "pending"


class ActualTariff:
    month_1 = 150
    month_3 = 400
    month_6 = 700
    month_12 = 1200


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    created_at = Column(Date, default=datetime.now(timezone.utc))
    referral_code = Column(String, nullable=True)
    referred_by = Column(Integer, nullable=True, default=None)
    balance = Column(Integer, default=0)
    free_months = Column(Boolean, default=False)
    devices = relationship(
        "Device", back_populates="user", cascade="all, delete-orphan"
    )


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    device_name = Column(String, nullable=False)  # Название устройства
    vpn_config = Column(String, nullable=True)  # Конфигурация для подключения
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    user = relationship("User", back_populates="devices")
    subscription = relationship(
        "Subscription",
        uselist=False,
        back_populates="device",
        cascade="all, delete-orphan",
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    device_id = Column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    plan = Column(Integer, nullable=False)  # 1, 3, 6, 12 месяцев
    start_date = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    end_date = Column(DateTime(timezone=True), nullable=False)
    device = relationship("Device", back_populates="subscription")
    payments = relationship(
        "Payment", back_populates="subscription", cascade="all, delete-orphan"
    )


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(
        Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    amount = Column(Integer, nullable=False)
    currency = Column(String, default="RUB")
    payment_date = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    payment_method = Column(
        String, default="карта", nullable=True
    )  # YooMoney, карта и т.д.

    subscription = relationship("Subscription", back_populates="payments")
