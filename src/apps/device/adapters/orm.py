from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.infrastructure.database.base import Base


class DeviceORM(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_name = Column(String, nullable=False)
    vpn_config = Column(String, nullable=True)
    vpn_client_uuid = Column(String(36), nullable=True)
    device_limit = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    user = relationship("UserORM", back_populates="devices")
    subscription = relationship(
        "SubscriptionORM",
        uselist=False,
        back_populates="device",
        cascade="all, delete-orphan",
    )


class SubscriptionORM(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    plan = Column(Integer, nullable=False)
    start_date = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    is_active = Column(Boolean, default=True)
    end_date = Column(DateTime(timezone=True), nullable=False)

    device = relationship("DeviceORM", back_populates="subscription")
    payments = relationship(
        "PaymentORM", back_populates="subscription", cascade="all, delete-orphan"
    )


class PaymentORM(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(
        Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    amount = Column(Integer, nullable=False)
    currency = Column(String, default="RUB")
    payment_date = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    payment_method = Column(String, default="карта", nullable=True)

    subscription = relationship("SubscriptionORM", back_populates="payments")


class PendingPaymentORM(Base):
    __tablename__ = "pending_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_telegram_id = Column(BigInteger, nullable=False)
    action = Column(String(10), nullable=False)  # "new" | "renew"
    device_type = Column(String(20), nullable=False)
    device_name = Column(String(100), nullable=True)  # для renew
    duration = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=False)
    balance_to_deduct = Column(Integer, nullable=False, default=0)
    device_limit = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False)


class UserSubscriptionORM(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan = Column(Integer, nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    device_limit = Column(Integer, nullable=False, default=1, server_default="1")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")

    payments = relationship(
        "UserPaymentORM", back_populates="subscription", cascade="all, delete-orphan"
    )


class UserPaymentORM(Base):
    __tablename__ = "user_payments"

    id = Column(Integer, primary_key=True)
    user_telegram_id = Column(BigInteger, nullable=False, index=True)
    subscription_id = Column(
        Integer, ForeignKey("user_subscriptions.id", ondelete="SET NULL"), nullable=True
    )
    amount = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=False)
    device_limit = Column(Integer, nullable=False, default=1, server_default="1")
    payment_date = Column(DateTime(timezone=True), nullable=False)
    currency = Column(String, default="RUB")
    payment_method = Column(String, default="карта", nullable=True)
    status = Column(String(20), nullable=False, default="success", server_default="success")
    external_id = Column(String, nullable=True)

    subscription = relationship("UserSubscriptionORM", back_populates="payments")


class NotificationLogORM(Base):
    __tablename__ = "notification_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    days_before = Column(Integer, nullable=False)
    sub_end_date = Column(Date, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "days_before", "sub_end_date", name="uq_notification_log"),
    )
