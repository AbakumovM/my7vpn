"""add email to users and auth tables

Revision ID: a1b2c3d4e5f6
Revises: 2d2e832aa2e3
Create Date: 2026-03-28 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "b5a530407867"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # users: добавить email, сделать telegram_id nullable
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.alter_column("users", "telegram_id", existing_type=sa.BigInteger(), nullable=True)

    # otp_codes: таблица для OTP-кодов
    op.create_table(
        "otp_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("code", sa.String(6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean(), default=False, nullable=False),
    )

    # bot_auth_tokens: одноразовые токены из бота
    op.create_table(
        "bot_auth_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean(), default=False, nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("bot_auth_tokens")
    op.drop_table("otp_codes")
    op.alter_column("users", "telegram_id", existing_type=sa.BigInteger(), nullable=False)
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "email")
