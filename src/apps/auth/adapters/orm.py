from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from src.infrastructure.database.base import Base


class OtpCodeORM(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False)
    code = Column(String(6), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)


class BotAuthTokenORM(Base):
    __tablename__ = "bot_auth_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
