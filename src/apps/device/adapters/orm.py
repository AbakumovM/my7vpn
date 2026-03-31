from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from src.infrastructure.database.base import Base


class DeviceORM(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_name = Column(String, nullable=False)
    vpn_config = Column(String, nullable=True)
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
