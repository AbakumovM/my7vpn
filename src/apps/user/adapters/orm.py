from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, Date, Integer, String
from sqlalchemy.orm import relationship

from src.infrastructure.database.base import Base


class UserORM(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    created_at = Column(Date, default=lambda: datetime.now(timezone.utc).date())
    referral_code = Column(String, nullable=True)
    referred_by = Column(BigInteger, nullable=True, default=None)
    balance = Column(Integer, default=0)
    free_months = Column(Boolean, default=False)
    devices = relationship(
        "DeviceORM", back_populates="user", cascade="all, delete-orphan"
    )
